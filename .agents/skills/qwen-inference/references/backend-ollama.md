# Backend: Ollama

Ollama is valid for local deployment, internal services, and single-machine setups. It is not a replacement for vLLM/SGLang at high concurrency or for fine-grained feature control, but for FastAPI services talking to a local GPU box it is the simplest correct path.

## When Ollama is the right choice

- Single-machine deployment (desktop/workstation with GPU).
- Low-to-medium concurrency (dozens of requests/minute, not thousands).
- FastAPI or similar backend acting as a thin client to the inference daemon.
- Internal LAN services where you control the network topology.

## When to switch off Ollama

- Need high throughput with continuous batching — use vLLM.
- Need fine control over tool-call parsers, reasoning parsers, MTP — use vLLM or SGLang.
- Need multimodal at scale — vLLM with proper config.
- Need exact parameter fidelity with the official model card — vLLM/SGLang expose more.

## Installation and model pull

```bash
# Install Ollama daemon (platform-specific; see ollama.com)
# Then:
ollama pull qwen3.5:9b
ollama run qwen3.5:9b   # interactive sanity check
```

The `qwen3.5:9b` artifact on Ollama is approximately 6.6 GB with `Q4_K_M` quantization by default. Architecture tag: `qwen35`. This is good enough for most deployments on consumer GPUs (RTX 3060 / 3070 / 3080 / 4070 tier and up).

For other quantization options (Q4_K_L, Q5_K_M, Q8_0), see `quantization-gguf.md`.

## Python client

Install:

```bash
pip install ollama
```

The official `ollama` Python library talks to the daemon over its HTTP API at `http://localhost:11434` (default).

### Sync client (simple scripts)

```python
from ollama import Client

client = Client(host="http://localhost:11434")

response = client.chat(
    model="qwen3.5:9b",
    messages=[
        {"role": "system", "content": "Responde de forma técnica y breve."},
        {"role": "user",   "content": "Resumen de arquitectura Qwen3.5-9B"},
    ],
    options={
        "temperature": 1.0,
        "top_p": 0.95,
        "top_k": 20,
        "num_ctx": 4096,
        "seed": 42,
        "repeat_penalty": 1.0,
    },
)
print(response.message.content)
```

### Async client (FastAPI)

For FastAPI: use `AsyncClient`. Wrapping sync calls in a thread pool works but wastes workers under load.

```python
import asyncio
from ollama import AsyncClient

async def generate(prompt: str) -> str:
    client = AsyncClient(host="http://localhost:11434")
    response = await client.chat(
        model="qwen3.5:9b",
        messages=[{"role": "user", "content": prompt}],
        options={
            "temperature": 0.1,
            "top_p": 0.95,
            "top_k": 20,
            "num_ctx": 4096,
            "seed": 42,
            "repeat_penalty": 1.0,
        },
    )
    return response.message.content
```

### Streaming

```python
stream = client.chat(
    model="qwen3.5:9b",
    messages=[{"role": "user", "content": "Explica YaRN en detalle"}],
    stream=True,
)
for chunk in stream:
    print(chunk["message"]["content"], end="", flush=True)
```

For FastAPI, wrap `AsyncClient.chat(..., stream=True)` in a `StreamingResponse` with `text/event-stream` for SSE.

## Parameter translation: OpenAI-compatible → Ollama

Ollama does not 1:1 match OpenAI's API. Translation table:

| Official Qwen preset field | Ollama `options` key | Notes |
|---|---|---|
| `temperature` | `temperature` | direct |
| `top_p` | `top_p` | direct |
| `top_k` | `top_k` | direct |
| `min_p` | `min_p` | direct |
| `presence_penalty` | **no direct equivalent** | Do not map to `repeat_penalty` — different semantics |
| `repetition_penalty` | `repeat_penalty` | direct |
| `max_tokens` | `num_predict` | direct |
| context window | `num_ctx` | set explicitly; default often smaller than model's native |
| `seed` | `seed` | direct |
| `chat_template_kwargs.enable_thinking` | **not exposed in Ollama options** | Must be controlled via Modelfile template override if needed |

## Thinking mode on Ollama

Ollama packages `qwen3.5:9b` with its own chat template. Controlling `enable_thinking` is less clean than on vLLM/SGLang. Options:

1. **Leave thinking on** (default) and parse the response, discarding reasoning when persisting history.
2. **Custom Modelfile** that overrides the template to disable thinking. Example:

```
FROM qwen3.5:9b
TEMPLATE """<your custom template with enable_thinking=False baked in>"""
```

Then `ollama create my-qwen-nothink -f Modelfile` and use `my-qwen-nothink` as the model name.

This is intrusive. If you need clean thinking control, vLLM/SGLang are the right choice.

## Context window

Set `num_ctx` explicitly in the `options` dict. Ollama defaults can be lower than the model's native 262K:

```python
options = {"num_ctx": 4096}  # for short interactive chat
options = {"num_ctx": 32768} # for long documents
options = {"num_ctx": 131072} # for very long context
```

Higher `num_ctx` = more VRAM used even if the actual input is short. Tune to real workload.

## Architecture pattern: FastAPI + Ollama

```
┌──────────────┐    ┌─────────────────┐    ┌──────────────┐
│ Frontend /   │───▶│ FastAPI service │───▶│ Ollama daemon│
│ external API │    │ (business logic)│    │ (inference)  │
└──────────────┘    └─────────────────┘    └──────────────┘
                             │
                             ▼
                    ┌─────────────────┐
                    │ DB / Redis      │
                    │ (history, PHI)  │
                    └─────────────────┘
```

Principles:

- FastAPI owns: authentication, rate limiting, history persistence, PHI/PII handling, tool execution, observability, validation.
- Ollama owns: model loading, GPU memory, tokenization, generation.
- Do not push business logic into the prompt. Do not push inference concerns into the FastAPI handlers.

See `python-patterns.md` for the full FastAPI example with validation and history sanitization.

## Known operational gotchas

- **Model warm-up:** first request after daemon restart is slow (model load). Warm up on service startup.
- **Concurrent requests:** Ollama serializes by default unless configured otherwise (`OLLAMA_NUM_PARALLEL`). For a real async FastAPI, set this.
- **VRAM headroom:** `num_ctx` at 32K+ with a 9B Q4 model on a 10GB card leaves little room. Monitor with `nvidia-smi` under load.
- **`httpx` timeouts:** long generations can exceed default httpx timeouts used by the `ollama` lib internally. For 32K+ output, extend timeouts or switch to streaming.
- **PHI-safe logging:** Do not log full prompts or responses if they contain patient data. Log IDs and token counts, not content.
