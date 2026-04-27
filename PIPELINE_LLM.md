# Pipeline de Inferencia Clinica - Documentacion Tecnica

Este documento describe el funcionamiento real del pipeline LLM de la API clinica optometrica con base en el codigo actual de:

- `app/main.py`
- `app/clinical_data.py`
- `app/cache.py`
- `app/prompt_builder.py`
- `app/inference.py`
- `app/providers/nvidia.py`
- `app/providers/ollama.py`
- `app/correlaciones.py`
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
| `akr` | `AkrSnapshot` | Medicion del autorrefractometro en OD y OI. |
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
| `eje` | `int \| None` | `0..180` |
| `add` | `float \| None` | Libre |
| `av_sc` | `str \| None` | Valores Snellen cerrados: `20/10`, `20/15`, `20/20`, `20/25`, `20/30`, `20/40`, `20/50`, `20/60`, `20/70`, `20/80`, `20/100`, `20/120`, `20/160`, `20/200`, `20/400`, `20/600` |
| `av_cc` | `str \| None` | Mismos valores que `av_sc` |

### AkrOjo

Se usa en `akr.od` y `akr.oi`. Es un snapshot del autorrefractometro; **no** incluye `add`, `av_sc` ni `av_cc`, ni `pd` (el SaaS no lo envia).

| Campo | Tipo |
|---|---|
| `esfera` | `float \| None` |
| `cilindro` | `float \| None` |
| `eje` | `int \| None` |

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

### Brechas actuales del contrato

Al auditar ambos repositorios el `2026-04-23`, se confirmo lo siguiente:

- El payload real que sale del SaaS **si** coincide en estructura con este documento.
- `ia-api` sigue siendo mas permisiva que la receta en varios puntos: hoy Pydantic no restringe `tipo_lente` a enum cerrado, no limita `eje` a `0..180`, no valida el catalogo Snellen de `av_sc` / `av_cc` y no declara `extra="forbid"` en los modelos de entrada.
- Eso significa que una llamada directa a `ia-api` podria mandar valores fuera del contrato real de la receta, aunque el SaaS no los emita normalmente.
- Las pruebas y ejemplos de `ia-api` deben preferir siempre valores que la UI real del SaaS si puede producir. En particular, `cover_test` debe modelarse como `"OD: {tipo}[ y {sub}] | OI: {tipo}[ y {sub}]"`, no como strings sinteticos tipo `"ortoforia"` o `"exoforia en VP"`.

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

Cada correlacion se define como:

- `_cond_x(req) -> bool`
- `_texto_x(req) -> str`

Y se registra como:

```python
Correlacion("nombre", _cond_x, _texto_x)
```

La funcion publica `evaluar_correlaciones(req)`:

1. recorre `CORRELACIONES` en orden fijo;
2. ejecuta cada condicion;
3. si una condicion es `True`, agrega su texto a la lista final;
4. registra en log los nombres activados.

### Propiedades del motor

- Determinista: mismo input, mismas correlaciones.
- None-safe: las condiciones hacen guards explicitos.
- Ordenado: la posicion en `CORRELACIONES` define el orden del bloque que recibe el LLM.
- Textual: las correlaciones generan texto final, no instrucciones.

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

Actualmente el registro contiene **36 correlaciones**.

### Orden real de evaluacion

1. `fondo_periferico_riesgo`
2. `papila_patologica`
3. `glaucoma_asimetrico` ← correlacion compuesta; suprime `pupilas_alteradas` y `fondo_glaucomatoso` cuando aplica
4. `pupilas_alteradas`
5. `fondo_glaucomatoso`
6. `fondo_macular_dmae`
7. `fondo_macular_otros`
8. `fondo_hipertensivo`
9. `fondo_vascular_diabetico`
10. `motilidad_alterada`
11. `campos_visuales_alterados`
12. `opacidad_cristaliniana`
13. `but_critico`
14. `miopia_magna`
15. `hipermetropia_alta`
16. `anisometropia`
17. `av_cc_limitada`
18. `ar_rx_espasmo_acomodativo`
19. `ar_rx_cambio_cristalino`
20. `ar_rx_variabilidad_inespecifica`
21. `ar_detecta_astigmatismo_no_prescrito`
22. `astig_oblicuo`
23. `amsler_alterado`
24. `anexos_patologicos`
25. `insuficiencia_convergencia`
26. `ppc_exoforia`
27. `cover_exoforia_sintomatica`
28. `cover_endoforia_sintomatica`
29. `desviacion_vertical`
30. `cvs_sospecha`
31. `endotropia_lente`
32. `exotropia_lente`
33. `but_pantallas`
34. `but_limitrofe`
35. `presbicia_multifocal`
36. `adulto_mayor_screening`

