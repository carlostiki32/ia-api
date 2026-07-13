# Batería de pruebas — `/inferencia/impresion-clinica`

> 137 casos reales para validar la arquitectura de correlaciones + LLM.
> Cada caso está **fundamentado** en el catálogo del frontend
> ([DICCIONARIO_DATOS_RECETA.md](DICCIONARIO_DATOS_RECETA.md)) y en las 41 reglas
> deterministas ([CORRELACIONES_CLINICAS.md](CORRELACIONES_CLINICAS.md)). No hay
> valores inventados fuera de catálogo salvo el **Bloque 10** (coerción tolerante),
> donde probar el fuera-de-rango ES el objetivo.

---

## 0. Cómo ejecutar (protocolo para el modelo probador)

**Endpoint**

```
POST http://localhost:8888/inferencia/impresion-clinica
Authorization: Bearer 12345678
Content-Type: application/json
```

**Qué hace cada caso.** El payload trae `receta_id` único. La API responde:

```json
{
  "status": "ok",
  "impresion_clinica": "…texto clínico del LLM…",
  "correlaciones_activadas": ["...", "..."]
}
```

**Protocolo de validación, 1 por 1:**

1. Toma el bloque `json` del caso y hazle `POST`.
2. Captura `status` HTTP, `correlaciones_activadas` y `impresion_clinica`.
3. Compara `correlaciones_activadas` (como **conjunto**) contra
   **Correlaciones esperadas** del caso. El orden en que las devuelve la API es el
   orden del registro; para validar basta comparar conjuntos.
4. Marca **PASS** si el conjunto coincide, **FAIL** si difiere (anota las que
   sobran/faltan). El `impresion_clinica` es texto libre del LLM: **no** se valida
   por igualdad, solo se revisa que mencione los hallazgos urgentes primero.
5. Registra el `impresion_clinica` para revisión cualitativa.

**Notas operativas:**

- La inferencia es GPU-bound (Ollama, qwen3.5:9b). Cada caso nuevo puede tardar
  varios segundos. Usa timeout ≥ 180 s por request.
- Repetir el **mismo** payload devuelve `"cached": true` sin tocar la GPU: útil
  para reintentar la validación de correlaciones sin re-inferir.
- Las `correlaciones_activadas` son **deterministas**: si fallan, el bug está en la
  capa de reglas, no en el LLM. Ese es el criterio PASS/FAIL duro.
- El caso `Z-10` espera **HTTP 422** (payload sin datos clínicos): es correcto que
  NO devuelva 200.

**Runner opcional (Python).** Parsea *este mismo archivo*, ejecuta cada caso y
escribe `resultados_bateria.json`:

```python
import json, re, sys, urllib.request

MD = sys.argv[1] if len(sys.argv) > 1 else "BATERIA_PRUEBAS_IA.md"
URL = "http://localhost:8888/inferencia/impresion-clinica"
KEY = "12345678"

texto = open(MD, encoding="utf-8").read()
# Cada caso empieza en una linea "### CASO <id>"
bloques = re.split(r"(?m)^### CASO ", texto)[1:]
casos = []
for b in bloques:
    cid = b.splitlines()[0].strip()
    m_exp = re.search(r"\*\*Correlaciones esperadas:\*\*\s*(.+)", b)
    m_json = re.search(r"```json\s*(\{.*?\})\s*```", b, re.S)
    if not m_json:
        continue
    esperado_raw = m_exp.group(1).strip() if m_exp else "[]"
    if "422" in esperado_raw:
        esperado = "HTTP_422"
    else:
        esperado = set(json.loads(esperado_raw.strip(" `")))
    casos.append((cid, esperado, json.loads(m_json.group(1))))

resultados = []
for cid, esperado, payload in casos:
    req = urllib.request.Request(
        URL, data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"},
        method="POST")
    try:
        with urllib.request.urlopen(req, timeout=200) as r:
            code, body = r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        code, body = e.code, {}
    if esperado == "HTTP_422":
        ok = code == 422
        got = f"HTTP {code}"
    else:
        got = set(body.get("correlaciones_activadas", []))
        ok = code == 200 and got == esperado
    print(f"[{'PASS' if ok else 'FAIL'}] {cid}  esperado={esperado}  obtenido={got}")
    resultados.append({"caso": cid, "http": code, "pass": ok,
                       "esperado": list(esperado) if isinstance(esperado, set) else esperado,
                       "obtenido": list(got) if isinstance(got, set) else got,
                       "impresion_clinica": body.get("impresion_clinica", "")})

json.dump(resultados, open("resultados_bateria.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=2)
print(f"\n{sum(r['pass'] for r in resultados)}/{len(resultados)} PASS")
```

---

## Índice de bloques

| Bloque | Tema | Casos |
|---|---|---|
| 1 | Rutina / normales (línea base) | R-01…R-10 |
| 2 | Refracción final (magna, hipermetropía, aniso, astig, AV) | RF-01…RF-16 |
| 3 | Fondo de ojo (8 reglas + supresión + negación) | F-01…F-17 |
| 4 | AKR vs Rx + córnea/queratometría | A-01…A-13 |
| 5 | Anexos, cristalino, pupilas, motilidad, campos, Amsler | S-01…S-18 |
| 6 | Binocularidad y convergencia | B-01…B-16 |
| 7 | Superficie ocular — BUT | C-01…C-07 |
| 8 | Edad, lente, pantallas, presbicia, screening | E-01…E-16 |
| 9 | Casos compuestos complejos (multi-disparador) | X-01…X-12 |
| 10 | Coerción tolerante y edge cases | Z-01…Z-12 |

> **Referencia de orden del registro** (así devuelve la API `correlaciones_activadas`):
> fondo_periferico_riesgo, papila_patologica, glaucoma_asimetrico, pupilas_alteradas,
> fondo_glaucomatoso, fondo_macular_dmae, fondo_macular_otros, fondo_hipertensivo,
> fondo_vascular_diabetico, motilidad_alterada, campos_visuales_alterados,
> opacidad_cristaliniana, but_critico, miopia_magna, hipermetropia_alta,
> anisometropia, av_cc_limitada, ar_rx_espasmo_acomodativo, ar_rx_cambio_cristalino,
> ar_rx_variabilidad_inespecifica, ar_detecta_astigmatismo_no_prescrito,
> astig_oblicuo, queratocono_ectasia_sospecha, astigmatismo_corneal_vs_refractivo,
> amsler_alterado, anexos_patologicos, insuficiencia_convergencia, ppc_exoforia,
> cover_exoforia_sintomatica, cover_endoforia_sintomatica, desviacion_vertical,
> cvs_sospecha, endotropia_lente, exotropia_lente, but_pantallas, but_limitrofe,
> presbicia_multifocal, presbicia_sin_adicion, adicion_incongruente_edad,
> ambliopia_sospecha, adulto_mayor_screening.

---

## Bloque 1 — Rutina / línea base

### CASO R-01
**Complejidad:** rutina · **Objetivo:** miope leve joven, sin disparadores.
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"R-01","paciente":{"edad":22,"ocupacion":"estudiante","motivo_consulta":"vision borrosa de lejos"},"refraccion":{"od":{"esfera":-0.75,"cilindro":0.0,"av_cc":"20/20"},"oi":{"esfera":-1.00,"cilindro":0.0,"av_cc":"20/20"}},"tipo_lente":"monofocal"}
```

### CASO R-02
**Complejidad:** rutina · **Objetivo:** emétrope adulto, chequeo anual.
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"R-02","paciente":{"edad":34,"ocupacion":"comerciante","motivo_consulta":"chequeo anual"},"refraccion":{"od":{"esfera":0.0,"cilindro":0.0,"av_cc":"20/20"},"oi":{"esfera":0.0,"cilindro":0.0,"av_cc":"20/20"}},"tipo_lente":"monofocal"}
```

### CASO R-03
**Complejidad:** rutina · **Objetivo:** astigmatismo bajo a favor de la regla, sin disparo.
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"R-03","paciente":{"edad":28,"ocupacion":"vendedor","motivo_consulta":"vision borrosa"},"refraccion":{"od":{"esfera":-0.50,"cilindro":-0.75,"eje":180,"av_cc":"20/20"},"oi":{"esfera":-0.25,"cilindro":-0.50,"eje":175,"av_cc":"20/20"}},"tipo_lente":"monofocal"}
```

### CASO R-04
**Complejidad:** rutina · **Objetivo:** présbita típico con progresivo y adición congruente.
**Correlaciones esperadas:** `["presbicia_multifocal"]`

```json
{"receta_id":"R-04","paciente":{"edad":52,"ocupacion":"contador","motivo_consulta":"dificultad para leer"},"refraccion":{"od":{"esfera":0.75,"cilindro":0.0,"add":2.00,"av_cc":"20/20"},"oi":{"esfera":0.75,"cilindro":0.0,"add":2.00,"av_cc":"20/20"}},"tipo_lente":"progresivo"}
```

### CASO R-05
**Complejidad:** rutina · **Objetivo:** présbita sin adición (recordatorio) — emétrope monofocal.
**Correlaciones esperadas:** `["presbicia_sin_adicion"]`

```json
{"receta_id":"R-05","paciente":{"edad":49,"ocupacion":"ama de casa","motivo_consulta":"revision de rutina"},"refraccion":{"od":{"esfera":-0.50,"cilindro":0.0,"av_cc":"20/20"},"oi":{"esfera":-0.25,"cilindro":0.0,"av_cc":"20/20"}},"tipo_lente":"monofocal"}
```

### CASO R-06
**Complejidad:** rutina · **Objetivo:** hipermétrope leve, no llega a hipermetropía alta.
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"R-06","paciente":{"edad":38,"ocupacion":"chofer","motivo_consulta":"molestia leve"},"refraccion":{"od":{"esfera":1.75,"cilindro":0.0,"av_cc":"20/20"},"oi":{"esfera":2.00,"cilindro":0.0,"av_cc":"20/20"}},"tipo_lente":"monofocal"}
```

### CASO R-07
**Complejidad:** rutina · **Objetivo:** miope moderado con astig ≤2 D, sin disparo.
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"R-07","paciente":{"edad":19,"ocupacion":"estudiante","motivo_consulta":"actualizar lentes"},"refraccion":{"od":{"esfera":-3.00,"cilindro":-1.00,"eje":10,"av_cc":"20/20"},"oi":{"esfera":-2.75,"cilindro":-1.25,"eje":170,"av_cc":"20/20"}},"tipo_lente":"monofocal"}
```

