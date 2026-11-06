# Certificación final: `explicacion_paciente` (texto simple para el paciente)

**Fecha:** 2026-11-06 · **Certificador:** TestingRealityChecker (solo lectura) · **Criterio del dueño:** «el paciente debe entender qué dice su graduación por medio de texto».

## VEREDICTO: NO CERTIFICADO

El texto es **seguro y robusto** (catálogo cerrado, guardas estrictas, 0 plantillas inválidas en 144 perfiles, 220 pruebas en verde), pero **no cumple el criterio de aceptación**: nombra el *tipo* de corrección y no explica *qué dice* la graduación. La propia plantilla lo admite al cerrar con «Puedes preguntar qué significa cada parte de tu receta…» (`app/patient_profile.py:47`). Puede seguir en uso porque no causa daño, pero no se puede certificar frente a ese criterio.

---

## 1. Lo que ejecuté (evidencia real)

| Comprobación | Cómo | Resultado |
|---|---|---|
| Pruebas | `venv/Scripts/python.exe -B -m pytest -p no:cacheprovider -q tests/test_patient_profile.py tests/test_dual_output.py` | **220 passed in 2.14s** |
| Hueco de magnitud | Script por stdin con `build_patient_profile`/`build_patient_template` | `-1/-1 == -1/-8 : True`; `-0.25/-0.25 == -12/-12 : True`; `CIL -0.75 == CIL -4.00 : True`; `ADD 1.00 == ADD 3.00: True` |
| Enumeración | 6 conjuntos por ojo × 6 × 4 variantes de ADD (ninguna/OD/OI/ambos) | **144 perfiles: 143 `aplicable`, 1 `sin_componentes_refractivos`; 0 plantillas inválidas; 62–85 palabras; 143 textos distintos** |
| Tú/usted | Regex sobre los 143 textos | **143 con tuteo, 0 con usted/su** |
| Contexto que recibe el LLM | `build_patient_context` con -1/-8 | Sin una sola cifra: solo nombres, lado, apertura y catálogo |
| NUM_CTX | `settings` + `_estimate_tokens` con el `.env` real | `num_ctx 4096`, límite al 95 % **3891**. Solo Rx: 3706 (pasa). **Rx+AKR: 3921 (desborda). Rx+AKR+clínica: 4176 (desborda)** |
| Peso del bloque educativo en el prompt | Diferencia entre el system dual y el clínico, más el JSON del perfil | Reglas **459 tok** + perfil **422 tok** ≈ **880 tok por petición** |

**No ejecuté:** inferencia (no hay GPU en esta PC), las pruebas de Laravel, el renderizado real del PDF ni el `.env` del equipo con GPU.

## 2. Verificación de hallazgos

### 2.1 Hueco de comprensión: CONFIRMADO
- `app/patient_profile.py:111-124`: el perfil elimina todas las cifras («sin cifras del expediente»).
- `app/prompt_builder.py:527`: prohíbe «OD/OI, cifras, dioptrías, ejes».
- `app/patient_profile.py:139-164`: el validador solo acepta frases exactas del catálogo, así que el LLM **no puede** explicar números aunque se le pida.
- El resultado es el mismo texto para -0.25 y para -12, para OD -1/OI -8 y para -1/-1, para CIL -0.75 y -4.00, y para ADD +1.00 y +3.00.

### 2.2 Clasificación óptica en casos frontera: CORRECTA (con simplificación aceptada)
- S=0 C=-1, S=+1 C=-1 (S+C=0), +0.5/-1.5 (mixto) → `astigmatismo` solamente, conforme a `SALIDA_DUAL.md:84`.
- Cilindro positivo: -1 +1.5 → `astigmatismo`; -2 +1 → `miopía, astigmatismo`. Coincide con la transposición de `app/schemas.py:116-133,149`.
- ADD=0 en ojos planos → `sin_componentes_refractivos`; ADD solo en OI → `aplicable`, 71 palabras.
- NaN, CIL ausente y esfera -31 (fuera de rango, `schemas.py:145`) → `datos_incompletos`.
- **Ojo plano:** con OD -3 y OI 0, el texto no menciona el ojo izquierdo (el paciente verá «0.00» en la tabla sin ninguna explicación). Con OD -8 y OI 0 (anisometropía) el texto es idéntico al de -3/0.
- **Redundancia:** cuando los ojos difieren, la apertura repite «Tu graduación incluye corrección para…» dos veces (`patient_profile.py:93-98`).

