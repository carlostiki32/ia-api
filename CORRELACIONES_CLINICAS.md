# Correlaciones clínicas — guía definitiva (código + fundamento clínico)

> Documento único de referencia para las **57 correlaciones clínicas** que la API
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
LLM el sistema corre una capa determinista que evalúa **57 reglas clínicas** sobre
los campos que escribiste. Cada regla:

1. **Lee uno o varios campos** de la receta (refracción, AKR/queratometría, fondo
   de ojo, anexos, motivo de consulta, etc.).
2. **Compara el contenido** contra umbrales numéricos o palabras clave clínicas.
3. **Si la condición se cumple**, agrega un hecho clínico pre-redactado al prompt
   del modelo, con la jerarquía correcta.

El LLM **no decide** ninguna correlación: solo integra los hechos ya evaluados al
párrafo final. La respuesta HTTP incluye además el campo `correlaciones_activadas`
con los nombres de las reglas que aplicaron, para trazabilidad.

> **Nota sobre acentos:** los textos de las correlaciones citados en este documento
> se almacenan **sin acentos** en el código (facilita el matching normalizado y los
> tests golden). El párrafo final que devuelve la API **sí** lleva acentos: un
> reacentuador determinista los restaura al final del pipeline
> ([PIPELINE_LLM.md §10](PIPELINE_LLM.md#10-postprocesamiento-del-output)).

Lo que tú escribes determina las correlaciones que aparecen. Si una correlación
esperada no salió, casi siempre es porque:

- el campo estaba vacío o con formato distinto al esperado;
- usaste una negación ("sin escotomas", "lattice ausente", "desgarro descartado"),
  interpretada como hallazgo ausente;
- una correlación más específica suprimió a la más general (ver
  [Apéndice A](#apéndice-a--reglas-de-supresión-jerarquía-clínica)).

### Normalización del texto

Antes de buscar palabras clave el sistema: pasa todo a minúsculas, elimina acentos
(`miopia` = `miopía`) y colapsa espacios. **No** tienes que preocuparte por
mayúsculas ni acentos. Sí importa **usar un término clínico reconocido**, pero las
listas de keywords están **enriquecidas con sinónimos, coloquialismos mexicanos,
abreviaturas y variantes de escritura** para tolerar la redacción libre real: por
ejemplo `carnosidad` (= pterigión), `calacio`/`perrilla` (= chalazión/orzuelo), `E/P
0.7` (= excavación/papila), `RAPD` (= DPAR), `IOL` (= pseudofaquia), `visión tubular`
(= constricción de campo), `veo doble`/`se juntan las letras` (síntomas binoculares).
Aun así, una descripción totalmente genérica ("lesión en periferia", "algo raro en la
mácula") no dispara: hace falta nombrar el hallazgo. Los listados por correlación de
abajo muestran keywords **representativas**, no exhaustivas.

> **Abreviaturas cortas:** las abreviaturas de 3–4 letras que son subcadena de
> palabras comunes (`mer` en "primero", `irma` en "afirma", `adie` en "nadie", `iol`
> en "violeta") se buscan como **palabra completa**, de modo que no generan falsos
> positivos dentro de otras palabras.

### Ventana de negación bidireccional por cláusula con quiebres sintácticos

Para los hallazgos cualitativos (fondo, motilidad, pupilas, campos, Amsler,
anexos, cristalino) el sistema evalúa la negación de forma **bidireccional** dentro de
la misma cláusula (delimitada por punto, punto y coma, dos puntos o signos de interrogación/admiración),
incorporando salvaguardas avanzadas contra falsos negativos y positivos:

1. **Negación prefija (antepuesta):**
   ```
   sin _, no _, no se observa, no se documenta, no presenta, no se detect_, sin evidencia, negativ_, ausenc_, libre de, descarte de
   ```
2. **Negación sufija (pospuesta, ventana de hasta 8 palabras):**
   ```
   ausente, ausentes, descartado, descartada, descartados, descartadas, negativo, negativa, negativos, negativas, fisiologico, fisiologica, normal, normales, libre, libres
   ```
3. **Quiebres afirmativos de transición (rompen prefijo negativo sin puntuación):**
   Conectores como `"se observa"`, `"presenta"`, `"se evidencia"`, `"se constata"` o `"con presencia de"`
   truncan de inmediato el alcance del prefijo negativo previo. Ejemplo: *"sin hemorragias ni exudados se observa desgarro en herradura"*
   reconoce activamente el desgarro.
4. **Quiebres causales en solicitudes de descarte:**
   Expresiones causales (`" por "`, `" debido a "`, `" secundario a "`) truncan el alcance de `"descarte de"`. Ejemplo:
   *"se solicita descarte de glaucoma por excavacion 0.8"* activa la sospecha glaucomatosa por el hallazgo objetivo.
5. **Protección de expresiones anatómicas globales:**
   Frases como `"resto normal"` o `"demas normal"` no actúan como negadores pospuestos de la patología precedente. Ejemplo:
   *"papiledema, resto normal"* activa la alerta urgente de papiledema.

---

## 2. Contrato de datos del frontend (catálogo estricto + coerción tolerante)

El frontend envía muchos campos como **dropdowns/enums cerrados o rangos estrictos**.
El schema Pydantic ([app/schemas.py](app/schemas.py)) refleja ese catálogo (fuente:
`OpticaOptions`, `RecetaFormOptions`, `RecetaValidationRules` del SaaS; mapeo completo
en [DICCIONARIO_DATOS_RECETA.md](DICCIONARIO_DATOS_RECETA.md)).

> **Política de validación: coerción tolerante, no rechazo.** El SaaS invoca este
> endpoint con el estado **crudo** del formulario (el botón "Generar con IA" arma el
> payload **antes** de validar/guardar). Por eso un valor fuera de catálogo en un
> campo secundario **no** produce `422`: se **descarta** (`None`) o se **normaliza**
> (el eje se toma módulo 180) y se registra en el log. El único `422` de datos es
> "no hay ningún dato clínico útil" (sección 5 del pipeline). Así, un eje de 190 o
> una K corrupta no tumban toda la generación.

| Campo | Origen / restricción | Fuera de catálogo | Notas |
|---|---|---|---|
| `receta_id` | str, requerido | — | No participa en cache ni correlaciones |
| `paciente.edad` | int, `0..120` (calculada) | → `None` | Modula varias correlaciones; `null` → comportamiento conservador |
| `paciente.ocupacion`, `paciente.motivo_consulta` | str libre | — | Se normaliza espacio en blanco |
| `refraccion.od/oi.esfera` | dropdown/input `+30.00..-30.00` paso 0.25 | → `None` | Tolerancia ampliada a ±30.00 D para alta miopía degenerativa y afaquias |
| `refraccion.od/oi.cilindro` | dropdown `0.00..-8.00` paso 0.25, **siempre ≤ 0** | → `None` | La Rx **no** se transpone (ya es minus-cyl) |
| `refraccion.od/oi.add` | input libre; `add ≤ 0` → `None` | — | `0` tecleado no es adición prescrita |
| `refraccion.od/oi.eje` | int, eje **cíclico** | **mod 180** (`225`→`45`) | El SaaS no valida rango; se normaliza, no se rechaza |
| `refraccion.od/oi.av_sc`, `av_cc` | dropdown Snellen + baja visión libre | se conserva | Soporta notaciones Snellen (`20/40`), decimal (`0.5`), métrica (`6/12`) y baja visión semicuantitativa (`"cuenta dedos"`, `"MM"`, `"PL"`, `"NPL"` mapeados a denominadores $\ge 1000$) |
| `akr.pd` | float (mm) | — | Distancia pupilar |
| `akr.vd` | float, `0..30` (mm) | → `None` | Distancia al vértice |
| `akr.ker_index` | float, `1.3..1.4` | → `None` | Índice queratométrico del equipo |
| `akr.od/oi.esfera`, `cilindro` | float (AR); **transposición solo AKR** si plus-cyl | — | Alinea la comparación esfera AR vs Rx |
| `akr.od/oi.eje`, `k1_eje`, `k2_eje`, `k_cilindro_eje` | int, eje cíclico | **mod 180** | Ejes |
| `akr.od/oi.k1_d`, `k2_d`, `k_promedio_d` | float, `25..80` | → `None` | Poder corneal (D) |
| `akr.od/oi.k1_mm`, `k2_mm`, `k_promedio_mm` | float, `4..12` | → `None` | Radio corneal (mm) |
| `akr.od/oi.k_cilindro` | float, `-20..20` | → `None` | Cilindro corneal (D) |
| `clinica.uso_pantallas` | `"lt2"` \| `"btw2_6"` \| `"gt6"` \| null | → `None` | Enum cerrado |
| `clinica.ojo_seco_but_seg` | dropdown int `1..15` | → `None` | BUT en segundos |
| `clinica.ppc_cm` | dropdown int `1..15` | → `None` | Punto próximo de convergencia |
| `clinica.cover_test` | str, formato UI (sub **opcional**) | — | `"OD: {tipo}[ y {sub}] \| OI: {tipo}[ y {sub}]"`; `" - "` → `" y "` |
| `clinica.anexos_oculares`, `reflejos_pupilares`, `motilidad_ocular`, `confrontacion_campos_visuales`, `fondo_de_ojo`, `grid_de_amsler` | str libre | — | Hallazgos cualitativos |
| `clinica.recomendacion_seguimiento` | str libre | — | **No** se envía al LLM; se añade determinísticamente al final |
| `tipo_lente` | catálogo `monofocal \| bifocal_blended \| progresivo \| flat_top` (abierto) | se conserva | Se normaliza espacio; `flat_top` cuenta como multifocal |

**Formato del cover test:** `tipo ∈ {Orto, Endo, Exo, Hiper, Hipo}` (radio, default
`Orto`), `sub ∈ {Tropia, Foria}` (radio **sin default, opcional**). Ejemplos:
`"OD: Orto | OI: Exo y Foria"` activa exoforia en OI; `"OD: Endo y Tropia | OI: Orto"`
activa endotropia en OD; y **tipo sin sub** `"OD: Exo | OI: Orto"` activa la
correlación binocular correspondiente pidiendo precisar foria/tropia (ver §10). No
envíes cadenas sintéticas como `"exoforia en VP"`.

**Reflejos pupilares:** la UI compone `"{opción}: {nota}"`. Opciones fijas:
`"Reflejo fotomotor, consesual, acomodativo"` (normal) o `"Marcus Gunn"` (dispara DPAR).
Documenta otros hallazgos atípicos (anisocoria, midriasis) en la nota.

---

## 3. Arquitectura del paquete

La lógica está particionada por dominio clínico en [app/correlaciones/](app/correlaciones/):

| Módulo | Correlaciones | Nº |
|---|---|---|
| [fondo_de_ojo.py](app/correlaciones/fondo_de_ojo.py) | periférico, glaucoma asimétrico, glaucomatoso, ISNT violada papila, papila patológica, DMAE, macular otros, hipertensivo, vascular diabético | 9 |
| [refractivas.py](app/correlaciones/refractivas.py) | miopía magna, hipermetropía alta, anisometropía, aniseiconia queratométrica severa, astig. oblicuo, AV c/c limitada | 6 |
| [akr.py](app/correlaciones/akr.py) | espasmo acomodativo, cambio cristalino, variabilidad, astig. no prescrito | 4 |
| [corneal.py](app/correlaciones/corneal.py) | queratocono/ectasia, córnea plana extrema, astigmatismo corneal vs refractivo, astigmatismo lenticular puro | 4 |
| [anexos_cristalino.py](app/correlaciones/anexos_cristalino.py) | anexos patológicos, opacidad cristaliniana | 2 |
| [pupilas_motilidad.py](app/correlaciones/pupilas_motilidad.py) | Horner / III par sospecha, pupilas alteradas, motilidad alterada | 3 |
| [campos_amsler.py](app/correlaciones/campos_amsler.py) | campos visuales, Amsler | 2 |
| [binocularidad.py](app/correlaciones/binocularidad.py) | insuf. convergencia, PPC/exoforia, exoforia sint., endoforia sint., desviación vertical, endotropia lente, exotropia lente | 7 |
| [superficie_ocular.py](app/correlaciones/superficie_ocular.py) | BUT crítico, ojo seco evaporativo / DGM, BUT pantallas, BUT limítrofe | 4 |
| [contexto.py](app/correlaciones/contexto.py) | presbicia multifocal, presbicia sin adición, insuficiencia acomodación joven, adición incongruente con la edad, CVS, ambliopía, déficit visual inexplicado refractivo, screening adulto mayor | 8 |

Helpers compartidos: `base.py` (memoización + tipo `Correlacion`), `texto.py`
(normalización y matching), `refraccion_utils.py` (Snellen, equivalente esférico),
`queratometria.py` (lectura corneal). El orden de evaluación —invariante clínico—
vive en [registry.py](app/correlaciones/registry.py).

> **Total del registro determinista:** **49 correlaciones clínicas** activas.

> **Queratometría:** el dato corneal (K1/K2/K promedio/cilindro corneal) se usa como
> **confirmación o matiz** de las correlaciones refractivas y de AR (miopía magna,
> hipermetropía alta, AV limitada, variabilidad, astig. no prescrito). La **excepción**
> son las dos correlaciones del módulo [corneal.py](app/correlaciones/corneal.py)
> (`queratocono_ectasia_sospecha` y `astigmatismo_corneal_vs_refractivo`), que **sí
> disparan a partir del dato corneal** porque describen procesos propios (ectasia,
> astigmatismo lenticular) que ninguna otra regla cubre. Umbrales: K sospechosa
> 47.20 D, ectasia 48.70 D, cilindro corneal relevante 0.75 D, muy alto 4.00 D, córnea
> plana 41.00 D.

---

## 4. Fondo de ojo

Todas evalúan `clinica.fondo_de_ojo` con ventana de negación. Cuando coexisten,
rige la jerarquía del [Apéndice A](#apéndice-a--reglas-de-supresión-jerarquía-clínica).

### 4.1 `fondo_periferico_riesgo`
**Keywords:** desgarro, rotura/ruptura retiniana, diálisis retiniana, agujero
retiniano/atrófico/operculado, lattice, degeneración reticular/en empalizada,
empalizada, palizada, baba/huella de caracol, blanco con presión, desprendimiento de retina,
schisis, retinosquisis. **Excluye** desprendimiento de vítreo posterior (DVP) y desprendimiento
del epitelio pigmentario (DEP), que son entidades clínicas diferenciadas.
**Texto (roturas, desgarros, agujeros, desprendimiento activo):** *"Hallazgo urgente: en la retina periferica se documenta {hallazgo}, que
amerita valoracion retinologica urgente y posible tratamiento profilactico."*
**Texto (degeneración lattice / empalizada asintomática):** *"En la retina periferica se documenta {hallazgo}, hallazgo predisponente que
amerita monitorizacion preventiva y educacion sobre sintomas de alarma (fotopsias/miodesopsias)."*
**Fundamento:** la AAO PPP (*Posterior Vitreous Detachment, Retinal Breaks, and Lattice Degeneration*)
establece una distinción fundamental: los desgarros retinianos activos en herradura requieren fotocoagulación
profiláctica urgente para prevenir el desprendimiento de retina regmatógeno, mientras que la degeneración
lattice asintomática sin roturas no exige láser profiláctico de urgencia, sino monitorización y educación
sobre signos de alarma.

### 4.2 `glaucoma_asimetrico` (compuesta)
**Requiere:** `reflejos_pupilares` con `dpar`/`marcus gunn` (con negación) **y**
`fondo_de_ojo` con keyword glaucomatosa.
**Suprime:** `pupilas_alteradas`, `fondo_glaucomatoso` e `isnt_violada_papila`.
**Texto:** *"Hallazgo urgente: se documenta excavacion papilar aumentada con defecto
pupilar aferente relativo, lo que indica compromiso asimetrico del nervio optico con
probable repercusion funcional, ameritando valoracion oftalmologica priorizada."*
**Fundamento:** un DPAR (defecto pupilar aferente relativo) refleja daño asimétrico
de la vía aferente; combinado con excavación glaucomatosa sugiere neuropatía óptica
glaucomatosa avanzada y asimétrica. Al tratarse de una urgencia mayor, suprime la alerta
de neuropatía inicial para evitar contradicciones clínicas. Etiquetada **urgente**.

### 4.3 `fondo_glaucomatoso`
**Keywords:** `c/d 0.6`–`0.9`, `cup/disc 0.6`–`0.9`, `e/p 0.6`–`0.9`, `cd 0.6`–`0.9`,
excavación/excavada/excavado (excluyendo excavaciones fisiológicas normales como 0.1, 0.2, 0.3 o 0.4),
papila asimétrica, asimetría c/d, hemorragia peripapilar/en astilla,
rima neural adelgazada, adelgazamiento del anillo neurorretiniano. **Excluye** frases de normalidad como
`"regla isnt respetada"`.
**Suprimida por:** `glaucoma_asimetrico` e `isnt_violada_papila`.
**Texto:** *"Se documentan hallazgos papilares con excavacion aumentada y/o
alteracion del anillo neurorretiniano, ameritando valoracion oftalmologica con
tonometria y perimetria para descarte de glaucoma."*
**Fundamento:** relación copa/disco aumentada y asimetría interocular son signos de neuropatía
glaucomatosa (AAO PPP *Primary Open-Angle Glaucoma*). Excavaciones fisiológicas ≤ 0.4 son la norma
poblacional (Blue Mountains / Rotterdam Study) y no disparan sospecha.

### 4.4 `isnt_violada_papila`
**Keywords:** regla isnt violada, violacion regla isnt, violacion de la regla isnt,
anillo temporal mas grueso, muesca inferior, escotadura inferior, notch inferior,
muesca superior, escotadura superior, notch superior.
**Suprime a:** `fondo_glaucomatoso` (aporta la máxima especificidad focal, evitando duplicación en el informe).
**Suprimida por:** `glaucoma_asimetrico`.
**Texto:** *"Se documenta alteracion focal del anillo neurorretiniano con violacion de la
regla ISNT en la papila optica, hallazgo sugestivo de neuropatia glaucomatosa inicial
que amerita tonometria y perimetria priorizada."*
**Fundamento:** la regla ISNT describe el grosor normal del anillo neurorretiniano
(Inferior ≥ Superior ≥ Nasal ≥ Temporal). Su violación focal (típicamente muesca o notch
inferior/superior) es el biomarcador más precoz de daño glaucomatoso incipiente (Jonas et al.).

### 4.5 `papila_patologica`
**Keywords:** palidez papilar/de papila, papila pálida, disco pálido, atrofia
óptica/papilar/del nervio óptico, neuritis óptica, neuropatía óptica. **Variante
urgente (edema):** edema de papila/papilar/del disco, papiledema (palabra completa, excluyendo
pseudopapiledema), papila/disco edematoso, borramiento de bordes, bordes borrosos/difuminados/mal definidos,
márgenes borrosos, límites borrosos.
**Coexiste** con `fondo_glaucomatoso` (etiologías distintas del nervio óptico).
**Texto base:** *"Se documenta alteracion del nervio optico no asociada a excavacion
glaucomatosa, ameritando valoracion neurooftalmologica para caracterizacion
etiologica."*
**Variante urgente** (papiledema/edema/bordes borrosos): *"Hallazgo urgente: los
hallazgos del nervio optico documentados son compatibles con edema de papila, lo que
amerita evaluacion neurooftalmologica urgente para descarte de hipertension
intracraneal."*
**Fundamento:** el papiledema bilateral obliga a descartar hipertensión
intracraneal urgente; el pseudopapiledema (variante benigna o por drusas papilares) se
excluye para evitar derivaciones erróneas.

### 4.6 `fondo_macular_dmae`
**Keywords:** drusas/drusa/drusen (excluyendo drusas de papila o disco óptico), alteración/cambios
pigmentarios maculares, atrofia del EPR, hiperplasia del EPR, atrofia geográfica, membrana
neovascular coroidea, mnvc, cnv, mev, epiteliopatía macular, dmae, dmre, degeneración macular senil.
**Texto:** *"Se documentan hallazgos maculares degenerativos en fondo de ojo,
ameritando OCT macular para caracterizacion y monitorizacion."*
**Fundamento:** drusas maculares y alteraciones del EPR definen DMAE (AREDS2); las drusas de papila
son una entidad del nervio óptico y se excluyen de la maculopatía.

### 4.7 `fondo_macular_otros`
**Keywords:** edema macular, membrana epirretiniana/epiretiniana, mer, gliosis
macular/premacular, pucker, tracción vitreomacular, agujero macular, quiste macular,
coroidopatía serosa, corio(r)retinopatía serosa, crsc, cscr, emq.
**Texto:** *"En la region macular se documenta alteracion estructural que amerita
OCT y valoracion retinologica."*
**Fundamento:** membrana epirretiniana, agujero macular y coriorretinopatía serosa
central son maculopatías estructurales no degenerativas que el OCT resuelve.

### 4.8 `fondo_hipertensivo`
**Keywords:** cruces arteriovenosos/AV, signo de Gunn/Salus/Bonnet,
estrechamiento/adelgazamiento arteriolar, relación A/V disminuida, hilos/alambre de
cobre/plata, algodonoso con signos hipertensivos, ingurgitación venosa, **hemorragia en llama/flama**,
retinopatía hipertensiva. **Excluye** tortuosidad vascular aislada (frecuente variante congénita benigna).
**Texto:** *"Se documentan hallazgos vasculares en fondo de ojo con alteraciones
arteriovenosas, ameritando correlacion con cifras tensionales sistemicas."*
**Fundamento:** cruces AV patológicos y hemorragias en llama son signos de retinopatía hipertensiva
(Keith-Wagener-Barker / Mitchell-Wong); la tortuosidad aislada sin esclerosis arteriolar es benigna.

### 4.9 `fondo_vascular_diabetico`
**Keywords:** microaneurisma(s), exudado duro, hemorragia retiniana/intra(r)retiniana/en
mancha/puntiforme/en punto, neovas, rubeosis, retinopatía diabética, RDNP, RDP,
arrosariamiento/rosario venoso, IRMA.
**Coexistencia completa (sin supresión indebida):** la retinopatía diabética es una
microangiopatía metabólica sistémica independiente. **NO** se suprime frente a
hallazgos mecánicos, degenerativos o neuropáticos (`fondo_periferico_riesgo`,
`fondo_glaucomatoso`, `fondo_macular_dmae`, `fondo_macular_otros`, `fondo_hipertensivo`).
Ambas condiciones coexisten en el prompt y en `correlaciones_activadas`.
**Texto:** *"Se documentan hallazgos vasculares en fondo de ojo con presencia de
alteraciones microvasculares, ameritando correlacion sistemica (control glucemico) y
valoracion retinologica."*
**Fundamento:** microaneurismas, exudados duros y hemorragias intrarretinianas son
signos de retinopatía diabética (escala ETDRS); la neovascularización/rubeosis marca
la forma proliferativa. Requiere estricta correlación glucémica sistémica. Manchas algodonosas
aisladas sin signos microvasculares diabéticos no fuerzan la presunción de diabetes descompensada.

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
**Condición:** `EE ≥ +5.00 D` **y** componente esférico `≥ +3.00 D` en al menos un ojo.
Modulada por edad. El piso de esfera evita clasificar como "hipermetropía alta" a un
**gran astígmata** (p. ej. `+1.00 esf −8.00 cil`, EE +5.00) cuyo riesgo de cierre
angular/acomodativo lo determina la esfera, no el cilindro.
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
**Modulación por edad:** si `edad ≤ 8` (periodo de maduración visual), el texto añade
una advertencia de **riesgo de ambliopía** y necesidad de corrección óptica temprana;
en el adulto el mensaje se limita al impacto fusional/aniseicónico.
**Texto:** *"Existe anisometropia moderada por diferencia de equivalente esferico de
2.50D entre OD (-1.00) y OI (-3.50); con posible impacto en la fusion binocular."*
La queratometría añade asimetría corneal interocular si aplica.
**Fundamento:** la anisometropía significativa induce aniseiconia y dificultad
fusional; el riesgo de **ambliopía es pediátrico** (hasta ~8–9 años). El umbral
ambliogénico depende del tipo (esférica hipermetrópica >1 D, esférica miópica >2 D,
astigmática >1.5 D); el sistema usa el umbral general de 1 D sobre el equivalente
esférico. Diferencias >3 D o antimetropía suelen requerir lente de contacto.

### 5.4 `aniseiconia_queratometrica_severa`
**Condición:** anisometropía significativa concomitante con una diferencia de K promedio
interocular **≥ 1.50 D** en la queratometría.
**Texto:** *"La asimetria queratometrica interocular significativa (2.25D) sugiere que la
anisometropia posee un fuerte componente corneal, lo que predispone a aniseiconia
sintomatica con lentes aereos; se sugiere considerar la adaptacion de lentes de contacto
para optimizar la fusion binocular."*
**Fundamento:** según la ley de Knapp y la óptica fisiológica, una anisometropía de origen
corneal/refractivo corregida con gafas aéreas genera una marcada disparidad en el tamaño de las
imágenes retinianas (aniseiconia de ~1.5% por cada dioptría de diferencia). Diferencias corneales
≥ 1.50 D frecuentemente superan el límite de fusión sensorial (3-5%), provocando astenopia
severa, diplopía y supresión; la adaptación de lentes de contacto minimiza la distancia al
vértice y normaliza el tamaño retiniano de la imagen.

### 5.5 `astig_oblicuo`
**Condición:** `|cilindro| > 2.00 D` **y** eje oblicuo (20–70° o 110–160°) en la Rx
final. La queratometría solo **confirma** (cilindro corneal ≥ 1.00 D con eje
coincidente ±20°), no dispara.
**Texto:** *"OD (-2.50 x 45): astigmatismo elevado con eje oblicuo[ confirmado por
queratometria]."* Severidad: elevado (`≤3`), alto (`≤4`), muy alto (`>4`).
**Fundamento:** el astigmatismo oblicuo de alta magnitud degrada más la agudeza y la
adaptación que el astigmatismo a favor/en contra de la regla; anticipa periodo de
adaptación al lente.

### 5.6 `av_cc_limitada`
**Condición:** denominador Snellen equivalente **> 25** en al menos un ojo (es decir
**20/30 o peor**; 20/20 y 20/25 se consideran dentro de límites normales y no
activan). Categorías: 20/26–30 leve, 20/31–50 moderada, 20/51–100 marcada, >20/100
déficit severo.
**Formatos aceptados:** el parser interpreta **pie** (`20/40`), **métrica** (`6/12`) y
**decimal** (`0.5` / `0,5`) y los convierte al denominador equivalente en pie.
Notaciones no interpretables (CF, MM, cuenta dedos) se conservan pero no disparan AV.
**Texto:** *"OD (20/40): reduccion moderada de la agudeza visual con correccion."*
Con irregularidad corneal, añade nota sobre superficie corneal.
**Fundamento:** la AV con corrección subnormal cuantifica el déficit funcional con
independencia de la causa; coexiste con la correlación patológica que lo explique
(catarata, DMAE, glaucoma) sin redundar —por eso `opacidad_cristaliniana` no
menciona la AV. El corte en 20/30 evita marcar como déficit una AV de 20/25
prácticamente normal (y evitar así el screening del adulto mayor por ese motivo).

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
**Condición:** discrepancia `≥ 1.50 D` en esfera o cilindro entre AR y Rx, y **no**
activaron 6.1 ni 6.2.
**Texto:** *"Se documenta discrepancia entre autorrefractometro y refraccion final,
compatible con variabilidad refractiva durante la exploracion."* (Con irregularidad
corneal añade la nota queratométrica.)
**Fundamento:** el umbral es **1.50 D** (no 1.00 D) a propósito: los
autorrefractómetros sobre-miopizan de forma rutinaria ~0.50–1.00 D respecto a la
refracción subjetiva, de modo que una discrepancia menor es comportamiento normal del
instrumento, no un hallazgo. Los patrones etarios específicos (espasmo, cambio
cristalino) conservan umbrales más sensibles porque orientan a una causa concreta.

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

## 6b. Córnea / queratometría como disparador

Las cuatro correlaciones del módulo [corneal.py](app/correlaciones/corneal.py) son la
**excepción** a la regla "la queratometría solo confirma o matiza": aquí el dato
corneal **dispara de forma independiente**, porque describe un proceso propio que
ninguna otra regla cubre. Solo aplican si hay valores queratométricos.

### 6b.1 `queratocono_ectasia_sospecha`
**Condición:** la queratometría sugiere irregularidad corneal en algún ojo, es decir
`K_max ≥ 48.70 D` (ectasia), **o** `K_max ≥ 47.20 D` con cilindro corneal ≥ 1.50 D (o
sin cilindro medido), **o** cilindro corneal ≥ 4.00 D. (Reutiliza la misma lógica que
ya se usaba para suprimir `ar_rx_cambio_cristalino` y el screening del adulto mayor.)
**Texto:** *"La queratometria documenta curvatura corneal pronunciada o cilindro
corneal elevado en OD (Kmax 49.00D, cilindro corneal 2.00D), hallazgo compatible con
irregularidad de la superficie corneal o posible ectasia que amerita
topografia/tomografia corneal para descarte de queratocono."*
**Coexiste** con la nota corneal que ya añaden `miopia_magna`/`hipermetropia_alta`; el
LLM integra ambas sin duplicar la recomendación de topografía.
**Fundamento:** una curvatura corneal muy pronunciada o un astigmatismo corneal muy
alto son signos de sospecha de queratocono/ectasia; el estándar de caracterización es
la topografía/tomografía corneal. Es tamizaje, no diagnóstico (no etiquetado urgente).

### 6b.2 `cornea_plana_extrema`
**Condición:** K promedio (o K1 si K promedio es nulo) **< 40.00 D** en al menos un ojo.
**Texto:** *"La queratometria revela curvatura corneal marcadamente plana en OD (38.50D),
variante anatomica de relevancia refractiva que amerita valoracion del segmento anterior
y monitorizacion biometrica."*
**Fundamento:** una curvatura queratométrica inferior a 40.00 D se sitúa a más de 2.5
desviaciones estándar por debajo de la media poblacional (~43.50 ± 1.50 D). Este hallazgo
constituye una bandera roja que sugiere fuertemente: 1) antecedente de cirugía refractiva
corneal ablativa previa (LASIK/PRK/SMILE miópico), lo que invalida fórmulas biométricas
estándar de cálculo de lente intraocular; 2) córnea plana congénita (autosómica recesiva/dominante,
asociada a microftalmos y cierre angular); o 3) alteraciones anatómicas del segmento anterior.

### 6b.3 `astigmatismo_corneal_vs_refractivo`
**Condición:** en algún ojo, con cilindro refractivo prescrito **≥ 0.75 D** y cilindro
corneal presente, existe **discrepancia de magnitud** (`| |cil_corneal| − |cil_Rx| | ≥
1.25 D`) **o de eje** (ambos cilindros ≥ 1.00 D y diferencia de eje ≥ 15°). El caso de
"Rx sin cilindro y AR sí" lo cubre `ar_detecta_astigmatismo_no_prescrito`, no esta
regla (por eso exige Rx con cilindro real).
**Suprimida por:** `astigmatismo_lenticular_puro` (cuando la córnea es esférica ≤ 0.50 D,
aplica la regla más específica).
**Texto:** *"Se documenta discrepancia entre el astigmatismo corneal queratometrico y
el cilindro refractivo prescrito en OD (cilindro refractivo -0.75D vs cilindro corneal
3.00D), lo que puede corresponder a un componente astigmatico lenticular o ameritar la
revision de la transposicion y el registro del cilindro en la refraccion final."*
**Fundamento:** el astigmatismo refractivo ≈ astigmatismo corneal + componente
lenticular (regla de Javal, ~0.5 D ATR fisiológico); una discrepancia mayor orienta a
astigmatismo lenticular relevante **o a un error de transposición/registro del cilindro
en la receta**. El umbral de magnitud (1.25 D) es generoso para no marcar el componente
lenticular fisiológico.

### 6b.4 `astigmatismo_lenticular_puro`
**Condición:** superficie corneal queratométricamente esférica o casi esférica
(cilindro corneal **≤ 0.50 D**) combinada con un astigmatismo refractivo prescrito o
detectado por autorrefractómetro **≥ 1.50 D**.
**Suprime a:** `astigmatismo_corneal_vs_refractivo`.
**Texto:** *"Se documenta astigmatismo refractivo relevante en presencia de una superficie
corneal queratometricamente esferica en OD (cilindro refractivo 2.00D vs cilindro corneal 0.25D),
lo que confirma un origen cristaliniano/interno del defecto y amerita valoracion del
segmento anterior para descartar asimetria cristaliniana o ectopia lentis."*
**Fundamento:** en ausencia de astigmatismo en la superficie corneal anterior (≤ 0.50 D),
la presencia de astigmatismo refractivo moderado o alto es de origen puramente interno/cristaliniano.
Permite identificar tempranamente opacidades corticales o nucleares con asimetría de índice,
inclinación (*tilt*) cristaliniano o subluxación lenticular precoz (síndrome de Marfan,
pseudoexfoliación, microesferofaquia).

---

## 7. Anexos oculares y cristalino

### 7.1 `anexos_patologicos`
**Keywords:** blefaritis, meibomitis / disfunción de meibomio / DGM, chalazión
(calacio), orzuelo (perrilla), pterigión/pterigio (carnosidad), pinguécula,
conjuntivitis, hiperemia / inyección conjuntival/ciliar, queratitis, queratopatía
punteada/bullosa, erosión / abrasión corneal / defecto epitelial, leucoma, nubécula,
opacidad/edema corneal, distiquiasis, triquiasis, ectropión, entropión, ptosis,
dermatochalasis, lagoftalmos, madarosis, dacriocistitis, xantelasma. Aplica negación y
deduplica.
**Texto:** *"En anexos oculares se documenta {hallazgos}."* (Si `horner_o_tercer_par_sospecha` se encuentra activa, la ptosis se purga de esta lista para evitar duplicaciones clínicas contradictorias).
**Fundamento:** la blefaritis y la disfunción de glándulas de Meibomio son causa
mayor de ojo seco evaporativo (TFOS DEWS II); el pterigión y las alteraciones
palpebrales tienen implicación refractiva y de superficie.

### 7.2 `opacidad_cristaliniana`
**Campos:** `anexos_oculares` + `fondo_de_ojo` concatenados (flexibilidad práctica
del registro).
**Keywords:** catarata(s), opacidad cristaliniana/del cristalino/lenticular/subcapsular,
facoesclerosis, esclerosis nuclear, nucleoesclerosis, esclerosis del cristalino,
pseudofaquia, pseudofaco, pseudofáquico, lente intraocular / IOL, afaquia, afáquico.
**Texto (cristalino biológico / catarata):** *"Se documenta alteracion del cristalino, ameritando evaluacion
biomicroscopica para caracterizacion y estadificacion de la opacidad."*
**Texto (pseudofaquia / lente intraocular):** *"Se documenta condicion de pseudofaquia/lente intraocular,
ameritando evaluacion biomicroscopica para verificar la posicion del lente y descartar opacificacion capsular posterior."*
**Fundamento:** la catarata biológica se gradúa por biomicroscopía (LOCS III); en el ojo pseudofáquico,
el cristalino ya fue sustituido por un LIO, por lo que la monitorización se orienta a la cápsula posterior
(perlas de Elsching / fibrosis capsular subsidiaria de capsulotomía láser YAG) y no a "estadificar la opacidad".

---

## 8. Pupilas y motilidad

### 8.1 `horner_o_tercer_par_sospecha` (urgencia neurooftalmológica)
**Condición:** presencia simultánea de alteración pupilar patológica (`reflejos_pupilares` con
anisocoria, midriasis, pupila fija/arreactiva o DPAR) **y** ptosis palpebral en `anexos_oculares`.
**Suprime a:** `pupilas_alteradas` (para evitar duplicar la alarma neurooftalmológica) y purga la ptosis de `anexos_patologicos`.
**Texto:** *"Hallazgo urgente: la presencia simultanea de alteracion pupilar y ptosis palpebral
sugiere compromiso de la inervacion simpatica u oculomotora (sospecha de sindrome de Horner
o paresia del III par craneal), ameritando valoracion neurooftalmologica urgente."*
**Fundamento:** la combinación de ptosis y alteración pupilar es un signo clásico y crítico
en neurooftalmología: 1) ptosis + miosis/anisocoria sugiere síndrome de Horner ipsilateral
(afectación de la vía oculosimpática, requiriendo angio-TAC o angio-RM urgente para descartar
disección de arteria carótida interna, aneurisma o tumor apical de Pancoast); 2) ptosis +
midriasis/anisocoria sugiere parálisis del tercer par craneal (nervio oculomotor) con
compromiso pupilar, emergencia médica que exige descartar un aneurisma compresivo de la arteria
comunicante posterior antes de que se produzca una rotura hemorrágica subaracnoidea letal.
Etiquetada **urgente**.

