# Backend: vLLM and SGLang

For production serving with real concurrency, tool calling, and fine-grained feature control, vLLM and SGLang are the two serious options documented by the official model card. Both expose OpenAI-compatible endpoints, but their server-side flags and parsers are not interchangeable.

## vLLM

### Baseline launch

```bash
vllm serve Qwen/Qwen3.5-9B \
    --host 0.0.0.0 \
    --port 8000 \
    --max-model-len 262144
```

### With tool calling

```bash
vllm serve Qwen/Qwen3.5-9B \
    --tool-call-parser qwen3_coder \
    --enable-auto-tool-choice \
    --max-model-len 262144
```

### Text-only mode (free VRAM, no vision encoder)

If the product is text-only, strip the vision stack:

```bash
vllm serve Qwen/Qwen3.5-9B --language-model-only
```

This releases VRAM that otherwise goes to the vision encoder and enlarges the available KV cache. Do this by default for text-only products — it is free performance.

### With MTP (speculative decoding)

Qwen3.5 is trained with MTP, so vLLM can use it for speculative decoding. Consult the vLLM version's docs for the exact flag — the feature naming has shifted across vLLM releases.

### Disabling thinking via client

Server stays on defaults; client controls via `extra_body`:

```python
from openai import OpenAI

client = OpenAI(base_url="http://localhost:8000/v1", api_key="EMPTY")

resp = client.chat.completions.create(
    model="Qwen/Qwen3.5-9B",
    messages=[{"role": "user", "content": "Summarize this..."}],
    temperature=0.7,
    top_p=0.8,
    presence_penalty=1.5,
    max_tokens=4096,
    extra_body={
        "top_k": 20,
        "chat_template_kwargs": {"enable_thinking": False},
    },
)
```

## SGLang

### Baseline launch

```bash
python -m sglang.launch_server \
    --model-path Qwen/Qwen3.5-9B \
    --host 0.0.0.0 \
    --port 30000
```

### With reasoning parser

```bash
python -m sglang.launch_server \
    --model-path Qwen/Qwen3.5-9B \
    --reasoning-parser qwen3
```

The `qwen3` reasoning parser extracts reasoning vs final answer into separate fields on the response. Consuming this on the client side is cleaner than string-parsing.

### With tool calling

```bash
python -m sglang.launch_server \
    --model-path Qwen/Qwen3.5-9B \
    --tool-call-parser qwen3_coder
```

### With MTP

See SGLang docs for the current flag; MTP support has been evolving. The model supports it; the server must be configured to use it.

## OpenAI-compatible client (both backends)

The same client code works for vLLM and SGLang. Only `base_url` changes.

```python
import os
from openai import OpenAI, AsyncOpenAI

client = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:8000/v1"),
    api_key=os.getenv("OPENAI_API_KEY", "EMPTY"),
)

# async variant for FastAPI:
async_client = AsyncOpenAI(
    base_url=os.getenv("OPENAI_BASE_URL", "http://localhost:8000/v1"),
    api_key=os.getenv("OPENAI_API_KEY", "EMPTY"),
)
```

Do not build against vLLM-specific Python APIs or SGLang-specific endpoints unless you have a concrete reason. The OpenAI layer is the portability boundary.

## Portability caveat

The OpenAI layer covers `messages`, `temperature`, `top_p`, `presence_penalty`, `max_tokens`. It does **not** fully cover:

- `extra_body` content — backend-specific keys.
- Tool call result formats — parsers differ.
- Reasoning surfacing — depends on `--reasoning-parser`.
- Streaming event shape for tool calls — varies.

Abstract these behind your own layer. See `python-patterns.md` for the wrapper pattern.

## Feature availability matrix

| Feature | vLLM | SGLang | Notes |
|---|---|---|---|
| OpenAI-compatible endpoint | ✅ | ✅ | Both expose `/v1/chat/completions` |
| Tool calling | ✅ `--tool-call-parser qwen3_coder` + `--enable-auto-tool-choice` | ✅ `--tool-call-parser qwen3_coder` | Must launch with flag; client-side alone is not enough |
| Reasoning parser | `chat_template_kwargs` on client | `--reasoning-parser qwen3` server-side | Different mechanisms for same goal |
| Text-only mode | ✅ `--language-model-only` | Check current version | Free VRAM when vision is unused |
| MTP / speculative | ✅ (version-dependent) | ✅ (version-dependent) | Both support; check flags |
| Multimodal (image/video) | ✅ | ✅ | Requires vision encoder loaded |
| Continuous batching | ✅ native | ✅ native | Strong throughput vs Transformers |
| KV cache optimization | ✅ PagedAttention | ✅ RadixAttention | Different internals, both effective |

## Choosing between vLLM and SGLang

Neither is strictly better. Decision factors:

- **vLLM** has broader adoption and more third-party tooling. Pick it if you want ecosystem compatibility.
- **SGLang** has faster inference in some benchmarks and a more expressive programming model for complex agentic flows. Pick it if you need its specific features.
- If the team already knows one, use that one. The win from switching is marginal compared to the cost of re-operationalizing.

## Deployment notes

- Both backends are memory-hungry at launch. Plan for ~18-20GB VRAM for Qwen3.5-9B in bf16, ~10-12GB for int4 quantization.
- Warm-up matters: first requests are slow while CUDA kernels compile. Include a startup probe that sends a dummy request.
- Health checks: `GET /v1/models` on both backends returns 200 when ready.
- Configure request timeouts at the reverse proxy (nginx/Caddy/etc) to match long-output budgets — `max_tokens=32768` can take minutes.