### 7.1 Correlaciones de fondo de ojo

#### `fondo_periferico_riesgo`

Activa por keywords como:

- `desgarro`
- `agujero retiniano`
- `lattice`
- `degeneracion reticular`
- `blanco con presion`
- `desprendimiento`
- `schisis`
- `retinosquisis`

Texto:

```text
Hallazgo urgente: en la retina periferica se documenta desgarro retiniano, degeneracion lattice o cualquier otro hallazgo periferico de riesgo, que amerita valoracion retinologica urgente y posible tratamiento profilactico.
```

#### `glaucoma_asimetrico`

Correlacion compuesta. Activa si se cumplen simultaneamente:

- `reflejos_pupilares` contiene `dpar` o `marcus gunn`
- `fondo_de_ojo` contiene alguna keyword de `fondo_glaucomatoso`

Cuando activa, suprime tanto `pupilas_alteradas` como `fondo_glaucomatoso`, evitando que el LLM reciba dos fragmentos separados que describen el mismo proceso (neuropatia optica glaucomatosa asimetrica).

Texto:

```text
Hallazgo urgente: los hallazgos papilares glaucomatosos asociados a defecto pupilar aferente relativo son compatibles con neuropatia optica glaucomatosa avanzada y asimetrica, con compromiso funcional confirmado, ameritando valoracion oftalmologica priorizada.
```

#### `fondo_glaucomatoso`

Activa por keywords papilares, por ejemplo:

- `c/d 0.6`, `c/d 0.7`, `c/d 0.8`, `c/d 0.9`
- `cup/disc 0.6` a `0.9`
- `excavacion`
- `papila asimetrica`
- `asimetria c/d`
- `muesca`
- `notch`
- `hemorragia peripapilar`
- `rima neural adelgazada`

Texto:

```text
Los hallazgos papilares documentados sugieren neuropatia optica glaucomatosa, ameritando valoracion oftalmologica con tonometria, paquimetria y perimetria para estadificacion.
```

#### `papila_patologica`

Captura hallazgos del nervio optico no glaucomatosos, por ejemplo:

- `palidez papilar`
- `palidez de papila`
- `atrofia optica`
- `atrofia papilar`
- `edema de papila`
- `papiledema`
- `neuritis optica`
- `borramiento de bordes`
- `bordes borrosos`

Puede coexistir con `fondo_glaucomatoso` porque cubre un tipo distinto de compromiso del nervio optico.

Si el fondo contiene:

- `papiledema`
- `edema de papila`
- `borramiento de bordes`
- `bordes borrosos`

el texto sube de prioridad a un mensaje urgente:

```text
Los hallazgos del nervio optico documentados son compatibles con edema de papila, lo que amerita evaluacion neurooftalmologica urgente para descarte de hipertension intracraneal.
```

En los demas casos usa:

```text
Los hallazgos del nervio optico documentados son compatibles con compromiso del mismo no glaucomatoso, ameritando valoracion neurooftalmologica para caracterizacion etiologica.
```

#### `fondo_macular_dmae`

Activa por keywords de DMAE, por ejemplo:

- `drusas`
- `drusen`
- `alteracion pigmentaria`
- `alteracion del epr`
- `atrofia geografica`
- `membrana neovascular`
- `mnvc`
- `cnv`
- `epiteliopatia`
- `dmae`
- `degeneracion macular`

Texto:

```text
Los hallazgos maculares documentados son compatibles con degeneracion macular asociada a la edad, ameritando OCT macular para caracterizacion y monitorizacion.
```

#### `fondo_macular_otros`

Activa por keywords maculares no DMAE, por ejemplo:

- `edema macular`
- `membrana epirretiniana`
- `mer`
- `pucker`
- `agujero macular`
- `quiste macular`
- `coroidopatia serosa`

Texto:

```text
En la region macular se documenta alteracion que amerita OCT y valoracion retinologica.
```

#### `fondo_hipertensivo`

Activa por keywords vasculares hipertensivas, por ejemplo:

- `tortuosidad vascular`
- `tortuosidad`
- `cruces arteriovenosos`
- `cruces av`
- `signo de gunn`
- `estrechamiento arterial`
- `hilos de cobre`
- `hilos de plata`
- `algodonoso`
- `cotton wool`
- `salus`

Texto:

```text
Los hallazgos vasculares en fondo de ojo son compatibles con retinopatia hipertensiva, ameritando correlacion con cifras tensionales sistemicas.
```

#### `fondo_vascular_diabetico`

Activa por:

- `microaneurisma`
- `microaneurismas`
- `exudado`
- `hemorragia retiniana`
- `hemorragia en llama`
- `hemorragia intraretin`
- `hemorragia en mancha`
- `hemorragia puntiforme`
- `neovas`
- `rubeosis`

Pero solo si no se activaron antes:

- `fondo_periferico_riesgo`
- `fondo_glaucomatoso`
- `fondo_macular_dmae`
- `fondo_macular_otros`
- `fondo_hipertensivo`

Texto:

```text
Los hallazgos en fondo de ojo son compatibles con retinopatia de origen metabolico o vascular, ameritando correlacion sistemica.
```

### 7.2 Correlaciones neuro-oftalmicas y de examen funcional

#### `pupilas_alteradas`

Busca hallazgos como:

- `anisocoria`
- `midriasis`
- `miosis`
- `dpar`
- `marcus gunn`
- `no reactivo`
- `no reactiva`
- `irregular`
- `discoria`
- `ausente`

Si detecta `dpar` o `marcus gunn`, el texto agrega una frase extra de urgencia.

Texto base:

```text
En la exploracion pupilar se documenta ..., lo que amerita valoracion neurooftalmologica.
```

Texto adicional si hay DPAR:

```text
Hallazgo urgente: la presencia de defecto pupilar aferente relativo es indicativa de patologia de via optica y requiere evaluacion urgente.
```

#### `motilidad_alterada`

Activa por keywords como:

- `limitacion`
- `paresia`
- `paralisis`
- `restriccion`
- `nistagmo`
- `nistagmus`
- `dolor con movimiento`
- `dolor al movimiento`
- `sobreacti`
- `hiperfuncion`
- `hipoaccion`
- `hipofuncion`
- `sincinesia`
- `duane`
- `oftalmoplejia`
- `oftalmoplegia`

Texto:

```text
Se documenta alteracion de la motilidad ocular, lo que amerita estudio de vias motoras y posible interconsulta neurooftalmologica.
```

#### `campos_visuales_alterados`

Activa si en `confrontacion_campos_visuales` encuentra keywords positivas como:

- `escotoma`
- `defecto`
- `hemianopsia`
- `cuadrantopsia`
- `constriccion`
- `alteracion`
- `no responde`

Y no encuentra negaciones globales como:

- `sin defect`
- `sin alteracion`
- `normal`
- `integro`

Texto:

```text
La confrontacion de campos visuales revela alteracion que amerita perimetria automatizada para caracterizacion del defecto.
```

#### `opacidad_cristaliniana`

Busca en la concatenacion de:

- `clinica.anexos_oculares`
- `clinica.fondo_de_ojo`

Esto es deliberadamente flexible: aunque el cristalino no pertenece formalmente a los anexos oculares, en la practica algunos hallazgos se documentan alli y el sistema intenta no perder esa informacion.

Keywords como:

- `catarata`
- `cataratas`
- `opacidad cristaliniana`
- `opacidad del cristalino`
- `facoesclerosis`
- `pseudofaquia`
- `pseudofaco`
- `pseudofaquico`
- `afaquia`
- `afaquico`

Texto:

```text
Se documenta alteracion del cristalino, ameritando evaluacion biomicroscopica para caracterizacion y estadificacion de la opacidad.
```

El texto no menciona la reduccion de AV deliberadamente: `av_cc_limitada` es la correlacion responsable de ese hecho. Separar ambas evita que el LLM repita la misma relacion causal dos veces.

#### `amsler_alterado`

Activa si `grid_de_amsler` contiene hallazgos funcionales como:

- `distorsion`
- `metamorfopsia`
- `escotoma central`
- `escotoma`
- `alterado`
- `alteracion`
- `ondulacion`
- `lineas torcidas`

Y no contiene negaciones globales como:

- `sin distorsion`
- `sin alteracion`
- `normal`
- `negativo`

Texto:

```text
El test de Amsler revela alteracion compatible con patologia macular funcional que amerita OCT macular.
```

### 7.3 Correlaciones refractivas

#### `miopia_magna`

Activa si el equivalente esferico es `<= -6.00D` en OD u OI.

Texto dinamico:

```text
Se documenta miopia magna en OD (EE -6.50D) y OI (EE -7.00D), lo que conlleva mayor riesgo de patologia retiniana periferica y macular.
```

