# Pipeline de Inferencia Clinica - Documentacion Tecnica

**Actualización W1b del 8 de noviembre de 2026:** la llamada clínica conserva prompts, opciones, reintentos y depuración. En dual, un punto de control publica el clínico final antes de redactar y verificar la explicación dentro del mismo turno. Las acciones CPU se anteponen al texto; errores posteriores conservan clínico y respaldo con HTTP 200. El contrato vigente, las ventanas de tiempo y las dos cachés están en [SALIDA_DUAL.md](SALIDA_DUAL.md). `OLLAMA_DUAL_NUM_PREDICT` sigue sin usarse.

Este documento describe el funcionamiento real del pipeline LLM de la API clinica optometrica con base en el codigo actual de:

- `app/main.py`
- `app/config.py`
- `app/clinical_data.py`
- `app/cache.py`
- `app/prompt_builder.py`
- `app/inference.py`
- `app/providers/ollama.py`
- `app/correlaciones/` (paquete por dominio)
- `app/schemas.py`

El objetivo del sistema es transformar un payload estructurado de refraccion y hallazgos clinicos en un parrafo de impresion clinica en espanol, usando una combinacion de logica determinista y generacion con LLM.

## Tareas y enrutado

`GET /v1/tareas`, autenticado con la misma API key, describe las opciones activas.
La selección de tarea la hace la ruta HTTP; el modelo no detecta ni decide el enrutado.

| Tarea | Prioridad | Llamadas y formato | Opciones por omisión | Respaldo |
|---|---|---|---|---|
| receta-clinica | interactiva | Clínica, texto; legacy y alias `/v1/inferencia/receta-clinica` | `OLLAMA_TEMPERATURE=0.2`, `OLLAMA_NUM_PREDICT=1024`, semilla global | Avisos urgentes deterministas si existen; en otro caso error HTTP. Conserva reintentos actuales. |
| explicacion-paciente | interactiva; hija de receta-clinica, montaje manual | Redacción y verificación JSON Schema en el turno del padre | 0.2/384 y 0.0/32, semilla 42; entrada 7000/7400 | Acciones + plantilla CPU; motivo y clínico conservado. |
| seguimiento-whatsapp | fondo | Redacción JSON Schema y verificación JSON Schema | Redacción: 0.4, 320 tokens, semilla global + variante; verificación: 0.0, 32 tokens, semilla global | Plantilla determinista del catálogo; HTTP 200 con motivo. Una tentativa por etapa. |

En seguimiento, `num_ctx`, `top_p`, `top_k`, `min_p` y `repeat_penalty` provienen
de los settings activos. Una semilla global negativa se conserva como −1.
El presupuesto total de la cadena LLM es `SEGUIMIENTO_TIMEOUT=45.0` segundos,
incluidas las esperas de turno; al agotarse se cancela y responde `ia_timeout`.
Los errores de la verificación producen `verificacion`; el agotamiento del
presupuesto total prevalece como `ia_timeout`.

`app/gpu_scheduler.py` mantiene colas FIFO por prioridad bajo un candado.
`MAX_CONCURRENT` debe ser 1 y uvicorn debe conservar un único worker.
Las recetas reservan turno para toda su cadena y mantienen los códigos HTTP
existentes. El fondo pide un turno por llamada: se rechaza atómicamente si una
interactiva ocupa o espera. Detrás de otro fondo espera hasta
`FONDO_QUEUE_WAIT_TIMEOUT=10.0`; las recetas que llegan pasan primero.
El límite total de espera es `MAX_QUEUE_SIZE`; la espera interactiva usa
`QUEUE_WAIT_TIMEOUT`. Cancelar tanto esperas como ocupantes libera los recursos.
`/health` conserva `concurrencia` y añade `gpu`:
`ocupada`, `ocupante`, `en_espera_interactiva`, `en_espera_fondo`.

El seguimiento calcula elegibilidad usando la normalización auditada de la Rx.
No envía al modelo cifras de Rx, meses, identificador ni datos personales.
El modelo elige ids y redacta apertura/invitación; el servidor ordena e inserta
los textos literales. El validador devuelve la primera regla fallida; la segunda
llamada examina solo apertura e invitación. El respaldo usa rangos deterministas,
paridad de recetas y combinaciones válidas. La matriz cubre **15 360 perfiles**.

La caché propia LRU + TTL guarda exclusivamente respuestas `generada`, con copias
independientes. Su SHA-256 incluye request canónico sin `paciente_ref`, modelo,
versiones de contrato/catálogo/prompts y opciones de ambas etapas, incluida la
semilla efectiva. `meses_desde_ultima_receta` permanece en la clave aunque no se
muestre al modelo. Un acierto devuelve `generacion.cached=true`.

Política de logs de seguimiento sin contenido: solo `paciente_ref`, estado,
motivo, ids, prioridad y métricas de tokens/duración de Ollama. No se registran
request, prompts ni prosa. La normalización de Rx suprime sus avisos con cifras
solo en este contexto. El bloque DEBUG clínico del prompt renderizado fue
sustituido por tamaños de system/user en caracteres y tokens estimados.
El filtro léxico y la verificación no garantizan corrección semántica formal:
Laravel conserva la revisión humana antes de abrir WhatsApp.

`scripts/probar_enrutado.py` verifica el sistema con servidores HTTP locales
simulados; `--modo real --url ... --api-key-env ...` mide el servidor GPU.
El modo simulado no permite medir latencias reales, calidad de Qwen ni si Ollama
detiene efectivamente la generación cuando se cancela el cliente.

---

## Tabla de contenidos

1. Descripcion general
2. Flujo completo del request
3. Endpoint, autenticacion y control de carga
4. Schema de entrada
5. Validacion clinica minima
6. Capa determinista de correlaciones
7. Correlaciones activas actuales
8. Construccion del prompt
9. Inferencia — Ollama
10. Postprocesamiento del output
11. Recomendacion de seguimiento
12. Cache de inferencia
13. Salida esperada
14. Como extender el sistema
15. Logging y observabilidad

---

## 1. Descripcion general

La API recibe datos estructurados de un examen optometrico y devuelve un unico parrafo clinico. El pipeline combina dos capas:

- Capa determinista en Python: evalua reglas clinicas fijas y genera hechos pre-redactados.
- Capa generativa con LLM: redacta el parrafo final a partir de los datos del examen y de esas correlaciones ya evaluadas.

Esto separa claramente:

- la decision clinica reproducible de si una correlacion aplica o no;
- la redaccion natural del informe final.

### Motor de inferencia

El unico motor de inferencia es **Ollama local** con el modelo `qwen3.5:9b`
(`OLLAMA_MODEL` en `.env`). El sistema nunca sale a internet.

---

## 2. Flujo completo del request

```text
Cliente HTTP
  |
  v
POST /inferencia/impresion-clinica
  |
  |- Verificacion Bearer token
  |- Validacion Pydantic del payload
  |- Validacion minima de datos clinicos
  |- Cache lookup
  |- Cola de espera + semaforo de concurrencia
  |
  v
run_inference(req, httpx_client)
  |
  |- build_system_prompt()
  |- build_user_prompt(req)
  |    |- serializa contexto, refraccion, AKR y hallazgos clinicos
  |    |- evaluar_correlaciones(req)
  |    |- agrega bloque "Correlaciones clinicas aplicables" si hay activaciones
  |
  v
  validacion preemptiva de contexto (num_ctx) -> 413 si excede
  |
  v
providers/ollama.call(system, user, client)
  |
  |- POST /api/chat a Ollama (think=false)
  |- reintentos ante timeout / respuesta vacia / 5xx
  |
  v
_postprocess(raw_text)
  |
  |- elimina bloques <think> (completos, residuales o truncados)
  |- limpia listas, fences y espacios
  |- recompone un solo parrafo
  |
  v
clean_impresion(text)   <- guardarrailes deterministas (prompt_builder.py)
  |
  |- descarta oraciones con placeholders sin rellenar ([valor], 20/??)
  |- elimina meta-referencias al bloque de correlaciones
  |- descarta meta-comentarios sobre datos ausentes
  |- strip del participio "diagnosticad*" y reacentuacion de terminos clinicos
  |
  v
_ensure_follow_up_last(text, recomendacion)
  |
  |- evita duplicados
  |- agrega recomendacion al final si existe
  |
  v
Cache store
  |
  v
Respuesta JSON  { status, impresion_clinica, cached?, correlaciones_activadas }
```