### CASO R-08
**Complejidad:** rutina · **Objetivo:** pantallas + BUT normal (12 s) NO debe disparar ojo seco.
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"R-08","paciente":{"edad":30,"ocupacion":"oficinista","motivo_consulta":"chequeo"},"refraccion":{"od":{"esfera":-1.00,"cilindro":0.0,"av_cc":"20/20"},"oi":{"esfera":-1.00,"cilindro":0.0,"av_cc":"20/20"}},"clinica":{"uso_pantallas":"gt6","ojo_seco_but_seg":12,"cover_test":"OD: Orto | OI: Orto","fondo_de_ojo":"Retina aplicada, papila de bordes netos, macula sin lesiones."},"tipo_lente":"monofocal"}
```

### CASO R-09
**Complejidad:** rutina · **Objetivo:** cover Orto + cefalea + PPC 5 cm NO dispara binocular.
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"R-09","paciente":{"edad":26,"ocupacion":"recepcionista","motivo_consulta":"cefalea ocasional"},"refraccion":{"od":{"esfera":-1.00,"cilindro":0.0,"av_cc":"20/20"},"oi":{"esfera":-1.00,"cilindro":0.0,"av_cc":"20/20"}},"clinica":{"cover_test":"OD: Orto | OI: Orto","ppc_cm":5},"tipo_lente":"monofocal"}
```

### CASO R-10
**Complejidad:** rutina · **Objetivo:** miope funcional 45 años sin adición NO dispara (EE < −1.50).
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"R-10","paciente":{"edad":45,"ocupacion":"maestro","motivo_consulta":"revision"},"refraccion":{"od":{"esfera":-2.00,"cilindro":-0.50,"eje":90,"av_cc":"20/20"},"oi":{"esfera":-2.25,"cilindro":-0.50,"eje":90,"av_cc":"20/20"}},"tipo_lente":"monofocal"}
```

## Bloque 2 — Refracción final

### CASO RF-01
**Complejidad:** rutina · **Objetivo:** miopía magna (EE ≤ −6.00) bilateral.
**Correlaciones esperadas:** `["miopia_magna"]`

```json
{"receta_id":"RF-01","paciente":{"edad":30,"ocupacion":"diseñador","motivo_consulta":"control de miopia"},"refraccion":{"od":{"esfera":-6.50,"cilindro":0.0,"av_cc":"20/25"},"oi":{"esfera":-6.00,"cilindro":0.0,"av_cc":"20/25"}},"tipo_lente":"monofocal"}
```

### CASO RF-02
**Complejidad:** compleja · **Objetivo:** miopía muy alta (EE ≤ −8) + AV limitada.
**Correlaciones esperadas:** `["miopia_magna","av_cc_limitada"]`

```json
{"receta_id":"RF-02","paciente":{"edad":45,"ocupacion":"empleado","motivo_consulta":"baja vision"},"refraccion":{"od":{"esfera":-9.00,"cilindro":-1.00,"eje":90,"av_cc":"20/40"},"oi":{"esfera":-8.50,"cilindro":0.0,"av_cc":"20/30"}},"tipo_lente":"monofocal"}
```

### CASO RF-03
**Complejidad:** compleja · **Objetivo:** hipermetropía alta présbita (≥40) + adición congruente.
**Correlaciones esperadas:** `["hipermetropia_alta","presbicia_multifocal"]`

```json
{"receta_id":"RF-03","paciente":{"edad":58,"ocupacion":"jubilado","motivo_consulta":"cansancio visual"},"refraccion":{"od":{"esfera":5.50,"cilindro":0.0,"add":2.50,"av_cc":"20/25"},"oi":{"esfera":5.00,"cilindro":0.0,"add":2.50,"av_cc":"20/25"}},"tipo_lente":"progresivo"}
```

### CASO RF-04
**Complejidad:** compleja · **Objetivo:** hipermetropía alta joven (demanda acomodativa) + AV.
**Correlaciones esperadas:** `["hipermetropia_alta","av_cc_limitada"]`

```json
{"receta_id":"RF-04","paciente":{"edad":8,"ocupacion":"estudiante","motivo_consulta":"le duele la cabeza al estudiar"},"refraccion":{"od":{"esfera":5.00,"cilindro":0.0,"av_cc":"20/30"},"oi":{"esfera":5.50,"cilindro":0.0,"av_cc":"20/30"}},"tipo_lente":"monofocal"}
```

### CASO RF-05
**Complejidad:** compleja · **Objetivo:** gran astígmata NO es hipermetropía alta (piso de esfera).
**Correlaciones esperadas:** `["av_cc_limitada"]`

```json
{"receta_id":"RF-05","paciente":{"edad":50,"ocupacion":"agricultor","motivo_consulta":"mala vision de siempre"},"refraccion":{"od":{"esfera":1.00,"cilindro":-8.00,"eje":90,"av_cc":"20/40"},"oi":{"esfera":0.75,"cilindro":-7.50,"eje":90,"av_cc":"20/40"}},"tipo_lente":"monofocal"}
```

### CASO RF-06
**Complejidad:** rutina · **Objetivo:** astigmatismo oblicuo elevado bilateral, AV conservada.
**Correlaciones esperadas:** `["astig_oblicuo"]`

```json
{"receta_id":"RF-06","paciente":{"edad":35,"ocupacion":"mecanico","motivo_consulta":"vision distorsionada"},"refraccion":{"od":{"esfera":-1.00,"cilindro":-2.50,"eje":45,"av_cc":"20/25"},"oi":{"esfera":-1.00,"cilindro":-2.50,"eje":135,"av_cc":"20/25"}},"tipo_lente":"monofocal"}
```

### CASO RF-07
**Complejidad:** rutina · **Objetivo:** astigmatismo oblicuo muy alto (>4 D) bilateral.
**Correlaciones esperadas:** `["astig_oblicuo"]`

```json
{"receta_id":"RF-07","paciente":{"edad":33,"ocupacion":"soldador","motivo_consulta":"control anual"},"refraccion":{"od":{"esfera":-2.00,"cilindro":-4.50,"eje":60,"av_cc":"20/20"},"oi":{"esfera":-2.00,"cilindro":-4.50,"eje":120,"av_cc":"20/20"}},"tipo_lente":"monofocal"}
```

### CASO RF-08
**Complejidad:** rutina · **Objetivo:** anisometropía moderada (ΔEE = 2.50).
**Correlaciones esperadas:** `["anisometropia"]`

```json
{"receta_id":"RF-08","paciente":{"edad":30,"ocupacion":"enfermera","motivo_consulta":"molestia al enfocar"},"refraccion":{"od":{"esfera":-1.00,"cilindro":0.0,"av_cc":"20/20"},"oi":{"esfera":-3.50,"cilindro":0.0,"av_cc":"20/20"}},"tipo_lente":"monofocal"}
```

### CASO RF-09
**Complejidad:** compleja · **Objetivo:** anisometropía severa con antimetropía.
**Correlaciones esperadas:** `["anisometropia"]`

```json
{"receta_id":"RF-09","paciente":{"edad":25,"ocupacion":"cajero","motivo_consulta":"vision desigual"},"refraccion":{"od":{"esfera":2.00,"cilindro":0.0,"av_cc":"20/20"},"oi":{"esfera":-3.00,"cilindro":0.0,"av_cc":"20/25"}},"tipo_lente":"monofocal"}
```

### CASO RF-10
**Complejidad:** compleja · **Objetivo:** anisometropía pediátrica (≤8) + AV + ambliopía.
**Correlaciones esperadas:** `["anisometropia","av_cc_limitada","ambliopia_sospecha"]`

```json
{"receta_id":"RF-10","paciente":{"edad":6,"ocupacion":"estudiante","motivo_consulta":"revision escolar"},"refraccion":{"od":{"esfera":1.00,"cilindro":0.0,"av_cc":"20/20"},"oi":{"esfera":4.50,"cilindro":0.0,"av_cc":"20/40","av_sc":"20/60"}},"tipo_lente":"monofocal"}
```

### CASO RF-11
**Complejidad:** rutina · **Objetivo:** AV con corrección limitada aislada (adulto joven, sin factor).
**Correlaciones esperadas:** `["av_cc_limitada"]`

```json
{"receta_id":"RF-11","paciente":{"edad":30,"ocupacion":"obrero","motivo_consulta":"no ve bien ni con lentes"},"refraccion":{"od":{"esfera":-2.00,"cilindro":0.0,"av_cc":"20/40"},"oi":{"esfera":-2.00,"cilindro":0.0,"av_cc":"20/40"}},"tipo_lente":"monofocal"}
```

### CASO RF-12
**Complejidad:** compleja · **Objetivo:** anciano con AV baja SIN causa → screening dirigido.
**Correlaciones esperadas:** `["av_cc_limitada","presbicia_multifocal","adulto_mayor_screening"]`

```json
{"receta_id":"RF-12","paciente":{"edad":68,"ocupacion":"jubilado","motivo_consulta":"ve borroso con lentes nuevos"},"refraccion":{"od":{"esfera":-1.00,"cilindro":0.0,"add":2.50,"av_cc":"20/80"},"oi":{"esfera":-1.00,"cilindro":0.0,"add":2.50,"av_cc":"20/60"}},"tipo_lente":"progresivo"}
```

### CASO RF-13
**Complejidad:** compleja · **Objetivo:** AV 20/30 (umbral leve) + présbita sin adición.
**Correlaciones esperadas:** `["av_cc_limitada","presbicia_sin_adicion"]`

```json
{"receta_id":"RF-13","paciente":{"edad":50,"ocupacion":"secretaria","motivo_consulta":"revision"},"refraccion":{"od":{"esfera":-1.00,"cilindro":0.0,"av_cc":"20/30"},"oi":{"esfera":-1.00,"cilindro":0.0,"av_cc":"20/25"}},"tipo_lente":"monofocal"}
```

### CASO RF-14
**Complejidad:** rutina · **Objetivo:** AV 20/25 NO dispara (límite normal).
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"RF-14","paciente":{"edad":30,"ocupacion":"empleado","motivo_consulta":"chequeo"},"refraccion":{"od":{"esfera":-1.00,"cilindro":0.0,"av_cc":"20/25"},"oi":{"esfera":-1.00,"cilindro":0.0,"av_cc":"20/20"}},"tipo_lente":"monofocal"}
```

### CASO RF-15
**Complejidad:** compleja · **Objetivo:** magna + anisometropía + AV (ambliopía suprimida por causa orgánica).
**Correlaciones esperadas:** `["miopia_magna","anisometropia","av_cc_limitada"]`