### 2.3 Enumeración de los 144 perfiles: CONFIRMADA (Codex y Antigravity coinciden: 62–85 palabras)

### 2.4 Tú/usted: CONFIRMADO
- El catálogo (`patient_profile.py:30,43-51,92,108`), el prompt («trato de tu», `prompt_builder.py:526`) y `SALIDA_DUAL.md:96` («Las guardas exigen … tú») usan tuteo.
- La óptica habla de usted con el paciente: `opt/lang/es/whatsapp.php:27` («le compartimos el informe clínico de su consulta… Puede consultar y descargar su receta en PDF»). Ese mismo PDF es el que contiene el texto en tuteo.

### 2.5 NUM_CTX: CONFIRMADO y más grave de lo que dijo Codex
- `ia-api/.env:6` tiene `OLLAMA_NUM_CTX=4096`; `app/config.py:28` y `.env.example:8` tienen 8192. `OLLAMA_DUAL_NUM_PREDICT` no está en `.env`, así que se usa el valor de config, 1024.
- Con ese `.env`, una consulta normal con AKR (3921) ya supera 3891 y lanza `context_overflow` (`inference.py:860-868`) antes de llamar al proveedor. No hace falta un texto libre largo para que falle.
- No sé qué valor tiene el equipo con GPU: queda como precondición verificable.

### 2.6 ¿El PDF muestra la tabla junto al texto? PARCIAL
- La tabla sí se imprime: `informe_clinico.blade.php:490-531`, «II. Resultado refractivo prescrito», con columnas Ojo/ESF/CIL/EJE/ADD/DNP/ALT/AV SC/AV CC.
- El texto **no está junto a la tabla**: va en una sección posterior, después de «V. Impresión clínica y plan» (`:675-685`), con el título sin acento «Explicacion a paciente» (`:679`).
- La tabla usa «OD/OI» y abreviaturas, y el texto tiene prohibido usarlas, así que nada conecta las dos cosas.
- ESF y CIL pasan por `DioptriaFormatter`, que imprime 0 como «0.00» y los positivos con «+». **ADD se imprime en bruto** (`:514,525`) y EJE también.
- **Riesgo de diseño:** Laravel acepta cilindro positivo (`RecetaValidationRules.php:160,168`, `between:-30,30`) y el PDF lo imprime tal cual, pero ia-api lo **transpone** (`schemas.py:149`). Una leyenda con cifras generada dentro de ia-api a partir de `req.refraccion` **no coincidiría con la tabla** cuando la receta use cilindro positivo.

### 2.7 Otros
- `PROPUESTA_RESUMEN_PACIENTE.md:176` (sin seguimiento en git) trae como ejemplo «Tus ojos se encuentran saludables… moderados». Contradice las reglas vigentes.
- Hay una contradicción interna en Antigravity: su encabezado dice «CERTIFICABLE CON CONDICIONES» y su cuerpo dice «no es certificable en su estado actual».

## 3. Resolución de desacuerdos

**(a) ¿Bloqueante o mayor? BLOQUEANTE para certificar (no para operar).** La gravedad se mide contra el criterio de aceptación, no contra la seguridad. El criterio pide entender *qué dice la graduación*, y lo que la graduación dice son sus valores: signo, potencia, cilindro, eje y adición por ojo. Un texto idéntico para -0.25 y -12 no transmite eso, y el catálogo remite al paciente a preguntar en la óptica. Antigravity lo clasifica como MAYOR porque es «seguro», pero eso confunde seguridad con aceptación. No es un riesgo clínico, así que no exige retirar la función.

**(b) Ojo plano: prevalece la regla vigente** («No afirmes que un ojo plano está sano ni que no necesita lentes»). «No requiere graduación» se lee como «no necesita lentes» o «está bien», y es falso cuando ese ojo lleva ADD o lente de balance. La redacción segura describe **el papel, no el ojo**:
- Sin ADD en ese ojo: «En el ojo izquierdo, su receta de lejos marca 0.00: ese lado no lleva corrección para ver de lejos.»
- Con ADD en ese ojo: «En el ojo izquierdo, su receta de lejos marca 0.00; ese lado solo lleva el apoyo para ver de cerca.»
- Prohibido en ambos casos: «sano», «normal», «bien», «no necesita», «no requiere».

