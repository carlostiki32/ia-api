# Umbrales de certificación en GPU — acuerdo firmado (2026-11-12)

Firmado por Claude (orquestador), Codex y Antigravity tras tres rondas (R1 crítica, R2 y R3 de firma). Antigravity firmó en R2 y R3. Codex firmó en R3 condicionado a ajustar solo los conteos de llamadas de A1, que quedaron ajustados como pidió. Los umbrales se fijaron **antes** de medir y no se cambian después de ver resultados.

Estructura: la parte I es la propuesta v2; la parte II, el acuerdo final, que **manda** donde difieran.

---

# Parte I — Propuesta v2

Integra la ronda R1 (Codex: NO FIRMO con 6 puntos; Antigravity: FIRMO con cambios menores). Cambios respecto de v1 marcados con **[v2]**.

## 1. Kit `scripts/certificar_gpu.py`
- **[v2] Instancia propia.** El kit arranca su propia ia-api desde el repo, con `cwd` en el repo para que cargue el `.env` real sin leerlo ni imprimirlo. Usa un puerto libre, `--workers 1` y caché vacía. Así mide el mismo código y la misma configuración, sin caché previa ni tráfico ajeno. Antes de empezar exige que no haya otra ia-api usando la GPU: GPU desocupada y colas vacías en `/health`, sin otro trabajo en `/api/ps`. Instrucción al dueño: detener la ia-api de producción durante la certificación y, al terminar, arrancarla y correr `scripts/probar_enrutado.py --modo real` contra la URL pública.
- **[v2] Proxy de medición transparente** entre la ia-api del kit y Ollama, solo para las fases de medición. Por cada llamada registra la tarea, la etapa, la duración, `prompt_eval_count`, `eval_count`, `eval_duration` (para los tokens/s), `done_reason`, si el JSON es válido y los intentos. No registra contenido clínico en el log; el contenido solo va a las hojas de revisión. El proxy no se usa en las fases de cancelación, para no alterar lo que se mide.
- **[v2] Telemetría de GPU** con `nvidia-smi` cada 5 s, si existe: VRAM, uso, temperatura y relojes. Además, la RAM del sistema.
- **[v2] Reproducibilidad.** El informe fija:
  - la versión de Ollama (`/api/version`) y el digest del modelo;
  - las opciones de cada llamada (`/v1/tareas`);
  - el hash del corpus y la versión del kit;
  - la versión de los prompts.
- Corpus sintético y versionado (`tests/fixtures/certificacion_gpu/`), generado de forma determinista. **[v2] Cada caso declara de antemano `elegible_personalizacion` (sí/no) y su categoría**; un fallo nunca se reclasifica después. Los casos difieren en datos que entran a la clave de caché (refracción, edad, motivo), no solo en `receta_id` o `paciente_ref`.
- Salidas, en una carpeta fuera del repo:
  - `informe.json` e `informe.md`, con la tabla criterio → umbral → medido → APTO / NO APTO / PENDIENTE;
  - `revision_paciente.csv`, con 100 filas;
  - `revision_whatsapp.csv`, con 50 filas.

  Los CSV van en UTF-8 con BOM, para Excel, y con columnas en español para que el dueño marque.
- `--cerrar CARPETA` lee las hojas marcadas y completa R6, R7 y W3. **[v2]** `--rapido`, una fase omitida o una casilla sin marcar **nunca** dan APTO global.
- **[v2] Pruebas sin GPU:** el Ollama simulado se amplía con `/api/version`, `/api/show`, descarga con `keep_alive:0`, `/api/ps`, demoras configurables y cancelación observable. Se inyectan un reloj y una telemetría de GPU simulados. Las pruebas cubren las fronteras de cada umbral, los respaldos, la concurrencia, el cierre incompleto y que nunca se imprima la clave.

## 2. Fases y umbrales

