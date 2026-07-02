# Correlaciones clínicas — guía definitiva (código + fundamento clínico)

> Documento único de referencia para las **36 correlaciones clínicas** que la API
> evalúa de forma determinista antes de invocar al LLM. Está dirigido tanto al
> **optometrista** que llena la receta en el SaaS (para entender qué activa cada
> campo) como al **equipo técnico** (para entender el contrato de datos y el
> fundamento clínico de cada regla).
>
> **Fuente de verdad:** el paquete [app/correlaciones/](app/correlaciones/). Este
> texto traduce esa lógica a lenguaje clínico y la fundamenta con evidencia. Los
> textos exactos que genera cada correlación están blindados por pruebas *golden*
> en [tests/test_correlaciones_golden.py](tests/test_correlaciones_golden.py): si
> el texto de una regla cambia sin actualizar su prueba, el CI falla. Por eso este
> documento y el código no pueden divergir en silencio.

---

## 1. Cómo funciona

Cuando guardas una receta y solicitas la impresión clínica, antes de invocar al
LLM el sistema corre una capa determinista que evalúa **36 reglas clínicas** sobre
los campos que escribiste. Cada regla:

1. **Lee uno o varios campos** de la receta (refracción, AKR/queratometría, fondo
   de ojo, anexos, motivo de consulta, etc.).
2. **Compara el contenido** contra umbrales numéricos o palabras clave clínicas.
3. **Si la condición se cumple**, agrega un hecho clínico pre-redactado al prompt
   del modelo, con la jerarquía correcta.

El LLM **no decide** ninguna correlación: solo integra los hechos ya evaluados al
párrafo final. La respuesta HTTP incluye además el campo `correlaciones_activadas`
con los nombres de las reglas que aplicaron, para trazabilidad.

Lo que tú escribes determina las correlaciones que aparecen. Si una correlación
esperada no salió, casi siempre es porque:

- el campo estaba vacío o con formato distinto al esperado;
- usaste una negación ("sin escotomas", "no presenta…"), interpretada como
  hallazgo ausente;
