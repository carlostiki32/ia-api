# Auditoría Completa de Correlaciones
**Archivo fuente:** `app/correlaciones.py`  
**Fecha de auditoría:** 2026-04-27  
**Total de correlaciones registradas en CORRELACIONES:** 36

---

## Correlación 1: fondo_periferico_riesgo

### Condición (_cond)
```python
@_memoize_cond
def _cond_fondo_periferico_riesgo(req: ImpresionClinicaRequest) -> bool:
    return _fondo_contains(req, _KEYWORDS_FONDO_PERIFERICO)
```
- **Campos evaluados:** `req.clinica.fondo_de_ojo`
- **Keywords:** `"desgarro"`, `"agujero retiniano"`, `"lattice"`, `"degeneracion reticular"`, `"blanco con presion"`, `"desprendimiento"`, `"schisis"`, `"retinosquisis"`
- **Negation window:** sí (`allow_negation_window=True`)
- **Dependencias:** ninguna (es la más prioritaria; otras correlaciones de fondo se suprimen si esta está activa)

### Texto actual (_texto)
Función dinámica `_texto_fondo_periferico_riesgo`:

```
"Hallazgo urgente: en la retina periferica se documenta {hallazgo}, que amerita
valoracion retinologica urgente y posible tratamiento profilactico."
```

Donde `{hallazgo}` es la lista normalizada de keywords encontradas (mapeadas via `_KEYWORDS_FONDO_PERIFERICO_MAP`):
- `desgarro` → "desgarro retiniano"
- `agujero retiniano` → "agujero retiniano"
- `lattice` → "degeneracion lattice"
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
"Los hallazgos del nervio optico documentados son compatibles con edema de
papila, lo que amerita evaluacion neurooftalmologica urgente para descarte
de hipertension intracraneal."
```

**Rama estándar** (cualquier otro hallazgo de la lista):
```
"Los hallazgos del nervio optico documentados son compatibles con compromiso del
mismo no glaucomatoso, ameritando valoracion neurooftalmologica para
caracterizacion etiologica."
```

### Ejemplo de activación
```
clinica.fondo_de_ojo = "palidez papilar temporal OD"
```
→ Rama estándar.

```
clinica.fondo_de_ojo = "papiledema bilateral"
```
→ Rama emergencia.

### Clasificación
- [ATRIBUCION CAUSAL] — "compatibles con edema de papila" / "compatibles con compromiso del mismo no glaucomatoso"
- [RECOMENDACION] — "amerita evaluacion neurooftalmologica urgente" / "ameritando valoracion neurooftalmologica"

---

## Correlación 3: glaucoma_asimetrico

### Condición (_cond)
```python
@_memoize_cond
def _cond_glaucoma_asimetrico(req: ImpresionClinicaRequest) -> bool:
    if req.clinica is None:
        return False
    txt_pupilas = _normalize_text(req.clinica.reflejos_pupilares)
    hay_dpar = any(k in txt_pupilas for k in ("dpar", "marcus gunn"))
    if not hay_dpar:
        return False
    return _fondo_contains(req, _KEYWORDS_FONDO_GLAUCOMATOSO)
```
- **Campos evaluados:** `req.clinica.reflejos_pupilares` (busca "dpar" o "marcus gunn") + `req.clinica.fondo_de_ojo` (keywords glaucomatosas)
- **Keywords fondo glaucomatoso:** `"c/d 0.6"`, `"c/d 0.7"`, `"c/d 0.8"`, `"c/d 0.9"`, `"cup/disc 0.6"–"0.9"`, `"excavacion"`, `"papila asimetrica"`, `"asimetria c/d"`, `"muesca"`, `"notch"`, `"hemorragia peripapilar"`, `"rima neural adelgazada"`
- **Negation window:** sí (para fondo)
- **Dependencias:** suprime `fondo_glaucomatoso` y `pupilas_alteradas` (si DPAR está en pupils + fondo glaucomatoso, éstas no se activan)

### Texto actual (_texto)
Texto fijo:
```
"Hallazgo urgente: los hallazgos papilares glaucomatosos asociados a defecto pupilar
aferente relativo son compatibles con neuropatia optica glaucomatosa avanzada y
asimetrica, con compromiso funcional confirmado, ameritando valoracion oftalmologica
priorizada."
```

### Ejemplo de activación
```
clinica.reflejos_pupilares = "DPAR positivo OI"
clinica.fondo_de_ojo = "excavacion aumentada c/d 0.8 OI, c/d 0.5 OD"
```

### Clasificación
- [DIAGNOSTICO] — "neuropatia optica glaucomatosa avanzada y asimetrica"
- [ATRIBUCION CAUSAL] — "compatibles con neuropatia optica glaucomatosa"
- [RECOMENDACION] — "ameritando valoracion oftalmologica priorizada"

---

## Correlación 4: pupilas_alteradas

### Condición (_cond)
```python
def _cond_pupilas_alteradas(req: ImpresionClinicaRequest) -> bool:
    if _cond_glaucoma_asimetrico(req):
        return False
    clinica = req.clinica
    if clinica is None:
        return False
    hallazgos = _extract_normalized_findings(
        clinica.reflejos_pupilares,
        _KEYWORDS_PUPILAS,
        allow_negation_window=True,
    )
    return bool(hallazgos)
