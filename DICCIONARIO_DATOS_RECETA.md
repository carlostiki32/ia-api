# Diccionario de Datos de la Receta (SaaS `opt`) — Verdad Absoluta para IA-API

> ## DIRECTIVA OBLIGATORIA PARA CUALQUIER AGENTE / MODELO DE LENGUAJE (LLM)
> 
> **ESTE DOCUMENTO ES LA FUENTE DE VERDAD ABSOLUTA, NORMATIVA Y DEFINITIVA** sobre la estructura, tipos de datos, límites, catálogos, presets de interfaz y reglas de validación de los datos que el SaaS de optometría (`c:\Users\Uriel Rojo\Documents\opt`) construye y envía a esta API (`ia-api`).
> 
> 1. **Cero Suposiciones:** Ningún LLM, agente o desarrollador debe asumir, inventar o inferir rangos o límites diferentes a los aquí expresados. La lógica del backend de Laravel ya pasó la auditoría clínica y de persistencia en base de datos.
> 2. **Fidelidad al 100% en Payloads Ficticios:** Cualquier caso de prueba, mock o payload sintético creado para evaluar la IA DEBE cumplir estrictamente con los catálogos y límites de este documento. Si un dato ficticio excede los límites aquí descritos (por ejemplo, una ocupación de 150 caracteres o una K1 de 90 D), es un caso inválido que Laravel jamás permitiría guardar.
> 3. **Anonimización Estricta (Zero-PII):** Los datos identificativos del paciente (`nombre`, `telefono`, `fecha_nacimiento` exacta, dirección) NUNCA viajan a la IA. Solo viajan edad calculada (entero), ocupación y motivo de consulta.

---

## 0. Fuentes de Verdad en el Repositorio SaaS (`opt`)

Cada regla y límite documentado aquí proviene directamente del código en producción del SaaS:

| Dominio | Archivo en SaaS (`opt`) | Responsabilidad |
|---|---|---|
| **Reglas de Validación** | `app/Support/Recetas/RecetaValidationRules.php` | Límites de BD, tipos, rangos `between`, `max` y `min`. |
| **Catálogos Numéricos y Lentes** | `app/Support/OpticaOptions.php` | Dropdowns de graduación (esferas, cilindros, AV) y tipos de lente. |
| **Opciones y Chips de Formulario** | `app/Support/Recetas/RecetaFormOptions.php` | Constantes de reflejos, opciones de Cover Test y sugerencias. |
| **Estado y Lógica de UI** | `app/Livewire/Forms/RecetaForm.php` | Composición de campos derivados, regla de estado limpio/sucio (`dirtyDerived`). |
| **Construcción del Payload IA** | `app/Services/IaApiService.php` (`buildPayload`) | Extracción, aplanado de motilidad, cálculo de edad y formateo final. |
| **Mapeo Modelo ⇄ Formulario** | `app/Support/Recetas/RecetaFormMapper.php` | Transformación del expediente y formulario hacia el payload. |
| **Formateo Queratometría** | `app/Support/Recetas/AkrKeratometryFormatter.php` | Representación clínica y reglas de presencia queratométrica. |
| **Vistas Blade (Captura y Presets)** | `resources/views/livewire/recetas/form/*.blade.php` | Botones de un clic (Default, SDPA, Presets de seguimiento) y selects. |

---

## 1. Diccionario de Datos del Payload `/inferencia/impresion-clinica`

Leyenda de **Origen**:
* `DROPDOWN`: Menú select cerrado de opciones fijas en la interfaz.
* `RADIO`: Botones de selección excluyente.
* `CHIP`: Botón conmutador que inyecta una constante predeterminada.
* `PRESET`: Botón de un solo clic que inyecta texto clínico estandarizado.
* `NUM LIBRE`: Entrada numérica con validación estricta de rango y decimales.
* `TEXTO`: Texto libre sanitizado con longitud máxima en caracteres (`max`).
* `CONCAT`: Cadena serializada por el SaaS a partir de subcampos estructurados.
* `CALC`: Dato derivado matemáticamente antes de construir el JSON.
* `DEVICE`: Lectura originada directamente desde el autorrefractómetro (solo lectura en UI).