- una correlación más específica suprimió a la más general (ver
  [Apéndice A](#apéndice-a--reglas-de-supresión-jerarquía-clínica)).

### Normalización del texto

Antes de buscar palabras clave el sistema: pasa todo a minúsculas, elimina acentos
(`miopia` = `miopía`) y colapsa espacios. **No** tienes que preocuparte por
mayúsculas ni acentos, **sí** por la palabra exacta: "lattice" o "degeneracion
reticular" se detectan; "lesion en periferia" no.

### Ventana de negación por oración

Para los hallazgos cualitativos (fondo, motilidad, pupilas, campos, Amsler,
anexos, cristalino) el sistema busca palabras de negación **antes** de la keyword
**en la misma oración**:

```
sin _, no se observa, no se documenta, no presenta, sin evidencia, negativ_, ausenc_, ausente
```

Ejemplo: *"Fondo sin desgarros. Lattice temporal en OI."* → NO activa por
"desgarro" (negado en su oración) pero SÍ por "lattice" (otra oración). **Buena
práctica:** separa hallazgos positivos y negativos en oraciones distintas.

---

## 2. Contrato de datos del frontend (valores estrictos)

El frontend envía varios campos como **constantes o rangos estrictos**. El schema
Pydantic ([app/schemas.py](app/schemas.py)) refleja ese contrato: valores fuera de
rango se rechazan con `422` antes de evaluar cualquier correlación.

| Campo | Tipo / restricción | Notas |
|---|---|---|
| `receta_id` | str, requerido | No participa en cache ni correlaciones |
| `paciente.edad` | int, `0..120` | Modula varias correlaciones; `null` → comportamiento conservador |
| `paciente.ocupacion`, `paciente.motivo_consulta` | str libre | Se normaliza espacio en blanco |
| `refraccion.od/oi.esfera`, `cilindro`, `add` | float | Dioptrías (convención con signo) |
| `refraccion.od/oi.eje` | int, `0..180` | Eje refractivo; **rango validado** |
| `refraccion.od/oi.av_sc`, `av_cc` | str Snellen `20/xx` | Se canoniza (`" 20 / 40 "` → `"20/40"`); notación no-Snellen se conserva pero no dispara AV |
| `akr.pd` | float | Distancia pupilar (mm) |
| `akr.vd` | float, `0..30` | Distancia al vértice (mm) |
| `akr.ker_index` | float, `1.3..1.4` | Índice queratométrico del equipo |
| `akr.od/oi.esfera`, `cilindro` | float | AR (autorrefractómetro) |
| `akr.od/oi.eje`, `k1_eje`, `k2_eje`, `k_cilindro_eje` | int, `0..180` | Ejes |
| `akr.od/oi.k1_d`, `k2_d`, `k_promedio_d` | float, `25..80` | Poder corneal (D) |
| `akr.od/oi.k1_mm`, `k2_mm`, `k_promedio_mm` | float, `4..12` | Radio corneal (mm) |
| `akr.od/oi.k_cilindro` | float, `-20..20` | Cilindro corneal (D) |
| `clinica.uso_pantallas` | `"lt2"` \| `"btw2_6"` \| `"gt6"` \| null | Enum cerrado |
| `clinica.ojo_seco_but_seg` | int, `1..15` | BUT en segundos |
| `clinica.ppc_cm` | int, `1..15` | Punto próximo de convergencia |
| `clinica.cover_test` | str, formato UI | `"OD: {tipo} [y {sub}] \| OI: {tipo} [y {sub}]"`; `" - "` se normaliza a `" y "` |
| `clinica.anexos_oculares`, `reflejos_pupilares`, `motilidad_ocular`, `confrontacion_campos_visuales`, `fondo_de_ojo`, `grid_de_amsler` | str libre | Hallazgos cualitativos |
| `clinica.recomendacion_seguimiento` | str libre | **No** se envía al LLM; se añade determinísticamente al final |
| `tipo_lente` | str | Catálogo abierto (monofocal, bifocal, progresivo, multifocal…); se normaliza espacio |

**Formato del cover test:** `tipo ∈ {Orto, Endo, Exo, Hiper, Hipo}`,
`sub ∈ {Tropia, Foria}`. Ejemplos: `"OD: Orto | OI: Exo y Foria"` activa exoforia
en OI; `"OD: Endo y Tropia | OI: Orto"` activa endotropia en OD. No envíes cadenas
sintéticas como `"exoforia en VP"`.

**Reflejos pupilares:** la UI compone `"{opción}: {nota}"`. Documenta los hallazgos
atípicos (DPAR, Marcus Gunn, anisocoria) en la nota para que se detecten.

---

## 3. Arquitectura del paquete

La lógica está particionada por dominio clínico en [app/correlaciones/](app/correlaciones/):

| Módulo | Correlaciones | Nº |
|---|---|---|
| [fondo_de_ojo.py](app/correlaciones/fondo_de_ojo.py) | periférico, glaucoma asimétrico, glaucomatoso, papila, DMAE, macular otros, hipertensivo, vascular diabético | 8 |
| [refractivas.py](app/correlaciones/refractivas.py) | miopía magna, hipermetropía alta, anisometropía, astig. oblicuo, AV c/c limitada | 5 |
| [akr.py](app/correlaciones/akr.py) | espasmo acomodativo, cambio cristalino, variabilidad, astig. no prescrito | 4 |
| [anexos_cristalino.py](app/correlaciones/anexos_cristalino.py) | anexos patológicos, opacidad cristaliniana | 2 |
| [pupilas_motilidad.py](app/correlaciones/pupilas_motilidad.py) | pupilas alteradas, motilidad alterada | 2 |
| [campos_amsler.py](app/correlaciones/campos_amsler.py) | campos visuales, Amsler | 2 |
| [binocularidad.py](app/correlaciones/binocularidad.py) | insuf. convergencia, PPC/exoforia, exoforia sint., endoforia sint., desviación vertical, endotropia lente, exotropia lente | 7 |
| [superficie_ocular.py](app/correlaciones/superficie_ocular.py) | BUT crítico, BUT pantallas, BUT limítrofe | 3 |
| [contexto.py](app/correlaciones/contexto.py) | presbicia multifocal, CVS, screening adulto mayor | 3 |

Helpers compartidos: `base.py` (memoización + tipo `Correlacion`), `texto.py`
(normalización y matching), `refraccion_utils.py` (Snellen, equivalente esférico),
`queratometria.py` (lectura corneal). El orden de evaluación —invariante clínico—
vive en [registry.py](app/correlaciones/registry.py).

> **Queratometría:** el dato corneal (K1/K2/K promedio/cilindro corneal) se usa como
> **confirmación o matiz** de correlaciones ya disparadas por la refracción o el AR,
> nunca como disparador independiente. Umbrales: K sospechosa 47.20 D, ectasia
> 48.70 D, cilindro corneal relevante 0.75 D, muy alto 4.00 D, córnea plana 41.00 D.

---

## 4. Fondo de ojo

Todas evalúan `clinica.fondo_de_ojo` con ventana de negación. Cuando coexisten,
rige la jerarquía del [Apéndice A](#apéndice-a--reglas-de-supresión-jerarquía-clínica).

### 4.1 `fondo_periferico_riesgo`
**Keywords:** desgarro, agujero retiniano/atrófico/operculado, lattice, degeneración
reticular/en empalizada, palizada, blanco con presión, desprendimiento, schisis,
retinosquisis.
**Texto:** *"Hallazgo urgente: en la retina periferica se documenta {hallazgo}, que
amerita valoracion retinologica urgente y posible tratamiento profilactico."*
**Fundamento:** la degeneración lattice y los desgarros retinianos son lesiones
predisponentes al desprendimiento de retina regmatógeno; ameritan valoración
retinológica y eventual retinopexia profiláctica (AAO PPP *Posterior Vitreous
Detachment, Retinal Breaks, and Lattice Degeneration*). Etiquetada **urgente**.

### 4.2 `glaucoma_asimetrico` (compuesta)
**Requiere:** `reflejos_pupilares` con `dpar`/`marcus gunn` (con negación) **y**
`fondo_de_ojo` con keyword glaucomatosa.
**Suprime:** `pupilas_alteradas` y `fondo_glaucomatoso`.
**Texto:** *"Hallazgo urgente: se documenta excavacion papilar aumentada con defecto
pupilar aferente relativo, lo que indica compromiso asimetrico del nervio optico con
probable repercusion funcional, ameritando valoracion oftalmologica priorizada."*
**Fundamento:** un DPAR (defecto pupilar aferente relativo) refleja daño asimétrico
de la vía aferente; combinado con excavación glaucomatosa sugiere neuropatía óptica
glaucomatosa avanzada y asimétrica. El texto dice "**probable** repercusión
funcional" —no "confirmada"— porque el sistema no dispone de campo visual ni OCT
para confirmarla. Etiquetada **urgente**.

### 4.3 `fondo_glaucomatoso`
**Keywords:** `c/d 0.5`–`0.9`, `cup/disc 0.5`–`0.9`, excavación, papila asimétrica,
asimetría c/d, muesca, notch, hemorragia peripapilar, rima neural adelgazada.
**Suprimida por:** `glaucoma_asimetrico`.
**Texto:** *"Se documentan hallazgos papilares con excavacion aumentada y/o
alteracion del anillo neurorretiniano, ameritando valoracion oftalmologica con
tonometria y perimetria para descarte de glaucoma."*
**Fundamento:** relación copa/disco aumentada, asimetría interocular y violación de
la regla ISNT (inferior ≥ superior ≥ nasal ≥ temporal) son signos de neuropatía
glaucomatosa; requieren tonometría, paquimetría y perimetría (AAO PPP *Primary
Open-Angle Glaucoma*). Documenta la relación C/D con decimal (`c/d 0.7`).

### 4.4 `papila_patologica`
**Keywords:** palidez papilar/de papila, atrofia óptica/papilar, edema de papila,
papiledema, neuritis óptica, borramiento de bordes, bordes borrosos.
**Coexiste** con `fondo_glaucomatoso` (etiologías distintas del nervio óptico).
**Texto base:** *"Se documenta alteracion del nervio optico no asociada a excavacion
glaucomatosa, ameritando valoracion neurooftalmologica para caracterizacion
etiologica."*
**Variante urgente** (papiledema/edema/bordes borrosos): *"Hallazgo urgente: los
hallazgos del nervio optico documentados son compatibles con edema de papila, lo que
amerita evaluacion neurooftalmologica urgente para descarte de hipertension
intracraneal."*
**Fundamento:** el edema de papila bilateral obliga a descartar hipertensión
intracraneal (neuroimagen ± punción lumbar); la palidez indica atrofia óptica
establecida. Ambos son neuro-oftalmológicos, distintos del glaucoma.

### 4.5 `fondo_macular_dmae`
**Keywords:** drusas, drusen, alteración pigmentaria/del EPR, atrofia geográfica,
membrana neovascular, mnvc, cnv, mev, epiteliopatía, dmae, degeneración macular.
**Texto:** *"Se documentan hallazgos maculares degenerativos en fondo de ojo,
ameritando OCT macular para caracterizacion y monitorizacion."*
**Fundamento:** drusas y alteraciones del EPR definen DMAE temprana/intermedia; la
neovascularización marca la forma exudativa. El OCT es el estándar de
caracterización y seguimiento; los suplementos AREDS2 aplican en estadios
intermedios (*Age-Related Eye Disease Study 2*).

### 4.6 `fondo_macular_otros`
**Keywords:** edema macular, membrana epirretiniana, mer, pucker, agujero macular,
quiste macular, coroidopatía serosa, corioretinopatía serosa, crsc.
**Texto:** *"En la region macular se documenta alteracion estructural que amerita
OCT y valoracion retinologica."*
**Fundamento:** membrana epirretiniana, agujero macular y coriorretinopatía serosa
central son maculopatías estructurales no degenerativas que el OCT resuelve.

### 4.7 `fondo_hipertensivo`
**Keywords:** tortuosidad vascular, cruces arteriovenosos, cruces AV, signo de Gunn,
estrechamiento arterial, hilos de cobre/plata, algodonoso, cotton wool, Salus,
ingurgitación venosa, **hemorragia en llama**.
**Texto:** *"Se documentan hallazgos vasculares en fondo de ojo con alteraciones
arteriovenosas, ameritando correlacion con cifras tensionales sistemicas."*
**Fundamento:** cruces AV patológicos, estrechamiento arteriolar y hemorragias en
llama son signos de retinopatía hipertensiva (clasificación Keith-Wagener-Barker /
Mitchell-Wong). La *hemorragia en llama* es un signo superficial de la capa de
fibras nerviosas típico de HTA/oclusión venosa, **no** de retinopatía diabética.

### 4.8 `fondo_vascular_diabetico`
**Keywords:** microaneurisma(s), exudado, hemorragia retiniana/intrarretin/en
mancha/puntiforme, neovas, rubeosis.
**Suprimida por:** `fondo_periferico_riesgo`, `fondo_glaucomatoso`,
`fondo_macular_dmae`, `fondo_macular_otros`. **No** se suprime contra
`fondo_hipertensivo` (retinopatía diabética e hipertensiva coexisten con frecuencia
—comorbilidad DM2 + HTA— y usan signos distintos que ambos merecen mención).
**Texto:** *"Se documentan hallazgos vasculares en fondo de ojo con presencia de
alteraciones microvasculares, ameritando correlacion sistemica (control glucemico) y
valoracion retinologica."*
**Fundamento:** microaneurismas, exudados duros y hemorragias intrarretinianas son
signos de retinopatía diabética (escala ETDRS); la neovascularización/rubeosis marca
la forma proliferativa. Requiere correlación glucémica.

---

## 5. Refracción final

### 5.1 `miopia_magna`
**Condición:** equivalente esférico (`EE = esfera + cilindro/2`) **≤ -6.00 D** en al
menos un ojo. Variante "muy alta" con `EE ≤ -8.00 D`.
**Texto:** *"Se documenta miopia de magnitud {alta|muy alta} en OD (EE -7.00D), lo que
conlleva {mayor riesgo|riesgo significativamente elevado} de patologia retiniana
periferica y macular."* Si la queratometría muestra irregularidad corneal, añade una
frase sobre componente corneal y estudio topográfico.
**Fundamento:** el International Myopia Institute define miopía alta como
`≤ -6.00 D` (o longitud axial ≥ 26 mm); conlleva mayor riesgo de maculopatía
miópica, desprendimiento de retina, glaucoma y catarata. Justifica vigilancia
retinológica periódica.

### 5.2 `hipermetropia_alta`
**Condición:** `EE ≥ +5.00 D` en al menos un ojo. Modulada por edad.
**Texto (edad ≥ 40 o desconocida):** énfasis en **ángulo camerular estrecho** →
evaluación de cámara anterior. **Texto (edad < 40):** énfasis en **demanda
acomodativa** → vigilancia de esoforia/esotropía acomodativa. La queratometría plana
o pronunciada añade matiz corneal.
**Fundamento:** el ojo hipermétrope es corto, con cámara anterior estrecha → mayor
riesgo de cierre angular en adultos; en niños/jóvenes la demanda acomodativa
sostenida predispone a esotropía acomodativa.

### 5.3 `anisometropia`
**Condición:** `|EE_OD − EE_OI| > 1.00 D`. Severidad: leve (`>1` y `<2`), moderada
(`≥2` y `≤3`), severa (`>3`). Antimetropía si `EE_OD × EE_OI < 0`.
**Texto:** *"Existe anisometropia moderada por diferencia de equivalente esferico de
2.50D entre OD (-1.00) y OI (-3.50); con posible impacto en la fusion binocular."*
La queratometría añade asimetría corneal interocular si aplica.
**Fundamento:** la anisometropía significativa induce aniseiconia y dificultad
fusional; en niños es factor de ambliopía. Diferencias >3 D o antimetropía suelen
requerir lente de contacto para minimizar disparidad de imagen.

### 5.4 `astig_oblicuo`
**Condición:** `|cilindro| > 2.00 D` **y** eje oblicuo (20–70° o 110–160°) en la Rx
final. La queratometría solo **confirma** (cilindro corneal ≥ 1.00 D con eje
coincidente ±20°), no dispara.
**Texto:** *"OD (-2.50 x 45): astigmatismo elevado con eje oblicuo[ confirmado por
queratometria]."* Severidad: elevado (`≤3`), alto (`≤4`), muy alto (`>4`).
**Fundamento:** el astigmatismo oblicuo de alta magnitud degrada más la agudeza y la
adaptación que el astigmatismo a favor/en contra de la regla; anticipa periodo de
adaptación al lente.

### 5.5 `av_cc_limitada`
**Condición:** denominador Snellen **> 20** en al menos un ojo (no activa con 20/20 o
supranormal). Categorías: 20/21–30 leve, 20/31–50 moderada, 20/51–100 marcada,
>20/100 déficit severo.
**Texto:** *"OD (20/40): reduccion moderada de la agudeza visual con correccion."*
Con irregularidad corneal, añade nota sobre superficie corneal.
**Fundamento:** la AV con corrección subnormal cuantifica el déficit funcional con
independencia de la causa; coexiste con la correlación patológica que lo explique
(catarata, DMAE, glaucoma) sin redundar —por eso `opacidad_cristaliniana` no
menciona la AV.

---

## 6. Autorrefractómetro / queratometría vs refracción final

Solo aplican si hay valores en `refraccion` **y** `akr` del mismo ojo. Jerarquía:
primero el patrón específico (espasmo, cristalino), luego la variabilidad.

### 6.1 `ar_rx_espasmo_acomodativo`
**Condición:** edad `< 40`, `uso_pantallas ∈ {btw2_6, gt6}`, y en algún ojo
`esfera_Rx − esfera_AR ≥ 0.50` (el AR mide más miope).
**Texto:** *"El autorrefractometro documenta mayor componente miopico que la
refraccion subjetiva final en un paciente joven con uso intensivo de pantallas,
patron compatible con espasmo acomodativo que amerita control posterior y eventual
refraccion bajo cicloplejia."*
**Fundamento:** la pseudomiopía por espasmo acomodativo es frecuente en jóvenes con
trabajo próximo intensivo; el AR sin cicloplejia sobreestima la miopía. La refracción
bajo cicloplejia lo confirma.

### 6.2 `ar_rx_cambio_cristalino`
**Condición:** edad `≥ 55`, `|esfera_AR − esfera_Rx| > 1.00 D`, y **sin** irregularidad
corneal queratométrica (que explicaría la diferencia por córnea, no por cristalino).
**Texto:** *"Se documenta discrepancia entre autorrefractometro y refraccion final en
un paciente mayor de 55 anos, sin patron queratometrico que explique primariamente la
diferencia refractiva, lo que puede reflejar cambios en el indice refractivo del
cristalino y amerita evaluacion biomicroscopica del segmento anterior."*
**Fundamento:** la esclerosis nuclear del cristalino aumenta su índice refractivo y
produce un desplazamiento miópico ("second sight"); requiere biomicroscopía.

### 6.3 `ar_rx_variabilidad_inespecifica` (red de seguridad)
**Condición:** discrepancia `> 1.00 D` en esfera o cilindro entre AR y Rx, y **no**
activaron 6.1 ni 6.2.
**Texto:** *"Se documenta discrepancia entre autorrefractometro y refraccion final,
compatible con variabilidad refractiva durante la exploracion."* (Con irregularidad
corneal añade la nota queratométrica.)
**Fundamento:** discrepancias sin patrón etario específico reflejan variabilidad
propia de la medición automatizada frente a la subjetiva.

### 6.4 `ar_detecta_astigmatismo_no_prescrito`
**Condición:** `|cilindro_AR| ≥ 0.75` y (`cilindro_Rx` nulo o `< 0.50`). Si hay
queratometría, debe **soportar** el astigmatismo (cilindro corneal ≥ 0.75 D); si no
lo soporta, no dispara.
**Texto:** *"El autorrefractometro detecta astigmatismo no incluido en la refraccion
subjetiva final en OD (AKR -1.00D), lo que puede corresponder a astigmatismo
subumbral con tolerancia clinica adecuada o variabilidad de la medicion
automatizada."*
**Fundamento:** documenta la decisión clínica de no prescribir un astigmatismo bajo
detectado por el AR (tolerancia adecuada o ruido de medición), sin sugerir corregirlo.

---

## 7. Anexos oculares y cristalino

### 7.1 `anexos_patologicos`
**Keywords:** blefaritis, meibomitis, chalazión, orzuelo, pterigión, pinguécula,
conjuntivitis, hiperemia, queratitis, erosión, leucoma, opacidad/edema corneal,
distriquiasis, triquiasis, ectropión, entropión, ptosis, dermatochalasis,
lagoftalmos. Aplica negación y deduplica.
**Texto:** *"En anexos oculares se documenta {hallazgos}."*
**Fundamento:** la blefaritis y la disfunción de glándulas de Meibomio son causa
mayor de ojo seco evaporativo (TFOS DEWS II); el pterigión y las alteraciones
palpebrales tienen implicación refractiva y de superficie.

### 7.2 `opacidad_cristaliniana`
**Campos:** `anexos_oculares` + `fondo_de_ojo` concatenados (flexibilidad práctica
del registro).
**Keywords:** catarata(s), opacidad cristaliniana/del cristalino, facoesclerosis,
esclerosis nuclear, pseudofaquia, pseudofaco, pseudofáquico, afaquia, afáquico.
**Texto:** *"Se documenta alteracion del cristalino, ameritando evaluacion
biomicroscopica para caracterizacion y estadificacion de la opacidad."* No menciona
AV (lo cubre `av_cc_limitada`).
**Fundamento:** la catarata se gradúa por biomicroscopía (p. ej. LOCS III); la
pseudofaquia/afaquia documenta estado quirúrgico previo relevante para la refracción.

---

## 8. Pupilas y motilidad

### 8.1 `pupilas_alteradas`
**Keywords:** anisocoria, midriasis, miosis, DPAR, Marcus Gunn, no reactivo/a,
irregular, discoria, ausente. **Excluye** anisocoria explícitamente calificada de
*fisiológica/benigna/simple*. **Suprimida por:** `glaucoma_asimetrico`.
**Texto base:** *"En la exploracion pupilar se documenta {hallazgos}, lo que amerita
valoracion neurooftalmologica."* **Variante urgente (DPAR/Marcus Gunn):** añade
*"Hallazgo urgente: la presencia de defecto pupilar aferente relativo es indicativa de
patologia de via optica y requiere evaluacion urgente."*
**Fundamento:** el DPAR localiza daño asimétrico de vía óptica aferente (urgente); la
anisocoria fisiológica afecta al ~15–30 % de la población y es benigna, por eso se
excluye cuando el clínico la califica como tal.

### 8.2 `motilidad_alterada`
**Keywords:** limitación, paresia, parálisis, restricción, nistagmo/nistagmus, dolor
con/al movimiento, sobreacti, hiperfunción, hipoacción/hipofunción, sincinesia,
Duane, oftalmoplejia/oftalmoplegia.
**Texto:** *"Se documenta alteracion de la motilidad ocular, lo que amerita estudio
de vias motoras y posible interconsulta neurooftalmologica."*
**Fundamento:** limitaciones y paresias sugieren afectación de pares craneales
III/IV/VI o restricción mecánica; el nistagmo y las sincinesias (Duane) orientan a
causas congénitas o neurológicas.

---

## 9. Campos visuales y test de Amsler

### 9.1 `campos_visuales_alterados`
**Keywords positivas:** escotoma, defecto, hemianopsia, cuadrantopsia, constricción,
restricción, campo reducido, alteración, no responde. **Bloqueo global:** `sin
defect`, `sin alteracion`, `normal`, `integro`. Además, negación por oración.
**Texto:** *"La confrontacion de campos visuales revela alteracion que amerita
perimetria automatizada para caracterizacion del defecto."*
**Fundamento:** el patrón del defecto localiza la lesión (hemianopsia → vía
retroquiasmática; escotoma central → mácula/nervio); la confrontación es de cribado
y la perimetría automatizada la caracteriza.

### 9.2 `amsler_alterado`
**Keywords positivas:** distorsión, metamorfopsia, escotoma central, escotoma,
alterado, alteración, ondulación, líneas torcidas. **Bloqueo global:** `sin
distorsion`, `sin alteracion`, `normal`, `negativo`.
**Texto:** *"El test de Amsler revela alteracion compatible con patologia macular
funcional que amerita OCT macular."*
**Fundamento:** la metamorfopsia en la rejilla de Amsler es marcador funcional de
patología macular (DMAE exudativa, MER, edema); indica OCT macular.

---

## 10. Binocularidad y convergencia

Jerarquía: `insuficiencia_convergencia` (compuesta) suprime `ppc_exoforia` y
`cover_exoforia_sintomatica`.

### 10.1 `insuficiencia_convergencia` (compuesta)
**Requiere:** `ppc_cm > 10`, `cover_test` con exoforia, y `motivo_consulta` con
keyword de cercanía (lectura, leer, estudiar, cerca, astenopia, fatiga, cefalea).
**Texto:** *"La combinacion de punto proximo de convergencia alejado, exoforia y
sintomatologia de vision proxima es compatible con insuficiencia de convergencia,
ameritando evaluacion binocular completa para confirmar el diagnostico y plantear
terapia visual si procede."*
**Fundamento:** la insuficiencia de convergencia (PPC alejado + exoforia mayor en
visión próxima + síntomas astenópicos de lectura) responde a terapia visual con
ejercicios de vergencia (Convergence Insufficiency Treatment Trial, CITT).

### 10.2 `ppc_exoforia`
**Activa con:** `ppc_cm > 10` **o** `cover_test` con exoforia. **Suprimida por:**
insuf. convergencia.
**Texto:** *"El paciente presenta {punto proximo de convergencia alejado (X cm)}[ y
{exoforia en vision proxima/lejana | tendencia divergente en el cover test}]."*
**Fundamento:** un PPC > 10 cm o una exoforia documentada son signos de disfunción de
vergencia que ameritan mención aun sin el cuadro sintomático completo.