```
- **Campos evaluados:** `req.clinica.reflejos_pupilares`
- **Keywords:** `"anisocoria"`, `"midriasis"`, `"miosis"`, `"dpar"`, `"marcus gunn"`, `"no reactivo"`, `"no reactiva"`, `"irregular"`, `"discoria"`, `"ausente"`
- **Negation window:** sí
- **Dependencias:** se suprime si `_cond_glaucoma_asimetrico` está activa

### Texto actual (_texto)
Función dinámica `_texto_pupilas_alteradas`:

**Texto base (siempre presente):**
```
"En la exploracion pupilar se documenta {hallazgos_unidos},
lo que amerita valoracion neurooftalmologica."
```

**Sufijo adicional (solo si "defecto pupilar aferente relativo" está en los hallazgos):**
```
" Hallazgo urgente: la presencia de defecto pupilar aferente relativo es
indicativa de patologia de via optica y requiere evaluacion urgente."
```

Los hallazgos se normalizan con el mapa `_KEYWORDS_PUPILAS`:
- `dpar` / `marcus gunn` → "defecto pupilar aferente relativo"
- `no reactivo` / `no reactiva` → "pupila no reactiva"
- `irregular` → "pupila irregular"
- `ausente` → "respuesta pupilar ausente"
- demás keywords se usan tal cual

### Ejemplo de activación
```
clinica.reflejos_pupilares = "anisocoria 1mm, DPAR OD"
```
→ Texto base + sufijo urgente.

```
clinica.reflejos_pupilares = "midriasis OI"
```
→ Solo texto base.

### Clasificación
- [RECOMENDACION] — "amerita valoracion neurooftalmologica" / "requiere evaluacion urgente"
- [ATRIBUCION CAUSAL] — "indicativa de patologia de via optica"

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
- **Keywords:** mismas que en `glaucoma_asimetrico` (ver arriba)
- **Negation window:** sí
- **Dependencias:** se suprime si `_cond_glaucoma_asimetrico` está activa

### Texto actual (_texto)
Texto fijo:
```
"Los hallazgos papilares documentados sugieren neuropatia optica glaucomatosa,
ameritando valoracion oftalmologica con tonometria, paquimetria y perimetria
para estadificacion."
```

### Ejemplo de activación
```
clinica.fondo_de_ojo = "excavacion c/d 0.7, muesca inferior OD"
clinica.reflejos_pupilares = "isocóricos normoreactivos"  # sin DPAR
```

### Clasificación
- [DIAGNOSTICO] — "neuropatia optica glaucomatosa"
- [ATRIBUCION CAUSAL] — "sugieren neuropatia optica glaucomatosa"
- [RECOMENDACION] — "ameritando valoracion oftalmologica con tonometria, paquimetria y perimetria"

---

## Correlación 6: fondo_macular_dmae

### Condición (_cond)
```python
@_memoize_cond
def _cond_fondo_macular_dmae(req: ImpresionClinicaRequest) -> bool:
    return _fondo_contains(req, _KEYWORDS_FONDO_DMAE)
```
- **Campos evaluados:** `req.clinica.fondo_de_ojo`
- **Keywords:** `"drusas"`, `"drusen"`, `"alteracion pigmentaria"`, `"alteracion del epr"`, `"atrofia geografica"`, `"membrana neovascular"`, `"mnvc"`, `"cnv"`, `"epiteliopatia"`, `"dmae"`, `"degeneracion macular"`
- **Negation window:** sí
- **Dependencias:** su activación suprime `fondo_vascular_diabetico`

### Texto actual (_texto)
Texto fijo:
```
"Los hallazgos maculares documentados son compatibles con degeneracion macular
asociada a la edad, ameritando OCT macular para caracterizacion y monitorizacion."
```

### Ejemplo de activación
```
clinica.fondo_de_ojo = "drusas duras y blandas maculares bilaterales"
```

### Clasificación
- [DIAGNOSTICO] — "degeneracion macular asociada a la edad"
- [ATRIBUCION CAUSAL] — "compatibles con degeneracion macular asociada a la edad"
- [RECOMENDACION] — "ameritando OCT macular"

---

## Correlación 7: fondo_macular_otros

### Condición (_cond)
```python
@_memoize_cond
def _cond_fondo_macular_otros(req: ImpresionClinicaRequest) -> bool:
    return _fondo_contains(req, _KEYWORDS_FONDO_MACULAR_OTROS)
```
- **Campos evaluados:** `req.clinica.fondo_de_ojo`
- **Keywords:** `"edema macular"`, `"membrana epirretiniana"`, `"mer"`, `"pucker"`, `"agujero macular"`, `"quiste macular"`, `"coroidopatia serosa"`
- **Negation window:** sí
- **Dependencias:** su activación suprime `fondo_vascular_diabetico`

### Texto actual (_texto)
Texto fijo:
```
"En la region macular se documenta alteracion que amerita OCT y valoracion
retinologica."
```

### Ejemplo de activación
```
clinica.fondo_de_ojo = "membrana epirretiniana OD"
```

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
- **Keywords:** `"tortuosidad vascular"`, `"tortuosidad"`, `"cruces arteriovenosos"`, `"cruces av"`, `"signo de gunn"`, `"estrechamiento arterial"`, `"hilos de cobre"`, `"hilos de plata"`, `"algodonoso"`, `"cotton wool"`, `"salus"`, `"ingurgitacion venosa"`
- **Negation window:** sí
- **Dependencias:** su activación suprime `fondo_vascular_diabetico`

### Texto actual (_texto)
Texto fijo:
```
"Los hallazgos vasculares en fondo de ojo son compatibles con retinopatia
hipertensiva, ameritando correlacion con cifras tensionales sistemicas."
```

### Ejemplo de activación
```
clinica.fondo_de_ojo = "cruces arteriovenosos grado II, hilos de cobre"
```

### Clasificación
- [DIAGNOSTICO] — "retinopatia hipertensiva"
- [ATRIBUCION CAUSAL] — "compatibles con retinopatia hipertensiva"
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
        _cond_fondo_hipertensivo(req),
    )):
        return False
    return _fondo_contains(req, _KEYWORDS_VASCULARES_DIABETICOS)
```
- **Campos evaluados:** `req.clinica.fondo_de_ojo`
- **Keywords:** `"microaneurisma"`, `"microaneurismas"`, `"exudado"`, `"hemorragia retiniana"`, `"hemorragia en llama"`, `"hemorragia intraretin"`, `"hemorragia en mancha"`, `"hemorragia puntiforme"`, `"neovas"`, `"rubeosis"`
- **Negation window:** sí
- **Dependencias:** se suprime si cualquiera de las 5 correlaciones de fondo anteriores está activa (fondo_periferico_riesgo, fondo_glaucomatoso, fondo_macular_dmae, fondo_macular_otros, fondo_hipertensivo)

