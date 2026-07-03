# Pipeline de Inferencia Clinica - Documentacion Tecnica

Este documento describe el funcionamiento real del pipeline LLM de la API clinica optometrica con base en el codigo actual de:

- `app/main.py`
- `app/clinical_data.py`
- `app/cache.py`
- `app/prompt_builder.py`
- `app/inference.py`
- `app/providers/nvidia.py`
- `app/providers/ollama.py`
- `app/correlaciones/` (paquete por dominio)
- `app/schemas.py`

El objetivo del sistema es transformar un payload estructurado de refraccion y hallazgos clinicos en un parrafo de impresion clinica en espanol, usando una combinacion de logica determinista y generacion con LLM.

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
9. Inferencia — proveedores y fallback
10. Postprocesamiento del output
11. Recomendacion de seguimiento
12. Cache de inferencia
13. Salida esperada
14. Como extender el sistema

---

## 1. Descripcion general

La API recibe datos estructurados de un examen optometrico y devuelve un unico parrafo clinico. El pipeline combina dos capas:

- Capa determinista en Python: evalua reglas clinicas fijas y genera hechos pre-redactados.
- Capa generativa con LLM: redacta el parrafo final a partir de los datos del examen y de esas correlaciones ya evaluadas.

Esto separa claramente:

- la decision clinica reproducible de si una correlacion aplica o no;
- la redaccion natural del informe final.

### Proveedores de inferencia

El sistema soporta dos proveedores configurables via `WEB_INFERENCE` en `.env`:

| `WEB_INFERENCE` | Comportamiento |
|---|---|
| `false` (default) | Inferencia local con Ollama (`qwen3.5:9b`) |
| `true` | NVIDIA NIM como principal (`deepseek-ai/deepseek-v3.2`), Ollama como fallback automatico |

El fallback a Ollama se activa ante: timeout de NVIDIA, error de conexion, rate limit (429) o error de servidor (5xx). Los errores de configuracion (401/403) o prompt invalido (400) no activan fallback.

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
  |- build_system_prompt(effective_max)
  |- build_user_prompt(req)
  |    |- serializa contexto, refraccion, AKR y hallazgos clinicos
  |    |- evaluar_correlaciones(req)
  |    |- agrega bloque "Correlaciones clinicas aplicables" si hay activaciones
  |
  v
  WEB_INFERENCE=true?
  |
  |- SI --> providers/nvidia.call(system, user)
  |           |- OK: raw_text, provider="nvidia"
  |           |- NvidiaUnavailableError: fallback a Ollama
  |           |- Error no recuperable (400/401/403): propagar
  |
  |- NO (o fallback) --> providers/ollama.call(system, user, client)
  |                        |- validacion preemptiva de contexto (num_ctx)
  |                        |- POST /api/chat a Ollama
  |                        |- provider="ollama"
  |
  v