```json
{"receta_id":"RF-15","paciente":{"edad":40,"ocupacion":"empleado","motivo_consulta":"vision muy mala del ojo izquierdo"},"refraccion":{"od":{"esfera":-10.00,"cilindro":0.0,"av_cc":"20/60"},"oi":{"esfera":-6.50,"cilindro":0.0,"av_cc":"20/30"}},"tipo_lente":"monofocal"}
```

### CASO RF-16
**Complejidad:** rutina · **Objetivo:** hipermetropía alta límite (EE exacto +5.00) unilateral.
**Correlaciones esperadas:** `["hipermetropia_alta"]`

```json
{"receta_id":"RF-16","paciente":{"edad":42,"ocupacion":"comerciante","motivo_consulta":"vista cansada"},"refraccion":{"od":{"esfera":5.00,"cilindro":0.0,"av_cc":"20/25"},"oi":{"esfera":4.00,"cilindro":0.0,"av_cc":"20/20"}},"tipo_lente":"monofocal"}
```

## Bloque 3 — Fondo de ojo

### CASO F-01
**Complejidad:** compleja · **Objetivo:** urgencia periférica — lattice.
**Correlaciones esperadas:** `["fondo_periferico_riesgo"]`

```json
{"receta_id":"F-01","paciente":{"edad":40,"ocupacion":"empleado","motivo_consulta":"destellos de luz"},"clinica":{"fondo_de_ojo":"Lattice en periferia temporal de OI, retina aplicada."}}
```

### CASO F-02
**Complejidad:** compleja · **Objetivo:** urgencia periférica — desgarro.
**Correlaciones esperadas:** `["fondo_periferico_riesgo"]`

```json
{"receta_id":"F-02","paciente":{"edad":55,"ocupacion":"empleado","motivo_consulta":"moscas volantes recientes"},"clinica":{"fondo_de_ojo":"Desgarro retiniano en cuadrante superior de OD."}}
```

### CASO F-03
**Complejidad:** compleja · **Objetivo:** urgencia periférica — desprendimiento.
**Correlaciones esperadas:** `["fondo_periferico_riesgo"]`

```json
{"receta_id":"F-03","paciente":{"edad":60,"ocupacion":"jubilado","motivo_consulta":"cortina en la vision"},"clinica":{"fondo_de_ojo":"Desprendimiento de retina inferior en OI."}}
```

### CASO F-04
**Complejidad:** rutina · **Objetivo:** glaucomatoso por relación C/D (0.7).
**Correlaciones esperadas:** `["fondo_glaucomatoso"]`

```json
{"receta_id":"F-04","paciente":{"edad":58,"ocupacion":"empleado","motivo_consulta":"antecedente familiar de glaucoma"},"clinica":{"fondo_de_ojo":"Excavacion papilar c/d 0.7 en ambos ojos, resto sin alteraciones."}}
```

### CASO F-05
**Complejidad:** rutina · **Objetivo:** glaucomatoso por notch / papila asimétrica.
**Correlaciones esperadas:** `["fondo_glaucomatoso"]`

```json
{"receta_id":"F-05","paciente":{"edad":62,"ocupacion":"empleado","motivo_consulta":"control"},"clinica":{"fondo_de_ojo":"Muesca en el anillo neurorretiniano inferior de OD, papila asimetrica."}}
```

### CASO F-06
**Complejidad:** compleja · **Objetivo:** glaucoma asimétrico (DPAR + excavación) suprime pupilas y fondo_glaucomatoso.
**Correlaciones esperadas:** `["glaucoma_asimetrico"]`

```json
{"receta_id":"F-06","paciente":{"edad":65,"ocupacion":"jubilado","motivo_consulta":"perdida de vision lateral"},"clinica":{"reflejos_pupilares":"Marcus Gunn: DPAR en OD","fondo_de_ojo":"Excavacion c/d 0.8 en OD con asimetria c/d marcada."}}
```

### CASO F-07
**Complejidad:** compleja · **Objetivo:** papila edematosa (variante urgente).
**Correlaciones esperadas:** `["papila_patologica"]`

```json
{"receta_id":"F-07","paciente":{"edad":33,"ocupacion":"empleado","motivo_consulta":"cefalea intensa y vision borrosa"},"clinica":{"fondo_de_ojo":"Edema de papila bilateral con borramiento de bordes."}}
```

### CASO F-08
**Complejidad:** rutina · **Objetivo:** palidez / atrofia óptica (variante base).
**Correlaciones esperadas:** `["papila_patologica"]`

```json
{"receta_id":"F-08","paciente":{"edad":48,"ocupacion":"empleado","motivo_consulta":"perdida de vision progresiva OI"},"clinica":{"fondo_de_ojo":"Palidez papilar en OI, atrofia optica."}}
```

### CASO F-09
**Complejidad:** rutina · **Objetivo:** DMAE — drusas.
**Correlaciones esperadas:** `["fondo_macular_dmae"]`

```json
{"receta_id":"F-09","paciente":{"edad":72,"ocupacion":"jubilado","motivo_consulta":"ve las lineas torcidas"},"clinica":{"fondo_de_ojo":"Drusas maculares blandas confluentes en ambos ojos."}}
```

### CASO F-10
**Complejidad:** rutina · **Objetivo:** macular otros — membrana epirretiniana.
**Correlaciones esperadas:** `["fondo_macular_otros"]`

```json
{"receta_id":"F-10","paciente":{"edad":66,"ocupacion":"jubilado","motivo_consulta":"distorsion central OD"},"clinica":{"fondo_de_ojo":"Membrana epirretiniana con pucker macular en OD."}}
```

### CASO F-11
**Complejidad:** rutina · **Objetivo:** retinopatía hipertensiva.
**Correlaciones esperadas:** `["fondo_hipertensivo"]`

```json
{"receta_id":"F-11","paciente":{"edad":57,"ocupacion":"empleado","motivo_consulta":"control, hipertenso"},"clinica":{"fondo_de_ojo":"Cruces arteriovenosos patologicos, estrechamiento arteriolar y hemorragia en llama en OD."}}
```

### CASO F-12
**Complejidad:** rutina · **Objetivo:** retinopatía diabética.
**Correlaciones esperadas:** `["fondo_vascular_diabetico"]`

```json
{"receta_id":"F-12","paciente":{"edad":54,"ocupacion":"empleado","motivo_consulta":"diabetico, control anual"},"clinica":{"fondo_de_ojo":"Microaneurismas y exudados duros en polo posterior, hemorragias puntiformes."}}
```

### CASO F-13
**Complejidad:** compleja · **Objetivo:** diabético + hipertensivo coexisten (comorbilidad, sin supresión).
**Correlaciones esperadas:** `["fondo_hipertensivo","fondo_vascular_diabetico"]`

```json
{"receta_id":"F-13","paciente":{"edad":63,"ocupacion":"empleado","motivo_consulta":"diabetico e hipertenso"},"clinica":{"fondo_de_ojo":"Microaneurismas y exudados duros; ademas cruces arteriovenosos y hemorragia en llama."}}
```

### CASO F-14
**Complejidad:** compleja · **Objetivo:** periférico suprime a diabético (jerarquía).
**Correlaciones esperadas:** `["fondo_periferico_riesgo"]`

```json
{"receta_id":"F-14","paciente":{"edad":58,"ocupacion":"empleado","motivo_consulta":"diabetico con destellos"},"clinica":{"fondo_de_ojo":"Desgarro retiniano temporal; microaneurismas y exudados en polo posterior."}}
```

### CASO F-15
**Complejidad:** compleja · **Objetivo:** ventana de negación por oración (sin desgarros / lattice sí).
**Correlaciones esperadas:** `["fondo_periferico_riesgo"]`

```json
{"receta_id":"F-15","paciente":{"edad":45,"ocupacion":"empleado","motivo_consulta":"revision de fondo"},"clinica":{"fondo_de_ojo":"Fondo sin desgarros ni hemorragias. Lattice en periferia nasal de OI."}}
```

### CASO F-16
**Complejidad:** rutina · **Objetivo:** negación total → sin falsos positivos.
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"F-16","paciente":{"edad":50,"ocupacion":"empleado","motivo_consulta":"chequeo"},"clinica":{"fondo_de_ojo":"Sin lesiones perifericas, sin excavacion aumentada, macula sin drusas, sin microaneurismas."}}
```

### CASO F-17
**Complejidad:** compleja · **Objetivo:** glaucomatoso + papila coexisten (neuropatías distintas).
**Correlaciones esperadas:** `["papila_patologica","fondo_glaucomatoso"]`

```json
{"receta_id":"F-17","paciente":{"edad":61,"ocupacion":"jubilado","motivo_consulta":"control de nervio optico"},"clinica":{"fondo_de_ojo":"Excavacion c/d 0.8 con atrofia optica en OI."}}
```

## Bloque 4 — AKR vs Rx + córnea/queratometría

### CASO A-01
**Complejidad:** compleja · **Objetivo:** espasmo acomodativo (joven + pantallas + AR más miope).
**Correlaciones esperadas:** `["ar_rx_espasmo_acomodativo"]`

```json
{"receta_id":"A-01","paciente":{"edad":24,"ocupacion":"estudiante","motivo_consulta":"vision fluctuante"},"refraccion":{"od":{"esfera":-0.75,"cilindro":0.0},"oi":{"esfera":-0.75,"cilindro":0.0}},"akr":{"od":{"esfera":-1.50,"cilindro":0.0},"oi":{"esfera":-1.50,"cilindro":0.0}},"clinica":{"uso_pantallas":"gt6"},"tipo_lente":"monofocal"}
```

### CASO A-02
**Complejidad:** compleja · **Objetivo:** cambio de índice del cristalino (≥55, discrepancia >1 D, sin córnea irregular).
**Correlaciones esperadas:** `["ar_rx_cambio_cristalino"]`

```json
{"receta_id":"A-02","paciente":{"edad":62,"ocupacion":"jubilado","motivo_consulta":"lee mejor sin lentes ultimamente"},"refraccion":{"od":{"esfera":-2.00,"cilindro":0.0},"oi":{"esfera":-2.00,"cilindro":0.0}},"akr":{"od":{"esfera":-3.50,"cilindro":0.0},"oi":{"esfera":-3.50,"cilindro":0.0}},"tipo_lente":"monofocal"}
```

### CASO A-03
**Complejidad:** compleja · **Objetivo:** variabilidad inespecífica (≥1.50 D, sin patrón etario).
**Correlaciones esperadas:** `["ar_rx_variabilidad_inespecifica"]`

```json
{"receta_id":"A-03","paciente":{"edad":47,"ocupacion":"empleado","motivo_consulta":"revision"},"refraccion":{"od":{"esfera":-2.00,"cilindro":0.0},"oi":{"esfera":-2.00,"cilindro":0.0}},"akr":{"od":{"esfera":-3.75,"cilindro":0.0},"oi":{"esfera":-2.00,"cilindro":0.0}},"tipo_lente":"monofocal"}
```

### CASO A-04
**Complejidad:** rutina · **Objetivo:** AR detecta astigmatismo no prescrito (sin queratometría).
**Correlaciones esperadas:** `["ar_detecta_astigmatismo_no_prescrito"]`

```json
{"receta_id":"A-04","paciente":{"edad":35,"ocupacion":"empleado","motivo_consulta":"revision"},"refraccion":{"od":{"esfera":-1.00,"cilindro":0.0},"oi":{"esfera":-1.00,"cilindro":0.0}},"akr":{"od":{"esfera":-1.00,"cilindro":-1.00},"oi":{"esfera":-1.00,"cilindro":0.0}},"tipo_lente":"monofocal"}
```

### CASO A-05
**Complejidad:** compleja · **Objetivo:** AR-astigmatismo SOPORTADO por queratometría (cil corneal ≥0.75).
**Correlaciones esperadas:** `["ar_detecta_astigmatismo_no_prescrito"]`

```json
{"receta_id":"A-05","paciente":{"edad":40,"ocupacion":"empleado","motivo_consulta":"revision"},"refraccion":{"od":{"esfera":-1.00,"cilindro":0.0},"oi":{"esfera":-1.00,"cilindro":0.0}},"akr":{"od":{"esfera":-1.00,"cilindro":-1.25,"k1_d":44.00,"k2_d":45.50,"k_cilindro":-1.50},"oi":{"esfera":-1.00,"cilindro":0.0}},"tipo_lente":"monofocal"}
```

### CASO A-06
**Complejidad:** compleja · **Objetivo:** AR-astigmatismo NO soportado por queratometría → NO dispara (gate corneal).
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"A-06","paciente":{"edad":35,"ocupacion":"empleado","motivo_consulta":"revision"},"refraccion":{"od":{"esfera":-1.00,"cilindro":0.0},"oi":{"esfera":-1.00,"cilindro":0.0}},"akr":{"od":{"esfera":-1.00,"cilindro":-1.00,"k1_d":43.00,"k2_d":43.50,"k_cilindro":-0.25},"oi":{"esfera":-1.00,"cilindro":0.0}},"tipo_lente":"monofocal"}
```

