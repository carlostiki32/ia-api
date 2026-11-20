# Diccionario de Datos de la Receta (SaaS `opt`) — Especificación de Catálogo para IA-API

> ## ESPECIFICACIÓN NORMATIVA DE INTEGRACIÓN
> 
> **ESTE DOCUMENTO DEFINE LA ESPECIFICACIÓN TÉCNICA Y DE CATÁLOGO** sobre la estructura, tipos de datos, límites, catálogos, presets de interfaz y reglas de validación de los datos que el SaaS de optometría (`opt`) construye y envía a esta API (`ia-api`).
> 
> 1. **Fidelidad al Catálogo:** Ningún modelo o evaluador debe asumir rangos o límites diferentes a los aquí expresados. La lógica del backend del SaaS y los esquemas de persistencia delimitan el dominio de entrada.
> 2. **Consistencia de Payloads de Prueba:** Los casos de prueba sintéticos deben reflejar los catálogos y límites de este documento para evaluar el comportamiento representativo de la herramienta en consulta real.
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

### 1.0 Opción de salida

`salida_version` es `string` tipado con valores `clinica-v1` (default al omitir)
y `clinica-paciente-v1`; nulo o cualquier otra versión produce 422. La opción no
cambia los campos clínicos de entrada. En dual, ESF/CIL representan la receta
final de lejos. Explicar la graduación requiere ESF/CIL explícitos de ambos ojos;
la explicación de hallazgos documentados puede generarse sin ese perfil completo.
Cero es un dato válido, nulo es ausencia y AKR no lo reemplaza. No se agrega una
bandera de confirmación/guardado ni una obligación de guardar antes de generar.
La aprobación y las ediciones ocurren en Óptica sin invocar la API al Guardar.
El contrato dual completo está en [SALIDA_DUAL.md](SALIDA_DUAL.md).

### 1.1 `paciente` (Contexto Clínico Anonimizado)

Laravel extrae los datos de `paciente`, omite cualquier dato identificativo (PII) y despacha únicamente:

| Campo | Tipo JSON | Origen | Límite y Regla en SaaS | Notas y Comportamiento Clínico |
|---|---|---|---|---|
| `edad` | `integer \| null` | CALC | Entero `≥ 0` y `≤ 125` | Calculado en Laravel mediante `Carbon::parse(fecha_nacimiento)->age`. En Laravel `fecha_nacimiento` se valida con `after_or_equal:1900-01-01\|before_or_equal:today`. La fecha exacta NUNCA viaja. |
| `ocupacion` | `string \| null` | TEXTO | `required\|string\|max:120` | **Tope exacto: 120 caracteres** (NO 255). Contexto clínico registrado; no confirma presbicia ni es fuente de la explicación refractiva para paciente. |
| `motivo_consulta` | `string \| null` | TEXTO | `required\|string\|max:1000` | **Tope exacto: 1000 caracteres** (NO 255). Admite descripciones detalladas de astenopía, cefalea o pérdida visual. |

*Datos del paciente que NUNCA viajan a la IA:* `nombre` (`string|max:255`), `telefono` (`string|max:50`), `fecha_nacimiento` original (`date`), dirección, correo o identificaciones fiscales.

---

### 1.2 `refraccion.od` / `refraccion.oi` (Refracción Subjetiva Final)

Ambos ojos poseen idéntica estructura y reglas:

| Campo | Tipo JSON | Origen | Límite y Regla en SaaS | Catálogo en UI / Comportamiento |
|---|---|---|---|---|
| `esfera` | `number \| null` | DROPDOWN | `nullable\|numeric\|decimal:0,2\|between:-30,30` | Dropdown de **+20.00 a -20.00 D en pasos de 0.25** (161 opciones exactas generadas por `OpticaOptions::esfera()`). Default en creación: `0.00`. Rango de BD admite hasta ±30.00 D para alta miopía y afaquia extrema. |
| `cilindro` | `number \| null` | DROPDOWN | `nullable\|numeric\|decimal:0,2\|between:-30,30` | Dropdown de **0.00 a -8.00 D en pasos de 0.25** (33 opciones en `OpticaOptions::cilindro()`). Siempre convención negativa (`≤ 0.00`). Default en creación: `0.00`. |
| `eje` | `integer \| null` | NUM LIBRE | `nullable\|integer\|between:0,180` | **Validado formalmente entre 0 y 180 grados**. Pydantic conserva valores de 0 a 180; valores atípicos se normalizan módulo 180. Un eje nulo permanece nulo; no se necesita para nombrar los componentes educativos. |
| `add` | `number \| null` | NUM LIBRE | `nullable\|numeric\|decimal:0,2\|between:0,30` | Entrada numérica con `step="0.25"`. El SaaS prohíbe negativos (`between:0,30`). Clínicamente oscila entre `+0.75` y `+3.50` D. Si llega `≤ 0.00` o `> 30.00`, la IA lo coerciona a `None` (sin adición). |
| `av_sc` | `string \| null` | DROPDOWN | `nullable\|string\|max:20` | Catálogo cerrado Snellen en pies (`OpticaOptions::av()`): `""` (vacío/guion), `20/10`, `20/15`, `20/20`, `20/25`, `20/30`, `20/40`, `20/50`, `20/60`, `20/70`, `20/80`, `20/100`, `20/120`, `20/160`, `20/200`, `20/400`, `20/600`. |
| `av_cc` | `string \| null` | DROPDOWN | `nullable\|string\|max:20` | Mismo catálogo exacto de 16 valores Snellen de `av_sc`. |

La API descarta ESF/CIL fuera de ±30.00 D. Si recibe cilindro positivo,
también transpone la Rx final a cilindro negativo, conservando esfera o eje
nulos cuando falten. El eje transpuesto usa `((eje + 90) % 180) or 180`;
la esfera resultante vuelve a comprobarse contra el rango permitido.

*Campos de graduación que NO viajan a la IA:* `dnp` (`decimal:0,2|between:0,100`), `altura_montaje` (`decimal:0,2|between:0,100`).

---

### 1.3 `akr` (Snapshot de Autorrefractómetro y Queratometría)

Lectura capturada automáticamente por el hardware óptico o cargada desde un ticket previo:

| Campo | Tipo JSON | Origen | Límite y Regla en SaaS | Notas y Formato |
|---|---|---|---|---|
| `ticket_id` | `integer \| null` | DEVICE | `nullable\|integer\|exists:akr_tickets,id` | ID del ticket original en BD (solo trazabilidad). |
| `taken_at` | `string \| null` | DEVICE | `nullable\|date\|after_or_equal:1970-01-02\|before_or_equal:2038-01-18` | Fecha/hora ISO/SQL (`Y-m-d H:i:s`) de captura. Pydantic lo modela y normaliza; participa en la clave del payload y no acredita identidad temporal entre receta y AKR. |
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

La API normaliza los textos clínicos conservando límites de línea y colapsando
espacios dentro de cada línea; los trunca a 500 caracteres, salvo
`recomendacion_seguimiento`, cuyo límite es 60000. Son límites de recepción de
`app/schemas.py`; los máximos de captura del SaaS siguen siendo los de la tabla.

### 1.5 `tipo_lente`

* **Tipo JSON:** `string`
* **Regla en SaaS:** `required|in:monofocal,bifocal_blended,progresivo,flat_top` (de `OpticaOptions::tiposLenteKeys()`).
* **Valores permitidos en el formulario:**
  1. `'monofocal'`: Monofocal (Valor por omisión en formulario nuevo).
  2. `'bifocal_blended'`: Bifocal blended (invisible sin línea divisoria).
  3. `'progresivo'`: Progresivo / multifocal continuo.
  4. `'flat_top'`: Bifocal de segmento visible flat-top (tratado como multifocal para justificar la adición).

---

En la explicación para paciente solo se admite la descripción CPU de cada diseño
en `app/paciente/contexto.py`. Monofocal no determina uso de lejos o cerca;
la regla `lente` rechaza atribuirle esas distancias o lectura en la misma frase.
Los efectos de la graduación y la ayuda de los lentes requieren respaldo en los
hechos del caso, sin deducir adaptación, materiales ni tratamientos.

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
> Un payload que únicamente envíe el bloque `paciente` (edad, ocupación, motivo) SIN refracción ni pruebas clínicas **será rechazado inmediatamente con error HTTP 422**. Todo caso de prueba válido debe tener al menos un valor en refracción, en `akr.od`/`akr.oi` o en clínica. La metadata AKR sola (`ticket_id`, `taken_at`, `pd`, `vd`, `ker_index`) no satisface `has_clinical_data`. El valor `0.00` en esfera o cilindro es un dato explícito válido; por sí solo no acredita normalidad del examen.