_postprocess(raw_text)
  |
  |- elimina bloques <think>
  |- limpia listas, fences y espacios
  |- recompone un solo parrafo
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
Respuesta JSON  { status, impresion_clinica, provider, cached? }
```

---

## 3. Endpoint, autenticacion y control de carga

### Endpoint principal

- Ruta: `POST /inferencia/impresion-clinica`
- Handler: `crear_impresion_clinica()` en [`app/main.py`](/c:/Users/Uriel%20Rojo/Documents/ia-api/app/main.py)

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

- `settings.max_concurrent = 1`
- un semaforo global `asyncio.Semaphore`
- una cola maxima de espera de `5` requests
- `settings.queue_wait_timeout = 120.0`

Si la cola ya esta llena, el endpoint responde `503`.

Si la inferencia completa supera el timeout total, responde `504`. Con `WEB_INFERENCE=true` el timeout cubre ambos proveedores en cadena (`nvidia_timeout + ollama_timeout + 10s`); con `WEB_INFERENCE=false` es simplemente `ollama_timeout`.

### Warmup al arrancar

Durante el `lifespan` de FastAPI se crea un `httpx.AsyncClient` y se hace un warmup simple contra Ollama para intentar cargar el modelo en VRAM.

---

## 4. Schema de entrada

El tipo raiz es `ImpresionClinicaRequest`.

> **Fuente de verdad:** el SaaS (Laravel) es la unica fuente que construye el payload. Todos los tipos, rangos y enums aqui listados reflejan lo que el SaaS realmente puede enviar (catalogos en `OpticaOptions` + `RecetaFormOptions`, validacion en `RecetaValidationRules`, construccion en `IaApiService::buildPayload`). El mapeo campo-por-campo esta en [DICCIONARIO_DATOS_RECETA.md](DICCIONARIO_DATOS_RECETA.md).

> **Politica de validacion: COERCION TOLERANTE (no rechazo).** El SaaS invoca este endpoint con el estado **crudo** del formulario, SIN pasar por `RecetaValidationRules` (el boton "Generar con IA" en `FormEditor::generateImpresionClinica` arma `toPayload()` y lo envia antes de guardar/validar). Por eso el schema **no** responde `422` ante un valor fuera de catalogo en un campo secundario: lo **descarta** (`None`) o lo **normaliza**, y lo registra en el log. Solo se responde `422` cuando no hay ningun dato clinico util (ver seccion 5). Esto evita que un eje de 190 o una K corrupta tumben toda la generacion.

### Campos de primer nivel

| Campo | Tipo | Uso |
|---|---|---|
| `receta_id` | `str` | Identificador del caso. Se usa para logging seguro, no para el cache. Puede ser `"nueva"` cuando la receta aun no se guardo. |
| `paciente` | `ContextoPaciente` | Edad (calculada en SaaS), ocupacion y motivo de consulta. |
| `refraccion` | `Refraccion` | Refraccion final prescrita en OD y OI. |
| `akr` | `AkrSnapshot` | Medicion del autorrefractometro en OD y OI, metadata de la sesion (PD, VD, indice queratometrico) y, desde 2026-07, los valores de queratometria (K1, K2, K promedio, cilindro corneal) capturados en el mismo ticket. |
| `clinica` | `DatosClinica` | Hallazgos de examen clinico. |
| `tipo_lente` | `str \| None` | Diseno de lente prescrito. |

### ContextoPaciente

| Campo | Tipo | Restriccion real del SaaS |
|---|---|---|
| `edad` | `int \| None` | Calculada desde `paciente.fecha_nacimiento` con `Carbon::parse(...)->age`. Si no hay fecha de nacimiento, llega `None`. |
| `ocupacion` | `str \| None` | `required\|max:255` en el SaaS. En la practica siempre llega con valor (nunca None). |
| `motivo_consulta` | `str \| None` | `required\|max:255` en el SaaS. En la practica siempre llega con valor (nunca None). |

El SaaS **no envia** `nombre`, `telefono` ni `fecha_nacimiento`.

### GraduacionOjo

Se usa en `refraccion.od` y `refraccion.oi`.

| Campo | Tipo | Restriccion real del SaaS |
|---|---|---|
| `esfera` | `float \| None` | Dropdown `OpticaOptions::esfera`: `+20.00`..`-20.00` paso `0.25`. Fuera de `±20.00` → se descarta (`None`). Default `0.00`, sin opcion vacia (en `create` siempre llega valor) |
| `cilindro` | `float \| None` | Dropdown `OpticaOptions::cilindro`: `0.00`..`-8.00` paso `0.25`, **siempre ≤ 0** (convencion negativa). Fuera de `\|8.00\|` → `None`. La Rx final **no** se transpone (el dropdown ya garantiza minus-cyl) |
| `eje` | `int \| None` | Input libre; el SaaS **no** valida rango. El eje es ciclico: fuera de `0..180` se **normaliza modulo 180** (`225`→`45`), no se rechaza |
| `add` | `float \| None` | Input libre. `add ≤ 0` (tecleado `0` o negativo) → `None`: "sin adicion" no cuenta como adicion prescrita |
| `av_sc` | `str \| None` | Dropdown `OpticaOptions::av` (16 valores): `20/10`, `20/15`, `20/20`, `20/25`, `20/30`, `20/40`, `20/50`, `20/60`, `20/70`, `20/80`, `20/100`, `20/120`, `20/160`, `20/200`, `20/400`, `20/600`. El schema **canoniza** `20/xx` (colapsa espacios); notaciones legacy no-Snellen se conservan sin disparar |
| `av_cc` | `str \| None` | Mismos valores que `av_sc` (tambien canonizados) |

### AkrSnapshot — metadata de sesion

Ademas de `od` y `oi`, el snapshot incluye metadata comun a la sesion de medicion:

| Campo | Tipo | Restriccion real del SaaS |
|---|---|---|
| `ticket_id` | `int \| None` | Referencia al ticket de autorrefractometro/queratometro origen. `nullable\|integer\|exists:akr_tickets,id` |
| `taken_at` | `str \| None` | Fecha/hora de la medicion. `nullable\|date` |
| `pd` | `float \| None` | Distancia interpupilar. `nullable\|numeric`, sin rango declarado |
| `vd` | `float \| None` | Distancia al vertice. `between:0,30`; fuera de rango → `None` |
| `ker_index` | `float \| None` | Indice queratometrico usado por el equipo para convertir mm↔D. `between:1.3,1.4`; fuera de rango → `None` |

### AkrOjo

Se usa en `akr.od` y `akr.oi`. Es un snapshot del autorrefractometro; **no** incluye `add`, `av_sc` ni `av_cc`. `pd` existe pero a nivel de sesion (`akr.pd`), no por ojo.

> **Transposicion del AKR (solo AKR, no la Rx).** La convencion de cilindro del AKR la fija el **dispositivo** y puede ser plus-cyl. Si `akr.od/oi.cilindro > 0`, el schema transpone la lectura a convencion negativa (`esf' = esf + cil`, `cil' = -cil`, `eje' = (eje+90) % 180`) para que la comparacion esfera-a-esfera AR vs Rx (`ar_rx_espasmo/cambio/variabilidad`) quede en la misma convencion que la Rx final. La **Rx final NO se transpone**: su dropdown ya garantiza minus-cyl y transponerla alteraria el piso de esfera de `hipermetropia_alta`.

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
| `k_cilindro` | `float \| None` | Cilindro corneal (K2 - K1 con signo). `-20..20`; fuera → `None` |
| `k_cilindro_eje` | `int \| None` | Eje del cilindro corneal. Ciclico: normalizado modulo 180 |

