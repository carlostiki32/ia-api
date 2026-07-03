# Verificación: las 41 correlaciones vs la investigación clínica

Objetivo: confirmar que la afinación al catálogo de datos del SaaS **no daña** el
disparo de ninguna correlación, y auditar si cada correlación está afinada para
dispararse exactamente como dicta [CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md)
(fuente de verdad clínica irrefutable). Regla aplicada: **la investigación manda; los
datos se adaptan al disparo, limitados por lo que el frontend puede enviar.**

Estado: **172 tests en verde.** Ninguna correlación cambió su umbral de disparo para
datos válidos del catálogo (convención negativa). Se corrigió una divergencia que había
introducido en `hipermetropia_alta` (ver §1) y se agregó cobertura para estados reales
del formulario que antes se ignoraban en silencio (ver §3).

---

## 1. Divergencia detectada y corregida (transposición de la Rx)

**Investigación §5.2 `hipermetropia_alta`:** el ejemplo `+1.00 esf / +8.00 cil` (EE +5.00)
debe **NO** disparar, porque la esfera (+1.00) está por debajo del piso de +3.00 D: es un
gran astígmata, no un hipermétrope alto.

**Lo que hice mal en la primera pasada:** transponía la Rx a convención negativa
(`+1.00/+8.00` → `+9.00/−8.00`), con lo que la esfera pasaba a +9.00 y **sí** disparaba.
Eso contradecía el ejemplo de la investigación.

**Corrección aplicada:** la Rx final **ya no se transpone**. Justificación clínica: el
dropdown del SaaS (`OpticaOptions::cilindro`) **solo emite cilindro negativo** (0.00…−8.00),
así que en producción no existe Rx en plus-cyl que transponer; transponerla solo rompía el
ejemplo de la investigación con datos legacy inexistentes. La transposición **se conserva
solo en el AKR** (lectura de dispositivo, cuya convención la fija el autorrefractómetro y sí
puede ser plus-cyl), donde protege la comparación esfera-a-esfera AR vs Rx de
`ar_rx_espasmo/cambio/variabilidad`. `abs()` en todas las demás lecturas del AKR hace que el
signo no afecte ningún otro disparo.

Resultado: el piso de esfera de `hipermetropia_alta` vuelve a comportarse **exactamente**
como §5.2. Cubierto por `test_hipermetropia_alta_no_dispara_por_astigmatismo_que_infla_el_ee`
y `test_graduacion_ojo_rx_no_se_transpone`.

---

## 2. Seguridad de cada cambio de datos vs el disparo de correlaciones

| Cambio en el schema | ¿Altera algún disparo con datos válidos del catálogo? | Por qué |
|---|---|---|
| Coerción tolerante (fuera de rango → `None`, no 422) | **No** | Un valor dentro del catálogo se comporta idéntico. Solo cambia el destino de valores corruptos: antes tumbaban todo con 422, ahora se descartan. Ninguna correlación dispara sobre `vd`, `ker_index`, `pd` (son metadata de prompt) |
| Eje normalizado módulo 180 | **No** (mejora) | El eje es cíclico; 0..180 pasa igual. Solo normaliza fuera de rango (225→45), que el SaaS **no valida**. `astig_oblicuo` evalúa el eje correcto en vez de recibir un 422 |
| Transposición **solo del AKR** | **No** | Preserva EE (`esf+cil/2` es invariante a la transposición). En producción el AKR real es minus-cyl y es no-op; con AKR plus-cyl alinea la comparación AR-vs-Rx. No toca la Rx (§1) |
| `add ≤ 0` → `None` | **Corrige un bug** | `add=0` tecleada NO es adición prescrita. Antes disparaba `presbicia_multifocal` y suprimía `presbicia_sin_adicion` (§12.1/§12.4). Ahora ambas operan como dicta la investigación |
| Esfera fuera de ±20.00 / cilindro fuera de \|8.00\| → `None` | **No** | Son los límites del dropdown; dentro del catálogo pasa igual. Fuera = dato corrupto que no debe contar como hallazgo |
| `flat_top` cuenta como multifocal | **Corrige una omisión** | `flat_top` es un bifocal de segmento (§12.1 "bifocal"). Antes se trataba como monofocal: no justificaba la add y disparaba en falso `presbicia_sin_adicion` |
| `TIPO_LENTE_MAP` en el prompt | **No** | Solo cambia la etiqueta legible que ve el LLM; no toca ninguna condición |
| Cover test estructurado (tipo sin sub) | **Solo agrega** | Ver §3. No modifica el path de keywords existente; añade disparo para estados que antes se perdían |