### Texto actual (_texto)
Texto fijo:
```
"Los hallazgos en fondo de ojo son compatibles con retinopatia de origen
metabolico o vascular, ameritando correlacion sistemica."
```

### Ejemplo de activación
```
clinica.fondo_de_ojo = "microaneurismas periféricos, exudados duros OD"
# (sin lattice, sin excavación aumentada, sin drusen, sin MER, sin tortuosidad)
```

### Clasificación
- [DIAGNOSTICO] — "retinopatia de origen metabolico o vascular"
- [ATRIBUCION CAUSAL] — "compatibles con retinopatia de origen metabolico o vascular"
- [RECOMENDACION] — "ameritando correlacion sistemica"

---

## Correlación 10: motilidad_alterada

### Condición (_cond)
```python
def _cond_motilidad_alterada(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    return _contains_keyword(
        clinica.motilidad_ocular,
        _KEYWORDS_MOTILIDAD,
        allow_negation_window=True,
    )
```
- **Campos evaluados:** `req.clinica.motilidad_ocular`
- **Keywords:** `"limitacion"`, `"paresia"`, `"paralisis"`, `"restriccion"`, `"nistagmo"`, `"nistagmus"`, `"dolor con movimiento"`, `"dolor al movimiento"`, `"sobreacti"`, `"hiperfuncion"`, `"hipoaccion"`, `"hipofuncion"`, `"sincinesia"`, `"duane"`, `"oftalmoplejia"`, `"oftalmoplegia"`
- **Negation window:** sí
- **Dependencias:** ninguna

### Texto actual (_texto)
Texto fijo:
```
"Se documenta alteracion de la motilidad ocular, lo que amerita estudio de vias
motoras y posible interconsulta neurooftalmologica."
```

### Ejemplo de activación
```
clinica.motilidad_ocular = "limitación de aducción OD"
```

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
    return _contains_keyword(
        clinica.confrontacion_campos_visuales,
        _KEYWORDS_CAMPOS_POSITIVOS,
        allow_negation_window=True,
    )