### CASO A-07
**Complejidad:** compleja · **Objetivo:** queratocono/ectasia (Kmax ≥48.70) aislado.
**Correlaciones esperadas:** `["queratocono_ectasia_sospecha"]`

```json
{"receta_id":"A-07","paciente":{"edad":30,"ocupacion":"empleado","motivo_consulta":"cambio frecuente de graduacion"},"refraccion":{"od":{"esfera":-2.00,"cilindro":0.0,"av_cc":"20/25"},"oi":{"esfera":-2.00,"cilindro":0.0,"av_cc":"20/25"}},"akr":{"od":{"k1_d":49.00,"k2_d":46.00},"oi":{"k1_d":44.00,"k2_d":44.50}},"tipo_lente":"monofocal"}
```

### CASO A-08
**Complejidad:** compleja · **Objetivo:** queratocono por cilindro corneal muy alto (≥4 D) + AV + discrepancia corneal/refractiva.
**Correlaciones esperadas:** `["av_cc_limitada","queratocono_ectasia_sospecha","astigmatismo_corneal_vs_refractivo"]`

```json
{"receta_id":"A-08","paciente":{"edad":26,"ocupacion":"empleado","motivo_consulta":"vision distorsionada OD"},"refraccion":{"od":{"esfera":-1.00,"cilindro":-1.00,"eje":90,"av_cc":"20/30"},"oi":{"esfera":-1.00,"cilindro":0.0,"av_cc":"20/20"}},"akr":{"od":{"k1_d":45.00,"k2_d":46.00,"k_cilindro":-4.50},"oi":{"k1_d":44.00,"k2_d":44.50}},"tipo_lente":"monofocal"}
```

### CASO A-09
**Complejidad:** compleja · **Objetivo:** astigmatismo corneal vs refractivo por MAGNITUD (lenticular) aislado.
**Correlaciones esperadas:** `["astigmatismo_corneal_vs_refractivo"]`

```json
{"receta_id":"A-09","paciente":{"edad":40,"ocupacion":"empleado","motivo_consulta":"revision"},"refraccion":{"od":{"esfera":-0.75,"cilindro":-0.75,"eje":90,"av_cc":"20/20"},"oi":{"esfera":-0.75,"cilindro":0.0,"av_cc":"20/20"}},"akr":{"od":{"k1_d":44.00,"k2_d":47.00,"k_cilindro":-3.00},"oi":{"k1_d":43.50,"k2_d":44.00}},"tipo_lente":"monofocal"}
```

### CASO A-10
**Complejidad:** compleja · **Objetivo:** astigmatismo corneal vs refractivo por EJE (Δeje ≥15°).
**Correlaciones esperadas:** `["astigmatismo_corneal_vs_refractivo"]`

```json
{"receta_id":"A-10","paciente":{"edad":38,"ocupacion":"empleado","motivo_consulta":"revision"},"refraccion":{"od":{"esfera":-2.00,"cilindro":-1.50,"eje":90,"av_cc":"20/25"},"oi":{"esfera":-2.00,"cilindro":0.0,"av_cc":"20/20"}},"akr":{"od":{"k1_d":44.00,"k2_d":45.50,"k_cilindro":-1.50,"k_cilindro_eje":20},"oi":{"k1_d":43.50,"k2_d":44.00}},"tipo_lente":"monofocal"}
```

### CASO A-11
**Complejidad:** compleja · **Objetivo:** espasmo bloqueado por falta de pantallas → variabilidad.
**Correlaciones esperadas:** `["ar_rx_variabilidad_inespecifica"]`

```json
{"receta_id":"A-11","paciente":{"edad":25,"ocupacion":"empleado","motivo_consulta":"revision"},"refraccion":{"od":{"esfera":-2.00,"cilindro":0.0},"oi":{"esfera":-2.00,"cilindro":0.0}},"akr":{"od":{"esfera":-3.75,"cilindro":0.0},"oi":{"esfera":-2.00,"cilindro":0.0}},"clinica":{"uso_pantallas":"lt2"},"tipo_lente":"monofocal"}
```

### CASO A-12
**Complejidad:** compleja · **Objetivo:** córnea irregular reencamina cambio_cristalino → variabilidad + queratocono.
**Correlaciones esperadas:** `["ar_rx_variabilidad_inespecifica","queratocono_ectasia_sospecha"]`

```json
{"receta_id":"A-12","paciente":{"edad":60,"ocupacion":"jubilado","motivo_consulta":"vision cambiante"},"refraccion":{"od":{"esfera":-2.00,"cilindro":0.0},"oi":{"esfera":-2.00,"cilindro":0.0}},"akr":{"od":{"esfera":-3.75,"cilindro":0.0,"k1_d":49.00,"k2_d":46.00},"oi":{"esfera":-2.00,"cilindro":0.0}},"tipo_lente":"monofocal"}
```

### CASO A-13
**Complejidad:** rutina · **Objetivo:** AR ≈ Rx (sin discrepancia) → nada.
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"A-13","paciente":{"edad":50,"ocupacion":"empleado","motivo_consulta":"revision"},"refraccion":{"od":{"esfera":-2.00,"cilindro":-0.50,"eje":90,"av_cc":"20/20"},"oi":{"esfera":-2.00,"cilindro":-0.50,"eje":90,"av_cc":"20/20"}},"akr":{"od":{"esfera":-2.00,"cilindro":-0.50,"k1_d":43.00,"k2_d":43.75},"oi":{"esfera":-2.00,"cilindro":-0.50,"k1_d":43.00,"k2_d":43.75}},"tipo_lente":"monofocal"}
```

## Bloque 5 — Anexos, cristalino, pupilas, motilidad, campos, Amsler

### CASO S-01
**Complejidad:** rutina · **Objetivo:** anexos — pterigión (coloquial "carnosidad").
**Correlaciones esperadas:** `["anexos_patologicos"]`

```json
{"receta_id":"S-01","paciente":{"edad":45,"ocupacion":"agricultor","motivo_consulta":"carnosidad en el ojo"},"clinica":{"anexos_oculares":"Pterigion nasal grado II en OD (carnosidad)."}}
```

### CASO S-02
**Complejidad:** rutina · **Objetivo:** anexos — blefaritis / DGM.
**Correlaciones esperadas:** `["anexos_patologicos"]`

```json
{"receta_id":"S-02","paciente":{"edad":50,"ocupacion":"empleado","motivo_consulta":"parpados irritados"},"clinica":{"anexos_oculares":"Blefaritis anterior con disfuncion de glandulas de meibomio."}}
```

### CASO S-03
**Complejidad:** rutina · **Objetivo:** anexos — orzuelo (coloquial "perrilla").
**Correlaciones esperadas:** `["anexos_patologicos"]`

```json
{"receta_id":"S-03","paciente":{"edad":28,"ocupacion":"empleado","motivo_consulta":"bolita en el parpado"},"clinica":{"anexos_oculares":"Perrilla en parpado superior de OI."}}
```

### CASO S-04
**Complejidad:** rutina · **Objetivo:** opacidad cristaliniana — catarata (campo anexos).
**Correlaciones esperadas:** `["opacidad_cristaliniana"]`

```json
{"receta_id":"S-04","paciente":{"edad":70,"ocupacion":"jubilado","motivo_consulta":"vision nublada"},"clinica":{"anexos_oculares":"Catarata nuclear grado 2 en ambos ojos."}}
```

### CASO S-05
**Complejidad:** rutina · **Objetivo:** pseudofaquia (IOL) leída desde fondo.
**Correlaciones esperadas:** `["opacidad_cristaliniana"]`

```json
{"receta_id":"S-05","paciente":{"edad":74,"ocupacion":"jubilado","motivo_consulta":"control post operado"},"clinica":{"fondo_de_ojo":"Pseudofaquia en OD, lente intraocular centrado, retina aplicada."}}
```

### CASO S-06
**Complejidad:** compleja · **Objetivo:** catarata + AV limitada; screening suprimido por causa orgánica.
**Correlaciones esperadas:** `["opacidad_cristaliniana","av_cc_limitada","presbicia_sin_adicion"]`

```json
{"receta_id":"S-06","paciente":{"edad":70,"ocupacion":"jubilado","motivo_consulta":"ve muy nublado"},"refraccion":{"od":{"esfera":-1.00,"cilindro":0.0,"av_cc":"20/80"},"oi":{"esfera":-1.00,"cilindro":0.0,"av_cc":"20/60"}},"clinica":{"anexos_oculares":"Catarata nuclear avanzada bilateral."},"tipo_lente":"monofocal"}
```

### CASO S-07
**Complejidad:** rutina · **Objetivo:** pupilas — anisocoria patológica (en nota libre).
**Correlaciones esperadas:** `["pupilas_alteradas"]`

```json
{"receta_id":"S-07","paciente":{"edad":40,"ocupacion":"empleado","motivo_consulta":"una pupila mas grande"},"clinica":{"reflejos_pupilares":"Reflejo fotomotor, consesual, acomodativo: anisocoria de 2 mm mayor en OD"}}
```

### CASO S-08
**Complejidad:** compleja · **Objetivo:** DPAR (Marcus Gunn) urgente SIN fondo glaucomatoso → pupilas_alteradas.
**Correlaciones esperadas:** `["pupilas_alteradas"]`

```json
{"receta_id":"S-08","paciente":{"edad":38,"ocupacion":"empleado","motivo_consulta":"perdida de vision subita OI"},"clinica":{"reflejos_pupilares":"Marcus Gunn: DPAR positivo en OI"}}
```

### CASO S-09
**Complejidad:** rutina · **Objetivo:** anisocoria fisiológica → NO dispara (exclusión benigna).
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"S-09","paciente":{"edad":30,"ocupacion":"empleado","motivo_consulta":"revision"},"clinica":{"reflejos_pupilares":"Reflejo fotomotor, consesual, acomodativo: anisocoria fisiologica de 1 mm"}}
```

