# Correlaciones clínicas — catálogo de implementación

> Catálogo de las **47 correlaciones clínicas** y **1 recordatorio técnico** que la API
> evalúa de forma determinista antes de invocar al LLM. Está dirigido tanto al
> **optometrista** que llena la receta en el SaaS (para entender qué activa cada
> campo) como al **equipo técnico** (para entender el contrato de datos y el
> fundamento clínico de cada regla).
>
> **Estado 2026-09-29:** que una regla figure activa aquí no significa que esté
> clínicamente validada; este catálogo describe la implementación y sus límites. Las
> pruebas sintéticas y golden acreditan el comportamiento comprobado, sin certificar rendimiento
> clínico ni completar exploraciones no documentadas. Los
> identificadores «#N» (1–58) son los números de orden con que se especificó cada regla
> y se conservan como referencia estable, incluidos los de las reglas retiradas (que no se
> reintroducen) y la #7, fusionada en #6. El contrato autoritativo del payload sigue siendo
> [DICCIONARIO_DATOS_RECETA.md](DICCIONARIO_DATOS_RECETA.md).
>
> **Fuente de referencia en código:** el paquete [app/correlaciones/](app/correlaciones/). Este
> texto traduce esa lógica a lenguaje clínico y documenta sus fundamentos y limitaciones. Los
> textos exactos que genera cada correlación están auditados por pruebas *golden* directas
> en [tests/test_correlaciones_golden.py](tests/test_correlaciones_golden.py): si
> el texto o condición de una regla cambia sin actualizar su prueba, la suite falla.
>
> **Aviso de Soporte a la Decisión Clínica (CDS):** Este sistema asiste al optometrista y al doctor
> en la identificación y redacción estructurada de hallazgos relevantes en el punto de atención.
> No constituye un diagnóstico médico autónomo, no reemplaza la exploración física presencial
> ni sustituye el juicio clínico independiente del doctor responsable.

---

## 1. Cómo funciona

Cuando solicitas la generación de la impresión clínica, antes de invocar al
LLM el sistema corre una capa determinista que evalúa **47 reglas clínicas** sobre
los campos que escribiste. Cada regla:

1. **Lee uno o varios campos** de la receta (refracción, AKR/queratometría, fondo
   de ojo, anexos, motivo de consulta, etc.).
2. **Compara el contenido** contra umbrales numéricos o palabras clave clínicas.
3. **Si la condición se cumple**, agrega un hecho clínico pre-redactado al prompt
   del modelo, con la jerarquía correcta.

