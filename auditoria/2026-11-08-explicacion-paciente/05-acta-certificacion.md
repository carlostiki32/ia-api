# Acta de certificación — Explicación al paciente inferida por Qwen en el mismo proceso de la impresión clínica

Fechas: 2026-11-07 a 2026-11-12. Orquestación y auditoría: Claude. Implementación: Codex (ia-api) y Antigravity (Laravel, corpus, redacción de acciones, prueba en navegador). Sin commits: los hace el dueño.

## 1. Requerimiento (00) y consenso (01)
El dueño pidió que Qwen simplifique para el paciente, «lo más entendible posible», lo que dice la impresión clínica ya pasada por las correlaciones deterministas, en un **único proceso** con ella. Hasta el 2026-11-06 la explicación salía de una plantilla CPU sin la impresión clínica.

Diseño acordado por los tres en cuatro rondas (R1 independiente, R2 crítica, R3 y R3-bis de firma), en la versión `01-diseno-v2.1.md`. El flujo, en la misma petición y el mismo turno de GPU:
1. Clínico certificado sin cambios.
2. Punto de control.
3. Redacción del paciente con el clínico final y hechos deterministas.
4. Validador determinista.
5. Verificación con Qwen.
6. Ensamblado CPU, con las acciones obligatorias primero.
7. Respaldo con la plantilla si algo falla.

## 2. Qué quedó implementado
- **ia-api**
  - `app/paciente/` contiene los síntomas, el catálogo de acciones, el contexto, los prompts y el glosario, el validador, el ensamblado, el servicio y la integración.
  - En `app/main.py`, el modo dual tiene el plazo global medido desde la llegada, la caché separada del clínico y del paciente y el interruptor `PACIENTE_LLM_HABILITADO`.
  - El registro declara `explicacion-paciente` como tarea hija con las llamadas `redaccion` (384) y `verificacion` (32).
  - El proveedor usa la política estricta en las llamadas del paciente y cuenta métricas por intento.
  - `scripts/probar_enrutado.py` y `scripts/catalogo_paciente.py`.
- **Laravel (optica):**
  - Mensajes por estado y por motivo.
  - Metadatos opcionales tolerados: si son inválidos se descartan y no invalidan la respuesta.
  - `IA_API_TIMEOUT=90` por omisión, con la guía de despliegue corregida (decía 300).
  - Nuevos textos de «sin explicación» que ya no exigen ESF/CIL.
- **Correcciones previas (W0):**
  - `PresupuestoExcedido` vuelve a dar 413 en modo dual; antes daba 502.
  - Negación coordinada en las correlaciones.
- **Documentación:**
  - `SALIDA_DUAL.md`, `PIPELINE_LLM.md`, `README.md`, `DICCIONARIO_DATOS_RECETA.md`, `COMO_AGREGAR_UNA_TAREA.md` y `.env.example`.
  - El detalle de los cambios está en `03-correcciones-documentales.md`.

## 3. Hallazgos de la auditoría de Claude (todos corregidos)
1. **Regresión de seguridad en W0.** La primera corrección de la negación perdía 8 urgencias reales que el código certificado detectaba. Por ejemplo: «Sin antecedentes de importancia, acude por destellos desde ayer.», «Sin dolor, pérdida visual súbita en OD desde hoy.», o un desgarro detrás de «OD:». No la vieron ni sus 22307 pruebas ni su informe de 80,282 casos. Se corrigió con el principio **«ante ambigüedad gana la detección»**: la coma solo extiende la negación en listas cerradas por coordinador, sin cláusula nueva, sin señal de tiempo y sin núcleo de antecedentes.
2. Una pérdida más, hallada con una segunda sonda nueva: «SIN ANTECEDENTES, DESTELLOS Y SOMBRA EN OD DESDE AYER.». Se corrigió con el corte por tiempo y por antecedentes.
3. Conservar los saltos de línea del texto libre cambiaba el prompt clínico certificado. Ahora el prompt vuelve a aplanarse y las correlaciones usan las líneas.
4. Al prompt del paciente le faltaba el objetivo del dueño, explicar en la vida diaria y sin tecnicismos. Se agregó.
5. `opciones()` fijaba `num_ctx` y fallaría con un `OLLAMA_NUM_CTX` distinto de 8192.
6. La regla `lente` rechazaba frases correctas como «Sus lentes le ayudan a ver con más claridad los letreros lejanos.». El error estaba en el contrato que escribió Claude; ahora solo aplica cuando la frase nombra «monofocal». Lo halló la prueba de punta a punta.
7. Los metadatos opcionales inválidos tumbaban toda la respuesta en Laravel, y con ella el clínico.
8. Archivos con `\r\r\n`: todo `acciones.py` y el final de los 16 JSON del corpus.
9. En el corpus había 2 casos aceptables que violaban reglas (`aceptable-016` «levemente» y `aceptable-037` «no requieren»). Se arbitraron a favor del validador.
10. Codex dejó en el repo una carpeta con sus bitácoras de pruebas; se movió fuera.