| # | Criterio | Umbral |
|---|---|---|
| P1 | `/health` ok, `model_available`, `tareas_degradadas = []`, `max_concurrent = 1`, GPU desocupada y colas vacías antes de medir | obligatorio |
| P2 | `modo_conteo = exacto` y `pre_tokenizador = qwen35` en las 3 tareas, al empezar **y al terminar** | obligatorio |
| P3 **[v2]** | C5: en `/v1/tareas`, `limite_contexto = 7782` (95 % de 8192) y todas las llamadas con `cabe = true`; además `context_length` de `/api/ps` si la versión de Ollama lo expone | obligatorio, salvo `/api/ps`, que es informativo |
| P4 **[v2]** | Personalización activa: al menos una receta nueva sale `generada/llm` | obligatorio |
| R1 | 100 recetas: 100 % HTTP 200 con impresión clínica no vacía; 0 respuestas 5xx; 0 respuestas 413 | obligatorio |
| R2 **[v2]** | En frío (modelo descargado con `keep_alive:0` y ausente en `/api/ps`, caso sin caché, sin otro tráfico): HTTP ≤ 88 s y 0 respuestas 504 | obligatorio |
| R3 **[v2]** | En caliente, solo la petición dual y sin caché: p95 ≤ 60 s; máximo HTTP ≤ 88 s (85 s de plazo interno + 3 s de transporte) | obligatorio |
| R4 | Etapa del paciente, medida en el proxy (redacción + verificación): p95 ≤ 20 s | obligatorio |
| R5 **[v2]** | En casos elegibles: `generada/llm` ≥ 90 %; `motivo = timeout` ≤ 5 % | obligatorio |
| R6 | En **todos** los elegibles, `generada` y marcada válida por el dueño ≥ 90 %; los respaldos y las abstenciones cuentan como no válidos | obligatorio, se cierra con `--cerrar` |
| R7 **[v2]** | Críticos = 0 en todas las salidas: clínico, explicación (también en los respaldos) y acciones. La hoja incluye el clínico junto a la explicación, y una casilla de «error crítico en el clínico». | obligatorio, se cierra con `--cerrar` |
| R8 **[v2]** | Caché, 10 recetas `generada` repetidas: `cache.clinico = true`, `cache.paciente = true` y 0 llamadas nuevas en el proxy. 10 WhatsApp repetidos: `cached = true`. Repetir un caso que cayó en respaldo **sí** vuelve a intentar la personalización. | obligatorio |
| W1 | 50 WhatsApp: 0 respuestas 5xx; p95 ≤ 20 s en caliente | obligatorio |
| W2 | `generada` ≥ 80 % en la primera ejecución, sin caché | obligatorio |
| W3 | Aceptables ≥ 90 % y 0 críticos (afirmación clínica, dato falso, tuteo, nombre o teléfono reales). Los marcadores `:paciente` y `:clinica` están permitidos. | obligatorio, se cierra con `--cerrar` |
| C1 **[v2]** | Receta enviada mientras corre un WhatsApp: HTTP 200 con clínico y espera adicional ≤ 20 s. Es una exigencia operativa, no una garantía del planificador. | obligatorio |
| C2 **[v2]** | WhatsApp enviado mientras corre una receta: HTTP 200, `plantilla` con `motivo = ia_ocupada`, en ≤ 1 s | obligatorio |
| C3 **[v2]** | Dos recetas distintas simultáneas: ambas con clínico. Aparte, saturación: 503 esperado al agotar los 30 s de cola, que se documenta. | obligatorio el par; informativa la saturación |
| X1 **[v2]** | Petición directa a Ollama abortada por el cliente a los 2 s: una petición mínima posterior tarda ≤ su línea base + 3 s, y el uso de la GPU baja en ≤ 5 s (este último, informativo) | obligatorio |
| X2 **[v2]** | Cancelación desde ia-api: segunda instancia del kit con `PACIENTE_TIMEOUT_REDACCION_S=1` → la respuesta llega con `plantilla/timeout` y la siguiente petición mínima cumple como en X1 | obligatorio |
| S1 **[v2]** | Sostenida, durante toda la corrida (≥ 30 min): 0 errores de memoria, 0 reinicios de Ollama y 0 cambios de digest; deriva de la mediana de latencia entre los primeros 20 y los últimos 20 casos | obligatorio lo primero; informativa la deriva, con alerta si supera +25 % |
| J1 **[v2]** | Tasa de JSON inválido, `done_reason = length`, verificaciones rechazadas y tokens/s por etapa | informativo |

