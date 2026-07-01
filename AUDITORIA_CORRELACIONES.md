# Auditoría Completa de Correlaciones
**Archivo fuente:** `app/correlaciones.py`
**Fecha de auditoría original:** 2026-04-27
**Última actualización:** 2026-07-01 (integración de queratometría + afinación clínica de las 36 correlaciones)
**Total de correlaciones registradas en CORRELACIONES:** 36

> **Nota de esta revisión (2026-07-01):** el frontend (SaaS) ahora envía también los datos de queratometría dentro del objeto `akr` (`k1_d/mm/eje`, `k2_d/mm/eje`, `k_promedio_d/mm`, `k_cilindro`, `k_cilindro_eje`, más metadata de sesión `pd`, `vd`, `ker_index`). Nueve correlaciones se afinaron para usar esos datos como **apoyo/confirmación o diagnóstico diferencial**, nunca como diagnóstico de ectasia/queratocono. La fundamentación clínica completa vive en [afinacion_correlaciones_queratometria.md](afinacion_correlaciones_queratometria.md). Umbrales queratométricos usados: K sospechosa ≥ 47.20 D, K ectasia ≥ 48.70 D, cilindro corneal relevante ≥ 0.75 D, cilindro corneal muy alto ≥ 4.00 D, K plana < 41.00 D, tolerancia de eje ± 20°. Este documento refleja el código real al 2026-07-01.

---

## Correlación 1: fondo_periferico_riesgo

### Condición (_cond)
```python
@_memoize_cond
def _cond_fondo_periferico_riesgo(req: ImpresionClinicaRequest) -> bool:
    return _fondo_contains(req, _KEYWORDS_FONDO_PERIFERICO)
```
- **Campos evaluados:** `req.clinica.fondo_de_ojo`
- **Keywords:** `"desgarro"`, `"agujero retiniano"`, `"agujero atrofico"`, `"agujero operculado"`, `"lattice"`, `"degeneracion reticular"`, `"degeneracion en empalizada"`, `"palizada"`, `"blanco con presion"`, `"desprendimiento"`, `"schisis"`, `"retinosquisis"`
- **Negation window:** sí (`allow_negation_window=True`)
- **Dependencias:** ninguna (es la más prioritaria; suprime `fondo_vascular_diabetico`)

### Texto actual (_texto)
Función dinámica `_texto_fondo_periferico_riesgo`:
```
"Hallazgo urgente: en la retina periferica se documenta {hallazgo}, que amerita
valoracion retinologica urgente y posible tratamiento profilactico."
```
Donde `{hallazgo}` es la lista normalizada vía `_KEYWORDS_FONDO_PERIFERICO_MAP`:
- `desgarro` → "desgarro retiniano"
- `agujero retiniano` → "agujero retiniano"
- `agujero atrofico` → "agujero atrofico"
- `agujero operculado` → "agujero operculado"
- `lattice` / `degeneracion en empalizada` / `palizada` → "degeneracion lattice"
- `degeneracion reticular` → "degeneracion reticular"
- `blanco con presion` → "blanco con presion"
- `desprendimiento` → "desprendimiento de retina"
- `schisis` → "schisis periferica"
- `retinosquisis` → "retinosquisis"

Si no se extrae ningún hallazgo concreto: `{hallazgo}` = `"hallazgo periferico de riesgo"`.

### Ejemplo de activación
```
clinica.fondo_de_ojo = "desgarro retiniano periférico OI"
```