### DatosClinica

| Campo | Tipo | Restriccion real del SaaS |
|---|---|---|
| `uso_pantallas` | `"lt2" \| "btw2_6" \| "gt6" \| None` | Enum cerrado |
| `anexos_oculares` | `str \| None` | Texto libre `max:255` |
| `reflejos_pupilares` | `str \| None` | `max:255`. **La UI compone** `"{opcion}: {nota}"`. Opciones UI fijas: `"Reflejo fotomotor, consesual, acomodativo"` o `"Marcus Gunn"` |
| `motilidad_ocular` | `str \| None` | `max:255`. **La UI compone** una sola linea: `"Versiones: X Ducciones: Y Sacadicos: Z Seguimiento: W"` (los saltos de linea se colapsan en el SaaS antes de enviar) |
| `confrontacion_campos_visuales` | `str \| None` | Texto libre `max:255` |
| `fondo_de_ojo` | `str \| None` | Texto libre `max:255` |
| `grid_de_amsler` | `str \| None` | Texto libre `max:255` |
| `ojo_seco_but_seg` | `int \| None` | Dropdown `1..15` (segundos). Fuera → `None` |
| `cover_test` | `str \| None` | `max:255`. **La UI compone siempre** `"OD: {tipo_od}[ y {sub_od}] \| OI: {tipo_oi}[ y {sub_oi}]"`. `tipo ∈ {Orto, Endo, Exo, Hiper, Hipo}` (radio, default `Orto`); `sub ∈ {Tropia, Foria}` (radio **SIN default, opcional**). Ejemplos reales: `"OD: Orto \| OI: Exo y Foria"`, `"OD: Endo y Tropia \| OI: Orto"`, y **tipo sin sub**: `"OD: Exo \| OI: Orto"`. La capa de correlaciones parsea el formato canonico y dispara tambien con el tipo sin clasificar (ver seccion 6). **No** se envian cadenas como `"exoforia"` unidas. |
| `ppc_cm` | `int \| None` | Dropdown `1..15` (cm). Fuera → `None` |
| `recomendacion_seguimiento` | `str \| None` | Texto libre (TEXT en DB, sin limite duro) |