```
- **Campos evaluados:** `req.clinica.confrontacion_campos_visuales`
- **Keywords positivas:** `"escotoma"`, `"defecto"`, `"hemianopsia"`, `"cuadrantopsia"`, `"constriccion"`, `"alteracion"`, `"no responde"`
- **Keywords negativas (suprimen):** `"sin defect"`, `"sin alteracion"`, `"normal"`, `"integro"`
- **Negation window:** sí (para keywords positivas)
- **Dependencias:** ninguna

### Texto actual (_texto)
Texto fijo:
```
"La confrontacion de campos visuales revela alteracion que amerita perimetria
automatizada para caracterizacion del defecto."
```

### Ejemplo de activación
```
clinica.confrontacion_campos_visuales = "escotoma paracentral OD"
```

### Clasificación
- [RECOMENDACION] — "amerita perimetria automatizada"

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
- **Keywords:** `"catarata"`, `"cataratas"`, `"opacidad cristaliniana"`, `"opacidad del cristalino"`, `"facoesclerosis"`, `"pseudofaquia"`, `"pseudofaco"`, `"pseudofaquico"`, `"afaquia"`, `"afaquico"`
- **Negation window:** sí
- **Dependencias:** su activación suprime `adulto_mayor_screening`

### Texto actual (_texto)
Texto fijo:
```
"Se documenta alteracion del cristalino, ameritando evaluacion biomicroscopica
para caracterizacion y estadificacion de la opacidad."
```

### Ejemplo de activación
```
clinica.anexos_oculares = "catarata nuclear incipiente OD"
```

### Clasificación
- [RECOMENDACION] — "ameritando evaluacion biomicroscopica"

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
- **Dependencias:** ninguna; tiene prioridad implícita sobre `but_pantallas` y `but_limitrofe` por rango exclusivo (< 5 no puede ser 5-9)

### Texto actual (_texto)
Función dinámica:
```
"El tiempo de ruptura lagrimal de {but}s es patologicamente bajo, compatible
con ojo seco clinico que amerita evaluacion."
```
Donde `{but}` es el valor numérico de `clinica.ojo_seco_but_seg`.

### Ejemplo de activación
```
clinica.ojo_seco_but_seg = 3
```
→ `"El tiempo de ruptura lagrimal de 3s es patologicamente bajo, compatible con ojo seco clinico que amerita evaluacion."`

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
- **Campos evaluados:** `req.refraccion.od.esfera`, `req.refraccion.od.cilindro`, `req.refraccion.oi.esfera`, `req.refraccion.oi.cilindro`
- **Umbral:** EE ≤ -6.00 D en cualquier ojo
- **Dependencias:** su activación suprime `adulto_mayor_screening`

### Texto actual (_texto)
Función dinámica `_texto_miopia_magna`:

**Rama "muy alta"** (si algún EE ≤ -8.00):
```
"Se documenta miopia de magnitud muy alta en {ojos_con_EE},
lo que conlleva riesgo significativamente elevado de patologia macular degenerativa,
desprendimiento de retina y glaucoma."
```

**Rama "alta"** (todos los EE entre -6.00 y -8.00):
```
"Se documenta miopia de magnitud alta en {ojos_con_EE},
lo que conlleva mayor riesgo de patologia retiniana periferica y macular."
```

`{ojos_con_EE}` tiene formato: `"OD (EE -7.25D)"` o `"OD (EE -7.25D) y OI (EE -6.50D)"`.

### Ejemplo de activación
```
refraccion.od.esfera = -7.00, refraccion.od.cilindro = -0.50  # EE = -7.25
```
→ Rama "alta": `"Se documenta miopia de magnitud alta en OD (EE -7.25D), lo que conlleva mayor riesgo de patologia retiniana periferica y macular."`

### Clasificación
- [ATRIBUCION CAUSAL] — "lo que conlleva riesgo/mayor riesgo de..."

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
Función dinámica `_texto_hipermetropia_alta` con dos ramas según edad:

**Rama edad ≥ 40 o edad desconocida:**
```
"Se documenta hipermetropia alta en {ojos_con_EE}, lo que amerita evaluacion de la
profundidad de camara anterior ante el riesgo asociado de angulo camerular estrecho."
```

**Rama edad < 40:**
```
"Se documenta hipermetropia alta en {ojos_con_EE}, lo que genera demanda acomodativa
significativa y amerita vigilancia de esoforia o esotropia acomodativa."
```

### Ejemplo de activación
```
refraccion.oi.esfera = +5.50, refraccion.oi.cilindro = None  # EE = +5.50
paciente.edad = 35
```
→ Rama joven.

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
- **Campos evaluados:** `req.refraccion.od/oi.esfera`, `.cilindro`
- **Umbral:** |EE_OD − EE_OI| > 1.00 D
- **Dependencias:** ninguna

### Texto actual (_texto)
Función dinámica `_texto_anisometropia` con ramas por magnitud y signo:

**Ramas por diferencia:**
- diff < 2.00 → severidad = "leve", cierre = "con posible impacto en la fusion binocular"
- 2.00 ≤ diff ≤ 3.00 → severidad = "moderada", cierre = "con posible impacto en la fusion binocular"
- diff > 3.00 → severidad = "severa", cierre = "considerar lente de contacto"

**Rama antimetropía** (EE_OD y EE_OI de signo opuesto, producto < 0), override de cierre:
- cierre = "antimetropia con posible compromiso fusional"

Formato final:
```
"Existe anisometropia {severidad} por diferencia de equivalente esferico de {diff:.2f}D
entre OD ({ee_od:+.2f}) y OI ({ee_oi:+.2f}); {cierre}."
```

### Ejemplo de activación
```
refraccion.od.esfera = -1.00, refraccion.oi.esfera = -3.50
# diff EE = 2.50 → moderada
```
→ `"Existe anisometropia moderada por diferencia de equivalente esferico de 2.50D entre OD (-1.00) y OI (-3.50); con posible impacto en la fusion binocular."`

### Clasificación
- [OK] — describe hallazgo refractivo objetivo con cuantificación, sin patología nombrada ni recomendación de acción clínica (solo descriptor "considerar lente de contacto" es orientativo, no directiva médica)

> Nota: "considerar lente de contacto" y "posible impacto en la fusion binocular" son descriptores, no directivas clínicas formales. Sin embargo, si se interpreta estrictamente, "considerar lente de contacto" podría etiquetarse como [RECOMENDACION] leve.

### Clasificación (estricta)
- [RECOMENDACION] leve — "considerar lente de contacto" (rama severa)

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
- **Campos evaluados:** `req.refraccion.od.av_cc`, `req.refraccion.oi.av_cc`
- **Umbral:** formato "20/X" con X > 20
- **Dependencias:** ninguna

### Texto actual (_texto)
Función dinámica `_texto_av_cc_limitada`:

Para cada ojo con AV limitada, agrega: `"{label} ({av}): {categoria}"`, separados por "; ", terminando en ".".

Categorías (`_av_categoria`):
- 20/21–20/30 → "leve reduccion de la agudeza visual con correccion"
- 20/31–20/50 → "reduccion moderada de la agudeza visual con correccion"
- 20/51–20/100 → "reduccion marcada de la agudeza visual con correccion"
- > 20/100 → "deficit visual severo con correccion optima"

Ejemplo con dos ojos:
```
"OD (20/40): reduccion moderada de la agudeza visual con correccion;
OI (20/25): leve reduccion de la agudeza visual con correccion."
```

### Ejemplo de activación
```
refraccion.od.av_cc = "20/40"
```
→ `"OD (20/40): reduccion moderada de la agudeza visual con correccion."`

### Clasificación
- [OK] — describe hallazgo funcional objetivo con cuantificación de categoría, sin diagnóstico ni recomendación

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
- **Campos evaluados:** `req.paciente.edad`, `req.clinica.uso_pantallas`, `req.akr.od/oi.esfera`, `req.refraccion.od/oi.esfera`
- **Umbrales:** edad < 40, uso_pantallas en ("btw2_6", "gt6"), (esf_Rx − esf_AR) ≥ +0.50 en cualquier ojo
- **Dependencias:** suprime `ar_rx_variabilidad_inespecifica`

### Texto actual (_texto)
Texto fijo:
```
"El autorrefractometro documenta mayor componente miopico que la refraccion
subjetiva final en un paciente joven con uso intensivo de pantallas, patron
compatible con espasmo acomodativo que amerita control posterior y eventual
refraccion bajo cicloplegia."
```

### Ejemplo de activación
```
paciente.edad = 22
clinica.uso_pantallas = "gt6"
akr.od.esfera = -3.50, refraccion.od.esfera = -2.75  # esf_Rx - esf_AR = +0.75 ≥ 0.50
```

### Clasificación
- [DIAGNOSTICO] — "espasmo acomodativo"
- [ATRIBUCION CAUSAL] — "compatible con espasmo acomodativo"
- [RECOMENDACION] — "amerita control posterior y eventual refraccion bajo cicloplegia"

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
    for ojo in ("od", "oi"):
        esf_ar = getattr(req.akr, ojo).esfera
        esf_rx = getattr(req.refraccion, ojo).esfera
        if esf_ar is None or esf_rx is None:
            continue
        if abs(esf_ar - esf_rx) > 1.00:
            return True
    return False
```
- **Campos evaluados:** `req.paciente.edad`, `req.akr.od/oi.esfera`, `req.refraccion.od/oi.esfera`
- **Umbrales:** edad ≥ 55, |esf_AR − esf_Rx| > 1.00 en cualquier ojo
- **Dependencias:** suprime `ar_rx_variabilidad_inespecifica`