### 10.3 `cover_exoforia_sintomatica`
**Requiere:** exoforia en cover + síntoma binocular (diplopía, visión doble, cefalea,
astenopia, fatiga visual, vista cansada, ardor/lagrimeo con lectura, pérdida del
renglón, salto de letras, visión borrosa intermitente). **Suprimida por:** insuf.
convergencia.
**Texto:** *"Se documenta exoforia con sintomatologia binocular asociada, compatible
con disfuncion binocular de tipo divergente que amerita evaluacion funcional."*
**Fundamento:** una exoforia descompensada sintomática configura disfunción binocular
divergente subsidiaria de estudio funcional.

### 10.4 `cover_endoforia_sintomatica`
**Requiere:** endoforia (y NO endotropia) en cover + síntoma binocular.
**Texto:** *"Se documenta endoforia con sintomatologia binocular asociada, compatible
con exceso de convergencia o disfuncion acomodativa que amerita evaluacion
funcional."*
**Fundamento:** la endoforia sintomática orienta a exceso de convergencia o disfunción
acomodativa (relación AC/A alterada).

### 10.5 `desviacion_vertical`
**Keywords:** hiperforia, hipoforia, hipertropia, hipotropia.
**Texto (solo forias):** *"Se documenta hiperforia, que puede generar sintomatologia
binocular especifica y amerita cuantificacion prismatica para evaluar compensacion."*
**Texto (tropías):** *"…que representa una desviacion manifiesta y amerita
cuantificacion prismatica inmediata con evaluacion binocular completa."*
**Fundamento:** las desviaciones verticales, aun pequeñas, son mal toleradas y
generan astenopia/diplopía; la tropía manifiesta es más urgente que la foria latente.