---

## 3. Dinámica del Estado Derivado y Normalizaciones

1. **Protección contra normalidad inventada (`dirtyDerived`):**  
   En recetas nuevas, si el optometrista no hace clic en los chips de reflejos o en los radios de cover test, el valor se mantiene en `null`. **Un payload que no practicó el cover test debe llevar `"cover_test": null`**. Nunca se debe asumir `"OD: Orto | OI: Orto"` si la prueba no se realizó.
2. **Normalización de separadores en Cover Test:**  
   Si en algún registro legacy existió la notación `" - "` (ej. `"OD: Endo - Tropia"`), `IaApiService` la transforma a `" y "` (`"OD: Endo y Tropia"`).
3. **Aplanado de Motilidad Ocular:**  
   En base de datos los 4 subcampos se guardan con saltos de línea (`\n`). `IaApiService::normalizeSingleLineString` colapsa todos los saltos de línea y múltiples espacios a un solo espacio antes de emitir el JSON.
4. **Transposición de Cilindro Positivo en AKR:**  
   El autorrefractómetro físico puede estar configurado en convención plus-cyl (`+cyl`). Si `ia-api` detecta cilindro positivo en `akr.od` o `akr.oi`, aplica automáticamente la transposición óptica (`esf' = esf + cil`, `cil' = -cil`, `eje' = ((eje + 90) % 180) or 180`) para que las correlaciones clínicas puedan compararlo limpiamente contra la refracción final en convención minus-cyl.

---

## 4. Estructura de Respuesta de la IA y Consumo en el SaaS

El ejemplo siguiente corresponde a `clinica-v1`. La respuesta dual añade
`explicacion_paciente`, `explicacion_paciente_estado`, `salida_version`, `cached`
booleano y `generacion` con origen/modelo/versiones/hash. El campo clínico válido
se conserva si falla solo el educativo, con respaldo determinista `plantilla`
tras redacción y verificación opcionales de la explicación. Si no hay plantilla
ni acciones, la explicación puede ser nula con el estado del perfil;
un fallo de ensamblado devuelve `rechazada` y motivo `error`.
`PACIENTE_LLM_HABILITADO=false` omite ambas llamadas del paciente y su prosa
cacheada; entrega respaldo CPU con motivo nulo salvo fallo de ensamblado. Detalles y excepción urgente sin origen LLM en
[SALIDA_DUAL.md](SALIDA_DUAL.md). Los textos generados/corregidos y la metadata
de revisión son **destinos**, nunca insumos para la siguiente inferencia.

La API responde exitosamente con HTTP 200 y el siguiente esquema JSON exacto:

```json
{
  "status": "ok",
  "impresion_clinica": "El paciente de 45 años se presenta a consulta por fatiga visual...",
  "correlaciones_activadas": [
    "but_pantallas"
  ]
}
```

* **Consumo en Laravel:** Extrae `$response->json('impresion_clinica')`. Si es un string no vacío, lo asigna en tiempo real al componente Livewire:  
  `$this->form->clinica['impresion_clinica_plan'] = $resultado['impresion_clinica'];`
* **Manejo de Errores:** Los errores HTTP 401, 413, 500, 502, 503 y 504 devuelven `{"detail": "Mensaje de error"}`. Un 422 por validación estructural de FastAPI/Pydantic lleva una lista en `detail`; el rechazo por falta de datos clínicos lleva un mensaje. Laravel extrae dicho `detail` y lo muestra al optometrista en un banner de alerta para permitirle continuar la captura manual.

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

## 6. Contrato `seguimiento-whatsapp-v2`

`POST /v1/inferencia/seguimiento-whatsapp`, con la misma autenticación Bearer
que el endpoint clínico. HTTP 200 para solicitudes válidas, incluido el respaldo;
401 sin token válido; 500 sin API_KEY configurada; 422 para solicitudes inválidas.

Este contrato no modifica el payload clínico de las secciones 0–5.
Laravel envía únicamente adultos con edad conocida y estado próximo o vencido;
no se deducen patologías ni presbicia de la ADD.

### Request
 (`extra="forbid"`; todos los campos son obligatorios salvo que diga «opcional»)