---

### 1.1 `paciente` (Contexto Clínico Anonimizado)

Laravel extrae los datos de `paciente`, omite cualquier dato identificativo (PII) y despacha únicamente:

| Campo | Tipo JSON | Origen | Límite y Regla en SaaS | Notas y Comportamiento Clínico |
|---|---|---|---|---|
| `edad` | `integer \| null` | CALC | Entero `≥ 0` y `≤ 125` | Calculado en Laravel mediante `Carbon::parse(fecha_nacimiento)->age`. En Laravel `fecha_nacimiento` se valida con `after_or_equal:1900-01-01\|before_or_equal:today`. La fecha exacta NUNCA viaja. |
| `ocupacion` | `string \| null` | TEXTO | `required\|string\|max:120` | **Tope exacto: 120 caracteres** (NO 255). Es insumo clave para evaluar distancias de trabajo, ergonomía visual y presbicia funcional. |
| `motivo_consulta` | `string \| null` | TEXTO | `required\|string\|max:1000` | **Tope exacto: 1000 caracteres** (NO 255). Admite descripciones detalladas de astenopía, cefalea o pérdida visual. |

*Datos del paciente que NUNCA viajan a la IA:* `nombre` (`string|max:255`), `telefono` (`string|max:50`), `fecha_nacimiento` original (`date`), dirección, correo o identificaciones fiscales.

---

### 1.2 `refraccion.od` / `refraccion.oi` (Refracción Subjetiva Final)

Ambos ojos poseen idéntica estructura y reglas:

| Campo | Tipo JSON | Origen | Límite y Regla en SaaS | Catálogo en UI / Comportamiento |
|---|---|---|---|---|
| `esfera` | `number \| null` | DROPDOWN | `nullable\|numeric\|decimal:0,2\|between:-30,30` | Dropdown de **+20.00 a -20.00 D en pasos de 0.25** (161 opciones exactas generadas por `OpticaOptions::esfera()`). Default en creación: `0.00`. Rango de BD admite hasta ±30.00 D para alta miopía y afaquia extrema. |
| `cilindro` | `number \| null` | DROPDOWN | `nullable\|numeric\|decimal:0,2\|between:-30,30` | Dropdown de **0.00 a -8.00 D en pasos de 0.25** (33 opciones en `OpticaOptions::cilindro()`). Siempre convención negativa (`≤ 0.00`). Default en creación: `0.00`. |
| `eje` | `integer \| null` | NUM LIBRE | `nullable\|integer\|between:0,180` | **Validado formalmente entre 0 y 180 grados**. En la IA se aplica `eje % 180` por si el optometrista tecleó un valor atípico antes de guardar. |
| `add` | `number \| null` | NUM LIBRE | `nullable\|numeric\|decimal:0,2\|between:0,30` | Entrada numérica con `step="0.25"`. El SaaS prohíbe negativos (`between:0,30`). Clínicamente oscila entre `+0.75` y `+3.50` D. Si llega `≤ 0.00`, la IA lo coerciona a `None` (sin adición). |
| `av_sc` | `string \| null` | DROPDOWN | `nullable\|string\|max:20` | Catálogo cerrado Snellen en pies (`OpticaOptions::av()`): `""` (vacío/guion), `20/10`, `20/15`, `20/20`, `20/25`, `20/30`, `20/40`, `20/50`, `20/60`, `20/70`, `20/80`, `20/100`, `20/120`, `20/160`, `20/200`, `20/400`, `20/600`. |
| `av_cc` | `string \| null` | DROPDOWN | `nullable\|string\|max:20` | Mismo catálogo exacto de 16 valores Snellen de `av_sc`. |

*Campos de graduación que NO viajan a la IA:* `dnp` (`decimal:0,2|between:0,100`), `altura_montaje` (`decimal:0,2|between:0,100`).

---

### 1.3 `akr` (Snapshot de Autorrefractómetro y Queratometría)

Lectura capturada automáticamente por el hardware óptico o cargada desde un ticket previo:

| Campo | Tipo JSON | Origen | Límite y Regla en SaaS | Notas y Formato |
|---|---|---|---|---|
| `ticket_id` | `integer \| null` | DEVICE | `nullable\|integer\|exists:akr_tickets,id` | ID del ticket original en BD (solo trazabilidad). |
| `taken_at` | `string \| null` | DEVICE | `nullable\|date\|after_or_equal:1970-01-02\|before_or_equal:2038-01-18` | Fecha/hora ISO/SQL (`Y-m-d H:i:s`) de captura. Pydantic lo ignora de forma inocua. |
| `pd` | `number \| null` | DEVICE | `nullable\|numeric\|decimal:0,2\|between:0,100` | Distancia pupilar medida por el autorefractor (mm). |
| `vd` | `number \| null` | DEVICE | `nullable\|numeric\|decimal:0,2\|between:0,30` | Distancia al vértice (habitual: 12.0 mm). |
| `ker_index` | `number \| null` | DEVICE | `nullable\|numeric\|decimal:0,4\|between:1.3,1.4` | Índice queratométrico calibrado (habitual: `1.3375`). |
| **`od` / `oi` (por ojo):** | | | | |
| `esfera` | `number \| null` | DEVICE | `nullable\|numeric\|decimal:0,2\|between:-30,30` | Esfera objetiva del autorrefractómetro. |
| `cilindro` | `number \| null` | DEVICE | `nullable\|numeric\|decimal:0,2\|between:-30,30` | Si el dispositivo entrega convención plus-cyl (`> 0`), la IA lo transpone a minus-cyl para equipararlo a la Rx. |
| `eje` | `integer \| null` | DEVICE | `nullable\|integer\|between:0,180` | Eje refractivo objetivo del dispositivo. |
| `k1_d` | `number \| null` | DEVICE | `nullable\|numeric\|decimal:0,2\|between:25,80` | Potencia corneal meridiano plano en Dioptrías. |
| `k1_mm` | `number \| null` | DEVICE | `nullable\|numeric\|decimal:0,2\|between:4,12` | Radio de curvatura meridiano plano en milímetros. |
| `k1_eje` | `integer \| null` | DEVICE | `nullable\|integer\|between:0,180` | Eje del meridiano K1. |
| `k2_d` | `number \| null` | DEVICE | `nullable\|numeric\|decimal:0,2\|between:25,80` | Potencia corneal meridiano curvo en Dioptrías. |
| `k2_mm` | `number \| null` | DEVICE | `nullable\|numeric\|decimal:0,2\|between:4,12` | Radio de curvatura meridiano curvo en milímetros. |
| `k2_eje` | `integer \| null` | DEVICE | `nullable\|integer\|between:0,180` | Eje del meridiano K2. |
| `k_promedio_d` | `number \| null` | DEVICE | `nullable\|numeric\|decimal:0,2\|between:25,80` | Potencia corneal media `(k1_d + k2_d) / 2`. |
| `k_promedio_mm`| `number \| null` | DEVICE | `nullable\|numeric\|decimal:0,2\|between:4,12` | Radio corneal medio `(k1_mm + k2_mm) / 2`. |
| `k_cilindro` | `number \| null` | DEVICE | `nullable\|numeric\|decimal:0,2\|between:-30,30` | Astigmatismo corneal (diferencia dióptrica `k2_d - k1_d`). |
| `k_cilindro_eje`| `integer \| null` | DEVICE | `nullable\|integer\|between:0,180` | Eje del astigmatismo corneal. |

---

### 1.4 `clinica` (Extensión Clínica Optométrica)

Solo disponible para optometristas con permiso `recetas.clinica`. Si el usuario no tiene permiso o no activa la extensión, estos campos no viajan o viajan vacíos:

| Campo | Tipo JSON | Origen | Límite y Regla en SaaS | Catálogo, Presets y Formato Exacto |
|---|---|---|---|---|
| `uso_pantallas` | `string \| null` | DROPDOWN | `nullable\|in:lt2,btw2_6,gt6` | Catálogo cerrado estricto de 3 opciones:<br>• `'lt2'`: Menos de 2 horas diarias<br>• `'btw2_6'`: Entre 2 y 6 horas diarias<br>• `'gt6'`: Más de 6 horas diarias |
| `anexos_oculares` | `string \| null` | TEXTO | `nullable\|string\|max:255` | Evaluación de párpados, pestañas, conjuntiva y córnea anterior (blefaritis, pterigión, pingüécula, etc.). |
| `reflejos_pupilares` | `string \| null` | CHIP + TEXTO | `nullable\|string\|max:255` | Selección por chips + nota libre.<br>• Chip Normal: `"Reflejo fotomotor, consensual, acomodativo"` (con **n**)<br>• Chip Patológico: `"Marcus Gunn"` (dispara sospecha de DPAR)<br>• Composición: `"Opción"` o `"Opción: Nota adicional"`. Si no se toca en receta nueva, viaja `null`. |
| `motilidad_ocular` | `string \| null` | CONCAT | `nullable\|string\|max:255` | 4 campos de texto en UI: *Versiones*, *Ducciones*, *Movimientos sacádicos*, *Movimientos de seguimiento*. En Laravel se unen y `IaApiService` los aplana con espacios a una sola línea: `"Versiones: Suaves Ducciones: Completas Sacadicos: Precisos Seguimiento: Continuo"`. |
| `confrontacion_campos_visuales` | `string \| null` | PRESET + TEXTO | `nullable\|string\|max:255` | Texto libre. Botón **"Default"** inyecta exactamente la constante:<br>`"Sin defectos perifericos evidentes."` |
| `fondo_de_ojo` | `string \| null` | TEXTO | `nullable\|string\|max:255` | Texto libre describiendo papila, relación copa/disco (E/P), vasos y mácula. |
| `grid_de_amsler` | `string \| null` | PRESET + TEXTO | `nullable\|string\|max:255` | Texto libre. Botón **"SDPA"** inyecta exactamente la constante:<br>`"Sin descendencia de patologia aparente."` |
| `ojo_seco_but_seg` | `integer \| null` | DROPDOWN | `nullable\|integer\|min:1\|max:15` | Dropdown numérico de **1 a 15 segundos** (tiempo de ruptura lagrimal BUT). Umbrales: `< 5 s` crítico, `5..9 s` moderado/pantallas, `≥ 10 s` normal. |
| `cover_test` | `string \| null` | CONCAT | `nullable\|string\|max:255` | Radios independientes para OD y OI. Si no se tocan en receta nueva viaja `null`. Estructura serializada:<br>`"OD: <Tipo>[ y <Sub>] \| OI: <Tipo>[ y <Sub>]"`<br>• Tipos: `Orto`, `Endo`, `Exo`, `Hiper`, `Hipo`<br>• Subtipos (opcionales): `Tropia`, `Foria`<br>• Ejemplo con subtipo: `"OD: Endo y Tropia \| OI: Orto"`<br>• Ejemplo sin clasificar: `"OD: Exo \| OI: Orto"` |
| `ppc_cm` | `integer \| null` | DROPDOWN | `nullable\|integer\|min:1\|max:15` | Dropdown numérico de **1 a 15 centímetros** (Punto Próximo de Convergencia). |
| `recomendacion_seguimiento`| `string \| null` | PRESET + TEXTO | `nullable\|string\|max:60000` | Columna `TEXT` de hasta 60,000 caracteres. Dispone de dos botones presets en la UI:<br>• Botón *"Revisión gratuita"*: `"Se recomienda revision optometrica de seguimiento. Control incluido sin costo. Proxima cita en: "`<br>• Botón *"Revisión anual"*: `"Se recomienda revision optometrica anual de control. Proxima cita en: 12 meses "` |
| `impresion_clinica_plan` | `string \| null` | DESTINO | `nullable\|string\|max:60000` | **Es el campo de DESTINO donde la respuesta de la IA se escribe.** No se envía como insumo de entrada a la inferencia. |

---

### 1.5 `tipo_lente`