### 10.6 `endotropia_lente`
**Requiere:** endotropia en cover + `tipo_lente` no nulo.
**Texto:** *"Se documenta endotropia en el cover test, ameritando evaluacion de la
respuesta a la correccion optica prescrita, con cover test bajo correccion para
clasificar el tipo de desviacion."*
**Fundamento:** la endotropía puede ser acomodativa (total o parcialmente corregida
por la Rx hipermetrópica); el cover test bajo corrección clasifica el componente.

### 10.7 `exotropia_lente`
**Requiere:** exotropia en cover + `tipo_lente` no nulo.
**Texto:** *"Se documenta exotropia en el cover test, ameritando evaluacion binocular
completa para determinar frecuencia y magnitud de la desviacion, asi como la
respuesta a la correccion optica prescrita."*
**Fundamento:** la exotropía intermitente requiere caracterizar frecuencia/magnitud y
control de fusión para decidir manejo óptico, prismático o quirúrgico.

---

## 11. Superficie ocular — tiempo de ruptura lagrimal (BUT)

Las tres son mutuamente excluyentes por construcción.

### 11.1 `but_critico`
**Condición:** `ojo_seco_but_seg < 5`.
**Texto:** *"El tiempo de ruptura lagrimal de {X}s es patologicamente bajo, compatible
con ojo seco clinico que amerita evaluacion."*
**Fundamento:** un BUT < 5 s indica inestabilidad grave de la película lagrimal
(criterio de ojo seco, TFOS DEWS II, donde BUT < 10 s ya es reducido).