### CASO S-10
**Complejidad:** rutina · **Objetivo:** midriasis farmacológica → NO dispara (examen bajo dilatación).
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"S-10","paciente":{"edad":55,"ocupacion":"empleado","motivo_consulta":"fondo de ojo dilatado"},"clinica":{"reflejos_pupilares":"Reflejo fotomotor, consesual, acomodativo: midriasis por tropicamida, examen bajo dilatacion"}}
```

### CASO S-11
**Complejidad:** rutina · **Objetivo:** motilidad — limitación de ducción.
**Correlaciones esperadas:** `["motilidad_alterada"]`

```json
{"receta_id":"S-11","paciente":{"edad":52,"ocupacion":"empleado","motivo_consulta":"vision doble al mirar de lado"},"clinica":{"motilidad_ocular":"Versiones: limitacion de la abduccion en OD. Ducciones: normales. Sacadicos: normales. Seguimiento: normal."}}
```

### CASO S-12
**Complejidad:** rutina · **Objetivo:** motilidad — nistagmo.
**Correlaciones esperadas:** `["motilidad_alterada"]`

```json
{"receta_id":"S-12","paciente":{"edad":18,"ocupacion":"estudiante","motivo_consulta":"le tiemblan los ojos"},"clinica":{"motilidad_ocular":"Versiones: nistagmo horizontal en posicion primaria. Ducciones: normales."}}
```

### CASO S-13
**Complejidad:** rutina · **Objetivo:** campos — escotoma por confrontación.
**Correlaciones esperadas:** `["campos_visuales_alterados"]`

```json
{"receta_id":"S-13","paciente":{"edad":60,"ocupacion":"empleado","motivo_consulta":"mancha en el campo visual"},"clinica":{"confrontacion_campos_visuales":"Escotoma en cuadrante superior de OI por confrontacion."}}
```

### CASO S-14
**Complejidad:** compleja · **Objetivo:** campos — hemianopsia.
**Correlaciones esperadas:** `["campos_visuales_alterados"]`

```json
{"receta_id":"S-14","paciente":{"edad":66,"ocupacion":"jubilado","motivo_consulta":"no ve un lado"},"clinica":{"confrontacion_campos_visuales":"Hemianopsia homonima derecha por confrontacion."}}
```

### CASO S-15
**Complejidad:** rutina · **Objetivo:** texto default de campos → NO dispara.
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"S-15","paciente":{"edad":40,"ocupacion":"empleado","motivo_consulta":"revision"},"clinica":{"confrontacion_campos_visuales":"Sin defectos perifericos evidentes."}}
```

### CASO S-16
**Complejidad:** rutina · **Objetivo:** Amsler — metamorfopsia.
**Correlaciones esperadas:** `["amsler_alterado"]`

```json
{"receta_id":"S-16","paciente":{"edad":68,"ocupacion":"jubilado","motivo_consulta":"lineas onduladas"},"clinica":{"grid_de_amsler":"Metamorfopsia central en OI."}}
```

### CASO S-17
**Complejidad:** rutina · **Objetivo:** texto default de Amsler → NO dispara.
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"S-17","paciente":{"edad":50,"ocupacion":"empleado","motivo_consulta":"revision"},"clinica":{"grid_de_amsler":"Sin descendencia de patologia aparente."}}
```

### CASO S-18
**Complejidad:** compleja · **Objetivo:** normalidad parcial NO suprime hallazgo (por oración).
**Correlaciones esperadas:** `["campos_visuales_alterados"]`

```json
{"receta_id":"S-18","paciente":{"edad":58,"ocupacion":"empleado","motivo_consulta":"mancha central"},"clinica":{"confrontacion_campos_visuales":"Escotoma central en OD, resto del campo normal."}}
```

## Bloque 6 — Binocularidad y convergencia

### CASO B-01
**Complejidad:** rutina · **Objetivo:** PPC alejado en joven (>6 cm) → ppc_exoforia.
**Correlaciones esperadas:** `["ppc_exoforia"]`

```json
{"receta_id":"B-01","paciente":{"edad":25,"ocupacion":"empleado","motivo_consulta":"chequeo"},"clinica":{"cover_test":"OD: Orto | OI: Orto","ppc_cm":9}}
```

### CASO B-02
**Complejidad:** rutina · **Objetivo:** exoforia clasificada sin síntomas → ppc_exoforia.
**Correlaciones esperadas:** `["ppc_exoforia"]`

```json
{"receta_id":"B-02","paciente":{"edad":30,"ocupacion":"empleado","motivo_consulta":"chequeo"},"clinica":{"cover_test":"OD: Exo y Foria | OI: Exo y Foria","ppc_cm":5}}
```

### CASO B-03
**Complejidad:** compleja · **Objetivo:** Exo sin clasificar (sub opcional) → ppc_exoforia (no clasificada).
**Correlaciones esperadas:** `["ppc_exoforia"]`

```json
{"receta_id":"B-03","paciente":{"edad":35,"ocupacion":"empleado","motivo_consulta":"revision"},"clinica":{"cover_test":"OD: Exo | OI: Orto","ppc_cm":4}}
```

### CASO B-04
**Complejidad:** compleja · **Objetivo:** exoforia sintomática (síntoma binocular) sin insuf. convergencia.
**Correlaciones esperadas:** `["ppc_exoforia","cover_exoforia_sintomatica"]`

```json
{"receta_id":"B-04","paciente":{"edad":28,"ocupacion":"empleado","motivo_consulta":"cefalea y vista cansada al leer"},"clinica":{"cover_test":"OD: Exo y Foria | OI: Exo y Foria","ppc_cm":5}}
```

### CASO B-05
**Complejidad:** compleja · **Objetivo:** insuficiencia de convergencia (compuesta) suprime ppc_exoforia y cover_exoforia.
**Correlaciones esperadas:** `["insuficiencia_convergencia"]`

```json
{"receta_id":"B-05","paciente":{"edad":22,"ocupacion":"estudiante","motivo_consulta":"cefalea al leer y vista cansada"},"clinica":{"cover_test":"OD: Exo y Foria | OI: Exo y Foria","ppc_cm":10}}
```

### CASO B-06
**Complejidad:** compleja · **Objetivo:** endoforia sintomática → cover_endoforia_sintomatica.
**Correlaciones esperadas:** `["cover_endoforia_sintomatica"]`

```json
{"receta_id":"B-06","paciente":{"edad":30,"ocupacion":"empleado","motivo_consulta":"diplopia y cefalea"},"clinica":{"cover_test":"OD: Endo y Foria | OI: Endo y Foria"}}
```

### CASO B-07
**Complejidad:** compleja · **Objetivo:** Endo sin clasificar + síntoma → cover_endoforia_sintomatica (no clasificada).
**Correlaciones esperadas:** `["cover_endoforia_sintomatica"]`

```json
{"receta_id":"B-07","paciente":{"edad":33,"ocupacion":"empleado","motivo_consulta":"vista cansada al enfocar"},"clinica":{"cover_test":"OD: Endo | OI: Orto"}}
```

### CASO B-08
**Complejidad:** rutina · **Objetivo:** desviación vertical — hiperforia (foria).
**Correlaciones esperadas:** `["desviacion_vertical"]`

```json
{"receta_id":"B-08","paciente":{"edad":40,"ocupacion":"empleado","motivo_consulta":"chequeo"},"clinica":{"cover_test":"OD: Hiper y Foria | OI: Orto"}}
```

### CASO B-09
**Complejidad:** compleja · **Objetivo:** desviación vertical — hipertropia (tropía manifiesta).
**Correlaciones esperadas:** `["desviacion_vertical"]`

```json
{"receta_id":"B-09","paciente":{"edad":35,"ocupacion":"empleado","motivo_consulta":"vision doble vertical"},"clinica":{"cover_test":"OD: Hiper y Tropia | OI: Orto"}}
```

### CASO B-10
**Complejidad:** compleja · **Objetivo:** Hiper sin clasificar → desviación vertical (no clasificada).
**Correlaciones esperadas:** `["desviacion_vertical"]`

```json
{"receta_id":"B-10","paciente":{"edad":45,"ocupacion":"empleado","motivo_consulta":"molestia"},"clinica":{"cover_test":"OD: Hiper | OI: Orto"}}
```

### CASO B-11
**Complejidad:** compleja · **Objetivo:** endotropia + lente → endotropia_lente.
**Correlaciones esperadas:** `["endotropia_lente"]`

```json
{"receta_id":"B-11","paciente":{"edad":30,"ocupacion":"empleado","motivo_consulta":"desviacion del ojo"},"clinica":{"cover_test":"OD: Endo y Tropia | OI: Orto"},"tipo_lente":"progresivo"}
```

### CASO B-12
**Complejidad:** compleja · **Objetivo:** exotropia + lente → exotropia_lente.
**Correlaciones esperadas:** `["exotropia_lente"]`

```json
{"receta_id":"B-12","paciente":{"edad":30,"ocupacion":"empleado","motivo_consulta":"ojo se va hacia afuera"},"clinica":{"cover_test":"OD: Exo y Tropia | OI: Orto"},"tipo_lente":"monofocal"}
```

### CASO B-13
**Complejidad:** rutina · **Objetivo:** cover Orto + PPC normal → nada.
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"B-13","paciente":{"edad":30,"ocupacion":"empleado","motivo_consulta":"chequeo"},"clinica":{"cover_test":"OD: Orto | OI: Orto","ppc_cm":5}}
```

