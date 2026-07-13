# Diccionario de datos de la receta (SaaS `opt`) y afinación de la IA-API

Análisis exhaustivo de cómo se construye la receta en el SaaS (`C:\Users\Uriel Rojo\Documents\opt`)
y de las limitantes reales de cada dato del payload que recibe esta API, con la afinación
aplicada al código de la IA-API para explotar los valores estandarizados (dropdowns,
constantes, concatenados) en lugar de adivinar sobre texto libre.

**Fuentes analizadas en el SaaS:**

| Pieza | Archivo |
|---|---|
| Catálogos numéricos (esfera, cilindro, AV, tipos de lente) | `app/Support/OpticaOptions.php` |
| Opciones del formulario (reflejos, cover test, materiales, tratamientos) | `app/Support/Recetas/RecetaFormOptions.php` |
| Reglas de validación (rangos AKR, clínica, enums) | `app/Support/Recetas/RecetaValidationRules.php` |
| Estado del formulario y campos concatenados | `app/Livewire/Forms/RecetaForm.php` |
| Flujo de guardado y llamada a la IA | `app/Livewire/Recetas/FormEditor.php` |
| Construcción del payload hacia la IA-API | `app/Services/IaApiService.php` (`buildPayload`) |
| UI de captura (dropdowns, radios, defaults, botones) | `resources/views/livewire/recetas/form/*.blade.php` |
| Mapeo modelo ⇄ formulario | `app/Support/Recetas/RecetaFormMapper.php` |

---

## 1. Diccionario de datos del payload `/inferencia/impresion-clinica`

Leyenda de **origen**: `DROPDOWN` (catálogo cerrado), `RADIO` (opciones fijas),
`NUM LIBRE` (input numérico sin catálogo), `TEXTO` (texto libre), `CONCAT`
(compuesto por el SaaS a partir de sub-campos), `CALC` (calculado), `DEVICE`
(lectura del autorrefractómetro, solo lectura en la UI).

### 1.1 `paciente`

| Campo | Origen | Limitante real | Notas |
|---|---|---|---|
| `edad` | CALC | entero ≥ 0; derivado de `fecha_nacimiento` (input date) con `Carbon::age` | El nombre y teléfono NO viajan a la IA |
| `ocupacion` | TEXTO | requerido, máx 255 | Insumo de `_KEYWORDS_OCUPACION_PROXIMA` |
| `motivo_consulta` | TEXTO | requerido, máx 255 | Insumo de keywords binoculares / CVS |

### 1.2 `refraccion.od` / `refraccion.oi` (Rx final)

| Campo | Origen | Limitante real | Notas |
|---|---|---|---|
| `esfera` | DROPDOWN | **+20.00 → −20.00, paso 0.25** (161 opciones); default `0.00`, sin opción vacía → en `create` SIEMPRE llega valor | `OpticaOptions::esfera()` |
| `cilindro` | DROPDOWN | **0.00 → −8.00, paso 0.25** (33 opciones); **siempre ≤ 0** (convención negativa); default `0.00` | `OpticaOptions::cilindro()` |
| `eje` | NUM LIBRE | entero; **el SaaS NO valida rango** (`nullable\|integer`, sin `between`) | ⚠ ver hallazgo H2 |
| `add` | NUM LIBRE | numérico, step 0.25, **sin rango**; puede teclearse 0 o negativo | ⚠ ver hallazgo H5 |
| `av_sc` / `av_cc` | DROPDOWN | catálogo cerrado de 16 valores Snellen en pies: `20/10, 20/15, 20/20, 20/25, 20/30, 20/40, 20/50, 20/60, 20/70, 20/80, 20/100, 20/120, 20/160, 20/200, 20/400, 20/600` (+ vacío) | `OpticaOptions::av()` |
| `dnp`, `altura_montaje` | NUM LIBRE | step 0.5 | **No viajan a la IA** |

### 1.3 `akr` (autorrefractómetro/queratometría — solo lectura, botón "Obtener medición")

