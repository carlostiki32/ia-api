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

> **Fuente de verdad:** el SaaS (Laravel) es la unica fuente que construye el payload. Todos los tipos, rangos y enums aqui listados reflejan lo que el SaaS realmente puede enviar (validacion en `RecetaValidationRules` + construccion en `IaApiService::buildPayload`). El schema Pydantic de `ia-api` debe mantenerse alineado con este contrato y nunca asumir datos que el SaaS no genera.

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
| `esfera` | `float \| None` | Rango UI: `-20.00` a `+20.00` con paso `0.25` |
| `cilindro` | `float \| None` | Rango UI: `-8.00` a `0.00` con paso `0.25` |
| `eje` | `int \| None` | `0..180` — **el schema de la API lo valida** (`422` fuera de rango) |
| `add` | `float \| None` | Libre |
| `av_sc` | `str \| None` | Valores Snellen cerrados: `20/10`, `20/15`, `20/20`, `20/25`, `20/30`, `20/40`, `20/50`, `20/60`, `20/70`, `20/80`, `20/100`, `20/120`, `20/160`, `20/200`, `20/400`, `20/600`. El schema **canoniza** `20/xx` (colapsa espacios) |
| `av_cc` | `str \| None` | Mismos valores que `av_sc` (tambien canonizados) |

### AkrSnapshot — metadata de sesion

Ademas de `od` y `oi`, el snapshot incluye metadata comun a la sesion de medicion:

| Campo | Tipo | Restriccion real del SaaS |
|---|---|---|
| `ticket_id` | `int \| None` | Referencia al ticket de autorrefractometro/queratometro origen. `nullable\|integer\|exists:akr_tickets,id` |
| `taken_at` | `str \| None` | Fecha/hora de la medicion. `nullable\|date` |
| `pd` | `float \| None` | Distancia interpupilar. `nullable\|numeric`, sin rango declarado |
| `vd` | `float \| None` | Distancia al vertice. `nullable\|numeric\|between:0,30` |
| `ker_index` | `float \| None` | Indice queratometrico usado por el equipo para convertir mm↔D. `nullable\|numeric\|between:1.3,1.4` |

### AkrOjo

Se usa en `akr.od` y `akr.oi`. Es un snapshot del autorrefractometro; **no** incluye `add`, `av_sc` ni `av_cc`. `pd` existe pero a nivel de sesion (`akr.pd`), no por ojo.

Desde 2026-07 el SaaS captura tambien la prueba de queratometria en el mismo ticket AKR (dato nuevo, antes no se enviaba):

| Campo | Tipo | Restriccion real del SaaS |
|---|---|---|
| `esfera` | `float \| None` | |
| `cilindro` | `float \| None` | |
| `eje` | `int \| None` | |
| `k1_d` | `float \| None` | Meridiano plano (K1) en dioptrias. `nullable\|numeric` (SaaS no acota rango; Pydantic si: `25..80`) |
| `k1_mm` | `float \| None` | K1 en radio de curvatura. `nullable\|numeric\|between:4,12` |
| `k1_eje` | `int \| None` | Eje de K1. `nullable\|integer\|between:0,180` |
| `k2_d` | `float \| None` | Meridiano curvo (K2) en dioptrias. `nullable\|numeric` (Pydantic acota `25..80`) |
| `k2_mm` | `float \| None` | K2 en radio de curvatura. `nullable\|numeric\|between:4,12` |
| `k2_eje` | `int \| None` | Eje de K2. `nullable\|integer\|between:0,180` |
| `k_promedio_d` | `float \| None` | K promedio en dioptrias. `nullable\|numeric\|between:25,80` |
| `k_promedio_mm` | `float \| None` | K promedio en radio de curvatura. `nullable\|numeric\|between:4,12` |
| `k_cilindro` | `float \| None` | Cilindro corneal (K2 - K1 con signo). `nullable\|numeric` (Pydantic acota `-20..20`) |
| `k_cilindro_eje` | `int \| None` | Eje del cilindro corneal. `nullable\|integer\|between:0,180` |

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
| `ojo_seco_but_seg` | `int \| None` | `1..15` (unsignedTinyInteger en DB del SaaS) |
| `cover_test` | `str \| None` | `max:255`. **La UI compone siempre** `"OD: {tipo_od}[ y {sub_od}] \| OI: {tipo_oi}[ y {sub_oi}]"`. `tipo ∈ {Orto, Endo, Exo, Hiper, Hipo}`, `sub ∈ {Tropia, Foria}`. Ejemplos reales: `"OD: Orto \| OI: Exo y Foria"`, `"OD: Endo y Tropia \| OI: Orto"`. **No** se envian cadenas como `"exoforia"` unidas. |
| `ppc_cm` | `int \| None` | `1..15` (unsignedTinyInteger en DB del SaaS) |
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

### Endurecimiento del contrato (estado actual)