### 11.2 `but_pantallas`
**Condición:** `5 ≤ BUT ≤ 9` **y** `uso_pantallas ∈ {btw2_6, gt6}`.
**Texto:** *"El tiempo de ruptura lagrimal de {X} segundos es reducido en el contexto
del uso de pantallas, lo que indica inestabilidad de la pelicula lagrimal."*
**Fundamento:** el uso intensivo de pantallas reduce la tasa de parpadeo y agrava la
inestabilidad lagrimal (componente evaporativo del síndrome visual informático).

### 11.3 `but_limitrofe`
**Condición:** `5 ≤ BUT ≤ 9` **y** `uso_pantallas` nulo o `lt2`.
**Texto:** *"El tiempo de ruptura lagrimal de {X}s se encuentra en rango suboptimo,
sugiriendo inestabilidad leve de la pelicula lagrimal."*
**Fundamento:** un BUT en rango suboptimo sin exposición alta a pantallas indica
inestabilidad leve, subsidiaria de vigilancia.

---

## 12. Edad, lente y pantallas

### 12.1 `presbicia_multifocal`
**Activa con:** (`tipo_lente` multifocal/bifocal/progresivo **y** (edad ≥ 40 **o** hay
add)) **o** (edad ≥ 40 **y** hay add).
**Texto (con edad):** *"El paciente de {X} anos presenta reduccion fisiologica de la
amplitud acomodativa propia de la edad, lo que justifica la adicion prescrita[ y el
lente multifocal indicado]."*
**Fundamento:** la presbicia es la reducción fisiológica progresiva de la amplitud
acomodativa a partir de ~40 años; justifica la adición y el diseño multifocal.

