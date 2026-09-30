# Sampling, token budgets, and YaRN

## Sampling presets (official, from model card)

These are not suggestions. They are the published baseline. If the model loops, repeats, or mixes languages, fix sampling and backend config first — do not reach for prompt engineering.

| Mode | temperature | top_p | top_k | min_p | presence_penalty | repetition_penalty |
|---|---:|---:|---:|---:|---:|---:|
| Thinking general | 1.0 | 0.95 | 20 | 0.0 | 1.5 | 1.0 |
| Thinking coding | 0.6 | 0.95 | 20 | 0.0 | 0.0 | 1.0 |
| Non-thinking general | 0.7 | 0.8 | 20 | 0.0 | 1.5 | 1.0 |
| Non-thinking reasoning | 1.0 | 1.0 | 40 | 0.0 | 2.0 | 1.0 |

### Notes per mode

- **Thinking general:** default for chat, Q&A, open-ended tasks with reasoning benefit.
- **Thinking coding:** lower temperature keeps code deterministic; `presence_penalty=0.0` because code naturally repeats tokens (keywords, identifiers) and penalizing that hurts quality.
- **Non-thinking general:** tuned for direct, fast responses without reasoning chain.
- **Non-thinking reasoning:** paradoxical name — this is for cases where reasoning is disabled at the backend but the task still benefits from high-temperature diverse sampling.

## Versioned Python presets

```python
SAMPLING_PRESETS = {
    "thinking_general": {
        "temperature": 1.0,
        "top_p": 0.95,
        "presence_penalty": 1.5,
        "extra_body": {"top_k": 20, "min_p": 0.0},
    },
    "thinking_code": {
        "temperature": 0.6,
        "top_p": 0.95,
        "presence_penalty": 0.0,
        "extra_body": {"top_k": 20, "min_p": 0.0},
    },
    "nothinking_general": {
        "temperature": 0.7,
        "top_p": 0.8,
        "presence_penalty": 1.5,
        "extra_body": {
            "top_k": 20,
            "min_p": 0.0,
            "chat_template_kwargs": {"enable_thinking": False},
        },
    },
    "nothinking_reasoning": {
        "temperature": 1.0,
        "top_p": 1.0,
        "presence_penalty": 2.0,
        "extra_body": {
            "top_k": 40,
            "min_p": 0.0,
            "chat_template_kwargs": {"enable_thinking": False},
        },
    },
}
```

## Backend translation

Not every backend accepts these keys directly:

- **vLLM / SGLang (OpenAI-compatible):** `temperature`, `top_p`, `presence_penalty` are top-level args; `top_k`, `min_p`, `chat_template_kwargs` go in `extra_body`.
- **Ollama:** different key names. `temperature`, `top_p`, `top_k` are direct options; `presence_penalty` has no direct Ollama equivalent — use `repeat_penalty` carefully, knowing it is not the same thing. Set `num_ctx`, `seed`, `repeat_penalty` in the `options` dict. See `backend-ollama.md` for the full mapping.
- **Transformers direct:** values passed to `generate()` or `GenerationConfig`. No OpenAI-compatible layer; you build it yourself.

## Token output budgets

Official recommendations:

- **32,768 tokens** — max output for most queries.
- **81,920 tokens** — max output for hard tasks (complex math, long-form coding, deep reasoning chains).

### What goes wrong with low caps

A common failure: system works in dev with `max_tokens=2048`, then users hit problems that need 6-8K of reasoning plus a 3K final answer. The model gets truncated mid-chain-of-thought. Symptoms: answers that just stop, no closing punctuation, or final answer missing entirely because all tokens were consumed by reasoning.

### Budget profiles by endpoint type

Do not ship a single global cap. Profile by use case:

| Endpoint type | Suggested max_output_tokens |
|---|---:|
| Interactive chat (user-facing) | 4,096 – 8,192 |
| Batch extraction / classification | 2,048 |
| Long-form generation (reports, docs) | 16,384 – 32,768 |
| Hard reasoning (math proofs, complex code) | 32,768 – 81,920 |
| Agentic loop (per-step) | 4,096 |

Expose these as profile presets, not scattered literals.

## Context and YaRN

### Native context

262,144 tokens. That is not a typo. For most workloads — including long documents, large RAG contexts, and extended multi-turn chat — you never need YaRN.

### When YaRN matters

YaRN extends usable context up to ~1,010,000 tokens. Turn it on only when:

- Real workloads consistently approach or exceed 262K.
- You have measured, not assumed, that the tail of your distribution needs it.

### Why YaRN is off by default

The publicly available implementation is **static YaRN**: the scaling factor is fixed at load time. On short inputs (which is most real traffic), static YaRN degrades quality vs. native RoPE. Enabling YaRN "just in case" penalizes the common case to serve the rare one.

### YaRN configuration

Example `rope_parameters` from the model card:

```python
rope_parameters = {
    "rope_type": "yarn",
    "rope_theta": 10_000_000,
    "partial_rotary_factor": 0.25,
    "factor": 4.0,                          # SCALE THIS TO YOUR WINDOW
    "original_max_position_embeddings": 262144,
}
```

The `factor=4.0` in the example corresponds to ~1M token windows. Calibrate:

- Need 524,288 tokens in practice? → `factor = 2.0`
- Need 393,216 tokens? → `factor ≈ 1.5`
- Need ≤262,144 tokens? → **do not enable YaRN at all**

Copying `factor=4.0` blindly into a system that never exceeds 300K tokens means every short request pays a quality tax for context that is never used.

## Seeds and determinism

- `seed` is supported on most backends but does not guarantee cross-backend reproducibility (vLLM, SGLang, Transformers, Ollama all have different internal sampling paths).
- For deterministic-ish outputs within a single backend: set `seed`, fix `temperature` low (0.1 - 0.3 for extraction tasks), and accept that true determinism across deployments is not realistic for LLMs at this scale.
- Temperature 0 is not true greedy on all backends — some clamp to a floor. Use `temperature=0.1` as a practical "near-greedy" if you need it.
