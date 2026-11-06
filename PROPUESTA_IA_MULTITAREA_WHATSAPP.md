# Propuesta: ia-api multitarea y mensajes de WhatsApp personalizados al expediente

Fecha: 2026-11-06 · Repos: `Documents/ia-api` (FastAPI + Ollama qwen3.5:9b, RTX 3070 Ti 8 GB, PC del consultorio vía Cloudflare Tunnel) y `Documents/opt` (Laravel en VPS con Redis + supervisor).
Autoría: Claude (Opus) redacta; Codex (gpt-6.1-sol) y Antigravity (Gemini) auditaron y debatieron cada decisión. **Consenso: los tres votaron SÍ en la ronda 3 (ver sección D).**

> Nota de enfoque: usar más la GPU es una **consecuencia**, no el objetivo. Cada función nueva se justifica por su valor para el paciente o la óptica; la GPU está ociosa, así que el costo marginal es casi cero.

---

## A. Texto simple para el paciente: dictamen

**Veredicto: NO CERTIFICADO todavía (seguro, pero no cumple el criterio "el paciente entiende qué dice su graduación").** Coinciden Codex (no certificable), el agente certificador (no certificado) y agy (hueco MAYOR; certificable solo con condiciones).

Lo que está bien (verificado por los tres): clasificación óptica S / S+C correcta en casos frontera; catálogo cerrado imposible de "colar"; 144 perfiles → 143 textos válidos de 62–85 palabras y 1 sin componentes; contrato de estados API↔Laravel correcto; `rechazada` no se cachea; el PDF solo imprime texto aprobado; 220 pruebas de perfil/dual pasan.

Por qué no se certifica:
1. **No explica la graduación**: −0.25 y −12 producen el mismo texto; CIL −0.75 = −4.00; ADD 1.00 = 3.00. El texto nombra el tipo de corrección pero no qué es ESF/CIL/EJE/ADD ni cómo leer su receta. El PDF sí imprime la tabla (`informe_clinico.blade.php:490-531`), pero el texto está lejos y nada los une.
2. **Tutea** (143/143) mientras la óptica trata de usted.
3. **Ojo plano** omitido (OD −3 / OI 0 nunca menciona el izquierdo) y apertura repetida cuando los ojos difieren.
4. **Qwen no aporta** en este texto: solo elige entre 1–2 definiciones y 7 cierres fijos, y cuesta ~880 tokens del prompt.
5. **Operación**: el `.env` local tiene `OLLAMA_NUM_CTX=4096`; receta + AKR ya llega a 3921 tokens (límite efectivo 3891) → 413. Debe ser ≥ 8192 en la PC con GPU.
6. **Riesgo nuevo**: Laravel acepta y la tabla del PDF imprime cilindro positivo; ia-api lo transpone. Una explicación con cifras generada en ia-api no coincidiría con la tabla.

**Condiciones para certificar (Fase 0)**:
| # | Cambio | Prueba de aceptación |
|---|---|---|
| C1 | Bloque determinista "Cómo leer su receta" por ojo, **en Laravel**, con los mismos valores que imprime la tabla (sin transponer): ESF (signo; "ESF 0.00 indica ausencia del componente esférico"; solo ESF **y** CIL explícitamente 0.00 permiten decir que ese lado no lleva corrección de lejos), CIL, EJE ("orientación en grados; no mide cuánto ve"), ADD, dioptría = potencia del lente, no % de visión. Sin leve/moderado/alto salvo umbrales aprobados por el optometrista. | −1/−8 ≠ −1/−1; −0.25 ≠ −12; cilindro positivo con los signos de la celda; ojo plano; ADD en un ojo; nulos sin leyenda; en el PDF cada cifra coincide con su celda. |
| C2 | Explicación 100 % CPU (plantilla), fuera del prompt de Qwen; estado/origen acordados en ambos repos para que Laravel no muestre "plantilla de respaldo". | El prompt no contiene "PERFIL EDUCATIVO"; Laravel no dice "respaldo". |
| C3 | Trato de usted en catálogo, prompt y pruebas. | 0 tuteos en los 144 perfiles. |
| C4 | Ojo plano (ESF y CIL explícitamente 0.00) descrito por la receta, nunca por el ojo: "En el ojo izquierdo, su receta de lejos marca 0.00: ese lado no lleva corrección para ver de lejos" (con ADD: "…solo lleva el apoyo para ver de cerca"). Prohibido: sano, normal, no necesita, no requiere. Quitar apertura repetida. | OD −3/OI 0 menciona el izquierdo; ningún perfil contiene las palabras prohibidas. |
| C5 | `OLLAMA_NUM_CTX ≥ 8192` en la PC con GPU (evidencia del `.env` real). | Caso receta + AKR + clínica pasa sin 413. |
| C6 | Título "Explicación para el paciente"; marcar `PROPUESTA_RESUMEN_PACIENTE.md` como histórica (contiene "Tus ojos se encuentran saludables"). | grep. |
Certificar exige cerrar **C1–C6**. Después: re-auditoría con los 144 perfiles con cifras y PDF real de −1/−8, cilindro positivo, ojo plano con ADD y anisometropía miope/hipermétrope.