```json
{
  "contrato_version": "seguimiento-whatsapp-v2",
  "paciente_ref": "3f9a1c0b7d2e4a51",
  "tramo_edad": "18_39",
  "estado_seguimiento": "proximo",
  "meses_desde_ultima_receta": 11,
  "recetas_previas": 2,
  "costo": "incluida",
  "ya_notificado_en_ciclo": false,
  "variante": 0,
  "rx_lejos": {"od": {"esfera": -2.25, "cilindro": -0.5, "add": null},
               "oi": {"esfera": -2.0, "cilindro": 0.0, "add": null}},
  "tipo_lente": "monofocal",
  "uso_pantallas": "gt6",
  "usa_armazon": null,
  "contexto_uso": {
    "ocupacion": "Estudiante",
    "motivo_consulta": "Revisión anual",
    "impresion_clinica": null,
    "explicacion_paciente": null,
    "observaciones_receta": null,
    "recomendacion_seguimiento": null
  },
  "fecha_revision": "2026-12-15",
  "meses_periodo": 12
}
```

| Campo | Tipo / valores | Origen en Laravel |
|---|---|---|
| `contrato_version` | literal `"seguimiento-whatsapp-v2"` | constante |
| `paciente_ref` | string `^[a-f0-9]{16}$` | `substr(hash_hmac('sha256', tenant_id.':'.paciente_id, config('app.key')), 0, 16)`; solo para correlacionar logs |
| `tramo_edad` | `"18_39"` \| `"40_59"` \| `"60_mas"` | edad a hoy desde `pacientes.fecha_nacimiento`. **Menores y edad desconocida nunca se envían** (Laravel usa el genérico) |
| `estado_seguimiento` | `"proximo"` \| `"vencido"` | `PacienteSeguimientoEstado` del paciente (los demás estados nunca se envían) |
| `meses_desde_ultima_receta` | int 0..600 \| null | meses completos entre `fecha_receta` de la última receta y hoy; null si no hay recetas |
| `recetas_previas` | int 0..1000 | número de recetas del paciente (tenant) |
| `costo` | `"incluida"` \| `"con_costo"` | `pacientes.proxima_evaluacion_con_costo` (true → `con_costo`) |
| `ya_notificado_en_ciclo` | bool | `pacientes.seguimiento_notificado_at !== null` |
| `variante` | int 0..1000 | 0 al abrir el diálogo; «Regenerar con IA» manda un valor nuevo 1..1000 |
| `rx_lejos` | objeto \| null | graduaciones OD/OI (`esfera`, `cilindro`, `add`, como float o null) de la **última receta** (`fecha_receta` desc, `id` desc). null si esa receta no tiene filas de graduación. Si falta una fila, ese ojo va con los tres valores null |
| `tipo_lente` | `"monofocal"` \| `"bifocal"` \| `"progresivo"` \| `"otro"` \| null | `recetas.tipo_lente` de **la misma receta** |
| `uso_pantallas` | `"lt2"` \| `"btw2_6"` \| `"gt6"` \| null | `receta_clinicas.uso_pantallas` de **la misma receta** |
| `usa_armazon` | bool \| null | **v2: Laravel siempre manda null** (el dato no existe de forma confiable; el catálogo §6.6 lo exige). ia-api acepta true/false/null |
| `contexto_uso` | objeto \| null | contexto cualitativo anonimizado (`extra="forbid"`): `ocupacion` (≤120), `motivo_consulta` (≤1000), `impresion_clinica` (≤1500), `explicacion_paciente` (≤1500), `observaciones_receta` (≤1500), `recomendacion_seguimiento` (≤1500). Cadenas vacías se normalizan a null. |
| `fecha_revision` | `date` \| null | fecha sugerida para la revisión (solo con `estado=proximo`; con `vencido` debe ser null) |
| `meses_periodo` | int 3..60 \| null | meses del periodo indicado para la revisión (solo con `estado=proximo`; con `vencido` debe ser null) |

Nunca viajan: nombre, teléfono, folio, fechas de nacimiento exactas, notas privadas, correlaciones, patologías, AKR, eje, agudeza visual.

ia-api normaliza `rx_lejos` con la misma lógica ya auditada de la Rx (rangos, transposición de cilindro positivo, `add <= 0` o `add > 30` = sin adición): reutiliza `app.schemas.Refraccion`/`GraduacionOjo`.


### Respuesta, estados y motivos