### CASO B-14
**Complejidad:** compleja · **Objetivo:** insuf. convergencia con demanda desde la OCUPACIÓN (motivo genérico).
**Correlaciones esperadas:** `["insuficiencia_convergencia"]`

```json
{"receta_id":"B-14","paciente":{"edad":35,"ocupacion":"programador","motivo_consulta":"molestias inespecificas"},"clinica":{"cover_test":"OD: Exo y Foria | OI: Exo y Foria","ppc_cm":8}}
```

### CASO B-15
**Complejidad:** compleja · **Objetivo:** PPC alejado en présbita (umbral >10 cm) → ppc_exoforia.
**Correlaciones esperadas:** `["ppc_exoforia"]`

```json
{"receta_id":"B-15","paciente":{"edad":55,"ocupacion":"empleado","motivo_consulta":"cansancio al leer"},"clinica":{"cover_test":"OD: Orto | OI: Orto","ppc_cm":11}}
```

### CASO B-16
**Complejidad:** rutina · **Objetivo:** PPC 8 cm en présbita NO dispara (umbral edad).
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"B-16","paciente":{"edad":55,"ocupacion":"empleado","motivo_consulta":"revision"},"clinica":{"cover_test":"OD: Orto | OI: Orto","ppc_cm":8}}
```

## Bloque 7 — Superficie ocular (BUT)

### CASO C-01
**Complejidad:** rutina · **Objetivo:** BUT crítico (<5 s).
**Correlaciones esperadas:** `["but_critico"]`

```json
{"receta_id":"C-01","paciente":{"edad":45,"ocupacion":"empleado","motivo_consulta":"ardor y sensacion de arena"},"clinica":{"ojo_seco_but_seg":3}}
```

### CASO C-02
**Complejidad:** rutina · **Objetivo:** BUT crítico borde (4 s).
**Correlaciones esperadas:** `["but_critico"]`

```json
{"receta_id":"C-02","paciente":{"edad":50,"ocupacion":"empleado","motivo_consulta":"ojo seco"},"clinica":{"ojo_seco_but_seg":4}}
```

### CASO C-03
**Complejidad:** compleja · **Objetivo:** BUT reducido con pantallas (5–9 s + gt6).
**Correlaciones esperadas:** `["but_pantallas"]`

```json
{"receta_id":"C-03","paciente":{"edad":30,"ocupacion":"oficinista","motivo_consulta":"molestia al final del dia"},"clinica":{"uso_pantallas":"gt6","ojo_seco_but_seg":7}}
```

### CASO C-04
**Complejidad:** rutina · **Objetivo:** BUT limítrofe sin pantallas (lt2).
**Correlaciones esperadas:** `["but_limitrofe"]`

```json
{"receta_id":"C-04","paciente":{"edad":35,"ocupacion":"empleado","motivo_consulta":"revision"},"clinica":{"uso_pantallas":"lt2","ojo_seco_but_seg":7}}
```

### CASO C-05
**Complejidad:** rutina · **Objetivo:** BUT limítrofe sin dato de pantallas (null).
**Correlaciones esperadas:** `["but_limitrofe"]`

```json
{"receta_id":"C-05","paciente":{"edad":40,"ocupacion":"empleado","motivo_consulta":"revision"},"clinica":{"ojo_seco_but_seg":8}}
```

### CASO C-06
**Complejidad:** rutina · **Objetivo:** BUT normal (12 s) → nada aunque haya pantallas.
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"C-06","paciente":{"edad":30,"ocupacion":"oficinista","motivo_consulta":"chequeo"},"clinica":{"uso_pantallas":"gt6","ojo_seco_but_seg":12}}
```

### CASO C-07
**Complejidad:** rutina · **Objetivo:** BUT 5 s (borde inferior de la banda) + pantallas → but_pantallas.
**Correlaciones esperadas:** `["but_pantallas"]`

```json
{"receta_id":"C-07","paciente":{"edad":33,"ocupacion":"capturista","motivo_consulta":"molestia ocular"},"clinica":{"uso_pantallas":"btw2_6","ojo_seco_but_seg":5}}
```

## Bloque 8 — Edad, lente, pantallas, presbicia, screening

### CASO E-01
**Complejidad:** rutina · **Objetivo:** presbicia multifocal por edad + adición (monofocal con add).
**Correlaciones esperadas:** `["presbicia_multifocal"]`

```json
{"receta_id":"E-01","paciente":{"edad":50,"ocupacion":"empleado","motivo_consulta":"no ve de cerca"},"refraccion":{"od":{"esfera":0.50,"cilindro":0.0,"add":1.75,"av_cc":"20/20"},"oi":{"esfera":0.50,"cilindro":0.0,"add":1.75,"av_cc":"20/20"}},"tipo_lente":"monofocal"}
```

### CASO E-02
**Complejidad:** rutina · **Objetivo:** presbicia multifocal por lente (progresivo) sin add.
**Correlaciones esperadas:** `["presbicia_multifocal"]`

```json
{"receta_id":"E-02","paciente":{"edad":44,"ocupacion":"empleado","motivo_consulta":"quiere progresivos"},"refraccion":{"od":{"esfera":0.75,"cilindro":0.0,"av_cc":"20/20"},"oi":{"esfera":0.75,"cilindro":0.0,"av_cc":"20/20"}},"tipo_lente":"progresivo"}
```

### CASO E-03
**Complejidad:** rutina · **Objetivo:** presbicia sin adición (recordatorio, hipermétrope).
**Correlaciones esperadas:** `["presbicia_sin_adicion"]`

```json
{"receta_id":"E-03","paciente":{"edad":47,"ocupacion":"empleado","motivo_consulta":"revision"},"refraccion":{"od":{"esfera":0.50,"cilindro":0.0,"av_cc":"20/20"},"oi":{"esfera":0.75,"cilindro":0.0,"av_cc":"20/20"}},"tipo_lente":"monofocal"}
```

### CASO E-04
**Complejidad:** compleja · **Objetivo:** miope funcional 50 años sin add NO dispara.
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"E-04","paciente":{"edad":50,"ocupacion":"empleado","motivo_consulta":"lee bien sin lentes"},"refraccion":{"od":{"esfera":-2.50,"cilindro":0.0,"av_cc":"20/20"},"oi":{"esfera":-2.00,"cilindro":0.0,"av_cc":"20/20"}},"tipo_lente":"monofocal"}
```

### CASO E-05
**Complejidad:** compleja · **Objetivo:** adición en no présbita (edad <40 con add ≥0.75).
**Correlaciones esperadas:** `["adicion_incongruente_edad"]`

```json
{"receta_id":"E-05","paciente":{"edad":28,"ocupacion":"empleado","motivo_consulta":"fatiga al leer"},"refraccion":{"od":{"esfera":-1.00,"cilindro":0.0,"add":1.00,"av_cc":"20/20"},"oi":{"esfera":-1.00,"cilindro":0.0,"add":1.00,"av_cc":"20/20"}},"tipo_lente":"monofocal"}
```

### CASO E-06
**Complejidad:** compleja · **Objetivo:** sobre-adición para la edad (coexiste con presbicia multifocal).
**Correlaciones esperadas:** `["presbicia_multifocal","adicion_incongruente_edad"]`

```json
{"receta_id":"E-06","paciente":{"edad":50,"ocupacion":"empleado","motivo_consulta":"no ve de cerca"},"refraccion":{"od":{"esfera":1.00,"cilindro":0.0,"add":3.50,"av_cc":"20/20"},"oi":{"esfera":1.00,"cilindro":0.0,"add":3.50,"av_cc":"20/20"}},"tipo_lente":"progresivo"}
```

### CASO E-07
**Complejidad:** compleja · **Objetivo:** add sobre techo absoluto sin edad (edad null).
**Correlaciones esperadas:** `["adicion_incongruente_edad"]`

```json
{"receta_id":"E-07","paciente":{"ocupacion":"empleado","motivo_consulta":"lentes de cerca"},"refraccion":{"od":{"esfera":1.00,"cilindro":0.0,"add":3.50,"av_cc":"20/20"},"oi":{"esfera":1.00,"cilindro":0.0,"av_cc":"20/20"}},"tipo_lente":"monofocal"}
```

### CASO E-08
**Complejidad:** compleja · **Objetivo:** CVS (pantallas + ardor).
**Correlaciones esperadas:** `["cvs_sospecha"]`

```json
{"receta_id":"E-08","paciente":{"edad":32,"ocupacion":"oficinista","motivo_consulta":"ardor ocular y vision borrosa al final del dia"},"clinica":{"uso_pantallas":"gt6"}}
```

### CASO E-09
**Complejidad:** compleja · **Objetivo:** CVS + BUT pantallas combinados.
**Correlaciones esperadas:** `["cvs_sospecha","but_pantallas"]`

```json
{"receta_id":"E-09","paciente":{"edad":35,"ocupacion":"oficinista","motivo_consulta":"resequedad y ardor ocular"},"clinica":{"uso_pantallas":"gt6","ojo_seco_but_seg":6}}
```

### CASO E-10
**Complejidad:** compleja · **Objetivo:** screening del adulto mayor con présbita multifocal + AV.
**Correlaciones esperadas:** `["av_cc_limitada","presbicia_multifocal","adulto_mayor_screening"]`

```json
{"receta_id":"E-10","paciente":{"edad":72,"ocupacion":"jubilado","motivo_consulta":"ve borroso pese a lentes"},"refraccion":{"od":{"esfera":-0.75,"cilindro":0.0,"add":2.50,"av_cc":"20/50"},"oi":{"esfera":-0.75,"cilindro":0.0,"add":2.50,"av_cc":"20/40"}},"tipo_lente":"progresivo"}
```

### CASO E-11
**Complejidad:** compleja · **Objetivo:** screening SUPRIMIDO por causa (DMAE) → solo DMAE + AV + presbicia.
**Correlaciones esperadas:** `["fondo_macular_dmae","av_cc_limitada","presbicia_multifocal"]`

```json
{"receta_id":"E-11","paciente":{"edad":75,"ocupacion":"jubilado","motivo_consulta":"mancha central y distorsion"},"refraccion":{"od":{"esfera":-0.50,"cilindro":0.0,"add":2.50,"av_cc":"20/80"},"oi":{"esfera":-0.50,"cilindro":0.0,"add":2.50,"av_cc":"20/100"}},"clinica":{"fondo_de_ojo":"Drusas maculares y atrofia geografica en ambos ojos."},"tipo_lente":"progresivo"}
```

### CASO E-12
**Complejidad:** compleja · **Objetivo:** ambliopía por anisometropía (con AV s/c y c/c).
**Correlaciones esperadas:** `["anisometropia","av_cc_limitada","ambliopia_sospecha"]`

```json
{"receta_id":"E-12","paciente":{"edad":35,"ocupacion":"empleado","motivo_consulta":"un ojo nunca vio bien"},"refraccion":{"od":{"esfera":-1.00,"cilindro":0.0,"av_cc":"20/20"},"oi":{"esfera":-4.00,"cilindro":0.0,"av_cc":"20/60","av_sc":"20/200"}},"tipo_lente":"monofocal"}
```

### CASO E-13
**Complejidad:** compleja · **Objetivo:** ambliopía SUPRIMIDA por miopía magna (causa orgánica).
**Correlaciones esperadas:** `["miopia_magna","anisometropia","av_cc_limitada"]`

```json
{"receta_id":"E-13","paciente":{"edad":40,"ocupacion":"empleado","motivo_consulta":"vision muy baja OI"},"refraccion":{"od":{"esfera":-8.00,"cilindro":0.0,"av_cc":"20/20"},"oi":{"esfera":-12.00,"cilindro":0.0,"av_cc":"20/80"}},"tipo_lente":"monofocal"}
```

### CASO E-14
**Complejidad:** rutina · **Objetivo:** flat_top cuenta como multifocal → presbicia_multifocal.
**Correlaciones esperadas:** `["presbicia_multifocal"]`

```json
{"receta_id":"E-14","paciente":{"edad":46,"ocupacion":"empleado","motivo_consulta":"lentes bifocales"},"refraccion":{"od":{"esfera":1.00,"cilindro":0.0,"av_cc":"20/20"},"oi":{"esfera":1.00,"cilindro":0.0,"av_cc":"20/20"}},"tipo_lente":"flat_top"}
```

### CASO E-15
**Complejidad:** rutina · **Objetivo:** bifocal_blended (clave cruda) cuenta como multifocal.
**Correlaciones esperadas:** `["presbicia_multifocal"]`

```json
{"receta_id":"E-15","paciente":{"edad":48,"ocupacion":"empleado","motivo_consulta":"no ve de cerca"},"refraccion":{"od":{"esfera":1.00,"cilindro":0.0,"add":1.50,"av_cc":"20/20"},"oi":{"esfera":1.00,"cilindro":0.0,"add":1.50,"av_cc":"20/20"}},"tipo_lente":"bifocal_blended"}
```

### CASO E-16
**Complejidad:** rutina · **Objetivo:** CVS bloqueado sin pantallas suficientes (lt2).
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"E-16","paciente":{"edad":30,"ocupacion":"empleado","motivo_consulta":"ardor ocular"},"clinica":{"uso_pantallas":"lt2"}}
```