| Campo | Origen | Limitante real (validación SaaS al guardar) |
|---|---|---|
| `od/oi.esfera`, `cilindro` | DEVICE | numérico sin rango |
| `od/oi.eje` | DEVICE | entero **sin rango** (a diferencia de los ejes K) |
| `od/oi.k1_d`, `k2_d` | DEVICE | numérico **sin rango** (solo el promedio tiene rango) |
| `od/oi.k1_mm`, `k2_mm`, `k_promedio_mm` | DEVICE | `between:4,12` |
| `od/oi.k1_eje`, `k2_eje`, `k_cilindro_eje` | DEVICE | `between:0,180` |
| `od/oi.k_promedio_d` | DEVICE | `between:25,80` |
| `od/oi.k_cilindro` | DEVICE | numérico sin rango |
| `pd` | DEVICE | numérico sin rango |
| `vd` | DEVICE | `between:0,30` |
| `ker_index` | DEVICE | `between:1.3,1.4` |
| `ticket_id`, `taken_at` | DEVICE | entero / fecha; solo trazabilidad. `taken_at` **no está modelado** en el schema de la API (Pydantic lo ignora) |

### 1.4 `clinica` (extensión clínica — solo si el usuario tiene permiso `recetas.clinica`)

| Campo | Origen | Limitante real | Notas |
|---|---|---|---|
| `uso_pantallas` | DROPDOWN | **enum cerrado: `lt2` \| `btw2_6` \| `gt6`** (`<2h`, `2–6h`, `>6h`) o vacío | Constante real: dispara CVS, espasmo acomodativo, BUT-pantallas |
| `anexos_oculares` | TEXTO | máx 255 | Keywords (blefaritis, pterigión, …) |
| `reflejos_pupilares` | CONCAT | `"Opción[: nota]"`. Opción por chips: **`Reflejo fotomotor, consesual, acomodativo`** (default/normal) \| **`Marcus Gunn`**; nota = texto libre | El chip "Marcus Gunn" dispara DPAR de forma determinista |
| `motilidad_ocular` | CONCAT | 4 sub-campos de texto libre unidos como `Versiones: X` / `Ducciones: Y` / `Sacadicos: Z` / `Seguimiento: W` (multilínea en BD; **aplanado a una sola línea** por `IaApiService::normalizeSingleLineString`) | Keywords sobre los valores libres |
| `confrontacion_campos_visuales` | TEXTO | máx 255; botón "Default" inserta la constante **`Sin defectos perifericos evidentes.`** | Verificado: la ventana de negación NO dispara con el default |
| `fondo_de_ojo` | TEXTO | máx 255 | Keywords (8 correlaciones de fondo) |
| `grid_de_amsler` | TEXTO | máx 255; botón "SDPA" inserta la constante **`Sin descendencia de patologia aparente.`** | Verificado: no dispara falsos positivos |
| `ojo_seco_but_seg` | DROPDOWN | **entero 1..15** (segundos) | Umbrales API: `<5` crítico, `5–9` límite/pantallas, `≥10` normal — todo alcanzable dentro del catálogo ✔ |
| `cover_test` | CONCAT | **`"OD: Tipo[ y Sub] \| OI: Tipo[ y Sub]"`**. Tipo (radio, default `Orto`): `Orto\|Endo\|Exo\|Hiper\|Hipo`. Sub (radio **SIN default, opcional**): `Tropia\|Foria` | ⚠ el sub puede quedar sin clasificar: "OD: Endo \| OI: Orto" es un estado real — ver hallazgo H6 |
| `ppc_cm` | DROPDOWN | **entero 1..15** (cm) | Umbrales API: `>6` joven / `>10` présbita — alcanzables ✔ |
| `recomendacion_seguimiento` | TEXTO | libre; 2 presets: revisión gratuita / revisión anual | Solo contexto de prompt |
| `impresion_clinica_plan` | TEXTO | libre | Es el DESTINO de la respuesta de la IA; no es insumo |

### 1.5 `tipo_lente` y campos que NO viajan

| Campo | Origen | Limitante real |
|---|---|---|
| `tipo_lente` | DROPDOWN | **enum cerrado validado: `monofocal` \| `bifocal_blended` \| `progresivo` \| `flat_top`**; default `monofocal`, requerido |