---

## 3. Endpoint, autenticacion y control de carga

### Endpoint principal

- Ruta: `POST /inferencia/impresion-clinica`
- Handler: `crear_impresion_clinica()` en [`app/main.py`](app/main.py)

### Autenticacion

El endpoint requiere header:

```http
Authorization: Bearer <token>
```

Comportamiento:

- Si `API_KEY` no esta configurada: `500`
- Si falta el header o el esquema no es `Bearer`: `401`
- Si el token no coincide: `401`

La comparacion usa `hmac.compare_digest`.

### Concurrencia y cola

El sistema usa:

- `settings.max_concurrent = 1` (`MAX_CONCURRENT`)
- el planificador `GPUScheduler`, con colas FIFO por prioridad y un `asyncio.Lock`
- una cola maxima de espera de `5` requests (`MAX_QUEUE_SIZE`)
- `settings.queue_wait_timeout = 30.0` (`QUEUE_WAIT_TIMEOUT`; `<= 0` = espera sin limite)

Si la cola ya esta llena, el endpoint responde `503`.

En `clinica-v1`, si la inferencia supera `ollama_timeout`, responde `504`. En dual rige el plazo global desde la llegada: antes del punto de control devuelve 504; después devuelve 200 con clínico y respaldo.

### Resumen de codigos de error

| Codigo | Causa |
|---|---|
| `401` | Header `Authorization` ausente o token invalido |
| `413` | El prompt estimado + `num_predict` excede `num_ctx` (validacion preemptiva; revisar longitud de campos de texto libre) |
| `422` | Payload sin ningun dato clinico util (ver seccion 5) |
| `500` | `API_KEY` no configurada en el servidor, o error interno (detalle solo en logs) |
| `502` | Ollama devolvio un error HTTP no recuperable |
| `503` | Cola de espera llena |
| `504` | La inferencia no respondio dentro del timeout total |

### Warmup al arrancar

Durante el `lifespan` de FastAPI se crea un `httpx.AsyncClient` (timeouts separados de connect/read/write/pool para que un socket colgado no consuma el presupuesto completo) y se hace un warmup contra Ollama con `num_predict=1` y el **mismo `num_ctx` de produccion**, para que Ollama asigne el KV cache definitivo al arrancar y no en el primer request real. Si el warmup falla solo se loggea un warning (no es critico).

El default de `OLLAMA_NUM_CTX` permanece en 8192. Si su valor efectivo es menor,
el `lifespan` registra un warning: «OLLAMA_NUM_CTX=%d < 8192: recetas con AKR y
datos clínicos pueden devolver 413». Esto no modifica el `.env` ni sustituye la
verificación del contexto en el equipo con GPU.

---

## 4. Schema de entrada

El tipo raiz es `ImpresionClinicaRequest`.

> **Fuente de verdad:** el SaaS (Laravel) es la unica fuente que construye el payload. Todos los tipos, rangos y enums aqui listados reflejan lo que el SaaS realmente puede enviar (catalogos en `OpticaOptions` + `RecetaFormOptions`, validacion en `RecetaValidationRules`, construccion en `IaApiService::buildPayload`). El mapeo campo-por-campo esta en [DICCIONARIO_DATOS_RECETA.md](DICCIONARIO_DATOS_RECETA.md).

> **Politica de validacion: COERCION TOLERANTE (no rechazo).** El SaaS invoca este endpoint con el estado **crudo** del formulario, SIN pasar por `RecetaValidationRules` (el boton "Generar con IA" en `FormEditor::generateImpresionClinica` arma `toPayload()` y lo envia antes de guardar/validar). Por eso el schema **no** responde `422` ante un valor fuera de catalogo en un campo secundario: lo **descarta** (`None`) o lo **normaliza**, y lo registra en el log. También hay `422` ante errores de estructura/tipos o una `salida_version` inválida; la validación mínima rechaza solicitudes sin datos clínicos útiles (sección 5). Esto evita que un eje de 190 o una K corrupta tumben toda la generacion.

### Campos de primer nivel

| Campo | Tipo | Uso |
|---|---|---|
| `receta_id` | `str` | Identificador del caso. Se usa para logging seguro, no para el cache. Puede ser `"nueva"` cuando la receta aun no se guardo. |
| `paciente` | `ContextoPaciente` | Edad (calculada en SaaS), ocupacion y motivo de consulta. |
| `refraccion` | `Refraccion` | Refraccion final prescrita en OD y OI. |
| `akr` | `AkrSnapshot` | Medicion del autorrefractometro en OD y OI, metadata de la sesion (PD, VD, indice queratometrico) y, desde 2026-07, los valores de queratometria (K1, K2, K promedio, cilindro corneal) capturados en el mismo ticket. |
| `clinica` | `DatosClinica` | Hallazgos de examen clinico. |
| `tipo_lente` | `str \| None` | Diseno de lente prescrito. |
| `salida_version` | `Literal["clinica-v1", "clinica-paciente-v1"]` | Omitido usa `clinica-v1`; nulo u otro valor produce 422. |

### ContextoPaciente

| Campo | Tipo | Restriccion real del SaaS |
|---|---|---|
| `edad` | `int \| None` | Calculada desde `paciente.fecha_nacimiento` con `Carbon::parse(...)->age`. Si no hay fecha de nacimiento, llega `None`. |
| `ocupacion` | `str \| None` | Captura SaaS: `required\|max:120`. La API admite ausencia/nulo y trunca a 120 caracteres. |
| `motivo_consulta` | `str \| None` | Captura SaaS: `required\|max:1000`. La API admite ausencia/nulo y trunca a 1000 caracteres, conservando límites de línea. |

El SaaS **no envia** `nombre`, `telefono` ni `fecha_nacimiento`.

### GraduacionOjo

Se usa en `refraccion.od` y `refraccion.oi`.

| Campo | Tipo | Restriccion real del SaaS |
|---|---|---|
| `esfera` | `float \| None` | Dropdown `+20.00`..`-20.00`, paso `0.25`; la API admite ±30.00 D. Fuera de ese rango → `None`, también después de transponer. Default de captura `0.00`; ausencia en API permanece nula. |
| `cilindro` | `float \| None` | Dropdown `0.00`..`-8.00`, paso `0.25`; la API admite ±30.00 D y descarta fuera de ese rango. La Rx final con cilindro positivo se transpone a negativo. |
| `eje` | `int \| None` | Captura SaaS: `between:0,180`. La API conserva ese rango y normaliza los valores atípicos módulo 180 (`225`→`45`); nulo permanece nulo. |
| `add` | `float \| None` | Input libre, `between:0,30` en SaaS. La API convierte `add ≤ 0` o `add > 30` a `None`. |
| `av_sc` | `str \| None` | Dropdown `OpticaOptions::av` (16 valores): `20/10`, `20/15`, `20/20`, `20/25`, `20/30`, `20/40`, `20/50`, `20/60`, `20/70`, `20/80`, `20/100`, `20/120`, `20/160`, `20/200`, `20/400`, `20/600`. El schema **canoniza** `20/xx` (colapsa espacios); notaciones legacy no-Snellen se conservan; las categorías sub-Snellen reconocidas también pueden activar reglas de AV. |
| `av_cc` | `str \| None` | Mismos valores que `av_sc` (tambien canonizados) |