### Normalizaciones Pydantic relevantes

- `motilidad_ocular`: colapsa saltos de linea y espacios duplicados (el SaaS ya envia una sola linea; la normalizacion es defensiva).
- `cover_test`: reemplaza `" - "` por `" y "` y colapsa espacios. En la practica **el SaaS ya envia `" y "`** como separador entre tipo y subtipo; este normalize es defensivo.

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
  (`225`→`45`). El input del SaaS no valida rango, asi que normalizar (no rechazar) es
  lo correcto para disparar `astig_oblicuo` con el eje real.
- `paciente.edad`: `0..120`; fuera → `None` (comportamiento conservador de las reglas
  que dependen de la edad).
- `esfera` (`±20.00`), `cilindro` (`\|8.00\|`), `ojo_seco_but_seg`/`ppc_cm` (`1..15`),
  `vd` (`0..30`), `ker_index` (`1.3..1.4`), K en dioptrias (`25..80`) y en mm (`4..12`):
  fuera de catalogo → `None`. Estos rangos son los limites de los dropdowns/dispositivo;
  un valor fuera es dato corrupto que no debe contar como hallazgo.
- `add ≤ 0` → `None`: el input de add es libre y un `0` tecleado no es una adicion
  prescrita (corrige el disparo de `presbicia_multifocal` / `presbicia_sin_adicion`).
- **Transposicion solo del AKR** (no la Rx): ver recuadro en la seccion AkrOjo.
- `av_sc` / `av_cc` se **canonizan**: `" 20 / 40 "` → `"20/40"`. Notaciones no-Snellen
  legacy (p. ej. "cuenta dedos") se conservan sin disparar AV.
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
[`app/correlaciones/`](/c:/dev/ia-api/app/correlaciones/):

- Dominios (10 modulos): `fondo_de_ojo`, `refractivas`, `akr`, `corneal`,
  `anexos_cristalino`, `pupilas_motilidad`, `campos_amsler`, `binocularidad`,
  `superficie_ocular`, `contexto`.
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
- Blindado: los 41 textos exactos estan cubiertos por pruebas *golden*
  (`tests/test_correlaciones_golden.py`) que impiden regresiones de contenido.

### Helpers clinicos relevantes

#### `_av_denominator(av)`

Extrae el denominador Snellen equivalente en pie a partir de las tres notaciones que
emiten los frontends: pie (`20/40`), metrica (`6/12`) y decimal (`0.5` / `0,5`).
Notaciones no interpretables (CF, MM, cuenta dedos) devuelven `None`.

#### `_av_es_limitada(av)`

Retorna `True` solo cuando el denominador Snellen equivalente es mayor a 25
(es decir 20/30 o peor).

Esto evita falsos positivos con AV supranormal o casi normal, por ejemplo `20/15`
o `20/25`.

#### `_av_categoria(av)`

Clasifica la reduccion de AV con correccion:

- `26-30`: leve
- `31-50`: moderada
- `51-100`: marcada
- `>100`: severa

#### `_equivalente_esferico(esf, cil)`

Calcula:

```python
esfera + (cilindro or 0.0) / 2.0
```

Se usa para anisometropia, miopia magna e hipermetropia alta.

#### Helpers de queratometria