### 8.2 `pupilas_alteradas`
**Keywords:** anisocoria, midriasis, miosis, DPAR/RAPD/defecto pupilar aferente,
Marcus Gunn, no reactivo/a, arreactiva, pupila fija, hiporreactiva, irregular,
discoria, corectopia, pupila tónica/Adie, reflejo pupilar ausente. **Excluye** anisocoria
calificada en la misma cláusula de *fisiológica/benigna/simple/esencial* (aun con modificadores no adyacentes),
y **excluye midriasis/miosis farmacológica** (calificadores como *farmacológica, post-dilatación,
bajo dilatación, midriáticos, cicloplejia, tropicamida, fenilefrina, pilocarpina*). El token `"ausente"` aislado
se eliminó del catálogo de keywords para evitar falsos positivos ante frases comunes como `"Anisocoria ausente"`.
**Suprimida por:** `glaucoma_asimetrico` y `horner_o_tercer_par_sospecha`.
**Texto base:** *"En la exploracion pupilar se documenta {hallazgos}, lo que amerita
valoracion neurooftalmologica."* **Variante urgente (DPAR/Marcus Gunn):** añade
*"Hallazgo urgente: la presencia de defecto pupilar aferente relativo es indicativa de
patologia de via optica y requiere evaluacion urgente."*
**Fundamento:** el DPAR localiza daño asimétrico de vía óptica aferente (urgente); la
anisocoria fisiológica afecta al ~15–30 % de la población y es benigna, por eso se
excluye cuando el clínico la califica como tal.