### AkrSnapshot — metadata de sesion

Ademas de `od` y `oi`, el snapshot incluye metadata comun a la sesion de medicion:

| Campo | Tipo | Restriccion real del SaaS |
|---|---|---|
| `ticket_id` | `int \| None` | Referencia al ticket de autorrefractometro/queratometro origen. `nullable\|integer\|exists:akr_tickets,id` |
| `pd` | `float \| None` | Distancia interpupilar; `0..100`, fuera de rango → `None`. |
| `vd` | `float \| None` | Distancia al vertice. `between:0,30`; fuera de rango → `None` |
| `ker_index` | `float \| None` | Indice queratometrico usado por el equipo para convertir mm↔D. `between:1.3,1.4`; fuera de rango → `None` |

El schema modela `taken_at` (fecha/hora de la medicion) y lo normaliza; junto con `ticket_id` participa en la clave del payload. No acredita por sí solo que AKR y receta pertenezcan al mismo instante ni permite inferir un ajuste clínico.

### AkrOjo

Se usa en `akr.od` y `akr.oi`. Es un snapshot del autorrefractometro; **no** incluye `add`, `av_sc` ni `av_cc`. `pd` existe pero a nivel de sesion (`akr.pd`), no por ojo.

> **Transposición de AKR y Rx final.** Ambos schemas convierten cilindro positivo a negativo: `esf' = esf + cil`, `cil' = -cil`, `eje' = ((eje + 90) % 180) or 180`. Si falta esfera o eje, se conserva nulo. La Rx final verifica además el rango de esfera después de la transposición. Las reglas AKR activas son `ar_rx_variabilidad_inespecifica` y `ar_detecta_astigmatismo_no_prescrito`; describen registros sin acreditar simultaneidad ni una causa clínica.

Desde 2026-07 el SaaS captura tambien la prueba de queratometria en el mismo ticket AKR (dato nuevo, antes no se enviaba):

| Campo | Tipo | Restriccion real del SaaS |
|---|---|---|
| `esfera` | `float \| None` | |
| `cilindro` | `float \| None` | |
| `eje` | `int \| None` | |
| `k1_d` | `float \| None` | Meridiano plano (K1) en dioptrias. Fisico `25..80`; fuera → `None` |
| `k1_mm` | `float \| None` | K1 en radio de curvatura. `4..12`; fuera → `None` |
| `k1_eje` | `int \| None` | Eje de K1. Ciclico: normalizado modulo 180 |
| `k2_d` | `float \| None` | Meridiano curvo (K2) en dioptrias. `25..80`; fuera → `None` |
| `k2_mm` | `float \| None` | K2 en radio de curvatura. `4..12`; fuera → `None` |
| `k2_eje` | `int \| None` | Eje de K2. Ciclico: normalizado modulo 180 |
| `k_promedio_d` | `float \| None` | K promedio en dioptrias. `25..80`; fuera → `None` |
| `k_promedio_mm` | `float \| None` | K promedio en radio de curvatura. `4..12`; fuera → `None` |
| `k_cilindro` | `float \| None` | Cilindro corneal (K2 - K1 con signo). `-30..30`; fuera → `None` |
| `k_cilindro_eje` | `int \| None` | Eje del cilindro corneal. Ciclico: normalizado modulo 180 |

### DatosClinica

| Campo | Tipo | Restriccion real del SaaS |
|---|---|---|
| `uso_pantallas` | `"lt2" \| "btw2_6" \| "gt6" \| None` | Enum cerrado |
| `anexos_oculares` | `str \| None` | Texto libre `max:255` |
| `reflejos_pupilares` | `str \| None` | `max:255`. **La UI compone** `"{opcion}: {nota}"`. Opciones UI fijas: `"Reflejo fotomotor, consensual, acomodativo"` o `"Marcus Gunn"` |
| `motilidad_ocular` | `str \| None` | `max:255`. **La UI compone** una sola linea: `"Versiones: X Ducciones: Y Sacadicos: Z Seguimiento: W"` (los saltos de linea se colapsan en el SaaS antes de enviar) |
| `confrontacion_campos_visuales` | `str \| None` | Texto libre `max:255` |
| `fondo_de_ojo` | `str \| None` | Texto libre `max:255` |
| `grid_de_amsler` | `str \| None` | Texto libre `max:255` |
| `ojo_seco_but_seg` | `int \| None` | Dropdown `1..15` (segundos). Fuera → `None` |
| `cover_test` | `str \| None` | `max:255`. **La UI compone, si se captura la prueba,** `"OD: {tipo_od}[ y {sub_od}] \| OI: {tipo_oi}[ y {sub_oi}]"`. `tipo ∈ {Orto, Endo, Exo, Hiper, Hipo}` (radio; si no se toca en receta nueva viaja nulo); `sub ∈ {Tropia, Foria}` (radio **SIN default, opcional**). Ejemplos reales: `"OD: Orto \| OI: Exo y Foria"`, `"OD: Endo y Tropia \| OI: Orto"`, y **tipo sin sub**: `"OD: Exo \| OI: Orto"`. La capa de correlaciones parsea el formato canonico y dispara tambien con el tipo sin clasificar (ver seccion 6). **No** se envian cadenas como `"exoforia"` unidas. |
| `ppc_cm` | `int \| None` | Dropdown `1..15` (cm). Fuera → `None` |
| `recomendacion_seguimiento` | `str \| None` | Texto libre (TEXT en DB); la API trunca a 60000 caracteres |

### Normalizaciones Pydantic relevantes

- Los textos clínicos conservan límites de línea, colapsan espacios dentro de cada línea y se truncan a 500 caracteres; `recomendacion_seguimiento` admite 60000. El prompt clínico aplana estos textos al serializarlos.
- `cover_test` reemplaza además `" - "` por `" y "`. El SaaS ya envía `" y "`; la normalización es defensiva.

### Campos que existen en la receta del SaaS y que NO llegan

El ia-api nunca debe asumir ni procesar ninguno de estos:

- Paciente: `nombre`, `telefono`, `fecha_nacimiento` (se envia solo `edad`).
- Graduacion: `prisma`, `base_prisma`, `dnp`, `altura_montaje`.
- Receta: `folio`, `estado`, `fecha_receta`, `precio_total`, `anticipo`, `observaciones_laboratorio`, `akr_pd`.
- Lente: `material`, `tratamientos`, `armazon_marca`, `armazon_modelo`, `armazon_color`.
- Clinica: `impresion_clinica_plan` (ese es precisamente la salida de esta API, nunca entrada).

### Alineacion del schema con el catalogo del SaaS (estado actual)

El schema ([`app/schemas.py`](app/schemas.py)) refleja el catalogo real del frontend
con **coercion tolerante**: un valor fuera de catalogo en un campo secundario se
descarta o normaliza (con warning en log), nunca tumba la generacion con `422`.

- `refraccion.od/oi.eje` y todos los ejes de AKR (`eje`, `k1_eje`, `k2_eje`,
  `k_cilindro_eje`): el eje es **ciclico**; fuera de `0..180` se normaliza modulo 180
  (`225`→`45`). El contrato SaaS valida `0..180`; la API tolera valores atípicos.
- `paciente.edad`: `0..125`; fuera → `None` (comportamiento conservador de las reglas
  que dependen de la edad).
- `esfera` (`±30.00`), `cilindro` (`±30.00`), `ojo_seco_but_seg`/`ppc_cm` (`1..15`),
  `vd` (`0..30`), `ker_index` (`1.3..1.4`), K en dioptrias (`25..80`) y en mm (`4..12`):
  fuera del rango de recepción → `None`. Los límites de esfera/cilindro admitidos por la API son más amplios que los dropdowns de captura.