---

## B. ia-api multitarea: una GPU, varios trabajos

### B.1 Hoy
Un endpoint (`POST /inferencia/impresion-clinica`), un modelo de request, `run_inference` con ramas `if dual`; turno de GPU por `asyncio.Semaphore(1)` local al proceso, cola 5, espera 30 s, sin prioridades. El proveedor ya acepta `num_predict` y `format` por llamada y registra tokens/duración, pero temperatura/seed son globales. Caché RAM versionada solo en modo dual. Una receta puede costar más de una llamada (reintentos por transporte, truncamiento, JSON inválido).

### B.2 ¿Es viable? Sí, con tres condiciones
1. **Un solo modelo** cargado (qwen3.5:9b); cambiar de tarea = cambiar prompt, esquema y sampling, sin recargar pesos. Alternar tareas pierde el prefijo de caché (re-prefill); el costo se **mide**, no se supone.
2. **Una sola generación a la vez** (8 GB, ~28 % del modelo en CPU) en **un solo proceso** uvicorn (el turno es local al proceso; ya documentado "conservar un worker").
3. **Prioridad sin interrupción**: una receta puede esperar a lo sumo la generación de fondo **ya iniciada**; por eso las tareas de fondo deben ser cortas (num_predict bajo) y su espera máxima medida y documentada.
Además: `OLLAMA_KEEP_ALIVE` en la PC define si el modelo se descarga tras 5 min (por defecto); la PC puede estar apagada o jugando → toda función debe degradar a su respaldo sin GPU.

### B.3 Diseño
- **D-1 Endpoints separados y tipados** (Laravel declara el tipo; ningún LLM "detecta" la tarea): `POST /v1/inferencia/receta-clinica` (adaptador del actual) y `POST /v1/inferencia/seguimiento-whatsapp`. `POST /inferencia/impresion-clinica` conserva su contrato HTTP (también mientras C2 saca el texto educativo del prompt). Sin registro dinámico hasta que exista una tercera tarea; sí un contrato interno común mínimo: `prompts → opciones → llamada → validar → respaldo`.
- **D-2 Ejecutor único con admisión por prioridad** (`app/gpu_scheduler.py`, reemplaza el semáforo): interactivas primero; una tarea de fondo solo se admite si no hay interactivas pendientes; si no, `503 + Retry-After`. Laravel reintenta con backoff + jitter + caducidad. **Cada llamada al modelo** (incluidos reintentos y la pasada de verificación) vuelve a pedir turno; no se reserva la GPU para toda la cadena. La cota de espera de una receta incluye carga del modelo, prefill y generación. Al cancelarse el HTTP, la cancelación se propaga a la petición a Ollama; verificar en la GPU que la generación se detiene antes de liberar el turno.
- **D-3 Opciones por tarea** (temperatura, num_predict, format, seed), caché por tarea con versión de prompt/catálogo/modelo en la clave, métricas por tarea (tokens, duración, estado) **sin contenido clínico** en logs; esto exige retirar el volcado DEBUG del prompt (`app/inference.py:836`) y el payload del log de Laravel (`IaApiService.php:113`).
- **D-4 Patrón obligatorio para todo texto que llega al paciente**: hechos deterministas → LLM redacta dentro de un esquema → validador determinista → respaldo determinista → revisión humana. El LLM nunca tiene la última palabra y nunca maneja cifras (los meses también los calcula e inserta el código). Si un texto puede ser 100 % determinista, el LLM sobra.
- **D-5 Laravel**: `IA_API_BASE_URL` + ruta por tarea (hoy solo hay URL completa por endpoint), health cacheado como circuit breaker (no llamar si el túnel está caído), worker supervisor dedicado a la cola `ia`, con `timeout HTTP < timeout del job < retry_after` y margen operativo.