### Texto actual (_texto)
Texto fijo:
```
"La discrepancia entre autorrefractometro y refraccion final en un paciente mayor
de 55 anos puede reflejar cambios en el indice refractivo del cristalino,
ameritando evaluacion biomicroscopica del segmento anterior."
```

### Ejemplo de activación
```
paciente.edad = 62
akr.oi.esfera = -1.00, refraccion.oi.esfera = +0.25  # |diff| = 1.25 > 1.00
```

### Clasificación
- [ATRIBUCION CAUSAL] — "puede reflejar cambios en el indice refractivo del cristalino"
- [RECOMENDACION] — "ameritando evaluacion biomicroscopica del segmento anterior"

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
- **Campos evaluados:** `req.akr.od/oi.esfera`, `req.akr.od/oi.cilindro`, `req.refraccion.od/oi.esfera`, `req.refraccion.od/oi.cilindro`
- **Umbrales:** |esf_AR − esf_Rx| > 1.00 O |cil_AR − cil_Rx| > 1.00 en cualquier ojo
- **Dependencias:** se suprime si `ar_rx_espasmo_acomodativo` o `ar_rx_cambio_cristalino` están activas

### Texto actual (_texto)
Texto fijo:
```
"Se documenta discrepancia entre autorrefractometro y refraccion final, compatible
con variabilidad refractiva durante la exploracion."
```

### Ejemplo de activación
```
paciente.edad = 30
clinica.uso_pantallas = None  # no activa espasmo
akr.od.cilindro = -2.00, refraccion.od.cilindro = -0.75  # |diff| = 1.25 > 1.00
```

### Clasificación
- [ATRIBUCION CAUSAL] — "compatible con variabilidad refractiva durante la exploracion"

---

## Correlación 21: ar_detecta_astigmatismo_no_prescrito

### Condición (_cond)
```python
def _cond_ar_detecta_astigmatismo_no_prescrito(req: ImpresionClinicaRequest) -> bool:
    if req.refraccion is None or req.akr is None:
        return False
    for ojo in ("od", "oi"):
        cil_ar = getattr(req.akr, ojo).cilindro
        cil_rx = getattr(req.refraccion, ojo).cilindro
        if cil_ar is None or abs(cil_ar) < 0.75:
            continue
        if cil_rx is None or abs(cil_rx) < 0.50:
            return True
    return False
```
- **Campos evaluados:** `req.akr.od/oi.cilindro`, `req.refraccion.od/oi.cilindro`
- **Umbrales:** |cil_AR| ≥ 0.75 Y (cil_Rx es None o |cil_Rx| < 0.50)
- **Dependencias:** ninguna

### Texto actual (_texto)
Texto fijo:
```
"El autorrefractometro detecta un componente astigmatico que no fue incluido en la
refraccion subjetiva final, lo que puede corresponder a astigmatismo subumbral
con tolerancia clinica adecuada o variabilidad de la medicion automatizada."
```

### Ejemplo de activación
```
akr.od.cilindro = -1.00, refraccion.od.cilindro = None
```

### Clasificación
- [OK] — describe discrepancia objetiva sin diagnóstico, sin recomendación de acción

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
- **Campos evaluados:** `req.refraccion.od/oi.cilindro`, `.eje`
- **Umbrales:** |cilindro| > 2.00 Y eje oblicuo (20–70° o 110–160°)
- **Dependencias:** ninguna

### Texto actual (_texto)
Función dinámica `_texto_astig_oblicuo`:

Para cada ojo que califica, según magnitud del cilindro:
- |cil| ≤ 3.00 → `"astigmatismo elevado con eje oblicuo"`
- 3.00 < |cil| ≤ 4.00 → `"astigmatismo alto con eje oblicuo, que puede requerir periodo de adaptacion a la correccion"`
- |cil| > 4.00 → `"astigmatismo de magnitud muy alta con eje oblicuo, con mayor impacto visual y de adaptacion"`

Formato por ojo: `"{label} ({cil:+.2f} x {eje}): {descripcion}"`, separados por "; ", terminando en ".".

### Ejemplo de activación
```
refraccion.od.cilindro = -3.50, refraccion.od.eje = 45
```
→ `"OD (-3.50 x 45): astigmatismo alto con eje oblicuo, que puede requerir periodo de adaptacion a la correccion."`

### Clasificación
- [OK] — describe hallazgo refractivo objetivo con graduaciones descriptivas. "puede requerir periodo de adaptacion" es descriptivo, no directiva clínica formal.

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
    return _contains_keyword(
        clinica.grid_de_amsler,
        _KEYWORDS_AMSLER_POSITIVOS,
        allow_negation_window=True,
    )
```
- **Campos evaluados:** `req.clinica.grid_de_amsler`
- **Keywords positivas:** `"distorsion"`, `"metamorfopsia"`, `"escotoma central"`, `"escotoma"`, `"alterado"`, `"alteracion"`, `"ondulacion"`, `"lineas torcidas"`
- **Keywords negativas (suprimen):** `"sin distorsion"`, `"sin alteracion"`, `"normal"`, `"negativo"`
- **Negation window:** sí (para positivas)
- **Dependencias:** ninguna

### Texto actual (_texto)
Texto fijo:
```
"El test de Amsler revela alteracion compatible con patologia macular funcional
que amerita OCT macular."
```

### Ejemplo de activación
```
clinica.grid_de_amsler = "metamorfopsia central OD"
```

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
    return bool(
        _extract_normalized_findings(
            clinica.anexos_oculares,
            _KEYWORDS_ANEXOS,
            allow_negation_window=True,
        )
    )
```
- **Campos evaluados:** `req.clinica.anexos_oculares`
- **Keywords (mapa):** `"blefaritis"`, `"chalazion"`, `"orzuelo"`, `"pterigion"`, `"pinguecula"`, `"conjuntivitis"`, `"hiperemia"` → "hiperemia conjuntival", `"queratitis"`, `"erosion"` → "erosion corneal", `"leucoma"` → "leucoma corneal", `"opacidad corneal"`, `"edema corneal"`, `"distriquiasis"`, `"triquiasis"`, `"ectropion"`, `"entropion"`, `"ptosis"` → "ptosis palpebral"
- **Negation window:** sí
- **Dependencias:** ninguna