Desde la integracion de datos de queratometria (`akr.od`/`akr.oi.k1_d`, `k2_d`, `k_promedio_d`, `k_cilindro`, `k_cilindro_eje`), el modulo agrega helpers para leer y clasificar esos valores: `_k_values`, `_has_keratometry`, `_k_max`, `_corneal_cyl_abs`, `_keratometry_axis`, `_keratometry_supports_astigmatism`, `_keratometry_axis_matches` y `_keratometry_suggests_corneal_irregularity` (curvatura corneal ≥ 47.20D como umbral de sospecha, ≥ 48.70D o cilindro corneal ≥ 4.00D como umbral de ectasia/irregularidad franca). Estos helpers alimentan las correlaciones refractivas y de AR como confirmacion/matiz, y ademas **disparan** las dos correlaciones del modulo `corneal.py` (`queratocono_ectasia_sospecha`, `astigmatismo_corneal_vs_refractivo`), unica excepcion a la regla "la queratometria no dispara".

**Estado:** integrada. El detalle clinico de como cada una de las 41 correlaciones
usa la queratometria (confirmacion/matiz en las refractivas, disparador propio en las
dos corneales) esta documentado por correlacion en [CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md).

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
[CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md) seccion 10 y en
[VERIFICACION_CORRELACIONES_VS_INVESTIGACION.md](VERIFICACION_CORRELACIONES_VS_INVESTIGACION.md).

---

## 7. Correlaciones activas actuales

El registro contiene **41 correlaciones**, particionadas por dominio clinico en el
paquete `app/correlaciones/` (ver estructura en la seccion 6).

> **Fuente unica de verdad clinica:** el catalogo completo de las 41 correlaciones
> —campos que las disparan, umbrales, keywords, texto exacto generado y **fundamento
> clinico con evidencia**— vive en [CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md).
> Este documento ya no lo duplica, para evitar la divergencia que existia entre ambos.
> Los textos exactos estan ademas blindados por pruebas *golden* en
> `tests/test_correlaciones_golden.py`: si una regla cambia su texto sin actualizar la
> prueba, el CI falla.

El **orden de evaluacion** es un invariante clinico (los hallazgos urgentes van
primero) definido explicitamente en `app/correlaciones/registry.py` y cubierto por
tests (`test_registro_tiene_41_correlaciones_con_nombres_unicos`,
`test_but_critico_esta_antes_que_correlaciones_contextuales`).

Trazabilidad: la respuesta HTTP incluye `correlaciones_activadas` con los nombres de
las reglas que aplicaron al caso (ver seccion 13).

---

## 8. Construccion del prompt

### `build_system_prompt(effective_max)`

El system prompt:

- obliga a devolver un solo parrafo;
- limita el numero maximo de oraciones;
- define el orden de redaccion;
- pide usar tercera persona;
- pide lenguaje clinico objetivo;
- prohibe incluir la recomendacion de seguimiento;
- pide no inferir causalidad mas alla del bloque de correlaciones;
- instruye al modelo a colocar cualquier correlacion marcada con "Hallazgo urgente:" en las primeras 2 oraciones del parrafo.

Aspectos clave del prompt actual:

- "av_sc es agudeza visual sin correccion y av_cc es agudeza visual con correccion; ambas corresponden a vision lejana."
- si existe recomendacion de seguimiento, `effective_max = max_sentences - 1`

### `build_user_prompt(req)`

Construye un prompt dinamico por secciones.

Orden real:

1. `Contexto del paciente`
2. `Refraccion final`
3. `Correlacion AKR vs refraccion final`
4. Bloques clinicos sueltos
5. `Diseno de lente prescrito`
6. `Correlaciones clinicas aplicables`
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

#### Correlacion AKR/queratometria vs refraccion final

Este bloque aparece si existe al menos un valor no nulo en la metadata de `akr` (`ticket_id`, `pd`, `vd`, `ker_index`) o en `akr.od`/`akr.oi` (incluyendo los campos de queratometria).

Orden por linea, si hay datos:

- `AKR metadata: PD ..., VD ..., Indice queratometrico ...` (solo si alguno de esos tres esta presente)
- `AKR OD: ...` / `Rx final OD: ...`
- `Queratometria OD: K1 ..., K2 ..., K promedio ..., Cil corneal ...`
- `AKR OI: ...` / `Rx final OI: ...`
- `Queratometria OI: ...`

