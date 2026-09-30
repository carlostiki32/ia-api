---
name: qwen35-inference
description: Authoritative reference for building Python inference systems around Qwen3.5-9B (post-trained and Base). Use this skill whenever the user mentions Qwen3.5, Qwen 3.5, qwen35, or is building inference code that targets a local/self-hosted Qwen model — including FastAPI backends that call Ollama/vLLM/SGLang, clinical or domain-specific text generation pipelines, tool calling with Qwen, multimodal Qwen pipelines, or GGUF/quantized local deployments. Also trigger when the user asks about thinking mode, chat template kwargs, YaRN context extension, sampling presets for Qwen, or when writing FastAPI/httpx/asyncio code that will hit a Qwen endpoint. This skill exists because Qwen3.5 has several non-obvious gotchas (thinking mode default-on, history sanitization, `/think` tags not supported, backend-specific parsers) that silently break systems built on generic LLM assumptions.
---

# Qwen3.5-9B inference skill

Authoritative guide for building Python inference systems around `Qwen/Qwen3.5-9B` (post-trained) or `Qwen/Qwen3.5-9B-Base`. Based on the official model card, official Qwen blog, and Unsloth GGUF documentation.

**Read this SKILL.md end-to-end first.** Then load the specific `references/*.md` files the task requires. Do not skip to code without reading the hard rules below.

---

## Hard rules that are never violated

These are not style preferences. Violating any of them silently breaks production systems.

1. **Thinking mode is ON by default.** Qwen3.5 generates internal reasoning before the final answer unless explicitly disabled. This affects latency, token cost, and the shape of the API contract.

2. **`/think` and `/nothink` prompt tags are NOT supported in Qwen3.5.** Disable thinking via backend options: `chat_template_kwargs={"enable_thinking": False}` on self-hosted OpenAI-compatible endpoints, or the `extra_body` equivalent on Alibaba Cloud Model Studio. Any prompt-level attempt to toggle thinking is an anti-pattern.

3. **Never persist `reasoning` content in conversation history.** Multi-turn systems must save only the `final_answer`. Persisting reasoning inflates tokens, leaks internal state, and breaks consistency across turns. This is the single most violated rule in Qwen3.5 systems.

4. **Post-trained vs Base is not interchangeable.** `Qwen/Qwen3.5-9B` is for inference/chat/agents/production. `Qwen/Qwen3.5-9B-Base` is for fine-tuning / SFT / in-context-learning research. Do not ship Base to users.

5. **Sampling presets are not optional.** Qwen publishes concrete sampling configs per mode (thinking general, thinking coding, non-thinking general, non-thinking reasoning). Loops, repetitions, or language-mixing are almost always sampling misconfig — fix sampling first, not prompts. Full table in `references/sampling-and-context.md`.

6. **YaRN is off unless you actually need >262K context.** Static YaRN degrades short-context quality. Default to native 262,144 tokens. Only enable YaRN when real workloads consistently exceed that window, and calibrate `factor` to the actual window (not the example value).

7. **Backends are not interchangeable.** vLLM, SGLang, Transformers, KTransformers and Ollama each expose different parameter surfaces, parsers, and tool-calling semantics. The OpenAI-compatible layer hides this partially, but `extra_body` content is backend-specific.

8. **Max output tokens has task-dependent budgets.** Qwen recommends 32,768 for most queries, 81,920 for hard math/coding. A single global cap for all endpoints is an architecture smell.

---

## Decision tree: which reference to load

Before writing any code, identify the task and load the matching reference file(s):

| Task | Load |
|---|---|
| "Explain what Qwen3.5 is" / model architecture / base vs post-trained | `references/architecture-and-modes.md` |
| Configuring sampling, thinking mode, YaRN, token budgets | `references/sampling-and-context.md` |
| Integrating with Ollama (local daemon, `ollama` Python lib) | `references/backend-ollama.md` |
| Serving with vLLM or SGLang (production, OpenAI-compatible endpoint) | `references/backend-vllm-sglang.md` |
| Direct HuggingFace Transformers (prototyping, low concurrency) | `references/backend-transformers.md` |
| Function calling / agents / structured tool output | `references/tool-calling.md` |
| Image/video input pipelines | `references/multimodal.md` |
| GGUF quant selection, Unsloth benchmarks, Q4_K_M decisions | `references/quantization-gguf.md` |
| FastAPI endpoint design, history persistence, validation, error handling | `references/python-patterns.md` |

For any non-trivial task, load `python-patterns.md` in addition to the backend-specific reference — it contains the configuration contract, validation rules, and error-handling patterns that the backend references assume.

---

## Quick reference: model facts

From the official model card for `Qwen/Qwen3.5-9B`:

- **Parameters:** 9B
- **Layers:** 32
- **Hidden size:** 4096
- **FFN:** 12288
- **Vocab / LM output:** 248,320
- **Native context:** 262,144 tokens
- **Extended context via YaRN:** ~1,010,000 tokens
- **Architecture:** Hybrid `8 × (3 × (Gated DeltaNet → FFN) → 1 × (Gated Attention → FFN))`
- **Trained with MTP** (multi-token prediction) — enables compatible speculative decoding
- **Modalities:** text, image, video (vision-language unified)

Compatible engines per model card: Transformers, vLLM, SGLang, KTransformers. Ollama also ships `qwen3.5:9b` as a GGUF artifact (~6.6 GB, Q4_K_M by default) — see `references/backend-ollama.md`.

---

## Quick reference: sampling presets (official)

| Mode | temperature | top_p | top_k | presence_penalty |
|---|---:|---:|---:|---:|
| Thinking general | 1.0 | 0.95 | 20 | 1.5 |
| Thinking coding | 0.6 | 0.95 | 20 | 0.0 |
| Non-thinking general | 0.7 | 0.8 | 20 | 1.5 |
| Non-thinking reasoning | 1.0 | 1.0 | 40 | 2.0 |

`min_p=0.0`, `repetition_penalty=1.0` across all modes unless noted. For `seed`, `num_ctx`, `repeat_penalty` and other Ollama-specific equivalents, see `references/backend-ollama.md`.

---

## Configuration contract

Every Qwen3.5 inference system should expose an explicit profile object. Flags scattered across the codebase guarantee silent misconfig:

```python
from dataclasses import dataclass
from typing import Literal

Backend = Literal["vllm", "sglang", "transformers", "ollama"]
Mode = Literal["thinking_general", "thinking_code", "nothinking_general", "nothinking_reasoning"]

@dataclass
class QwenProfile:
    model: str = "Qwen/Qwen3.5-9B"       # or "qwen3.5:9b" for Ollama
    backend: Backend = "vllm"
    enable_thinking: bool = True
    multimodal: bool = False
    max_output_tokens: int = 32768
    max_context_tokens: int = 262144
    sampling_mode: Mode = "thinking_general"
    keep_thinking_in_history: bool = False   # MUST stay False
    tool_calling: bool = False
```

This contract is mandatory — not decorative. Validation rules that consume it live in `references/python-patterns.md`.

---

## Pre-flight validation checklist

Before generating code, confirm the following from the user's context (ask if ambiguous):

- **Backend:** Ollama / vLLM / SGLang / Transformers? (Changes `extra_body` keys, tool parser names, multimodal paths.)
- **Thinking on or off?** (Changes sampling preset and history sanitization logic.)
- **Multimodal?** (If no, reject `image_url`/`video_url` blocks and recommend `--language-model-only` for vLLM.)
- **Tool calling?** (If yes, confirm backend was launched with correct `--tool-call-parser qwen3_coder` / `--enable-auto-tool-choice`.)
- **Context window in practice?** (Determines whether YaRN is needed and what `factor` to set.)
- **Single-turn or multi-turn?** (Multi-turn requires history sanitization logic.)

Reject configurations that combine incompatible flags (e.g., `multimodal=True` on a `--language-model-only` vLLM instance). The full validation ruleset is in `references/python-patterns.md`.

---

## Anti-patterns to reject on sight

If the user's existing code contains any of these, flag and fix before proceeding:

- `messages.append({"role": "assistant", "content": raw_response_including_reasoning})` — violates rule 3.
- `prompt = "/nothink\n" + user_prompt` — violates rule 2.
- Hardcoded `temperature=0.7` for every endpoint regardless of task — violates rule 5.
- YaRN enabled globally "just in case" — violates rule 6.
- Same client code paths for vLLM and Ollama without abstraction — violates rule 7 (Ollama does not expose `extra_body` the same way).
- Single `max_tokens=2048` cap everywhere — violates rule 8 and silently truncates long reasoning chains.
- Mixing `Qwen/Qwen3.5-9B-Base` with a chat template — violates rule 4.

---

## Output style for this skill

When the user asks for code:

- Use the `QwenProfile` contract explicitly; do not inline magic values.
- Pull sampling values from the official presets table, never invent them.
- Separate `reasoning` from `final_answer` at the response-parsing layer.
- Show `sanitize_assistant_message` or equivalent in any multi-turn example.
- For FastAPI examples, use `AsyncClient` (Ollama) or async OpenAI client, not sync in async handlers.
- Reject the request and explain why if the user asks for something that violates the hard rules — don't silently "fix" it by adding a comment.

When the user asks for explanation rather than code, still cite the hard rule that applies, not vague "best practices".
