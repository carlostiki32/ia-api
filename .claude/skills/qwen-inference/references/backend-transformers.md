# Backend: HuggingFace Transformers (direct)

Transformers is for prototyping, fine-tuning, and low-concurrency experimentation. It is **not** a production serving backend.

## When to use Transformers directly

- Prototyping / smoke tests during development.
- Local scripts where you want Python-level control over generation (custom stopping criteria, logit processors, etc.).
- Fine-tuning / LoRA training (use `Qwen/Qwen3.5-9B-Base` here).
- Research into model behavior (attention patterns, activations).

## When NOT to use Transformers directly

- Any multi-user production service.
- Anything behind a web endpoint with real concurrency.
- High-throughput batch jobs.

For those cases, use vLLM or SGLang. Running `model.generate()` in a FastAPI handler will serialize requests and waste GPU cycles badly.

## Minimal text generation

```python
from transformers import AutoModelForCausalLM, AutoTokenizer
import torch

model_name = "Qwen/Qwen3.5-9B"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype=torch.bfloat16,
    device_map="auto",
)

messages = [
    {"role": "user", "content": "Explica qué es Qwen3.5-9B en dos frases."}
]

# Apply the official chat template
text = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True,
)

inputs = tokenizer(text, return_tensors="pt").to(model.device)

outputs = model.generate(
    **inputs,
    max_new_tokens=1024,
    temperature=1.0,
    top_p=0.95,
    top_k=20,
    do_sample=True,
)

response = tokenizer.decode(
    outputs[0][inputs.input_ids.shape[-1]:],
    skip_special_tokens=True,
)
print(response)
```

## Disabling thinking

Pass `enable_thinking=False` to `apply_chat_template`:

```python
text = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True,
    enable_thinking=False,   # <-- here
)
```

This is the direct Transformers equivalent of the `chat_template_kwargs` used on OpenAI-compatible endpoints.

## Multimodal with AutoProcessor

For image/video input, use `AutoProcessor`, not just the tokenizer:

```python
from transformers import AutoModelForCausalLM, AutoProcessor

processor = AutoProcessor.from_pretrained("Qwen/Qwen3.5-9B")
model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3.5-9B",
    torch_dtype=torch.bfloat16,
    device_map="auto",
)

messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "image": "path/or/url/to/image.jpg"},
            {"type": "text",  "text":  "Describe esta imagen."},
        ],
    }
]

inputs = processor.apply_chat_template(
    messages,
    tokenize=True,
    add_generation_prompt=True,
    return_tensors="pt",
).to(model.device)

outputs = model.generate(**inputs, max_new_tokens=512)
```

See `multimodal.md` for full image/video patterns.

## Generation config best practices

Build a `GenerationConfig` per mode instead of passing kwargs ad-hoc:

```python
from transformers import GenerationConfig

thinking_general = GenerationConfig(
    temperature=1.0,
    top_p=0.95,
    top_k=20,
    do_sample=True,
    max_new_tokens=32768,
    repetition_penalty=1.0,
)

thinking_code = GenerationConfig(
    temperature=0.6,
    top_p=0.95,
    top_k=20,
    do_sample=True,
    max_new_tokens=32768,
    repetition_penalty=1.0,
)
```

Note: Transformers' `GenerationConfig` doesn't have `presence_penalty` in the OpenAI sense. Use `repetition_penalty` and/or custom logit processors if needed, but know they are not the same semantics.

## Quantization via Transformers

For running Qwen3.5-9B on consumer GPUs without using Ollama/vLLM's built-in quant:

```python
from transformers import BitsAndBytesConfig, AutoModelForCausalLM
import torch

bnb = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_compute_dtype=torch.bfloat16,
    bnb_4bit_quant_type="nf4",
)

model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3.5-9B",
    quantization_config=bnb,
    device_map="auto",
)
```

bnb quantization is convenient but not benchmark-competitive with GGUF quants for this model family. For deployment, prefer GGUF via Ollama or vLLM's native quant pipeline. See `quantization-gguf.md`.

## Fine-tuning entry point (Base model)

For LoRA/SFT, start from Base, not post-trained:

```python
from transformers import AutoModelForCausalLM, AutoTokenizer

base_model = AutoModelForCausalLM.from_pretrained(
    "Qwen/Qwen3.5-9B-Base",   # not the post-trained checkpoint
    torch_dtype=torch.bfloat16,
)
tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3.5-9B-Base")
```

Then wrap with PEFT/LoRA, `trl.SFTTrainer`, or whatever fine-tuning stack applies. The chat template on Base may be absent or minimal — be explicit about what you train on.

## Concurrency limits

A single `AutoModelForCausalLM` on a single GPU can service roughly one request at a time efficiently. Batching is possible via `generate(input_ids=batched_tensor)`, but managing it manually is error-prone.

If you find yourself writing your own batching queue around Transformers, **stop and use vLLM instead** — that is exactly what vLLM already does correctly.