* **Tipo JSON:** `string`
* **Regla en SaaS:** `required|in:monofocal,bifocal_blended,progresivo,flat_top` (de `OpticaOptions::tiposLenteKeys()`).
* **Valores permitidos en el formulario:**
  1. `'monofocal'`: Monofocal (Valor por omisión en formulario nuevo).
  2. `'bifocal_blended'`: Bifocal blended (invisible sin línea divisoria).
  3. `'progresivo'`: Progresivo / multifocal continuo.
  4. `'flat_top'`: Bifocal de segmento visible flat-top (tratado como multifocal para justificar la adición).

---

### 1.6 Campos de la Receta que NUNCA viajan a la IA

La receta del SaaS gestiona el expediente y la venta integral en ópticas, pero `IaApiService::buildPayload()` filtra estrictamente para no enviar a la IA:
* **Datos del armazón:** `armazon_marca`, `armazon_modelo`, `armazon_color` (`max:100`).
* **Montaje de laboratorio:** `od_dnp`, `oi_dnp`, `od_altura_montaje`, `oi_altura_montaje` (`between:0,100`).
* **Árbol de materiales y tratamientos de micas:** `producto_id`, `material_matrix_id`, `selected_path_node_ids`, `free_materials` (CR-39, Policarbonato, Hi-Index, Ultra Hi), `free_treatments` (AR, BlueRay, Blanco W, Fotocromático, Polarizado, etc.).
* **Transacción y Cobro:** `precio_total`, `anticipo` (`decimal:0,2|min:0|max:99999999.99`).
* **Notas de taller y garantía:** `observaciones_laboratorio`, `observaciones_generales`, `garantia_texto` (`max:5000`).

---

## 2. Regla de Activación Clínica del Botón "Generar con IA"

Tanto Laravel (`IaApiService.php`) como la API (`clinical_data.py`) exigen que el payload contenga **datos clínicos reales** para proceder:

```php
$hasRefraccion = $this->hasAnyValue($payload['refraccion']['od'])
    || $this->hasAnyValue($payload['refraccion']['oi']);
$hasClinica = $this->hasAnyValue($payload['clinica']);

if (! $hasRefraccion && ! $hasClinica) {
    return null; // Laravel rechaza con 422: "El formulario no contiene datos clinicos suficientes..."
}
```

> **Regla para Generación de Payloads Ficticios:**
> Un payload que únicamente envíe el bloque `paciente` (edad, ocupación, motivo) SIN refracción ni pruebas clínicas **será rechazado inmediatamente con error HTTP 422**. Todo caso de prueba válido debe tener al menos una esfera, cilindro, o prueba clínica registrada. El valor `0.00` en esfera o cilindro es considerado un dato clínico válido (emétrope o sin astigmatismo).

---

## 3. Dinámica del Estado Derivado y Normalizaciones

1. **Protección contra normalidad inventada (`dirtyDerived`):**  
   En recetas nuevas, si el optometrista no hace clic en los chips de reflejos o en los radios de cover test, el valor se mantiene en `null`. **Un payload que no practicó el cover test debe llevar `"cover_test": null`**. Nunca se debe asumir `"OD: Orto | OI: Orto"` si la prueba no se realizó.
2. **Normalización de separadores en Cover Test:**  
   Si en algún registro legacy existió la notación `" - "` (ej. `"OD: Endo - Tropia"`), `IaApiService` la transforma a `" y "` (`"OD: Endo y Tropia"`).
3. **Aplanado de Motilidad Ocular:**  
   En base de datos los 4 subcampos se guardan con saltos de línea (`\n`). `IaApiService::normalizeSingleLineString` colapsa todos los saltos de línea y múltiples espacios a un solo espacio antes de emitir el JSON.
4. **Transposición de Cilindro Positivo en AKR:**  
   El autorrefractómetro físico puede estar configurado en convención plus-cyl (`+cyl`). Si `ia-api` detecta cilindro positivo en `akr.od` o `akr.oi`, aplica automáticamente la transposición óptica (`esf' = esf + cil`, `cil' = -cil`, `eje' = (eje + 90) % 180`) para que las correlaciones clínicas puedan compararlo limpiamente contra la refracción final en convención minus-cyl.