- `add ≤ 0` o `add > 30` → `None`: el input de add es libre y un `0` tecleado no es una adicion
  prescrita. Las correlaciones de presbicia por edad/ADD se retiraron el 22 de septiembre de 2026; ADD no acredita ese diagnóstico.
- **Transposicion de AKR y Rx final**: ambos schemas convierten cilindro positivo a negativo y conservan esfera/eje nulos cuando faltan.
- `av_sc` / `av_cc` se **canonizan**: `" 20 / 40 "` → `"20/40"`. Notaciones no-Snellen
  legacy se conservan; CD, MM, PL y NPL reconocidos usan centinelas internos para filtros de AV.
- `uso_pantallas` es enum cerrado (`lt2`/`btw2_6`/`gt6`); un valor fuera → `None`.
- `tipo_lente` se normaliza (espacio) pero **no** se cierra a enum: el catalogo canonico
  del SaaS es `monofocal | bifocal_blended | progresivo | flat_top`, pero puede crecer
  sin coordinacion con la API. La deteccion multifocal se hace por tokens e **incluye
  `flat_top`** (bifocal de segmento). El prompt mapea la clave a etiqueta legible
  (ver seccion 8).
- No se declara `extra="forbid"`: se toleran campos adicionales para no romper ante
  despliegues desincronizados entre SaaS y API.

Las pruebas y ejemplos deben preferir valores que la UI real del SaaS si puede
producir. En particular, `cover_test` se modela como
`"OD: {tipo}[ y {sub}] | OI: {tipo}[ y {sub}]"` (con el sub opcional), no como strings
sinteticos tipo `"ortoforia"` o `"exoforia en VP"`.

---

## 5. Validacion clinica minima

Antes de inferir, `has_clinical_data(req)` valida que exista al menos un valor no nulo dentro de:

- `req.refraccion`
- `req.akr.od` o `req.akr.oi` (la metadata AKR sola no basta)
- `req.clinica`

No basta con enviar solo:

- `paciente.edad`
- `paciente.ocupacion`
- `paciente.motivo_consulta`
- `tipo_lente`

Si no hay datos de refraccion ni datos clinicos, la API responde `422`.

---

## 6. Capa determinista de correlaciones

### Arquitectura

La logica esta particionada por dominio clinico en el paquete
[`app/correlaciones/`](app/correlaciones/):

- Dominios: `fondo_de_ojo`, `refractivas`, `akr`, `corneal`,
  `anexos_cristalino`, `segmento_anterior`, `pupilas_motilidad`, `motilidad`,
  `sintomas_agudos`, `campos_amsler`, `binocularidad`, `superficie_ocular`, `contexto`.
- Helpers compartidos: `base` (memoizacion + tipo `Correlacion`), `texto`
  (normalizacion y matching), `refraccion_utils` (Snellen, equivalente esferico),
  `queratometria` (lectura corneal).
- `registry.py`: ensambla `CORRELACIONES` en el orden fijo de evaluacion y expone
  `evaluar_correlaciones` y `nombres_correlaciones_activas`.
- `__init__.py`: API publica estable (`Correlacion`, `CORRELACIONES`,
  `evaluar_correlaciones`, `nombres_correlaciones_activas`), consumida por
  `prompt_builder` y `main`.

Cada correlacion se define como `_cond_x(req) -> bool` y `_texto_x(req) -> str`
(o un texto constante) y se registra como:

```python
Correlacion("nombre", _cond_x, _texto_x)
```

La funcion publica `evaluar_correlaciones(req)`:

1. recorre `CORRELACIONES` en orden fijo dentro de un unico scope de memoizacion;
2. ejecuta cada condicion;
3. si una condicion es `True`, agrega su texto a la lista final;
4. registra en log los nombres activados.

`nombres_correlaciones_activas(req)` devuelve solo los nombres (para trazabilidad
en la respuesta HTTP), con la misma logica de supresion.

### Propiedades del motor

- Determinista: mismo input, mismas correlaciones.
- None-safe: las condiciones hacen guards explicitos.
- Ordenado: la posicion en `CORRELACIONES` (en `registry.py`) define el orden del
  bloque que recibe el LLM; es un invariante clinico cubierto por tests.
- Textual: las correlaciones generan texto final, no instrucciones.
- Verificación determinista: los 47 textos exactos están cubiertos por pruebas *golden*
  (`tests/test_correlaciones_golden.py`) que auditan su activación y contenido exacto.

### Helpers clinicos relevantes

#### `_av_denominator(av)`

Extrae el denominador Snellen equivalente en pie a partir de las tres notaciones que
emiten los frontends: pie (`20/40`), metrica (`6/12`) y decimal (`0.5` / `0,5`).
Las categorías sub-Snellen CD, MM, PL y NPL reconocidas usan centinelas internos
para ordenamiento, sin equivalencia Snellen medida; las no interpretables devuelven `None`.

#### `_av_es_limitada(av)`

Retorna `True` solo cuando el denominador Snellen equivalente es mayor a 25
(es decir 20/30 o peor).

Esto evita falsos positivos con AV supranormal o casi normal, por ejemplo `20/15`
o `20/25`.

#### `_av_categoria(av)`

Devuelve `AV con correccion registrada inferior a 20/25; pendiente de verificacion`
si el denominador supera 25, o `None` en los demás casos. No clasifica gravedad
ni discapacidad.

#### `_equivalente_esferico(esf, cil)`

Calcula:

```python
esfera + cilindro / 2.0
```

Requiere ambos componentes registrados; si falta uno devuelve `None`.
Se usa para anisometropia, miopia magna e hipermetropia alta.

#### Helpers de queratometria

Los helpers `_k_values`, `_has_keratometry`, `_k_steepest_d`, `_corneal_cyl_abs`,
`_keratometry_axis`, `_keratometry_supports_astigmatism`, `_keratometry_axis_matches`
y `_keratometry_suggests_corneal_irregularity` leen valores registrados sin
establecer anatomía ni etiología. El selector de valores elevados exige K ≥ 48.70 D,
o K ≥ 47.20 D junto con cilindro corneal ≥ 1.50 D, o cilindro corneal ≥ 4.00 D;
rechaza queratometría contradictoria. Son criterios operativos de revisión.
`corneal.py` contiene `queratocono_ectasia_sospecha`,
`astigmatismo_corneal_vs_refractivo`, `cornea_plana_extrema` y
`queratometria_asimetrica_interocular`. La Rx y la queratometría aportan registros
independientes; no prueban un mecanismo refractivo o lenticular ni una causa de AV.
El detalle está en [CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md).

### Matching de texto libre

El modulo usa normalizacion de texto:

- lowercase
- remocion de acentos con `unicodedata.normalize`
- colapso de espacios

Como los campos cualitativos son de **texto libre** (no dropdowns), las listas de
keywords estan enriquecidas con sinonimos clinicos, coloquialismos mexicanos
(`carnosidad`=pterigion, `calacio`=chalazion, `perrilla`=orzuelo), abreviaturas
(`RAPD`, `IOL`, `RDNP`, `E/P`, `DGM`) y variantes de escritura/plural. Las abreviaturas
de 3-4 letras que son subcadena de palabras comunes (`mer`, `irma`, `adie`, `iol`,
`isnt`, `cnv`, `cscr`, `emq`...) se listan en `_WHOLE_WORD_KEYWORDS` y se buscan como
**palabra completa** para no disparar dentro de otras palabras ("afirma", "nadie",
"violeta").

Para varios hallazgos se usa negacion por oracion. El sistema busca la keyword dentro de una oracion y revisa si antes de esa keyword, dentro de la misma oracion, aparece alguna marca de negacion como:

```python
("sin ", "no se observa", "no se documenta", "no presenta", "sin evidencia", "negativ", "ausenc", "ausente")
```

Si existe negacion previa en esa misma oracion, la coincidencia se descarta.

Esto se usa, por ejemplo, en:

- fondo de ojo
- pupilas
- motilidad
- campos visuales
- Amsler
- anexos
- opacidad del cristalino

#### Cover test: parser estructurado del formato canonico

Ademas del matching por keywords, `texto.py` parsea el formato canonico del SaaS
(`"OD: {tipo}[ y {sub}] | OI: {tipo}[ y {sub}]"`) con dos rutas complementarias:

- `_normalize_cover_text`: expande los pares `"exo y foria"` → `"exoforia"` para que
  las keywords unidas (`exoforia`, `endotropia`, `hiperforia`...) matcheen.
- `_cover_desviaciones`: cuando el optometrista eligio el tipo pero **dejo el sub sin
  clasificar** (`"OD: Exo | OI: Orto"`, estado real porque el sub es un radio sin
  default), devuelve el tipo suelto (`exo`, `endo`, `hiper`, `hipo`). `orto` no genera
  token.

Con esto, un tipo sin clasificar **si dispara** la correlacion binocular correspondiente
(`ppc_exoforia`, `cover_endoforia_sintomatica`, `desviacion_vertical`) con un texto que
pide precisar foria/tropia, pero **nunca** se trata como tropia manifiesta: las reglas
`endotropia_lente`/`exotropia_lente` y el factor-tropia de `ambliopia_sospecha` siguen
exigiendo el sub `Tropia` explicito. El detalle clinico esta en
[CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md) seccion 10.

---

## 7. Correlaciones activas actuales

El registro contiene **47 correlaciones medicas** (mas 1 recordatorio tecnico, evaluado aparte), particionadas por dominio clinico en el
paquete `app/correlaciones/` (ver estructura en la seccion 6).

> **Fuente de referencia clinica:** el catalogo completo de las 47 correlaciones medicas y el recordatorio tecnico
> —campos que las disparan, umbrales, keywords, texto exacto generado y **fundamento
> clinico con evidencia**— vive en [CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md).
> Este documento ya no lo duplica, para evitar la divergencia que existia entre ambos.
> Los textos exactos estan auditados por pruebas *golden* en
> `tests/test_correlaciones_golden.py`: si una regla cambia su texto sin actualizar la
> prueba, la suite falla.

El **orden de evaluacion** es un invariante clinico (los hallazgos urgentes van
primero) definido explicitamente en `app/correlaciones/registry.py` y cubierto por
tests (`test_registro_separa_47_medicas_y_un_recordatorio_tecnico`,
`test_but_critico_esta_antes_que_correlaciones_contextuales`).

Trazabilidad: la respuesta HTTP incluye `correlaciones_activadas` con los nombres de
las reglas que aplicaron al caso (ver seccion 13).

---

## 8. Construccion del prompt

### `build_system_prompt()`

El system prompt es **inmutable** (~1595 tokens) para permitir que Ollama / llama.cpp mantenga y reutilice el **KV Prefix Cache** a traves de peticiones consecutivas, reduciendo drasticamente el Time-To-First-Token (TTFT). Esta organizado en bloques explicitos (el texto completo vive en [app/prompt_builder.py](app/prompt_builder.py)):

- **Regla de oro — nunca diagnosticar:** prohibe emitir diagnosticos o nombres de
  enfermedad, escalar un hallazgo a una entidad clinica, y proponer descartes,
  estudios o conductas que no provengan textualmente de una correlacion del bloque
  "Correlaciones clinicas aplicables".
- **Solo lo que aparece en el user prompt:** prohibe describir campos ausentes,
  rellenar ausencias con normalidad supuesta ("el fondo de ojo es normal" cuando no
  vino), inventar valores o usar placeholders (`[valor]`, `20/xx`), e interpretar
  por cuenta propia valores numericos sueltos (BUT, PPC, queratometria) sin
  correlacion que los interprete.
- **Formato:** maximo `{settings.max_sentences}` oraciones en un solo parrafo corrido, sin bullets ni
  encabezados, "El paciente" en tercera persona sin asumir genero, tiempo presente,
  español con acentos, punto final. Sin recomendaciones de seguimiento propias.
- **Orden de redaccion:** motivo de consulta y AV s/c → refraccion final con AV c/c
  (respetando el signo: esfera negativa = miopia) → hallazgos presentes →
  correlaciones integradas como observacion objetiva.
- **Urgencia restringida:** "urgente/inmediata/prioritaria/grave" SOLO cuando el
  texto de una correlacion trae el prefijo `Hallazgo urgente:`; en ese caso el
  hallazgo va en la **segunda o tercera oracion** del parrafo.
- **Integracion de correlaciones:** reescribir cada correlacion con palabras propias
  (nunca pegar el texto literal ni el prefijo `Hallazgo urgente:`), integrada al
  flujo del parrafo.
- **Sin meta-referencias ni meta-comentarios:** prohibido mencionar "correlaciones",
  el nombre del bloque interno, o comentar que falta un dato ("no se dispone de...").
- **Glosario** para interpretar los datos sin copiarlo al parrafo: PPC (punto proximo
  de convergencia, cm), BUT (tiempo de ruptura lagrimal, s), c/d o E/P (relacion
  copa/disco), AV s/c / AV c/c.

Si existe recomendacion de seguimiento, `_ensure_follow_up_last()` la agrega deterministamente al final.

> El LLM pequeño (9B) no respeta estas reglas de forma 100% fiable; por eso ademas
> del prompt existen los **guardarrailes deterministas** de `clean_impresion`
> (seccion 10), que limpian placeholders, meta-referencias, meta-comentarios de
> ausencia y el participio "diagnosticad*" de la salida.

### `build_user_prompt(req)`

Construye un prompt dinamico por secciones.

Orden real:

1. `Contexto del paciente`
2. `Refraccion final`
3. `Datos AKR/queratometria y refraccion final` (mediciones registradas sin inferir ajuste, causa ni identidad temporal)
4. Bloques clinicos sueltos
5. `Diseno de lente prescrito`
6. `Correlaciones clinicas aplicables (hechos pre-evaluados del caso)`
7. `Genera el parrafo.`

### Secciones incluidas

#### Contexto del paciente

Incluye si hay datos:

- `Edad`
- `Ocupacion`
- `Motivo de consulta`

#### Refraccion final

Cada ojo se serializa con `_format_ojo()`.

Posibles componentes:

- `Esf`
- `Cil`
- `Eje`
- `Add`
- `AV s/c`
- `AV c/c`

Un `Eje` sin cilindro (posible cuando la coercion descarto esfera/cilindro fuera de
catalogo y solo sobrevivio el eje) **se omite**: un eje suelto no tiene sentido
clinico y confundia al modelo.

#### Correlacion AKR/queratometria vs refraccion final

Este bloque aparece si existe al menos un valor no nulo en la metadata de `akr` (`ticket_id`, `pd`, `vd`, `ker_index`) o en `akr.od`/`akr.oi` (incluyendo los campos de queratometria).

Orden por linea, si hay datos:

- `AKR metadata: PD ..., VD ..., Indice queratometrico ...` (solo si alguno de esos tres esta presente)
- `AKR OD: ...` / `Rx final OD: ...`
- `Queratometria OD: K1 ..., K2 ..., K promedio ..., Cil corneal ...`
- `AKR OI: ...` / `Rx final OI: ...`
- `Queratometria OI: ...`

Dentro del bloque, las líneas `AKR OD/OI`, `Rx final OD/OI` y
`Queratometria OD/OI` se agregan independientemente si cada una tiene datos.

#### Hallazgos clinicos sueltos