## 3. Interruptores y veredicto por perfil **[v2]**
- Nuevo **`SEGUIMIENTO_LLM_HABILITADO`** (por omisión `true`). Con `false`, ia-api responde el mensaje del catálogo **antes de consultar la caché**, sin llamar a Ollama. Igual que `PACIENTE_LLM_HABILITADO`, se lee al arrancar: cambiarlo exige reiniciar ia-api, no desplegar.
- El kit emite un veredicto por perfil:
  - **A**: todo con Qwen.
  - **B**: `PACIENTE_LLM_HABILITADO=false`.
  - **C**: `SEGUIMIENTO_LLM_HABILITADO=false`.
  - **D**: ambos en `false`.

  Un perfil con un interruptor apagado es APTO solo si pasan sus propios criterios **y** una verificación corta con ese interruptor apagado: 5 casos sin llamadas de esa función en el proxy y con el respaldo correcto. Un fallo de calidad nunca se vuelve APTO por recomendar un interruptor; se informa como «APTO en el perfil B».
- Si fallan P1–P3, R1–R3, X1, X2 o S1, ningún perfil es APTO: no se despliega la ia-api nueva.

## 4. Reglas de la corrida
- Una sola corrida certificadora. Si se interrumpe, se repite completa con el mismo corpus.
- El dueño marca las hojas sin ver el informe automático de calidad, para no sesgar la revisión.
- «0 críticos observados» no demuestra riesgo cero. La revisión editorial del catálogo y del glosario (`02-catalogo-y-prompts-para-revision.md`) sigue siendo del dueño.


---

# Parte II — Acuerdo final (manda sobre la parte I)

Este documento **manda sobre `GPU-propuesta-v2.md`** donde difieran. Resuelve los puntos de Codex en R2, que no firmó y pidió concreciones, y los de Antigravity.

## A1. Muestras sin caché (R8 y todas las fases de medición)
- Cada muestra de medición exige `generacion.cache.clinico = false` y `generacion.cache.paciente = false` en la receta dual, y `generacion.cached = false` en WhatsApp.
- Además, el proxy debe registrar **al menos una llamada nueva** a Ollama por muestra, y sus llamadas deben corresponder a las etapas que la respuesta dice haber ejecutado: clínica (con sus reintentos, `app/inference.py`), redacción y verificación del paciente según el estado y el motivo, y redacción con o sin verificación en WhatsApp (un respaldo por validación hace solo la redacción). El informe muestra las llamadas por etapa y los intentos; no se exige un número fijo.
- Si una muestra viene de la caché, la fase sale **NO APTO («muestra contaminada»)** y se repite la corrida completa; no se descarta la muestra.
- El generador del corpus garantiza claves clínicas distintas, con una prueba. La clave del paciente depende del clínico generado, así que se vigila en tiempo de corrida con la regla anterior.

## A2. Tráfico ajeno y estado previo (P1)
- `nvidia-smi` es **obligatorio**. Si no existe, el veredicto global es NO APTO por falta de telemetría.
- Antes de cada fase de medición: 10 s con uso de GPU < 10 %, la instancia propia sin cola y `/api/ps` registrado.
- `/api/ps` acredita qué modelos están residentes, no la ausencia de peticiones; por eso manda la muestra de uso de la GPU.