## 4. Evidencia
- **Sondas de negación** (70 frases, foto previa frente a código final): 0 detecciones perdidas y 12 errores corregidos. El informe de Codex sobre 92,977 casos da 99 falsos positivos retirados, 22 recuperaciones y 0 bajas fuera del principio.
- **Clínico idéntico:** con la misma respuesta simulada, el clínico y el prompt salen iguales a la foto, también con entradas multilínea. De 52 payloads multilínea, 50 dan un prompt byte a byte igual y los otros 2 cambian solo por el conjunto de correlaciones.
- **Corpus independiente de Antigravity:** 225 casos (180 rechazos en 15 reglas y 45 aceptables) → 225/225. 17 frases naturales correctas → 17/17 aceptadas tras W1c.
- **Pruebas:**
  - ia-api: **23226 passed + 3 xfail**, con el tokenizador oficial. Los 3 xfail son la brecha de vocabulario del §6.
  - Laravel: **654 OK (3397 aserciones)** en una base exclusiva, con la huella de `laravel` y `laravel_testing` intacta.
  - JS: 37/37. Pint, `diff --check`, finales de línea y codificación limpios.
- **De punta a punta por HTTP** (ia-api real contra un Ollama simulado con el tokenizador oficial de Qwen3.5, en modo exacto):

  | Caso | Resultado |
  |---|---|
  | Éxito | `generada/llm` con 3 llamadas (clínica 1568, redacción 1327 y verificación 545 tokens) |
  | Caché completo | sin llamadas |
  | Tuteo | `plantilla/validacion` |
  | Verificación falsa | `plantilla/verificacion` |
  | Abstención | `plantilla/abstencion` |
  | Urgencia | acción de 48 h primero y después la prosa de Qwen |
  | Lento | `plantilla/timeout` a los 15 s, con HTTP 200 y el clínico |
  | Reintento | clínico de caché y solo se regenera la parte del paciente |

- **Navegador (Antigravity, Edge y Livewire reales):**
  - Éxito con el mensaje de `generada` y 3 llamadas.
  - Respaldo con su razón comprensible.
  - Urgencia con la acción primero.
  - Guardar y recargar conserva los textos.
  - Prueba cruzada `IaApiService` → `generada/llm`.
  - 0 errores de consola.
- **Tokens del prompt:** el system de redacción tiene 1012 (glosario 419) y el de verificación 174. Techos de entrada: 7000 y 7400. El caso máximo razonable queda muy por debajo de 7782.

## 5. Pendiente en la PC con GPU (no se puede probar aquí)
- Calidad real de Qwen: al menos 100 salidas revisadas, con un objetivo inicial de 90 % de explicaciones personalizadas válidas y 0 contradicciones críticas.
- Latencias en frío y en caliente; ajustar `PACIENTE_TIMEOUT_REDACCION_S` y `PACIENTE_TIMEOUT_VERIFICACION_S`.
- Que Ollama cancele de verdad la generación al vencer el plazo y libere la GPU.
- Competencia con WhatsApp y tasa de personalización bajo carga (con `PACIENTE_OMITIR_SI_ESPERA`).
- `scripts/probar_enrutado.py --modo real`.

## 6. Decisiones del dueño
1. **Receta sin conteo exacto:** `PRESUPUESTO_RECETA_SIN_EXACTO`. `conservador`, el actual, mantiene la receta disponible pero sin garantía demostrable. `estricto` da una garantía demostrable, pero la receta normal responde 413. Codex vota estricto; Antigravity y Claude, conservador.
2. **Revisar** `02-catalogo-y-prompts-para-revision.md`: las 104 frases de acciones, el glosario y los prompts.
3. **Etiquetas de magnitud** (leve, alta…): suspendidas hasta que apruebes umbrales.
4. **Consejos prácticos:** solo con respaldo en el clínico o en una correlación.
5. **Brecha previa de vocabulario** en las correlaciones (tarea aparte): no se detectan «perdió la visión», «viendo doble», «sombra en la visión» ni «pérdida de visión» sin «súbita». **Cerrada el 2026-11-12**: ver `auditoria/2026-11-12-cierre-y-certificacion-gpu/02-vocabulario-de-sintomas.md`.
6. **En el modo dual**, el plazo de 85 s desde la llegada acota también la llamada clínica, que antes tenía 120 s tras obtener la GPU. Es coherente con Laravel (90 s) y Cloudflare (100 s).

## 7. Despliegue y vuelta atrás
- **ia-api:** `pip install -r requirements.txt`, `OLLAMA_NUM_CTX=8192` y reiniciar. Luego revisar `/health`: debe decir `modo_conteo` exacto y `pre_tokenizador` `qwen35`.
- **Laravel:** `php artisan migrate`, `npm run build`, `IA_API_TIMEOUT=90` y `php artisan config:cache`.
- **Vuelta atrás sin desplegar:** `PACIENTE_LLM_HABILITADO=false`. Deja de llamar a Qwen para el paciente y entrega acciones más plantilla.
