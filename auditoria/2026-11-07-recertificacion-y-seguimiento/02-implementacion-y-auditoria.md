# Mensajes de WhatsApp personalizados y enrutado multitarea — implementación y auditoría (2026-11-07)

Continúa `RETOMAR_TRABAJO_2026-11-06.md`. Orquestó y auditó Claude; implementaron Codex (gpt-6.1-sol) y Antigravity (Gemini). Contrato normativo: `00-contrato-seguimiento-whatsapp-v1.md` (copia exacta del que recibieron ambos workers).

## 1. Decisiones
**Del dueño (2026-11-07):**
- Consentimiento (D-17): la IA es local y el dueño declara tener acuerdos con sus pacientes; el sistema no exige un registro de consentimiento para personalizar.
- Flujo: en el listado de pacientes, el botón de WhatsApp abre de inmediato un diálogo con el mensaje preliminar **editable**; el mensaje se personaliza solo; **Aceptar** abre WhatsApp con el texto del diálogo. Sin Aceptar no se abre nada.

**Consenso de implementación** (regla del proyecto: los tres de acuerdo). Ronda 1: Antigravity SÍ; Codex NO con tres bloqueos, aceptados: (1) el seguimiento no espera si una receta ocupa o espera la GPU; (2) el `base_hash` del diálogo incluye teléfono, nombre y clínica; (3) el mensaje siempre comunica la condición de costo. Ronda 2: los tres SÍ.
Puntos principales: acción Livewire 4.4 `#[Json]` (asíncrona, sin worker nuevo) en lugar de job + cola; respaldo de ia-api = mensaje 100 % del catálogo (`plantilla`); el genérico corregido queda en Laravel; solo se personaliza con semáforo próximo/vencido, adulto y fecha de nacimiento; catálogo v1-revisado en uso con los valores por omisión de su §6 (hechos de armazón inactivos, antimetropía sin nombrar la condición); «Regenerar» cambia la semilla (`variante`).

## 2. Qué se construyó
**ia-api** (W1 y W1-FIX, Codex): `POST /v1/inferencia/seguimiento-whatsapp` (catálogo literal, elegibilidad, combinación, validador, verificación, respaldo determinista, caché solo de `generada`), planificador de GPU con prioridad (`app/gpu_scheduler.py`), alias `POST /v1/inferencia/receta-clinica`, `GET /v1/tareas`, `scripts/probar_enrutado.py`, opciones por llamada en el proveedor, volcado DEBUG del prompt clínico retirado (D-3), contrato en `DICCIONARIO_DATOS_RECETA.md` §6. Pruebas: 6321 → **22151**.
**Laravel `optica`** (W2 Antigravity; W2-FIX y DOCFIX Codex): diálogo `x-modal` con Alpine, `prepararNotificacion` / `#[Json] personalizarMensaje` / `aprobarYAbrir`, `PersonalizarMensajeSeguimientoAction`, `SeguimientoIaPayloadBuilder`, cliente estricto en `IaApiService`, tabla `paciente_mensajes_ia`, genérico corregido (§4 del catálogo), `payload` retirado del log clínico (D-3). Pruebas PHP: 586 → **620**; JS: 26 → **37**.
**F0-FIX** (Codex): cierre de C1, ver `01-recertificacion-c1-c6.md`.

## 3. Verificación propia del orquestador
- Suites repetidas por Claude: ia-api **22151 passed**; Laravel **620 OK** y JS **37/37** (corrida en solitario).
- Finales de línea: ia-api 100 % CRLF; optica 100 % LF.
- Sondas adversariales contra el validador: 22 propias y 23 de la revisión cruzada de Antigravity. Antes del endurecimiento pasaban 11 + 23; después solo pasa una frase en inglés («Book now»), que queda para la verificación del modelo y la aprobación humana. El léxico es una defensa adicional, no una garantía semántica.
- **Prueba cruzada real** (Laravel → ia-api real con uvicorn → Ollama simulado propio): las respuestas reales de G1–G3 pasan la validación estricta de Laravel y son idénticas a los fixtures; los payloads que arma Laravel para pacientes sembrados los acepta ia-api sin un solo 422. **0 fallos.**
- **Prueba en navegador real** (Edge sin interfaz por CDP, `window.open` interceptado): personalizado con IA, edición y apertura de WhatsApp al teléfono correcto con el texto editado; respaldo del catálogo con motivo legible; menor y sin fecha de nacimiento → mensaje general; editar mientras la IA trabaja conserva la edición; regenerar tras editar reemplaza; cambio de teléfono con el diálogo abierto → no se abre WhatsApp, aviso dentro del diálogo y resincronización.
- Revisión cruzada: Antigravity revisó ia-api (6 hallazgos, corregidos); Codex revisó Laravel (5 hallazgos, corregidos junto con 4 del orquestador).

## 4. Enrutado (salida de `scripts/probar_enrutado.py`, modo simulado)
| Endpoint | Llamadas a Qwen | Etapa / prompt / temperatura / num_predict / format |
|---|---|---|
| `/inferencia/impresion-clinica` (`clinica-v1`) | 1 | clínica / clinica-v1 / 0.2 / 1024 / no |
| `/inferencia/impresion-clinica` (`clinica-paciente-v1`) | 1 | clínica (la explicación del paciente sale de CPU) |
| `/v1/inferencia/receta-clinica` | igual que el legado (mismo handler y caché) | — |
| `/v1/inferencia/seguimiento-whatsapp` | 2 | redacción / seguimiento-whatsapp-prompt-v1 / 0.4 / 320 / JSON schema · verificación / seguimiento-verificacion-v1 / 0.0 / 32 / JSON schema |

Prioridad demostrada: con un seguimiento redactando, una receta que llega obtiene el turno antes que la verificación del seguimiento, y el seguimiento responde de inmediato `plantilla/ia_ocupada`.

## 5. Límites y pendientes
- **Qwen real no se ejecutó** (esta PC no tiene Ollama ni el modelo). Falta en la PC con GPU: `scripts/probar_enrutado.py --modo real --url … --api-key-env …`, `OLLAMA_NUM_CTX=8192`, medir latencias, tasa `generada`/`plantilla` y comprobar que Ollama detiene la generación al cancelar (piloto F4 con umbrales fijados antes).
- Desplegar ia-api y Laravel **juntos**.
- `graphify update .` pendiente en optica (Graphify no está instalado en esta PC).
- El nombre del paciente se sustituye completo y en mayúsculas, como el genérico anterior; usar solo el primer nombre en tipo título sería una mejora para decidir.
- Las decisiones de firma del catálogo (§6) se aplicaron con los valores por omisión; el dueño puede retirar hechos o cambiar textos (el catálogo es un dato versionado en `app/seguimiento/catalogo.py`).