El schema ([`app/schemas.py`](/c:/dev/ia-api/app/schemas.py)) se alineo con las
constantes estrictas del frontend:

- `refraccion.od/oi.eje` ahora se valida a `0..180` (paridad con los ejes de AKR).
- `paciente.edad` se valida a `0..120`.
- `av_sc` / `av_cc` se **canonizan**: `" 20 / 40 "` → `"20/40"`. Las notaciones
  no-Snellen (p. ej. "cuenta dedos") se conservan sin rechazar, porque el catalogo
  real del frontend puede incluirlas y la capa de correlaciones las ignora sin error.
- `tipo_lente` se normaliza (espacio en blanco) pero **no** se cierra a enum: el
  catalogo de disenos lo define el frontend y puede crecer sin coordinacion con la
  API; cerrarlo romperia compatibilidad hacia adelante. La deteccion multifocal se
  hace por substring.
- No se declara `extra="forbid"`: se prefiere tolerar campos adicionales para no
  romper ante despliegues desincronizados entre SaaS y API.

Las pruebas y ejemplos deben preferir valores que la UI real del SaaS si puede
producir. En particular, `cover_test` se modela como
`"OD: {tipo}[ y {sub}] | OI: {tipo}[ y {sub}]"`, no como strings sinteticos tipo
`"ortoforia"` o `"exoforia en VP"`.
- Para queratometria, `ia-api` es en cambio **mas estricta** que el SaaS: Pydantic acota `k1_d`/`k2_d`/`k_promedio_d` a `25..80` D y `k_cilindro` a `-20..20` D, rangos que `RecetaValidationRules` no impone explicitamente en `k1_d`/`k2_d`/`k_cilindro` (solo los valida como `numeric`). En la practica esto no deberia rechazar mediciones reales (fuera de ese rango no hay corneas humanas viables), pero si el SaaS llegara a aceptar una entrada manual fuera de rango, `ia-api` respondera `422` en vez de silenciarlo.

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

- Dominios (9 modulos): `fondo_de_ojo`, `refractivas`, `akr`, `anexos_cristalino`,
  `pupilas_motilidad`, `campos_amsler`, `binocularidad`, `superficie_ocular`,
  `contexto`.
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
- Blindado: los 36 textos exactos estan cubiertos por pruebas *golden*
  (`tests/test_correlaciones_golden.py`) que impiden regresiones de contenido.

### Helpers clinicos relevantes

#### `_snellen_denominator(av)`

Extrae el denominador de una AV tipo `20/30`, `20/100`, etc.

#### `_av_es_limitada(av)`

Retorna `True` solo cuando el denominador Snellen es mayor a 20.

Esto evita falsos positivos con AV supranormal, por ejemplo `20/15`.

#### `_av_categoria(av)`

Clasifica la reduccion de AV con correccion:

- `21-30`: leve
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

Desde la integracion de datos de queratometria (`akr.od`/`akr.oi.k1_d`, `k2_d`, `k_promedio_d`, `k_cilindro`, `k_cilindro_eje`), el modulo agrega helpers para leer y clasificar esos valores: `_k_values`, `_has_keratometry`, `_k_max`, `_corneal_cyl_abs`, `_keratometry_axis`, `_keratometry_supports_astigmatism`, `_keratometry_axis_matches` y `_keratometry_suggests_corneal_irregularity` (curvatura corneal ≥ 47.20D como umbral de sospecha, ≥ 48.70D o cilindro corneal ≥ 4.00D como umbral de ectasia/irregularidad franca). Estos helpers ya alimentan varias correlaciones existentes (ver seccion 7) como dato adicional, no como disparador independiente.

**Estado:** integrada. El detalle clinico de como cada una de las 36 correlaciones
usa la queratometria (como confirmacion/matiz, no como disparador) esta documentado
por correlacion en [CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md).

### Matching de texto libre

El modulo usa normalizacion de texto:

- lowercase
- remocion de acentos con `unicodedata.normalize`
- colapso de espacios

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

---

## 7. Correlaciones activas actuales

El registro contiene **36 correlaciones**, particionadas por dominio clinico en el
paquete `app/correlaciones/` (ver estructura en la seccion 6).

> **Fuente unica de verdad clinica:** el catalogo completo de las 36 correlaciones
> —campos que las disparan, umbrales, keywords, texto exacto generado y **fundamento
> clinico con evidencia**— vive en [CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md).
> Este documento ya no lo duplica, para evitar la divergencia que existia entre ambos.
> Los textos exactos estan ademas blindados por pruebas *golden* en
> `tests/test_correlaciones_golden.py`: si una regla cambia su texto sin actualizar la
> prueba, el CI falla.

El **orden de evaluacion** es un invariante clinico (los hallazgos urgentes van
primero) definido explicitamente en `app/correlaciones/registry.py` y cubierto por
tests (`test_registro_tiene_36_correlaciones_con_nombres_unicos`,
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
   `test_registro_tiene_36_correlaciones_con_nombres_unicos`.
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