No viajan a la IA (existen en la receta pero `buildPayload` no los incluye):
`material` (chips: CR-39, Policarbonato, Hi-Index, Ultra Hi), `tratamientos` (chips: AR,
BlueRay, Blanco W, Fotocromatico, Polarizado, Entintado, Verde, Gris, Cafe), armazón
(marca/modelo/color), `dnp`, `altura_montaje`, pago (precio/anticipo), observaciones
(laboratorio/generales), nombre y teléfono del paciente.

---

## 2. Hallazgo transversal más importante

**El endpoint de IA recibe el formulario SIN validar.** `FormEditor::generateImpresionClinica()`
llama `$this->form->toPayload(true)` y lo envía directo a `IaApiService`; la validación de
Laravel (`RecetaValidationRules`) solo corre en `save()`. Por lo tanto la IA-API puede recibir
ejes de 190°, adds negativas o Ks corruptas **aunque el SaaS "valide" la receta**, porque el
botón "Generar con IA" se usa antes de guardar.

**Afinación aplicada:** el schema de la IA-API pasó de *rechazo estricto (422)* a
**coerción tolerante**: el valor fuera de catálogo se descarta (`None`) o se normaliza y se
loggea, en vez de tumbar toda la generación por un dato secundario.

---

## 3. Afinación aplicada vs código actual (hallazgo → cambio)

| # | Hallazgo | Antes (ia-api) | Cambio aplicado |
|---|---|---|---|
| H1 | El payload llega sin validar desde el SaaS (sección 2) | Cualquier valor fuera de rango → 422 de todo el request | **Coerción tolerante** en `app/schemas.py`: los límites del catálogo viven como constantes (`_ESFERA_MAX_ABS_D`, `_CILINDRO_MAX_ABS_D`, `_EJE_MIN/_EJE_MAX`, `_BUT_PPC_MIN/_BUT_PPC_MAX`, `_USO_PANTALLAS`); fuera de rango → `None` + warning en log (`_rango_o_none`) |
| H2 | `eje` es input libre **sin validación de rango en el SaaS**; la API exigía 0..180 | `eje=190` → 422 | El eje es cíclico: se **normaliza módulo 180** (190→10, −1→179, 225→45). Aplica a Rx y a los 4 ejes de AKR |
| H3 | El catálogo de cilindro es **solo negativo** (0..−8); un cilindro positivo del **AKR** (lectura de dispositivo) puede venir en convención plus-cyl y sesgar la comparación esfera-a-esfera AR vs Rx | El AKR plus-cyl se aceptaba tal cual → comparación AR vs Rx en distinta convención | **Transposición automática a convención negativa** (`esf'=esf+cil`, `cil'=−cil`, `eje'=(eje+90)%180`) **solo en el AKR**. La **Rx final NO se transpone**: el dropdown ya garantiza minus-cyl y transponerla alteraría el piso de esfera de `hipermetropia_alta` (ver [CORRELACIONES_CLINICAS.md §5.2](CORRELACIONES_CLINICAS.md)) |
| H4 | Esfera limitada al catálogo ±20.00; cilindro a \|8.00\| | Sin límite | Fuera de catálogo → `None` (dato corrupto, no hallazgo) |
| H5 | `add` es input libre: el optometrista puede teclear `0` | `add=0.0` contaba como "adición prescrita": disparaba `presbicia_multifocal` y **suprimía** `presbicia_sin_adicion` (bug real) | `add ≤ 0` → `None`; con ello `presbicia_sin_adicion` vuelve a operar correctamente |
| H6 | El **sub del cover test es opcional** (radios sin default): "OD: Exo \| OI: Orto" es un estado real del formulario que las keywords unidas (`exoforia`, `exotropia`) no ven | Un Endo/Exo/Hiper/Hipo sin clasificar **no disparaba nada** (dato de dropdown silenciosamente ignorado) | Parser estructurado del formato canónico (`_cover_desviaciones` en `texto.py`): `Exo` suelto → `ppc_exoforia` ("exodesviación no clasificada"); `Endo` suelto + síntomas → `cover_endoforia_sintomatica`; `Hiper/Hipo` sueltos → `desviacion_vertical`. Un tipo sin clasificar NUNCA se trata como tropía manifiesta |
| H7 | `flat_top` **es un bifocal** de segmento visible (catálogo del SaaS) | `_MULTIFOCAL_TOKENS = (bifocal, progresivo, multifocal)` → flat_top se trataba como monofocal: no justificaba la add y disparaba en falso `presbicia_sin_adicion` | `flat_top` (y variantes `flat-top`, `flat top`) agregado a `_MULTIFOCAL_TOKENS` en `contexto.py` |
| H8 | La clave cruda `bifocal_blended`/`flat_top` llegaba al prompt del LLM | El modelo podía copiar "bifocal_blended" (con guion bajo) al párrafo clínico | `TIPO_LENTE_MAP` en `prompt_builder.py`: claves canónicas → etiqueta clínica legible ("bifocal blended (sin linea visible)", "bifocal flat-top (segmento visible)") |
| H9 | `k1_d`/`k2_d` **sin rango en el SaaS** (solo el promedio tiene `between:25,80`) | `Field(ge=25, le=80)` → 422 con lectura corrupta | Fuera de 25..80 D (o 4..12 mm) → `None`; misma política para `vd` (0..30) y `ker_index` (1.3..1.4) |
| H10 | `uso_pantallas`, `ppc_cm`, `ojo_seco_but_seg`, `edad` son catálogos cerrados | 422 si llegaba algo fuera | Coerción a `None` conservando el `Literal`/rango como contrato documental |