### Texto actual (_texto)
Función dinámica:
```
"En anexos oculares se documenta {hallazgos_unidos}."
```
Donde `{hallazgos_unidos}` es la lista normalizada de los hallazgos encontrados, separada por ", " y " y " para el último.

### Ejemplo de activación
```
clinica.anexos_oculares = "blefaritis posterior bilateral, ptosis palpebral OD"
```
→ `"En anexos oculares se documenta blefaritis y ptosis palpebral."`

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
- **Campos evaluados:** `req.clinica.ppc_cm` (> 10 cm), `req.clinica.cover_test` (contiene "exoforia"), `req.paciente.motivo_consulta` (contiene keywords de cercanía)
- **Keywords cercanía:** `"lectura"`, `"leer"`, `"estudiar"`, `"cerca"`, `"astenopia"`, `"fatiga"`, `"cefalea"`
- **Dependencias:** suprime `ppc_exoforia` y `cover_exoforia_sintomatica` (ambas verifican que `_cond_insuficiencia_convergencia` sea False antes de activarse)

### Texto actual (_texto)
Texto fijo:
```
"La combinacion de punto proximo de convergencia alejado, exoforia y sintomatologia
de vision proxima es compatible con insuficiencia de convergencia, ameritando
evaluacion binocular completa para confirmar diagnostico y plantear terapia
visual si procede."
```

### Ejemplo de activación
```
clinica.ppc_cm = 14
clinica.cover_test = "OD: Exo y Foria | OI: Orto"
paciente.motivo_consulta = "cefalea con lectura prolongada"
```

### Clasificación
- [DIAGNOSTICO] — "insuficiencia de convergencia"
- [ATRIBUCION CAUSAL] — "compatible con insuficiencia de convergencia"
- [RECOMENDACION] — "ameritando evaluacion binocular completa para confirmar diagnostico y plantear terapia visual"

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
- **Campos evaluados:** `req.clinica.ppc_cm` (> 10 cm), `req.clinica.cover_test` (contiene "exoforia")
- **Dependencias:** se suprime si `_cond_insuficiencia_convergencia` está activa

### Texto actual (_texto)
Función dinámica `_texto_ppc_exoforia`:

Construye lista de partes:
1. Si PPC > 15: `"punto proximo de convergencia marcadamente alejado ({ppc} cm)"`
2. Si PPC 11-15: `"punto proximo de convergencia alejado ({ppc} cm)"`
3. Si "exoforia" en cover:
   - Con tokens "vp"/"cerca"/"proxima" → `"exoforia en vision proxima"`
   - Con tokens "vl"/"lejos" → `"exoforia en vision lejana"`
   - Sin ninguno → `"tendencia divergente en el cover test"`

Formato final:
```
"El paciente presenta {parte1} y {parte2}."
```
(o solo una parte si solo hay una condición activa)

### Ejemplo de activación
```
clinica.ppc_cm = 13
clinica.cover_test = "OD: Exo y Foria | OI: Orto"
# sin síntomas de cercanía en motivo → no activa insuficiencia_convergencia
```
→ `"El paciente presenta punto proximo de convergencia alejado (13 cm) y tendencia divergente en el cover test."`

### Clasificación
- [OK] — describe hallazgos clínicos objetivos sin diagnóstico formal ni recomendación de acción

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
- **Campos evaluados:** `req.clinica.cover_test` (contiene "exoforia"), `req.paciente.motivo_consulta` (keywords binoculares)
- **Keywords binoculares:** `"diplopia"`, `"vision doble"`, `"cefalea"`, `"dolor de cabeza"`, `"astenopia"`, `"fatiga visual"`, `"vista cansada"`, `"mareo"`, `"vertigo"`, `"ardor con lectura"`, `"lagrimeo con lectura"`, `"perdida del renglon"`, `"salto de letras"`, `"vision borrosa intermitente"`
- **Dependencias:** se suprime si `_cond_insuficiencia_convergencia` está activa

### Texto actual (_texto)
Texto fijo:
```
"La exoforia documentada junto con la sintomatologia referida es compatible con
disfuncion binocular de tipo divergente que amerita evaluacion funcional."
```

### Ejemplo de activación
```
clinica.cover_test = "OD: Exo y Foria"
paciente.motivo_consulta = "diplopia ocasional"
clinica.ppc_cm = None  # no activa insuficiencia_convergencia
```

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
- **Campos evaluados:** `req.clinica.cover_test` (contiene "endoforia" pero NO "endotropia"), `req.paciente.motivo_consulta` (keywords binoculares)
- **Dependencias:** ninguna

### Texto actual (_texto)
Texto fijo:
```
"La endoforia documentada junto con la sintomatologia referida es compatible con
exceso de convergencia o disfuncion acomodativa que amerita evaluacion funcional."
```

### Ejemplo de activación
```
clinica.cover_test = "OD: Endo y Foria | OI: Orto"
paciente.motivo_consulta = "cefalea frontal, astenopia"
```

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
Función dinámica `_texto_desviacion_vertical`:

Clasifica las keywords encontradas en forias vs tropias:

**Si hay tropias:**
```
"Se documenta {hallazgo}, que representa una desviacion manifiesta y amerita
cuantificacion prismatica inmediata con evaluacion binocular completa."
```

**Si solo hay forias:**
```
"Se documenta {hallazgo}, que puede generar sintomatologia binocular especifica
y amerita cuantificacion prismatica para evaluar compensacion."
```

`{hallazgo}` es la combinación de forias y/o tropias encontradas, unidas por " y ".

### Ejemplo de activación
```
clinica.cover_test = "OD: Hiper y Foria | OI: Orto"
```
→ `"Se documenta hiperforia, que puede generar sintomatologia binocular especifica y amerita cuantificacion prismatica para evaluar compensacion."`