## Bloque 9 — Casos compuestos complejos

### CASO X-01
**Complejidad:** compleja · **Objetivo:** urgencia periférica + miopía magna + AV.
**Correlaciones esperadas:** `["fondo_periferico_riesgo","miopia_magna","av_cc_limitada"]`

```json
{"receta_id":"X-01","paciente":{"edad":55,"ocupacion":"empleado","motivo_consulta":"destellos y baja vision"},"refraccion":{"od":{"esfera":-12.00,"cilindro":0.0,"av_cc":"20/60"},"oi":{"esfera":-11.00,"cilindro":0.0,"av_cc":"20/50"}},"clinica":{"fondo_de_ojo":"Desgarro retiniano con lattice extenso en periferia temporal de OD."},"tipo_lente":"monofocal"}
```

### CASO X-02
**Complejidad:** compleja · **Objetivo:** glaucoma asimétrico + campos + motilidad (pupilas y fondo_glaucomatoso suprimidos).
**Correlaciones esperadas:** `["glaucoma_asimetrico","motilidad_alterada","campos_visuales_alterados"]`

```json
{"receta_id":"X-02","paciente":{"edad":65,"ocupacion":"jubilado","motivo_consulta":"perdida de campo y vision doble"},"refraccion":{"od":{"esfera":-2.00,"cilindro":0.0,"av_cc":"20/25"},"oi":{"esfera":-2.00,"cilindro":0.0,"av_cc":"20/25"}},"clinica":{"reflejos_pupilares":"Marcus Gunn: DPAR en OD","fondo_de_ojo":"Excavacion c/d 0.85 en OD con muesca inferior; asimetria c/d.","confrontacion_campos_visuales":"Escalon nasal en OD por confrontacion.","motilidad_ocular":"Versiones: limitacion leve de la elevacion en OD."},"tipo_lente":"monofocal"}
```

### CASO X-03
**Complejidad:** compleja · **Objetivo:** diabético + hipertensivo + catarata + AV + presbicia (screening suprimido).
**Correlaciones esperadas:** `["fondo_hipertensivo","fondo_vascular_diabetico","opacidad_cristaliniana","av_cc_limitada","presbicia_multifocal"]`

```json
{"receta_id":"X-03","paciente":{"edad":68,"ocupacion":"jubilado","motivo_consulta":"diabetico e hipertenso, ve mal"},"refraccion":{"od":{"esfera":-0.50,"cilindro":0.0,"add":2.50,"av_cc":"20/70"},"oi":{"esfera":-0.50,"cilindro":0.0,"add":2.50,"av_cc":"20/60"}},"clinica":{"fondo_de_ojo":"Microaneurismas, exudados duros y hemorragias puntiformes; cruces arteriovenosos y hemorragia en llama.","anexos_oculares":"Catarata nuclear bilateral."},"tipo_lente":"progresivo"}
```

### CASO X-04
**Complejidad:** compleja · **Objetivo:** insuf. convergencia + CVS + BUT pantallas (joven digital).
**Correlaciones esperadas:** `["insuficiencia_convergencia","cvs_sospecha","but_pantallas"]`

```json
{"receta_id":"X-04","paciente":{"edad":26,"ocupacion":"programador","motivo_consulta":"cefalea, ardor ocular y vista cansada al leer en computadora"},"refraccion":{"od":{"esfera":-1.50,"cilindro":-0.75,"eje":90,"av_cc":"20/20"},"oi":{"esfera":-1.50,"cilindro":-0.75,"eje":90,"av_cc":"20/20"}},"clinica":{"uso_pantallas":"gt6","ppc_cm":10,"cover_test":"OD: Exo y Foria | OI: Exo y Foria","ojo_seco_but_seg":6},"tipo_lente":"monofocal"}
```

### CASO X-05
**Complejidad:** compleja · **Objetivo:** espasmo acomodativo + CVS + BUT pantallas (joven).
**Correlaciones esperadas:** `["ar_rx_espasmo_acomodativo","cvs_sospecha","but_pantallas"]`

```json
{"receta_id":"X-05","paciente":{"edad":20,"ocupacion":"estudiante","motivo_consulta":"vision borrosa y fatiga visual con el celular"},"refraccion":{"od":{"esfera":-0.50,"cilindro":0.0,"av_cc":"20/20"},"oi":{"esfera":-0.50,"cilindro":0.0,"av_cc":"20/20"}},"akr":{"od":{"esfera":-1.25,"cilindro":0.0},"oi":{"esfera":-1.25,"cilindro":0.0}},"clinica":{"uso_pantallas":"gt6","ojo_seco_but_seg":8},"tipo_lente":"monofocal"}
```

### CASO X-06
**Complejidad:** compleja · **Objetivo:** pediátrico integral — hipermetropía alta + aniso + AV + endotropia lente + ambliopía.
**Correlaciones esperadas:** `["hipermetropia_alta","anisometropia","av_cc_limitada","endotropia_lente","ambliopia_sospecha"]`

```json
{"receta_id":"X-06","paciente":{"edad":5,"ocupacion":"preescolar","motivo_consulta":"ojo desviado hacia adentro"},"refraccion":{"od":{"esfera":6.00,"cilindro":0.0,"av_cc":"20/40"},"oi":{"esfera":3.00,"cilindro":0.0,"av_cc":"20/20"}},"clinica":{"cover_test":"OD: Endo y Tropia | OI: Orto"},"tipo_lente":"monofocal"}
```

### CASO X-07
**Complejidad:** compleja · **Objetivo:** miopía magna + aniso + AV + astig oblicuo + queratocono (ambliopía suprimida).
**Correlaciones esperadas:** `["miopia_magna","anisometropia","av_cc_limitada","astig_oblicuo","queratocono_ectasia_sospecha"]`

```json
{"receta_id":"X-07","paciente":{"edad":24,"ocupacion":"empleado","motivo_consulta":"vision muy distorsionada"},"refraccion":{"od":{"esfera":-7.00,"cilindro":-3.50,"eje":55,"av_cc":"20/50"},"oi":{"esfera":-6.50,"cilindro":-1.00,"eje":90,"av_cc":"20/30"}},"akr":{"od":{"k1_d":50.00,"k2_d":46.00,"k_cilindro":-4.00},"oi":{"k1_d":47.00,"k2_d":45.00}},"tipo_lente":"monofocal"}
```

