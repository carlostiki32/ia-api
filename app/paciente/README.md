# Núcleo de explicación al paciente (integrado en W1b)

W1b integra este paquete desde inferencia, main y registro mediante `integracion.py`. Reutiliza el perfil CPU y la negación W0; no modifica constructores clínicos. La explicación validada no altera el clínico final que recibe.

## Interfaz integrada

`contexto_desde_receta(req, impresion_clinica_final, correlaciones)` recibe correlaciones efectivas como objetos con `nombre` y `texto`. Produce hechos con fuentes canónicas, ocurrencias personales con offsets originales, acciones y el perfil CPU. `construir_contexto(**caso)` permite al adaptador del oráculo construir exactamente los mismos hechos a partir de su contrato: los ids de síntomas aportados en ese contrato son la verdad del oráculo.

`await servicio.generar(contexto, llamar, llegada=..., reloj=..., hay_interactiva_esperando=..., plazos=...)` no adquiere GPU. `llegada` debe preceder a la cola y compartir base monotónica con `reloj`. `llamar(LlamadaPaciente)` ejecuta una única llamada con esquema, opciones, política estricta, timeout, think=False y tarea/etapa declarados; devuelve JSON, `RespuestaEtapa` o `(raw, metadata)`. El adaptador debe cumplir la cancelación de su transporte. El núcleo aplica además `asyncio.wait_for` y revalida el plazo después del conteo de presupuesto.

El resultado contiene `texto`, `estado`, `origen`, `motivo`, `regla` y `acciones_sin_mapear`. `integracion.py` incluye en la clave de caché las versiones de servicio, contexto, prompt, esquema, glosario, validador, verificador, acciones y respaldo, además del perfil; la respuesta publica `paciente_version`. No se cachean respaldos transitorios. El proveedor cuenta intentos físicos.

## Decisiones locales

- Ventanas mínimas iniciales configurables: un segundo para redacción, medio segundo para verificación y una décima de reserva CPU. Son valores operativos iniciales pendientes de medir en GPU.
- El proveedor se inyecta mediante un objeto de llamada, evitando dependencias del transporte y adquisiciones duplicadas de GPU. El comprobador de presupuesto también se puede inyectar; el predeterminado usa siempre política estricta.
- Los techos de entrada son 7000 y 7400: con las salidas 384 y 32 suman 7384 y 7432, respectivamente, por debajo de 7782. El conteo por llamada sigue siendo obligatorio. Un contexto mayor obtiene respaldo por presupuesto; no se recorta el clínico.
- El catálogo reconoce el texto clínico renderizado. Un inventario AST independiente enumera expresiones de acción y selectores; su snapshot falla si cambia una rama. Además se controlan los 32 sitios urgentes de 18 constructores. Las pruebas no prueban combinaciones cartesianas imposibles de hallazgos.
- El respaldo antepone acciones fuera de la plantilla heredada. No valida el bloque ensamblado con `validate_patient_text`; `build_patient_template` conserva su validación interna original.
- Ante más de 2000 puntos de código se elimina la prosa completa y se intenta solo el bloque de acciones. Si las acciones por sí solas exceden el límite, no existe una salida que cumpla simultáneamente integridad y longitud. La guarda extrema devuelve texto nulo, estado rechazada y motivo error, conservando el clínico. Esta decisión fue aceptada por Claude para W1b; no se trunca ninguna acción.
- No hay máximo finito de longitud del clínico final recibido en el contrato del núcleo. La medición de estrés de 60000 caracteres y todas las variantes es una prueba de rechazo de presupuesto, no la afirmación de un máximo posible ni de una combinación clínica realizable.

## Regla `lente` e interruptor

El lente se describe con `contexto.LENTES`. Monofocal no determina una distancia
de uso: `validar` rechaza lejos, cerca o lectura en la misma frase que monofocal.
Sí se permiten efectos de la graduación y ayuda de los lentes sustentados por
los hechos del caso, sujetos a las demás reglas; no se infieren adaptación,
materiales ni tratamientos.

`PACIENTE_LLM_HABILITADO` vale `true` por omisión. Con `false`, la integración
omite redacción/verificación y no recupera prosa paciente cacheada; devuelve
acciones + plantilla CPU, o el estado del perfil si no hay texto. El motivo es
nulo salvo fallo de ensamblado (`rechazada`/`error`). El clínico sigue su flujo.

El material para el dueño se genera desde el código con `scripts/catalogo_paciente.py`; incluye acciones,
glosario, system prompts, descripciones CPU del lente y versiones.

## Oráculo independiente

`tests/test_paciente_corpus.py` consume el corpus sin excepciones ni xfail. Tras el arbitraje independiente pasa 225/225. W1b no edita esos archivos. La fidelidad de paráfrasis sigue dependiendo del verificador y de la revisión clínica; los filtros léxicos no son una prueba semántica.

Pendientes externos: revisión editorial del catálogo/glosario, identidad del tokenizador contra el Ollama instalado y cancelación efectiva/latencias/calidad en GPU. Ver `SALIDA_DUAL.md` para el contrato integrado y los settings.