### B.4 Tareas candidatas
| # | Tarea | Prioridad | Nota |
|---|---|---|---|
| 1 | `receta-clinica` (impresión clínica) | interactiva | existe; tras C2 el texto del paciente sale del prompt |
| 2 | `seguimiento-whatsapp` | fondo / interactiva al regenerar | Parte C |
| 3 | `resumen-evolucion` (interno, previo a consulta) | interactiva | **riesgo medio**: puede influir decisiones clínicas; cálculos y cronología deterministas, el LLM solo narra |
| 4 | `mensaje-entrega` | fondo | solo con indicaciones realmente registradas |

---

## C. WhatsApp de seguimiento personalizado y persuasivo

### C.1 Hoy
`Pacientes/IndexPage::notificarWhatsApp` arma texto fijo (`lang/es/whatsapp.php`) y abre `wa.me`; **una persona siempre aprieta enviar** (no hay API Business). Marca `seguimiento_notificado_at` antes de abrir (abrir ≠ enviar). Semáforo: vencido, próximo (≤14 d), al día, con cita, pausado (`Descartado`), sin programar. El texto genérico actual ya incumple los límites de esta propuesta: promete "garantizar" la graduación óptima y la variante `con_costo` no dice que tiene costo → se corrige en F1.

### C.2 Flujo
- **D-6 Nunca bloquear al usuario**: al pulsar WhatsApp se abre vista previa **inmediata** con el borrador vigente si existe, o el genérico corregido. Botón "Personalizar con IA" genera en segundo plano (job + polling Livewire); si la GPU no está, se queda el genérico.
- **D-7 Preparación anticipada opcional** en una **ventana configurable** en que la PC suele estar encendida (no necesariamente de noche), con circuit breaker de health antes de despachar, solo para pacientes que entrarán a "próximo/vencido" en los siguientes días. Se activa **después** del piloto, cuando se conozca el volumen real de seguimientos.
- **D-8 Jobs seguros**: tenant explícito (en consola el scope global de tenant puede no aplicar), unicidad por paciente/ciclo/base_hash, revalidar al terminar el job y **justo antes de abrir WhatsApp** (cita, pausa, consentimiento, costo, base, versiones de catálogo/prompt); una respuesta tardía nunca sobrescribe una edición humana.
- **D-9 Persistencia y aprobación**: tabla `paciente_mensajes_ia` (tenant, paciente, tipo, texto, estado, origen, base_hash, versiones, generado_at, aprobado_por, aprobado_at, hash del texto aprobado, abierto_at, enviado_confirmado_at). **Ningún mensaje personalizado abre WhatsApp sin aprobación humana explícita del texto completo**; editarlo invalida la aprobación. "Abrir WhatsApp" y "Marcar como enviado" se separan.

### C.3 Qué datos viajan a ia-api (minimización)
- **D-10 Sí**: ESF/CIL/ADD numéricos de la **última** Rx final de lejos (sin eje), para que ia-api derive el tipo de corrección con la lógica ya auditada; `build_patient_profile` hoy exige `ImpresionClinicaRequest`, así que se adapta para recibir un tipo mínimo `RxLejos` (od/oi). Tramo de edad (si la edad es desconocida, no se personaliza) (adulto / ≥ 40 / ≥ 60), estado relativo (próximo / vencido y meses aproximados), política de costo (incluida / con costo), uso de pantallas solo si está registrado (`lt2|btw2_6|gt6`), tipo de lente.
- **No**: nombre, teléfono, folio, fechas exactas, dos Rx (comparación), ocupación libre, motivo de consulta, notas, impresión clínica, correlaciones, patologías, AKR. Nombre y clínica los pone Laravel al final (`:paciente`, `:clinica`).
- **D-11 Sin "progresión"** en v1: una diferencia de equivalente esférico no demuestra progresión (y omite cilindro/eje). ADD no demuestra presbicia ni envejecimiento: solo permite hablar de "su apoyo para ver de cerca".