Se agregan como lineas individuales, con estas etiquetas exactas:

- `Uso de pantallas: {menos de 2 / entre 2 y 6 / mas de 6} horas diarias`
- `Anexos oculares: ...`
- `Reflejos pupilares: ...`
- `Motilidad ocular: ...`
- `Confrontacion de campos visuales: ...`
- `Fondo de ojo: ...`
- `Grid de Amsler: ...`
- `Tiempo de ruptura lagrimal (BUT): {X} segundos`
- `Cover test: ...`
- `Punto proximo de convergencia (PPC): {X} cm`

Las etiquetas de BUT y PPC van desplegadas (no solo la sigla) para que el modelo no
malinterprete la abreviatura; el glosario del system prompt las refuerza.

#### Tipo de lente

Se agrega como:

```text
Diseno de lente prescrito: ...
```

La clave canonica del SaaS se mapea a una etiqueta clinica legible via `TIPO_LENTE_MAP`
para que el LLM no copie la clave cruda (`bifocal_blended`) al parrafo:

| Clave SaaS | Etiqueta en prompt |
|---|---|
| `monofocal` | `monofocal` |
| `bifocal_blended` | `bifocal blended (sin linea visible)` |
| `progresivo` | `progresivo` |
| `flat_top` | `bifocal flat-top (segmento visible)` |

Una clave fuera del catalogo se pasa tal cual (texto libre legacy).

#### Correlaciones clinicas aplicables

Si `evaluar_correlaciones(req)` devuelve elementos, se agrega:

```text
Correlaciones clinicas aplicables (hechos pre-evaluados del caso):
- ...
- ...
```

### Sanitizacion

Los campos de texto libre (ocupacion, motivo, hallazgos clinicos y los textos de las
correlaciones) pasan por `_sanitize()`, que elimina los tokens de control de Qwen3.5
que podrian romper el chat template si se inyectan accidentalmente en texto clinico
(p. ej. copiado desde un log del modelo):

- directivas `/think` y `/no_think` (no soportadas en Qwen3.5, pero se eliminan igual);
- delimitadores del chat template: `<|im_start|>`, `<|im_end|>`, `<|system|>`,
  `<|user|>`, `<|assistant|>`;
- tags `<think>`/`</think>` y `<tool_call>`/`</tool_call>`.

Campos numericos no se sanitizan porque ya estan validados por schema.

### Mapeo de uso de pantallas

| Valor | Texto en prompt |
|---|---|
| `lt2` | `menos de 2 horas diarias` |
| `btw2_6` | `entre 2 y 6 horas diarias` |
| `gt6` | `mas de 6 horas diarias` |

---

## 9. Inferencia — Ollama

La funcion central es `run_inference(payload, client)` en `app/inference.py`:
construye los prompts, valida el contexto de forma preemptiva, llama a Ollama y
aplica el postprocesado + guardarraíles. En `clinica-v1` devuelve el párrafo;
en dual publica el punto de control y devuelve `DualInferenceResult` tras la rama paciente.

### Cliente Ollama (`app/providers/ollama.py`)

- Endpoint: `POST {OLLAMA_URL}/api/chat`
- Modelo: `OLLAMA_MODEL` (default: `qwen3.5:9b`)
- `stream = False`, `think = False`

| Parametro | Valor | Por que |
|---|---|---|
| `temperature` | `0.2` | Tarea de extraccion/reporte fiel, no chat general; con seed fijo la salida es casi determinista y auditable |
| `top_p` | `0.8` | Preset non-thinking oficial de Qwen3.5 |
| `top_k` | `20` | Preset non-thinking oficial de Qwen3.5 |
| `min_p` | `0.0` | Preset non-thinking oficial de Qwen3.5 |
| `repeat_penalty` | `1.0` | Desactivado: la terminologia clinica exige repeticion exacta (OD/OI, agudeza visual). El `presence_penalty=1.5` del preset oficial **no** existe en Ollama y **no** debe mapearse a `repeat_penalty` (semanticas distintas) |
| `num_predict` | `1024` | Elimina el truncado (`done_reason=length`) en casos con 4+ correlaciones activas |
| `num_ctx` | `8192` | El system prompt afinado pesa ~1595 tok y el payload maximo del diccionario ~3300 tok: con `num_predict=1024` no cabia en 4096 (daba `413`). Medido en la 3070 Ti: 4096→8192 solo sube el footprint 0.2 GB |
| `seed` | `42` | Reproducibilidad (`-1` para variabilidad) |
| `ollama_max_retries` | `2` | Número total de intentos del proveedor; reintenta ante ReadTimeout, contenido vacío/inválido o HTTP 500/503. |

Cada valor esta comentado con su justificacion (incluidas las mediciones de VRAM en
la 3070 Ti) en [app/config.py](app/config.py).

Se reintenta ante: `httpx.ReadTimeout`, `ValueError` por respuesta vacia, HTTP 500/503.
Tras la respuesta, si `done_reason == "length"` se loggea warning de salida truncada.

### Validacion preemptiva de contexto

Antes de llamar a Ollama se verifica:

```python
est_input + num_predict <= num_ctx * 0.95
```

`est_input` se estima con un heuristico calibrado de ~3.3 caracteres por token (español con
tokenizer Qwen); el conteo real lo devuelve Ollama en `prompt_eval_count` despues de
la inferencia. Si se excede, se lanza `ValueError` con prefijo `context_overflow:` →
`413` en el cliente. Después, el proveedor verifica también el presupuesto
completo con roles y envoltura, la política activa y el contexto efectivo
`min(OLLAMA_NUM_CTX, LIMITE_CONTEXTO_TOKENS, 8192)`; también se comprueba al
reenviar con más salida. Véase «Registro y presupuesto de tareas».

### Logging del prompt renderizado

Con `LOG_LEVEL=DEBUG`, `run_inference` registra solo tamaños de system/user
en caracteres y estimaciones de tokens, sin imprimir los prompts completos.

### Monitoreo de contexto (Ollama)

Despues de inferir se calcula:

```python
ctx_margin = num_ctx - num_predict - prompt_eval_count
```

Si el margen es menor a `100`, se emite warning.

---

## 10. Postprocesamiento del output

El texto crudo del modelo pasa por limpieza estructural, depuración, filtro de
fidelidad, preservación de urgencias y seguimiento, en este orden:

```
_postprocess(raw) → clean_impresion(text) → _purgar_no_sustentado(text, clinical_prompt)
  → _ensure_emergency_preserved(text, payload)
  → _ensure_follow_up_last(text, recomendacion, payload=payload)
```

### Etapa 1 — `_postprocess` (limpieza estructural)

1. elimina bloques `<think>...</think>` completos (Qwen3.5 puede emitirlos aun con
   `think=False`);
2. si queda un `</think>` residual (apertura implicita), conserva solo lo posterior
   al ultimo `</think>`;
3. si queda un `<think>` sin cerrar (el budget de `num_predict` se agoto dentro del
   razonamiento), conserva solo lo **anterior** al primer `<think>`;
4. remueve fences Markdown;
5. remueve bullets y listas numeradas;
6. une todo en un solo parrafo;
7. recompone oraciones con proteccion de abreviaturas;
8. asegura punto final;
9. si el resultado queda vacío, lanza `ValueError` después de la llamada al proveedor;
   no dispara su retry. En dual se convierte en `GeneracionIncompletaError`.

#### Abreviaturas protegidas

Antes de dividir oraciones se protegen estos tokens (los que realmente contienen un
punto que confundiria al separador de oraciones):

- `O.D.` / `O.I.` / `A.O.`
- `Esf.` / `Cil.` / `Eje.` / `D.`
- `s.c.` / `c.c.`

Esto evita partir mal una oracion clinica.