### 12.2 `cvs_sospecha`
**Requiere:** `uso_pantallas ∈ {btw2_6, gt6}` + `motivo_consulta` con ardor/sequedad
ocular, visión borrosa (intermitente), dolor ocular, cefalea, picazón, prurito,
lagrimeo.
**Texto:** *"El perfil de uso de pantallas se correlaciona con la sintomatologia
visual referida, compatible con sindrome visual informatico, ameritando
recomendaciones ergonomicas y eventual correccion optica para vision intermedia."*
**Fundamento:** el síndrome visual informático (digital eye strain) combina fatiga
acomodativa, disfunción lagrimal y ergonomía; el manejo incluye recomendaciones
ergonómicas (regla 20-20-20) y corrección para distancia intermedia.

### 12.3 `adulto_mayor_screening`
**Requiere:** edad ≥ 60 + AV c/c limitada. **Suprimida** si ya hay causa específica:
opacidad cristaliniana, fondo glaucomatoso, DMAE, macular otros, vascular diabético,
hipertensivo, miopía magna, papila patológica o irregularidad corneal queratométrica.
**Texto:** *"En paciente de {X} anos con reduccion de agudeza visual sin causa
identificada en el examen actual, se recomienda descarte activo de catarata, glaucoma
y maculopatia asociada a la edad mediante exploracion dirigida."*
**Fundamento:** ante AV reducida en el adulto mayor sin causa documentada, el cribado
dirigido de las tres causas prevalentes de baja visión (catarata, glaucoma, DMAE) es
buena práctica; si ya hay causa, el mensaje genérico sería redundante.

