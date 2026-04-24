# Hallazgos de auditoria - Cumplimiento con documentacion oficial de Qwen3.5-9B

Fecha original: 2026-04-24
Ultima actualizacion: 2026-04-24 (tras aplicar Fase 1, Fase 2 y Paso 2 de Fase 3)
Modelo: `qwen3.5:9b` (Ollama, Q4_K_M, ~6.6 GB)
Hardware: RTX 3070 Ti (8 GB VRAM)
Backend: **Ollama** (decision firme, no se considera migracion)
Uso: impresion clinica optometrica single-turn, `think=False`

---

## Estado de avance

| Fase | Estado | Hallazgos |
|---|---|---|
| Fase 1 — Fixes criticos | APLICADA | `num_ctx`, `num_predict`, warmup |
| Fase 2 — Robustez | APLICADA | sanitizacion, system prompt, `_postprocess` |
| Fase 3 — Alineacion avanzada | **Parcial** | Paso 2 aplicado; Paso 1 y Paso 3 pendientes |
| Fase 4 — Documentacion | Pendiente | Actualizar `PIPELINE_LLM.md` |

Todos los hallazgos restantes son compatibles con permanecer en Ollama.

---

## Tabla de contenidos

1. [Metodologia y contexto](#1-metodologia-y-contexto)
2. [Hallazgos pendientes](#2-hallazgos-pendientes)
   - 2.1 `think=False` + Modelfile custom para eliminar emisiones de `<think>`
   - 2.2 Comentarios faltantes en `repeat_penalty` y `seed`
3. [Hallazgos NO APLICAN (revisados)](#3-hallazgos-no-aplican-revisados)
4. [Plan de ejecucion de Fase 3 restante](#4-plan-de-ejecucion-de-fase-3-restante)
5. [Fase 4 — Documentacion final](#5-fase-4--documentacion-final)

---

## 1. Metodologia y contexto

La auditoria se realizo contrastando el codigo actual contra:

- La skill oficial `qwen-inference` en [.claude/skills/qwen-inference/SKILL.md](.claude/skills/qwen-inference/SKILL.md), que replica el model card oficial de `Qwen/Qwen3.5-9B`.
- Las referencias de la skill: `backend-ollama.md`, `sampling-and-context.md`, `architecture-and-modes.md`, `python-patterns.md`, `quantization-gguf.md`.
- El flujo documentado en [PIPELINE_LLM.md](PIPELINE_LLM.md).

El backend es Ollama por decision firme del proyecto. Todos los fixes aqui se adaptan a las posibilidades y limitaciones reales del backend.

---

## 2. Hallazgos pendientes

### 2.1 `think=False` + Modelfile custom para eliminar emisiones de `<think>`

**Archivos:** [app/main.py](app/main.py), [app/inference.py](app/inference.py)

**Codigo actual:**
```python
request_body = {
    "model": settings.ollama_model,
    ...
    "think":  False,
    "options": _OLLAMA_OPTIONS,
}
```

**Lo que dice la documentacion:**

`backend-ollama.md`, seccion "Thinking mode on Ollama":

> "Ollama packages `qwen3.5:9b` with its own chat template. Controlling `enable_thinking` is less clean than on vLLM/SGLang. Options:
> 1. Leave thinking on (default) and parse the response, discarding reasoning when persisting history.
> 2. **Custom Modelfile** that overrides the template to disable thinking."

**Por que el actual es sub-optimo:**

El parametro `think: false` existe en la API de Ollama (desde 0.5.x) y **deberia** aplicar `enable_thinking=False` al chat template, pero **solo si el Modelfile del tag `qwen3.5:9b` hace passthrough del flag**. Si el Modelfile tiene el template hardcodeado con thinking activado, `think: False` se ignora silenciosamente.

En la practica el modelo a veces sigue emitiendo `<think>...</think>`. El `_postprocess` ya endurecido en Fase 2 maneja los 3 patrones (bloque completo, residual, truncado), pero:

- Parte del budget de `num_predict=1024` se gasta en razonamiento ocasional.
- Un `<think>` truncado sin cerrar dispara retry (consume tiempo).

**Fix propuesto (opcion A, recomendada — elimina la emision de raiz):**

Crear `ops/Modelfile.qwen3-5-9b-nothink`:

```
FROM qwen3.5:9b

TEMPLATE """{{- range $i, $_ := .Messages }}
{{- if eq .Role "system" }}<|im_start|>system
{{ .Content }}<|im_end|>
{{ else if eq .Role "user" }}<|im_start|>user
{{ .Content }}<|im_end|>
{{ else if eq .Role "assistant" }}<|im_start|>assistant
{{ .Content }}<|im_end|>
{{ end }}
{{- end -}}
<|im_start|>assistant
"""

PARAMETER stop "<|im_end|>"
PARAMETER stop "<|im_start|>"
```

(El template omite el bloque `<think>` que el Modelfile default de Qwen3.5 inyecta cuando thinking esta activo.)

Build:
```bash
ollama create qwen3.5-9b-nothink -f ops/Modelfile.qwen3-5-9b-nothink
```

Actualizar `.env`:
```
OLLAMA_MODEL=qwen3.5-9b-nothink
```

**Fix propuesto (opcion B, no tocar nada):**

Aceptar que el `_postprocess` ya blinda los 3 casos. Costo: retries ocasionales cuando el razonamiento se trunca sin cerrar. Esto es tolerable si la prioridad es no mantener un artefacto extra (`ops/Modelfile.*`).

---

### 2.2 Comentarios faltantes en `repeat_penalty` y `seed`

**Archivo:** [app/config.py](app/config.py)

**Codigo actual:**

```python
ollama_repeat_penalty: float = 1.0  # 1.0 = desactivado. La terminología
                                    # clínica requiere repetición exacta
                                    # de términos (OD/OI, agudeza visual);
                                    # penalizarla genera circunloquios.
...
ollama_seed: int = 42               # Fija reproducibilidad. -1 para
                                    # desactivar y obtener variabilidad.
```

**Lo que dice la documentacion:**

`sampling-and-context.md` tabla oficial: non-thinking general incluye `presence_penalty=1.5`, que **Ollama no expone**. `backend-ollama.md` prohibe mapearlo a `repeat_penalty`:

> `presence_penalty` — **no direct equivalent** — Do not map to `repeat_penalty` — different semantics.

**Por que agregar comentarios:**

Sin esa nota, un proximo desarrollador podria "arreglar" el `repeat_penalty=1.0` subiendolo a 1.5 creyendo que es el equivalente del `presence_penalty` oficial. Es la trampa que la doc avisa.

**Fix propuesto:**

```python
ollama_repeat_penalty: float = 1.0  # 1.0 = desactivado. La terminologia
                                    # clinica repite terminos exactos
                                    # (OD/OI, agudeza visual); penalizarla
                                    # genera circunloquios.
                                    # NOTA: Qwen3.5 non-thinking oficial
                                    # pide presence_penalty=1.5, que Ollama
                                    # NO expone. No mapear a repeat_penalty:
                                    # semantica distinta segun doc oficial
                                    # (backend-ollama.md, rule 5 de SKILL).

ollama_seed: int = 42               # Seed fijo: dos casos identicos
                                    # (excluyendo receta_id) generan la
                                    # misma redaccion. Cambiar a -1 solo si
                                    # se quiere variabilidad entre recetas
                                    # iguales — hoy no se quiere porque
                                    # el cache por hash las unificaria igual.
```

---

## 3. Hallazgos NO APLICAN (revisados)

Items de la doc oficial que se revisaron y **no aplican** al sistema actual:

| Regla del model card | Por que no aplica aqui |
|---|---|
| Rule 3: no persistir `reasoning` en history | El sistema es single-turn, no hay history. El cache guarda solo el parrafo final, no hay contaminacion cross-turn. |
| Rule 6: YaRN off salvo >262K tokens | El prompt total nunca pasa de 2500 tokens. YaRN no aparece en el codigo. Correcto. |
| Rule 4: Base vs post-trained | Ollama `qwen3.5:9b` sirve el post-trained por defecto. No hay riesgo. |
| Rule 8: max_output_tokens por endpoint | Solo hay un endpoint con un tipo de output. La regla aplica a sistemas multi-endpoint; aqui es prematura. |
| Tool calling parsers | No se usan. |
| Multimodal / vision encoder | No se usan. `think=False` + texto puro. |
| Streaming con backpressure | Se usa `stream=False`, correcto para parrafos cortos single-shot. |
| Abreviaturas con punto (`O.D.`, `A.O.`) en `_postprocess` | Protegidas pero casi nunca emitidas por el modelo; mantener el codigo defensivo no cuesta. |
| **QwenProfile desacoplado** | **Descartado por decision del proyecto: no se abriran endpoints adicionales.** Aplanar sampling en `Settings` es aceptable para un unico caso de uso. |

---

## 4. Plan de ejecucion de Fase 3 restante

Quedan 2 pasos independientes. Se puede hacer cualquiera de los dos, ambos, o ninguno sin que afecte la estabilidad actual.

### Paso 1 — Modelfile custom (hallazgo 2.1)

**Esfuerzo:** ~20 min.
**Ganancia:** elimina emisiones intermitentes de `<think>` de raiz. Libera budget de `num_predict` y evita retries por truncamiento de razonamiento.

**Acciones:**

1. Crear `ops/Modelfile.qwen3-5-9b-nothink` con el template sin bloque `<think>` (contenido en seccion 2.1).
2. Ejecutar `ollama create qwen3.5-9b-nothink -f ops/Modelfile.qwen3-5-9b-nothink`.
3. Verificar en `ollama list` que aparezca el nuevo tag.
4. Actualizar `.env` y `.env.example`:
   ```
   OLLAMA_MODEL=qwen3.5-9b-nothink
   ```
5. Reiniciar el servicio FastAPI.

**Validacion:**

- Correr 10-15 peticiones reales variadas.
- En logs, confirmar que el warning `Removed duplicate follow-up` y las llamadas a retry disminuyen o desaparecen.
- Endpoint `/health` debe devolver `model_available: true` para el nuevo tag (si no, revisar el Modelfile).

**Rollback:** `OLLAMA_MODEL=qwen3.5:9b` en `.env`, reiniciar.

---

### Paso 2 — Comentarios de `repeat_penalty` y `seed` (hallazgo 2.2)

**Esfuerzo:** ~5 min.
**Ganancia:** previene que un proximo desarrollador "arregle" el `repeat_penalty` subiendolo a 1.5 por confundirlo con `presence_penalty`.

**Acciones:**

1. Actualizar los comentarios en [app/config.py](app/config.py) con el texto de 2.2.
2. Opcional: agregar un aviso en la cabecera de `.env.example` indicando que `OLLAMA_REPEAT_PENALTY` y `OLLAMA_SEED` tienen rationale documentado en `config.py`.

**Validacion:** ninguna (solo comentarios).

---

## 5. Fase 4 — Documentacion final

Una vez aplicada la Fase 3 (completa o parcial):

1. **Actualizar [PIPELINE_LLM.md](PIPELINE_LLM.md)**:
   - Seccion 9 (Inferencia con Ollama): actualizar la tabla de parametros con los valores reales (`num_ctx=4096`, `num_predict=1024`).
   - Mencionar la validacion preemptiva de contexto (HTTP 413 si el prompt estimado excede `num_ctx * 0.95`).
   - Si se aplico Paso 1: cambiar la mencion del modelo a `qwen3.5-9b-nothink` y explicar por que.

2. **Archivar esta guia**:
   - Si los 2 pasos restantes se completaron: borrar `HALLAZGOS_QWEN3.5.md` (o moverlo a `docs/decisiones/HALLAZGOS_QWEN3.5_2026-04-24.md` como registro historico).
   - Si solo se hicieron algunos: mantener el archivo con los restantes.

---

## Referencias cruzadas

- [.claude/skills/qwen-inference/SKILL.md](.claude/skills/qwen-inference/SKILL.md) — reglas duras, preset de sampling.
- [.claude/skills/qwen-inference/references/backend-ollama.md](.claude/skills/qwen-inference/references/backend-ollama.md) — traduccion de parametros, gotchas.
- [.claude/skills/qwen-inference/references/sampling-and-context.md](.claude/skills/qwen-inference/references/sampling-and-context.md) — presets oficiales, budgets de tokens.
- [.claude/skills/qwen-inference/references/architecture-and-modes.md](.claude/skills/qwen-inference/references/architecture-and-modes.md) — thinking mode, history rule.
- [.claude/skills/qwen-inference/references/python-patterns.md](.claude/skills/qwen-inference/references/python-patterns.md) — arquitectura FastAPI, validacion, errores.
- [PIPELINE_LLM.md](PIPELINE_LLM.md) — pipeline actual documentado.