---

## 4. Estructura de Respuesta de la IA y Consumo en el SaaS

La API responde exitosamente con HTTP 200 y el siguiente esquema JSON exacto:

```json
{
  "status": "ok",
  "impresion_clinica": "El paciente de 45 años se presenta a consulta por fatiga visual...",
  "correlaciones_activadas": [
    "presbicia_multifocal",
    "ojo_seco_pantallas"
  ]
}
```

* **Consumo en Laravel:** Extrae `$response->json('impresion_clinica')`. Si es un string no vacío, lo asigna en tiempo real al componente Livewire:  
  `$this->form->clinica['impresion_clinica_plan'] = $resultado['impresion_clinica'];`
* **Manejo de Errores:** En caso de error (HTTP 401, 413, 422, 502, 503, 504), la API devuelve `{"detail": "Mensaje de error"}`. Laravel extrae dicho `detail` y lo muestra al optometrista en un banner de alerta para permitirle continuar la captura manual.

---

## 5. Golden Payload (Caso Ficticio Canónico 100% Válido)

Cualquier generador de pruebas, LLM o evaluador debe tomar esta estructura como referencia canónica:

```json
{
  "receta_id": "42",
  "paciente": {
    "edad": 48,
    "ocupacion": "Arquitecta de interiores",
    "motivo_consulta": "Vision borrosa de cerca, astenopia vespertina y sensacion de arenilla tras jornadas prolongadas frente a monitor CAD"
  },
  "refraccion": {
    "od": {
      "esfera": -2.25,
      "cilindro": -1.00,
      "eje": 180,
      "add": 1.75,
      "av_sc": "20/100",
      "av_cc": "20/20"
    },
    "oi": {
      "esfera": -2.00,
      "cilindro": -0.75,
      "eje": 175,
      "add": 1.75,
      "av_sc": "20/80",
      "av_cc": "20/20"
    }
  },
  "akr": {
    "ticket_id": 1,
    "taken_at": "2026-09-10 10:00:00",
    "pd": 63.5,
    "vd": 12.0,
    "ker_index": 1.3375,
    "od": {
      "esfera": -2.50,
      "cilindro": -1.00,
      "eje": 180,
      "k1_d": 42.50,
      "k1_mm": 7.94,
      "k1_eje": 180,
      "k2_d": 43.50,
      "k2_mm": 7.76,
      "k2_eje": 90,
      "k_promedio_d": 43.00,
      "k_promedio_mm": 7.85,
      "k_cilindro": -1.00,
      "k_cilindro_eje": 180
    },
    "oi": {
      "esfera": -2.25,
      "cilindro": -0.75,
      "eje": 175,
      "k1_d": 42.75,
      "k1_mm": 7.89,
      "k1_eje": 175,
      "k2_d": 43.50,
      "k2_mm": 7.76,
      "k2_eje": 85,
      "k_promedio_d": 43.12,
      "k_promedio_mm": 7.83,
      "k_cilindro": -0.75,
      "k_cilindro_eje": 175
    }
  },
  "clinica": {
    "uso_pantallas": "gt6",
    "anexos_oculares": "Bordes palpebrales con leve hiperemia conjuntival interpalpebral",
    "reflejos_pupilares": "Reflejo fotomotor, consensual, acomodativo",
    "motilidad_ocular": "Versiones: Suaves y completas Ducciones: Libres Sacadicos: Adecuados Seguimiento: Continuo",
    "confrontacion_campos_visuales": "Sin defectos perifericos evidentes.",
    "fondo_de_ojo": "Papilas rosadas de bordes nitidos, relacion copa/disco 0.3 bilateral, macula y retina aplicadas sin alteraciones vasculares",
    "grid_de_amsler": "Sin descendencia de patologia aparente.",
    "ojo_seco_but_seg": 6,
    "cover_test": "OD: Orto | OI: Orto",
    "ppc_cm": 8,
    "recomendacion_seguimiento": "Se recomienda revision optometrica anual de control. Proxima cita en: 12 meses "
  },
  "tipo_lente": "progresivo"
}
```