---

## Apéndice A — Reglas de supresión (jerarquía clínica)

| Si activa | Se suprimen |
|---|---|
| `glaucoma_asimetrico` | `pupilas_alteradas`, `fondo_glaucomatoso` |
| `insuficiencia_convergencia` | `ppc_exoforia`, `cover_exoforia_sintomatica` |
| `fondo_periferico_riesgo` / `fondo_glaucomatoso` / `fondo_macular_dmae` / `fondo_macular_otros` | `fondo_vascular_diabetico` |
| `ar_rx_espasmo_acomodativo` / `ar_rx_cambio_cristalino` | `ar_rx_variabilidad_inespecifica` |
| `opacidad_cristaliniana` / `fondo_glaucomatoso` / `fondo_macular_dmae` / `fondo_macular_otros` / `fondo_vascular_diabetico` / `fondo_hipertensivo` / `miopia_magna` / `papila_patologica` / irregularidad corneal queratométrica | `adulto_mayor_screening` |

Coexistencias intencionadas: `papila_patologica` no se suprime con
`fondo_glaucomatoso` (neuropatías distintas); `av_cc_limitada` y
`opacidad_cristaliniana` coexisten (una cuantifica, la otra nombra la causa);
`fondo_vascular_diabetico` no se suprime con `fondo_hipertensivo` (comorbilidad).