### C.4 Cómo escribe Qwen sin inventar
- **D-12 Catálogo cerrado de hechos** escrito y firmado por el optometrista (en usted, sin miedo), cada uno con su regla de elegibilidad determinista. Ejemplos: miopía → "La miopía puede cambiar con el tiempo; revisarla periódicamente permite ajustar sus lentes si hace falta."; apoyo de cerca → "Revisar su graduación ayuda a confirmar que su apoyo para ver de cerca siga siendo el adecuado."; pantallas gt6 → "Si pasa muchas horas frente a pantallas, en la revisión podemos ver qué tan cómodos le resultan sus lentes."
- **D-13 Ensamblado por el servidor**: Qwen devuelve JSON `{apertura, hechos:[ids], invitacion}`. Elige los 0–2 hechos elegibles más relevantes para la persona y redacta una apertura cálida y una invitación que **sabe** que van antes y después de esos hechos (así el mensaje se lee de corrido). El servidor ensambla `apertura + frases de hechos (oraciones independientes, posición fija, texto literal del catálogo) + invitacion`. La prosa libre no puede modificar, negar ni interpretar las frases clínicas, y no puede contener ninguna afirmación clínica propia. Así, la parte clínica es 100 % del optometrista, y el tono y la selección son del modelo.
- **D-14 Validador determinista sobre el mensaje ensamblado**: 50–110 palabras; usted; `:paciente` y `:clinica` presentes una vez; ids elegibles, sin duplicados, correspondencia exacta id↔frase; ningún hecho adicional, repetido ni alterado; sin cifras (salvo meses); fuera de las frases de hechos, **vocabulario clínico prohibido** (nombres de condiciones, visión/ver borroso, graduación empeoró, ojo sano, etc.), léxico de miedo/urgencia/promesa/precio/descuento; costo coherente con la bandera; la **invitación** termina con una pregunta para agendar y después el servidor añade la línea fija de baja (fuera del conteo de palabras). La lista de palabras prohibidas es una defensa adicional, no una garantía semántica.
- **D-15 Segunda pasada de verificación con Qwen** (tarea de fondo barata, temp 0, JSON sí/no): "¿afirma algo sobre la salud, la visión o la graduación de esta persona fuera de las frases citadas?". Si dice sí, o hay timeout, JSON inválido o respuesta indeterminada → respaldo. Esta pasada vuelve a pedir turno de GPU. No es prueba formal, es una red adicional; la última red es la revisión humana.
- **D-16 Respaldo**: genérico corregido. Estados: `generada | plantilla | no_aplicable`.

### C.5 Ética y ley (no negociable)
- **D-17 Consentimiento demostrable** (LFPDPPP: datos de salud = sensibles): finalidad explícita en el aviso de privacidad, consentimiento expreso y por escrito con evidencia y autenticación conservadas (art. 8), más fecha, medio, versión del aviso y revocación, salvo excepción legal documentada. Sin registro → no se personaliza (y el uso del genérico también debe estar cubierto por el aviso). Documentar el recorrido VPS → Cloudflare → PC → WhatsApp y la retención. Validar con asesor legal: esta propuesta no es asesoría jurídica.
- **D-18 Menores**: no existe un campo de tutor/teléfono autorizado; hasta que exista, los menores reciben solo el genérico. El genérico también queda sujeto a D-17 y a verificar que el teléfono sea un destinatario autorizado.
- **D-19 Persuasión permitida**: relevancia personal, facilidad ("nosotros le agendamos"), costo verdadero, cuidado. **Prohibida**: miedo, culpa, urgencia falsa, promesas, descuentos inventados.
- **D-20 Nunca patologías por WhatsApp persuasivo** (se elimina la "Fase 2"). Una comunicación asistencial sobre hallazgos sería otro flujo dirigido por el profesional.

### C.6 Fases
| Fase | Contenido | Cierre |
|---|---|---|
| F0 | Condiciones C1–C6 del texto del paciente + `NUM_CTX` | re-auditoría y certificación |
| F1 | Contrato `seguimiento-whatsapp` en el diccionario, catálogo de hechos firmado por el optometrista, genérico corregido, consentimiento (D-17), exclusión de menores | revisión del optometrista |
| F2 | ia-api: endpoint, ejecutor con prioridad (D-2), validador, verificación, respaldo; regresión HTTP completa del endpoint clínico | pytest + regresión + pruebas adversariales (negación/contexto alrededor de hechos) + prioridad entre llamadas consecutivas |
| F3 | Laravel: tabla, payload builder, job con tenant explícito, vista previa no bloqueante, aprobación, abrir vs enviado, worker `ia` | pruebas de aislamiento, carreras, invalidación, aprobación, edición posterior y bloqueo de apertura sin aprobación vigente |
| F4 | Piloto en la GPU con **umbrales fijados antes** (latencia, espera máxima de una receta detrás de un mensaje, % de rechazo): % generada/plantilla, revisión humana de 50 mensajes, quejas/bajas | informe del piloto contra umbrales |
| F5 | Solo si F4 lo justifica: preparación anticipada (D-7) y medición de conversión con asignación aleatoria personalizado vs genérico (abrir WhatsApp no prueba exposición) | decisión del dueño |