### 8.3 `motilidad_alterada`
**Keywords:** limitación, movimientos/ducciones/versiones limitadas, mirada limitada,
paresia/parético, parálisis/paralítico, oftalmoparesia, restricción, incomitancia/
incomitante, nistagmo/nistagmus, tortícolis, posición compensadora, dolor con/al
movimiento, sobreacti, hiperfunción, hipoacción/hipofunción, sincinesia, Duane,
oftalmoplejia/oftalmoplegia. **Excluye explícitamente el nistagmo optocinético** (`"optocinetico"`).
**Texto:** *"Se documenta alteracion de la motilidad ocular, lo que amerita estudio
de vias motoras y posible interconsulta neurooftalmologica."*
**Fundamento:** limitaciones y paresias sugieren afectación de pares craneales
III/IV/VI o restricción mecánica; el nistagmo patológico orienta a causas neurológicas
o vestibulares. El nistagmo optocinético es un reflejo fisiológico involuntario normal
que certifica la integridad de las vías visuales y motoras subcorticales.

---

## 9. Campos visuales y test de Amsler

### 9.1 `campos_visuales_alterados`
**Keywords positivas:** escotoma, defecto, hemianopsia/hemianopia,
cuadrantopsia/cuadrantanopsia/cuadrantanopia, escalón nasal, constricción, restricción,
campo reducido, reducción/estrechamiento del campo, visión/campo tubular, alteración,
no responde.
**Negación:** ventana de negación **por oración** (misma mecánica que fondo/pupilas).
Ya **no** hay bloqueo global del campo por la palabra `normal`: una normalidad parcial
(*"escotoma en OD, resto del campo normal"*) no suprime el hallazgo positivo. Un campo
verdaderamente normal no dispara simplemente porque no contiene ninguna keyword
positiva; y *"sin escotoma"*, *"campo normal sin defectos"* se niegan por oración.
**Texto:** *"La confrontacion de campos visuales revela alteracion que amerita
perimetria automatizada para caracterizacion del defecto."*
**Fundamento:** el patrón del defecto localiza la lesión (hemianopsia → vía
retroquiasmática; escotoma central → mácula/nervio); la confrontación es de cribado
y la perimetría automatizada la caracteriza.