#### `hipermetropia_alta`

Activa si el equivalente esferico es `>= +5.00D` en OD u OI.

El texto varia segun la edad:

- `edad is None` o `edad >= 40`:

```text
Se documenta hipermetropia alta en {ojos}, lo que amerita evaluacion de la profundidad de camara anterior ante el riesgo asociado de angulo camerular estrecho.
```

- `edad < 40`:

```text
Se documenta hipermetropia alta en {ojos}, lo que genera demanda acomodativa significativa y amerita vigilancia de esoforia o esotropia acomodativa.
```

#### `anisometropia`

Usa equivalente esferico, no esfera pura.

Activa si:

```text
abs(EE_OD - EE_OI) > 1.00D
```

Clasificacion textual:

- `< 2.00D`: leve
- `<= 3.00D`: moderada
- `> 3.00D`: severa

Si los equivalentes tienen signo opuesto, el cierre cambia a:

```text
antimetropia con posible compromiso fusional
```

Texto base:

```text
Existe anisometropia ... por diferencia de equivalente esferico de X.XXD entre OD (...) y OI (...); ...
```

#### `av_cc_limitada`

Activa solo si la AV con correccion tiene denominador Snellen `> 20`.

No activa con:

- `20/20`
- `20/15`
- otros valores mejores o iguales a 20/20

Categorias:

- `21-30`: leve reduccion
- `31-50`: reduccion moderada
- `51-100`: reduccion marcada
- `>100`: deficit visual severo

Texto dinamico por ojo:

```text
OD (20/30): leve reduccion de la agudeza visual con correccion; OI (20/60): reduccion marcada de la agudeza visual con correccion.
```

### 7.4 Correlaciones AR vs Rx

#### `ar_rx_espasmo_acomodativo`

Activa si:

- `edad < 40`
- `uso_pantallas in ("btw2_6", "gt6")`
- en al menos un ojo, `esf_rx - esf_ar >= 0.50`

Interpretacion: el autorrefractometro da un componente mas miopico que la refraccion final.

Texto:

```text
El autorrefractometro documenta mayor componente miopico que la refraccion subjetiva final en un paciente joven con uso intensivo de pantallas, patron compatible con espasmo acomodativo que amerita control posterior y eventual refraccion bajo cicloplegia.
```

#### `ar_rx_cambio_cristalino`

Activa si:

- `edad >= 55`
- en al menos un ojo `abs(esf_ar - esf_rx) > 1.00`

Texto:

```text
La discrepancia entre autorrefractometro y refraccion final en un paciente mayor de 55 anos puede reflejar cambios en el indice refractivo del cristalino, ameritando evaluacion biomicroscopica del segmento anterior.
```

#### `ar_rx_variabilidad_inespecifica`

Activa si existe discrepancia mayor a `1.00D` en esfera o cilindro entre AR y Rx, pero no activaron:

- `ar_rx_espasmo_acomodativo`
- `ar_rx_cambio_cristalino`

Texto:

```text
Se documenta discrepancia entre autorrefractometro y refraccion final, compatible con variabilidad refractiva durante la exploracion.
```

#### `ar_detecta_astigmatismo_no_prescrito`

Activa si en algun ojo:

- `abs(cilindro_AR) >= 0.75`
- y `cilindro_Rx` es `None` o `abs(cilindro_Rx) < 0.50`

Texto:

```text
El autorrefractometro detecta un componente astigmatico que no fue incluido en la refraccion subjetiva final, lo que puede corresponder a astigmatismo subumbral con tolerancia clinica adecuada o variabilidad de la medicion automatizada.
```

### 7.5 Correlaciones de anexos, binocularidad y superficie ocular

#### `astig_oblicuo`

Activa si en OD u OI:

- `abs(cilindro) > 2.00`
- y el eje es oblicuo: `20-70` o `110-160`

La severidad del texto depende de la magnitud:

- `<= 3.00`: astigmatismo elevado con eje oblicuo
- `<= 4.00`: astigmatismo alto con posible periodo de adaptacion
- `> 4.00`: magnitud muy alta con mayor impacto visual y de adaptacion

Texto dinamico por ojo.

#### `anexos_patologicos`

Busca en `anexos_oculares` hallazgos como:

- `blefaritis`
- `chalazion`
- `orzuelo`
- `pterigion`
- `pinguecula`
- `conjuntivitis`
- `hiperemia`
- `queratitis`
- `erosion`
- `leucoma`
- `opacidad corneal`
- `edema corneal`
- `distriquiasis`
- `triquiasis`
- `ectropion`
- `entropion`
- `ptosis`

