# Registro de tareas escalable y límite de 8k tokens — 2026-11-07

Pedido del dueño: «que sea escalable para cuando se me ocurran más funciones con IA, respetando el límite de los 8k tokens». Diseño de Claude, consenso con Codex y Antigravity en 4 rondas, implementación de Codex (ia-api) y Antigravity (Laravel), auditoría de Claude.

## Qué quedó
- **Agregar una función ya no toca `main.py`**: se escribe su definición en `app/tareas/definiciones/` (ficha, esquemas, llamadas a Qwen declaradas, `ejecutar(req, ctx)`, respaldo) y se registra en `app/tareas/registro.py` (`cargar_definiciones`). La ruta, `/v1/tareas`, `/v1/metricas`, la prioridad de GPU, el presupuesto de tokens y la prueba de enrutado salen del registro. Guía: `COMO_AGREGAR_UNA_TAREA.md`; plantilla: `app/tareas/definiciones/_plantilla.py`.
- La receta clínica **no se movió** (sigue en `main.py`, certificada); el registro la describe. El seguimiento de WhatsApp ya corre por el ejecutor del registro.
- Laravel: `IaApiService::ejecutarTarea($tarea, $payload)` (transporte genérico) con `IA_API_BASE_URL` y `services.ia_api.tareas.<tarea>.endpoint|timeout`.

## Garantía del límite de 8k
- **Guardián único en el proveedor** (`app/providers/ollama.py`): cada envío a Qwen —incluidos los reintentos de la receta y cualquier opción fusionada— se cuenta antes de salir; si `prompt + num_predict` supera `int(0,95 × min(OLLAMA_NUM_CTX, LIMITE_CONTEXTO_TOKENS, 8192))` = **7782**, no llega a Ollama (receta → 413; seguimiento → mensaje del catálogo con motivo `presupuesto`). `num_ctx` no se puede sobrescribir y nunca pasa de 8192.
- **Conteo exacto**: el tokenizador del modelo cargado se reconstruye desde `/api/show` de Ollama (soporta los pre-tokenizadores de Qwen2 y de **Qwen3.5**, que tiene vocabulario y expresión nuevos), se tokeniza el prompt completo con la plantilla de chat y se **verifica al arrancar** con 6 sondas contra `prompt_eval_count`; queda fijado a versión de Ollama, digest, plantilla y `num_ctx`.
- **Sin conteo exacto verificado**: toda tarea usa la cota **estricta** demostrable (bytes UTF-8 del prompt renderizado), salvo la receta, que usa la cota **conservadora** por decisión de disponibilidad (con la estricta hasta la receta normal excede 7782). `PRESUPUESTO_RECETA_SIN_EXACTO=estricto` la endurece. **Decisión pendiente del dueño** (Codex votó por estricto; Antigravity por conservador).

## Verificación de Claude
- Suites: ia-api **22188 passed** (más la prueba opcional contra el tokenizador oficial, que pasa con `QWEN_TOKENIZER_JSON`); Laravel **636 OK**; JS **37/37**.
- **Tokenizador oficial de Qwen3.5-9B** (descargado de Hugging Face): la reconstrucción da **los mismos conteos** en prosa, cifras, signos, emoji, saltos, marcadores especiales y en los prompts reales (receta renderizada **2469** tokens; seguimiento **1930**). Con texto NFD (acentos descompuestos) cuenta de más (lado seguro).
- **De punta a punta** con un Ollama simulado que responde con el tokenizador oficial: ia-api verificó las 6 sondas y activó el modo **exacto** (`pre_tokenizador: qwen35`); en las métricas, los tokens reales y la cota coinciden (1624/1624); todos los envíos con `num_ctx` 8192; prueba cruzada Laravel ↔ ia-api **0 fallos**; prueba en navegador (personalizar, editar, regenerar, cambio de teléfono, abrir WhatsApp) sin errores.
- Hallazgos corregidos en la auditoría: caracteres perdidos en 9 archivos, falta de soporte del tokenizador de Qwen3.5 (el modo exacto no se habría activado con el modelo real), sin reintento tras una verificación fallida, `/api/show` completo en cada llamada, reverificación periódica innecesaria, motivo de respuestas no JSON en Laravel y documentación de timeouts. Revisión cruzada de Antigravity: APROBADO.

## Pendiente en la PC con GPU
Tras desplegar, revisar `/health`: `modo_conteo` debe decir `exacto` y `pre_tokenizador` el nombre real que reporte Ollama. Si dice otro nombre no soportado, el log lo registra y basta con añadirlo a la tabla de `app/tareas/presupuesto.py`.