### 9.2 `amsler_alterado`
**Keywords positivas:** distorsión, metamorfopsia, micropsia, macropsia, escotoma
central, escotoma, alterado, alteración, ondulación, líneas torcidas/onduladas/
distorsionadas/quebradas, área/zona faltante.
**Negación:** ventana de negación **por oración** (sin bloqueo global por `normal`).
*"Metamorfopsia central en OI, resto normal"* dispara; *"amsler negativo"* / *"sin
distorsion"* no.
**Texto:** *"El test de Amsler revela alteracion compatible con patologia macular
funcional que amerita OCT macular."*
**Fundamento:** la metamorfopsia en la rejilla de Amsler es marcador funcional de
patología macular (DMAE exudativa, MER, edema); indica OCT macular.

---

## 10. Binocularidad y convergencia

Jerarquía: `insuficiencia_convergencia` (compuesta) suprime `ppc_exoforia` y
`cover_exoforia_sintomatica`.

> **Cover test con tipo sin clasificar (sub opcional).** El sub `Tropia`/`Foria` es un
> radio **sin default**: el optometrista puede elegir `Endo/Exo/Hiper/Hipo` y dejar el
> sub en blanco (`"OD: Exo | OI: Orto"`). Ese estado es un dato de dropdown real, así
> que **sí dispara** la correlación binocular correspondiente, con un texto que pide
> precisar foria/tropia — pero **nunca** se interpreta como tropía manifiesta: un tipo
> sin sub no activa `endotropia_lente`/`exotropia_lente`, `insuficiencia_convergencia`
> (que exige exoforia clasificada) ni el factor-tropía de `ambliopia_sospecha`. Esas
> reglas de mayor confianza siguen exigiendo el sub explícito. El default
> `"OD: Orto | OI: Orto"` no dispara nada.