### Clasificación
- [RECOMENDACION] — "amerita cuantificacion prismatica inmediata" / "amerita cuantificacion prismatica"

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
- **Campos evaluados:** `req.clinica.uso_pantallas` (debe ser "btw2_6" o "gt6"), `req.paciente.motivo_consulta`
- **Keywords CVS:** `"ardor ocular"`, `"sequedad ocular"`, `"vision borrosa intermitente"`, `"dolor ocular"`, `"ardor"`, `"sequedad"`
- **Dependencias:** ninguna

### Texto actual (_texto)
Texto fijo:
```
"El perfil de uso de pantallas y la sintomatologia referida son compatibles con
sindrome visual informatico, ameritando recomendaciones ergonomicas y eventual
correccion optica para vision intermedia."
```

### Ejemplo de activación
```
clinica.uso_pantallas = "gt6"
paciente.motivo_consulta = "ardor ocular y vision borrosa al terminar de trabajar"
```

### Clasificación
- [DIAGNOSTICO] — "sindrome visual informatico"
- [ATRIBUCION CAUSAL] — "compatibles con sindrome visual informatico"
- [RECOMENDACION] — "ameritando recomendaciones ergonomicas y eventual correccion optica"

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
Texto fijo:
```
"La endotropia documentada en el cover test amerita evaluacion de la respuesta
a la correccion optica prescrita, con cover test bajo correccion para clasificar
el tipo de desviacion."
```

### Ejemplo de activación
```
clinica.cover_test = "OD: Endo y Tropia"
tipo_lente = "monofocal"
```

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
Texto fijo:
```
"La exotropia documentada en el cover test amerita evaluacion binocular completa
para determinar frecuencia y magnitud de la desviacion, asi como la respuesta
a la correccion optica prescrita."
```

### Ejemplo de activación
```
clinica.cover_test = "OI: Exo y Tropia"
tipo_lente = "progresivo"
```

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
- **Campos evaluados:** `req.clinica.ojo_seco_but_seg` (rango 5–9 s), `req.clinica.uso_pantallas` ("btw2_6" o "gt6")
- **Dependencias:** rango exclusivo respecto a `but_critico` (< 5) y `but_limitrofe` (5-9 sin pantallas)

### Texto actual (_texto)
Función dinámica:
```
"El tiempo de ruptura lagrimal de {but} segundos es reducido en el contexto
del uso de pantallas, lo que indica inestabilidad de la pelicula lagrimal."
```

### Ejemplo de activación
```
clinica.ojo_seco_but_seg = 7
clinica.uso_pantallas = "btw2_6"
```
→ `"El tiempo de ruptura lagrimal de 7 segundos es reducido en el contexto del uso de pantallas, lo que indica inestabilidad de la pelicula lagrimal."`

### Clasificación
- [OK] — describe hallazgo objetivo con contexto clínico, sin diagnóstico formal ni recomendación de acción. "indica inestabilidad de la pelicula lagrimal" es hallazgo descriptivo.

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
- **Campos evaluados:** `req.clinica.ojo_seco_but_seg` (rango 5–9 s), `req.clinica.uso_pantallas` (None o "lt2")
- **Dependencias:** rango exclusivo respecto a `but_critico` y `but_pantallas`

### Texto actual (_texto)
Función dinámica:
```
"El tiempo de ruptura lagrimal de {but}s se encuentra en rango suboptimo,
sugiriendo inestabilidad leve de la pelicula lagrimal."
```

### Ejemplo de activación
```
clinica.ojo_seco_but_seg = 8
clinica.uso_pantallas = None
```
→ `"El tiempo de ruptura lagrimal de 8s se encuentra en rango suboptimo, sugiriendo inestabilidad leve de la pelicula lagrimal."`

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
- **Campos evaluados:** `req.tipo_lente` (tokens "bifocal"/"progresivo"/"multifocal"), `req.paciente.edad` (≥ 40), `req.refraccion.od.add` o `req.refraccion.oi.add` (no nulo)
- **Lógica:** activa si (multifocal Y (edad≥40 O hay_add)) O (edad≥40 Y hay_add)
- **Dependencias:** ninguna

### Texto actual (_texto)
Función dinámica `_texto_presbicia_multifocal`:

**Rama con edad conocida:**
```
"El paciente de {edad} anos presenta reduccion fisiologica de la amplitud
acomodativa propia de la edad, lo que justifica la adicion prescrita{sufijo_lente}."
```

**Rama sin edad (edad is None):**
```
"Se documenta reduccion fisiologica de la amplitud acomodativa, lo que justifica
la adicion prescrita{sufijo_lente}."
```

`{sufijo_lente}`:
- Si lente multifocal: `" y el lente multifocal indicado"`
- Si no: `""` (cadena vacía)

### Ejemplo de activación
```
paciente.edad = 52
refraccion.od.add = +2.00
tipo_lente = "progresivo"
```
→ `"El paciente de 52 anos presenta reduccion fisiologica de la amplitud acomodativa propia de la edad, lo que justifica la adicion prescrita y el lente multifocal indicado."`

### Clasificación
- [OK] — contextualiza hallazgo fisiológico esperado por edad, sin diagnosticar, sin recomendar acción adicional

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
        )
    )
