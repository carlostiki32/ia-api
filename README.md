# ia-api — Documentación maestra

API que recibe los datos estructurados de un examen optométrico (refracción, AKR/queratometría, hallazgos clínicos) y devuelve un párrafo de **impresión clínica en español**, generado combinando reglas clínicas deterministas con un LLM.

Este documento es el punto de entrada. Da la vista completa del sistema de forma resumida y enlaza a los documentos de detalle para cada tema.

---

## Índice

1. [¿Esto respeta mi flujo original?](#1-esto-respeta-mi-flujo-original)
2. [Arquitectura en un vistazo](#2-arquitectura-en-un-vistazo)
3. [Mapa del proyecto](#3-mapa-del-proyecto)
4. [Puesta en marcha rápida](#4-puesta-en-marcha-rápida)
5. [Probar con Postman](#5-probar-con-postman)
6. [Endpoints](#6-endpoints)
7. [Casos optométricos (correlaciones clínicas)](#7-casos-optométricos-correlaciones-clínicas)
8. [Cómo agregar un caso optométrico nuevo](#8-cómo-agregar-un-caso-optométrico-nuevo)
9. [Configuración (`.env`)](#9-configuración-env)
10. [Mapa completo de documentación](#10-mapa-completo-de-documentación)

---

## 1. ¿Esto respeta mi flujo original?

**Sí, tal cual.** El flujo que tenías en mente sigue siendo el modo por defecto y el más simple de operar:

```
PC Ubuntu con GPU
  └─ ollama serve                  (ya tienes qwen3.5:9b descargado)
       └─ uvicorn app.main:app     (levanta esta API en ese mismo Ubuntu)
            └─ Postman             (haces requests HTTP a esa API)
```

Nada de la arquitectura actual agrega un servicio adicional obligatorio. Todo — validación, reglas clínicas, armado de prompt, llamada a Ollama, limpieza del texto — corre **dentro del mismo proceso de FastAPI**. Lo único "nuevo" respecto a lo que imaginabas:

- **NVIDIA NIM es 100% opcional** (`WEB_INFERENCE=true` en `.env`). Con el default `false`, el sistema nunca sale a internet: todo pasa por tu Ollama local. Ver [§9](#9-configuración-env).
- Las reglas clínicas (antes un archivo único `correlaciones.py`) ahora viven en un **paquete** `app/correlaciones/` dividido por dominio clínico. Esto no cambia el deployment, solo organiza el código.
- Hay una **cola de concurrencia** (`MAX_CONCURRENT=1`) porque tu GPU solo puede correr una inferencia a la vez — evita que dos requests de Postman simultáneos truenen la VRAM.
- Hay un **cache en memoria** que evita volver a llamar a Ollama si mandas el mismo caso dos veces.

Para el paso a paso completo de instalación en Ubuntu (drivers Nvidia, Ollama, `.venv`, `.env`, script de arranque) ver **[INSTALACION_UBUNTU_24.md](INSTALACION_UBUNTU_24.md)**.

---

## 2. Arquitectura en un vistazo

```
Postman / SaaS (Laravel)
   │  POST /inferencia/impresion-clinica
   │  Header: Authorization: Bearer <API_KEY>
   ▼
FastAPI (uvicorn) ─ app/main.py
   │  valida Bearer token
   │  valida el payload (Pydantic) ─ app/schemas.py
   │  valida que haya datos clínicos mínimos ─ app/clinical_data.py
   │  busca en cache (hash SHA-256 del payload) ─ app/cache.py
   │  si no hay cache: entra a la cola de concurrencia (máx. 1 inferencia a la vez)
   ▼
Capa determinista ─ app/correlaciones/
   │  evalúa 41 reglas clínicas fijas sobre el payload (sin LLM, 100% reproducible)
   │  produce una lista de hechos clínicos ya redactados
   ▼
Construcción del prompt ─ app/prompt_builder.py
   │  arma el system prompt (reglas de redacción) y el user prompt
   │  (contexto del paciente, refracción, AKR/queratometría, hallazgos, correlaciones activas)
   ▼
Inferencia ─ app/inference.py
   │
   ├─ WEB_INFERENCE=false (tu flujo estándar)
   │     └─ app/providers/ollama.py → Ollama local → modelo qwen3.5:9b
   │
   └─ WEB_INFERENCE=true (opcional)
         └─ app/providers/nvidia.py → NVIDIA NIM (DeepSeek V3.2)
               └─ si falla (timeout/5xx/429) → fallback automático a Ollama
   ▼
Postprocesado ─ limpia <think>, listas y fences; arma un solo párrafo;
                agrega la recomendación de seguimiento al final
   ▼
Respuesta JSON → Postman / SaaS
```

Dos capas separadas a propósito:

- **Determinista (Python puro):** decide *si* una correlación clínica aplica. Mismo input → mismo resultado, siempre. Cubierta por tests "golden" que congelan el texto exacto de cada regla.
- **Generativa (LLM):** solo redacta el párrafo final integrando esos hechos ya decididos. El modelo **nunca** decide una correlación clínica, solo la integra a la prosa.

Detalle línea por línea de este flujo (headers, timeouts, reintentos, formato exacto del prompt): **[PIPELINE_LLM.md](PIPELINE_LLM.md)**.

---

## 3. Mapa del proyecto

| Ruta | Qué hace (resumen) |
|---|---|
| `app/main.py` | Define la API FastAPI: endpoint principal, auth Bearer, cola/semáforo de concurrencia, `/health`, warmup del modelo al arrancar. |
| `app/config.py` | Todas las variables de configuración (`Settings`, vía `pydantic-settings`), leídas de `.env`. También configura logging a consola + `logs/inference.log`. |
| `app/schemas.py` | Modelos Pydantic del payload de entrada (`ImpresionClinicaRequest` y sub-modelos). Refleja el catálogo real del SaaS (dropdowns, enums, rangos) con **coerción tolerante**: un valor fuera de catálogo se descarta o normaliza (no tumba el request con `422`). Mapeo campo-por-campo en [DICCIONARIO_DATOS_RECETA.md](DICCIONARIO_DATOS_RECETA.md). |
| `app/clinical_data.py` | Un solo chequeo: `has_clinical_data(req)` — rechaza payloads sin refracción ni datos clínicos. |
| `app/correlaciones/` | **El motor de casos optométricos.** Paquete con las 41 reglas clínicas, organizadas por dominio. Ver [§7](#7-casos-optométricos-correlaciones-clínicas). |
| `app/prompt_builder.py` | Arma el system prompt y el user prompt que se le mandan al LLM, a partir del payload + las correlaciones activas. |
| `app/inference.py` | Orquesta la llamada al proveedor de LLM activo (Ollama u/o NVIDIA), aplica fallback, y hace el postprocesado del texto crudo. |
| `app/providers/ollama.py` | Cliente HTTP hacia Ollama (`/api/chat`), parámetros de sampling, reintentos, validación de contexto. |
| `app/providers/nvidia.py` | Cliente hacia NVIDIA NIM (SDK `openai`), solo se usa si `WEB_INFERENCE=true`. |
| `app/cache.py` | Cache en memoria (TTL + tamaño máximo) para no repetir inferencias idénticas. |
| `tests/` | Suite de pytest: correlaciones (incluye golden tests de texto exacto), prompt builder, schemas, inferencia, endpoint principal. |
| `start_linux.sh` | Script de arranque para Ubuntu: valida `.env`, levanta Ollama si hace falta, descarga el modelo si falta, activa el venv, corre uvicorn. |
| `.env` / `.env.example` | Configuración real / plantilla. Ver [§9](#9-configuración-env). |

---

## 4. Puesta en marcha rápida

En tu PC Ubuntu (con Ollama y `qwen3.5:9b` ya listos):

```bash
cd ia-api
source .venv/bin/activate      # o venv/bin/activate según cómo lo creaste
cp .env.example .env           # si aún no existe
# edita .env: define API_KEY con un token real
./start_linux.sh
```

Esto valida `.env`, confirma que Ollama responde, revisa que el modelo esté descargado y levanta uvicorn en `HOST:PORT` (default `0.0.0.0:8888`).

Verificación rápida:

```bash
curl http://localhost:8888/health
```

Guía completa (drivers Nvidia, instalación de Ollama, troubleshooting): **[INSTALACION_UBUNTU_24.md](INSTALACION_UBUNTU_24.md)**.

---

## 5. Probar con Postman

- **Método:** `POST`
- **URL:** `http://<ip-de-tu-ubuntu>:8888/inferencia/impresion-clinica`
- **Headers:**
  - `Authorization: Bearer <el mismo valor que API_KEY en tu .env>`
  - `Content-Type: application/json`
- **Body (raw JSON):** un payload con al menos `refraccion` o `clinica` con algún valor. Ejemplo completo listo para copiar en **[INSTALACION_UBUNTU_24.md, sección 11](INSTALACION_UBUNTU_24.md#11-comandos-de-uso-diario)**.

Respuesta esperada:

```json
{
  "status": "ok",
  "impresion_clinica": "El paciente ...",
  "provider": "ollama",
  "correlaciones_activadas": ["fondo_periferico_riesgo", "av_cc_limitada"]
}
```

- `provider` te dice si respondió Ollama o NVIDIA.
- `correlaciones_activadas` te dice qué reglas clínicas se dispararon con ese caso (útil para depurar por qué el texto dice lo que dice).
- Si mandas el mismo caso dos veces, la segunda respuesta trae `"cached": true` y no toca la GPU.

---

## 6. Endpoints

| Endpoint | Método | Auth | Qué hace |
|---|---|---|---|
| `/inferencia/impresion-clinica` | `POST` | Bearer | Endpoint principal. Recibe el examen, devuelve la impresión clínica. |
| `/health` | `GET` | No | Estado de Ollama/NVIDIA, si el modelo está descargado y cargado en VRAM, y profundidad de la cola de concurrencia. |

Errores más comunes: `401` (token inválido), `422` (payload **sin datos clínicos** — un valor fuera de catálogo ya no genera `422`: se descarta o normaliza por coerción tolerante), `503` (cola llena), `504` (timeout de inferencia), `413` (prompt excede el contexto del modelo). Detalle y causas en [PIPELINE_LLM.md §3](PIPELINE_LLM.md#3-endpoint-autenticacion-y-control-de-carga) e [INSTALACION_UBUNTU_24.md §12](INSTALACION_UBUNTU_24.md#12-problemas-comunes).

---

## 7. Casos optométricos (correlaciones clínicas)

Un "caso optométrico" en este sistema es una **correlación clínica**: una regla fija que dice *"si el examen tiene tales valores, entonces hay tal hallazgo clínico relevante"*. Por ejemplo: si la agudeza visual con corrección está muy reducida, o si el fondo de ojo describe un hallazgo de riesgo periférico, el sistema agrega ese hecho al prompt antes de que el LLM redacte el párrafo.

**Dónde viven:** paquete [`app/correlaciones/`](app/correlaciones/), un módulo por dominio clínico:

| Módulo | Dominio |
|---|---|
| `fondo_de_ojo.py` | Hallazgos de fondo de ojo (glaucoma, DMAE, vascular, periférico...) |
| `refractivas.py` | Miopía magna, hipermetropía alta, anisometropía, AV limitada... |
| `akr.py` | Correlación entre autorrefractómetro y refracción final |
| `corneal.py` | Queratocono/ectasia y astigmatismo corneal vs refractivo (queratometría como disparador) |
| `anexos_cristalino.py` | Anexos oculares, opacidad de cristalino |
| `pupilas_motilidad.py` | Reflejos pupilares, motilidad ocular |
| `campos_amsler.py` | Campos visuales, rejilla de Amsler |
| `binocularidad.py` | Cover test, PPC, forias/tropias |
| `superficie_ocular.py` | BUT (ojo seco) |
| `contexto.py` | Edad, ocupación, motivo de consulta (screening, CVS, presbicia) |
| `registry.py` | **Ensambla las 41 en orden fijo** y expone `evaluar_correlaciones` / `nombres_correlaciones_activas` |
| `base.py`, `texto.py`, `refraccion_utils.py`, `queratometria.py` | Helpers compartidos (memoización, normalización de texto, cálculos clínicos) |

Cada regla es determinista: no la decide el LLM, la decide Python. El LLM solo la redacta.

**Catálogo clínico completo** (qué dispara cada una de las 41, con el fundamento clínico/evidencia detrás de cada una): **[CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md)** — este es el documento que le sirve tanto al optometrista (para entender qué campo activa qué hallazgo) como al equipo técnico.

---

## 8. Cómo agregar un caso optométrico nuevo

1. Abre el módulo de dominio correspondiente en `app/correlaciones/` (o crea uno nuevo si el dominio no existe todavía).
2. Escribe dos funciones:
   - `_cond_x(req) -> bool` — decide si la regla aplica.
   - `_texto_x(req) -> str` — el texto clínico que se agrega al prompt si aplica.
3. Regístrala en `app/correlaciones/registry.py`, agregando `Correlacion("nombre_unico", _cond_x, _texto_x)` a la lista `CORRELACIONES`, en la posición correcta según prioridad clínica (los hallazgos urgentes van primero — el orden de esa lista es el orden en que aparecen en el párrafo final).
4. Si tu regla depende de texto libre (fondo de ojo, motilidad, etc.), revisa los helpers de `texto.py` para normalización y ventana de negación ("sin desgarros" no debe disparar la regla de "desgarro").
5. Agrega un test **golden** en `tests/test_correlaciones_golden.py` que fije el texto exacto de tu regla nueva (obligatorio — hay un test que falla si te falta) y actualiza el conteo esperado de correlaciones en `tests/test_correlaciones.py`.
6. Documenta la regla (campos que la disparan, umbral, fundamento clínico) en `CORRELACIONES_CLINICAS.md`.

Paso a paso con más contexto de arquitectura: [PIPELINE_LLM.md §14](PIPELINE_LLM.md#14-como-extender-el-sistema).

---

## 9. Configuración (`.env`)

Las variables completas con explicación de cada una están en **[INSTALACION_UBUNTU_24.md §5](INSTALACION_UBUNTU_24.md#5-crear-el-archivo-env)**. Las que más te importan para tu flujo:

| Variable | Para qué |
|---|---|
| `OLLAMA_URL` | Dónde vive tu Ollama (default `http://localhost:11434`, correcto si la API corre en el mismo Ubuntu). |
| `OLLAMA_MODEL` | El modelo a usar — déjalo en `qwen3.5:9b`. |
| `API_KEY` | El token que Postman debe mandar en `Authorization: Bearer`. **Cámbialo del placeholder.** |
| `HOST` / `PORT` | Dónde escucha uvicorn (default `0.0.0.0:8888`, para que Postman le pueda pegar desde otra máquina en tu red). |
| `WEB_INFERENCE` | `false` = solo Ollama local (tu flujo). `true` = agrega NVIDIA NIM como principal con Ollama de respaldo. |
| `MAX_CONCURRENT` | Déjalo en `1` — tu GPU procesa una inferencia a la vez. |

---

## 10. Mapa completo de documentación

| Documento | Para qué sirve |
|---|---|
| **README.md** (este archivo) | Punto de entrada: arquitectura, flujo Ubuntu/Ollama/Postman, dónde está cada cosa. |
| [PIPELINE_LLM.md](PIPELINE_LLM.md) | Detalle técnico línea por línea del pipeline: schema completo, construcción del prompt, proveedores, cache, cómo extender el sistema. |
| [CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md) | Catálogo clínico de las 41 correlaciones: qué las dispara y por qué, con evidencia. |
| [DICCIONARIO_DATOS_RECETA.md](DICCIONARIO_DATOS_RECETA.md) | Diccionario de datos del SaaS: catálogo real (dropdowns, enums, rangos, texto libre) de cada campo del payload y afinación del schema a esas limitantes. |
| [VERIFICACION_CORRELACIONES_VS_INVESTIGACION.md](VERIFICACION_CORRELACIONES_VS_INVESTIGACION.md) | Auditoría 41/41: cada correlación vs la investigación clínica, y seguridad de la afinación al catálogo. |
| [INSTALACION_UBUNTU_24.md](INSTALACION_UBUNTU_24.md) | Instalación desde cero en Ubuntu 24.04: drivers Nvidia, Ollama, entorno virtual, `.env`, script de arranque, troubleshooting. |
| [HALLAZGOS_QWEN3.5.md](HALLAZGOS_QWEN3.5.md) | Registro histórico de auditoría contra la documentación oficial de Qwen3.5 — por qué los parámetros de sampling son los que son. |
| [.claude/skills/qwen-inference/](.claude/skills/qwen-inference/) | Referencia técnica de Qwen3.5 usada como fuente para los parámetros de inferencia. |