## A3. Opciones efectivas y reparto CPU/GPU (reproducibilidad, S1)
- El proxy guarda, sin contenido, las opciones del **cuerpo real** de cada llamada: `num_ctx`, `num_predict`, `temperature`, `seed`, si hay `format` y `keep_alive`. El informe las resume por tarea y etapa.
- `/v1/tareas` queda como referencia declarada.
- El informe registra el reparto CPU/GPU con `size` y `size_vram` de `/api/ps`, al empezar y al terminar.
- El corpus declara **5 casos de entrada máxima representativa**: textos multilínea largos, AKR y todos los hallazgos. Se informan por separado y cuentan en R1–R5.

## A4. Cancelación (X1, X2 y nuevas X3–X5)
Para toda cancelación hay que **acreditar inferencia activa**: uso de GPU ≥ 30 % en la muestra anterior al corte. Si la llamada termina antes del corte, la muestra no sirve y se reintenta con un caso más largo, hasta 3 veces. Si nunca se logra, el resultado es **NO VERIFICADO**, que cuenta como NO APTO.

| # | Prueba | Umbral |
|---|---|---|
| X1 | Petición directa a Ollama abortada por el cliente a los 2 s | siguiente petición mínima ≤ su línea base + 3 s; la caída de la GPU en ≤ 5 s es informativa |
| X2 | Instancia con `PACIENTE_TIMEOUT_REDACCION_S=1`: respuesta `plantilla/timeout` | recuperación como en X1 |
| X3 | Instancia con `PACIENTE_TIMEOUT_VERIFICACION_S` mínimo y la redacción normal: respuesta con el motivo que dé el código para la verificación vencida | recuperación como en X1 |
| X4 | Instancia con `PLAZO_GLOBAL_RECETA_S` corto (por ejemplo 10 s), que vence durante la llamada clínica: respuesta que documente el código, sin 500 | recuperación como en X1 |
| X5 | El kit corta su conexión HTTP con ia-api a mitad de la llamada clínica | ia-api atiende la siguiente petición en ≤ 90 s después del corte y sin turno de GPU colgado; si cancela antes, se informa |

Las instancias de X2–X4 tienen la personalización activada.

## A5. Matriz de perfiles
Las mediciones se hacen una vez, en el perfil A. Los otros perfiles reutilizan los criterios que les aplican y agregan una verificación corta con el interruptor apagado: 5 casos, sin llamadas de esa función en el proxy y con el respaldo correcto.

| Perfil | Criterios que aplican | No aplican |
|---|---|---|
| A, todo con Qwen | todos | — |
| B, `PACIENTE_LLM_HABILITADO=false` | P1–P3, R1–R3, R7 (clínico y plantilla), R8 (solo clínico), W1–W3, C1–C3, X1, X4, X5, S1, más la verificación con el paciente apagado | P4, R4–R6, X2, X3 |
| C, `SEGUIMIENTO_LLM_HABILITADO=false` | P1–P4, R1–R8, C3, X1–X5, S1, más la verificación con WhatsApp apagado | W1–W3, C1, C2 |
| D, ambos en `false` | P1–P3, R1–R3, R7 (clínico y plantilla), C3, X1, X4, X5, S1, más las dos verificaciones | el resto |

## A6. Comprobación final en producción
Tras la certificación, el dueño arranca la ia-api de producción y corre:

`python scripts/probar_enrutado.py --modo real --url URL_PUBLICA --api-key-env VARIABLE_CON_LA_CLAVE`

Debe salir sin fallos.

## A7. Observaciones de Antigravity en R2 sobre la caché de WhatsApp (verificadas por Claude: no proceden)
- «Un WhatsApp repetido responde `cached = false`»: no es así. `CacheTareas.get` marca `generacion.cached = True` en la copia (`app/tareas/nucleo.py:135-137`) y lo comprueba `tests/test_seguimiento_endpoint.py:79`.
- «Se guardan los respaldos en la caché»: no es así. `CacheTareas.put` descarta todo lo que no sea `generada` (`app/tareas/nucleo.py:142`).

R8 para WhatsApp queda como en la v2. El kit, además, exige 0 llamadas nuevas en el proxy.