**Invariante clave verificado:** para el contrato real del SaaS (cilindro siempre ≤ 0,
enums cerrados, dropdowns 1..15), **todos los umbrales de la investigación se alcanzan y
ninguna condición de disparo cambió.**

---

## 3. Cover test: estado real del formulario que antes se ignoraba

**Hallazgo estructural:** la UI del cover test (`clinica.blade.php`) tiene el sub
(`Tropia`/`Foria`) como **radios SIN default**. El optometrista puede elegir
`Endo/Exo/Hiper/Hipo` y **dejar el sub sin marcar**. El SaaS entonces compone, p. ej.,
`"OD: Exo | OI: Orto"`. Las keywords unidas de la investigación (`exoforia`, `exotropia`,
`hiperforia`…) **no ven** ese `Exo` suelto → el dato de dropdown se perdía en silencio.

**Afinación (fiel a la jerarquía de la investigación §10):** un tipo sin clasificar se
trata como *desviación documentada que amerita mención*, nunca como tropía manifiesta:

| Estado del dropdown | Correlación que dispara | Fidelidad a la investigación |
|---|---|---|
| `Exo` sin sub | `ppc_exoforia` con texto "exodesviación no clasificada (conviene precisar foria o tropia)" | §10.2 activa con exoforia; se elige la correlación **más leve** y se pide clasificar. NO dispara `exotropia_lente` (que exige "exotropia" explícita) |
| `Endo` sin sub + síntoma binocular | `cover_endoforia_sintomatica` con "endodesviación no clasificada" | §10.4; excluye endotropia. NO dispara `endotropia_lente` |
| `Hiper`/`Hipo` sin sub | `desviacion_vertical` con "desviación vertical no clasificada" | §10.5; usa el cierre genérico (no el de tropía manifiesta) |
| `Orto` / `Orto` (default) | nada | Estado por defecto; no genera falso positivo |

**Por qué es conservador y correcto:** `insuficiencia_convergencia` (§10.1, compuesta de
alta confianza) y los `*_lente`/factor-tropía de `ambliopia_sospecha` **siguen exigiendo la
clasificación explícita** (`exoforia`/`exotropia`/`endotropia` con sub). Un dato ambiguo
nunca escala a un diagnóstico manifiesto; solo se menciona y se pide precisar. Cubierto por
5 tests nuevos (`test_cover_exo_sin_clasificar_*`, `test_cover_orto_ambos_ojos_no_dispara_*`,
`test_cover_endo_sin_clasificar_no_dispara_endotropia_lente`).

---

## 4. Auditoría correlación por correlación (condición del código vs investigación)

`OK` = el código dispara exactamente como la investigación. Todas verificadas contra el
código leído y los tests golden.

### Fondo de ojo (8)
| # | Correlación | Condición investigación | Código | Estado |
|---|---|---|---|---|
| 4.1 | `fondo_periferico_riesgo` | keywords periféricas + negación; urgente | `_KEYWORDS_FONDO_PERIFERICO` + ventana negación | OK |
| 4.2 | `glaucoma_asimetrico` | DPAR/Marcus Gunn **y** keyword glaucomatosa; suprime pupilas y glaucomatoso | idéntico; `@memoize` compartido | OK |
| 4.3 | `fondo_glaucomatoso` | C/D 0.6–0.9, notch, ISNT…; suprimida por asimétrico | idéntico | OK |
| 4.4 | `papila_patologica` | palidez/atrofia (base) + edema/papiledema (urgente) | dos variantes de texto | OK |
| 4.5 | `fondo_macular_dmae` | drusas, EPR, neovascularización | `_KEYWORDS_FONDO_DMAE` | OK |
| 4.6 | `fondo_macular_otros` | MER, agujero, CSC | `_KEYWORDS_FONDO_MACULAR_OTROS` | OK |
| 4.7 | `fondo_hipertensivo` | cruces AV, llama, cotton wool | `_KEYWORDS_FONDO_HIPERTENSIVO` | OK |
| 4.8 | `fondo_vascular_diabetico` | microaneurismas, RDNP; suprimida por 4.1/4.3/4.5/4.6, **no** por hipertensivo | idéntico | OK |