> **Umbral de PPC dependiente de la edad.** El punto próximo de convergencia se aleja
> fisiológicamente con la edad, así que el corte de "alejado" **no** es fijo: `> 6 cm`
> si `edad < 40` (criterio CITT para pre-présbitas) y `> 10 cm` si `edad ≥ 40` o si la
> edad es desconocida (corte conservador para no sobre-disparar en un posible présbita).
> Esto corrige el punto ciego previo, donde un joven con PPC de 8–9 cm (claramente
> patológico) no disparaba nada. Aplica a `insuficiencia_convergencia` y `ppc_exoforia`.

### 10.1 `insuficiencia_convergencia` (compuesta)
**Requiere:** PPC alejado (umbral por edad, ver recuadro), `cover_test` con exoforia, y
**demanda de visión próxima**, que puede provenir del `motivo_consulta` (lectura, leer,
estudiar, cerca, visión próxima/cercana, trabajo de cerca, computadora, pantalla,
celular, escribir, astenopia, fatiga, cefalea) **o de la `ocupacion`** (estudiante,
oficinista, programador, contador, capturista, diseñador, costurera, relojero,
dentista…). Así, un trabajo intensivo de cerca aporta el contexto aunque el motivo venga
genérico.
**Texto:** *"La combinacion de punto proximo de convergencia alejado, exoforia y
sintomatologia de vision proxima es compatible con insuficiencia de convergencia,
ameritando evaluacion binocular completa para confirmar el diagnostico y plantear
terapia visual si procede."*
**Fundamento:** la insuficiencia de convergencia (PPC alejado + exoforia mayor en
visión próxima + síntomas astenópicos de lectura) responde a terapia visual con
ejercicios de vergencia (Convergence Insufficiency Treatment Trial, CITT). El criterio
CITT fija el punto de ruptura del PPC anormal en **≥ 6 cm** para pre-présbitas.