```json
{
  "status": "ok",
  "contrato_version": "seguimiento-whatsapp-v2",
  "estado": "generada",
  "mensaje": "<apertura>\n\n<frase_uso>\n\n<frase_fecha>\n\n<hecho>\n\n<cierre>\n\nSi prefiere no recibir estos mensajes, solo díganoslo.",
  "partes": {
    "apertura": "...",
    "apertura_id": null,
    "frase_uso": "...",
    "frase_fecha": "...",
    "hechos": ["progresivo_zonas"],
    "cierre": "...",
    "cierre_id": "CI_INC_1",
    "baja": "Si prefiere no recibir estos mensajes, solo díganoslo."
  },
  "motivo": null,
  "hechos_elegibles": ["progresivo_zonas"],
  "generacion": {
    "origen": "llm",
    "modelo": "qwen3.5:9b",
    "catalogo_version": "v2-borrador-2026-11-20",
    "prompt_version": "seguimiento-whatsapp-prompt-v3",
    "base_hash_api": "<64 hex>",
    "cached": false
  },
  "uso_lentes": "estudiar",
  "origen_uso": "llm"
}
```

Reglas:
- `estado`: `"generada"` (Qwen redactó apertura, seleccionó hechos [0–1] y cierre de catálogo; pasó validador y verificación) o `"plantilla"` (mensaje 100 % del catálogo armado por el servidor).
- `generacion.origen`: `"llm"` si `estado="generada"`; `"catalogo"` si `estado="plantilla"`. `modelo` es string con `origen="llm"` y null con `"catalogo"`.
- `motivo`: null si `generada`; si `plantilla`, uno de: `ia_ocupada`, `ia_timeout`, `ollama_error`, `json_invalido`, `validacion:<regla>`, `verificacion`, `presupuesto` o `ia_deshabilitada` (ia-api con `SEGUIMIENTO_LLM_HABILITADO=false`).
- `mensaje` = partes no vacías unidas con `\n\n` en el orden: `apertura` → `frase_uso` → `frase_fecha` → `hechos` (0–1) → `cierre` → `baja`. Longitud 60–140 palabras (sin la baja), ≤ 2000 caracteres.
- `partes.hechos`: lista de 0 a 1 hechos conservados.
- `hechos_elegibles`: lista de hechos elegibles según el catálogo v2.
- `mensaje` contiene **exactamente una vez** `:paciente` y **exactamente una vez** `:clinica`, ambos dentro de `apertura`. La apertura no contiene «¿» ni «?». El cierre contiene exactamente un «¿» y un «?».
- `generacion.base_hash_api`: sha256 hex (64) de la clave de caché del request (`contexto_uso` entra solo como su sha256, nunca en claro).
- `cached`: true si salió de la caché de ia-api (solo se cachean respuestas `generada`).
- `uso_lentes`: etiqueta de uso clasificada por la etapa `uso` o por reglas deterministas.
- `origen_uso`: `"llm"` si provino de la etapa `uso`; `"reglas"` si provino de reglas deterministas.

Laravel valida esta forma de manera estricta; cualquier desviación → mensaje genérico local con motivo `respuesta_invalida`.


### Versiones, respaldo y fixtures compartidos

- Catálogo: `v2-borrador-2026-11-20`.
- Redacción: `seguimiento-whatsapp-prompt-v3`.
- Verificación: `seguimiento-verificacion-v1`.
- Uso: `seguimiento-uso-v1`.
- Contrato: `seguimiento-whatsapp-v2`.

Los fixtures normativos están en `tests/fixtures/seguimiento_whatsapp/`: `g1-request.json`, `g2-request.json`, `g3-request.json`, las respuestas `gN-respuesta-plantilla.json`, `g1-modelo-uso.json`, `g1-modelo-redaccion.json`, `modelo-verificacion-false.json` y `g1-respuesta-generada.json`. `sha256.json` fija sus hashes.

El respaldo usa textos literales del catálogo con rotación determinista por sha256. No se cachea. La respuesta generada pasa validación determinista y verificación de apertura, y se cachea en memoria con LRU + TTL. La clave excluye `paciente_ref` y anonimiza `contexto_uso` como sha256.

Laravel sustituye `:paciente` y `:clinica` una sola vez al mostrar o aprobar; ia-api nunca recibe los nombres ni abre WhatsApp. La prosa completa se revisa antes de que el operador acepte. Logs de seguimiento sin contenido ni textos clínicos de `contexto_uso`.
