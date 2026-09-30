# Architecture and modes

## Model identity

`Qwen/Qwen3.5-9B` is the **post-trained** 9B model intended for final-use inference, not a research checkpoint. It is a unified vision-language model with hybrid architecture.

`Qwen/Qwen3.5-9B-Base` is a separate artifact, documented for fine-tuning, in-context-learning experiments, and research. **Do not ship Base to users.** If the goal is LoRA / SFT / continued pre-training, start from Base. For everything else (chat, agents, extraction, RAG, APIs, product features), use the post-trained model.

## Architecture details

From the official model card:

| Property | Value |
|---|---|
| Parameters | 9B |
| Layers | 32 |
| Hidden size | 4096 |
| FFN intermediate | 12288 |
| Vocabulary / LM output | 248,320 |
| Native context | 262,144 tokens |
| Extended context (YaRN) | ~1,010,000 tokens |
| MTP (multi-token prediction) | yes |
| Modalities | text, image, video |

The layer pattern is hybrid: `8 × (3 × (Gated DeltaNet → FFN) → 1 × (Gated Attention → FFN))`. This is not a standard dense decoder — consequences:

- Older backend versions may not support it correctly.
- Generic quantization schemes can behave unevenly across layer types.
- "Treat it like LLaMA" is a reliable way to ship a broken system.

MTP support matters if you want speculative decoding with a compatible draft setup. Confirm your backend exposes the feature before planning for it.

## Thinking mode

Qwen3.5 **thinks by default**. The model produces internal reasoning tokens before the final answer on every request unless explicitly disabled.

### What this means operationally

- Latency is higher than with non-thinking models of similar size.
- Token cost includes the reasoning budget.
- The API response contains two logical parts — `reasoning` and `final_answer` — and a correctly designed system treats them as separate fields.
- History persistence must drop reasoning. See rule 3 in SKILL.md.

### How to disable thinking

**Not supported:** `/think`, `/nothink`, or any prompt-level tag. These work in some older Qwen families; in Qwen3.5 they do nothing or silently do the wrong thing.

**Supported:**

- Self-hosted OpenAI-compatible endpoints (vLLM, SGLang): pass `chat_template_kwargs={"enable_thinking": False}` inside `extra_body`.
- Alibaba Cloud Model Studio: pass the equivalent toggle via `extra_body`.
- SGLang: can also be invoked with `--reasoning-parser qwen3` at server launch, which affects how reasoning is surfaced, not whether it happens.

Example (OpenAI-compatible client):

```python
response = client.chat.completions.create(
    model="Qwen/Qwen3.5-9B",
    messages=messages,
    extra_body={
        "chat_template_kwargs": {"enable_thinking": False},
    },
)
```

### When to disable

- Low-latency user-facing endpoints where perceived responsiveness matters more than reasoning quality.
- High-volume batch jobs where cost dominates.
- Tasks that are genuinely mechanical (format conversion, simple extraction from clean input).

### When to keep thinking on

- Multi-step reasoning, math, code generation.
- Tool-calling agents where planning matters.
- Clinical / medical / legal impression-style outputs that benefit from implicit structured thought.

## History rule (restated with teeth)

Multi-turn conversations **must** persist only the `final_answer`. The raw assistant message (with reasoning) is for the current turn's response parsing only.

```python
def sanitize_assistant_message(raw: dict) -> dict:
    # raw may contain: {"reasoning": "...", "content": "final answer"}
    # or a parsed split depending on backend; normalize to final content only
    return {
        "role": "assistant",
        "content": raw.get("final_content") or raw.get("content", ""),
    }
```

Violating this rule causes:

- Monotonically increasing token cost per turn.
- Reasoning from turn N leaking as "fact" into turn N+1's context.
- Inconsistencies when the model re-reads its own prior reasoning and contradicts it.
- Privacy leakage if reasoning contains PHI/PII the user never saw.

## Modalities

The model accepts text, image, and video. For text-only products, the vision stack is pure overhead — see `multimodal.md` for how to strip it at the serving layer.