### C.7 Ejemplo ilustrativo (paciente adulto, miopía, más de 6 h de pantallas, revisión incluida)
> **[apertura · Qwen]** Hola :paciente, le saludamos de :clinica. Se acerca la fecha de su revisión visual de control y quisimos recordársela con tiempo.
> **[hecho · catálogo]** En la revisión comprobamos si sus lentes le siguen dando una visión de lejos cómoda para sus actividades diarias.
> **[hecho · catálogo]** Si pasa muchas horas frente a pantallas, en la revisión podemos ver qué tan cómodos le resultan sus lentes para esas actividades.
> **[invitación · Qwen]** La revisión está incluida en su atención. ¿Qué día de la semana le queda mejor para venir?
> **[línea fija · servidor]** Si prefiere no recibir estos recordatorios, solo díganoslo.

*Corregido el 2026-11-06 tras la revisión clínica: la versión anterior combinaba «la miopía puede cambiar» con pantallas (insinúa causalidad no sustentada) y decía «esta semana». Catálogo completo: [CATALOGO_WHATSAPP_Y_TRATO_AL_PACIENTE.md](CATALOGO_WHATSAPP_Y_TRATO_AL_PACIENTE.md).*

Laravel sustituye `:paciente` y `:clinica`, muestra el texto completo para aprobación y solo entonces abre WhatsApp. Las frases de catálogo son ejemplos: las redacta y firma el optometrista en F1.

---

## D. Debate y consenso

| Ronda | Codex | Antigravity | Qué cambió |
|---|---|---|---|
| Auditoría del texto del paciente | NO CERTIFICABLE | Certificable con condiciones | Agente certificador independiente: **NO CERTIFICADO**, condiciones C1–C6 |
| R1 (borrador v1) | Acepta con cambios; rechaza el orden de fases | Rechaza el lote nocturno y el formato por ids | Endpoints tipados, vista previa no bloqueante, minimización fuerte, consentimiento demostrable, sin tutor inventado, sin patologías, piloto antes del refactor |
| R2 (v2) | 2 bloqueos (ESF 0.00; negación alrededor de frases literales) | SÍ | C1/C4 corregidos; D-13 pasa a ensamblado por el servidor + aprobación humana obligatoria |
| R3 (v3) | **SÍ** | **SÍ** (acepta explícitamente el nuevo D-13) | — |

Rechazado durante el debate, con razones: generar solo al vuelo con timeout de 4–5 s (un 9B con ~28 % en CPU no cabe ahí de forma fiable); prosa libre con hechos como premisas (no garantiza que no se nieguen ni se deformen); todo de catálogo (Qwen dejaría de aportar, como pasó con el texto del paciente); "progresión" a partir del equivalente esférico; deducir presbicia de la ADD; patologías por WhatsApp; dirigirse a un tutor que no existe en los datos.

Lo que este documento **no** afirma: latencias, tasas de aceptación ni conversión. Nada se ha medido en la GPU (esta PC es solo de desarrollo). Todo eso se mide en F4 contra umbrales fijados antes.

## E. Decisiones que le corresponden al dueño
1. Autorizar F0 (C1–C6) para certificar el texto del paciente.
2. Aprobar el trato de **usted** en el informe impreso.
3. Si quiere umbrales de magnitud (leve/moderado/alto) en "Cómo leer su receta"; si no, no se usan.
4. Redactar y firmar el catálogo de hechos del WhatsApp (F1).
5. Mecanismo de consentimiento y revisión con un asesor legal (D-17).
6. Horario en que la PC con GPU suele estar encendida (para D-7, tras el piloto).

Informes completos del debate: `auditoria/2026-11-06-texto-paciente-y-propuesta/`.