### Etapa 2 — `clean_impresion` (guardarrailes deterministas)

El prompt ya prohibe estos defectos, pero el modelo de 9B no lo respeta de forma
fiable; `clean_impresion` ([app/prompt_builder.py](app/prompt_builder.py)) los limpia
de forma determinista, oracion por oracion:

- **Anti-placeholder:** descarta la oracion completa si contiene un marcador sin
  rellenar: `[valor]`/`[dato]` (cualquier cosa entre corchetes), `20/??`, `20/xx`, `??`.
- **Anti-meta-referencia:** elimina las frases de atribucion al bloque interno
  ("segun las correlaciones clinicas aplicables", "la correlacion clinica indica
  que", "se integra la observacion de que"...) **conservando el hallazgo clinico**
  de la oracion. No toca "correlacion con cifras tensionales" ni "correlacion
  sistemica", que si son texto clinico.
- **Anti-meta-comentario de ausencia:** descarta oraciones que solo comentan que
  falta un dato ("no se dispone de datos de...", "la refraccion final no fue
  documentada", "no existen correlaciones..."). Los negativos clinicos legitimos
  del payload ("fondo sin lesiones", "no presenta pterigion") se conservan.
- **Fragmentos colgados:** descarta oraciones que no empiezan con mayuscula.
- **Regla de oro:** elimina el participio `diagnosticad{o,a,os,as}` (el sustantivo
  "diagnostico" que usa la correlacion de insuficiencia de convergencia se conserva).
- **Reacentuador:** los textos de las correlaciones se almacenan sin acentos (para
  el matching por normalizacion) y el modelo los copia tal cual; ademas el propio
  modelo omite acentos. Se restaura la ortografia con: (a) regla generica segura
  `-cion`/`-sion` → `-ción`/`-sión` (el singular siempre lleva acento); (b) lista
  blanca de terminos clinicos sin homografo (miopia→miopía, clinico→clínico,
  pterigion→pterigión, anos→años...); (c) conversion de acento grave (artefacto del
  modelo: `retinològica`) a agudo. Opera sobre el texto FINAL, asi que no afecta el
  matching de keywords (que trabaja sobre la entrada normalizada).

---

## 11. Recomendacion de seguimiento (etapa 3 del postprocesado)

La recomendacion en `clinica.recomendacion_seguimiento` no se manda al modelo como parte del parrafo final. En su lugar:

- `run_inference` usa `build_system_prompt()` con `settings.max_sentences`, sin reducirlo por seguimiento;
- despues de la inferencia, `_ensure_follow_up_last()` la agrega al final.

Esta funcion:

1. ante una urgencia, suprime el seguimiento rutinario incompatible o sus oraciones incompatibles;
2. normaliza el seguimiento restante y asegura punto final;
3. elimina una última oración idéntica si el modelo ya la incluyó;
4. elimina una última oración muy parecida si la similitud es `>= 0.70`;
5. agrega el seguimiento restante al final, si existe.

Esto garantiza:

- texto del seguimiento normalizado y compatible con las urgencias activas;
- posición final, si queda seguimiento;
- menos riesgo de paráfrasis no deseadas.

---

## 12. Cache de inferencia

El cache es in-memory y vive en `InferenceCache`.

### Configuracion actual

- TTL: `86400` segundos
- tamano maximo: `500` entradas

### Clave del cache

La clave SHA-256 se construye con:

- `payload.model_dump(mode="json")`
- excluyendo `receta_id`
- el modelo activo (`ollama_model`)
- flag booleano `__has_recommendation`

Detalles importantes:

- `receta_id` no afecta el cache;
- `salida_version` participa en la clave. Para compartir la caché clínica, el handler dual usa una copia con `salida_version="clinica-v1"`; la caché paciente es independiente (véase SALIDA_DUAL.md);
- el `base_hash_api` dual se calcula con el request dual y añade perfil, prompt, pipeline y opciones clínicas; no es la clave paciente;
- los demás campos nuevos del schema participan automáticamente en la clave, salvo `receta_id`;
- si cambia `OLLAMA_MODEL`, cambia la clave (no se sirven respuestas generadas por otro modelo);
- si el caso tiene o no recomendacion, cambia la clave.

### Politica de eviction

Si el cache está lleno y entra una nueva clave, se elimina la menos recientemente
usada; cada acierto mueve su entrada al final.

---

## 13. Salida esperada

### Respuesta exitosa sin cache

```json
{
  "status": "ok",
  "impresion_clinica": "El paciente ...",
  "correlaciones_activadas": ["fondo_periferico_riesgo", "av_cc_limitada"]
}
```

### Respuesta exitosa desde cache

```json
{
  "status": "ok",
  "impresion_clinica": "El paciente ...",
  "cached": true,
  "correlaciones_activadas": ["fondo_periferico_riesgo", "av_cc_limitada"]
}
```

- `correlaciones_activadas` lista los nombres de las reglas deterministas que
  aplicaron al caso (trazabilidad); se incluye tambien en cache hit. El detalle
  clinico de cada nombre esta en [CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md).

### Respaldo determinista y errores de generacion

- Si el modelo termina por longitud (`done_reason=length`) se reintenta una vez con mas `num_predict`; si persiste, o si la
  depuracion deja la impresion vacia, la API **no** devuelve un exito vacio ni lo guarda en cache: responde `502`
  (`"El modelo no produjo una impresion clinica completa. Intente de nuevo."`).
- Con una urgencia activa la API entrega en su lugar el **respaldo determinista** (avisos urgentes + seguimiento compatible), sin cache,
  identificado con un campo adicional:

```json
{
  "status": "ok",
  "impresion_clinica": "Hallazgo urgente: ...",
  "origen": "determinista",
  "correlaciones_activadas": ["diplopia_aguda"]
}
```

- Las oraciones del modelo con cifras de riesgo (mmHg, um, %, mm), terapias o diagnosticos graves ausentes de lo que recibio
  el modelo se omiten. Es una contencion, no una verificacion de la fidelidad del texto. Detalle en el Apendice D de
  [CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md).

### Endpoint `/health`

Ademas del estado de Ollama/modelo, `/health` expone el bloque `concurrencia`
con `max_concurrent`, `en_cola` y `max_en_cola`. Con `max_concurrent=1`, la
profundidad de cola (`en_cola`) es la senal operacional mas relevante. Sin
`API_KEY` configurada responde `503` (`degraded`, `api_key_configurada=false`): el POST
clinico responderia `500`.

### Propiedades del texto final

- un solo parrafo;
- sin bullets;
- sin encabezados;
- sin explicaciones adicionales;
- en espanol;
- en tercera persona;
- con punto final;
- con recomendacion de seguimiento al final, si existe.

---

## 14. Como extender el sistema

### Agregar una nueva correlacion

1. Definir `_cond_x(req)` y `_texto_x(req)` en el modulo de dominio correspondiente
   dentro de `app/correlaciones/` (p. ej. `fondo_de_ojo.py`, `binocularidad.py`).
   Si el dominio no existe, crear un modulo nuevo.
2. Exportar ambas y registrar `Correlacion("x", _cond_x, _texto_x)` en la lista
   `CORRELACIONES` de `app/correlaciones/registry.py`, en la posicion de prioridad
   correcta (los hallazgos urgentes van primero).
3. Si depende de texto libre, decidir si requiere normalizacion, keywords o ventana
   de negacion (helpers en `texto.py`).
4. **Agregar un golden** en `tests/test_correlaciones_golden.py` que fije el texto
   exacto (obligatorio: `test_golden_cubre_todas_las_correlaciones` falla si no lo
   haces) y actualizar el conteo (47) en
   `test_registro_separa_47_medicas_y_un_recordatorio_tecnico`.
5. Documentar la correlacion y su fundamento clinico en
   [CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md).

### Regla de oro

La condicion decide si aplica.

El texto redacta un hecho clinico ya decidido.

El LLM no debe decidir la correlacion: solo integrarla al parrafo.

### Si cambias prompts o correlaciones

Debes revisar al menos:

- `PIPELINE_LLM.md` y `CORRELACIONES_CLINICAS.md`
- `app/prompt_builder.py` (system prompt **y** guardarrailes de `clean_impresion`:
  si el prompt cambia de vocabulario, los patrones anti-meta pueden dejar de matchear)
- el paquete `app/correlaciones/` (dominio + `registry.py`)
- `tests/test_correlaciones_golden.py` (texto exacto) y `tests/test_prompt_builder.py`
- `app/cache.py` si cambian condiciones que deban invalidar cache

### Si cambias parametros de inferencia

- Los parametros de sampling de Ollama se leen de `.env` en `app/config.py`
  (cada uno comentado con su justificacion) y se arman en `app/providers/ollama.py`
- La orquestacion (prompts, validacion de contexto, postprocesado) esta en
  `app/inference.py` (`run_inference`)
- En `clinica-v1`, el timeout de inferencia es `ollama_timeout` (`_INFERENCE_TIMEOUT`).
  En dual se acota además por `PLAZO_GLOBAL_RECETA_S` desde la llegada, incluida cola.

---

## 15. Logging y observabilidad

Configurado en [app/observability.py](app/observability.py) (lo activa
`config.py` al importar). Tres destinos, todos con el mismo formato:

```
2026-07-11 15:40:42 [INFO] [a395f5b3] app.main: → POST /inferencia/impresion-clinica (origen 157.180.39.184)
                            ^^^^^^^^ request-id
```

| Destino | Nivel | Rotacion |
|---|---|---|
| Consola | `LOG_LEVEL` (default INFO) | — |
| `logs/inference.log` | `LOG_LEVEL` | 10 MB × 5 archivos |
| `logs/errors.log` | WARNING+ (con traceback) | 10 MB × 5 archivos |

### Request-id

El middleware de `main.py` asigna a cada request un id corto (propaga el header
`X-Request-ID` si el cliente lo envia, o genera uno), lo inyecta en **todas** las
lineas de log de ese request via `ContextVar` + `logging.Filter`, y lo devuelve
en el header `X-Request-ID` de la respuesta. Para reconstruir un request:
`grep <rid> logs/inference.log`.

### Que se loggea por request (INFO)

1. `→ POST /inferencia/impresion-clinica (origen <ip>)` — la IP real se toma de
   `CF-Connecting-IP` / `X-Forwarded-For` (detras de Cloudflare Tunnel el socket
   siempre es local).
2. `Payload recibido [sid]: edad=45 rx=OD+OI akr=OD clinica=[fondo_de_ojo, ...]`
   — QUÉ campos vienen, no el contenido de sus textos.
3. `Correlaciones activadas [sid] (n): [...]`.
4. Cache hit/miss, cola (`queued`/`acquired`/`released`).
5. Metricas de Ollama: tokens de entrada/salida, tok/s, duracion total y de
   carga, `done_reason`.
6. Acciones de guardarrailes (`Guardarrail: ...`): meta-referencias eliminadas,
   oraciones descartadas (placeholder/meta-ausencia/fragmento) y el strip de
   `diagnosticad*`.
7. `Inferencia completada [sid] en X.Xs (N chars, M correlaciones)` y
   `← POST ... 200 en X.XXs`.

Los errores agregan contexto especifico: auth rechazada (401, con longitud del
token recibido), payload sin datos (422), overflow de contexto (413, con la
estimacion de tokens), cola saturada (503, con profundidad), timeout (504, con
el limite configurado) y cualquier excepcion no manejada con traceback completo
en `logs/errors.log`.

Con `LOG_LEVEL=DEBUG` se agregan tamaños de system/user y el margen real de
contexto que reporta Ollama; no se registran los prompts completos. El logger `httpx` esta silenciado a
WARNING (duplicaba cada POST).

La guia de conexion y debugging del despliegue completo (SaaS + Cloudflare +
tunel) esta en [GUIA_CONEXION.md](GUIA_CONEXION.md).

El léxico determinista sobre la apertura y la invitación de Qwen es una defensa
adicional: no garantiza detectar toda afirmación semántica ni todo cambio de
idioma. La verificación posterior y la aprobación humana del mensaje completo
siguen siendo necesarias antes de enviarlo al paciente.

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


### Tokenizadores y reverificación

Se soportan `qwen2` y `qwen35` (alias `qwen3.5`, `qwen3_5`), cada uno con su
expresión de pre-tokenización; Qwen3.5 incluye marcas Unicode `\p{M}`.
Un nombre desconocido se registra y desactiva el conteo exacto. Se publica
`pre_tokenizador` junto a `modo_conteo` en la información de cada tarea.
No se normaliza a NFC: con texto NFD el conteo puede exceder al oficial,
en el lado conservador, como en la ruta de llama.cpp. Las seis sondas usan NFC.

La verificación descarga `/api/show` verbose y solo activa exacto tras concordar
las seis sondas. Se reintenta en segundo plano cada `PRESUPUESTO_REVERIFICAR_S`
(300 segundos por omisión), incluso sin solicitudes. Nunca se solapan verificaciones.
La comprobación de identidad se agenda sin bloquear al solicitante, como máximo
cada 60 segundos, mediante version, tags y show **sin verbose**; solo necesita
la plantilla para su hash. Un cambio invalida el contador y exige reverificación.

Validación opcional sin Ollama: instalar `tokenizers==0.23.3` y definir
`QWEN_TOKENIZER_JSON` con la ruta de `tokenizer.json` oficial; ejecutar
`python -m pytest tests/test_tokenizador_oficial.py -q -s`.
Sin la variable se omite. Reconstruye metadatos GGUF con `qwen35` y compara un
corpus Unicode y los prompts reales de receta y seguimiento; en NFD exige que
la reconstrucción no cuente menos que el oficial.

## Integración W1b del paciente

El middleware fija llegada monotónica antes de la cola. En dual el plazo global
por omisión es 85 s. Redacción 15 s y verificación 5 s, ventanas mínimas 1 s y
0.5 s, reserva 0.1 s; se aplican por tiempo restante. Antes de cada etapa se cede
si espera otra interactiva (`PACIENTE_OMITIR_SI_ESPERA=true`). El interruptor
`PACIENTE_LLM_HABILITADO=false` devuelve respaldo sin llamadas del paciente ni
recuperación de su prosa cacheada; motivo nulo salvo fallo de ensamblado
(`rechazada`/`error`). Las llamadas declaradas en `/v1/tareas` se conservan.
La regla `lente` solo permite la descripción CPU del diseño: monofocal no
determina lejos, cerca o lectura. Los efectos de la graduación y ayuda de los
lentes se permiten cuando los hechos los sustentan.
El modo clínico histórico mantiene su timeout actual.

El clínico cacheado permite reintentar solo el paciente con turno interactivo;
espera rechazada o vencida devuelve ese clínico con `ocupado` o `timeout`.
Solo se cachea explicación validada. `cached` requiere ambos aciertos;
`generacion.cache` informa los parciales. La clave canónica del paciente incluye
clínico, contexto, opciones efectivas y todas las versiones de sus módulos.

El proveedor recibe tarea y etapa internas, sin cambiar el cuerpo clínico, y
cuenta cada intento físico, incluidos reintentos, errores y cancelaciones.
`/v1/metricas` no conserva contenido. El paciente usa siempre política estricta
sin conteo exacto; la receta conserva la elección del dueño entre estricto y
conservador. El primero puede rechazar una receta típica con 413; el segundo
usa heurística sin garantía exacta. El modo exacto BPE prevalece cuando está verificado.
