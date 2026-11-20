# ia-api — Documentación maestra

API que recibe los datos estructurados de un examen optométrico (refracción, AKR/queratometría, hallazgos clínicos) y devuelve un párrafo de **impresión clínica en español**, generado combinando reglas clínicas deterministas con un LLM.

Desde W1b (8 de noviembre de 2026), `salida_version=clinica-paciente-v1` conserva la llamada clínica y agrega redacción y verificación de la explicación al paciente. Las acciones obligatorias van primero. El clínico final queda protegido por un punto de control; un fallo posterior entrega HTTP 200 con ese clínico y respaldo CPU. El modo omitido (`clinica-v1`) conserva su respuesta y clave de caché. Contrato, plazos, interruptor `PACIENTE_LLM_HABILITADO`, estados y cachés separadas: **[SALIDA_DUAL.md](SALIDA_DUAL.md)**.

La explicación puede describir hallazgos documentados aunque no haya un perfil refractivo completo. Se dirige al paciente de usted y presenta efectos cotidianos como posibilidades. Óptica solicita ambos textos con **Generar con IA**; **Guardar** no llama al modelo. Las pruebas locales usan transporte simulado; quedan pendientes calidad, latencias y cancelación real con GPU.

Este documento es el punto de entrada. Da la vista completa del sistema de forma resumida y enlaza a los documentos de detalle para cada tema.

### Tareas v1 y prueba de enrutado

Todos los endpoints siguientes requieren `Authorization: Bearer <API_KEY>`:

| Endpoint | Comportamiento |
|---|---|
| `POST /v1/inferencia/receta-clinica` | Alias del handler de `/inferencia/impresion-clinica`: mismos contratos y caché. Prioridad interactiva. |
| `POST /v1/inferencia/seguimiento-whatsapp` | Contrato `seguimiento-whatsapp-v1`: catálogo determinista, redacción y verificación JSON en fondo; cualquier fallo del modelo devuelve HTTP 200 con `estado=plantilla` y `motivo`. |
| `GET /v1/tareas` | Tabla calculada con los settings activos: endpoints, prioridades, llamadas, versiones, opciones y respaldos. La explicación es una tarea hija: redacción (384) y verificación (32), en el turno clínico o en un turno propio si solo falta el paciente tras un acierto parcial de caché; respaldo en CPU. |