**Verificado sin cambios (ya alineado con el catálogo):**

- Umbrales de BUT (`<5`, `5–9`, `≥10`) y PPC (`>6` joven, `>10` présbita) alcanzables dentro de los dropdowns 1..15 ✔
- `_av_denominator` cubre los 16 valores del catálogo AV (20/10..20/600) ✔; el catálogo quedó documentado en `AV_CATALOGO`
- El chip "Marcus Gunn" de reflejos pupilares dispara `pupilas_alteradas`/DPAR de forma determinista ✔
- Los textos default del SaaS ("Sin defectos perifericos evidentes.", "Sin descendencia de patologia aparente.") no generan falsos positivos gracias a la ventana de negación ✔
- El aplanado a una línea de `motilidad_ocular` (etiquetas `Versiones:`/`Ducciones:`/`Sacadicos:`/`Seguimiento:`) es compatible con las keywords de motilidad ✔
- La normalización `" - "` → `" y "` del cover test replica exactamente `IaApiService::normalizeCoverTest` ✔

**Archivos modificados en la IA-API:**

- `app/schemas.py` — reescrito: catálogo del SaaS como constantes + coerción tolerante + transposición
- `app/correlaciones/texto.py` — `_cover_desviaciones()`: parser estructurado del cover test canónico
- `app/correlaciones/binocularidad.py` — manejo de tipos sin clasificar (exo/endo/hiper/hipo sueltos)
- `app/correlaciones/contexto.py` — `flat_top` como multifocal
- `app/prompt_builder.py` — `TIPO_LENTE_MAP` para el prompt
- `tests/test_schemas.py`, `tests/test_correlaciones.py` — 172 tests en verde (nuevos tests de transposición, eje mod 180, cover sin clasificar, flat_top, add=0)

---

## 4. Recomendaciones para el lado SaaS (no aplicadas aquí)

1. **Validar el eje**: agregar `between:0,180` a `od_eje`/`oi_eje` (y a `akr_od_eje`/`akr_oi_eje`)
   en `RecetaValidationRules::request()`. Hoy es el único campo de graduación sin catálogo ni rango.
2. **Validar antes de "Generar con IA"**: en `FormEditor::generateImpresionClinica()`, correr el
   validator (o al menos los campos numéricos) antes de `toPayload()`. La IA-API ya es tolerante,
   pero la fuente de verdad debería ser el SaaS.
3. **Sub del cover test**: considerar exigir Tropia/Foria cuando el tipo ≠ Orto (o agregar opción
   explícita "Sin clasificar"), para que el dato quede siempre completo.
4. **`add` como dropdown**: dado que esfera/cilindro ya son catálogos, un dropdown `+0.75..+3.50`
   paso 0.25 eliminaría los ceros/negativos tecleables y alinearía la captura con la práctica clínica.