Texto:

```text
En anexos oculares se documenta blefaritis y pterigion.
```

Los hallazgos se deduplican antes de construir la frase.

#### `ppc_exoforia`

Activa si:

- `ppc_cm > 10`
- o `cover_test` contiene `exoforia`

Pero se suprime si ya activo `insuficiencia_convergencia`, para evitar redundancia entre hallazgos componentes y la correlacion compuesta mas especifica.

Texto dinamico:

- `ppc > 15`: "punto proximo de convergencia marcadamente alejado"
- `ppc > 10`: "punto proximo de convergencia alejado"
- `exoforia` con `vp`, `cerca` o `proxima`: "exoforia en vision proxima"
- `exoforia` con `vl` o `lejos`: "exoforia en vision lejana"
- si no, "tendencia divergente en el cover test"

#### `cover_exoforia_sintomatica`

Activa si:

- `cover_test` contiene `exoforia`
- y `motivo_consulta` contiene algun sintoma binocular

Tambien se suprime si ya activo `insuficiencia_convergencia`.

Keywords de sintomas:

- `diplopia`
- `vision doble`
- `cefalea`
- `dolor de cabeza`
- `astenopia`
- `fatiga visual`
- `vista cansada`
- `mareo`
- `vertigo`
- `ardor con lectura`
- `lagrimeo con lectura`
- `perdida del renglon`
- `salto de letras`
- `vision borrosa intermitente`

Texto:

```text
La exoforia documentada junto con la sintomatologia referida es compatible con disfuncion binocular de tipo divergente que amerita evaluacion funcional.
```

#### `cover_endoforia_sintomatica`

Activa si:

- `cover_test` contiene `endoforia`
- no contiene `endotropia`
- y hay sintomas binoculares en el motivo

Texto:

```text
La endoforia documentada junto con la sintomatologia referida es compatible con exceso de convergencia o disfuncion acomodativa que amerita evaluacion funcional.
```

#### `insuficiencia_convergencia`

Activa si:

- `ppc_cm > 10`
- `cover_test` contiene `exoforia`
- `motivo_consulta` contiene una keyword de vision cercana

Keywords de cercania:

- `lectura`
- `leer`
- `estudiar`
- `cerca`
- `astenopia`
- `fatiga`
- `cefalea`

Texto:

```text
La combinacion de punto proximo de convergencia alejado, exoforia y sintomatologia de vision proxima es compatible con insuficiencia de convergencia, ameritando evaluacion binocular completa para confirmar diagnostico y plantear terapia visual si procede.
```

Esta correlacion se evalua antes que `ppc_exoforia` y `cover_exoforia_sintomatica`, y hace de capa mas especifica dentro del bloque binocular.

#### `cvs_sospecha`

Activa si:

- `uso_pantallas in ("btw2_6", "gt6")`
- y el motivo tiene sintomas compatibles con CVS

Keywords:

- `ardor ocular`
- `sequedad ocular`
- `vision borrosa intermitente`
- `dolor ocular`
- `ardor`
- `sequedad`

Texto:

```text
El perfil de uso de pantallas y la sintomatologia referida son compatibles con sindrome visual informatico, ameritando recomendaciones ergonomicas y eventual correccion optica para vision intermedia.
```

#### `endotropia_lente`

Activa si:

- `cover_test` contiene `endotropia`
- y `tipo_lente` no es `None`

Texto:

```text
La endotropia documentada en el cover test amerita evaluacion de la respuesta a la correccion optica prescrita, con cover test bajo correccion para clasificar el tipo de desviacion.
```

#### `exotropia_lente`

Activa si:

- `cover_test` contiene `exotropia`
- y `tipo_lente` no es `None`

Texto:

```text
La exotropia documentada en el cover test amerita evaluacion binocular completa para determinar frecuencia y magnitud de la desviacion, asi como la respuesta a la correccion optica prescrita.
```

#### `desviacion_vertical`

Activa si `cover_test` contiene alguna desviacion vertical como:

- `hiperforia`
- `hipoforia`
- `hipertropia`
- `hipotropia`

El texto es dinamico: cita solo los hallazgos detectados y distingue forias (desviacion latente) de tropias (desviacion manifiesta).

Texto con foria solamente:

```text
Se documenta hiperforia, que puede generar sintomatologia binocular especifica y amerita cuantificacion prismatica para evaluar compensacion.
```