### Refracción final (5)
| # | Correlación | Condición investigación | Código | Estado |
|---|---|---|---|---|
| 5.1 | `miopia_magna` | EE ≤ −6.00 (muy alta ≤ −8.00) | `ee <= -6.00` / `-8.00` | OK |
| 5.2 | `hipermetropia_alta` | EE ≥ +5.00 **y** esfera ≥ +3.00 | `_HIPERMETROPIA_EE_MIN/ESFERA_MIN`; Rx sin transponer (§1) | OK (corregido) |
| 5.3 | `anisometropia` | \|ΔEE\| > 1.00; leve/moderada/severa; antimetropía | idéntico; modula por edad ≤ 8 | OK |
| 5.4 | `astig_oblicuo` | \|cil\| > 2.00 **y** eje 20–70/110–160; K solo confirma | idéntico; eje ya normalizado mod 180 | OK |
| 5.5 | `av_cc_limitada` | denominador Snellen > 25 | `_AV_DENOM_LIMITE=25`; parser pie/métrica/decimal | OK |

### AR/queratometría vs Rx (4)
| # | Correlación | Condición investigación | Código | Estado |
|---|---|---|---|---|
| 6.1 | `ar_rx_espasmo_acomodativo` | edad<40, pantallas, esf_rx−esf_ar ≥ 0.50 | idéntico | OK |
| 6.2 | `ar_rx_cambio_cristalino` | edad≥55, \|Δesf\|>1.00, sin irregularidad corneal | idéntico | OK |
| 6.3 | `ar_rx_variabilidad_inespecifica` | Δ ≥ 1.50 en esf o cil; red de seguridad | `_UMBRAL_VARIABILIDAD_D=1.50` | OK |
| 6.4 | `ar_detecta_astigmatismo_no_prescrito` | \|cil_ar\|≥0.75, cil_rx nulo/<0.50, K soporta | idéntico | OK |

### Córnea disparadora (2)
| # | Correlación | Condición investigación | Código | Estado |
|---|---|---|---|---|
| 6b.1 | `queratocono_ectasia_sospecha` | Kmax≥48.70, o ≥47.20+cil≥1.50, o cil≥4.00 | `_keratometry_suggests_corneal_irregularity` | OK |
| 6b.2 | `astigmatismo_corneal_vs_refractivo` | cil_rx≥0.75 + Δmagnitud≥1.25 o Δeje≥15 (ambos≥1.00) | idéntico | OK |

### Anexos/cristalino, pupilas/motilidad, campos/Amsler (6)
| # | Correlación | Condición investigación | Código | Estado |
|---|---|---|---|---|
| 7.1 | `anexos_patologicos` | keywords anexos + negación + dedupe | `_KEYWORDS_ANEXOS` | OK |
| 7.2 | `opacidad_cristaliniana` | anexos+fondo concatenados; catarata/IOL/afaquia | idéntico | OK |
| 8.1 | `pupilas_alteradas` | anisocoria/DPAR…; excluye fisiológica y farmacológica; suprimida por asimétrico | idéntico | OK |
| 8.2 | `motilidad_alterada` | limitación/nistagmo/paresia + negación | `_KEYWORDS_MOTILIDAD` | OK |
| 9.1 | `campos_visuales_alterados` | escotoma/hemianopsia + negación por oración | idéntico | OK |
| 9.2 | `amsler_alterado` | metamorfopsia/distorsión + negación por oración | idéntico | OK |

### Binocularidad (7)
| # | Correlación | Condición investigación | Código | Estado |
|---|---|---|---|---|
| 10.1 | `insuficiencia_convergencia` | PPC alejado (umbral por edad) + **exoforia** + demanda próxima; suprime 10.2/10.3 | idéntico; exige "exoforia" explícita | OK |
| 10.2 | `ppc_exoforia` | PPC alejado **o** exoforia | + `Exo` sin sub (§3) | OK (ampliado) |
| 10.3 | `cover_exoforia_sintomatica` | exoforia + síntoma binocular; suprimida por 10.1 | idéntico | OK |
| 10.4 | `cover_endoforia_sintomatica` | endoforia (no endotropia) + síntoma | + `Endo` sin sub (§3) | OK (ampliado) |
| 10.5 | `desviacion_vertical` | hiper/hipo foria o tropia | + `Hiper`/`Hipo` sin sub (§3) | OK (ampliado) |
| 10.6 | `endotropia_lente` | endotropia + tipo_lente | exige "endotropia" explícita | OK |
| 10.7 | `exotropia_lente` | exotropia + tipo_lente | exige "exotropia" explícita | OK |

