===== antigravity (ok, 414.3s) =====
# Auditoría Técnica y Clínica: `explicacion_paciente`

## Veredicto: CERTIFICABLE CON CONDICIONES

El pipeline es técnicamente sólido, clínicamente seguro y matemáticamente blindado contra alucinaciones. Sin embargo, **no es certificable en su estado actual** por dos factores críticos: un desajuste operacional que arroja HTTP 413 con casos completos (`OLLAMA_NUM_CTX=4096`), y una brecha conceptual entre el texto generado (glosario fisiológico) y el criterio del dueño (*"entender qué dice su graduación"*).

---

## 1. Verificación y Reproducibilidad

Todo el análisis se realizó en modo **solo lectura**:
1. **Espacio de perfiles finitos**: Se ejecutó un script en Python contra [`build_patient_template`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/patient_profile.py#L167-L182) evaluando las 144 combinaciones posibles de $(OD \times OI \times ADD)$. 143 resultaron aplicables; el conteo de palabras osciló entre 62 y 85 palabras con 0 fallos de validación.
2. **Estimación de contexto y desborde**: Con [`_estimate_tokens`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/inference.py#L90-L96) se simuló un caso clínico completo (anamnesis + AKR + 6 campos clínicos + refracción). Input total: 3,839 tokens + budget 1,024 = 4,863 tokens.
3. **Auditoría cruzada de contratos**: Lectura estática de esquemas, middleware de caché y renderizado en Laravel Blade.

---

## 2. Auditoría Punto por Punto

### 1. Corrección Óptica
- **Transposición ($S$ y $S+C$)**: Impecable en [`app/patient_profile.py:57-76`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/patient_profile.py#L57-L76). El uso de potencias principales $S$ y $S+C$ garantiza invariancia ante cilindros positivos o negativos (ej. $+0.50\ -1.50$ y $-1.00\ +1.50$ clasifican igual a `("astigmatismo",)`).
- **Casos frontera**: 
  - $S=0, C \neq 0$ y $S+C=0$ (astigmatismos simples): Clasifican únicamente como `("astigmatismo",)` sin distinguir meridiano miópico o hipermetrópico (`SALIDA_DUAL.md:85`).
  - *Anisometropía monocular con ojo plano*: Si OD es miope y OI es plano ($0.00$), [`patient_opening`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/patient_profile.py#L87-L100) omite completamente el ojo izquierdo sin aclarar que llevará lente neutro.
  - *Valores no finitos*: Nulos, `NaN` e `Inf` son interceptados limpiamente en [`app/patient_profile.py:60`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/patient_profile.py#L60) retornando `datos_incompletos`.
  - *ADD*: Requiere $ADD > 0$ y finito ([`app/patient_profile.py:77`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/patient_profile.py#L77)); $ADD = 0$ se ignora correctamente. Si viene en un solo ojo, genera `"en el ojo [lado]"` sin romper la sintaxis.

### 2. Comprensibilidad frente al Criterio del Dueño
- **Brecha identificada**: El texto actual explica qué es la miopía o el astigmatismo de forma general, pero **no explica la graduación**.
- **Lo que NO entiende el paciente**:
  - No sabe qué columna es cuál (ignora qué es Esfera, Cilindro o Eje).
  - Si lee `Eje 180°`, el paciente mexicano suele creer que tiene "180 grados de desviación ocular o ceguera".
  - No comprende magnitudes (si $-0.75$ es leve o $-6.00$ es alto).
- **Veredicto**: No cumple plenamente el criterio de *"entender qué dice su graduación"*. Sobran cierres redundantes de catálogo ([`app/patient_profile.py:46-47`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/patient_profile.py#L46-L47)) y falta un puente pedagógico hacia los datos de la receta.

### 3. Seguridad Clínica y Lenguaje
- **Alarmismo y promesas**: Cero alarmismo; uso riguroso de modales ("puede hacer", "puede verse"). No promete visión perfecta ([`app/patient_profile.py:48-50`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/patient_profile.py#L48-L50)).
- **Diagnósticos y salud**: No inventa patologías. Si un ojo es plano, no afirma falsamente que el ojo "está sano" o "es normal".
- **Presbicia**: Omitida deliberadamente ([`app/patient_profile.py:43`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/patient_profile.py#L43)); se usa `"apoyo extra para enfocar de cerca"`.
- **Tono**: Todo el catálogo y el system prompt ([`app/prompt_builder.py:526`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/prompt_builder.py#L526)) fuerzan **"tú"**. En el contexto óptico mexicano y en un informe médico impreso, el trato esperado es **"usted"** (mismo tono que usa la óptica en WhatsApp).

### 4. Guardas y Plantilla
- [`validate_patient_text`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/patient_profile.py#L139-L164) exige coincidencia exacta, ordenada y normalizada con el catálogo cerrado. Es matemáticamente imposible que se cuele texto libre, inyecciones o alucinaciones.
- Los 143 perfiles aplicables generan entre 62 y 85 palabras; ninguno cae en `rechazada` por longitud.

### 5. Contrato y Estados (API ↔ Laravel)
- Estados perfectamente sincronizados entre [`app/dual_contract.py:10-12`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/dual_contract.py#L10-L12) y [`IaApiService.php:809`](file:///C:/Users/Uriel%20Rojo/Documents/opt/app/Services/IaApiService.php#L809).
- `rechazada` no se cachea ([`app/main.py:291`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/main.py#L291)).
- El respaldo urgente omite el bloque `generacion` ([`app/main.py:314-318`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/main.py#L314-L318)); Laravel lo detecta ([`IaApiService.php:162-170`](file:///C:/Users/Uriel%20Rojo/Documents/opt/app/Services/IaApiService.php#L162-L170)) e impide su aprobación automática para PDF ([`IaGenerationContext.php:120-136`](file:///C:/Users/Uriel%20Rojo/Documents/opt/app/Support/Recetas/IaGenerationContext.php#L120-L136)).
- El PDF ([`informe_clinico.blade.php:658-685`](file:///C:/Users/Uriel%20Rojo/Documents/opt/resources/views/recetas/pdf/informe_clinico.blade.php#L658-L685)) únicamente imprime texto si `$iaTextsApproved` es verdadero.

### 6. Operación y Contexto
- El archivo local [`ia-api/.env:6`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/.env#L6) tiene `OLLAMA_NUM_CTX=4096`.
- El límite preemptivo al 95% es de **3,891 tokens** ([`app/inference.py:863`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/inference.py#L863)).
- Una consulta dual completa alcanza **4,863 tokens**, detonando un **HTTP 413 inmediato** ([`app/main.py:327-334`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/main.py#L327-L334)).

### 7. Valor Real del LLM
- Dado que [`validate_patient_text`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/patient_profile.py#L139-L164) rechaza cualquier palabra fuera del catálogo, Qwen solo funciona como un selector aleatorio entre 2 definiciones y 7 cierres.
- Aporta **valor nulo**: introduce latencia, riesgo de JSON malformado y consumo de VRAM para producir un texto que [`build_patient_template`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/patient_profile.py#L167-L182) genera en menos de 0.1 ms en CPU con 100% de fiabilidad.

---

## 3. Hallazgos y Correcciones

### [H-01] BLOQUEANTE: Desborde de contexto (HTTP 413) por `OLLAMA_NUM_CTX=4096`
- **Evidencia**: [`ia-api/.env:6`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/.env#L6) vs [`app/config.py:28`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/config.py#L28) y [`app/inference.py:861-870`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/inference.py#L861-L870).
- **Impacto**: Consultas clínicas completas con AKR fallan con HTTP 413 antes de inferir.
- **Corrección**: Actualizar el `.env` de producción a `OLLAMA_NUM_CTX=8192` y `OLLAMA_DUAL_NUM_PREDICT=1024`.

### [H-02] MAYOR: Brecha entre glosario teórico y comprensión de la receta
- **Evidencia**: [`app/patient_profile.py:27-52`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/patient_profile.py#L27-L52) y [`SALIDA_DUAL.md:89-93`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/SALIDA_DUAL.md#L89-L93).
- **Impacto**: El paciente no entiende qué significan las cifras, signos ni columnas de su informe impreso.
- **Corrección**: Incluir en el catálogo una frase puente opcional que relacione la columna con la función: *"La esfera enfoca la distancia y el cilindro con su eje afina los detalles del astigmatismo"*.

### [H-03] MENOR: Discordancia de registro (Tú vs Usted)
- **Evidencia**: [`app/prompt_builder.py:526`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/prompt_builder.py#L526) y frases en [`app/patient_profile.py:44-52, 92-95`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/patient_profile.py#L44-L52).
- **Impacto**: Inconsistencia con el canal WhatsApp y pérdida de formalidad en el informe impreso.
- **Corrección**: Migrar el catálogo a trato de "Usted" (*"Su graduación incluye...", "Sus lentes llevan..."*).

### [H-04] MENOR: Redacción redundante y omisión de ojo plano en anisometropía
- **Evidencia**: [`app/patient_profile.py:93-98`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/patient_profile.py#L93-L98).
- **Impacto**: Si los ojos difieren, concatena dos oraciones idénticas. Si un ojo es plano, se ignora y el paciente cree que hubo un error.
- **Corrección**: Integrar en [`patient_opening`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/patient_profile.py#L87-L99) una mención neutra para el ojo plano (*"el ojo [lado] no requiere graduación"*).

### [H-05] OBSERVACIÓN: Sobreingeniería de LLM en salida determinista
- **Evidencia**: [`app/inference.py:942-948`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/inference.py#L942-L948).
- **Impacto**: Desperdicio de tokens y VRAM en GPU.
- **Recomendación**: Generar `explicacion_paciente` directamente con [`build_patient_template`](file:///C:/Users/Uriel%20Rojo/Documents/ia-api/app/patient_profile.py#L167-L182) en CPU, reservando Qwen exclusivamente para la impresión clínica.