`GET /health` conserva sus claves y añade `gpu` con ocupación, prioridad del ocupante
y esperas separadas. El planificador es local al proceso: **un worker de uvicorn y
`MAX_CONCURRENT=1`**. Una receta en espera pasa antes que el fondo; el seguimiento
pide turno por cada llamada y responde `ia_ocupada` si hay una receta ocupando o esperando.
Request, respuesta y fixtures compartidos: [diccionario §6](DICCIONARIO_DATOS_RECETA.md#6-contrato-seguimiento-whatsapp-v1).

Prueba sin GPU, sin Ollama instalado y sin Internet (Python del entorno del repo):

```powershell
.venv\Scripts\python.exe -B scripts\probar_enrutado.py
# Equivalente: --modo simulado
```

El script inicia un Ollama simulado en loopback y uvicorn en un subproceso con
clave efímera y directorio temporal para los logs. Comprueba enrutado, cuerpos de
Ollama y prioridad, imprime la tabla y termina con código 0 si todo coincide.
G2/G3 reciben la redacción fija de G1 y demuestran el respaldo por validación.

Desde la PC que tenga acceso al servidor con GPU, con la clave guardada en una
variable de entorno (el script nunca la imprime):

```powershell
.venv\Scripts\python.exe -B scripts\probar_enrutado.py --modo real --url http://HOST:PUERTO --api-key-env IA_API_KEY
```

El modo real muestra HTTP, latencia y estado/motivo del seguimiento. Las latencias
reales y la detención efectiva de Ollama tras cancelar se verifican en la GPU.

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

- **Todo es 100% local.** El único método de inferencia es tu Ollama con `qwen3.5:9b`: el sistema nunca sale a internet.
- Las reglas clínicas (antes un archivo único `correlaciones.py`) ahora viven en un **paquete** `app/correlaciones/` dividido por dominio clínico. Esto no cambia el deployment, solo organiza el código.
- Hay una **cola de concurrencia** (`MAX_CONCURRENT=1`) porque tu GPU solo puede correr una inferencia a la vez — evita que dos requests de Postman simultáneos truenen la VRAM.
- Hay un **cache en memoria** que evita volver a llamar a Ollama si mandas el mismo caso dos veces.

La puesta en marcha (venv, dependencias, modelo, `.env`, script de arranque) está en [§4](#4-puesta-en-marcha-rápida).

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
   │  evalúa 47 reglas clínicas fijas (más 1 recordatorio técnico) sobre el payload (sin LLM, 100% reproducible)
   │  produce una lista de hechos clínicos ya redactados
   ▼
Construcción del prompt ─ app/prompt_builder.py
   │  arma el system prompt (reglas de redacción) y el user prompt
   │  (contexto del paciente, refracción, AKR/queratometría, hallazgos, correlaciones activas)
   ▼
Inferencia ─ app/inference.py
   │  valida que el prompt quepa en el contexto (413 si no)
   └─ app/providers/ollama.py → Ollama local → modelo qwen3.5:9b
   ▼
Postprocesado + guardarraíles ─ limpia <think>, listas y fences; arma un solo párrafo;
                descarta placeholders y meta-referencias; reacentúa términos clínicos;
                agrega la recomendación de seguimiento al final
   ▼
Respuesta JSON → Postman / SaaS
   { status, impresion_clinica, correlaciones_activadas }
```

Dos capas separadas a propósito:

- **Determinista (Python puro):** decide *si* una correlación clínica aplica. Mismo input → mismo resultado, siempre. Cubierta por tests "golden" que verifican el texto exacto de cada regla.
- **Generativa (LLM):** solo redacta el párrafo final integrando esos hechos ya decididos como soporte a la decisión clínica. El modelo **nunca** decide una correlación clínica, solo la integra a la prosa.

Detalle línea por línea de este flujo (headers, timeouts, reintentos, formato exacto del prompt): **[PIPELINE_LLM.md](PIPELINE_LLM.md)**.

---

## 3. Mapa del proyecto

| Ruta | Qué hace (resumen) |
|---|---|
| `app/main.py` | Define la API FastAPI: endpoint principal, auth Bearer, cola/semáforo de concurrencia, `/health`, warmup del modelo al arrancar. |
| `app/config.py` | Todas las variables de configuración (`Settings`, vía `pydantic-settings`), leídas de `.env`. También configura logging a consola + `logs/inference.log`. |
| `app/schemas.py` | Modelos Pydantic del payload de entrada (`ImpresionClinicaRequest` y sub-modelos). Refleja el catálogo real del SaaS (dropdowns, enums, rangos) con **coerción tolerante**: un valor fuera de catálogo se descarta o normaliza (no tumba el request con `422`). Mapeo campo-por-campo en [DICCIONARIO_DATOS_RECETA.md](DICCIONARIO_DATOS_RECETA.md). |
| `app/clinical_data.py` | Un solo chequeo: `has_clinical_data(req)` — rechaza payloads sin refracción ni datos clínicos. |
| `app/correlaciones/` | **El motor de casos optométricos.** Paquete con las 47 reglas clínicas y el recordatorio técnico, organizadas por dominio. Ver [§7](#7-casos-optométricos-correlaciones-clínicas). |
| `app/prompt_builder.py` | Arma el system prompt y el user prompt que se le mandan al LLM, a partir del payload + las correlaciones activas. |
| `app/patient_profile.py` | Calcula el perfil educativo de la refracción final y comparte el catálogo entre el prompt, sus guardas y el respaldo CPU. |
| `app/dual_contract.py` | Define el resultado dual interno, estados/orígenes y versiones del catálogo/perfil para invalidar la caché dual. |
| `app/inference.py` | Orquesta la inferencia: construye los prompts, valida el contexto, llama a Ollama y aplica el postprocesado + guardarraíles del texto crudo. |
| `app/providers/ollama.py` | Cliente HTTP hacia Ollama (`/api/chat`), parámetros de sampling, reintentos, monitoreo de contexto. |
| `app/cache.py` | Cache en memoria (TTL + tamaño máximo) para no repetir inferencias idénticas. |
| `tests/` | Suite de pytest (más de 6000 pruebas): correlaciones (incluye golden tests de texto exacto), prompt builder, schemas, inferencia, endpoint principal y el corpus de casos históricos. |
| `auditoria/` | Material de revisión, corpus y scripts de referencia, incluidas las matrices consumidas por las pruebas y el catálogo generado para el dueño. |
| `start_linux.sh` | Script de arranque para Ubuntu: valida `.env`, levanta Ollama si hace falta, descarga el modelo si falta, activa el venv, corre uvicorn. |
| `.env` / `.env.example` | Configuración real / plantilla. Ver [§9](#9-configuración-env). |

---

## 4. Puesta en marcha rápida

En tu PC Ubuntu con GPU (Ollama instalado — `curl -fsSL https://ollama.com/install.sh | sh` si falta):

```bash
cd ia-api
python3 -m venv .venv                       # solo la primera vez
.venv/bin/pip install -r requirements.txt   # solo la primera vez
ollama pull qwen3.5:9b                      # si el modelo no está descargado
cp .env.example .env                        # si aún no existe
# edita .env: define API_KEY con un token real
./start_linux.sh
```

`start_linux.sh` valida `.env` (rechaza el API_KEY placeholder), levanta Ollama si no está corriendo, descarga el modelo si falta, activa el venv y levanta uvicorn en `HOST:PORT` (default `0.0.0.0:8888`).

Verificación rápida:

```bash
curl http://localhost:8888/health
```

Correr la suite de pruebas (no necesita GPU ni Ollama; más de 6000 pruebas, ~1 minuto):

```bash
.venv/bin/python -m pytest
```

Las pruebas leen datos de referencia de `auditoria/` (ver [§3](#3-mapa-del-proyecto)); no los borres.

---

## 5. Probar con Postman

- **Método:** `POST`
- **URL:** `http://<ip-de-tu-ubuntu>:8888/inferencia/impresion-clinica`
- **Headers:**
  - `Authorization: Bearer <el mismo valor que API_KEY en tu .env>`
  - `Content-Type: application/json`
- **Body (raw JSON):** un payload con al menos `refraccion`, `akr` o `clinica` con algún valor. La estructura campo por campo está en [DICCIONARIO_DATOS_RECETA.md](DICCIONARIO_DATOS_RECETA.md).

Respuesta esperada:

```json
{
  "status": "ok",
  "impresion_clinica": "El paciente ...",
  "correlaciones_activadas": ["fondo_periferico_riesgo", "av_cc_limitada"]
}
```

- `correlaciones_activadas` te dice qué reglas clínicas se dispararon con ese caso (útil para depurar por qué el texto dice lo que dice).
- Si mandas el mismo caso dos veces, la segunda respuesta trae `"cached": true` y no toca la GPU.

---

## 6. Endpoints

| Endpoint | Método | Auth | Qué hace |
|---|---|---|---|
| `/inferencia/impresion-clinica` | `POST` | Bearer | Endpoint principal. Recibe el examen, devuelve la impresión clínica. |
| `/health` | `GET` | No | Estado de Ollama, si el modelo está descargado y cargado en VRAM, y profundidad de la cola de concurrencia. |

Errores más comunes: `401` (token inválido), `422` (payload **sin datos clínicos** — un valor fuera de catálogo ya no genera `422`: se descarta o normaliza por coerción tolerante), `503` (cola llena), `504` (timeout de inferencia), `413` (prompt excede el contexto del modelo). Detalle y causas en [PIPELINE_LLM.md §3](PIPELINE_LLM.md#3-endpoint-autenticacion-y-control-de-carga).

---

## 7. Casos optométricos (correlaciones clínicas)

Un "caso optométrico" en este sistema es una **correlación clínica**: una regla fija que dice *"si el examen tiene tales valores, entonces hay tal hallazgo clínico relevante"*. Por ejemplo: si la agudeza visual con corrección está muy reducida, o si el fondo de ojo describe un hallazgo de riesgo periférico, el sistema agrega ese hecho al prompt antes de que el LLM redacte el párrafo.

**Dónde viven:** paquete [`app/correlaciones/`](app/correlaciones/), un módulo por dominio clínico:

| Módulo | Dominio |
|---|---|
| `fondo_de_ojo.py` | Hallazgos de fondo de ojo (glaucoma, DMAE, vascular, periférico...) |
| `refractivas.py` | Miopía magna, hipermetropía alta, anisometropía, AV limitada... |
| `akr.py` | Correlación entre autorrefractómetro y refracción final |
| `corneal.py` | Valores queratométricos elevados o planos, discrepancias con Rx y asimetría entre ojos |
| `anexos_cristalino.py` | Anexos oculares |
| `segmento_anterior.py` | Opacidad del cristalino y riesgo de glaucoma secundario |
| `motilidad.py` | Motilidad ocular |
| `sintomas_agudos.py` | Diplopía aguda |
| `pupilas_motilidad.py` | Reflejos pupilares y combinaciones de pupilas/motilidad |
| `campos_amsler.py` | Campos visuales, rejilla de Amsler |
| `binocularidad.py` | Cover test, PPC, forias/tropias |
| `superficie_ocular.py` | BUT (ojo seco) |
| `contexto.py` | Edad, ocupación y motivo de consulta; reglas automáticas de presbicia retiradas. |
| `registry.py` | **Ensambla las reglas en orden fijo** y expone `evaluar_correlaciones` / `nombres_correlaciones_activas` |
| `base.py`, `texto.py`, `refraccion_utils.py`, `queratometria.py` | Helpers compartidos (memoización, normalización de texto, cálculos clínicos) |

Cada regla es determinista: no la decide el LLM, la decide Python. El LLM solo la redacta como soporte a la decisión clínica.

**Catálogo clínico completo** (qué dispara cada una de las 47 reglas y el recordatorio técnico, con el fundamento clínico/evidencia detrás de cada una): **[CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md)** — este es el documento que le sirve tanto al optometrista y al doctor (para entender qué campo activa qué hallazgo) como al equipo técnico.

---

## 8. Cómo agregar un caso optométrico nuevo

1. Abre el módulo de dominio correspondiente en `app/correlaciones/` (o crea uno nuevo si el dominio no existe todavía).
2. Escribe dos funciones:
   - `_cond_x(req) -> bool` — decide si la regla aplica.
   - `_texto_x(req) -> str` — el texto clínico que se agrega al prompt si aplica.
3. Regístrala en `app/correlaciones/registry.py`, agregando `Correlacion("nombre_unico", _cond_x, _texto_x)` a la lista `CORRELACIONES`, en la posición correcta según prioridad clínica (los hallazgos urgentes van primero — el orden de esa lista es el orden en que aparecen en el párrafo final).
4. Si tu regla depende de texto libre (fondo de ojo, motilidad, etc.), revisa los helpers de `texto.py` para normalización y ventana de negación ("sin desgarros" no debe disparar la regla de "desgarro").
5. Agrega un test **golden** en `tests/test_correlaciones_golden.py` que audite directamente el texto exacto de tu regla nueva (obligatorio: `test_golden_cubre_todas_las_correlaciones` falla si te falta) y actualiza el conteo esperado (47 médicas) en `tests/test_correlaciones.py` (`test_registro_separa_47_medicas_y_un_recordatorio_tecnico`).
6. Documenta la regla (campos que la disparan, umbral, fundamento clínico) en `CORRELACIONES_CLINICAS.md`.

Paso a paso con más contexto de arquitectura: [PIPELINE_LLM.md §14](PIPELINE_LLM.md#14-como-extender-el-sistema).

---

## 9. Configuración (`.env`)

La plantilla de configuración es [.env.example](.env.example); cada parámetro de sampling/contexto de Ollama está comentado con su justificación (incluidas mediciones en la 3070 Ti) en [app/config.py](app/config.py). Las variables que más te importan para tu flujo:

| Variable | Para qué |
|---|---|
| `OLLAMA_URL` | Dónde vive tu Ollama (default `http://localhost:11434`, correcto si la API corre en el mismo Ubuntu). |
| `OLLAMA_MODEL` | El modelo a usar — déjalo en `qwen3.5:9b`. |
| `OLLAMA_DUAL_NUM_PREDICT` | `1024` — aceptado por compatibilidad con `.env` existentes; ya no se usa. Ambos modos usan `OLLAMA_NUM_PREDICT`. |
| `OLLAMA_TEMPERATURE` | `0.2` — tarea de extracción/reporte fiel, no chat; con seed fijo da salida casi determinista. |
| `OLLAMA_NUM_CTX` | `8192` — el payload máximo del diccionario no cabía en 4096 (daba `413`). Medido en la 3070 Ti: solo +0.2 GB de footprint vs 4096. |
| `API_KEY` | El token que Postman debe mandar en `Authorization: Bearer`. **Cámbialo del placeholder** (el script de arranque lo exige). |
| `HOST` / `PORT` | Dónde escucha uvicorn (default `0.0.0.0:8888`, para que Postman le pueda pegar desde otra máquina en tu red). Los lee `start_linux.sh`. |
| `MAX_CONCURRENT` | Déjalo en `1` — tu GPU procesa una inferencia a la vez. |
| `PACIENTE_LLM_HABILITADO` | `true` por omisión; `false` omite redacción/verificación y la prosa paciente cacheada, con respaldo CPU. No cambia la llamada clínica. |
| `SEGUIMIENTO_LLM_HABILITADO` | `true` por omisión; `false` responde el mensaje del catálogo antes de consultar la caché y sin llamar a Ollama. Usa el respaldo del catálogo con `motivo=ia_deshabilitada`. Se lee al arrancar: cambiarlo exige reiniciar ia-api. |
| `LOG_LEVEL` | `INFO` normal; `DEBUG` registra tamaños de system/user y estimaciones de tokens, sin imprimir los prompts completos. |

---

## 10. Mapa completo de documentación

| Documento | Para qué sirve |
|---|---|
| **README.md** (este archivo) | Punto de entrada: arquitectura, flujo Ubuntu/Ollama/Postman, dónde está cada cosa. |
| [SALIDA_DUAL.md](SALIDA_DUAL.md) | Contrato tipado y pipeline clínico/paciente, reglas educativas, respaldo y caché versionada. |
| [PIPELINE_LLM.md](PIPELINE_LLM.md) | Detalle técnico línea por línea del pipeline: schema completo, construcción del prompt, inferencia con Ollama, postprocesado + guardarraíles, cache, cómo extender el sistema. |
| [CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md) | Catálogo clínico de las 47 correlaciones y el recordatorio técnico: qué las dispara y por qué, con evidencia y límites metodológicos. |
| [DICCIONARIO_DATOS_RECETA.md](DICCIONARIO_DATOS_RECETA.md) | Diccionario de datos del SaaS: catálogo real (dropdowns, enums, rangos, texto libre) de cada campo del payload y especificación técnica del schema. |
| [GUIA_CONEXION.md](GUIA_CONEXION.md) | Conexión total en producción: SaaS en Hetzner (`www.redcoretech.xyz`) → Cloudflare Tunnel → ia-api en la PC de casa. Namecheap/Cloudflare/WAF/systemd paso a paso, verificación end-to-end y tabla de debugging. |
| [.claude/skills/qwen-inference/](.claude/skills/qwen-inference/) | Referencia técnica de Qwen3.5 usada como fuente para los parámetros de inferencia. |

## Registro y presupuesto de tareas

`app/tareas/registro.py` mantiene las definiciones. `montar_rutas(app)` genera
POST, `/v1/tareas` y `/v1/metricas` autenticados. Receta y explicacion son
fichas manuales; el handler clinico permanece en main.py. Seguimiento usa
ContextoEjecucion.llamar con prioridad fondo y un turno por llamada.

El proveedor verifica cada envio, incluidas opciones fusionadas y reintentos:
entrada + salida <= int(0.95 * min(OLLAMA_NUM_CTX, LIMITE_CONTEXTO_TOKENS, 8192)).
num_ctx no se puede sobrescribir. Una tarea que no cabe figura degradada sin
cambiar la disponibilidad global de health.

Conteo exacto: BPE reconstruido desde show y prompt Qwen completo con roles,
think=False y seis sondas concordantes antes de publicar el contador.
Se fija version de Ollama, digest, plantilla y contexto. Durante verificacion
rige el respaldo. Requiere tokenizers>=0.22 (objetivo 0.23.3).
Respaldo estricto: bytes UTF-8 del prompt renderizado. Solo receta permite
conservador: 16 + suma por mensaje de numeros Unicode, simbolos, saltos,
ceil(letras/2) y 8. Cuenta digitos individualmente; no garantiza cota del BPE.
PRESUPUESTO_RECETA_SIN_EXACTO=estricto cierra esa excepcion de disponibilidad.
Cada uso conservador emite WARNING; se advierte si los tokens reales superan
la cota. El modo aparece en health y tareas. Metricas en memoria sin contenido:
contadores, sumas y maximos; reinician con el proceso.

Despliegue: Laravel debe aceptar y mostrar presupuesto antes o junto con esta
API; versiones anteriores pueden sustituirlo por respuesta_invalida local.
Streaming, varias GPU y planificacion distribuida son extensiones futuras.
Ver [COMO_AGREGAR_UNA_TAREA.md](COMO_AGREGAR_UNA_TAREA.md).
