# Python patterns for Qwen3.5-9B systems

This reference assumes you've read the hard rules in `SKILL.md` and picked a backend (see `backend-*.md`). It covers the application-layer patterns: configuration, wrappers, FastAPI shape, history, validation, error handling, observability.

## Layered architecture

```
┌──────────────────────────────────────────────────────┐
│  Presentation layer                                  │
│  (FastAPI routes, request/response models)           │
├──────────────────────────────────────────────────────┤
│  Service layer                                       │
│  (business logic, authorization, rate limiting)      │
├──────────────────────────────────────────────────────┤
│  Inference orchestration layer                       │
│  (QwenClient wrapper, sampling, history sanitizer)   │
├──────────────────────────────────────────────────────┤
│  Backend adapter layer                               │
│  (Ollama / OpenAI-compat / Transformers)             │
└──────────────────────────────────────────────────────┘
```

Rules:

- Routes never call the backend directly.
- Business logic never touches sampling parameters or backend-specific kwargs.
- The inference orchestration layer owns the `QwenProfile` contract.
- Swapping backends changes only the adapter layer.

## Configuration contract (restated)

```python
from dataclasses import dataclass, field
from typing import Literal

Backend = Literal["vllm", "sglang", "transformers", "ollama"]
Mode = Literal["thinking_general", "thinking_code", "nothinking_general", "nothinking_reasoning"]

@dataclass
class QwenProfile:
    model: str = "Qwen/Qwen3.5-9B"
    backend: Backend = "vllm"
    base_url: str = "http://localhost:8000/v1"
    enable_thinking: bool = True
    multimodal: bool = False
    max_output_tokens: int = 32768
    max_context_tokens: int = 262144
    sampling_mode: Mode = "thinking_general"
    keep_thinking_in_history: bool = False
    tool_calling: bool = False
    yarn_enabled: bool = False
    yarn_factor: float = 1.0
```

Profiles are created at app startup and injected as dependencies. They are not mutated per request.

## Client wrapper

A single wrapper that hides backend differences:

```python
from openai import AsyncOpenAI
from ollama import AsyncClient as AsyncOllamaClient

class QwenClient:
    def __init__(self, profile: QwenProfile):
        self.profile = profile
        if profile.backend in ("vllm", "sglang"):
            self._openai = AsyncOpenAI(
                base_url=profile.base_url,
                api_key="EMPTY",
            )
            self._ollama = None
        elif profile.backend == "ollama":
            self._ollama = AsyncOllamaClient(host=profile.base_url)
            self._openai = None
        else:
            raise NotImplementedError(f"Backend {profile.backend} not wired")

    async def chat(self, messages: list, mode: Mode | None = None) -> dict:
        mode = mode or self.profile.sampling_mode
        preset = SAMPLING_PRESETS[mode]

        if self._openai:
            return await self._chat_openai(messages, preset)
        if self._ollama:
            return await self._chat_ollama(messages, preset)

    async def _chat_openai(self, messages, preset):
        extra = preset.get("extra_body", {}).copy()
        if not self.profile.enable_thinking:
            extra.setdefault("chat_template_kwargs", {})
            extra["chat_template_kwargs"]["enable_thinking"] = False

        resp = await self._openai.chat.completions.create(
            model=self.profile.model,
            messages=messages,
            temperature=preset["temperature"],
            top_p=preset["top_p"],
            presence_penalty=preset.get("presence_penalty", 0.0),
            max_tokens=self.profile.max_output_tokens,
            extra_body=extra,
        )
        return {
            "content": resp.choices[0].message.content,
            "finish_reason": resp.choices[0].finish_reason,
            "usage": resp.usage.model_dump() if resp.usage else None,
        }

    async def _chat_ollama(self, messages, preset):
        # Translate OpenAI preset → Ollama options
        options = {
            "temperature": preset["temperature"],
            "top_p": preset["top_p"],
            "top_k": preset.get("extra_body", {}).get("top_k", 20),
            "num_ctx": 4096,  # configurable
            "num_predict": self.profile.max_output_tokens,
            "repeat_penalty": 1.0,
            "seed": 42,
        }
        resp = await self._ollama.chat(
            model=self.profile.model,
            messages=messages,
            options=options,
        )
        return {
            "content": resp.message.content,
            "finish_reason": None,  # Ollama doesn't expose this the same way
            "usage": None,
        }
```

## History sanitization

The critical function in any multi-turn system:

```python
def sanitize_assistant_message(raw: dict, backend: Backend) -> dict:
    """Strip reasoning, keep only the final answer for history persistence."""
    if backend in ("vllm", "sglang") and raw.get("reasoning") is not None:
        # If backend surfaced reasoning separately, drop it
        return {"role": "assistant", "content": raw.get("final_content") or raw.get("content", "")}

    # If reasoning was inlined in content, strip by convention (backend-dependent)
    content = raw.get("content", "")
    # Some deployments wrap reasoning in <think>...</think> tags; strip if present
    if "<think>" in content and "</think>" in content:
        # keep only content after the last </think>
        content = content.rsplit("</think>", 1)[-1].strip()

    return {"role": "assistant", "content": content}
```

Apply this before calling `save_history()`. Never persist the raw response.

## FastAPI endpoint