### 10.2 `ppc_exoforia`
**Activa con:** PPC alejado (umbral por edad, ver recuadro) **o** `cover_test` con
exoforia **o** `Exo` sin clasificar. **Suprimida por:** insuf. convergencia.
**Texto:** *"El paciente presenta {punto proximo de convergencia alejado (X cm)}[ y
{exoforia en vision proxima/lejana | tendencia divergente en el cover test |
exodesviacion no clasificada en el cover test (conviene precisar foria o tropia)}]."*
**Fundamento:** un PPC > 10 cm o una exoforia documentada son signos de disfunción de
vergencia que ameritan mención aun sin el cuadro sintomático completo.

### 10.3 `cover_exoforia_sintomatica`
**Requiere:** exoforia en cover + síntoma binocular (diplopía, visión doble, veo doble,
imágenes dobles, cefalea, astenopia, fatiga visual/ocular, vista cansada, cansancio
visual/ocular, ojos cansados, ardor/lagrimeo con lectura, pérdida/salto del renglón,
salto de letras, se juntan las letras, letras que bailan/se mueven, dificultad para
enfocar, mareo al leer, sueño al leer, visión borrosa intermitente). **Suprimida por:**
insuf. convergencia.
**Texto:** *"Se documenta exoforia con sintomatologia binocular asociada, compatible
con disfuncion binocular de tipo divergente que amerita evaluacion funcional."*
**Fundamento:** una exoforia descompensada sintomática configura disfunción binocular
divergente subsidiaria de estudio funcional.

### 10.4 `cover_endoforia_sintomatica`
**Requiere:** endoforia (o `Endo` sin clasificar), NO endotropia, + síntoma binocular.
**Texto:** *"Se documenta {endoforia | una endodesviacion no clasificada en el cover
test} con sintomatologia binocular asociada, compatible con exceso de convergencia o
disfuncion acomodativa que amerita evaluacion funcional."*
**Fundamento:** la endoforia sintomática orienta a exceso de convergencia o disfunción
acomodativa (relación AC/A alterada).

### 10.5 `desviacion_vertical`
**Keywords:** hiperforia, hipoforia, hipertropia, hipotropia; o `Hiper`/`Hipo` sin
clasificar.
**Texto (solo forias):** *"Se documenta hiperforia, que puede generar sintomatologia
binocular especifica y amerita cuantificacion prismatica para evaluar compensacion."*
**Texto (tropías):** *"…que representa una desviacion manifiesta y amerita
cuantificacion prismatica inmediata con evaluacion binocular completa."*
**Texto (tipo sin clasificar):** *"Se documenta una desviacion vertical no clasificada
en el cover test, que puede generar sintomatologia binocular especifica…"* (cierre de
foria, no de tropía manifiesta).
**Fundamento:** las desviaciones verticales, aun pequeñas, son mal toleradas y
generan astenopia/diplopía; la tropía manifiesta es más urgente que la foria latente.

### 10.6 `endotropia_lente`
**Requiere:** endotropia manifiesta en cover test.
**Texto:** *"Se documenta endotropia en el cover test, ameritando evaluacion de la
respuesta a la correccion optica prescrita, con cover test bajo correccion para
clasificar el tipo de desviacion."*
**Fundamento:** la endotropía puede ser acomodativa (total o parcialmente corregida
por la Rx hipermetrópica); el cover test bajo corrección clasifica el componente motor y acomodativo
independientemente de si el paciente ha seleccionado un diseño de lente específico en el formulario.

### 10.7 `exotropia_lente`
**Requiere:** exotropia manifiesta en cover test.
**Texto:** *"Se documenta exotropia en el cover test, ameritando evaluacion binocular
completa para determinar frecuencia y magnitud de la desviacion, asi como la
respuesta a la correccion optica prescrita."*
**Fundamento:** la exotropía intermitente requiere caracterizar frecuencia/magnitud y
control de fusión para decidir manejo óptico, prismático o quirúrgico.

---

## 11. Superficie ocular — tiempo de ruptura lagrimal (BUT) y glándulas de Meibomio

### 11.1 `but_critico`
**Condición:** `ojo_seco_but_seg < 5`.
**Texto:** *"El tiempo de ruptura lagrimal de {X}s es patologicamente bajo, compatible
con ojo seco clinico que amerita evaluacion."*
**Fundamento:** un BUT < 5 s indica inestabilidad grave de la película lagrimal
(criterio de ojo seco, TFOS DEWS II, donde BUT < 10 s ya es reducido).

### 11.2 `ojo_seco_evaporativo_dgm`
**Condición:** presencia de compromiso en borde palpebral o glándulas de Meibomio en
`anexos_oculares` (blefaritis, meibomitis, disfunción de glándulas de Meibomio, DGM, telangiectasias
o collaretes) **concomitante con** tiempo de ruptura lagrimal reducido (`ojo_seco_but_seg < 10 s`).
**Excluye:** casos donde las glándulas de Meibomio se reportan explícitamente como normales o permeables
(en tal caso, un BUT bajo se orienta a deficiencia acuosa o mucínica pura).
**Texto:** *"La presencia de alteracion en glandulas de Meibomio o blefaritis asociada a un
tiempo de ruptura lagrimal reducido configura un cuadro compatible con ojo seco de predominio
evaporativo, ameritando manejo dirigido a la superficie palpebral y estabilidad lagrimal."*
**Fundamento:** el reporte internacional TFOS DEWS II (*Tear Film & Ocular Surface Society Dry Eye
Workshop II*) establece que la disfunción de glándulas de Meibomio (DGM) es la causa principal del
ojo seco evaporativo a nivel mundial (>85% de los casos). Si las glándulas son normales, la inestabilidad
no debe atribuirse a evaporación por meibomitis.