Texto con tropia (con o sin foria asociada):

```text
Se documenta hipertropia, que representa una desviacion manifiesta y amerita cuantificacion prismatica inmediata con evaluacion binocular completa.
```

#### `but_critico`

Activa si:

- `ojo_seco_but_seg < 5`

Texto:

```text
El tiempo de ruptura lagrimal de Xs es patologicamente bajo, compatible con ojo seco clinico que amerita evaluacion.
```

#### `but_pantallas`

Activa si:

- `5 <= BUT <= 9`
- y `uso_pantallas in ("btw2_6", "gt6")`

Texto:

```text
El tiempo de ruptura lagrimal de X segundos es reducido en el contexto del uso de pantallas, lo que indica inestabilidad de la pelicula lagrimal.
```

#### `but_limitrofe`

Activa si:

- `5 <= BUT <= 9`
- y `uso_pantallas in (None, "lt2")`

Texto:

```text
El tiempo de ruptura lagrimal de Xs se encuentra en rango suboptimo, sugiriendo inestabilidad leve de la pelicula lagrimal.
```

### 7.6 Correlaciones de edad y contexto refractivo

#### `presbicia_multifocal`

Activa si se cumple cualquiera de estas dos ramas:

- `tipo_lente` contiene `bifocal`, `progresivo` o `multifocal`, y ademas hay edad `>= 40` o algun `add`;
- o bien hay `edad >= 40` y algun `add`, aunque el lente no sea multifocal.

Texto:

- con edad:

```text
El paciente de 48 anos presenta reduccion fisiologica de la amplitud acomodativa propia de la edad, lo que justifica la adicion prescrita y el lente multifocal indicado.
```

- sin edad, pero con add:

```text
Se documenta reduccion fisiologica de la amplitud acomodativa, lo que justifica la adicion prescrita.
```

#### `adulto_mayor_screening`

Activa si:

- `edad >= 60`
- y existe AV con correccion limitada en OD u OI

Pero se suprime si ya existe una correlacion patologica especifica que explique la reduccion visual, por ejemplo:

- `opacidad_cristaliniana`
- `fondo_glaucomatoso`
- `fondo_macular_dmae`
- `fondo_macular_otros`
- `fondo_vascular_diabetico`
- `fondo_hipertensivo`
- `miopia_magna`
- `papila_patologica`

Texto:

```text
En paciente de X anos con reduccion de agudeza visual, se recomienda descarte activo de catarata, glaucoma y maculopatia asociada a la edad mediante exploracion dirigida.
```

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

#### Correlacion AKR vs refraccion final

Este bloque aparece si existe al menos un valor no nulo en `akr.od` o `akr.oi`.

Para cada ojo, si hay datos, incluye:

- `AKR OD: ...`
- `Rx final OD: ...`
- `AKR OI: ...`
- `Rx final OI: ...`

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
  "provider": "nvidia"
}
```

### Respuesta exitosa desde cache

```json
{
  "status": "ok",
  "impresion_clinica": "El paciente ...",
  "provider": "nvidia",
  "cached": true
}
```

El campo `provider` indica que proveedor genero la respuesta: `"nvidia"` o `"ollama"`. Util para monitoreo y debug sin necesidad de revisar logs del servidor.

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

1. Definir `_cond_x(req)` y `_texto_x(req)` en `app/correlaciones.py`.
2. Agregar `Correlacion("x", _cond_x, _texto_x)` al registro `CORRELACIONES`.
3. Si depende de texto libre, decidir si requiere:
   - normalizacion;
   - keywords;
   - ventana de negacion.
4. Verificar el orden de prioridad dentro de `CORRELACIONES`.
5. Actualizar esta documentacion.

### Regla de oro

La condicion decide si aplica.

El texto redacta un hecho clinico ya decidido.

El LLM no debe decidir la correlacion: solo integrarla al parrafo.

### Si cambias prompts o correlaciones

Debes revisar al menos:

- `PIPELINE_LLM.md`
- `app/prompt_builder.py`
- `app/correlaciones.py`
- `app/cache.py` si cambian condiciones que deban invalidar cache

### Si cambias el proveedor de inferencia

- Los parametros de sampling de Ollama estan en `app/providers/ollama.py`
- Los parametros de NVIDIA estan en `app/providers/nvidia.py` y `app/config.py`
- La logica de fallback y seleccion esta en `app/inference.py` (`run_inference`)
- El timeout total de `asyncio.wait_for` se calcula en `app/main.py` (`_INFERENCE_TIMEOUT`)