```
- **Campos evaluados:** `req.paciente.edad` (≥ 60), `req.refraccion.od/oi.av_cc` (AV limitada), ausencia de 8 correlaciones específicas
- **Dependencias:** se suprime si cualquiera de las 8 correlaciones listadas está activa (es un "catch-all" para AV reducida en mayor sin causa identificada)

### Texto actual (_texto)
Función dinámica:
```
"En paciente de {edad} anos con reduccion de agudeza visual, se recomienda
descarte activo de catarata, glaucoma y maculopatia asociada a la edad mediante
exploracion dirigida."
```

### Ejemplo de activación
```
paciente.edad = 68
refraccion.od.av_cc = "20/50"
# sin catarata, sin excavación, sin drusas, sin MER, sin microaneurismas,
# sin tortuosidad, sin miopia magna, sin palidez papilar
```
→ `"En paciente de 68 anos con reduccion de agudeza visual, se recomienda descarte activo de catarata, glaucoma y maculopatia asociada a la edad mediante exploracion dirigida."`

### Clasificación
- [RECOMENDACION] — "se recomienda descarte activo de catarata, glaucoma y maculopatia"

---

## RESUMEN FINAL

### Conteos por etiqueta

| Etiqueta | Total | Correlaciones |
|---|---|---|
| **[DIAGNOSTICO]** | **10** | glaucoma_asimetrico, fondo_glaucomatoso, fondo_macular_dmae, fondo_hipertensivo, fondo_vascular_diabetico, but_critico, ar_rx_espasmo_acomodativo, insuficiencia_convergencia, cvs_sospecha, (ver detalle) |
| **[RECOMENDACION]** | **26** | fondo_periferico_riesgo, papila_patologica, glaucoma_asimetrico, pupilas_alteradas, fondo_glaucomatoso, fondo_macular_dmae, fondo_macular_otros, fondo_hipertensivo, fondo_vascular_diabetico, motilidad_alterada, campos_visuales_alterados, opacidad_cristaliniana, but_critico, hipermetropia_alta, anisometropia (leve), ar_rx_espasmo_acomodativo, ar_rx_cambio_cristalino, amsler_alterado, insuficiencia_convergencia, cover_exoforia_sintomatica, cover_endoforia_sintomatica, desviacion_vertical, cvs_sospecha, endotropia_lente, exotropia_lente, adulto_mayor_screening |
| **[ATRIBUCION CAUSAL]** | **16** | papila_patologica, glaucoma_asimetrico, pupilas_alteradas, fondo_glaucomatoso, fondo_macular_dmae, fondo_hipertensivo, fondo_vascular_diabetico, but_critico, miopia_magna, ar_rx_espasmo_acomodativo, ar_rx_cambio_cristalino, ar_rx_variabilidad_inespecifica, amsler_alterado, insuficiencia_convergencia, cover_exoforia_sintomatica, cover_endoforia_sintomatica, but_limitrofe |
| **[OK]** | **7** | av_cc_limitada, ar_detecta_astigmatismo_no_prescrito, astig_oblicuo, anexos_patologicos, ppc_exoforia, but_pantallas, presbicia_multifocal |

> Nota: una correlación puede tener múltiples etiquetas. Los totales de arriba cuentan correlaciones que tienen al menos esa etiqueta.

### Tabla resumen individual

| # | Nombre | DIAGNOSTICO | RECOMENDACION | ATRIBUCION CAUSAL | OK |
|---|---|:---:|:---:|:---:|:---:|
| 1 | fondo_periferico_riesgo | — | ✓ | — | — |
| 2 | papila_patologica | — | ✓ | ✓ | — |
| 3 | glaucoma_asimetrico | ✓ | ✓ | ✓ | — |
| 4 | pupilas_alteradas | — | ✓ | ✓ | — |
| 5 | fondo_glaucomatoso | ✓ | ✓ | ✓ | — |
| 6 | fondo_macular_dmae | ✓ | ✓ | ✓ | — |
| 7 | fondo_macular_otros | — | ✓ | — | — |
| 8 | fondo_hipertensivo | ✓ | ✓ | ✓ | — |
| 9 | fondo_vascular_diabetico | ✓ | ✓ | ✓ | — |
| 10 | motilidad_alterada | — | ✓ | — | — |
| 11 | campos_visuales_alterados | — | ✓ | — | — |
| 12 | opacidad_cristaliniana | — | ✓ | — | — |
| 13 | but_critico | ✓ | ✓ | ✓ | — |
| 14 | miopia_magna | — | — | ✓ | — |
| 15 | hipermetropia_alta | — | ✓ | — | — |
| 16 | anisometropia | — | ✓* | — | — |
| 17 | av_cc_limitada | — | — | — | ✓ |
| 18 | ar_rx_espasmo_acomodativo | ✓ | ✓ | ✓ | — |
| 19 | ar_rx_cambio_cristalino | — | ✓ | ✓ | — |
| 20 | ar_rx_variabilidad_inespecifica | — | — | ✓ | — |
| 21 | ar_detecta_astigmatismo_no_prescrito | — | — | — | ✓ |
| 22 | astig_oblicuo | — | — | — | ✓ |
| 23 | amsler_alterado | — | ✓ | ✓ | — |
| 24 | anexos_patologicos | — | — | — | ✓ |
| 25 | insuficiencia_convergencia | ✓ | ✓ | ✓ | — |
| 26 | ppc_exoforia | — | — | — | ✓ |
| 27 | cover_exoforia_sintomatica | — | ✓ | ✓ | — |
| 28 | cover_endoforia_sintomatica | — | ✓ | ✓ | — |
| 29 | desviacion_vertical | — | ✓ | — | — |
| 30 | cvs_sospecha | ✓ | ✓ | ✓ | — |
| 31 | endotropia_lente | — | ✓ | — | — |
| 32 | exotropia_lente | — | ✓ | — | — |
| 33 | but_pantallas | — | — | — | ✓ |
| 34 | but_limitrofe | — | — | ✓ | — |
| 35 | presbicia_multifocal | — | — | — | ✓ |
| 36 | adulto_mayor_screening | — | ✓ | — | — |

*`anisometropia` rama severa incluye "considerar lente de contacto" (recomendación leve)

### Correlaciones con prefijo "Hallazgo urgente:"

Las siguientes correlaciones incluyen literalmente el texto `"Hallazgo urgente:"` en alguna de sus ramas:

1. **fondo_periferico_riesgo** — siempre (es el inicio del texto)
2. **glaucoma_asimetrico** — siempre (es el inicio del texto fijo)
3. **pupilas_alteradas** — solo en el sufijo adicional cuando hay DPAR entre los hallazgos

Total: **3 correlaciones** con prefijo "Hallazgo urgente:"