A diferencia de `AKR OD/OI` y `Rx final OD/OI` (que solo aparecen juntos), la linea `Queratometria {OD|OI}` se agrega de forma independiente por ojo si ese ojo tiene algun valor de K.

#### Hallazgos clinicos sueltos

Se agregan como lineas individuales:

- `Uso de pantallas`
- `Anexos oculares`
- `Reflejos pupilares`
- `Motilidad ocular`
- `Confrontacion de campos visuales`
- `Fondo de ojo`
- `Grid de Amsler`
- `Ojo seco (BUT)`
- `Cover test`
- `PPC`

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

Los campos de texto libre pasan por `_sanitize()`, que elimina directivas `/think` y `/no_think`.

Campos numericos no se sanitizan porque ya estan validados por schema.

### Mapeo de uso de pantallas

| Valor | Texto en prompt |
|---|---|
| `lt2` | `menos de 2 horas diarias` |
| `btw2_6` | `entre 2 y 6 horas diarias` |
| `gt6` | `mas de 6 horas diarias` |

---

## 9. Inferencia — proveedores y fallback

La funcion central es `run_inference(payload, client)` en `app/inference.py`. Delega la llamada real al proveedor activo.

### Logica de seleccion de proveedor

```python
if WEB_INFERENCE:
    try:
        raw_text = await nvidia.call(system, user)   # proveedor principal
        provider = "nvidia"
    except NvidiaUnavailableError:
        raw_text = await ollama.call(system, user, client)  # fallback
        provider = "ollama"
else:
    raw_text = await ollama.call(system, user, client)
    provider = "ollama"
```

### Provider NVIDIA NIM (`app/providers/nvidia.py`)

- SDK: `openai` con `base_url=https://integrate.api.nvidia.com/v1`
- Modelo: `NVIDIA_MODEL` (default: `deepseek-ai/deepseek-v3.2`)
- Stream: `False`
- Thinking mode: controlado por `NVIDIA_THINKING` via `chat_template_kwargs`

| Parametro | Valor default |
|---|---|
| `temperature` | `0.7` |
| `top_p` | `0.95` |
| `max_tokens` | `1024` |
| `nvidia_timeout` | `60.0s` |
| `nvidia_max_retries` | `2` |

Errores que activan fallback a Ollama: timeout, connection error, HTTP 429/500/502/503/504.
Errores que NO activan fallback: HTTP 400 (prompt invalido), 401/403 (credenciales incorrectas).

### Provider Ollama (`app/providers/ollama.py`)

- Endpoint: `POST {OLLAMA_URL}/api/chat`
- Modelo: `OLLAMA_MODEL` (default: `qwen3.5:9b`)
- `stream = False`, `think = False`

| Parametro | Valor |
|---|---|
| `temperature` | `0.7` |
| `top_p` | `0.8` |
| `top_k` | `20` |
| `min_p` | `0.0` |
| `repeat_penalty` | `1.0` |
| `num_predict` | `1024` |
| `num_ctx` | `4096` |
| `seed` | `42` |
| `ollama_max_retries` | `2` |

Se reintenta ante: `httpx.ReadTimeout`, `ValueError` por respuesta vacia, HTTP 500/503.

### Validacion preemptiva de contexto (solo Ollama)

Antes de llamar a Ollama se verifica:

```python
est_input + num_predict <= num_ctx * 0.95
```

Si se excede, se lanza `ValueError` con prefijo `context_overflow:` → `413` en el cliente.
Esta validacion no aplica en NVIDIA NIM (DeepSeek V3.2 tiene contexto de 128K tokens).

### Monitoreo de contexto (Ollama)

Despues de inferir se calcula:

```python
ctx_margin = num_ctx - num_predict - prompt_eval_count
```

Si el margen es menor a `100`, se emite warning.

---

## 10. Postprocesamiento del output

`_postprocess(raw_text)` aplica esta secuencia:

1. elimina bloques `<think>...</think>`;
2. elimina bloques `<think>` truncados;
3. elimina razonamiento residual antes de `</think>`;
4. remueve fences Markdown;
5. remueve bullets y listas numeradas;
6. une todo en un solo parrafo;
7. recompone oraciones con proteccion de abreviaturas;
8. asegura punto final;
9. si el resultado queda vacio, lanza `ValueError`.

### Abreviaturas protegidas

Antes de dividir oraciones se protegen tokens como:

- `O.D.`
- `O.I.`
- `A.O.`
- `Dr.`
- `Dra.`
- `Esf.`
- `Cil.`
- `Eje.`
- `mmHg.`
- `s.c.`
- `c.c.`
- `seg.`
- `cm.`

Esto evita partir mal una oracion clinica.

---

## 11. Recomendacion de seguimiento

La recomendacion en `clinica.recomendacion_seguimiento` no se manda al modelo como parte del parrafo final. En su lugar:

- el system prompt reserva espacio reduciendo el limite de oraciones;
- despues de la inferencia, `_ensure_follow_up_last()` la agrega al final.

Esta funcion:

1. normaliza la recomendacion;
2. elimina una ultima oracion identica si el modelo ya la incluyo;
3. elimina una ultima oracion muy parecida si la similitud es `>= 0.70`;
4. agrega la recomendacion como ultima oracion.

Esto garantiza:

- texto final exacto;
- posicion final;
- menos riesgo de parafrasis no deseadas.

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
- modelo activo: `nvidia_model` si `WEB_INFERENCE=true`, `ollama_model` si `false`
- flag booleano `__has_recommendation`

Detalles importantes:

- `receta_id` no afecta el cache;
- como la clave usa `payload.model_dump(mode="json")` completo, cualquier campo nuevo del schema (incluyendo los de queratometria) participa automaticamente en la clave sin cambios en `cache.py`;
- si cambia el modelo o el proveedor activo, cambia la clave (evita servir respuestas de Qwen como si fueran de DeepSeek);
- si el caso tiene o no recomendacion, cambia la clave.

### Politica de eviction

Si el cache esta lleno y entra una nueva clave, se elimina la entrada mas antigua.

---

## 13. Salida esperada

### Respuesta exitosa sin cache

```json
{
  "status": "ok",
  "impresion_clinica": "El paciente ...",
  "provider": "nvidia",
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

- `provider` (solo en respuestas frescas) indica que proveedor genero la respuesta:
  `"nvidia"` o `"ollama"`. Util para monitoreo y debug sin revisar logs.
- `correlaciones_activadas` lista los nombres de las reglas deterministas que
  aplicaron al caso (trazabilidad); se incluye tambien en cache hit. El detalle
  clinico de cada nombre esta en [CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md).

### Endpoint `/health`

Ademas del estado de proveedores/modelo, `/health` expone el bloque `concurrencia`
con `max_concurrent`, `en_cola` y `max_en_cola`. Con `max_concurrent=1`, la
profundidad de cola (`en_cola`) es la senal operacional mas relevante.

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
   haces) y actualizar el conteo en
   `test_registro_tiene_41_correlaciones_con_nombres_unicos`.
5. Documentar la correlacion y su fundamento clinico en
   [CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md).

### Regla de oro

La condicion decide si aplica.

El texto redacta un hecho clinico ya decidido.

El LLM no debe decidir la correlacion: solo integrarla al parrafo.

### Si cambias prompts o correlaciones

Debes revisar al menos:

- `PIPELINE_LLM.md` y `CORRELACIONES_CLINICAS.md`
- `app/prompt_builder.py`
- el paquete `app/correlaciones/` (dominio + `registry.py`)
- `tests/test_correlaciones_golden.py` (texto exacto)
- `app/cache.py` si cambian condiciones que deban invalidar cache

### Si cambias el proveedor de inferencia

- Los parametros de sampling de Ollama estan en `app/providers/ollama.py`
- Los parametros de NVIDIA estan en `app/providers/nvidia.py` y `app/config.py`
- La logica de fallback y seleccion esta en `app/inference.py` (`run_inference`)
- El timeout total de `asyncio.wait_for` se calcula en `app/main.py` (`_INFERENCE_TIMEOUT`)