**(c) ¿100 % CPU? SÍ, y pasa a ser obligatorio en cuanto se añadan cifras.**
- El LLM solo elige entre 1–2 definiciones y 7 cierres (`validate_patient_text`), es decir, no aporta valor educativo.
- Cuesta unos 880 tokens por petición, y eso es justo lo que hace desbordar el contexto con 4096: sin ese bloque, el caso Rx+AKR+clínica bajaría de 4176 a unos 3300.
- Las cifras no pueden pasar por el LLM: el prompt las prohíbe y lo que se busca es exactitud.
- Qwen queda solo para el texto clínico.
- **Cuidado con el contrato:** si se reutiliza `estado="plantilla"`, Laravel mostrará siempre «se usó una plantilla de respaldo» (`FormEditor.php:684`) y el estado `recovered` (`:484`). Hay que coordinar estado, origen y mensajes en los dos repositorios.

## 4. Condiciones mínimas y verificables para certificar

| # | Cambio | Archivo(s) | Prueba que lo demuestra |
|---|---|---|---|
| C1 (bloqueante) | Leyenda determinista «Cómo leer su receta», por ojo, generada **con los mismos valores que imprime la tabla** (sin transponer). Debe explicar: ESF (signo −/+ = corrige para ver de lejos / para enfocar; «0.00» = sin corrección de lejos), CIL (astigmatismo; 0 = no lleva), EJE («orientación en grados de la corrección del astigmatismo; no mide cuánto ve»), ADD (apoyo extra para cerca), que la dioptría mide la potencia del lente y no un porcentaje de visión, y una comparación neutral entre ojos («el ojo izquierdo lleva más potencia»). Sin etiquetas leve/moderada/alta salvo que el dueño apruebe los umbrales. Ubicación recomendada: Laravel (un formateador PHP y un partial pegado a la sección II), o bien ia-api conservando los valores crudos antes de transponer. | `opt/app/Support/Recetas/` (clase nueva), `informe_clinico.blade.php:490-531`; alternativa: `ia-api/app/patient_profile.py` y `schemas.py` | Prueba unitaria: OD -1/OI -8 **≠** -1/-1; -0.25 ≠ -12; cilindro positivo: la leyenda cita los mismos signos y valores que las celdas; plano → la frase de 3(b); ADD unilateral; valor nulo → sin leyenda. Prueba de render: el HTML del PDF contiene la leyenda pegada a la tabla y cada cifra coincide con su celda. |
| C2 | Explicación 100 % CPU; quitar el bloque PERFIL EDUCATIVO y las reglas del prompt dual; estado y origen acordados en los dos repositorios, con mensajes de UI que no digan «respaldo». | `inference.py:836-838,942-950`, `prompt_builder.py:521-531`, `dual_contract.py`, `IaApiService.php:807-815`, `FormEditor.php:484,684` | pytest: el prompt enviado no contiene «PERFIL EDUCATIVO» y la explicación sale de CPU aunque el LLM devuelva basura; prueba de Laravel: el estado nuevo muestra el mensaje de éxito. |
| C3 | Trato de usted en el catálogo, el prompt (si queda) y la documentación. | `patient_profile.py:28-52,92,108`, `SALIDA_DUAL.md:96`, pruebas | Enumeración de los 144 perfiles: 0 coincidencias de `\b(tu|tus|te|puedes|veas|tienes|usas)\b` o `-rte\b`. |
| C4 | Mención segura del ojo plano (redacción de 3b) y apertura sin la frase repetida. | `patient_profile.py:87-99` | OD -3/OI 0 menciona «ojo izquierdo… 0.00»; ningún perfil contiene `sano|normal|no necesita|no requiere`. |
| C5 (precondición operativa) | `OLLAMA_NUM_CTX ≥ 8192` en el equipo con GPU, más una prueba que falle si la carga representativa no cabe. | `.env` del equipo con GPU, `config.py:28` | pytest con una carga Rx+AKR+clínica completa: `est_total ≤ int(num_ctx*0.95)` usando el `.env` real; captura del `.env` del host con GPU. |
| C6 (menor) | Título «Explicación para el paciente»; marcar `PROPUESTA_RESUMEN_PACIENTE.md` como histórica o quitar su ejemplo «saludables». | `informe_clinico.blade.php:679`, `PROPUESTA_RESUMEN_PACIENTE.md:176` | grep. |

**Reauditoría:** después de C1–C5, enumerar de nuevo los 144 perfiles, añadir casos con cifras y renderizar el PDF real (captura) con: -1/-8, cilindro positivo, plano con ADD y antimetropía.