```python
from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel, Field

app = FastAPI()

def get_client() -> QwenClient:
    # configured at startup
    return app.state.qwen_client

class ChatRequest(BaseModel):
    session_id: str = Field(min_length=1, max_length=128)
    message: str = Field(min_length=1, max_length=16_384)
    mode: Mode | None = None

class ChatResponse(BaseModel):
    answer: str
    tokens_used: int | None = None

@app.post("/chat", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    client: QwenClient = Depends(get_client),
):
    history = await load_history(req.session_id)
    messages = history + [{"role": "user", "content": req.message}]

    try:
        resp = await client.chat(messages, mode=req.mode)
    except TimeoutError:
        raise HTTPException(status_code=504, detail="Inference timeout")
    except Exception as e:
        # Log with context, do NOT leak internals to client
        logger.exception("Inference failure", extra={"session_id": req.session_id})
        raise HTTPException(status_code=502, detail="Inference error")

    sanitized = sanitize_assistant_message(resp, client.profile.backend)
    await append_history(req.session_id, [
        {"role": "user", "content": req.message},
        sanitized,
    ])

    return ChatResponse(
        answer=sanitized["content"],
        tokens_used=resp.get("usage", {}).get("total_tokens") if resp.get("usage") else None,
    )
```

## Validation layer

Validate the profile itself at startup and individual requests at runtime:

```python
def validate_profile(profile: QwenProfile, server_features: dict) -> None:
    """Run at startup to fail fast on misconfiguration."""

    if profile.multimodal and server_features.get("language_model_only"):
        raise ValueError(
            "profile.multimodal=True but server launched with --language-model-only"
        )

    if profile.tool_calling and not server_features.get("tool_parser_enabled"):
        raise ValueError(
            "profile.tool_calling=True but server has no --tool-call-parser"
        )

    if profile.max_context_tokens > server_features.get("max_model_len", 262144):
        raise ValueError(
            f"profile.max_context_tokens={profile.max_context_tokens} exceeds server's max_model_len"
        )

    if profile.keep_thinking_in_history:
        raise ValueError(
            "keep_thinking_in_history=True is a policy violation (rule 3 in SKILL.md)"
        )

    if profile.yarn_enabled and profile.max_context_tokens <= 262144:
        raise ValueError(
            "YaRN enabled but max_context_tokens within native range — disables without benefit"
        )
```

## Observability

Log what matters, not what leaks:

```python
import logging
import time

logger = logging.getLogger(__name__)

async def chat_with_metrics(client: QwenClient, messages: list, session_id: str) -> dict:
    start = time.perf_counter()
    resp = await client.chat(messages)
    elapsed_ms = (time.perf_counter() - start) * 1000

    logger.info(
        "inference_completed",
        extra={
            "session_id": session_id,
            "backend": client.profile.backend,
            "mode": client.profile.sampling_mode,
            "latency_ms": round(elapsed_ms, 1),
            "input_tokens": resp.get("usage", {}).get("prompt_tokens"),
            "output_tokens": resp.get("usage", {}).get("completion_tokens"),
            "finish_reason": resp.get("finish_reason"),
            # NOT logged: message content, PHI, PII
        },
    )
    return resp
```

Metrics to track:

- Latency (p50, p95, p99) per endpoint and per sampling mode.
- Token usage (input/output separately) — this is your cost signal.
- Finish reason distribution — if `length` dominates, your `max_tokens` is too low.
- Error rate by type (timeout, backend error, validation error).
- Queue depth / concurrent inflight requests.

## Error taxonomy

Handle these distinct cases explicitly:

```python
class InferenceError(Exception): pass
class InferenceTimeout(InferenceError): pass
class BackendUnavailable(InferenceError): pass
class ContextTooLong(InferenceError): pass
class InvalidToolCall(InferenceError): pass
class OutputTruncated(InferenceError): pass
```

Map at the edge:

| Internal | HTTP | Client-facing message |
|---|---|---|
| `InferenceTimeout` | 504 | "Request timed out, try again" |
| `BackendUnavailable` | 503 | "Service temporarily unavailable" |
| `ContextTooLong` | 413 | "Input exceeds context window" |
| `InvalidToolCall` | 502 | "Tool call validation failed" (log internally with detail) |
| `OutputTruncated` | 200 | Return partial output with a `truncated: true` flag |

## Common architectural mistakes

1. **Business logic in prompts.** Putting policy decisions, workflows, or multi-step reasoning rules in the system prompt instead of in Python code. Prompts drift, code doesn't.
2. **Hardcoded backend details in route handlers.** `extra_body` keys, Ollama options, tool parser names all leaking into FastAPI routes. Push these down into the adapter.
3. **Global state for the client.** If you need different sampling modes for different endpoints, use multiple `QwenProfile` instances, not a single mutated one.
4. **Sync inference in async handlers.** Wrapping `ollama.chat()` (sync) in `asyncio.to_thread` works but burns workers. Use `AsyncClient`.
5. **No startup warm-up.** First request after deploy is always slow. Send a dummy request on startup.
6. **No rate limiting.** A single misbehaving client can saturate a single-GPU inference box. Rate-limit at the FastAPI layer (or in front of it).
7. **Streaming without backpressure.** If the client stops reading, does your streaming generator stop generating? If no, you're wasting GPU cycles on abandoned responses.

## Testing patterns

- **Unit-test** the `sanitize_assistant_message` function with synthetic reasoning-containing responses.
- **Integration-test** the `QwenClient` against a running local backend using a small prompt and fixed `seed` — assert the response contains expected substrings (not exact match; LLMs are nondeterministic enough that exact match tests are flaky).
- **Contract-test** the FastAPI endpoints with mocked `QwenClient` — the route behavior shouldn't depend on the model actually running.
- **Load-test** against a real backend at least once before production — identify the concurrency ceiling of your specific hardware/backend combination.