### 11.3 `but_pantallas`
**Condición:** `5 ≤ BUT ≤ 9` **y** `uso_pantallas ∈ {btw2_6, gt6}`.
**Texto:** *"El tiempo de ruptura lagrimal de {X} segundos es reducido en el contexto
del uso de pantallas, lo que indica inestabilidad de la pelicula lagrimal."*
**Fundamento:** el uso intensivo de pantallas reduce la tasa de parpadeo y agrava la
inestabilidad lagrimal (componente evaporativo del síndrome visual informático).

### 11.4 `but_limitrofe`
**Condición:** `5 ≤ BUT ≤ 9` **y** `uso_pantallas` nulo o `lt2`.
**Texto:** *"El tiempo de ruptura lagrimal de {X}s se encuentra en rango suboptimo,
sugiriendo inestabilidad leve de la pelicula lagrimal."*
**Fundamento:** un BUT en rango suboptimo sin exposición alta a pantallas indica
inestabilidad leve, subsidiaria de vigilancia.

---

## 12. Edad, lente y pantallas

### 12.1 `presbicia_multifocal`
**Activa con:** (`edad >= 40` o `edad is None`) **y** (`tipo_lente` multifocal/bifocal/progresivo/**flat_top** **o** hay `add` prescrita).
**Protección pediátrica/juvenil:** En menores de 40 años **no activa** presbicia; si hay adición prescrita,
se canaliza a través de `insuficiencia_acomodacion_joven` o `adicion_incongruente_edad` para evitar contradicciones clínicas.
**Texto (con adición):** *"El paciente de {X} anos presenta reduccion fisiologica de la
amplitud acomodativa propia de la edad, lo que justifica la adicion prescrita[ y el
lente multifocal indicado]."*
**Texto (sin adición):** *"El paciente de {X} anos presenta reduccion fisiologica de la
amplitud acomodativa propia de la edad, lo que justifica el diseno multifocal indicado."*
**Fundamento:** la presbicia es la reducción fisiológica progresiva de la amplitud
acomodativa a partir de ~40 años; justifica la adición y el diseño multifocal.

### 12.2 `cvs_sospecha`
**Requiere:** `uso_pantallas ∈ {btw2_6, gt6}` + `motivo_consulta` con síntomas específicos:
ardor/sequedad ocular, ojo seco, resequedad, arenilla, cuerpo extraño, astenopia, fatiga/cansancio
visual/ocular, dolor ocular, cefalea asociada a pantallas, picazón/comezón, lagrimeo o dificultad para enfocar.
**Excluye:** la `"vision borrosa"` genérica aislada (atribuible a vicios de refracción generales).
**Texto:** *"El perfil de uso de pantallas se correlaciona con la sintomatologia
visual referida, compatible con sindrome visual informatico, ameritando
recomendaciones ergonomicas y eventual correccion optica para vision intermedia."*
**Fundamento:** el síndrome visual informático (digital eye strain) combina fatiga
acomodativa, disfunción lagrimal y ergonomía; el síntoma cardinal es la astenopia o sequedad, no la borrosidad no corregida.

### 12.3 `presbicia_sin_adicion`
**Requiere:** `edad ≥ 45`, refracción de distancia presente (alguna esfera o cilindro),
**sin** adición prescrita en ningún ojo y lente **no** multifocal. **No dispara en el
miope funcional:** si el ojo menos miope tiene `EE ≤ −1.50 D` (ambos ojos miopes), el
paciente lee cómodamente quitándose los lentes y la falta de adición es lo esperable, no
un olvido. Es mutuamente excluyente con `presbicia_multifocal` (esta última exige
adición o diseño multifocal).
**Texto:** *"El paciente de {X} anos no presenta adicion prescrita pese a encontrarse en
el rango de edad con reduccion fisiologica de la amplitud acomodativa, por lo que
conviene verificar la necesidad de correccion para vision proxima."*
**Fundamento:** a partir de ~45 años la amplitud acomodativa suele ser insuficiente para
la visión próxima; una receta de distancia sin adición en ese rango de edad merece una
verificación explícita de la necesidad de corrección de cerca. Es un recordatorio, no
una afirmación de error.

### 12.4 `insuficiencia_acomodacion_joven`
**Condición:** paciente joven (`edad < 38 años`) con adición prescrita (`add ≥ +0.75 D`)
y presencia de síntomas de fatiga o astenopia en visión próxima en el motivo de consulta
(`astenopia`, `fatiga`, `cansancio`, `dificultad para enfocar`, `borrosa de cerca`,
`borroso al leer`, `lectura`, `cerca`, `cefalea`).
**Suprime a:** `adicion_incongruente_edad`.
**Texto:** *"El paciente de {edad} anos presenta sintomatologia astenopica en vision cercana
asociada a la prescripcion de adicion (+{add:.2f}D), patron sugestivo de insuficiencia o
disfuncion acomodativa; se recomienda evaluar la amplitud de acomodacion (metodo de Donders o
Sheard) y la flexibilidad acomodativa con flippers antes de consolidar la adicion definitiva."*
**Fundamento:** la prescripción de una adición para lectura en un no présbita sintomático orienta
a una disfunción del sistema acomodativo (insuficiencia de acomodación, fatiga o inercia
acomodativa; estudios CITT - *Convergence Insufficiency Treatment Trial* y criterios de Daum).
La adición positiva alivia la astenopia pero requiere diferenciar una verdadera hipofunción
acomodativa de una pseudomiopía o sobrecorrección miópica de lejos antes de volverla permanente.

### 12.5 `adicion_incongruente_edad`
**Requiere:** una adición prescrita **incongruente con la edad**: (a) `add` en un no
présbita (`edad < 40` con `add ≥ +0.75`), o (b) `add` por encima del rango fisiológico
para la edad (`> +3.00 D` en cualquier caso, o `> techo_edad + 0.50` donde el techo va de
`+1.25` a `< 45 años` hasta `+3.00` a `≥ 60`). Sin edad, solo aplica el techo absoluto
`> +3.00 D`. Coexiste con `presbicia_multifocal` (una justifica la adición, la otra
cuestiona su magnitud).
**Suprimida por:** `insuficiencia_acomodacion_joven` (si el paciente joven tiene síntomas
astenópicos documentados, se activa la regla específica de acomodación).
**Texto (add en no présbita):** *"Se prescribe una adicion de +X en un paciente de {edad}
anos, edad en la que la amplitud acomodativa suele ser suficiente…; conviene verificar la
indicacion (disfuncion acomodativa) o descartar una sobrecorreccion miopica de lejos."*
**Texto (sobre-adición):** *"La adicion prescrita (+X) supera el rango para la edad…;
conviene verificar la distancia de trabajo y descartar una subcorreccion hipermetropica o
una sobreestimacion de la refraccion de lejos."*
**Fundamento:** la adición sigue una progresión conocida por edad; un valor fuera de ese
rango suele delatar una refracción de lejos mal balanceada (hiper subcorregida / miopía
sobrecorregida) o una distancia de trabajo atípica. Usa `add` + `edad`, datos que ya
recolectas.

### 12.6 `ambliopia_sospecha`
**Requiere:** AV con corrección **limitada** (denominador > 25) en algún ojo, **más** un
factor ambliogénico (**anisometropía** significativa **o** una **tropía** en el cover),
**y** ausencia de causa orgánica documentada (mismo set de supresores que el screening:
opacidad, glaucomatoso, DMAE, macular otros, vascular, hipertensivo, periférico, papila,
miopía magna, irregularidad corneal). Usa `av_sc`/`av_cc` para caracterizar la respuesta
a la corrección. Coexiste con `av_cc_limitada` (una cuantifica, esta nombra el patrón).
**Texto:** *"Se documenta agudeza visual con correccion limitada en OI (20/60), con
agudeza visual sin correccion de 20/200 en presencia de anisometropia significativa,
patron compatible con ambliopia; amerita verificar el antecedente de ambliopia y la
fijacion, y descartar una causa organica no evidente en el examen actual."*
**Fundamento:** la ambliopía es una reducción de la mejor AV corregida **no atribuible a
causa estructural**, con antecedente de anisometropía o estrabismo en la infancia. El
patrón (AV corregida que no normaliza + factor ambliogénico + fondo/segmento sin causa)
es exactamente el de la ambliopía funcional; el sistema lo señala como diferencial a
verificar, no como diagnóstico. Revive el campo `av_sc`, hasta ahora sin uso.

### 12.7 `deficit_visual_inexplicado_refractivo` (red de seguridad refractiva)
**Condición:** paciente no senil (`edad < 60 años` o no especificada) con refracción prescrita
(esfera o cilindro presentes), AV sin corrección reducida (`av_sc ≤ 20/50`, denominador ≥ 50)
y agudeza visual con corrección subnormal (`av_cc ≤ 20/40`, denominador ≥ 40), en ausencia de
causa orgánica visible y sin factor ambliogénico manifiesto.
**Suprime a:** `adulto_mayor_screening`.
**Texto:** *"Se registra agudeza visual subnormal en OD con correccion (20/50) (AV sin correccion 20/100)
sin hallazgos organicos evidentes en el examen actual ni factores ambliogenicos manifiestos;
se recomienda prueba con agujero estenopeico, reevaluar refraccion bajo ciclopejia o descartar
patologia corneal o macular subclinica."*
**Fundamento:** cuando la refracción óptica óptima no logra alcanzar una agudeza visual normal
(≥ 20/30) en un paciente joven o adulto activo sin lesiones oftalmoscópicas evidentes ni estrabismo,
constituye una deficiencia visual no explicada. Las directrices de la AAO y del Consejo Internacional
de Oftalmología recomiendan: 1) prueba de agujero estenopeico (si la AV mejora, existe aberración de
alto orden o defecto refractivo no corregido); 2) refracción bajo cicloplejía (descarte de espasmo
acomodativo o hipermetropía latente); y 3) evaluación dirigida para descartar distrofia macular precoz,
ectasia corneal subclínica o neuropatía incipiente.

### 12.8 `adulto_mayor_screening`
**Requiere:** edad ≥ 60 + AV c/c limitada (`av_cc ≤ 20/30`). **Suprimida** si ya hay causa
específica documentada (opacidad cristaliniana, fondo periférico de riesgo, fondo glaucomatoso,
DMAE, macular otros, vascular diabético, hipertensivo, miopía magna, papila patológica,
irregularidad corneal queratométrica), `ambliopia_sospecha` o `deficit_visual_inexplicado_refractivo`.
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
| `glaucoma_asimetrico` | `pupilas_alteradas`, `fondo_glaucomatoso`, `isnt_violada_papila` |
| `horner_o_tercer_par_sospecha` | `pupilas_alteradas` (y purga la ptosis de `anexos_patologicos`) |
| `isnt_violada_papila` | `fondo_glaucomatoso` (mayor especificidad topográfica focal) |
| `astigmatismo_lenticular_puro` | `astigmatismo_corneal_vs_refractivo` |
| `insuficiencia_acomodacion_joven` | `adicion_incongruente_edad` |
| `insuficiencia_convergencia` | `ppc_exoforia`, `cover_exoforia_sintomatica` |
| `ar_rx_espasmo_acomodativo` / `ar_rx_cambio_cristalino` | `ar_rx_variabilidad_inespecifica` |
| causa orgánica (opacidad, periférico, glaucomatoso, DMAE, macular otros, vascular, hipertensivo, papila, miopía magna, irregularidad corneal) | `ambliopia_sospecha`, `deficit_visual_inexplicado_refractivo` |
| causa orgánica (misma lista) **o** `ambliopia_sospecha` **o** `deficit_visual_inexplicado_refractivo` | `adulto_mayor_screening` |

**Coexistencias intencionadas y cambios clave:**
- `fondo_vascular_diabetico` **NO es suprimida** por ninguna patología no vascular (periférico, glaucoma, DMAE, macular otros); coexiste libremente reflejando la patología metabólica de base.
- `papila_patologica` no se suprime con `fondo_glaucomatoso` (neuropatías distintas).
- `isnt_violada_papila` **suprime** a `fondo_glaucomatoso` para evitar duplicar el reporte papilar con dos hechos casi idénticos.
- `glaucoma_asimetrico` **suprime** a `isnt_violada_papila` para evitar la colisión contradictoria entre daño avanzado urgente y neuropatía inicial incipiente.
- `av_cc_limitada` y `opacidad_cristaliniana` coexisten (una cuantifica, la otra nombra la causa).
- `fondo_vascular_diabetico` no se suprime con `fondo_hipertensivo` (comorbilidad sistémica).
- `queratocono_ectasia_sospecha` coexiste con la nota corneal de `miopia_magna`/`hipermetropia_alta`.
- `ambliopia_sospecha` y `av_cc_limitada` coexisten (una nombra el patrón, la otra cuantifica).
- `presbicia_multifocal` exige `edad >= 40` años, eliminando contradicciones con `insuficiencia_acomodacion_joven` o `adicion_incongruente_edad` en pacientes jóvenes.

## Apéndice B — Hallazgos urgentes

Solo las correlaciones cuyo texto trae el prefijo `Hallazgo urgente:` autorizan al
LLM a usar lenguaje de urgencia; el system prompt obliga a colocar ese hallazgo en
la **segunda o tercera oración** del párrafo (y prohíbe calificar de urgente
cualquier otro):

- `fondo_periferico_riesgo` (únicamente ante desgarro, rotura, agujero o desprendimiento activo; la degeneración lattice aislada genera texto preventivo)
- `glaucoma_asimetrico` (siempre)
- `horner_o_tercer_par_sospecha` (siempre)
- `papila_patologica` (variante papiledema / edema de papila / bordes borrosos)
- `pupilas_alteradas` (cuando hay DPAR o Marcus Gunn)

## Apéndice C — Buenas prácticas para activar correctamente las correlaciones

1. **Nombra el hallazgo** con un término clínico reconocido: `"lattice"`, `"papila
   asimetrica"`, `"c/d 0.7"` (o `"e/p 0.7"`), `"microaneurismas"`. Las listas toleran
   sinónimos, coloquialismos (`"carnosidad"`, `"calacio"`, `"perrilla"`), abreviaturas
   (`"RAPD"`, `"IOL"`, `"RDNP"`) y variantes de escritura, pero una descripción
   totalmente genérica ("algo raro", "lesión") no activa nada.
2. **Separa positivos de negativos** en oraciones distintas o usa cláusulas delimitadas.
3. **Relación C/D con decimal:** `"c/d 0.7"` o `"cup/disc 0.7"` (desde 0.6; valores
   fisiológicos 0.2 o 0.3 son normales y no alertan).
4. **Cover test:** usa el formato de la UI `"OD: Tipo [y Sub] | OI: Tipo [y Sub]"`.
5. **Reflejos pupilares:** registra hallazgos atípicos en la nota libre.
6. **PPC y BUT** son enteros 1–15; fuera de rango el schema los descarta (`None`,
   coerción tolerante) y ninguna correlación de BUT/PPC dispara.
7. **Motivo de consulta:** muchas correlaciones binoculares, de pantallas y de acomodación
   dependen de palabras clave aquí (cefalea, astenopia, lectura, ardor…). Anota síntomas
   reales en lugar de "examen de rutina".
8. **AKR vs Rx:** si el AR no se midió, deja los campos nulos; valores inventados o
   iguales a la Rx no activan nada pero pueden silenciar correlaciones válidas.
9. **Edad:** modula hipermetropía alta, espasmo, cambio cristalino, presbicia, acomodación
   joven y screening. Sin fecha de nacimiento, la edad llega `null` y varias reglas se
   vuelven conservadoras.
10. **Tipo de lente:** activa la rama "con lente" de `endotropia_lente`,
    `exotropia_lente` y `presbicia_multifocal`.

## Resumen ejecutivo

- **49 correlaciones**, 10 dominios clínicos, particionadas en
  [app/correlaciones/](app/correlaciones/).
- **Determinista:** mismos datos → mismas correlaciones.
- **Jerárquica:** las específicas suprimen a las generales (Apéndice A).
- **None-safe:** campos vacíos no producen errores.
- **Texto dinámico:** muchas correlaciones citan ojo, valores y hallazgos exactos.
- **Queratometría** como confirmación/matiz en las reglas refractivas, y como
  **disparador propio** en las cuatro correlaciones córneales (`corneal.py`).
- **El LLM no decide** la correlación, solo la integra; los nombres activados se
  devuelven en `correlaciones_activadas`.
- **Blindaje:** los 49 textos están cubiertos por pruebas *golden* que impiden
  regresiones silenciosas del contenido clínico.