El LLM **no decide** ninguna correlación: solo integra los hechos ya evaluados al
párrafo final. La respuesta HTTP incluye además el campo `correlaciones_activadas`
con los nombres de las reglas que aplicaron, para trazabilidad.
El recordatorio técnico #29 se evalúa por una función separada y no se incorpora
a los hechos médicos del prompt ni a `correlaciones_activadas` de la respuesta.

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
ejemplo `calacio`/`perrilla` (= chalazión/orzuelo), `E/P
0.7` (= excavación/papila), `RAPD` (= DPAR), `IOL` (lente intraocular), `visión tubular`
(= constricción de campo), `veo doble`/`se juntan las letras` (síntomas binoculares).
Aun así, una descripción totalmente genérica ("lesión en periferia", "algo raro en la
mácula") no dispara: hace falta nombrar el hallazgo. Los listados por correlación de
abajo muestran keywords **representativas**, no exhaustivas. `Carnosidad`,
`hiperemia`, `erosión` o `disfunción glandular` conservan su denominación y la
anatomía escrita; no se convierten por sí solas en pterigión, lesión corneal o DGM.

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
2. **Negación sufija (pospuesta, hasta 3 palabras clínicas de contenido):** se omiten
   tokens de ojo y palabras gramaticales; comas y conectores delimitan el alcance.
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
6. **Listas coordinadas bajo un mismo negador (2026-09-29):**
   - En el extractor por ocurrencia (`pupilas_motilidad._ocurrencias_oculares`), una lista unida por
     `y`, `e`, `o` o `ni` conserva el negador de su primer elemento: *"Sin cefalea y diplopia desde hoy"*
     niega ambos síntomas. La negación **no** se hereda a través de una coma, `pero`, `con`, `sin`, `no`,
     ni entre ojos distintos (*"Sin cefalea pero con diplopia"*, *"Sin cefalea, diplopia desde hoy"* siguen
     afirmando la diplopia).
   - En `texto._is_match_negated`, *"Sin evidencia en OD ni en OI de desgarro"* es una negación bilateral
     coordinada (`ni` no es un cambio interocular); *"Sin desgarro en OD, desgarro en OI"* sigue afirmando OI.
   - `fondo_hipertensivo` (#10) aplica lo mismo a sus cláusulas (`_ClausulasHipertensivas`): *"Sin evidencia
     de estrechamiento arteriolar y hemorragias en llama"* con PA crítica ya no genera la urgencia.
7. **Ojo nombrado en otro tramo:** *"Limitación de la abducción OD, OI normal"* conserva solo OD
   (`_ojo_del_tramo`, `_NORMALIDAD_OJO_RE`); un ojo que solo aparece en tramos marcados como normales o
   negados no localiza el hallazgo (*"diplopia desde hoy, OD normal"* queda sin ojo). Sin marca de
   normalidad (elipsis *"nuclear OD, cortical OI"*, *"sin cambios en OI"*, *"OI no normal"*) se conservan
   ambos ojos.
8. **Sujeto:** `hechos_textuales._SUJETO_FAMILIAR` reconoce familiares como sujeto con cualquier verbo de
   síntoma (*se queja, comenzó, empezó…*), *"madre del paciente presenta"* (el paciente completa al familiar)
   y *"antecedente familiar"* en singular y plural. Un antecedente fechado (*"conocida desde 2020"*) no anula un
   cambio brusco actual del mismo síntoma (*"empeoró subitamente hoy"*): se describe como *empeoramiento
   reciente*, no como inicio nuevo.

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
| `paciente.edad` | int, `0..125` (calculada) | → `None` | Modula varias correlaciones; `null` → comportamiento conservador |
| `paciente.ocupacion`, `paciente.motivo_consulta` | str libre | — | Se normaliza espacio en blanco |
| `refraccion.od/oi.esfera` | dropdown `+20.00..-20.00` paso 0.25; persistencia/API hasta ±30 D | → `None` | El rango ampliado no convierte la cifra en diagnóstico ni amplía el dropdown |
| `refraccion.od/oi.cilindro` | dropdown `0.00..-8.00` paso 0.25; BD admite `-30..30` | fuera de ±30 → `None` | Rx contractual negativa; entradas positivas legacy toleradas se transponen preservando esfera ausente |
| `refraccion.od/oi.add` | input libre; `add ≤ 0` → `None` | — | `0` tecleado no es adición prescrita |
| `refraccion.od/oi.eje` | int, `0..180` en SaaS | **mod 180** para entradas toleradas | El rango del contrato es 0..180; la tolerancia API no amplía el catálogo |
| `refraccion.od/oi.av_sc`, `av_cc` | dropdown Snellen (16 valores) | se normaliza | Catálogo cerrado Snellen (`20/10`..`20/600`); el schema canoniza espacios (`20/xx`) y los parsers admiten notaciones decimales (`0.5`), métricas (`6/12`) o legacy sin rechazo |
| `akr.pd` | float (mm) | — | Distancia pupilar |
| `akr.taken_at` | fecha del ticket SQL/ISO, opcional | inválida → `None` y aviso de log | Se ignora para inferencia conforme al contrato; no hay ventana de 24 h ni fecha de Rx que acredite simultaneidad |
| `akr.vd` | float, `0..30` (mm) | → `None` | Distancia del dispositivo; no acredita los planos de la refracción subjetiva |
| `akr.ker_index` | float, `1.3..1.4` | → `None` | Índice queratométrico del equipo |
| `akr.od/oi.esfera`, `cilindro` | float (AR); transposición si plus-cyl | — | Conserva esfera ausente: no se sustituye por cero al transponer; solo se comparan componentes disponibles |
| `akr.od/oi.eje`, `k1_eje`, `k2_eje`, `k_cilindro_eje` | int, eje cíclico | **mod 180** | Ejes |
| `akr.od/oi.k1_d`, `k2_d`, `k_promedio_d` | float, `25..80` | → `None` | Poder corneal (D) |
| `akr.od/oi.k1_mm`, `k2_mm`, `k_promedio_mm` | float, `4..12` | → `None` | Radio corneal (mm) |
| `akr.od/oi.k_cilindro` | float, `-30..30` | → `None` | Diferencia queratométrica; su signo no documenta la convención angular de `k_cilindro_eje` |
| `clinica.uso_pantallas` | `"lt2"` \| `"btw2_6"` \| `"gt6"` \| null | → `None` | Enum cerrado |
| `clinica.ojo_seco_but_seg` | dropdown int `1..15` | → `None` | BUT en segundos |
| `clinica.ppc_cm` | dropdown int `1..15` | → `None` | Punto próximo de convergencia |
| `clinica.cover_test` | str, formato UI (sub **opcional**) | — | `"OD: {tipo}[ y {sub}] \| OI: {tipo}[ y {sub}]"`; `" - "` → `" y "` |
| `clinica.anexos_oculares`, `reflejos_pupilares`, `motilidad_ocular`, `confrontacion_campos_visuales`, `fondo_de_ojo`, `grid_de_amsler` | str libre | — | Hallazgos cualitativos |
| `clinica.recomendacion_seguimiento` | str libre, hasta 60000 caracteres | exceso → truncado al límite contractual | Se añade determinísticamente al final; fragmentos clínicos pertinentes pueden conservarse como contexto de los hechos |
| `tipo_lente` | enum cerrado SaaS `monofocal \| bifocal_blended \| progresivo \| flat_top` | la API conserva texto tolerado | La tolerancia no amplía el catálogo contractual ni acredita función acomodativa |

**Formato del cover test:** `tipo ∈ {Orto, Endo, Exo, Hiper, Hipo}` (radio;
sin asumir `Orto` si no se realizó), `sub ∈ {Tropia, Foria}` (radio **sin default, opcional**). Ejemplos:
`"OD: Orto | OI: Exo y Foria"` activa exoforia en OI; `"OD: Endo y Tropia | OI: Orto"`
activa endotropia en OD; y **tipo sin sub** `"OD: Exo | OI: Orto"` activa la
correlación binocular correspondiente pidiendo precisar foria/tropia (ver §10). No
envíes cadenas sintéticas como `"exoforia en VP"`.

**Reflejos pupilares:** la UI compone `"{opción}: {nota}"`. Opciones fijas:
`"Reflejo fotomotor, consensual, acomodativo"` (normal) o `"Marcus Gunn"` (dispara DPAR).
Documenta otros hallazgos atípicos (anisocoria, midriasis) en la nota.

---

## 3. Arquitectura del paquete

La lógica está particionada por dominio clínico en [app/correlaciones/](app/correlaciones/):

| Módulo | Correlaciones | Nº |
|---|---|---|
| [fondo_de_ojo.py](app/correlaciones/fondo_de_ojo.py) | periférico de riesgo, oclusión vascular urgente, émbolo retiniano, papila patológica, glaucoma asimétrico, fondo glaucomatoso (absorbe regla ISNT), DMAE macular, macular otros, síntomas tracción vitreorretiniana, fondo hipertensivo, vascular diabético | 11 |
| [refractivas.py](app/correlaciones/refractivas.py) | miopía magna, hipermetropía alta, anisometropía, astig. oblicuo, AV c/c registrada reducida | 5 |
| [akr.py](app/correlaciones/akr.py) | variabilidad inespecífica, astig. no prescrito | 2 |
| [corneal.py](app/correlaciones/corneal.py) | K elevados, medias interoculares diferentes, curvatura registrada baja, comparación de cilindro K/Rx (IDs históricos #33–36) | 4 |
| [anexos_cristalino.py](app/correlaciones/anexos_cristalino.py) / [segmento_anterior.py](app/correlaciones/segmento_anterior.py) | anexos patológicos, signos del segmento anterior y riesgo glaucoma secundario, estados del cristalino/cápsula/posición/reflejo rojo | 3 |
| [pupilas_motilidad.py](app/correlaciones/pupilas_motilidad.py) | Horner / III par sospecha, pupilas alteradas, motilidad alterada | 3 |
| [campos_amsler.py](app/correlaciones/campos_amsler.py) | campos visuales, Amsler | 2 |
| [binocularidad.py](app/correlaciones/binocularidad.py) | insuf. convergencia, PPC/exoforia, exoforia sint., endoforia sint., desviación vertical, endotropia lente, exotropia lente | 7 |
| [sintomas_agudos.py](app/correlaciones/sintomas_agudos.py) | diplopía aguda: vía independiente exigida por la retirada #27 D6 | 1 |
| [superficie_ocular.py](app/correlaciones/superficie_ocular.py) | BUT crítico, ojo seco evaporativo / DGM, BUT pantallas, BUT limítrofe | 4 |
| [contexto.py](app/correlaciones/contexto.py) | CVS, ambliopía isoametrópica bilateral, ambliopía sospecha, déficit visual inexplicado refractivo, screening adulto mayor | 5 |

Helpers compartidos: `base.py` (memoización + tipo `Correlacion`), `texto.py`
(normalización y matching), `refraccion_utils.py` (Snellen, equivalente esférico),
`queratometria.py` (lectura corneal), `hechos_textuales.py` (sujeto y modalidad por
ocurrencia, sin transferir hechos familiares ni completar cronología). El orden de evaluación —invariante clínico—
vive en [registry.py](app/correlaciones/registry.py).

> **Total del registro determinista:** **47 correlaciones clínicas** activas.
> `RECORDATORIOS_TECNICOS` contiene además #29; su evaluación permanece separada
> del catálogo médico y del prompt generativo.

> **Queratometría:** el dato corneal (K1/K2/K promedio/cilindro corneal) se usa como
> **información descriptiva**, sin confirmar causas refractivas ni explicar AV.
> Las cuatro correlaciones del módulo [corneal.py](app/correlaciones/corneal.py)
> (`queratocono_ectasia_sospecha`, `cornea_plana_extrema`, `astigmatismo_corneal_vs_refractivo`,
> `queratometria_asimetrica_interocular`) **seleccionan datos corneales propios**,
> conservando ojo, magnitud y procedencia.
> Los cortes 47,20/48,70 D, cilindro 4 D, K<38 D y diferencia de medias≥1 D son
> criterios operativos de revisión; no diagnostican ectasia, causa lenticular ni
> córnea plana hereditaria. Una K parcial no se llama media ni Kmax topográfico.

---

## 4. Fondo de ojo

Todas evalúan `clinica.fondo_de_ojo` (o `paciente.motivo_consulta` en el caso de los síntomas de tracción vítrea) con ventana de negación por cláusula. Cuando coexisten, rige la jerarquía del [Apéndice A](#apéndice-a--reglas-de-supresión-jerarquía-clínica).

### 4.1 `fondo_periferico_riesgo`
**Keywords:** desgarro (en herradura, operculado), rotura/ruptura retiniana, diálisis retiniana, agujero retiniano operculado/atrófico, degeneración lattice / en empalizada / reticular, degeneración en baba/huella de caracol, desprendimiento de retina, retinosquisis / esquisis retiniana, tracción vítrea periférica, avulsión o hemorragia vítrea periférica. **Excluye** "blanco con presión" (variante periférica inocua), desprendimiento de vítreo posterior (DVP, evaluado en síntomas de tracción) y desprendimiento del epitelio pigmentario (DEP, patología macular evaluada en §4.8 y §4.9).
**Estratificación en 6 niveles jerárquicos:**
1. **Desprendimiento de retina activo (`DR` - Urgente):**
   *"Hallazgo urgente: en la retina periferica se documenta desprendimiento de retina, lo que amerita valoracion retinologica urgente para estudio y eventual tratamiento quirurgico."*
2. **Roturas y desgarros retinianos (`ROTURA` - Urgente):**
   *"Hallazgo urgente: en la retina periferica se documenta {hallazgo}, lo que amerita valoracion retinologica urgente para estudio y posible tratamiento profilactico."*
3. **Tracción vítrea periférica / hemorragia vítrea (`VITREO` - Urgente):**
   *"Hallazgo urgente: en la retina periferica se documenta {hallazgo}, lo que amerita valoracion retinologica urgente con exploracion de la retina periferica bajo midriasis."*
4. **Lesión predisponente sintomática (`PREDISPONENTE_SINTOMAS` - Urgente):** Lesiones predisponentes (lattice, caracol, agujero atrófico, retinosquisis) con síntomas agudos de tracción referidos en el motivo de consulta.
   *"Hallazgo urgente: en la retina periferica se documenta {hallazgo} y el paciente refiere sintomas visuales de inicio reciente, lo que amerita valoracion retinologica urgente con exploracion de la retina periferica bajo midriasis."*
5. **Lesión predisponente sin síntomas agudos documentados (`PREDISPONENTE` - Preventivo no urgente):**
   *"En la retina periferica se documenta {hallazgo}, que amerita exploracion programada de la periferia bajo midriasis y educacion al paciente para acudir a revision sin esperar a la cita programada si presenta fotopsias, miodesopsias nuevas o sombra en el campo visual."*
6. **Antecedente tratado o antiguo (`ANTECEDENTE` - Seguimiento):** Antecedente de desgarro tratado con láser o cirugía de desprendimiento de retina previa.
   *"Se documenta antecedente de {hallazgo} tratado o de larga evolucion, que amerita mantener el seguimiento retinologico programado y educacion sobre sintomas de alarma."*
**Suprime a:** `sintomas_alarma_traccion_vitreoretina` cuando la lesión periférica es urgente (niveles DR, ROTURA, VITREO o PREDISPONENTE_SINTOMAS).
**Fundamento:** [AAO PPP2025](https://pubmed.ncbi.nlm.nih.gov/39918519/) respalda la evaluación especializada de roturas, desprendimiento y hemorragia vítrea, con vigilancia individualizada de lesiones predisponentes. La regla describe el hallazgo; no decide láser ni cirugía. Plurales, antecedentes y localizaciones se interpretan por hecho: una cirugía de catarata no convierte la hemorragia vítrea en antecedente, ni una mácula normal excluye retinosquisis periférica. Desgarro iridiano y diálisis renal/peritoneal no acreditan lesión retiniana.

### 4.2 `sintomas_alarma_traccion_vitreoretina`
**Campo:** `paciente.motivo_consulta`. Reconoce fotopsias, miodesopsias y sus variantes, cortina/sombra y pérdida visual súbita. Cada síntoma conserva su negación y cronología local; una cefalea de ayer no vuelve recientes las moscas volantes habituales.

**Niveles:** A, cortina/sombra o pérdida visual súbita afirmadas: valoración el mismo día; B, fotopsias/miodesopsias de inicio reciente: exploración de retina periférica bajo midriasis en un máximo de48 horas, o referencia si no puede realizarse; C, crónicas o sin tiempo documentado: conducta programada o condicionada a precisar el inicio, sin H01. Un episodio antiguo resuelto no se presenta como nuevo. El texto expresa el síntoma encontrado, sin diagnosticar desprendimiento vítreo/retiniano.

**Integración:** #1 urgente suprime duplicidad. La pérdida visual actual puede coexistir con #3/#58; se conserva la prioridad más apremiante. Fundamento: AAO PPP2025. La lectura textual no demuestra el mecanismo del síntoma.

### 4.3 `fondo_oclusion_vascular_urgente`
**Condición:** descripción retiniana de oclusión o signos específicos en `fondo_de_ojo`. Los acrónimos oculares (OACR/OVCR y variantes) tienen contexto específico; los vasos genéricos requieren anclaje ocular. Se excluyen trombosis/carótida/yugular/pulmonar y otros vasos extraoculares. Una sospecha puede justificar valoración, pero no funciona como causa orgánica demostrada de baja AV.

**Conductas:**
- Arterial: derivación inmediata el mismo día a urgencias con atención neurovascular y oftalmológica; valorar arteritis de células gigantes cuando la edad lo justifique o no esté documentada.
- Sin tipificar: valoración oftalmológica el mismo día; si hay pérdida súbita de horas, derivación inmediata a urgencias con atención de evento vascular cerebral.
- Venosa: valoración oftalmológica prioritaria en los próximos días, sin esperar la cita programada; PIO, edema/neovascularización y evaluación médica de factores de riesgo. En menores de50 años el texto deja a valoración médica estudiar hipercoagulabilidad.
- Secuela explícita: comprobar seguimiento y factores de riesgo, sin atribuir carácter agudo.

La cronicidad se vincula al evento dentro de una ventana local, sin tomar la cirugía de otra estructura ni una futura cita como inicio de oclusión. Las salidas dicen «signos descritos como», sin confirmar un diagnóstico desde el motor. Fundamento: [AAO PPP2025](https://pubmed.ncbi.nlm.nih.gov/39918522/).

### 4.4 `fondo_embolo_retiniano` (placa o material embólico retiniano)
**Condición:** Hollenhorst explícito o material embólico con localización retiniana. El brillo inespecífico, la anatomía extravascular/sistémica, el descarte aislado y la lesión histórica resuelta no acreditan un hallazgo actual. Una descripción «posible» se conserva como tal y solicita verificación oftalmológica.

**Datos conservados:** ojo, bilateralidad, lateralidad desconocida y tipo realmente descrito (calcificado, plaquetario, colesterol o inespecífico). No se convierte una vena en arteriola ni todo émbolo en Hollenhorst.

**Conducta:**
- Con pérdida visual transitoria o súbita actual, o signos arteriales concomitantes de #3: referencia inmediata a urgencias con atención neurovascular y oftalmológica, protegida por H01. Describe el ojo del síntoma por separado; la coexistencia no demuestra causalidad.
- Con síntomas neurológicos agudos reconocidos: evaluación inmediata por esos síntomas, sin atribuirlos a la placa. Este detector no sustituye un triaje neurológico general.
- Con ausencia visual explícitamente documentada: valoración médica ambulatoria de riesgo cardiovascular y posible fuente embólica, incluida valoración carotídea a criterio médico.
- Sin información suficiente de síntomas: pide precisar síntomas y temporalidad antes de definir prioridad, sin asumir que sea asintomático. Ante otra oclusión activa de #3 conserva la atención indicada por ella.

Los síntomas se leen en motivo, fondo y anexos con procedencia, negación y temporalidad. Amaurosis congénita o un episodio remoto no se convierten en pérdida aguda.

**Fundamento:** [AAO PPP2025](https://pubmed.ncbi.nlm.nih.gov/39918522/), [AHA2021](https://pubmed.ncbi.nlm.nih.gov/33677974/) y [Bakri2013](https://pubmed.ncbi.nlm.nih.gov/24072943/) respaldan estudiar el hallazgo y priorizar los episodios sintomáticos agudos. La placa aislada no establece estenosis carotídea, origen embólico ni oclusión arterial.

### 4.5 `papila_patologica`
**Keywords:** edema de papila/papilar, papiledema, papilitis, neuritis óptica, neuropatía óptica (no glaucomatosa), palidez papilar, disco pálido, atrofia óptica, borramiento de bordes, bordes papilares poco definidos, márgenes borrosos, sospecha de pseudoedema / pseudopapiledema.
**Estratificación en 4 niveles clínicos:**
1. **Nivel A (Edema verdadero / Papiledema / Signos floridos o síntomas de HIC - Urgente 24h):**
   *"Hallazgo urgente: se documenta aspecto de edema de papila en el fondo de ojo, hallazgo que amerita valoracion oftalmologica o neurooftalmologica dentro de las 24 horas para verificar si se trata de edema verdadero y, en ese caso, estudiar su causa, incluida la hipertension intracraneal{ y, por la edad, el descarte de arteritis de celulas gigantes si edad ≥ 50}."*
2. **Nivel B (Bordes poco definidos / Sospecha de pseudoedema - Preferente):**
   *"Se documentan bordes papilares poco definidos o sospecha de pseudoedema de papila; la oftalmoscopia no distingue con fiabilidad pseudoedema de edema verdadero, por lo que amerita valoracion oftalmologica preferente con imagen del nervio optico (OCT o ecografia) y campimetria, indicando al paciente adelantarla si presenta oscurecimientos visuales transitorios, zumbido pulsatil o vision doble."*
   *(Protección de seguridad: el Nivel B nunca cuenta como causa orgánica explicativa en `contexto.py`, evitando silenciar falsamente la red de déficit visual inexplicable).*
3. **Nivel Palidez (Palidez papilar pura o combinada con excavación):**
   - **Palidez con excavación patológica aumentada:** Suprime a `#6 fondo_glaucomatoso` para enfocar el diagnóstico diferencial.
     *"Se documenta excavacion papilar aumentada acompanada de palidez papilar, combinacion que amerita valoracion oftalmologica preferente con tonometria, campimetria e imagen del nervio optico para diferenciar neuropatia glaucomatosa de no glaucomatosa."*
   - **Palidez pura:**
     *"Se documenta alteracion del nervio optico (palidez, atrofia o neuropatia referida), hallazgo que amerita valoracion oftalmologica preferente con campimetria e imagen del nervio optico para determinar su causa, incluida neuroimagen a criterio del especialista."*
4. **Nivel Antecedente (Neuritis/neuropatía antigua tratada o en seguimiento):**
   *"Se documenta antecedente referido de neuritis o neuropatia optica, que amerita confirmar su seguimiento oftalmologico o neurologico y adelantar la valoracion si aparece nueva disminucion visual o dolor con los movimientos oculares."*
5. **Variantes anatómicas benignas (B-BENIGNA):** Disco inclinado / tilteado, crescentes miópicos o esclerales, drusas de papila aisladas y fibras de mielina / fibras nerviosas mielinizadas se reconocen como hallazgos anatómicos benignos que no activan alarma patológica ni suprimen el screening visual.
**Fundamento:** El edema papilar descrito requiere evaluación de su causa; la regla no acredita hipertensión intracraneal ni isquemia. Los bordes ambiguos requieren distinguir edema y pseudoedema con exploración e imagen especializada. La palidez documentada amerita estudio del nervio óptico, sin establecer causa ni irreversibilidad desde el payload. Los signos de distintos ojos no se combinan para inventar un edema o una excavación pálida.

### 4.6 `glaucoma_asimetrico` (Sospecha de neuropatía óptica con asimetría funcional y estructural)
**Reclasificación:** **Preferente** (no urgente, retirada de `_EMERGENCY_SPECS`).
**Requiere:** Defecto pupilar aferente relativo (DPAR / Marcus Gunn) en un ojo determinado (`ojo_dpar ∈ {OD, OI}`) en `reflejos_pupilares` concordante con hallazgo estructural en el mismo ojo:
- Asimetría de excavación interocular $\ge 0.20$ con mayor relación C/D en el ojo con DPAR; o
- Signo focal papilar en el ojo con DPAR (muesca/notch de anillo, adelgazamiento de rima o violación de la regla ISNT comprobada exclusivamente en el ojo con DPAR).
**Descarta (transfiere a neurooftalmología y no dispara glaucoma asimétrico):** Pacientes menores de 50 años, agudeza visual subnormal peor a 20/40 en el ojo con DPAR, defectos campimétricos quiasmáticos (hemianopsias, cuadrantanopsias), o presencia de palidez/edema en fondo de ojo.
**Suprime a:** `pupilas_alteradas` y `fondo_glaucomatoso`.
**Texto:** *"Se documenta defecto pupilar aferente relativo en {el ojo derecho | el ojo izquierdo} junto con {hallazgo papilar} en el mismo ojo; esta asimetria funcional y estructural de la via visual aferente amerita valoracion oftalmologica preferente con tonometria, perimetria y OCT de capa de fibras nerviosas para establecer si su origen es glaucomatoso o de otra causa."*
**Fundamento:** La combinación concordante de DPAR y asimetría estructural fundamenta investigar la vía aferente con tonometría, perimetría y OCT. No determina si la causa es glaucomatosa. Las exclusiones evitan atribuir a glaucoma otros cuadros, pero no demuestran su etiología alternativa. Sin lateralidad explícita de los valores C/D no se fabrica concordancia; signos presentes en ambos ojos no se describen como unilaterales.

### 4.7 `fondo_glaucomatoso` (con absorción completa de #7 `isnt_violada_papila`)
**Condición:** Evaluación integral de excavación papilar y signos focales del anillo neurorretiniano.
- **Relación Copa/Disco (C/D o E/P):** Umbral operativo de aviso $\ge 0.70$ (ajustado a $\ge 0.60$ si se documenta microdisco/papila pequeña en ese ojo, o $\ge 0.80$ ante macrodisco/papila grande). No es un umbral diagnóstico; el tamaño contralateral no se transfiere. Valores sin ojo no se asignan por orden.
- **Asimetría interocular:** Diferencia $| \text{C/D}_{\text{OD}} - \text{C/D}_{\text{OI}} | \ge 0.20$ (salvo asimetría fisiológica por discos de diferente tamaño).
- **Signos focales glaucomatosos:** Hemorragias en astilla / de Drance en el borde del disco, muesca o escotadura (notch) del anillo neurorretiniano, adelgazamiento localizado de la rima neural, defecto en cuña de la capa de fibras nerviosas (CFNR), o violación de la regla ISNT.
**Absorción de la regla ISNT:**
- Si se documenta la **violación de la regla ISNT como hallazgo aislado** (sin excavación $\ge 0.70$ ni asimetría ni otros signos focales):
  *"Se documenta en el fondo de ojo violacion de la regla ISNT como hallazgo papilar aislado, que amerita completar estudio de glaucoma con tonometria, campimetria y OCT de nervio optico, con valoracion oftalmologica si alguno resulta alterado."*
- Si coexisten excavación aumentada, asimetría o signos focales:
  *"Se documenta en el fondo de ojo {detalles papilares}, hallazgo papilar que amerita valoracion oftalmologica para estudio de glaucoma con tonometria, gonioscopia, paquimetria, campimetria y OCT de nervio optico{; la relacion copa/disco debe interpretarse segun el tamano del disco}.{ La miopia registrada constituye un factor de riesgo adicional.}"*
**Suprimida por:** `glaucoma_asimetrico` o `papila_patologica` (en caso de palidez con excavación).
**Protección de seguridad:** La sospecha papilar de glaucoma no justifica por sí sola una pérdida de agudeza visual central corregida ($\le 20/40$), garantizando que no silencie la red de déficit visual inexplicable en `contexto.py`.
**Fundamento:** ISNT y los signos focales fundamentan completar el estudio del nervio óptico; una violación aislada tiene especificidad limitada y no confirma glaucoma. Se conservan negación, anatomía y ojo de cada signo, sin transformar muesca palpebral o hemorragia resuelta en lesión papilar actual.

### 4.8 `fondo_macular_dmae` (Degeneración Macular Asociada a la Edad y Formas Neovasculares)
**Estratificación clínica basada en la clasificación de Beckman (2013) y formas exudativas/neovasculares:**
1. **Nivel A (Neovascular / Exudativa / Hemorragia activa - Urgente 1 día hábil):** Membrana neovascular coroidea (MNV), líquido subretiniano o intrarretiniano activo, hemorragia macular/subretiniana, desprendimiento del epitelio pigmentario (DEP) vascularizado.
   *"Hallazgo urgente: se documentan en la region macular hallazgos exudativos, hemorragicos o neovasculares ({hallazgos}), que ameritan derivacion prioritaria a retina gestionada en un plazo maximo de 1 dia habil para OCT macular y valoracion de tratamiento."*
2. **Nivel A2 (hallazgo macular y cambio visual explícitamente reciente - Urgente1 día hábil):** Requiere inicio/cambio nuevo afirmado y concordancia cuando ambos ojos están identificados; ausencia de cronología, estabilidad, negación o prueba no interpretable no bastan. Conserva el síntoma exacto (incluido escotoma/micropsia), la fuente y el ojo; no toma la fecha de una cefalea independiente ni los síntomas de un familiar. Sin ojo especificado, no afirma concordancia anatómica.
   El texto muestra los hallazgos y síntomas documentados y la indicación de OCT/retina en1 día hábil. Solo suprime `amsler_alterado` cuando la evidencia fue absorbida, incluyendo síntomas independientes.
3. **Nivel B-TRATADA (Neovascular tratada / Inactiva - Seguimiento preferente):** MNV referida como inactiva, tratada, con cicatriz disciforme o fibrosis subretiniana.
   *"Se documenta enfermedad macular neovascular referida como tratada o inactiva, que amerita mantener el seguimiento retinologico establecido y acudir a revision sin esperar a la cita programada ante cambios visuales."*
4. **Nivel C (Drusas maculares en pacientes jóvenes < 50 años - Programado / Atípico):**
   *"Se documentan depositos tipo drusas en la region macular en paciente menor de 50 anos, hallazgo atipico para la edad que amerita valoracion retinologica programada con OCT e imagen multimodal para caracterizacion."*
5. **Nivel B (DMAE seca / Intermedia / Atrófica en ≥ 50 años - Programado):** Drusas intermedias (≥ 63 µm) o grandes (≥ 125 µm), alteraciones pigmentarias del EPR o atrofia geográfica foveal/extrafoveal.
   *"Se documentan drusas o alteraciones pigmentarias o atroficas maculares, que ameritan valoracion oftalmologica programada con retinografia u OCT macular para estadificacion y para definir la indicacion de suplementacion antioxidante segun estadio, junto con educacion en autocontrol con rejilla de Amsler para acudir a revision sin esperar a la cita programada si aparece distorsion o mancha central nueva."*
6. **Filtro Benigno (Beckman):** Drusas duras miliares pequeñas (< 63 µm) aisladas sin cambios pigmentarios se consideran cambios normales por envejecimiento y no activan la correlación. Las drusas de papila aisladas quedan rigurosamente excluidas por ser una condición peripapilar distinta.
**Fundamento:** Las alteraciones maculares descritas y los síntomas nuevos concordantes justifican completar la exploración con OCT y valoración de retina. La rejilla de Amsler no confirma ni excluye neovascularización; no se atribuye DMAE ni se indica tratamiento desde edad, drusas o distorsión aisladas. Fuentes y límites constan en #8 y la reapertura A2 de #16.

### 4.9 `fondo_macular_otros` (Maculopatías estructurales no asociadas a DMAE)
**Keywords:** agujero macular de espesor completo, agujero foveal, agujero lamelar, pseudoagujero macular, membrana epirretiniana (MER), gliosis macular o premacular, pucker macular, maculopatía en celofán, tracción vitreomacular (TVM), edema macular (cistoide, diabético EMD/EMCS, postquirúrgico de Irvine-Gass), coroidopatía o coriorretinopatía serosa central (CSC / CSR), desgarro del EPR, foveosquisis miópica, atrofia coriorretiniana miópica / estafiloma / estrías de laca.
**Estratificación en 2 niveles de prioridad:**
1. **Nivel P (Preferente):** Hallazgos con alto riesgo de compromiso foveal rápido (agujero macular completo, edema macular, CSC en < 50 años sin drusas, desgarro del EPR).
   *"En la region macular se documenta alteracion estructural que puede comprometer la vision central y amerita OCT macular y valoracion retinologica preferente."*
2. **Nivel R (Programado):** Alteraciones estructurales crónicas o de evolución lenta (membrana epirretiniana, pucker macular, tracción vitreomacular, agujero lamelar / pseudoagujero, foveosquisis miópica, atrofia coriorretiniana miópica).
   *"En la region macular se documenta alteracion estructural que amerita OCT macular y valoracion retinologica programada, con reconsulta si aparece distorsion o disminucion de la vision central."*
**Enrutamiento clínico:** La descripción de líquido/CSC en mayores, con miopía en el ojo afectado o drusas maculares concordantes se dirige a #8 para caracterización especializada, sin afirmar etiología. Una drusa papilar, mención negada o miopía contralateral no presta ese contexto. Maculopatía miópica con hemorragia también conserva la vía de #8.
**Supresión:** Oclusión concordante de #3 o aviso urgente macular de #8; la oclusión OI no borra un edema OD. MER afirmada con líquido negado y maculopatía miópica sin hemorragia conservan la alteración estructural. Antecedente resuelto o incertidumbre aislada no se redactan como lesión actual demostrada.
**Fundamento:** El agujero macular, edema y otras alteraciones estructurales ameritan caracterización con OCT y valoración de retina según el hallazgo. La regla no decide vitrectomía ni demuestra progresión; la conducta definitiva depende del especialista.

### 4.10 `fondo_hipertensivo`
**Criterio clínico y extractor:** Extractor factual estructurado con memoización (`_eval_fondo_hipertensivo_info`).
- **Núcleo conservable:** Signos vasculares morfológicamente confirmados: estrechamiento arteriolar focal/generalizado, relación A/V disminuida, cambios de pared (hilos/alambres de cobre/plata en singular y plural), cruces arteriovenosos patológicos (pinzamiento, compresión, desviación/deflexión) y signos epónimos vasculares (Gunn, Salus, Bonnet; excluyendo el chip pupilar 'Marcus Gunn' y patología no vascular).
- **Filtros de exclusión:** Cruces fisiológicos normales, conservados, sin compresión o sin pinzamiento; antecedentes resueltos; y solicitudes aisladas de descarte ("descartar retinopatía hipertensiva").
- **Rama Urgente (Guías NICE NG136 §1.5.2):** Adulto (edad ≥ 18) con registro contemporáneo de PA crítica (sistólica ≥ 180 o diastólica ≥ 120 mmHg) en motivo o fondo de ojo + hemorragias retinianas o edema de papila. Activa alerta de derivación médica especializada el mismo día con salvaguarda determinista H01.
**Texto dinámico:**
- *No urgente:* *"Se describe {hallazgo efectivamente documentado} en los vasos retinianos, lo que amerita valoracion oftalmologica y revision medica de la presion arterial."*
- *Urgente:* *"Hallazgo urgente: se registra presion arterial de {PA} mmHg junto con {hemorragias retinianas | edema de papila}; esta combinacion amerita valoracion medica especializada el mismo dia."*
**Fundamento:** Los signos vasculares ameritan evaluación de su causa. Según NICE NG136, la combinación descrita de cifras críticas de PA con hemorragias o edema papilar requiere evaluación médica el mismo día; el motor no establece emergencia hipertensiva ni daño agudo de órgano. Se excluyen cifras invertidas, distintas lecturas ambiguas, ejemplos, antecedentes de hemorragia y el simple borramiento de bordes sin edema documentado.

### 4.11 `fondo_vascular_diabetico` (Aviso microvascular retiniano y triage neovascular)
**Condición:** Presencia confirmada de lesiones microvasculares retinianas objetivas (microaneurismas, exudados duros/lipídicos, manchas algodonosas actuales, microhemorragias/hemorragias intrarretinianas, IRMA, arrosariamiento venoso o edema macular) o proliferativas activas (NVD papilar, NVE retiniano o rubeosis de iris).
- **Exclusiones estrictas:** Neovasos corneales (vía anterior), exudados conjuntivales, neovascularización coroidea/subretiniana (enrutada a #8 `fondo_macular_dmae`), antecedentes tratados inactivos, descarte sin hallazgos y hemorragias atribuidas a OVCR activa (evita duplicidad con #3 salvo lesiones independientes).
- **Evaluación cláusula por cláusula y por ojo:** Una lesión negada o histórica no anula otra actual. Una lateralidad ausente permanece sin determinar. La deduplicación con oclusión venosa exige la misma atribución ocular; no borra las lesiones contralaterales.
- **Triage urgente (H01):** NVD papilar activo, NVE retiniano activo o neovasos en iris activan salvaguarda `AlertaUrgencia(H01)` con texto *"Hallazgo urgente: se describe neovascularizacion {localizacion}, que amerita contacto con oftalmologia para triage y valoracion especializada."* Rubeosis de iris con síntomas agudos (dolor/visión borrosa) exige valoración urgente el mismo día.
- **No urgente:** *"Se documentan hallazgos microvasculares retinianos ({lesiones}), lo que amerita valoracion retinologica y evaluacion medica sistemica, incluida la glucemia y la presion arterial."* IRMA, arrosariamiento venoso o hallazgo macular añaden valoración preferente; el edema se coordina con la misma valoración de #9. Solo la diabetes personal afirmada permite añadir control glucémico con su médico; un antecedente familiar independiente no borra esa afirmación personal.
- **Hemorragia prerretiniana:** Nueva o con síntomas oculares actuales, genera H01 para evaluación el mismo día. Sin esos datos se mantiene valoración preferente, sin inventar la causa.
**Fundamento:** No inventa diagnósticos de diabetes no consignados en el payload; describe las alteraciones vasculares objetivas y prioriza el triage urgente ante signos proliferativos de alto riesgo de pérdida visual severa según protocolos internacionales (ICDR / ETDRS / College of Optometrists Annex 4).

---

## 5. Refracción final

### 5.1 `miopia_magna` — #24
**Selección:** EE≤−6,00 D por ojo cuando constan esfera y cilindro. Si falta el
cilindro, una esfera≤−6 D se describe como esfera registrada, con EE exacto no
calculable; no se imputa 0. Se conserva la cifra y el ojo, sin una segunda banda −8.
**Aviso:** valorar retina central/periférica y ajustar seguimiento a los hallazgos
reales y controles consignados. La Rx no demuestra lesión retiniana, longitud
axial, progresión, mecanismo corneal ni riesgo individual cuantificado. Se
conserva contexto literal de lectura provisional, causa conocida o evaluación
previa. La magnitud sola no da urgencia; los síntomas agudos se evalúan por sus
rutas independientes.

### 5.2 `hipermetropia_alta` — #25
**Selección operativa:** EE≥+5,00 D calculable con esfera y cilindro presentes en
el mismo ojo; no se añade un piso esférico ni una frontera fisiológica a los 40.
**Aviso:** conserva EE y ojo, propone valorar AV, alineación y segmento anterior,
y evaluar cámara/ángulo según antecedentes y exploración. No afirma ojo corto,
estrechez angular ni esfuerzo acomodativo residual. En edad documentada<18 se
revisa desarrollo visual y alineación. Cirugía, pseudofaquia, fiabilidad o
estabilidad explícitas permanecen como contexto; K no determina la causa de Rx.
El dolor ocular reciente con halos/náuseas/cambio visual tiene triaje independiente
mediante #19, sin depender del EE ni diagnosticar cierre angular.

### 5.3 `anisometropia` — #26
**Selección operativa:** |EE_OD−EE_OI|>1,00 D, con esfera y cilindro explícitos en
cada ojo. Conserva ΔEE y los dos EE; signos opuestos se describen como antimetropía.
**Aviso:** valorar AV monocular y tolerancia binocular con la corrección indicada.
No asigna bandas de gravedad, alteración de fusión, aniseiconía ni ambliopía desde
la diferencia. En edad<18 se revisa desarrollo visual, sin frontera de descarte
a los 8 años. K aporta solo diferencia de medias completas≥1 D o de cilindros
corneales≥1,50 D cuando están disponibles; un meridiano aislado no es K media.
El contexto provisional/estable se conserva. No prescribe lentes de contacto ni
urgencia por la magnitud aislada.

### 5.4 `aniseiconia_queratometrica_severa` — retirada
**Estado:** retirada del registro el 2026-09-22 (ID histórico #28).
La combinación de diferencia de EE y K no determina predominio corneal,
aniseiconía sintomática/severa ni beneficio fusional de lentes de contacto.
Las asimetrías descriptivas siguen cubiertas por `anisometropia`.
No se usa una proporción fija entre dioptrías y diferencia percibida de tamaño.

### 5.5 `astig_oblicuo` — #30
**Selección:** cilindro final>2,00 D en magnitud y eje en las bandas abiertas
(20,70) o (110,160) grados, por ojo. 20/70/110/160 quedan fuera; 69/159 quedan dentro.
**Aviso:** describe cifra y orientación del cilindro prescrito. Con cilindro
corneal ipsilateral≥1 D y orientación geométrica del meridiano plano documentada
coincidente dentro de 20 grados, añade coincidencia aproximada de orientación;
no confirma igual magnitud ni origen exclusivo. Un eje de cilindro K aislado no
se transpone usando su signo. En niños se comprueban AV monocular/desarrollo.
No se deduce pérdida funcional, gravedad de daño, adaptación difícil o indicación
automática de topografía. Contexto y lecturas provisionales se conservan.

### 5.6 `av_cc_limitada` — #32
**Selección operativa:** AVcc registrada con denominador Snellen equivalente>25;
en el catálogo contractual empieza en 20/30. No aplica etiquetas propias de
severidad, discapacidad ni diagnóstico infantil. `null` o notación no interpretable
no se convierten en una medición ni en 20/20. El parser mantiene compatibilidad
con notación métrica/decimal legacy, sin ampliar el catálogo del SaaS.
**Aviso:** ojo y AV exacta; verificar medición/corrección utilizada porque `av_cc`
no acredita mejor AV corregida. Si persiste reducida sin explicación documentada,
valorar oftalmología y controles consignados. AVsc mejor que AVcc genera advertencia
de inconsistencia. En menores se usa protocolo adecuado a edad/desarrollo; edad
nula limita la interpretación. No explica déficit por K ni presupone causa desde
otra correlación; la pérdida súbita conserva su vía urgente independiente.

### 5.7 `distancia_vertice_alta_ametropia` — #29, recordatorio técnico
**Ubicación:** `RECORDATORIOS_TECNICOS` y `evaluar_recordatorios_tecnicos`; fuera de
`CORRELACIONES`, de los hechos médicos para Qwen y de la lista HTTP de correlaciones
clínicas activadas. No se añade una interfaz nueva de dispensación.
**Selección:** |S|≥4 D o |S+C|≥4 D por ojo, usando únicamente componentes presentes.
Si falta cilindro se puede describir S, sin reconstruir S+C; sin esfera no se calcula
ningún meridiano. Describe valores y pide comprobar planos/distancias de origen y
destino si se cambia la adaptación. `akr.vd` no sustituye esas distancias. No calcula
compensación, afirma impacto clínico individual, patología ni necesidad de lentes de contacto.
**Límite:** el corte ±4 D orienta revisión óptica técnica, sin ser umbral biológico
ni aviso urgente.

### 5.8 `antimetropia_pura_acomodativa` — retirada
**Estado:** retirada del registro el 2026-09-22 (ID histórico #27).
Los EE de signos opuestos quedan descritos por `anisometropia`. No demuestran
anisoforia, demanda acomodativa asimétrica ni necesidad de lentes de contacto;
con astigmatismo mixto tampoco representan ametropías puras.

### 5.9 `astigmatismo_contra_regla_joven` — retirada (2026-09-22)
La combinación de edad menor de 40 años, cilindro prescrito ≤−1 D y eje 70–110°
permite describir la orientación refractiva, pero no demuestra irregularidad corneal
ni fundamenta por sí sola la sospecha de ectasia y derivación automática a topografía.
Se retiró del registro; la Rx permanece disponible y las reglas basadas en otros
hallazgos corneales siguen evaluándose.

---

## 6. Autorrefractómetro / queratometría vs refracción final

Solo aplican si hay valores en `refraccion` **y** `akr` del mismo ojo. Las
atribuciones automáticas a espasmo y cambio cristaliniano se retiraron del registro.

### 6.1 `ar_rx_espasmo_acomodativo` — retirada (2026-09-22)
Edad, exposición a pantallas y diferencia entre esfera AR y Rx prescrita no
identifican espasmo acomodativo. Se retiró este aviso y su veto de la comparación
inespecífica. Las discrepancias que cumplen #40 siguen disponibles; no se redujo
su umbral para conservar los casos eliminados. ID histórico: #38.

### 6.2 `ar_rx_cambio_cristalino` — retirada (2026-09-22)
Una diferencia entre AR y Rx de una visita no es un cambio refractivo longitudinal
ni acredita alteración del índice del cristalino. Edad ≥55 y falta de un disparo
corneal no identifican esa causa. Se retiró la regla y su veto de #40, sin bajar
el umbral de la comparación descriptiva. ID histórico: #39.

### 6.3 `ar_rx_variabilidad_inespecifica` — #40, comparación de registros
**Selección operativa:** diferencia absoluta≥1,50 D en esfera o cilindro presentes
entre AR y Rx final del mismo ojo. `null` no es 0; un componente faltante no impide
comparar el otro cuando está disponible. La transposición refractiva plus-cyl del
AKR ocurre en el esquema; no autoriza transponer el eje del cilindro queratométrico.
**Aviso:** conserva ojo, componente, ambos valores y Δ. Solicita revisar mediciones
y criterio de prescripción. No afirma variabilidad longitudinal, causa, lesión ni
referencia obligatoria. K no confirma ni veta. `taken_at` se ignora conforme al
contrato; fechas próximas/faltantes no acreditan simultaneidad con Rx. No compara
ejes ni reconstruye vectores/plano óptico. La falta de aviso no acredita concordancia
completa.

### 6.4 `ar_detecta_astigmatismo_no_prescrito` — #41, ID histórico
**Selección operativa:** cilindro AR explícito con magnitud≥0,75 D y cilindro Rx
explícito con magnitud<0,50 D, en el mismo ojo. Cilindro Rx nulo no equivale a una
decisión de no prescribir; no se genera aviso desde ese faltante.
**Aviso:** describe ambos cilindros/ojos y propone revisar mediciones y criterio de
prescripción. No declara tolerancia adecuada, astigmatismo subumbral, error ni ruido
instrumental. K no representa todo el componente ocular y no confirma ni suprime
la comparación. El corte no evalúa eje; no acredita temporalidad ni planos iguales,
y `taken_at` no aplica ventana de reloj.

## 6b. Córnea / queratometría como disparador

Las cuatro correlaciones del módulo [corneal.py](app/correlaciones/corneal.py) son la
lectura descriptiva de datos corneales. Pueden activar de forma independiente,
sin identificar etiología desde K ni sustituir una exploración. Solo aplican con
valores registrados y coherentes; radios solos no se convierten a dioptrías.

### 6b.1 `queratocono_ectasia_sospecha` — #33, ID histórico
**Selección numérica:** K registrada≥48,70 D; o K≥47,20 D con cilindro corneal≥1,50 D;
o cilindro corneal≥4,00 D. El cilindro ausente no es evidencia favorable. Un cilindro
alto conserva su aviso al completar meridianos de menor curvatura.
**Procedencia:** muestra K1/K2 registrados, media explícita disponible y ojo; si
solo consta un meridiano señala parcialidad. Cada K afirmada conserva su valor
para la selección: una media elevada no desaparece al añadir un meridiano parcial
compatible. Se distingue la media del mayor meridiano, sin reconstruir el faltante.
No denomina ninguna de ellas Kmax topográfico ni inventa un mapa corneal.
**Aviso:** verificar repetibilidad/contexto y valorar evaluación corneal e imagen si
persiste sin explicación o hay hallazgos coexistentes. No afirma irregularidad ni
ectasia incipiente desde las cifras. Cirugía, LC, lectura inestable, estudio normal
explícito o enfermedad conocida se citan como contexto, sin excluir enfermedad por
su ausencia. No establece examen actual desde un ticket ni activa urgencia por K.

### 6b.2 `cornea_plana_extrema` — #35, ID histórico
**Selección numérica:** menor meridiano registrado<38,00 D; si faltan ambos, media
explícita<38. Se exige coherencia interna y se identifica fuente K1/K2/media y ojo,
con parcialidad si solo consta un meridiano. La media no reemplaza el mínimo cuando
se completa de forma redundante.
**Aviso:** valor de curvatura registrado bajo; verificar lectura, repetibilidad y
antecedentes y valorar segmento anterior si persiste sin explicación o hay hallazgos
clínicos. No diagnostica CNA1/CNA2, microftalmos, cierre angular, cirugía previa ni
invalidez de fórmulas LIO. K1 baja/K2 alta pueden coexistir como datos distintos;
el mínimo no describe la córnea como globalmente plana o esférica. Se conserva
contexto literal y se retira monitorización biométrica automática.

### 6b.3 `astigmatismo_corneal_vs_refractivo` — #36
**Selección operativa:** Rx con cilindro≥0,75 D en magnitud y cilindro K disponible;
diferencia escalar≥1,25 D, o diferencia angular circular≥15 grados cuando ambos
cilindros≥1 D. No asigna enfermedad ni deriva un residual óptico de esos cortes.
**Aviso:** ojo, cilindro de prescripción final, cilindro K y diferencia de magnitudes.
Si se comparan orientaciones, muestra eje Rx, meridiano plano K y diferencia angular.
Prioriza ejes geométricos meridionales documentados; el signo de `k_cilindro` no
acredita convención para rotar su eje aislado. Sin orientación suficiente solo se
comparan magnitudes. No interpreta la prescripción final como defecto total ni
atribuye diferencia a cristalino/error. No calcula vectores ni planos desconocidos.
El cilindro calculado conserva precisión para decidir; solo se formatea al mostrar.
`akr.vd` no es la distancia subjetiva; `taken_at` se ignora y no hay veto global #37.
Reducción deliberada, pseudofaquia y contexto real se conservan literalmente.

### 6b.4 `astigmatismo_lenticular_puro` — retirada (2026-09-22)
Cilindro queratométrico ≤0,50 D y cilindro prescrito ≥1,50 D no identifican origen
lenticular puro, una superficie globalmente esférica ni ectopia lentis. Se retiró
esta regla y su supresión global de #36. La comparación descriptiva sigue disponible
cuando cumple los criterios de #36; no se redujo su umbral para conservar avisos.

### 6b.5 `queratometria_asimetrica_interocular` — #34
**Selección operativa:** diferencia absoluta de K media≥1,00 D con media explícita
o calculable desde K1/K2 completos en cada ojo. No se sustituye media por meridiano
aislado; `null` no satisface comparación. Las medias se comparan antes de redondear
la salida: una diferencia de 0,995 D no satisface el corte≥1 D.
**Aviso:** conserva diferencia, valores y ojos; verificar repetibilidad/antecedentes
y valorar evaluación corneal si persiste sin explicación o hay hallazgos asociados.
No afirma significación patológica, córnea virgen, ausencia de ectasia, queratocono
frustro ni periodicidad biométrica. Coexiste con #33; ninguna condición booleana
negativa se presenta como examen normal. Cirugía, LC, fiabilidad y diagnóstico
conocido se conservan como contexto.

## 7. Anexos oculares y cristalino

### 7.1 `anexos_patologicos` — #19
**Extracción:** lesión/localización exactas por ojo, negación, certeza y evolución.
Reconoce signos de párpados, conjuntiva y córnea como blefaritis, chalazión/orzuelo,
pterigión, hiperemia/inyección ciliar, queratitis, úlcera, infiltrado, defecto epitelial,
cuerpo extraño, hipopión, ptosis/proptosis y lesión palpebral ulcerada con madarosis.
No transforma carnosidad en pterigión, glandular en Meibomio ni erosión/hiperemia genéricas
en anatomía no escrita. Hipótesis se describen sin confirmar; planes/resueltos y
antecedentes estables no se convierten en nueva alarma.
**Aviso:** signo y ojo registrados con evaluación para caracterizar lesión/repercusión,
sin etiología ni tratamiento. La ptosis solo se deduplica con #12 en el ojo cubierto;
el otro ojo/hallazgo actual permanece y antecedentes pueden conservarse en el prompt.
**Prioridad:** úlcera/hipopión/cuerpo extraño corneal, infiltrado con defecto corneal
afirmado, proptosis reciente, lesión de superficie con síntomas recientes y cuadro
lagrimal con fiebre conservan el mismo día. Hay ruta independiente para dolor ocular
reciente con halos, náuseas/vómitos, cambio visual o fotofobia; conserva ojos compatibles
y datos por fuente aunque la lesión sea incierta. No diagnostica infección, cierre
angular o tumor.

### 7.2 `opacidad_cristaliniana` — #18, estados del segmento anterior
**Fuentes:** anexos y fondo se evalúan por separado, sin concatenar negaciones.
Se distinguen opacidad del cristalino, lesión capsular, posición anómala de cristalino/
implante y leucocoria/reflejo rojo anormal; conserva término, ojo, certeza y evolución.
Pseudofaquia/LIO, afaquia y lente fáquico normales aislados son contexto, sin nueva
correlación. Catarata objeto de cirugía previa no equivale a opacidad presente.
La imposibilidad de visualizar fondo por catarata no niega la catarata afirmada.
**Aviso:** valoración para caracterizar la lesión real/repercusión, sin atribuir AV,
estadio ni necesidad quirúrgica. En edad documentada<18 agrega evaluación pediátrica
y desarrollo visual; edad nula no inventa esa categoría.
**Prioridad:** leucocoria/reflejo rojo anormal afirmado, posición anómala con trauma/
síntoma reciente compatible por ojo, y dolor intenso o disminución visual recientes
tras evento quirúrgico ocular afirmado del paciente dentro de 42 días requieren el
mismo día. Negación, hipótesis o familiar no completan cirugía; una cirugía ocular
genérica no se llama catarata. Eventos/síntomas de ojos distintos no se combinan.

### 7.3 `anexos_riesgo_glaucoma_secundario`
**Datos:** `anexos_oculares` y `fondo_de_ojo` **evaluados por separado** (nunca concatenados: la negación de un
campo no alcanza al otro); no hay PIO ni gonioscopia estructuradas.
**Signos:** huso de Krukenberg; línea de Sampaolesi; material pseudoexfoliativo; los nombres de síndrome
*dispersión pigmentaria* y *pseudoexfoliación (PXF/PEX)* —que se presentan como **diagnóstico referido en el
registro**, no como hallazgo probado—; y dos combinaciones descriptivas con anatomía completa: *pigmento en
endotelio corneal + defectos de transiluminación iridiana* y *depósitos blanquecinos en cápsula anterior + margen
pupilar* (sin nombrar el síndrome; «pigmento» o «depósitos» sueltos no bastan). La dispersión pigmentaria
**retiniana/macular/papilar** no cuenta.
**No dispara:** negación local, antecedente familiar, plan («descartar… en la próxima revisión»), hallazgo
resuelto («sin pigmento actual») y síndrome conocido y estable; un cambio nuevo en la misma cláusula sí. *Posible/
no concluyente* → «El registro plantea, sin confirmar…» y verificar.
**Texto:** *«Se registra {signo, ojo y campo de origen}, que amerita evaluacion oftalmologica del segmento anterior
y del riesgo glaucomatoso, incluyendo presion intraocular y gonioscopia segun corresponda.»* No afirma glaucoma,
hipertensión ocular ni que la biomicroscopía o la gonioscopía se hayan hecho; no fija frecuencia de vigilancia.
**Síntomas agudos:** con el signo registrado y **dolor ocular reciente + halos, náusea/vómito, baja visual u ojo
rojo reciente** → *«Hallazgo urgente: … con {síntomas}; esta combinacion amerita valoracion oftalmologica el mismo dia…,
sin esperar el control periodico»*, sin diagnosticar cierre angular. H01 exige urgente/«el mismo día».
**Fundamento:** Siddiqui 2003 (el síndrome exige dos de tres signos y solo una parte evoluciona a glaucoma pigmentario), Jeng 2007
(pseudoexfoliación: el desenlace incluyó hipertensión ocular tratada, no solo glaucoma) y Shouchane-Blum 2023
(los signos pueden no estar presentes en el pseudofáquico). Los signos justifican evaluar; no diagnostican.

---

## 8. Pupilas y motilidad

### 8.1 `horner_o_tercer_par_sospecha` (ID histórico; hallazgos con ptosis)
**Datos:** notas de pupilas, anexos, motilidad y motivo de consulta. Se extraen
ocurrencias afirmadas con ojo, evolución y explicación local/farmacológica.
La comparación OD>OI no identifica por sí sola la pupila patológica; proptosis
no se interpreta como ptosis. No se inventan Horner, paresia ni etiología.

**Activación:** ptosis y cambio de tamaño pupilar no explicado, sin contradicción
lateral; con datos incompletos se describen los hallazgos y se solicita caracterizar
lado y evolución. La ruta motora aguda también conserva ptosis reciente con
limitación motora concordante o diplopía nueva, incluso con pupilas normales.
Una ptosis antigua no explica automáticamente una alteración pupilar nueva.

**Prioridad:** inicio/cambio reciente o síntomas de alarma del episodio justifican
valoración médica el mismo día. La combinación estable o de evolución desconocida
no se convierte automáticamente en una urgencia neurológica. H01 consume los
hallazgos filtrados y protege lateralidad y plazo; elimina controles anuales
incompatibles cuando existe urgencia. Se suprimen en #13 solo las ocurrencias
pupilares cubiertas, conservando DPAR y hallazgos independientes.

**Fundamento y aceptación:** NANOS (anisocoria/ptosis),
ACR Horner 2025 y College of Optometrists, tabla de urgencias. Estas fuentes
respaldan evaluación y triaje, no validan diagnósticos obtenidos con el payload.

### 8.2 `pupilas_alteradas`
**Datos:** solo `reflejos_pupilares` (chip + nota ≤255). El chip literal *Marcus Gunn* significa
DPAR (diccionario); el chip normal no prueba ausencia de DPAR. El motivo puede fechar un signo o
aportar síntomas agudos, nunca crea un signo pupilar.

**Extracción por ocurrencia** (compartida con #12): tipo exacto, ojo, afirmación, explicación,
evolución y certeza. Tipos que se conservan sin convertirse entre sí: **aferente** (DPAR),
**tamaño** (anisocoria, midriasis, miosis), **forma** (pupila/iris/contorno irregular, discoria,
corectopia), **reacción** (no reactiva, hiporreactiva, respuesta fotomotora/consensual/acomodativa
ausente o abolida) y pupila tónica/Adie (un solo nombre). "Irregular" exige sustantivo anatómico;
*respuesta irregular* sigue siendo una respuesta. *Reflejo corneal ausente* o *no evaluado* no son
hallazgos pupilares. Una función ausente no se interpreta como DPAR.

**No dispara:** negación local (*sin, ni, no se observa, DPAR negativo, DPAR (-), DPAR: no*), plan
de descarte resuelto, anisocoria fisiológica/benigna/simple (la negación de la explicación —*no
fisiológica*— no es normalidad), miosis/midriasis por adaptación luminosa, efecto farmacológico
afirmado (*farmacológica, post-dilatación, tropicamida instilada, por atropina…*; un fármaco
negado no excluye), historia local conocida y estable (cirugía/Adie conocido sin cambios) y el
fenómeno mandibulopalpebral de Marcus Gunn (solo cuando el propio fragmento lo identifica; un DPAR
explícito en otra cláusula/ojo se conserva).

**Certeza:** *dudoso/posible/sospecha/no concluyente* → «resultado no concluyente para X» y se pide
repetir/verificar la prueba; *descartar X / X?* → «sospecha por descartar de X» y se pide completar
la prueba. Ninguno se presenta como hallazgo medido.

**Prioridad (nunca por la palabra "DPAR" sola):**
- *Hallazgo urgente, el mismo día:* signo no antiguo con síntoma agudo del motivo (cefalea/diplopía/
  pérdida visual/traumatismo… con inicio reciente) o con dolor cervical/ocular, disartria o debilidad
  aunque no conste la fecha; un signo antiguo solo se reactiva por **pérdida visual nueva**. El texto
  nombra el síntoma que eleva la prioridad.
- *Hallazgo urgente:* signo con inicio/empeoramiento reciente documentado (nuevo, súbito, hoy, ayer,
  hace horas o hasta 14 días) y sin duda sobre la medición.
- *Sin urgencia:* inicio desconocido → «Verificar inicio y síntomas asociados para decidir la
  prioridad»; no se inventa novedad ni estabilidad. DPAR antiguo estable → «evolución antigua
  descrita», sin urgencia.

**Deduplicación (sin vetos globales):** `horner_o_tercer_par_sospecha` retira solo las ocurrencias
pupilares que ya describe; `glaucoma_asimetrico` cubre el DPAR del mismo ojo salvo que exista prioridad
aguda propia. Cualquier otro ojo, tipo de signo o dato agudo se conserva.

**Texto:** *"Se registra {hallazgos con ojo}; amerita valoracion oftalmologica {de retina y via visual
aferente | de la respuesta y anatomia pupilar} para establecer su causa y revisar su evolucion y
seguimiento."* Variante urgente: *"Hallazgo urgente: se registra {hallazgos}[, con {síntomas}];
amerita valoracion oftalmologica {el mismo dia | urgente}, con evaluacion … para establecer su causa."*
No diagnostica lesión de vía óptica, Horner ni III par y no impone neurooftalmología.
**H01:** protege cualquiera de los signos pupilares (no solo DPAR), usa los hechos filtrados para el ojo
(sin ojo si hay dos) y preserva el plazo «mismo día».
**Fundamento:** el DPAR también aparece en enfermedad
retiniana (Servais 1986, PMID 2422618); la anisocoria fisiológica es común y benigna (NANOS).

### 8.3 `motilidad_alterada`
**Datos:** `motilidad_ocular` (≤255, cadena aplanada «Versiones: … Ducciones: … Sacadicos: …
Seguimiento: …» o texto libre). El motivo aporta diplopía, trauma, vértigo, dolor o deterioro visual;
su ausencia no descarta nada. No hay pruebas para distinguir paresia neurógena de restricción
mecánica ni mediciones instrumentales.

**Extracción por sección y ocurrencia** (mismo extractor que #12/#13; plurales y negación local):
*limitación/restricción/hipofunción* (con el movimiento nombrado: «limitación de abducción OD»),
*paresia/parálisis/oftalmoparesia/oftalmoplejía* (se conserva la denominación del registro, p. ej.
«paresia del VI par»; una limitación **no** se convierte en paresia), *incomitancia*, *nistagmo* (con sus
descriptores: vertical, espontáneo, adquirido, latente, en mirada extrema…), *dolor con el movimiento*
(síntoma, no déficit motor), *postura compensadora/tortícolis* (la tortícolis exige vínculo ocular; la
cervical/muscular no cuenta), *sobreacción*, *sincinesia/Duane*, **sacádicos** (lentos, hipo/hipermétricos,
dismétricos, latencia aumentada) y **seguimiento** (entrecortado, discontinuo, sacádico, lento, asimétrico),
además de la **respuesta optocinética anormal** (asimétrica/ausente/alterada).

**No dispara:** negación local («sin limitación», «nistagmo (-)», «sin restricciones ni limitación»),
secciones normales o *no evaluadas*, nistagmo *fisiológico* y nistagmo optocinético fisiológico/conservado
(un «OKN conservado» en otra cláusula no cancela un nistagmo espontáneo real; «no fisiológico» no es
normalidad), y **diagnósticos o secuelas ya conocidos** («Duane conocido», «nistagmo congénito estable,
en seguimiento», «limitación antigua estable por cirugía»); un cambio nuevo en la misma cláusula, u otro
signo/ojo independiente, sí se conserva.

**Certeza:** *posible/dudoso* → «hallazgo no concluyente de X»; *descartar X / X?* → «sospecha por
descartar de X»; ambos piden repetir/completar la exploración y nunca se presentan como confirmados.

**Prioridad (por combinación explícita, no por palabra):**
- *Hallazgo urgente, el mismo día:* déficit motor con diplopía reciente (o diplopía y déficit reciente),
  trauma orbitario reciente (con o sin restricción y síntomas: dolor, náusea), dolor/cefalea/deterioro visual
  reciente, dolor ocular, disartria o debilidad; **dolor con el movimiento + deterioro visual reciente**;
  **nistagmo + vértigo/mareo/inestabilidad/náusea reciente** (o disartria/debilidad). Lo evalúa cada signo
  con los síntomas de su propio ojo; un síntoma del otro ojo no se asocia.
- *Hallazgo urgente (24 h):* déficit motor o nistagmo con inicio/empeoramiento reciente documentado, sin más síntomas.
- *Sin urgencia:* fecha desconocida («Verificar inicio y síntomas asociados»), dolor aislado, sacádicos/seguimiento,
  postura, nistagmo en mirada extrema sin caracterizar («amerita caracterizarse… para decidir si requiere valoración»).

**Deduplicación (sin vetos globales):** la ruta motora aguda de #12 (ptosis nueva + limitación concordante)
conserva la limitación del mismo ojo con los movimientos afectados; #14 no la repite, pero conserva cualquier
otro ojo o tipo de signo. **H01** protege el hallazgo, usa los hechos filtrados para el ojo (sin ojo si hay dos),
purga «motilidad normal» y exige urgente/mismo día.

**Texto:** *«La exploracion documenta {hallazgo exacto y ojo}, que amerita valoracion especializada para aclarar su
origen.»* Urgente: *«Hallazgo urgente: … con {síntomas}; esta combinacion amerita valoracion medica el mismo dia para
aclarar su origen.»* No diagnostica paresia, lesión de nervio craneal ni causa vestibular.

**Fundamento:** AAO Adult Strabismus PPP (Dagi 2020), consenso Bárány (Eggers 2019, nistagmo), Tamhankar 2013 (parálisis oculomotoras agudas),
NICE NG127 (vértigo agudo con nistagmo) y College of Optometrists Annex 4 («Acute onset diplopia/squint/ptosis/nerve
palsy» y «Pain on ocular movement»: 24 h).

---

## 9. Campos visuales y test de Amsler

### 9.1 `campos_visuales_alterados`
**Datos:** `confrontacion_campos_visuales` (texto ≤255; preset «Sin defectos perifericos evidentes.») y el
motivo. No hay umbrales, índices de fiabilidad ni técnica: el módulo no supone ninguno.

**Extracción por mención** (extractor compartido con #12–#14): hemianopsia, cuadrantanopsia, defecto
altitudinal, escalón nasal, escotoma, defecto del campo, reducción/constricción/restricción del campo,
disminución o pérdida del campo, falta de respuesta al **estímulo visual** y alteración campimétrica, cada una
con su ojo (el «derecha/izquierda» de un hemicampo no es un ojo) y su sector. «Defecto» exige campo:
*defecto refractivo, de fijación, epitelial o pupilar* no cuentan; «no responde» exige estímulo (no
«a preguntas»).

**No dispara:** negación local, mancha ciega/escotoma fisiológico, plan sin examen («no evaluado, descartar
en la próxima consulta»), diagnóstico conocido y estable («hemianopsia antigua estable por ictus previo, en
seguimiento») y pruebas no interpretables (incomprensión, atención, hipoacusia, no valorable). Una zona u
ojo normal no cancela el positivo del otro.

**Certeza:** *posible/poco confiable/no reproducible* → «resultado no concluyente» y repetir la
confrontación o hacer perimetría formal; *descartar X / X?* → «plantea, sin confirmar, X». Nunca se declara
como alteración. Un defecto atribuido en el registro a ptosis/armazón conserva esa atribución textual.

**Ruta independiente por síntomas del motivo** (no se anula con una confrontación normal): pérdida de la mitad
o de un lado del campo, pérdida del campo visual, o episodio transitorio reciente, con inicio reciente. Describe
el **síntoma referido**, nunca un defecto observado inventado. La mancha o el escotoma **central** fijo es visión
central y lo recoge `amsler_alterado` (9.2).

**Prioridad** (por inicio documentado y combinación, no por la palabra):
- *Hallazgo urgente, valoración médica inmediata en urgencias:* hemianopsia/cuadrantanopsia/defecto altitudinal
  de inicio reciente, o pérdida amplia del campo referida y persistente, o cualquier pérdida reciente con
  síntomas neurológicos focales (habla, lenguaje, debilidad, hormigueo, asimetría facial, confusión). La ausencia
  de cefalea o debilidad no reduce la prioridad.
- *Hallazgo urgente, el mismo día:* otro defecto o síntoma reciente (escotoma central, defecto monocular…),
  episodio transitorio reciente («deje de ver la mitad derecha 20 minutos») y empeoramiento reciente de un defecto
  conocido; el antiguo permanece independiente del nuevo.
- *Sin urgencia:* inicio desconocido o no reciente («Verificar inicio y síntomas asociados»); no se certifica estabilidad.

**Texto basal:** *«Se documenta {hallazgo y ojo} durante la confrontacion de campos visuales. Este hallazgo requiere
evaluacion especializada y caracterizacion mediante perimetria formal segun corresponda.»* No nombra glaucoma,
ictus, tumor ni localización anatómica. **H01** protege el hallazgo, toma el ojo de los hechos filtrados, purga
«campos normales» y exige «inmediata en urgencias» o «el mismo día».

**Fundamento:** la confrontación tiene sensibilidad limitada (Johnson 1991; Kerr 2010), por eso una confrontación normal no descarta un
síntoma agudo; NICE NG128 (déficit neurológico súbito/AIT) y College of Optometrists Annex 4 («Sudden visual loss of
unknown cause»).

### 9.2 `amsler_alterado`
**Datos:** `grid_de_amsler` (texto ≤255; preset «Sin descendencia de patologia aparente.») y el motivo.
El contrato no acredita corrección de cerca, fijación, fiabilidad ni ejecución monocular: no se suponen.

**Extracción por mención** (extractor compartido): distorsión, metamorfopsia, líneas onduladas/torcidas/
quebradas/curvas/interrumpidas, micropsia, macropsia, escotoma (central), mancha central fija, zona borrosa
central, zona/área faltante, cuadrados de distinto tamaño y «Amsler/rejilla alterada», cada una con su ojo
(«OD normal. OI con escotoma central» → OI; «Sin alteración OD OI con metamorfopsia» → OI) y su tiempo.

**No afirma alteración** cuando no hay percepción interpretable actual: negación local, plan sin examen
(«No evaluado. Descartar… en próxima revisión»), error material («líneas torcidas por defecto de impresión de
la rejilla»), prueba no valorable/no interpretable (incomprensión, no logra fijar, sin corrección de cerca) y
metamorfopsia conocida y estable («por MER conocida, en seguimiento»). **Certeza:** *posible/poco confiable/no
reproducible* → «resultado no concluyente» y repetir la prueba; *descartar X* → «el registro plantea, sin confirmar».

**Ruta independiente por síntomas del motivo** (no la veta el preset normal): distorsión/líneas torcidas, mancha
o escotoma central fijo, zona borrosa central, micro/macropsia reciente. Un episodio transitorio reciente
(«escotoma central transitorio ayer, hoy rejilla normal») se conserva como episodio con su tiempo, no como
lectura actual ni como antecedente remoto inocuo; «una rejilla sin alteraciones no descarta el síntoma».

**Prioridad:** cambio **reciente** (nuevo, hoy/ayer, hace horas o hasta 14 días, empeoramiento) →
*«Hallazgo urgente: … este cambio reciente de la visión central amerita valoración oftalmológica urgente, con OCT
macular según los hallazgos»*; inicio desconocido → aviso basal con *«Verificar inicio y síntomas asociados»*, sin
inventar agudeza ni estabilidad; no se impone a todo Amsler alterado el plazo de la DMAE húmeda. Edad o drusas
aisladas no demuestran DMAE activa.

**Integración A2 de #8:** con hallazgo macular (drusas blandas, atrofia…) y un síntoma **reciente y fiable del
ojo compatible**, `fondo_macular_dmae` (A2) emite la derivación en 1 día hábil y lista toda la evidencia con
ojo, fuente y tiempo (incluida la estable o la del otro ojo); solo entonces #16 no se repite. Se reconocen
«de inicio hoy/ayer» (antes se perdían); un síntoma dudoso o de otro ojo no activa A2 y #16 lo conserva; un
escotoma no se convierte en metamorfopsia.

**Texto basal:** *«En la rejilla de Amsler se refiere {percepción exacta y ojo}. Este hallazgo amerita evaluacion
oftalmologica de la vision central y estudios complementarios segun los hallazgos.»* No nombra DMAE ni maculopatía.
**H01:** protege el hallazgo, usa los hechos filtrados para el ojo, purga «Amsler normal» y exige «urgente».
**Fundamento:** la rejilla omite escotomas y tiene sensibilidad limitada (Schuchard 1993; Loewenstein 2003), por lo que un resultado
normal no excluye; NICE NG82 (derivación en 1 día hábil ante sospecha de DMAE húmeda activa, no ante cualquier Amsler alterado).

---

## 10. Binocularidad y convergencia

Los IDs históricos conservan compatibilidad; la salida describe PPC/cover y
molestias reales sin diagnosticar insuficiencia, descompensación ni causalidad.
`cover_test` se interpreta por ojo y subtipo. Una forma canónica clasificada
(`Exo y Tropia`) no vuelve a generar un `Exo` sin clasificar; `Endo/Exo/Hiper/Hipo`
sin subtipo conservan incertidumbre y piden precisarlo. `null` no es ortoforia ni
prueba realizada. Cover no documenta distancia, corrección usada, magnitud prismática
ni reservas fusionales; PPC no documenta objetivo, rotura/recuperación o protocolo.

La clasificación por cortes PPC de 6/10 cm y edad 40 se retiró de estas reglas activas.
Se informa cualquier PPC contractual registrado (1–15 cm), con verificación del
protocolo. Las ocupaciones/tareas no sustituyen síntomas. Los fragmentos de motivo
se conservan si son visuales, afirmados y actuales; fatiga general, cefalea aislada,
quejas monoculares en estas correlaciones y síntomas negados/resueltos no completan
la asociación binocular.

**Prioridad compartida:** diplopía de inicio agudo documentado→el mismo día;
pérdida visual súbita, dolor ocular con trauma actual o dolor/ojo rojo/fotofobia→
urgencias inmediatas. El plazo procede del síntoma real, no del subtipo del cover.
Se conserva contexto de estrabismo conocido, estabilidad y corrección referido,
sin convertirlo en examen completo o excluir un cambio nuevo. H01 protege el plazo.

### 10.0 `diplopia_aguda` — integración de #27 D6

Diplopía afirmada del paciente con inicio reciente explícito activa valoración el
mismo día, aunque no existan Cover, PPC, alteración pupilar o AV reducida. La
cronología se liga a su episodio; hipótesis, familiares, negados y antecedentes
estables no activan esta vía. Si coexiste una alarma que exige atención inmediata,
se conserva ese plazo superior. El aviso no atribuye el síntoma a la graduación.
H01 conserva el hecho, el ojo cuando consta y el plazo. La regla histórica #27
permanece retirada; esta vía describe un síntoma independiente.

### 10.1 `insuficiencia_convergencia` — #42, ID histórico
**Condición:** PPC presente (cualquier valor), exoforia clasificada por ojo y
molestias visuales actuales vinculadas a cerca/lectura/pantallas en motivo.
**Aviso:** PPC numérico, todos los registros de cover incluidos los mixtos y el
fragmento sintomático. Completar evaluación binocular y verificar protocolo, medir
cerca/lejos y reservas antes de interpretar relación. No concluye insuficiencia
de convergencia ni plantea terapia desde estos datos. Deduplica #43/#44 porque
conserva sus hechos completos.

### 10.2 `ppc_exoforia` — #43, descripción de registros
**Condición:** PPC presente o exoforia clasificada o `Exo` sin subtipo, siempre que
#42 no haya resumido el conjunto. Una exotropía sola no se vuelve exoforia/Exo
no clasificada. **Aviso:** número PPC y/o ojo/subtipo del cover; verificar protocolo
y precisar subtipo pendiente. Sin síntomas no presupone disfunción ni impone
referencia.

### 10.3 `cover_exoforia_sintomatica` — #44
**Condición:** exoforia clasificada y molestia visual afirmada actual en motivo,
sin resumen #42. **Aviso:** ojo del cover y fragmento sintomático para evaluar
posible relación; no demuestra descompensación o disfunción divergente. Exo
no clasificada se mantiene en #43.

### 10.4 `cover_endoforia_sintomatica` — #45
**Condición:** endoforia o `Endo` sin subtipo junto con molestias visuales actuales.
No aplica veto global por una tropía contralateral. **Aviso:** todos los registros
relevantes por ojo, con subtipo pendiente explícito y síntomas referidos; confirmar,
cuantificar y evaluar relación. No afirma exceso de convergencia, AC/A alterada ni
disfunción acomodativa.

### 10.5 `desviacion_vertical` — #46
**Condición:** hiper/hipoforia, hiper/hipotropía o `Hiper/Hipo` sin subtipo registrados.
**Aviso:** conserva ojos y todos los subtipos, pide confirmar/cuantificar y valorar
relevancia funcional. No imputa síntomas hipotéticos, paresia ni mayor urgencia
por ser tropía. La prioridad surge de síntomas agudos reales.

### 10.6 `endotropia_lente` — #47, ID histórico
**Condición:** endotropía clasificada en cover, por ojo. **Aviso:** cuantificar y
completar evaluación de estrabismo/refracción. No presupone corrección usada,
respuesta a la Rx, componente acomodativo, cicloplejia realizada ni etiología.
Rx y lente nulos siguen nulos; el tipo de lente no reemplaza la prueba.

### 10.7 `exotropia_lente` — #48, ID histórico
**Condición:** exotropía clasificada, por ojo. **Aviso:** evaluar estrabismo,
cuantificar y caracterizar frecuencia/control/función/refracción como evaluaciones
pendientes; no afirma intermitencia, fusión alterada ni origen desde el texto del
cover. Contexto conocido/sensorial se cita como referido. `Exo y Tropia` no genera
además una exodesviación no clasificada.

---

## 11. Superficie ocular — BUT y glándulas de Meibomio

Los intervalos BUT proceden del contrato (1–15 s); no sustituyen técnica/síntomas/
exploración ni clasifican por sí solos ojo seco, gravedad o mecanismo. El valor
no tiene lateralidad estructurada: no se le asigna el ojo de una lesión palpebral.
Método no invasivo/fluoresceína o fiabilidad se incorporan solo cuando el motivo
los documenta; lectura poco confiable pide repetición antes de interpretarla.
Exposición de pantallas es contexto, sin atribución causal. Si motivo y dropdown
discrepan se conservan ambas fuentes y se pide contrastarlas, sin sustituir datos.

### 11.1 `but_critico` — #20, ID histórico
**Condición:** BUT<5 s cuando #21 no resume el hallazgo asociado. **Aviso:** cifra
registrada reducida; corroborar medición y valorar estabilidad con síntomas y
exploración. No diagnostica ojo seco clínico ni disfunción grave, ni prescribe
tratamiento.

### 11.2 `ojo_seco_evaporativo_dgm` — #21, ID histórico
**Condición:** BUT<10 s y anomalía meibomiana afirmada en anexos (DGM/meibomitis/
disfunción meibomiana u obstrucción, secreción espesa, mala expresibilidad o atrofia
con anatomía de Meibomio explícita). Blefaritis/collaretes/telangiectasias genéricos,
glándula lagrimal, mención anatómica sola, hipótesis y antecedentes estables no
sustituyen el hallazgo. `No permeables` puede ser anomalía afirmada; normalidad de
otro ojo no la elimina globalmente.
**Aviso:** BUT y hallazgo/ojos escritos coexisten; evaluar función glandular y
estabilidad. No declara predominio evaporativo ni deriva deficiencia acuosa/mucínica
por faltar DGM. Deduplica las salidas BUT #20/#22/#23 conservando sus datos y
contexto, sin suprimir la lesión independiente #19.

### 11.3 `but_pantallas` — #22
**Condición:** BUT 5–9 s y pantallas `btw2_6` o `gt6`, si #21 no lo resume.
**Aviso:** valor/técnica/fiabilidad documentados y categoría de exposición. No
atribuye el resultado a pantallas ni confirma inestabilidad independiente del
método.

### 11.4 `but_limitrofe` — #23, ID histórico
**Condición:** BUT 5–9 s y pantallas `lt2` o nulo, si #21 no lo resume. `null` no
significa baja exposición ni ausencia de pantallas. **Aviso:** cifra registrada y
verificación de medición/método con síntomas; no etiqueta inestabilidad leve desde
el número ni fija vigilancia automática.

---

## 12. Edad, lente y pantallas

### 12.1 `presbicia_multifocal` — retirada (2026-09-22)
Edad, adición y diseño de lente no acreditan una medición individual de amplitud
acomodativa ni justifican automáticamente la prescripción. La regla avalaba incluso
adiciones elevadas y multifocales sin edad. Se retira la inferencia circular; los
valores de receta y diseño siguen disponibles en el prompt. ID histórico: #49.

### 12.2 `cvs_sospecha` — #53, ID histórico
**Selección:** alguna categoría de pantallas `lt2`, `btw2_6` o `gt6` registrada y
molestias oculares/visuales afirmadas actuales en motivo. `lt2` no es ausencia de
exposición; `null` no se reemplaza por ocupación o una estimación textual. Fatiga
general/cefalea aislada, síntomas negados/resueltos y anatomía ajena no completan
la condición; el fragmento visual real se conserva.
**Aviso:** categoría y molestias coexisten, sin diagnosticar CVS ni declarar causa
por pantallas, necesidad de corrección intermedia o descompensación acomodativa.
Propone caracterizar molestias, superficie y función visual con contexto referido.
Dolor ocular con trauma actual, dolor/ojo rojo/fotofobia o pérdida visual aguda
siguen triaje inmediato; diplopía aguda documentada requiere el mismo día, sin
atribuirlo a pantallas.

### 12.3 `presbicia_sin_adicion` — retirada (2026-09-22)
Edad ≥45, ausencia de adición y Rx de lejos no demuestran déficit próximo ni
necesidad de otra prescripción. Tampoco EE≤−1,50 permite asegurar lectura cómoda.
Se retiró la alerta y sus helpers exclusivos; no se creó un reemplazo automático.
ID histórico: #50. La evaluación próxima requiere información funcional real.

### 12.4 `insuficiencia_acomodacion_joven` — retirada (2026-09-22)
Edad <38 y adición ≥0,75, incluso con molestias, no miden amplitud, facilidad ni
respuesta acomodativa. La condición interpretaba además palabras neutras como
lectura/cerca como síntomas. Se retira la sospecha específica y sus helpers
exclusivos, sin crear otra inferencia desde la receta. ID histórico: #52.

### 12.5 `adicion_incongruente_edad` — retirada (2026-09-22)
Las tablas de edad y el techo de +3 D no son detectores validados de error de
prescripción. Faltan función próxima, indicación y distancia de trabajo; existen
usos de adición en jóvenes y baja visión. Se retira la atribución de incongruencia,
disfunción y errores de refracción. No se introduce un umbral alternativo. ID histórico: #51.

---

## 13. Registros de AV, refracción y contexto — #54–57

Los cuatro IDs históricos conservan compatibilidad; sus salidas describen los
registros sin diagnosticar ambliopía, causa refractiva/subclínica o enfermedad por
edad. Comparten selección operativa AVcc con denominador>25 (20/30 o peor en el
catálogo). Este corte no acredita mejor AV corregida ni normalidad/deficiencia
por edad; un `null` no es AV normal. Conservan todos los ojos seleccionados, AVcc,
AVsc disponible y edad conocida; AVsc mejor que AVcc requiere verificar concordancia.
Contexto de mejor/máxima AV, adaptación, cooperación, fiabilidad, corrección parcial,
estabilidad y enfermedad conocida se cita como referido, sin convertirlo en prueba
realizada o causa confirmada. Las lesiones orgánicas registradas no vetan los datos AV.
La pérdida visual súbita exige urgencias inmediatas y diplopía aguda el mismo día,
según síntomas reales; H01 conserva hechos/plazo.

### 13.1 `ambliopia_sospecha` — #54, ID histórico
**Condición:** AVcc seleccionada en algún ojo y uno de estos datos adicionales: diferencia EE>1 D
calculada solo con S/C presentes en ambos ojos o tropía explícita en cover. No hay límite etario
diagnóstico ni sospecha automática de ambliopía.
**Aviso:** AV de todos los ojos seleccionados, graduaciones disponibles por ojo y
cover registrado, para verificar medición/corrección y completar evaluación. No
afirma factor ambliogénico, causa orgánica excluida ni eficacia de corrección.

### 13.2 `ambliopia_isoametropica_bilateral` — #55, ID histórico
**Condición operativa:** edad documentada<18, AVcc seleccionada en ambos ojos y al
menos uno de estos datos: esfera≥+4 D en ambos o cilindro≤−2,50 D en ambos. No exige igualdad/simetría de EE,
ni completa componentes ausentes. #54 puede resumir el conjunto porque conserva
ambos ojos/graduaciones; entonces no se repite esta salida.
**Aviso:** resumen bilateral numérico para evaluación pediátrica, sin concluir
ambliopía bilateral/isoametropía, corrección total prescrita ni indicar estimulación/
terapia. Una lesión orgánica no elimina los datos.

### 13.3 `deficit_visual_inexplicado_refractivo` — #56, ID histórico
**Condición:** AVcc seleccionada en ojos aún no descritos por #54/#55, con edad
menor de 60 o desconocida. No requiere Rx numérica, AVsc mínima, ausencia de lesiones ni veto por K.
**Aviso:** datos AV por ojo y comprobación de medición/corrección con evaluación
ocular para aclarar hallazgos; no atribuye un déficit refractivo o subclínico ni
prescribe cicloplejia universal.

### 13.4 `adulto_mayor_screening` — #57, ID histórico
**Condición:** mismos ojos/criterio/recomendación que #56, con edad documentada≥60.
La frontera 59/60 solo enruta el identificador histórico; no crea salto de riesgo ni
cribado automático de catarata/glaucoma/mácula. Se mantienen ojos no resumidos por
#54/#55 y no se suprimen por palabras de lesión o implante. Edad nula sigue #56.

---

## Apéndice A — Reglas de supresión (jerarquía clínica)

La deduplicación depende de los hechos que conserva el aviso preferente. Una
correlación activa no prueba una causa ni permite eliminar datos de otro ojo.

| Si activa | Datos o salidas que se deduplican |
|---|---|
| `glaucoma_asimetrico` | `fondo_glaucomatoso`; en `pupilas_alteradas`, solo el DPAR del ojo ya cubierto y sin prioridad pupilar urgente propia. Otros ojos/signos o datos agudos permanecen. |
| `horner_o_tercer_par_sospecha` | Ocurrencias pupilares y limitación motora del mismo ojo ya descritas; en #19, solo la ptosis del ojo cubierto. Otros hallazgos/ojos permanecen. |
| `papila_patologica`, nivel `PALIDEZ_EXCAVACION` | `fondo_glaucomatoso`. Otros niveles de papila no aplican este veto. |
| `fondo_periferico_riesgo`, niveles `DR`, `ROTURA`, `VITREO` o `PREDISP_SINT` | `sintomas_alarma_traccion_vitreoretina`, según la jerarquía del evaluador periférico. |
| `fondo_macular_dmae`, nivel A2 | `amsler_alterado` únicamente si sus hechos completos, fuentes, ojos y temporalidad quedaron representados de forma fiable (`amsler_absorbido`). |
| `ojo_seco_evaporativo_dgm` (#21) | #20/#22/#23; conserva BUT, método/fiabilidad y exposición documentados. No suprime la lesión independiente de #19. |
| `insuficiencia_convergencia` (#42) | #43/#44 porque conserva PPC, todos los registros de cover y síntomas pertinentes. |
| `ambliopia_sospecha` (#54) | #55 cuando resume todos los datos bilaterales; mantiene AV, graduaciones y cover registrados. |
| #54/#55 | Solo los ojos con AV que ya describen en #56/#57. Los ojos restantes siguen disponibles. |

**Coexistencias y límites:**

- #33 y #34 coexisten: valores K seleccionados y diferencia interocular son datos
  distintos. No se afirma ectasia ni normalidad desde una condición booleana.
- Las lesiones orgánicas registradas, pseudofaquia o K no vetan #54–57. Estas
  salidas conservan la AV y no identifican su causa. #32 puede coexistir con ellas
  y con #18; la deduplicación entre #54–57 no elimina los registros originales.
- La evaluación de `fondo_macular_otros` excluye ocurrencias ya explicadas por la
  ruta vascular/macular según ojo, término y contexto del propio evaluador (§4.9).
  No hay un veto general sobre todos sus hallazgos por cualquier aviso DMAE u oclusión.
- `fondo_vascular_diabetico` y `fondo_hipertensivo` pueden coexistir; otros hallazgos
  de retina, papila o mácula no eliminan automáticamente el registro vascular.
- #7 se integró en `fondo_glaucomatoso`; #27–28, #31, #37–39 y #49–52 se retiraron.
  #29 se conserva como recordatorio técnico separado. El resultado es **47 reglas
  clínicas y 1 recordatorio técnico**, sin reactivar inferencias retiradas.

## Apéndice B — Hallazgos urgentes

El prefijo literal `Hallazgo urgente:` del texto determinista es la fuente de
urgencia para el LLM y la salvaguarda H01. El modelo debe conservar el hecho, el
ojo y el plazo que la regla aporta; una recomendación genérica de valoración no
sustituye un plazo explícito. H01 comprueba el resultado y puede añadir el aviso
omitido o incompleto. El nombre histórico de una regla no otorga urgencia.

Las rutas que pueden aportar el prefijo, según los criterios de sus secciones, son:

- Fondo: #1 periferia, #2 síntomas de tracción, #3 oclusión, #4 émbolo, #5 papila,
  #8 mácula/DMAE, #10 hipertensión y #11 signos vasculares diabéticos. Los niveles
  de antecedente, estabilidad o seguimiento conservan su conducta propia; no se
  convierten en alerta aguda por el identificador.
- Pupilas, motilidad, campo, Amsler y segmento anterior: #12–19. La prioridad
  procede de signos/síntomas, certeza, evolución y lateralidad compatibles. Un DPAR
  estable o una catarata registrada sin alarma no implican por sí solos el mismo
  plazo que un cambio agudo. #18 conserva el mismo día para las situaciones de
  leucocoria, posición anómala con alarma compatible o evento posoperatorio
  afirmado que define §7.2; #19 conserva las rutas de superficie y síntomas de §7.1.
- Binocularidad/PPC y contexto visual: #42–48 y #53–57 únicamente cuando constan
  síntomas agudos reales. Diplopía de inicio agudo documentado requiere valoración
  el mismo día; pérdida visual súbita, dolor ocular con trauma actual o dolor con
  ojo rojo y fotofobia requieren urgencias inmediatas. Los síntomas de familiar,
  hipotéticos, negados, resueltos o de una fecha antigua no acreditan un episodio
  actual. La categoría de pantallas, PPC, cover, edad o magnitud de Rx no crea el
  plazo ni permite atribuir la alarma a esa exposición o desviación.

`glaucoma_asimetrico` mantiene evaluación preferente según sus hechos; su selección
no es una alerta urgente aislada. Los umbrales refractivos, queratométricos, BUT y
el recordatorio técnico #29 tampoco generan urgencia por su magnitud sola. Los
plazos de las demás rutas se conservan como los redacta cada regla, sin sustituirlos
por un único plazo común para todas las alertas.

## Apéndice C — Buenas prácticas para registrar los datos

1. **Describe el hallazgo y su anatomía**, con ojo, certeza y evolución cuando se
   conocen. Términos como carnosidad, hiperemia, erosión o disfunción glandular
   conservan lo escrito; no equivalen automáticamente a pterigión, lesión corneal
   o anomalía de Meibomio. Una hipótesis no es un diagnóstico confirmado.
2. **Separa positivos, negativos, antecedentes y planes.** Identifica si el dato
   corresponde al paciente o a un familiar. Anota cuándo empezó un síntoma; una
   recomendación de actuar pronto no acredita inicio reciente.
3. **Registra C/D con su cifra y ojo**, por ejemplo `c/d 0.7`. El valor se interpreta
   junto al resto de los signos y contexto documentados, sin un umbral universal
   que certifique normalidad o enfermedad.
4. **Cover test:** usa `OD: Tipo [y Sub] | OI: Tipo [y Sub]`. Si no se realizó,
   envía `null`; no completes ortoforia. Si falta subtipo, no inventes foria/tropía
   ni distancia, corrección utilizada o magnitud prismática.
5. **Reflejos, motilidad, campos y Amsler:** registra los hallazgos reales y sus
   calificadores. Un campo nulo no prueba una exploración normal.
6. **PPC y BUT:** el catálogo es 1–15 en cm y segundos, respectivamente. Un valor
   inválido se descarta mediante coerción tolerante; eso elimina ese componente
   numérico, sin cancelar otros datos válidos. Anota técnica y fiabilidad conocidas.
7. **Motivo de consulta:** describe molestias oculares/visuales reales, ojo y
   temporalidad. Ocupación, pantalla o cefalea/fatiga general aisladas no sustituyen
   los síntomas que exige una correlación. Conserva discrepancias entre texto y
   categorías estructuradas para contrastarlas.
8. **AKR y Rx final:** conserva los valores y componentes presentes, dejando los
   faltantes nulos. No copies una graduación para completar otra. K media requiere
   media explícita o K1/K2 completos; un eje de cilindro K aislado no acredita su
   convención. `taken_at` se ignora para inferencia y no prueba simultaneidad.
9. **Edad:** conserva la edad conocida o `null`. Los cortes operativos no confirman
   diagnóstico ni convierten la edad desconocida en una categoría asumida.
10. **Tipo de lente y seguimiento:** registra el diseño prescrito y controles
    referidos. No acreditan función acomodativa, corrección usada durante una
    prueba ni un mecanismo fisiológico. La inferencia de #49 sigue retirada.

## Apéndice D — Cadena final de generación (H01 y entrega)

Verificada con proveedor simulado (`tests/test_cadena_generacion.py`); **no se ha ensayado Qwen real ni el
Ubuntu de destino**.

- **Seguimiento y urgencia:** el texto de `recomendacion_seguimiento` se añade al final, pero con una urgencia
  activa se omiten sus oraciones que la contradicen (*"No requiere acudir a urgencias"*, plazos rutinarios,
  falsa normalidad); el resto se conserva. Los logs registran cuántas se omitieron, no su contenido.
- **Generación cortada (`done_reason=length`):** se reintenta una vez con más `num_predict` (sin salir de
  `num_ctx`); si persiste se rechaza (`GeneracionIncompletaError`). Con una urgencia activa la API entrega el
  **respaldo determinista** (avisos urgentes + seguimiento compatible) marcado `"origen": "determinista"`; sin
  urgencia responde 502. Un respaldo o un error nunca se guarda en caché.
- **Impresión vacía:** si tras la depuración no queda texto (p. ej. *"No se dispone de datos clínicos."*) no
  hay éxito HTTP con texto vacío ni caché: 502 (o respaldo determinista con urgencia).
- **Fidelidad mínima (contención, no verificación clínica):** se omiten las oraciones del modelo con cifras de
  riesgo (mmHg, µm, %, mm) ausentes de los datos recibidos, con cirugía/fármacos/tratamientos que el payload no
  menciona o con un diagnóstico grave (glaucoma, catarata, queratocono, desprendimiento, retinopatía, uveítis,
  tumor…) que ni el payload ni las correlaciones contienen. Si nada sobrevive, no hay éxito vacío (502 o respaldo
  determinista con urgencia). No sustituye una revisión clínica de la salida: la fidelidad general del texto libre
  no está garantizada (un diagnóstico que sí aparece en las correlaciones puede repetirse sin sustento propio).
- **API:** un `Bearer` no ASCII responde 401 (antes 500); `/health` responde 503 `degraded` con
  `api_key_configurada=false`; ningún log de nivel INFO/WARNING contiene texto clínico (solo DEBUG, que
  incluye el prompt completo: con `LOG_LEVEL=DEBUG` `logs/inference.log` persiste contenido del paciente;
  mantener INFO en producción y justificar acceso y retención si se activa).
- **Segmentación de oraciones:** el punto tras `OD`/`OI` cierra la oración (la abreviatura `D.` de dioptrías ya
  no se protege dentro de `OD.`).

## Resumen ejecutivo

- **47 correlaciones clínicas y 1 recordatorio técnico**, con IDs históricos
  conservados y #29 separado de los hechos médicos del LLM y de la lista HTTP.
- **Determinismo:** los datos normalizados y las reglas fijan los hechos y plazos;
  el LLM integra su redacción. `correlaciones_activadas` permite trazabilidad.
- **Contrato:** nulos, valores, ojos, fuentes, certeza y contexto documentados
  limitan lo que se describe; no completan exploraciones ni causas desconocidas.
- **Queratometría y refracción:** los cortes operativos seleccionan cifras para
  verificación/evaluación; no confirman ectasia, mecanismo corneal o lenticular.
- **Deduplicación:** conserva los hechos ya descritos y deja los demás disponibles,
  con las condiciones específicas del Apéndice A.
- **Evidencia:** las pruebas de `tests/` y sus casos sintéticos documentan el
  comportamiento comprobado; no constituyen certificación clínica.