### Afinación clínica (2026-07-01)
Se agregaron sinónimos en español que un optometrista real escribe: `"degeneracion en empalizada"` y `"palizada"` (traducciones de *lattice*), y `"agujero atrofico"` / `"agujero operculado"` (antes solo estaba `"agujero retiniano"`). **No** se incluye "desprendimiento de vítreo posterior/DVP" a propósito: es un hallazgo benigno frecuente que generaría falsos positivos. Fuente: [Lattice Degeneration – EyeWiki](https://eyewiki.org/Lattice_Degeneration).

### Clasificación
- [RECOMENDACION] — "amerita valoracion retinologica urgente y posible tratamiento profilactico"

---

## Correlación 2: papila_patologica

### Condición (_cond)
```python
@_memoize_cond
def _cond_papila_patologica(req: ImpresionClinicaRequest) -> bool:
    return _fondo_contains(req, _KEYWORDS_PAPILA_NO_GLAUCOMA)
```
- **Campos evaluados:** `req.clinica.fondo_de_ojo`
- **Keywords:** `"palidez papilar"`, `"palidez de papila"`, `"atrofia optica"`, `"atrofia papilar"`, `"edema de papila"`, `"papiledema"`, `"neuritis optica"`, `"borramiento de bordes"`, `"bordes borrosos"`
- **Negation window:** sí
- **Dependencias:** ninguna directa; se evalúa antes que `glaucoma_asimetrico` en la lista

### Texto actual (_texto)
Función dinámica `_texto_papila_patologica` con dos ramas:

**Rama emergencia** (si el fondo contiene: `"papiledema"`, `"edema de papila"`, `"borramiento de bordes"` o `"bordes borrosos"`):
```
"Hallazgo urgente: los hallazgos del nervio optico documentados son compatibles
con edema de papila, lo que amerita evaluacion neurooftalmologica urgente para
descarte de hipertension intracraneal."
```

**Rama estándar** (cualquier otro hallazgo de la lista):
```
"Se documenta alteracion del nervio optico no asociada a excavacion glaucomatosa,
ameritando valoracion neurooftalmologica para caracterizacion etiologica."
```

### Ejemplo de activación
```
clinica.fondo_de_ojo = "palidez papilar temporal OD"   → rama estándar
clinica.fondo_de_ojo = "papiledema bilateral"          → rama emergencia
```

### Afinación clínica (2026-07-01)
Verificada contra la clínica: papiledema/edema bilateral es signo de emergencia (posible HIC); palidez/atrofia son crónicos que ameritan estudio sin urgencia inmediata. La bifurcación es correcta. Fuente: [Optic Disc Swelling – patient.info](https://patient.info/doctor/history-examination/optic-disc-swelling-including-papilloedema).

### Clasificación
- [ATRIBUCION CAUSAL] — "compatibles con edema de papila" / "alteracion del nervio optico no asociada a excavacion glaucomatosa"
- [RECOMENDACION] — "evaluacion neurooftalmologica urgente" / "valoracion neurooftalmologica para caracterizacion etiologica"

---

## Correlación 3: glaucoma_asimetrico

### Condición (_cond)
```python
@_memoize_cond
def _cond_glaucoma_asimetrico(req: ImpresionClinicaRequest) -> bool:
    if req.clinica is None:
        return False
    txt_pupilas = _normalize_text(req.clinica.reflejos_pupilares)
    hay_dpar = any(
        _keyword_matches(txt_pupilas, k, allow_negation_window=True)
        for k in ("dpar", "marcus gunn")
    )
    if not hay_dpar:
        return False
    return _fondo_contains(req, _KEYWORDS_FONDO_GLAUCOMATOSO)
```
- **Campos evaluados:** `req.clinica.reflejos_pupilares` (busca "dpar" o "marcus gunn") + `req.clinica.fondo_de_ojo` (keywords glaucomatosas)
- **Keywords fondo glaucomatoso:** `"c/d 0.5"`–`"c/d 0.9"`, `"cup/disc 0.5"`–`"0.9"`, `"excavacion"`, `"papila asimetrica"`, `"asimetria c/d"`, `"muesca"`, `"notch"`, `"hemorragia peripapilar"`, `"rima neural adelgazada"`
- **Negation window:** sí (para fondo **y**, desde 2026-07-01, para la detección de DPAR en pupilas)
- **Dependencias:** suprime `fondo_glaucomatoso` y `pupilas_alteradas`

### Texto actual (_texto)
Texto fijo:
```
"Hallazgo urgente: se documenta excavacion papilar aumentada con defecto pupilar
aferente relativo, lo que indica compromiso asimetrico del nervio optico con
probable repercusion funcional, ameritando valoracion oftalmologica priorizada."
```

### Ejemplo de activación
```
clinica.reflejos_pupilares = "DPAR positivo OI"
clinica.fondo_de_ojo = "excavacion aumentada c/d 0.8 OI, c/d 0.5 OD"
```

### Afinación clínica (2026-07-01)
Dos correcciones: (1) **bug de falso positivo** — la detección de "dpar"/"marcus gunn" en pupilas usaba `in` simple sin ventana de negación; ahora usa `_keyword_matches(..., allow_negation_window=True)`, de modo que "sin DPAR" ya **no** activa la correlación. (2) **sobre-interpretación** — el texto decía "compromiso funcional confirmado"; se suavizó a "probable repercusion funcional" (el sistema no tiene campo visual/OCT para confirmar). Fuente: [Marcus Gunn Pupil – StatPearls](https://www.ncbi.nlm.nih.gov/books/NBK557675/).

### Clasificación
- [DIAGNOSTICO] — "compromiso asimetrico del nervio optico" (glaucoma)
- [ATRIBUCION CAUSAL] — "indica compromiso asimetrico del nervio optico con probable repercusion funcional"
- [RECOMENDACION] — "ameritando valoracion oftalmologica priorizada"

---

## Correlación 4: pupilas_alteradas

### Condición (_cond)
```python
def _cond_pupilas_alteradas(req: ImpresionClinicaRequest) -> bool:
    if _cond_glaucoma_asimetrico(req):
        return False
    return bool(_pupilas_hallazgos(req.clinica))
```
Con helper (nuevo 2026-07-01) que descarta anisocoria fisiológica/benigna:
```python
def _pupilas_hallazgos(clinica) -> list[str]:
    if clinica is None:
        return []
    hallazgos = _extract_normalized_findings(
        clinica.reflejos_pupilares, _KEYWORDS_PUPILAS, allow_negation_window=True)
    texto_norm = _normalize_text(clinica.reflejos_pupilares)
    if "anisocoria" in hallazgos and any(k in texto_norm for k in _KEYWORDS_ANISOCORIA_BENIGNA):
        hallazgos = [h for h in hallazgos if h != "anisocoria"]
    return hallazgos
```
- **Campos evaluados:** `req.clinica.reflejos_pupilares`
- **Keywords:** `"anisocoria"`, `"midriasis"`, `"miosis"`, `"dpar"`, `"marcus gunn"`, `"no reactivo"`, `"no reactiva"`, `"irregular"`, `"discoria"`, `"ausente"`
- **Keywords de exclusión (anisocoria benigna):** `"anisocoria fisiologica"`, `"anisocoria benigna"`, `"anisocoria simple"`
- **Negation window:** sí
- **Dependencias:** se suprime si `_cond_glaucoma_asimetrico` está activa

### Texto actual (_texto)
```
"En la exploracion pupilar se documenta {hallazgos}, lo que amerita valoracion
neurooftalmologica."
```
**Sufijo adicional** (si "defecto pupilar aferente relativo" está en los hallazgos):
```
" Hallazgo urgente: la presencia de defecto pupilar aferente relativo es
indicativa de patologia de via optica y requiere evaluacion urgente."
```
Normalización vía `_KEYWORDS_PUPILAS`: `dpar`/`marcus gunn` → "defecto pupilar aferente relativo"; `no reactivo`/`no reactiva` → "pupila no reactiva"; `irregular` → "pupila irregular"; `ausente` → "respuesta pupilar ausente".

### Ejemplo de activación
```
clinica.reflejos_pupilares = "anisocoria 1mm, DPAR OD"   → texto base + sufijo urgente
clinica.reflejos_pupilares = "anisocoria fisiologica"    → NO activa (excluida)
```

### Afinación clínica (2026-07-01)
Se agregó la exclusión de anisocoria explícitamente calificada de fisiológica/benigna/simple (prevalencia poblacional ~15–30%, hallazgo benigno). La ventana de negación estándar no la cubría porque el calificador va **después** del sustantivo. Fuente: [Physiological anisocoria – Wikipedia](https://en.wikipedia.org/wiki/Physiological_anisocoria).

### Clasificación
- [ATRIBUCION CAUSAL] — "indicativa de patologia de via optica"
- [RECOMENDACION] — "amerita valoracion neurooftalmologica" / "requiere evaluacion urgente"

---

## Correlación 5: fondo_glaucomatoso

### Condición (_cond)
```python
@_memoize_cond
def _cond_fondo_glaucomatoso(req: ImpresionClinicaRequest) -> bool:
    if _cond_glaucoma_asimetrico(req):
        return False
    return _fondo_contains(req, _KEYWORDS_FONDO_GLAUCOMATOSO)
```
- **Campos evaluados:** `req.clinica.fondo_de_ojo`
- **Keywords:** `"c/d 0.5"`–`"c/d 0.9"`, `"cup/disc 0.5"`–`"0.9"`, `"excavacion"`, `"papila asimetrica"`, `"asimetria c/d"`, `"muesca"`, `"notch"`, `"hemorragia peripapilar"`, `"rima neural adelgazada"`
- **Negation window:** sí
- **Dependencias:** se suprime si `_cond_glaucoma_asimetrico` está activa

### Texto actual (_texto)
```
"Se documentan hallazgos papilares con excavacion aumentada y/o alteracion del
anillo neurorretiniano, ameritando valoracion oftalmologica con tonometria y
perimetria para descarte de glaucoma."
```

### Ejemplo de activación
```
clinica.fondo_de_ojo = "excavacion c/d 0.7, muesca inferior OD"
clinica.reflejos_pupilares = "isocoricos normoreactivos"   # sin DPAR
```

### Afinación clínica (2026-07-01)
Se añadieron `"c/d 0.5"` y `"cup/disc 0.5"`: 0.5 es el umbral estándar de sospecha de glaucoma en varias guías (se mantiene en 0.5, no menor, para no capturar papilas grandes fisiológicas). El texto es descriptivo + recomienda tonometría/perimetría (no diagnostica glaucoma). Fuente: [CDR asymmetry ≥0.2, CDR ≥0.5 – PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11656306/).

### Clasificación
- [ATRIBUCION CAUSAL] — "hallazgos papilares con excavacion aumentada"
- [RECOMENDACION] — "ameritando valoracion oftalmologica con tonometria y perimetria para descarte de glaucoma"

---

## Correlación 6: fondo_macular_dmae

### Condición (_cond)
```python
@_memoize_cond
def _cond_fondo_macular_dmae(req: ImpresionClinicaRequest) -> bool:
    return _fondo_contains(req, _KEYWORDS_FONDO_DMAE)
```
- **Campos evaluados:** `req.clinica.fondo_de_ojo`
- **Keywords:** `"drusas"`, `"drusen"`, `"alteracion pigmentaria"`, `"alteracion del epr"`, `"atrofia geografica"`, `"membrana neovascular"`, `"mnvc"`, `"cnv"`, `"mev"`, `"epiteliopatia"`, `"dmae"`, `"degeneracion macular"`
- **Negation window:** sí
- **Dependencias:** su activación suprime `fondo_vascular_diabetico`

### Texto actual (_texto)
```
"Se documentan hallazgos maculares degenerativos en fondo de ojo, ameritando OCT
macular para caracterizacion y monitorizacion."
```

### Ejemplo de activación
```
clinica.fondo_de_ojo = "drusas duras y blandas maculares bilaterales"
```

### Afinación clínica (2026-07-01)
Se agregó `"mev"` (variante de abreviatura para membrana neovascular). Cobertura alineada con AREDS. El texto es descriptivo ("hallazgos maculares degenerativos") y no afirma DMAE definitiva. Fuente: [AREDS Report No. 18 – PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC1473206/).

### Clasificación
- [ATRIBUCION CAUSAL] — "hallazgos maculares degenerativos"
- [RECOMENDACION] — "ameritando OCT macular para caracterizacion y monitorizacion"

---

## Correlación 7: fondo_macular_otros

### Condición (_cond)
```python
@_memoize_cond
def _cond_fondo_macular_otros(req: ImpresionClinicaRequest) -> bool:
    return _fondo_contains(req, _KEYWORDS_FONDO_MACULAR_OTROS)
```
- **Campos evaluados:** `req.clinica.fondo_de_ojo`
- **Keywords:** `"edema macular"`, `"membrana epirretiniana"`, `"mer"`, `"pucker"`, `"agujero macular"`, `"quiste macular"`, `"coroidopatia serosa"`, `"corioretinopatia serosa"`, `"crsc"`
- **Negation window:** sí
- **Dependencias:** su activación suprime `fondo_vascular_diabetico`

### Texto actual (_texto)
```
"En la region macular se documenta alteracion estructural que amerita OCT y
valoracion retinologica."
```

### Ejemplo de activación
```
clinica.fondo_de_ojo = "membrana epirretiniana OD"
```

### Afinación clínica (2026-07-01)
Se añadieron `"corioretinopatia serosa"` y `"crsc"` como sinónimos de uso real (antes solo `"coroidopatia serosa"`, forma menos frecuente).

### Clasificación
- [RECOMENDACION] — "amerita OCT y valoracion retinologica"

---

## Correlación 8: fondo_hipertensivo

### Condición (_cond)
```python
@_memoize_cond
def _cond_fondo_hipertensivo(req: ImpresionClinicaRequest) -> bool:
    return _fondo_contains(req, _KEYWORDS_FONDO_HIPERTENSIVO)
```
- **Campos evaluados:** `req.clinica.fondo_de_ojo`
- **Keywords:** `"tortuosidad vascular"`, `"tortuosidad"`, `"cruces arteriovenosos"`, `"cruces av"`, `"signo de gunn"`, `"estrechamiento arterial"`, `"hilos de cobre"`, `"hilos de plata"`, `"algodonoso"`, `"cotton wool"`, `"salus"`, `"ingurgitacion venosa"`, `"hemorragia en llama"`
- **Negation window:** sí
- **Dependencias:** ninguna (ya **no** suprime `fondo_vascular_diabetico`, ver Correlación 9)

### Texto actual (_texto)
```
"Se documentan hallazgos vasculares en fondo de ojo con alteraciones
arteriovenosas, ameritando correlacion con cifras tensionales sistemicas."
```

### Ejemplo de activación
```
clinica.fondo_de_ojo = "cruces arteriovenosos grado II, hilos de cobre"
```

### Afinación clínica (2026-07-01)
Se **movió** `"hemorragia en llama"` (flame hemorrhage) desde el set diabético a este set: es un hallazgo clásicamente asociado a retinopatía **hipertensiva** y oclusiones venosas (capa de fibras nerviosas), no a diabetes (que se caracteriza por hemorragias "en mancha/puntiformes" profundas, ya presentes en el set diabético). Alineado con Keith-Wagener-Barker. Fuentes: [Flame hemorrhages – EyesOnEyeCare](https://eyesoneyecare.com/resources/what-ophthalmology-residents-should-know-about-flame-hemorrhages/), [KWB classification – StatPearls](https://www.ncbi.nlm.nih.gov/books/NBK525980/).

### Clasificación
- [ATRIBUCION CAUSAL] — "hallazgos vasculares... con alteraciones arteriovenosas"
- [RECOMENDACION] — "ameritando correlacion con cifras tensionales sistemicas"

---

## Correlación 9: fondo_vascular_diabetico

### Condición (_cond)
```python
@_memoize_cond
def _cond_fondo_vascular_diabetico(req: ImpresionClinicaRequest) -> bool:
    if any((
        _cond_fondo_periferico_riesgo(req),
        _cond_fondo_glaucomatoso(req),
        _cond_fondo_macular_dmae(req),
        _cond_fondo_macular_otros(req),
    )):
        return False
    return _fondo_contains(req, _KEYWORDS_VASCULARES_DIABETICOS)
```
- **Campos evaluados:** `req.clinica.fondo_de_ojo`
- **Keywords:** `"microaneurisma"`, `"microaneurismas"`, `"exudado"`, `"hemorragia retiniana"`, `"hemorragia intraretin"`, `"hemorragia en mancha"`, `"hemorragia puntiforme"`, `"neovas"`, `"rubeosis"`
- **Negation window:** sí
- **Dependencias:** se suprime si `fondo_periferico_riesgo`, `fondo_glaucomatoso`, `fondo_macular_dmae` o `fondo_macular_otros` están activas. **Ya NO se suprime contra `fondo_hipertensivo`.**

### Texto actual (_texto)
```
"Se documentan hallazgos vasculares en fondo de ojo con presencia de alteraciones
microvasculares, ameritando correlacion sistemica (control glucemico) y valoracion
retinologica."
```

### Ejemplo de activación
```
clinica.fondo_de_ojo = "microaneurismas periféricos, exudados duros OD"
```

### Afinación clínica (2026-07-01)
Dos cambios: (1) se **quitó** `"hemorragia en llama"` (reubicada en `fondo_hipertensivo`, ver Correlación 8). (2) se **eliminó la supresión contra `fondo_hipertensivo`**: retinopatía diabética e hipertensiva coexisten con frecuencia (comorbilidad DM2 + HTA) y usan hallazgos distintos que ambos merecen mencionarse; la supresión anterior perdía la mención de microaneurismas/exudados en pacientes diabéticos-hipertensos. La supresión se mantiene solo contra procesos anatómicamente distintos (periférico/glaucomatoso/macular). Fuente: [Retinal Hemorrhage – StatPearls](https://www.ncbi.nlm.nih.gov/books/NBK560777/).

### Clasificación
- [ATRIBUCION CAUSAL] — "hallazgos vasculares... con presencia de alteraciones microvasculares"
- [RECOMENDACION] — "ameritando correlacion sistemica (control glucemico) y valoracion retinologica"

---

## Correlación 10: motilidad_alterada

### Condición (_cond)
```python
def _cond_motilidad_alterada(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    return _contains_keyword(clinica.motilidad_ocular, _KEYWORDS_MOTILIDAD, allow_negation_window=True)
```
- **Campos evaluados:** `req.clinica.motilidad_ocular`
- **Keywords:** `"limitacion"`, `"paresia"`, `"paralisis"`, `"restriccion"`, `"nistagmo"`, `"nistagmus"`, `"dolor con movimiento"`, `"dolor al movimiento"`, `"sobreacti"`, `"hiperfuncion"`, `"hipoaccion"`, `"hipofuncion"`, `"sincinesia"`, `"duane"`, `"oftalmoplejia"`, `"oftalmoplegia"`
- **Negation window:** sí
- **Dependencias:** ninguna

### Texto actual (_texto)
```
"Se documenta alteracion de la motilidad ocular, lo que amerita estudio de vias
motoras y posible interconsulta neurooftalmologica."
```

### Ejemplo de activación
```
clinica.motilidad_ocular = "limitación de aducción OD"
```

### Afinación clínica (2026-07-01)
Cobertura verificada (pares craneales III/IV/VI, patrones de sobre/infra-acción, nistagmo, Duane, sincinesias). Sin cambios de keywords; estrabismo manifiesto se captura mejor vía `cover_test` (evita duplicación). Fuente: [Cranial Nerve III Palsy – StatPearls](https://www.ncbi.nlm.nih.gov/books/NBK526112/).

### Clasificación
- [RECOMENDACION] — "amerita estudio de vias motoras y posible interconsulta neurooftalmologica"

---

## Correlación 11: campos_visuales_alterados

### Condición (_cond)
```python
def _cond_campos_visuales_alterados(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    texto = _normalize_text(clinica.confrontacion_campos_visuales)
    if not texto:
        return False
    if any(neg in texto for neg in _KEYWORDS_CAMPOS_NEGATIVOS):
        return False
    return _contains_keyword(clinica.confrontacion_campos_visuales, _KEYWORDS_CAMPOS_POSITIVOS, allow_negation_window=True)
```
- **Campos evaluados:** `req.clinica.confrontacion_campos_visuales`
- **Keywords positivas:** `"escotoma"`, `"defecto"`, `"hemianopsia"`, `"cuadrantopsia"`, `"constriccion"`, `"restriccion"`, `"campo reducido"`, `"alteracion"`, `"no responde"`
- **Keywords negativas (suprimen):** `"sin defect"`, `"sin alteracion"`, `"normal"`, `"integro"`
- **Negation window:** sí (para positivas)
- **Dependencias:** ninguna

### Texto actual (_texto)
```
"La confrontacion de campos visuales revela alteracion que amerita perimetria
automatizada para caracterizacion del defecto."
```

### Ejemplo de activación
```
clinica.confrontacion_campos_visuales = "escotoma paracentral OD"
```

### Afinación clínica (2026-07-01)
Se agregaron `"restriccion"` y `"campo reducido"` (formas comunes de describir constricción concéntrica). Se conservan `"defecto"`/`"alteracion"` genéricas por sensibilidad (la confrontación es un test grosero), mitigadas por las keywords negativas. Fuente: [Sensitivity/specificity confrontation VF – PMC2571584](https://pmc.ncbi.nlm.nih.gov/articles/PMC2571584/).

### Clasificación
- [RECOMENDACION] — "amerita perimetria automatizada para caracterizacion del defecto"

---

## Correlación 12: opacidad_cristaliniana

### Condición (_cond)
```python
@_memoize_cond
def _cond_opacidad_cristaliniana(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    texto = " ".join(filter(None, [clinica.anexos_oculares, clinica.fondo_de_ojo]))
    return _contains_keyword(texto, _KEYWORDS_OPACIDAD_CRISTALINO, allow_negation_window=True)
```
- **Campos evaluados:** `req.clinica.anexos_oculares` + `req.clinica.fondo_de_ojo` (concatenados)
- **Keywords:** `"catarata"`, `"cataratas"`, `"opacidad cristaliniana"`, `"opacidad del cristalino"`, `"facoesclerosis"`, `"esclerosis nuclear"`, `"pseudofaquia"`, `"pseudofaco"`, `"pseudofaquico"`, `"afaquia"`, `"afaquico"`
- **Negation window:** sí
- **Dependencias:** su activación suprime `adulto_mayor_screening`

### Texto actual (_texto)
```
"Se documenta alteracion del cristalino, ameritando evaluacion biomicroscopica
para caracterizacion y estadificacion de la opacidad."
```

### Ejemplo de activación
```
clinica.anexos_oculares = "catarata nuclear incipiente OD"
```

### Afinación clínica (2026-07-01)
Se agregó `"esclerosis nuclear"` (sinónimo muy usado de facoesclerosis). El texto se mantiene genérico (no clasifica subtipo LOCS III desde texto libre, apropiado). Fuente: [LOCS III – PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC12454382/).

### Clasificación
- [RECOMENDACION] — "ameritando evaluacion biomicroscopica para caracterizacion y estadificacion de la opacidad"

---

## Correlación 13: but_critico

### Condición (_cond)
```python
def _cond_but_critico(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    but = clinica.ojo_seco_but_seg
    return but is not None and but < 5
```
- **Campos evaluados:** `req.clinica.ojo_seco_but_seg`
- **Umbral:** BUT < 5 segundos
- **Dependencias:** ninguna; rango exclusivo respecto a `but_pantallas` y `but_limitrofe` (5–9)

### Texto actual (_texto)
Función dinámica:
```
"El tiempo de ruptura lagrimal de {but}s es patologicamente bajo, compatible con
ojo seco clinico que amerita evaluacion."
```

### Ejemplo de activación
```
clinica.ojo_seco_but_seg = 3
→ "El tiempo de ruptura lagrimal de 3s es patologicamente bajo, compatible con ojo seco clinico que amerita evaluacion."
```

### Afinación clínica (2026-07-01)
Umbral BUT < 5 s coincide con TFOS DEWS II (< 5 s = clínicamente crítico, < 10 s = anormal). Se restauró la cláusula clínica "compatible con ojo seco... amerita evaluacion" que una optimización previa había recortado a solo el dato numérico.

### Clasificación
- [DIAGNOSTICO] — "ojo seco clinico"
- [ATRIBUCION CAUSAL] — "compatible con ojo seco clinico"
- [RECOMENDACION] — "amerita evaluacion"

---

## Correlación 14: miopia_magna

### Condición (_cond)
```python
@_memoize_cond
def _cond_miopia_magna(req: ImpresionClinicaRequest) -> bool:
    refraccion = req.refraccion
    if refraccion is None:
        return False
    for ojo in (refraccion.od, refraccion.oi):
        ee = _equivalente_esferico(ojo.esfera, ojo.cilindro)
        if ee is not None and ee <= -6.00:
            return True
    return False
```
- **Campos evaluados:** `req.refraccion.od/oi.esfera`, `.cilindro`
- **Umbral:** EE ≤ -6.00 D en cualquier ojo (muy alta si EE ≤ -8.00)
- **Dependencias:** su activación suprime `adulto_mayor_screening`

### Texto actual (_texto)
Función dinámica `_texto_miopia_magna`:
```
"Se documenta miopia de magnitud {alta|muy alta} en {ojos}, lo que conlleva
{mayor riesgo|riesgo significativamente elevado} de patologia retiniana periferica
y macular."
```
**Addendum queratométrico** (si algún ojo tiene curvatura corneal pronunciada, `_keratometry_suggests_corneal_irregularity`):
```
" La queratometria muestra curvatura corneal pronunciada en {ojos}, lo que sugiere
un componente corneal (no exclusivamente axial) en la magnitud miopica, y amerita
estudio topografico antes de asumir el mismo riesgo de patologia retiniana
periferica asociado a la miopia axial pura."
```

### Ejemplo de activación
```
refraccion.od.esfera = -7.00, refraccion.od.cilindro = -0.50   # EE = -7.25 → "alta"
akr.od.k2_d = 49.00, akr.od.k_cilindro = -2.50                  # + addendum corneal
```

### Afinación clínica (2026-07-01)
La miopía magna clásica es **axial** (riesgo retiniano periférico/macular real). El addendum queratométrico avisa que una curvatura corneal pronunciada sugiere componente corneal (no exclusivamente axial), que **no** conlleva necesariamente el mismo riesgo retiniano, y orienta a topografía antes de asumirlo. Se restauró la cláusula de riesgo. Ver [afinacion_correlaciones_queratometria.md](afinacion_correlaciones_queratometria.md) §3.5.

### Clasificación
- [ATRIBUCION CAUSAL] — "conlleva {mayor riesgo|riesgo significativamente elevado} de patologia retiniana"
- [RECOMENDACION] — (solo con addendum) "amerita estudio topografico"

---

## Correlación 15: hipermetropia_alta

### Condición (_cond)
```python
def _cond_hipermetropia_alta(req: ImpresionClinicaRequest) -> bool:
    refraccion = req.refraccion
    if refraccion is None:
        return False
    for ojo in (refraccion.od, refraccion.oi):
        ee = _equivalente_esferico(ojo.esfera, ojo.cilindro)
        if ee is not None and ee >= 5.00:
            return True
    return False
```
- **Campos evaluados:** `req.refraccion.od/oi.esfera`, `.cilindro`
- **Umbral:** EE ≥ +5.00 D en cualquier ojo
- **Dependencias:** ninguna

### Texto actual (_texto)
Función dinámica con dos ramas por edad:

**Rama edad ≥ 40 o desconocida:**
```
"Se documenta hipermetropia alta en {ojos}, lo que amerita evaluacion de la
profundidad de camara anterior ante el riesgo asociado de angulo camerular estrecho."
```
**Rama edad < 40:**
```
"Se documenta hipermetropia alta en {ojos}, con demanda acomodativa significativa
que amerita vigilancia de esoforia o esotropia acomodativa."
```
**Addendum queratométrico:**
- Si curvatura corneal pronunciada (`_format_corneal_irregularity`): `" La queratometria documenta curvatura corneal pronunciada en {ojos}, hallazgo que no explica por si solo la hipermetropia alta pero si modifica la interpretacion del astigmatismo asociado."`
- Si no, y K promedio plana (< 41 D, `_format_flat_keratometry`): `" La queratometria muestra curvatura corneal plana en {ojos}, compatible con un componente corneal (y no exclusivamente axial) de la hipermetropia."`

### Ejemplo de activación
```
refraccion.oi.esfera = +5.50, paciente.edad = 35   → rama joven
akr.od.k_promedio_d = 40.00                          → addendum K plana
```

### Afinación clínica (2026-07-01)
Se restauraron ambas cláusulas de recomendación (cámara anterior / vigilancia esoforia) que una optimización previa había recortado. Se agregó el addendum de K plana (< 41 D) como matiz de origen corneal vs axial (nuevo helper `_format_flat_keratometry`, sin umbral de alarma). Ver [afinacion_correlaciones_queratometria.md](afinacion_correlaciones_queratometria.md) §3.6.

### Clasificación
- [RECOMENDACION] — "amerita evaluacion de la profundidad de camara anterior" / "amerita vigilancia de esoforia o esotropia acomodativa"

---

## Correlación 16: anisometropia

### Condición (_cond)
```python
def _cond_anisometropia(req: ImpresionClinicaRequest) -> bool:
    refraccion = req.refraccion
    if refraccion is None:
        return False
    ee_od = _equivalente_esferico(refraccion.od.esfera, refraccion.od.cilindro)
    ee_oi = _equivalente_esferico(refraccion.oi.esfera, refraccion.oi.cilindro)
    if ee_od is None or ee_oi is None:
        return False
    return abs(ee_od - ee_oi) > 1.00
```
- **Campos evaluados:** `req.refraccion.od/oi.esfera`, `.cilindro` (+ `akr.od/oi.k_promedio_d`, `k_cilindro` para addendum)
- **Umbral:** |EE_OD − EE_OI| > 1.00 D
- **Dependencias:** ninguna

### Texto actual (_texto)
```
"Existe anisometropia {leve|moderada|severa} por diferencia de equivalente esferico
de {diff}D entre OD ({ee_od}) y OI ({ee_oi}); {cierre}."
```
- diff < 2.00 → "leve", cierre "con posible impacto en la fusion binocular"
- 2.00 ≤ diff ≤ 3.00 → "moderada", cierre "con posible impacto en la fusion binocular"
- diff > 3.00 → "severa", cierre "con diferencia significativa entre ambos ojos"
- signos opuestos (EE_OD·EE_OI < 0) → cierre "antimetropia con posible compromiso fusional"

**Addendum queratométrico** (si ambos ojos tienen queratometría):
- si |K_prom_OD − K_prom_OI| ≥ 1.00 D → `" La queratometria agrega asimetria corneal interocular de {X}D en K promedio."`
- si no, y |cil_corneal_OD − cil_corneal_OI| ≥ 1.50 D → `" La queratometria agrega asimetria interocular relevante del cilindro corneal."`

### Ejemplo de activación
```
refraccion.od.esfera = -1.00, refraccion.oi.esfera = -3.50   # diff EE = 2.50 → moderada
akr.od.k_promedio_d = 43.00, akr.oi.k_promedio_d = 45.50      # + addendum asimetria corneal
```

### Afinación clínica (2026-07-01)
Umbral > 1.00 D coincide con la definición clínica estándar; ≤ 3 D suele tolerarse (moderada). Se **decidió NO** extender el disparador a asimetría puramente queratométrica: la anisometropía es diferencia de **poder refractivo**, no de curvatura; la queratometría entra solo como addendum informativo. Ver [afinacion_correlaciones_queratometria.md](afinacion_correlaciones_queratometria.md) §3.7. Fuente: [Anisometropia – Cleveland Clinic](https://my.clevelandclinic.org/health/diseases/24274-anisometropia).

### Clasificación
- [OK] — describe hallazgo refractivo objetivo con cuantificación; "con posible impacto en la fusion binocular" es descriptor, no directiva

---

## Correlación 17: av_cc_limitada

### Condición (_cond)
```python
def _cond_av_cc_limitada(req: ImpresionClinicaRequest) -> bool:
    refraccion = req.refraccion
    if refraccion is None:
        return False
    return _av_es_limitada(refraccion.od.av_cc) or _av_es_limitada(refraccion.oi.av_cc)
```
- **Campos evaluados:** `req.refraccion.od/oi.av_cc` (+ `akr` para addendum)
- **Umbral:** denominador Snellen > 20
- **Dependencias:** ninguna

### Texto actual (_texto)
Por cada ojo con AV limitada: `"{label} ({av}): {categoria}"`, separados por "; ".
Categorías (`_av_categoria`): 21–30 leve, 31–50 moderada, 51–100 marcada, >100 severa.

**Addendum queratométrico** (si ese ojo tiene curvatura corneal irregular, `_keratometry_suggests_corneal_irregularity`):
```
", con queratometria compatible con irregularidad de la superficie corneal, lo que
puede explicar la limitacion de la agudeza visual pese a la correccion"
```

### Ejemplo de activación
```
refraccion.od.av_cc = "20/40"                              # moderada
akr.od.k2_d = 49.00, akr.od.k_cilindro = -2.50             # + addendum irregularidad corneal
```

### Afinación clínica (2026-07-01)
El addendum solo aparece con **irregularidad corneal franca** (no astigmatismo corneal regular, que se corrige bien con anteojos): solo la irregularidad ectásica explica biológicamente una AV corregida reducida. Ver [afinacion_correlaciones_queratometria.md](afinacion_correlaciones_queratometria.md) §3.8.

### Clasificación
- [OK] — describe hallazgo funcional objetivo; el addendum corneal es atribución causal cautelosa ("puede explicar")

---

## Correlación 18: ar_rx_espasmo_acomodativo

### Condición (_cond)
```python
@_memoize_cond
def _cond_ar_rx_espasmo_acomodativo(req: ImpresionClinicaRequest) -> bool:
    if req.refraccion is None or req.akr is None or req.paciente is None or req.clinica is None:
        return False
    edad = req.paciente.edad
    if edad is None or edad >= 40:
        return False
    if req.clinica.uso_pantallas not in ("btw2_6", "gt6"):
        return False
    for ojo in ("od", "oi"):
        esf_ar = getattr(req.akr, ojo).esfera
        esf_rx = getattr(req.refraccion, ojo).esfera
        if esf_ar is None or esf_rx is None:
            continue
        if (esf_rx - esf_ar) >= 0.50:
            return True
    return False
```
- **Campos evaluados:** `paciente.edad`, `clinica.uso_pantallas`, `akr.od/oi.esfera`, `refraccion.od/oi.esfera`
- **Umbrales:** edad < 40, uso_pantallas en ("btw2_6","gt6"), (esf_Rx − esf_AR) ≥ +0.50 en algún ojo
- **Dependencias:** suprime `ar_rx_variabilidad_inespecifica`

### Texto actual (_texto)
```
"El autorrefractometro documenta mayor componente miopico que la refraccion
subjetiva final en un paciente joven con uso intensivo de pantallas, patron
compatible con espasmo acomodativo que amerita control posterior y eventual
refraccion bajo cicloplejia."
```

### Ejemplo de activación
```
paciente.edad = 22, clinica.uso_pantallas = "gt6"
akr.od.esfera = -3.50, refraccion.od.esfera = -2.75   # esf_Rx - esf_AR = +0.75
```

### Afinación clínica (2026-07-01)
Patrón AR más miope que Rx en joven con trabajo cercano intensivo = pseudomiopía/espasmo acomodativo; la refracción bajo cicloplejia es el estándar diagnóstico. Se restauró la cláusula clínica completa. La queratometría **no aplica** (proceso acomodativo, no corneal). Fuente: [Pseudomyopia / accommodative spasm – Cureus](https://www.cureus.com/articles/462248).

### Clasificación
- [DIAGNOSTICO] — "espasmo acomodativo"
- [ATRIBUCION CAUSAL] — "patron compatible con espasmo acomodativo"
- [RECOMENDACION] — "amerita control posterior y eventual refraccion bajo cicloplejia"

---

## Correlación 19: ar_rx_cambio_cristalino

### Condición (_cond)
```python
@_memoize_cond
def _cond_ar_rx_cambio_cristalino(req: ImpresionClinicaRequest) -> bool:
    if req.refraccion is None or req.akr is None or req.paciente is None:
        return False
    edad = req.paciente.edad
    if edad is None or edad < 55:
        return False
    if _req_has_corneal_irregularity(req):
        return False
    for ojo in ("od", "oi"):
        esf_ar = getattr(req.akr, ojo).esfera
        esf_rx = getattr(req.refraccion, ojo).esfera
        if esf_ar is None or esf_rx is None:
            continue
        if abs(esf_ar - esf_rx) > 1.00:
            return True
    return False
```
- **Campos evaluados:** `paciente.edad`, `akr.od/oi.esfera`, `refraccion.od/oi.esfera` (+ queratometría para exclusión)
- **Umbrales:** edad ≥ 55, |esf_AR − esf_Rx| > 1.00 en algún ojo, y **sin** irregularidad corneal franca
- **Dependencias:** suprime `ar_rx_variabilidad_inespecifica`

### Texto actual (_texto)
```
"Se documenta discrepancia entre autorrefractometro y refraccion final en un
paciente mayor de 55 anos, sin patron queratometrico que explique primariamente la
diferencia refractiva, lo que puede reflejar cambios en el indice refractivo del
cristalino y amerita evaluacion biomicroscopica del segmento anterior."
```

### Ejemplo de activación
```
paciente.edad = 62
akr.oi.esfera = -1.00, refraccion.oi.esfera = +0.25   # |diff| = 1.25 > 1.00
# sin irregularidad corneal franca
```

### Afinación clínica (2026-07-01)
La hipótesis es miopización de índice por esclerosis nuclear (cambio **lenticular**). Si la queratometría muestra irregularidad corneal franca (≥ 47.20 D o cilindro ≥ 4 D), la correlación **se suprime** (cede a `ar_rx_variabilidad_inespecifica`), porque parte de la discrepancia sería corneal. Umbral alto para no sobre-suprimir casos reales de esclerosis nuclear. Ver [afinacion_correlaciones_queratometria.md](afinacion_correlaciones_queratometria.md) §3.2.

### Clasificación
- [ATRIBUCION CAUSAL] — "puede reflejar cambios en el indice refractivo del cristalino"
- [RECOMENDACION] — "amerita evaluacion biomicroscopica del segmento anterior"

---

## Correlación 20: ar_rx_variabilidad_inespecifica

### Condición (_cond)
```python
def _cond_ar_rx_variabilidad_inespecifica(req: ImpresionClinicaRequest) -> bool:
    if req.refraccion is None or req.akr is None:
        return False
    if _cond_ar_rx_espasmo_acomodativo(req) or _cond_ar_rx_cambio_cristalino(req):
        return False
    for ojo in ("od", "oi"):
        esf_ar = getattr(req.akr, ojo).esfera
        esf_rx = getattr(req.refraccion, ojo).esfera
        cil_ar = getattr(req.akr, ojo).cilindro
        cil_rx = getattr(req.refraccion, ojo).cilindro
        if esf_ar is not None and esf_rx is not None and abs(esf_ar - esf_rx) > 1.00:
            return True
        if cil_ar is not None and cil_rx is not None and abs(cil_ar - cil_rx) > 1.00:
            return True
    return False
```
- **Campos evaluados:** `akr.od/oi.esfera/cilindro`, `refraccion.od/oi.esfera/cilindro` (+ queratometría para addendum)
- **Umbrales:** |esf_AR − esf_Rx| > 1.00 O |cil_AR − cil_Rx| > 1.00
- **Dependencias:** se suprime si `ar_rx_espasmo_acomodativo` o `ar_rx_cambio_cristalino` están activas (catch-all)

### Texto actual (_texto)
Función dinámica:
```
# sin queratometría relevante:
"Se documenta discrepancia entre autorrefractometro y refraccion final."
# con curvatura corneal pronunciada:
"Se documenta discrepancia entre autorrefractometro y refraccion final con
queratometria de curvatura corneal pronunciada en {ojos}."
```

### Ejemplo de activación
```
paciente.edad = 30, clinica.uso_pantallas = None
akr.od.cilindro = -2.00, refraccion.od.cilindro = -0.75   # |diff| = 1.25 > 1.00
```

### Afinación clínica (2026-07-01)
Como catch-all, absorbe el matiz queratométrico sin cambiar su condición de activación. Correcto que sea el más laxo. Ver [afinacion_correlaciones_queratometria.md](afinacion_correlaciones_queratometria.md) §3.3.

### Clasificación
- [ATRIBUCION CAUSAL] — "discrepancia... con queratometria de curvatura corneal pronunciada" (solo con addendum)
- [OK] — en su forma base (solo describe discrepancia objetiva)

---

## Correlación 21: ar_detecta_astigmatismo_no_prescrito

### Condición (_cond)
```python
def _cond_ar_detecta_astigmatismo_no_prescrito(req: ImpresionClinicaRequest) -> bool:
    if req.refraccion is None or req.akr is None:
        return False
    for ojo in ("od", "oi"):
        akr_eye = getattr(req.akr, ojo)
        cil_ar = akr_eye.cilindro
        cil_rx = getattr(req.refraccion, ojo).cilindro
        if cil_ar is None or abs(cil_ar) < 0.75:
            continue
        if _has_keratometry(akr_eye) and not _keratometry_supports_astigmatism(akr_eye):
            continue
        if cil_rx is None or abs(cil_rx) < 0.50:
            return True
    return False
```
- **Campos evaluados:** `akr.od/oi.cilindro`, `refraccion.od/oi.cilindro`, y `akr.od/oi.k_cilindro` (queratometría)
- **Umbrales:** |cil_AR| ≥ 0.75 Y (si hay queratometría, |cil_corneal| ≥ 0.75 debe soportarlo) Y (cil_Rx None o |cil_Rx| < 0.50)
- **Dependencias:** ninguna

### Texto actual (_texto)
Función dinámica; por cada ojo que califica genera detalle con AR (y cilindro corneal si la queratometría lo soporta), y añade:
```
"El autorrefractometro detecta astigmatismo no incluido en la refraccion subjetiva
final en {ojos}. lo que puede corresponder a astigmatismo subumbral con tolerancia
clinica adecuada o variabilidad de la medicion automatizada."
```

### Ejemplo de activación
```
akr.od.cilindro = -1.00, refraccion.od.cilindro = None
akr.od.k_cilindro = -1.25   # queratometría soporta el astigmatismo → confianza alta
```

### Afinación clínica (2026-07-01)
Es la aplicación más sólida de la queratometría: el cilindro del AR sin cicloplejia es ruidoso; la queratometría (estructura estática) confirma si es real. Si hay dato de queratometría y **no** soporta el astigmatismo (|cil_corneal| < 0.75), la correlación **no** se dispara (reduce falsos positivos). Si no hay queratometría, se comporta como antes (fallback). Se restauró la cláusula "subumbral con tolerancia adecuada". Ver [afinacion_correlaciones_queratometria.md](afinacion_correlaciones_queratometria.md) §3.1.

### Clasificación
- [ATRIBUCION CAUSAL] — "puede corresponder a astigmatismo subumbral... o variabilidad de la medicion"
- [OK] — describe discrepancia objetiva, sin directiva de acción

---

## Correlación 22: astig_oblicuo

### Condición (_cond)
```python
def _cond_astig_oblicuo(req: ImpresionClinicaRequest) -> bool:
    refraccion = req.refraccion
    if refraccion is None:
        return False
    for ojo in (refraccion.od, refraccion.oi):
        cil = ojo.cilindro
        eje = ojo.eje
        if cil is None or eje is None:
            continue
        if abs(cil) > 2.00 and _es_eje_oblicuo(eje):
            return True
    return False
```
- **Campos evaluados:** `req.refraccion.od/oi.cilindro`, `.eje` (+ `akr` solo como confirmación en el texto)
- **Umbrales:** |cilindro Rx| > 2.00 Y eje oblicuo (20–70° o 110–160°)
- **Dependencias:** ninguna

### Texto actual (_texto)
Por cada ojo que califica: `"{label} ({cil} x {eje}): {descripcion}"`.
- |cil| ≤ 3.00 → "astigmatismo elevado con eje oblicuo"
- 3.00 < |cil| ≤ 4.00 → "astigmatismo alto con eje oblicuo"
- |cil| > 4.00 → "astigmatismo de magnitud muy alta con eje oblicuo"
Si la queratometría soporta el astigmatismo (|cil_corneal| ≥ 1.00) **y** el eje coincide (± 20°), se añade `" confirmado por queratometria"`.

### Ejemplo de activación
```
refraccion.od.cilindro = -2.50, refraccion.od.eje = 45
akr.od.k_cilindro = -3.00, akr.od.k_cilindro_eje = 45   → "...confirmado por queratometria"
```

### Afinación clínica (2026-07-01)
**Decisión de diseño (opción 1 del guide):** la correlación se **restringe** al cilindro de la Rx final prescrita (definición clínica de astigmatismo oblicuo prescrito, con riesgo de intolerancia/adaptación). La queratometría se usa **solo como confirmación**, nunca como vía de disparo independiente: un cilindro corneal oblicuo sin correlato en la Rx es competencia de `ar_detecta_astigmatismo_no_prescrito`, no de esta correlación (se eliminó la vía de disparo por queratometría aislada que existía en el borrador). Ver [afinacion_correlaciones_queratometria.md](afinacion_correlaciones_queratometria.md) §3.4.

### Clasificación
- [OK] — describe hallazgo refractivo objetivo con graduaciones descriptivas

---

## Correlación 23: amsler_alterado

### Condición (_cond)
```python
def _cond_amsler_alterado(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    texto = _normalize_text(clinica.grid_de_amsler)
    if not texto:
        return False
    if any(neg in texto for neg in _KEYWORDS_AMSLER_NEGATIVOS):
        return False
    return _contains_keyword(clinica.grid_de_amsler, _KEYWORDS_AMSLER_POSITIVOS, allow_negation_window=True)
```
- **Campos evaluados:** `req.clinica.grid_de_amsler`
- **Keywords positivas:** `"distorsion"`, `"metamorfopsia"`, `"escotoma central"`, `"escotoma"`, `"alterado"`, `"alteracion"`, `"ondulacion"`, `"lineas torcidas"`
- **Keywords negativas (suprimen):** `"sin distorsion"`, `"sin alteracion"`, `"normal"`, `"negativo"`
- **Negation window:** sí (para positivas)
- **Dependencias:** ninguna

### Texto actual (_texto)
```
"El test de Amsler revela alteracion compatible con patologia macular funcional que
amerita OCT macular."
```

### Ejemplo de activación
```
clinica.grid_de_amsler = "metamorfopsia central OD"
```

### Afinación clínica (2026-07-01)
Se restauró la cláusula "compatible con patologia macular funcional que amerita OCT macular". El texto es apropiadamente humilde (Amsler tiene sensibilidad limitada ~56%; un positivo amerita OCT). Fuente: [Amsler grid sensitivity – PMC8380298](https://pmc.ncbi.nlm.nih.gov/articles/PMC8380298/).

### Clasificación
- [ATRIBUCION CAUSAL] — "compatible con patologia macular funcional"
- [RECOMENDACION] — "amerita OCT macular"

---

## Correlación 24: anexos_patologicos

### Condición (_cond)
```python
def _cond_anexos_patologicos(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    return bool(_extract_normalized_findings(clinica.anexos_oculares, _KEYWORDS_ANEXOS, allow_negation_window=True))
```
- **Campos evaluados:** `req.clinica.anexos_oculares`
- **Keywords (mapa):** `"blefaritis"`, `"meibomitis"` → "disfuncion de glandulas de meibomio", `"chalazion"`, `"orzuelo"`, `"pterigion"`, `"pinguecula"`, `"conjuntivitis"`, `"hiperemia"` → "hiperemia conjuntival", `"queratitis"`, `"erosion"` → "erosion corneal", `"leucoma"` → "leucoma corneal", `"opacidad corneal"`, `"edema corneal"`, `"distriquiasis"`, `"triquiasis"`, `"ectropion"`, `"entropion"`, `"ptosis"` → "ptosis palpebral", `"dermatochalasis"`, `"lagoftalmos"`
- **Negation window:** sí
- **Dependencias:** ninguna

### Texto actual (_texto)
```
"En anexos oculares se documenta {hallazgos_unidos}."
```

### Ejemplo de activación
```
clinica.anexos_oculares = "blefaritis posterior bilateral, ptosis palpebral OD"
→ "En anexos oculares se documenta blefaritis y ptosis palpebral."
```

### Afinación clínica (2026-07-01)
Se agregaron `"meibomitis"` (→ disfunción de glándulas de Meibomio), `"dermatochalasis"` y `"lagoftalmos"`. Enumera hallazgos objetivos sin diagnóstico ni directiva.

### Clasificación
- [OK] — enumera hallazgos objetivos sin diagnóstico, recomendación ni atribución causal

---

## Correlación 25: insuficiencia_convergencia

### Condición (_cond)
```python
@_memoize_cond
def _cond_insuficiencia_convergencia(req: ImpresionClinicaRequest) -> bool:
    if req.clinica is None or req.paciente is None:
        return False
    if req.clinica.ppc_cm is None or req.clinica.ppc_cm <= 10:
        return False
    cover = _normalize_cover_text(req.clinica.cover_test)
    if "exoforia" not in cover:
        return False
    return _contains_keyword(req.paciente.motivo_consulta, _KEYWORDS_CERCANIA)
```
- **Campos evaluados:** `clinica.ppc_cm` (> 10 cm), `clinica.cover_test` (contiene "exoforia"), `paciente.motivo_consulta` (keywords de cercanía)
- **Keywords cercanía:** `"lectura"`, `"leer"`, `"estudiar"`, `"cerca"`, `"astenopia"`, `"fatiga"`, `"cefalea"`
- **Dependencias:** suprime `ppc_exoforia` y `cover_exoforia_sintomatica`

### Texto actual (_texto)
```
"La combinacion de punto proximo de convergencia alejado, exoforia y sintomatologia
de vision proxima es compatible con insuficiencia de convergencia, ameritando
evaluacion binocular completa para confirmar el diagnostico y plantear terapia
visual si procede."
```

### Ejemplo de activación
```
clinica.ppc_cm = 14, clinica.cover_test = "OD: Exo y Foria | OI: Orto"
paciente.motivo_consulta = "cefalea con lectura prolongada"
```

### Afinación clínica (2026-07-01)
El umbral PPC > 10 cm es conservador respecto al CITT (PPC de ruptura anormal > 6 cm) — por diseño evita falsos positivos exigiendo además exoforia + síntomas de cercanía. Correcto. Fuente: CITT (Convergence Insufficiency Treatment Trial).

### Clasificación
- [DIAGNOSTICO] — "insuficiencia de convergencia"
- [ATRIBUCION CAUSAL] — "compatible con insuficiencia de convergencia"
- [RECOMENDACION] — "ameritando evaluacion binocular completa... terapia visual si procede"

---

## Correlación 26: ppc_exoforia

### Condición (_cond)
```python
def _cond_ppc_exoforia(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    if _cond_insuficiencia_convergencia(req):
        return False
    ppc_alto = clinica.ppc_cm is not None and clinica.ppc_cm > 10
    cover = _normalize_cover_text(clinica.cover_test)
    return ppc_alto or ("exoforia" in cover)
```
- **Campos evaluados:** `clinica.ppc_cm` (> 10 cm), `clinica.cover_test` (contiene "exoforia")
- **Dependencias:** se suprime si `_cond_insuficiencia_convergencia` está activa

### Texto actual (_texto)
Función dinámica `_texto_ppc_exoforia`:
```
"El paciente presenta {partes}."
```
- Si PPC > 10: `"punto proximo de convergencia alejado ({ppc} cm)"`
- Si "exoforia" en cover: con "vp"/"cerca"/"proxima" → "exoforia en vision proxima"; con "vl"/"lejos" → "exoforia en vision lejana"; si no → "tendencia divergente en el cover test"

### Ejemplo de activación
```
clinica.ppc_cm = 13, clinica.cover_test = "OD: Exo y Foria | OI: Orto"
→ "El paciente presenta punto proximo de convergencia alejado (13 cm) y tendencia divergente en el cover test."
```

### Afinación clínica (2026-07-01)
**Bug corregido:** el texto tenía una rama "PPC > 15 → marcadamente alejado" **inalcanzable** (el schema limita `ppc_cm` a 1–15). Se eliminó la subdivisión; ahora todo PPC > 10 usa "alejado".

### Clasificación
- [OK] — describe hallazgos clínicos objetivos sin diagnóstico formal ni recomendación

---

## Correlación 27: cover_exoforia_sintomatica

### Condición (_cond)
```python
def _cond_cover_exoforia_sintomatica(req: ImpresionClinicaRequest) -> bool:
    if req.clinica is None or req.paciente is None:
        return False
    if _cond_insuficiencia_convergencia(req):
        return False
    cover = _normalize_cover_text(req.clinica.cover_test)
    return "exoforia" in cover and _has_binocular_symptoms(req)
```
- **Campos evaluados:** `clinica.cover_test` (contiene "exoforia"), `paciente.motivo_consulta` (keywords binoculares)
- **Keywords binoculares:** `"diplopia"`, `"vision doble"`, `"cefalea"`, `"dolor de cabeza"`, `"astenopia"`, `"fatiga visual"`, `"vista cansada"`, `"ardor con lectura"`, `"lagrimeo con lectura"`, `"perdida del renglon"`, `"salto de letras"`, `"vision borrosa intermitente"`
- **Dependencias:** se suprime si `_cond_insuficiencia_convergencia` está activa

### Texto actual (_texto)
```
"Se documenta exoforia con sintomatologia binocular asociada, compatible con
disfuncion binocular de tipo divergente que amerita evaluacion funcional."
```

### Ejemplo de activación
```
clinica.cover_test = "OD: Exo y Foria", paciente.motivo_consulta = "diplopia ocasional"
```

### Afinación clínica (2026-07-01)
Se **quitaron** `"mareo"` y `"vertigo"` de `_KEYWORDS_BINOCULAR` (síntomas inespecíficos, alto riesgo de falso positivo — afectaba también a `cover_endoforia_sintomatica`, que comparte el set). Se restauró la cláusula clínica completa.

### Clasificación
- [ATRIBUCION CAUSAL] — "compatible con disfuncion binocular de tipo divergente"
- [RECOMENDACION] — "amerita evaluacion funcional"

---

## Correlación 28: cover_endoforia_sintomatica

### Condición (_cond)
```python
def _cond_cover_endoforia_sintomatica(req: ImpresionClinicaRequest) -> bool:
    if req.clinica is None or req.paciente is None:
        return False
    cover = _normalize_cover_text(req.clinica.cover_test)
    return "endoforia" in cover and "endotropia" not in cover and _has_binocular_symptoms(req)
```
- **Campos evaluados:** `clinica.cover_test` (contiene "endoforia" pero NO "endotropia"), `paciente.motivo_consulta` (keywords binoculares)
- **Dependencias:** ninguna

### Texto actual (_texto)
```
"Se documenta endoforia con sintomatologia binocular asociada, compatible con
exceso de convergencia o disfuncion acomodativa que amerita evaluacion funcional."
```

### Ejemplo de activación
```
clinica.cover_test = "OD: Endo y Foria | OI: Orto", paciente.motivo_consulta = "cefalea frontal, astenopia"
```

### Afinación clínica (2026-07-01)
Misma limpieza de keywords binoculares que la Correlación 27 (`"mareo"`/`"vertigo"` removidos). Se restauró la cláusula clínica.

### Clasificación
- [ATRIBUCION CAUSAL] — "compatible con exceso de convergencia o disfuncion acomodativa"
- [RECOMENDACION] — "amerita evaluacion funcional"

---

## Correlación 29: desviacion_vertical

### Condición (_cond)
```python
def _cond_desviacion_vertical(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    cover = _normalize_cover_text(clinica.cover_test)
    return any(keyword in cover for keyword in _KEYWORDS_DESVIACION_VERTICAL)
```
- **Campos evaluados:** `req.clinica.cover_test`
- **Keywords:** `"hiperforia"`, `"hipoforia"`, `"hipertropia"`, `"hipotropia"`
- **Dependencias:** ninguna

### Texto actual (_texto)
Clasifica forias vs tropias:
- **Con tropia:** `"Se documenta {hallazgo}, que representa una desviacion manifiesta y amerita cuantificacion prismatica inmediata con evaluacion binocular completa."`
- **Solo foria:** `"Se documenta {hallazgo}, que puede generar sintomatologia binocular especifica y amerita cuantificacion prismatica para evaluar compensacion."`

### Ejemplo de activación
```
clinica.cover_test = "OD: Hiper y Foria | OI: Orto"
→ "Se documenta hiperforia, que puede generar sintomatologia binocular especifica y amerita cuantificacion prismatica para evaluar compensacion."
```

### Afinación clínica (2026-07-01)
Se restauraron las cláusulas de recomendación (cuantificación prismática) en ambas ramas. La distinción foria (latente) vs tropia (manifiesta) con urgencia diferenciada es correcta.

### Clasificación
- [RECOMENDACION] — "amerita cuantificacion prismatica inmediata" / "amerita cuantificacion prismatica para evaluar compensacion"

---

## Correlación 30: cvs_sospecha

### Condición (_cond)
```python
def _cond_cvs_sospecha(req: ImpresionClinicaRequest) -> bool:
    if req.clinica is None or req.paciente is None:
        return False
    if req.clinica.uso_pantallas not in ("btw2_6", "gt6"):
        return False
    return _contains_keyword(req.paciente.motivo_consulta, _KEYWORDS_CVS)
```
- **Campos evaluados:** `clinica.uso_pantallas` ("btw2_6" o "gt6"), `paciente.motivo_consulta`
- **Keywords CVS:** `"ardor ocular"`, `"sequedad ocular"`, `"vision borrosa intermitente"`, `"vision borrosa"`, `"dolor ocular"`, `"ardor"`, `"sequedad"`, `"cefalea"`, `"picazon"`, `"prurito"`, `"lagrimeo"`
- **Dependencias:** ninguna

### Texto actual (_texto)
```
"El perfil de uso de pantallas se correlaciona con la sintomatologia visual
referida, compatible con sindrome visual informatico, ameritando recomendaciones
ergonomicas y eventual correccion optica para vision intermedia."
```

### Ejemplo de activación
```
clinica.uso_pantallas = "gt6", paciente.motivo_consulta = "ardor ocular y vision borrosa al terminar de trabajar"
```

### Afinación clínica (2026-07-01)
Se ampliaron las keywords a síntomas frecuentes de CVS/DES (computer vision syndrome / digital eye strain): `"cefalea"`, `"vision borrosa"`, `"picazon"`, `"prurito"`, `"lagrimeo"`. Se restauró la cláusula clínica completa. Fuente: AOA – Computer Vision Syndrome / Digital Eye Strain.

### Clasificación
- [DIAGNOSTICO] — "sindrome visual informatico"
- [ATRIBUCION CAUSAL] — "compatible con sindrome visual informatico"
- [RECOMENDACION] — "ameritando recomendaciones ergonomicas y eventual correccion optica para vision intermedia"

---

## Correlación 31: endotropia_lente

### Condición (_cond)
```python
def _cond_endotropia_lente(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    cover = _normalize_cover_text(clinica.cover_test)
    return "endotropia" in cover and req.tipo_lente is not None
```
- **Campos evaluados:** `req.clinica.cover_test` (contiene "endotropia"), `req.tipo_lente` (no nulo)
- **Dependencias:** ninguna

### Texto actual (_texto)
```
"Se documenta endotropia en el cover test, ameritando evaluacion de la respuesta a
la correccion optica prescrita, con cover test bajo correccion para clasificar el
tipo de desviacion."
```

### Ejemplo de activación
```
clinica.cover_test = "OD: Endo y Tropia", tipo_lente = "monofocal"
```

### Afinación clínica (2026-07-01)
Se restauró la cláusula (evaluación bajo corrección para clasificar el tipo de desviación — relevante para esotropía acomodativa).

### Clasificación
- [RECOMENDACION] — "amerita evaluacion de la respuesta a la correccion optica prescrita"

---

## Correlación 32: exotropia_lente

### Condición (_cond)
```python
def _cond_exotropia_lente(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    cover = _normalize_cover_text(clinica.cover_test)
    return "exotropia" in cover and req.tipo_lente is not None
```
- **Campos evaluados:** `req.clinica.cover_test` (contiene "exotropia"), `req.tipo_lente` (no nulo)
- **Dependencias:** ninguna

### Texto actual (_texto)
```
"Se documenta exotropia en el cover test, ameritando evaluacion binocular completa
para determinar frecuencia y magnitud de la desviacion, asi como la respuesta a la
correccion optica prescrita."
```

### Ejemplo de activación
```
clinica.cover_test = "OI: Exo y Tropia", tipo_lente = "progresivo"
```

### Afinación clínica (2026-07-01)
Se restauró la cláusula (evaluación binocular completa + respuesta a la corrección).

### Clasificación
- [RECOMENDACION] — "amerita evaluacion binocular completa"

---

## Correlación 33: but_pantallas

### Condición (_cond)
```python
def _cond_but_pantallas(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    but = clinica.ojo_seco_but_seg
    return but is not None and 5 <= but <= 9 and clinica.uso_pantallas in ("btw2_6", "gt6")
```
- **Campos evaluados:** `req.clinica.ojo_seco_but_seg` (5–9 s), `req.clinica.uso_pantallas` ("btw2_6" o "gt6")
- **Dependencias:** rango exclusivo respecto a `but_critico` (< 5) y `but_limitrofe` (5–9 sin pantallas)

### Texto actual (_texto)
```
"El tiempo de ruptura lagrimal de {but} segundos es reducido en el contexto del uso
de pantallas, lo que indica inestabilidad de la pelicula lagrimal."
```

### Ejemplo de activación
```
clinica.ojo_seco_but_seg = 7, clinica.uso_pantallas = "btw2_6"
```

### Afinación clínica (2026-07-01)
BUT 5–9 s = zona límite/subóptima según TFOS DEWS II (< 10 s anormal, < 5 s crítico). La partición con `but_limitrofe` según `uso_pantallas` es clínicamente sensata. Sin cambios.

### Clasificación
- [OK] — describe hallazgo objetivo con contexto; "indica inestabilidad de la pelicula lagrimal" es descriptivo

---

## Correlación 34: but_limitrofe

### Condición (_cond)
```python
def _cond_but_limitrofe(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    but = clinica.ojo_seco_but_seg
    return but is not None and 5 <= but <= 9 and clinica.uso_pantallas in (None, "lt2")
```
- **Campos evaluados:** `req.clinica.ojo_seco_but_seg` (5–9 s), `req.clinica.uso_pantallas` (None o "lt2")
- **Dependencias:** rango exclusivo respecto a `but_critico` y `but_pantallas`

### Texto actual (_texto)
```
"El tiempo de ruptura lagrimal de {but}s se encuentra en rango suboptimo,
sugiriendo inestabilidad leve de la pelicula lagrimal."
```

### Ejemplo de activación
```
clinica.ojo_seco_but_seg = 8, clinica.uso_pantallas = None
```

### Afinación clínica (2026-07-01)
Se restauró la cláusula "sugiriendo inestabilidad leve de la pelicula lagrimal". Clasificación clínica correcta (DEWS).

### Clasificación
- [ATRIBUCION CAUSAL] — "sugiriendo inestabilidad leve de la pelicula lagrimal"

---

## Correlación 35: presbicia_multifocal

### Condición (_cond)
```python
def _cond_presbicia_multifocal(req: ImpresionClinicaRequest) -> bool:
    paciente = req.paciente
    refraccion = req.refraccion
    if paciente is None or refraccion is None:
        return False
    es_multifocal = _es_lente_multifocal(req)
    edad = paciente.edad
    hay_edad = edad is not None and edad >= 40
    hay_add = refraccion.od.add is not None or refraccion.oi.add is not None
    return (es_multifocal and (hay_edad or hay_add)) or (hay_edad and hay_add)
```
- **Campos evaluados:** `req.tipo_lente` (tokens "bifocal"/"progresivo"/"multifocal"), `req.paciente.edad` (≥ 40), `req.refraccion.od/oi.add`
- **Lógica:** (multifocal Y (edad≥40 O hay_add)) O (edad≥40 Y hay_add)
- **Dependencias:** ninguna

### Texto actual (_texto)
**Rama con edad:** `"El paciente de {edad} anos presenta reduccion fisiologica de la amplitud acomodativa propia de la edad, lo que justifica la adicion prescrita{sufijo_lente}."`
**Rama sin edad:** `"Se documenta reduccion fisiologica de la amplitud acomodativa, lo que justifica la adicion prescrita{sufijo_lente}."`
`{sufijo_lente}` = `" y el lente multifocal indicado"` si multifocal, si no `""`.

### Ejemplo de activación
```
paciente.edad = 52, refraccion.od.add = +2.00, tipo_lente = "progresivo"
→ "El paciente de 52 anos presenta reduccion fisiologica de la amplitud acomodativa propia de la edad, lo que justifica la adicion prescrita y el lente multifocal indicado."
```

### Afinación clínica (2026-07-01)
Umbral edad ≥ 40 coherente con el inicio de presbicia (40–45 años). El texto contextualiza un fenómeno fisiológico esperado (no patológico). Sin cambios.

### Clasificación
- [OK] — contextualiza hallazgo fisiológico esperado por edad, sin diagnosticar ni recomendar acción adicional

---

## Correlación 36: adulto_mayor_screening

### Condición (_cond)
```python
def _cond_adulto_mayor_screening(req: ImpresionClinicaRequest) -> bool:
    if req.paciente is None or req.refraccion is None:
        return False
    edad = req.paciente.edad
    if edad is None or edad < 60:
        return False
    if not (_av_es_limitada(req.refraccion.od.av_cc) or _av_es_limitada(req.refraccion.oi.av_cc)):
        return False
    return not any(
        cond(req) for cond in (
            _cond_opacidad_cristaliniana,
            _cond_fondo_glaucomatoso,
            _cond_fondo_macular_dmae,
            _cond_fondo_macular_otros,
            _cond_fondo_vascular_diabetico,
            _cond_fondo_hipertensivo,
            _cond_miopia_magna,
            _cond_papila_patologica,
            _req_has_corneal_irregularity,
        )
    )
```
- **Campos evaluados:** `req.paciente.edad` (≥ 60), `req.refraccion.od/oi.av_cc` (AV limitada), ausencia de 9 causas específicas (incluida, desde 2026-07-01, la irregularidad corneal queratométrica)
- **Dependencias:** se suprime si cualquiera de las 9 condiciones listadas está activa (catch-all)

### Texto actual (_texto)
```
"En paciente de {edad} anos con reduccion de agudeza visual sin causa identificada
en el examen actual, se recomienda descarte activo de catarata, glaucoma y
maculopatia asociada a la edad mediante exploracion dirigida."
```

### Ejemplo de activación
```
paciente.edad = 68, refraccion.od.av_cc = "20/50"
# sin catarata/excavación/drusas/MER/microaneurismas/tortuosidad/miopía magna/palidez papilar/irregularidad corneal
```

### Afinación clínica (2026-07-01)
Se agregó `_req_has_corneal_irregularity` a la lista de supresores: si la queratometría ya explica la reducción de AV (irregularidad corneal), no hace falta el mensaje genérico de screening. Se restauró la cláusula de recomendación completa.

### Clasificación
- [RECOMENDACION] — "se recomienda descarte activo de catarata, glaucoma y maculopatia"

---

## RESUMEN FINAL

### Cambios de esta revisión (2026-07-01)

**Queratometría integrada (9 correlaciones, como apoyo/diferencial, nunca diagnóstico de ectasia):**
`ar_detecta_astigmatismo_no_prescrito` (confirmación de astigmatismo real), `ar_rx_cambio_cristalino` (exclusión si hay irregularidad corneal), `ar_rx_variabilidad_inespecifica` (addendum), `astig_oblicuo` (solo confirmación), `miopia_magna` (componente corneal vs axial), `hipermetropia_alta` (K plana/pronunciada), `anisometropia` (asimetría corneal addendum), `av_cc_limitada` (irregularidad explica AV reducida), `adulto_mayor_screening` (irregularidad como supresor).

**Bugs corregidos:** DPAR en `glaucoma_asimetrico` sin ventana de negación (falso positivo con "sin DPAR"); rama inalcanzable PPC > 15 en `ppc_exoforia`; `hemorragia en llama` mal clasificada como diabética.

**Keywords ampliadas:** fondo periférico (empalizada, agujeros atrófico/operculado), glaucomatoso (c/d 0.5), DMAE (mev), macular otros (crsc), hipertensivo (hemorragia en llama), opacidad (esclerosis nuclear), campos (restriccion, campo reducido), anexos (meibomitis, dermatochalasis, lagoftalmos), CVS (cefalea, visión borrosa, picazón, prurito, lagrimeo). **Keywords removidas:** `mareo`/`vertigo` de sintomatología binocular (inespecíficos).

**Textos:** se restauraron las cláusulas de recomendación/atribución que una optimización previa había recortado (el system prompt prohíbe al LLM añadir recomendaciones no presentes en el texto de la correlación, por lo que el recorte silenciaba referencias/seguimientos en el párrafo final).

**Supresión ajustada:** `fondo_vascular_diabetico` ya no se suprime contra `fondo_hipertensivo` (coexistencia DM+HTA); `adulto_mayor_screening` suma la irregularidad corneal como supresor.

### Tabla resumen individual

| # | Nombre | DIAGNOSTICO | RECOMENDACION | ATRIBUCION CAUSAL | OK | Usa queratometría |
|---|---|:---:|:---:|:---:|:---:|:---:|
| 1 | fondo_periferico_riesgo | — | ✓ | — | — | — |
| 2 | papila_patologica | — | ✓ | ✓ | — | — |
| 3 | glaucoma_asimetrico | ✓ | ✓ | ✓ | — | — |
| 4 | pupilas_alteradas | — | ✓ | ✓ | — | — |
| 5 | fondo_glaucomatoso | — | ✓ | ✓ | — | — |
| 6 | fondo_macular_dmae | — | ✓ | ✓ | — | — |
| 7 | fondo_macular_otros | — | ✓ | — | — | — |
| 8 | fondo_hipertensivo | — | ✓ | ✓ | — | — |
| 9 | fondo_vascular_diabetico | — | ✓ | ✓ | — | — |
| 10 | motilidad_alterada | — | ✓ | — | — | — |
| 11 | campos_visuales_alterados | — | ✓ | — | — | — |
| 12 | opacidad_cristaliniana | — | ✓ | — | — | — |
| 13 | but_critico | ✓ | ✓ | ✓ | — | — |
| 14 | miopia_magna | — | ✓* | ✓ | — | ✓ |
| 15 | hipermetropia_alta | — | ✓ | — | — | ✓ |
| 16 | anisometropia | — | — | — | ✓ | ✓ |
| 17 | av_cc_limitada | — | — | ✓* | ✓ | ✓ |
| 18 | ar_rx_espasmo_acomodativo | ✓ | ✓ | ✓ | — | — |
| 19 | ar_rx_cambio_cristalino | — | ✓ | ✓ | — | ✓ (exclusión) |
| 20 | ar_rx_variabilidad_inespecifica | — | — | ✓ | ✓ | ✓ |
| 21 | ar_detecta_astigmatismo_no_prescrito | — | — | ✓ | ✓ | ✓ |
| 22 | astig_oblicuo | — | — | — | ✓ | ✓ (confirmación) |
| 23 | amsler_alterado | — | ✓ | ✓ | — | — |
| 24 | anexos_patologicos | — | — | — | ✓ | — |
| 25 | insuficiencia_convergencia | ✓ | ✓ | ✓ | — | — |
| 26 | ppc_exoforia | — | — | — | ✓ | — |
| 27 | cover_exoforia_sintomatica | — | ✓ | ✓ | — | — |
| 28 | cover_endoforia_sintomatica | — | ✓ | ✓ | — | — |
| 29 | desviacion_vertical | — | ✓ | — | — | — |
| 30 | cvs_sospecha | ✓ | ✓ | ✓ | — | — |
| 31 | endotropia_lente | — | ✓ | — | — | — |
| 32 | exotropia_lente | — | ✓ | — | — | — |
| 33 | but_pantallas | — | — | — | ✓ | — |
| 34 | but_limitrofe | — | — | ✓ | — | — |
| 35 | presbicia_multifocal | — | — | — | ✓ | — |
| 36 | adulto_mayor_screening | — | ✓ | — | — | ✓ (supresor) |

*`miopia_magna` incluye [RECOMENDACION] solo cuando aparece el addendum queratométrico. `av_cc_limitada` incluye [ATRIBUCION CAUSAL] solo con el addendum corneal.

### Correlaciones con prefijo "Hallazgo urgente:"

1. **fondo_periferico_riesgo** — siempre (inicio del texto)
2. **glaucoma_asimetrico** — siempre (inicio del texto fijo)
3. **papila_patologica** — solo en la rama emergencia (papiledema/edema/bordes borrosos)
4. **pupilas_alteradas** — solo en el sufijo adicional cuando hay DPAR entre los hallazgos

### Fundamentación cruzada

- Integración de queratometría y umbrales: [afinacion_correlaciones_queratometria.md](afinacion_correlaciones_queratometria.md)
- Pipeline completo y schema de entrada (incluyendo campos de queratometría): [PIPELINE_LLM.md](PIPELINE_LLM.md)