Umbral de PPC por edad verificado: `>6 cm` si edad<40, `>10 cm` si ≥40/desconocida
(`_PPC_UMBRAL_JOVEN_CM/PRESBITA_CM`). Alcanzable en el dropdown 1..15. OK.

### Superficie ocular (3)
| # | Correlación | Condición investigación | Código | Estado |
|---|---|---|---|---|
| 11.1 | `but_critico` | BUT < 5 | `but < 5` | OK |
| 11.2 | `but_pantallas` | 5≤BUT≤9 **y** pantallas btw2_6/gt6 | idéntico | OK |
| 11.3 | `but_limitrofe` | 5≤BUT≤9 **y** pantallas nulo/lt2 | idéntico | OK |

Dropdown BUT 1..15 cubre los tres rangos (<5, 5–9, ≥10). OK.

### Edad/lente/pantallas (6)
| # | Correlación | Condición investigación | Código | Estado |
|---|---|---|---|---|
| 12.1 | `presbicia_multifocal` | (multifocal **y** (edad≥40 o add)) o (edad≥40 **y** add) | idéntico; `flat_top`∈multifocal | OK |
| 12.2 | `cvs_sospecha` | pantallas btw2_6/gt6 + síntoma en motivo | idéntico | OK |
| 12.3 | `adulto_mayor_screening` | edad≥60 + AV limitada, sin causa orgánica ni ambliopía | idéntico | OK |
| 12.4 | `presbicia_sin_adicion` | edad≥45, Rx distancia, sin add, no multifocal, EE menos miope > −1.50 | idéntico; `add=0`→None lo respeta | OK |
| 12.5 | `adicion_incongruente_edad` | add en <40 (≥0.75) o sobre techo por edad (+0.50) | idéntico | OK |
| 12.6 | `ambliopia_sospecha` | AV limitada + (anisometropía o **tropía**) sin causa orgánica | idéntico; tropía exige sub explícito | OK |

**Resultado de la auditoría: 41/41 correlaciones disparan como dicta la investigación.**
Las 3 marcadas "ampliado" solo agregan cobertura para estados del formulario que antes se
perdían (dropdown sin sub), sin alterar el disparo ya existente.

---

## 5. Fireabilidad desde el frontend (¿el payload permite el disparo?)

Verificado que **cada** correlación es disparable con los datos que el SaaS puede enviar:

- **C/D glaucomatosa, keywords de fondo/anexos/motilidad/campos/Amsler**: `fondo_de_ojo`,
  `anexos_oculares`, etc. son texto libre (máx 255) → el optometrista escribe el término.
- **DPAR**: chip "Marcus Gunn" o nota libre en `reflejos_pupilares`.
- **Cover test**: dropdown canónico, incluido el caso sin sub (§3).
- **PPC/BUT**: dropdowns 1..15, cubren todos los umbrales.
- **Uso de pantallas**: enum cerrado exacto.
- **Refracción/AV/add/tipo_lente/edad**: dropdowns y catálogos cerrados.

No hay ninguna correlación que quede "muerta" por límites del payload.

---

## 6. Documentación sincronizada con el código

Toda la documentación se actualizó al contrato actual (**coerción tolerante** + eje mod 180 +
transposición solo-AKR + catálogo `monofocal|bifocal_blended|progresivo|flat_top` con
`flat_top` multifocal + cover test con sub opcional):

- **CORRELACIONES_CLINICAS.md §2** (tabla de contrato) y §10/§12.1 (cover sin sub, flat_top).
- **PIPELINE_LLM.md §4** (schema), §6 (parser de cover) y §8 (mapeo `TIPO_LENTE`).
- **README.md** (validación por coerción y códigos de error).
- El detalle completo del catálogo del SaaS y el mapeo campo→correlación está en
  [DICCIONARIO_DATOS_RECETA.md](DICCIONARIO_DATOS_RECETA.md).

## 7. Conclusión

1. La afinación al catálogo **no daña** ninguna de las 41 correlaciones: para datos válidos
   del contrato del SaaS, todos los umbrales de la investigación se conservan intactos.
2. Se **corrigió** la única divergencia real que introduje (transposición de la Rx vs el
   ejemplo de §5.2) restringiendo la transposición al AKR.
3. Se **recuperaron** 3 disparos que el payload permitía pero el código ignoraba (cover test
   con tipo sin clasificar), siempre por debajo del umbral de "tropía manifiesta" para no
   sobre-diagnosticar.
4. Auditoría 41/41: cada correlación dispara como dicta la investigación clínica. 172 tests
   en verde.