### CASO X-08
**Complejidad:** rutina · **Objetivo:** control grande — todo normal (sanity, sin disparadores).
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"X-08","paciente":{"edad":30,"ocupacion":"empleado","motivo_consulta":"chequeo general"},"refraccion":{"od":{"esfera":-1.25,"cilindro":0.0,"av_cc":"20/20"},"oi":{"esfera":-1.25,"cilindro":0.0,"av_cc":"20/20"}},"clinica":{"uso_pantallas":"lt2","anexos_oculares":"Anexos sin alteraciones.","reflejos_pupilares":"Reflejo fotomotor, consesual, acomodativo","motilidad_ocular":"Versiones: normales. Ducciones: normales.","confrontacion_campos_visuales":"Sin defectos perifericos evidentes.","fondo_de_ojo":"Retina aplicada, papila de bordes netos, macula sin lesiones.","grid_de_amsler":"Sin descendencia de patologia aparente.","cover_test":"OD: Orto | OI: Orto","ojo_seco_but_seg":12,"ppc_cm":5},"tipo_lente":"monofocal"}
```

### CASO X-09
**Complejidad:** compleja · **Objetivo:** fondo glaucomatoso + papila (coexisten) + campos.
**Correlaciones esperadas:** `["papila_patologica","fondo_glaucomatoso","campos_visuales_alterados"]`

```json
{"receta_id":"X-09","paciente":{"edad":60,"ocupacion":"jubilado","motivo_consulta":"control de nervio optico"},"refraccion":{"od":{"esfera":-2.00,"cilindro":0.0,"av_cc":"20/25"},"oi":{"esfera":-2.00,"cilindro":0.0,"av_cc":"20/25"}},"clinica":{"fondo_de_ojo":"Excavacion c/d 0.8 con adelgazamiento del anillo neurorretiniano; ademas palidez papilar temporal en OI.","confrontacion_campos_visuales":"Escotoma arciforme por confrontacion en OI."},"tipo_lente":"monofocal"}
```

### CASO X-10
**Complejidad:** compleja · **Objetivo:** desviación vertical (tropía) + exotropia con lente + síntomas.
**Correlaciones esperadas:** `["desviacion_vertical","exotropia_lente"]`

```json
{"receta_id":"X-10","paciente":{"edad":34,"ocupacion":"empleado","motivo_consulta":"diplopia vertical intermitente"},"clinica":{"cover_test":"OD: Hiper y Tropia | OI: Exo y Tropia"},"tipo_lente":"monofocal"}
```

### CASO X-11
**Complejidad:** compleja · **Objetivo:** segmento anterior — anexos + catarata + BUT crítico + presbicia.
**Correlaciones esperadas:** `["opacidad_cristaliniana","but_critico","anexos_patologicos","presbicia_multifocal"]`

```json
{"receta_id":"X-11","paciente":{"edad":58,"ocupacion":"empleado","motivo_consulta":"ardor y vision nublada"},"refraccion":{"od":{"esfera":-1.00,"cilindro":0.0,"add":2.25,"av_cc":"20/25"},"oi":{"esfera":-1.00,"cilindro":0.0,"add":2.25,"av_cc":"20/25"}},"clinica":{"anexos_oculares":"Blefaritis con disfuncion de meibomio; catarata cortical incipiente en OD.","ojo_seco_but_seg":4,"confrontacion_campos_visuales":"Sin defectos perifericos evidentes."},"tipo_lente":"progresivo"}
```

### CASO X-12
**Complejidad:** compleja · **Objetivo:** carga máxima multi-dominio (stress test de integración del LLM).
**Correlaciones esperadas:** `["pupilas_alteradas","fondo_vascular_diabetico","motilidad_alterada","campos_visuales_alterados","av_cc_limitada","amsler_alterado","anexos_patologicos","insuficiencia_convergencia","cvs_sospecha","but_pantallas","presbicia_multifocal"]`

```json
{"receta_id":"X-12","paciente":{"edad":63,"ocupacion":"contador","motivo_consulta":"diplopia, cefalea y ardor ocular al leer"},"refraccion":{"od":{"esfera":-0.50,"cilindro":0.0,"add":2.50,"av_cc":"20/50"},"oi":{"esfera":-0.50,"cilindro":0.0,"add":2.50,"av_cc":"20/40"}},"clinica":{"uso_pantallas":"gt6","ppc_cm":12,"cover_test":"OD: Exo y Foria | OI: Exo y Foria","ojo_seco_but_seg":6,"reflejos_pupilares":"Reflejo fotomotor, consesual, acomodativo: anisocoria de 1.5 mm mayor en OD","motilidad_ocular":"Versiones: nistagmo en levoversion.","fondo_de_ojo":"Microaneurismas y exudados duros dispersos.","anexos_oculares":"Pterigion nasal en OD.","confrontacion_campos_visuales":"Escotoma paracentral en OI.","grid_de_amsler":"Metamorfopsia central en OI."},"tipo_lente":"progresivo"}
```

## Bloque 10 — Coerción tolerante y edge cases

### CASO Z-01
**Complejidad:** compleja · **Objetivo:** eje >180 se normaliza mod 180 (225→45, oblicuo).
**Correlaciones esperadas:** `["astig_oblicuo"]`

```json
{"receta_id":"Z-01","paciente":{"edad":30,"ocupacion":"empleado","motivo_consulta":"vision distorsionada"},"refraccion":{"od":{"esfera":-3.00,"cilindro":-2.50,"eje":225,"av_cc":"20/25"},"oi":{"esfera":-3.00,"cilindro":-2.50,"eje":225,"av_cc":"20/25"}},"tipo_lente":"monofocal"}
```

### CASO Z-02
**Complejidad:** compleja · **Objetivo:** add = 0 no cuenta como adición → presbicia sin adición sí opera.
**Correlaciones esperadas:** `["presbicia_sin_adicion"]`

```json
{"receta_id":"Z-02","paciente":{"edad":50,"ocupacion":"empleado","motivo_consulta":"revision"},"refraccion":{"od":{"esfera":-0.50,"cilindro":0.0,"add":0,"av_cc":"20/20"},"oi":{"esfera":-0.50,"cilindro":0.0,"add":0,"av_cc":"20/20"}},"tipo_lente":"monofocal"}
```

### CASO Z-03
**Complejidad:** compleja · **Objetivo:** add negativa se descarta → presbicia sin adición.
**Correlaciones esperadas:** `["presbicia_sin_adicion"]`

```json
{"receta_id":"Z-03","paciente":{"edad":45,"ocupacion":"empleado","motivo_consulta":"revision"},"refraccion":{"od":{"esfera":0.25,"cilindro":0.0,"add":-0.50,"av_cc":"20/20"},"oi":{"esfera":0.25,"cilindro":0.0,"av_cc":"20/20"}},"tipo_lente":"monofocal"}
```

### CASO Z-04
**Complejidad:** compleja · **Objetivo:** K corruptas (fuera de 25–80 D) se descartan → sin córnea.
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"Z-04","paciente":{"edad":40,"ocupacion":"empleado","motivo_consulta":"revision"},"refraccion":{"od":{"esfera":-2.00,"cilindro":0.0,"av_cc":"20/20"},"oi":{"esfera":-2.00,"cilindro":0.0,"av_cc":"20/20"}},"akr":{"od":{"k1_d":99.00,"k2_d":5.00,"k_promedio_d":95.00},"oi":{"k1_d":98.00,"k2_d":4.00}},"tipo_lente":"monofocal"}
```

### CASO Z-05
**Complejidad:** compleja · **Objetivo:** esfera/cilindro fuera de catálogo se descartan (OD ignorado).
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"Z-05","paciente":{"edad":30,"ocupacion":"empleado","motivo_consulta":"revision"},"refraccion":{"od":{"esfera":-25.00,"cilindro":-10.00,"eje":200},"oi":{"esfera":-1.00,"cilindro":0.0,"av_cc":"20/20"}},"tipo_lente":"monofocal"}
```

### CASO Z-06
**Complejidad:** compleja · **Objetivo:** AKR plus-cyl se transpone a convención negativa → AR detecta astig.
**Correlaciones esperadas:** `["ar_detecta_astigmatismo_no_prescrito"]`

```json
{"receta_id":"Z-06","paciente":{"edad":35,"ocupacion":"empleado","motivo_consulta":"revision"},"refraccion":{"od":{"esfera":1.00,"cilindro":0.0,"av_cc":"20/20"},"oi":{"esfera":1.00,"cilindro":0.0,"av_cc":"20/20"}},"akr":{"od":{"esfera":-1.00,"cilindro":1.00,"eje":90},"oi":{"esfera":1.00,"cilindro":0.0}},"tipo_lente":"monofocal"}
```

### CASO Z-07
**Complejidad:** compleja · **Objetivo:** cover con " - " se normaliza a " y " (Exo - Foria → exoforia).
**Correlaciones esperadas:** `["ppc_exoforia"]`

```json
{"receta_id":"Z-07","paciente":{"edad":30,"ocupacion":"empleado","motivo_consulta":"chequeo"},"clinica":{"cover_test":"OD: Exo - Foria | OI: Orto"}}
```

### CASO Z-08
**Complejidad:** compleja · **Objetivo:** uso_pantallas fuera de catálogo → None; BUT 7 cae en limítrofe.
**Correlaciones esperadas:** `["but_limitrofe"]`

```json
{"receta_id":"Z-08","paciente":{"edad":33,"ocupacion":"empleado","motivo_consulta":"molestia"},"clinica":{"uso_pantallas":"muchas horas","ojo_seco_but_seg":7}}
```

### CASO Z-09
**Complejidad:** compleja · **Objetivo:** ppc_cm fuera de rango (>15) → None; la exoforia clasificada aún dispara.
**Correlaciones esperadas:** `["ppc_exoforia"]`

```json
{"receta_id":"Z-09","paciente":{"edad":30,"ocupacion":"empleado","motivo_consulta":"chequeo"},"clinica":{"cover_test":"OD: Exo y Foria | OI: Orto","ppc_cm":25}}
```

### CASO Z-10
**Complejidad:** compleja · **Objetivo:** payload sin datos clínicos → HTTP 422.
**Correlaciones esperadas:** HTTP 422

```json
{"receta_id":"Z-10","paciente":{"edad":40,"ocupacion":"empleado","motivo_consulta":"chequeo"}}
```

### CASO Z-11
**Complejidad:** compleja · **Objetivo:** negación en anexos → sin falsos positivos.
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"Z-11","paciente":{"edad":45,"ocupacion":"empleado","motivo_consulta":"revision"},"clinica":{"anexos_oculares":"Sin pterigion ni blefaritis. Cornea transparente."}}
```

### CASO Z-12
**Complejidad:** compleja · **Objetivo:** DPAR negado → sin hallazgo pupilar.
**Correlaciones esperadas:** `[]`

```json
{"receta_id":"Z-12","paciente":{"edad":38,"ocupacion":"empleado","motivo_consulta":"revision"},"clinica":{"reflejos_pupilares":"Reflejo fotomotor, consesual, acomodativo: sin DPAR"}}
```

---

## Resumen de cobertura

- **41/41 correlaciones** con al menos un caso que las dispara.
- **Supresiones cubiertas:** glaucoma_asimetrico→(pupilas, fondo_glaucomatoso); periférico→diabético; insuf_convergencia→(ppc_exoforia, cover_exoforia); causa orgánica→(ambliopía, screening); espasmo/cambio→variabilidad.
- **Coexistencias cubiertas:** papila+glaucomatoso; diabético+hipertensivo; opacidad+av_cc; presbicia_multifocal+adicion_incongruente; av_cc+ambliopía.
- **Coerción tolerante:** eje mod 180, add≤0, K fuera de rango, esfera/cil fuera de catálogo, transposición AKR plus-cyl, uso_pantallas/ppc fuera de catálogo, 422 sin datos.
- **Negación por oración:** fondo, anexos, campos, pupilas.