## Apéndice B — Hallazgos urgentes

El system prompt obliga al LLM a colocarlos en las primeras dos o tres oraciones:

- `fondo_periferico_riesgo` (siempre)
- `glaucoma_asimetrico` (siempre)
- `papila_patologica` (variante papiledema / edema de papila / bordes borrosos)
- `pupilas_alteradas` (cuando hay DPAR o Marcus Gunn)

## Apéndice C — Buenas prácticas para activar correctamente las correlaciones

1. **Nombres clínicos exactos:** `"lattice"`, `"papila asimetrica"`, `"c/d 0.7"`,
   `"microaneurismas"`. Las descripciones genéricas no activan keywords.
2. **Separa positivos de negativos** en oraciones distintas.
3. **Relación C/D con decimal:** `"c/d 0.7"` o `"cup/disc 0.7"` (desde 0.5).
4. **Cover test:** usa el formato de la UI `"OD: Tipo [y Sub] | OI: Tipo [y Sub]"`.
5. **Reflejos pupilares:** registra hallazgos atípicos en la nota libre.
6. **PPC y BUT** son enteros 1–15; fuera de rango los rechaza el schema.
7. **Motivo de consulta:** muchas correlaciones binoculares y de pantallas dependen
   de palabras clave aquí (cefalea, astenopia, lectura, ardor…). Anota síntomas
   reales en lugar de "examen de rutina".
8. **AKR vs Rx:** si el AR no se midió, deja los campos nulos; valores inventados o
   iguales a la Rx no activan nada pero pueden silenciar correlaciones válidas.
9. **Edad:** modula hipermetropía alta, espasmo, cambio cristalino, presbicia y
   screening. Sin fecha de nacimiento, la edad llega `null` y varias reglas se
   vuelven conservadoras.
10. **Tipo de lente:** activa la rama "con lente" de `endotropia_lente`,
    `exotropia_lente` y `presbicia_multifocal`.

## Resumen ejecutivo

- **36 correlaciones**, 9 dominios clínicos, particionadas en
  [app/correlaciones/](app/correlaciones/).
- **Determinista:** mismos datos → mismas correlaciones.
- **Jerárquica:** las específicas suprimen a las generales (Apéndice A).
- **None-safe:** campos vacíos no producen errores.
- **Texto dinámico:** muchas correlaciones citan ojo, valores y hallazgos exactos.
- **Queratometría** como confirmación/matiz, nunca como disparador aislado.
- **El LLM no decide** la correlación, solo la integra; los nombres activados se
  devuelven en `correlaciones_activadas`.
- **Blindaje:** los 36 textos están cubiertos por pruebas *golden* que impiden
  regresiones silenciosas del contenido clínico.
