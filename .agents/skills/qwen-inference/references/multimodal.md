# Multimodal

Qwen3.5-9B is a vision-language model: text, image, and video input are supported natively. Output remains text.

## When to enable multimodal

- Product genuinely needs image or video understanding (visual Q&A, OCR-like tasks, document analysis, medical imaging, video summarization).
- User traffic includes visual content at non-trivial volume.

## When NOT to enable multimodal

- Pure text product (chat, text extraction, summarization of written content).
- Occasional visual input that can be handled by a separate pipeline (OCR pre-processing, dedicated vision model).

Running the vision encoder consumes VRAM that could otherwise go to KV cache. If you don't need it, strip it:

- **vLLM:** `--language-model-only` at launch.
- **Transformers:** load with `AutoModelForCausalLM` instead of the multimodal variant where possible.
- **Ollama:** the `qwen3.5:9b` tag is text-focused; multimodal variants may have separate tags — check the current Ollama library.

## Input structure (OpenAI-compatible)

Images and videos are passed as content blocks within a message:

### Image input

```python
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "Describe lo que ves en esta imagen."},
            {
                "type": "image_url",
                "image_url": {"url": "https://example.com/image.jpg"},
            },
        ],
    }
]
```

Base64-encoded images also work:

```python
import base64

with open("image.jpg", "rb") as f:
    b64 = base64.b64encode(f.read()).decode()

messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "¿Qué marca es este producto?"},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{b64}"},
            },
        ],
    }
]
```

### Video input

```python
messages = [
    {
        "role": "user",
        "content": [
            {"type": "text", "text": "Resume lo que ocurre en este video."},
            {
                "type": "video_url",
                "video_url": {"url": "https://example.com/clip.mp4"},
            },
        ],
    }
]
```

Video is sampled into frames internally; longer videos use more context. Budget accordingly.

## Validation on the server side (your API)

Before forwarding multimodal blocks to the inference backend, validate:

```python
from urllib.parse import urlparse

ALLOWED_IMAGE_MIMETYPES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_VIDEO_MIMETYPES = {"video/mp4", "video/webm"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024   # 10 MB
MAX_VIDEO_BYTES = 100 * 1024 * 1024  # 100 MB

def validate_image_block(block: dict) -> None:
    url = block["image_url"]["url"]
    if url.startswith("data:"):
        # Validate mimetype from data URL
        mime = url.split(";")[0].removeprefix("data:")
        if mime not in ALLOWED_IMAGE_MIMETYPES:
            raise ValueError(f"Disallowed image type: {mime}")
    else:
        # Validate URL scheme, domain allowlist, reachability
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https"):
            raise ValueError("Only http(s) URLs allowed")
        # ... domain allowlist check, HEAD request for size/mime, etc.
```

Skipping validation exposes:

- **Arbitrary URL fetch.** If your backend fetches the image, an attacker-controlled URL can hit internal services (SSRF).
- **Oversized inputs.** A 200MB image silently blows past context / VRAM.
- **Non-image content.** Passing a 10MB PDF as `image_url` breaks the pipeline.

## Mixed multimodal in a multi-turn conversation

Images and text can interleave across turns. Persist them correctly:

- Keep the image block as part of the user message in history.
- Do not re-resolve URLs per turn — if you fetched and base64'd an image on turn 1, reuse that base64 on subsequent turns where context includes it.
- Be aware of context cost: every retained image adds tokens (image tokens, not just the URL string).

## Transformers direct with images

```python
from transformers import AutoProcessor, AutoModelForCausalLM
from PIL import Image

processor = AutoProcessor.from_pretrained("Qwen/Qwen3.5-9B")
model = AutoModelForCausalLM.from_pretrained("Qwen/Qwen3.5-9B", device_map="auto")

image = Image.open("photo.jpg")

messages = [
    {
        "role": "user",
        "content": [
            {"type": "image", "image": image},
            {"type": "text",  "text":  "¿Qué ves aquí?"},
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
response = processor.decode(outputs[0][inputs["input_ids"].shape[-1]:], skip_special_tokens=True)
```

## Context budgeting for multimodal

Images consume large token counts when encoded. Rough order-of-magnitude:

- A 512×512 image ≈ hundreds to ~1K tokens depending on encoder config.
- Higher resolutions scale roughly quadratically.
- Video is frames × image cost, so short clips are fine but long videos are expensive.

Account for this when setting `num_ctx` on Ollama or `--max-model-len` on vLLM. A 4K context is too tight for meaningful image+text tasks; aim for 16K+ minimum.

## Common failures

- **Multimodal request to text-only server.** Returns an error or ignores the image. Check the backend was not launched with `--language-model-only`.
- **VRAM OOM on image input.** Vision encoder at load plus KV cache for a long image prompt. Reduce resolution, lower `num_ctx`, or move to larger VRAM.
- **Rate limits / timeouts on image URL fetch.** Your API is fetching the image synchronously; consider pre-fetching and caching.
- **Base64 expansion in logs.** Never log raw base64 of images — floods storage and leaks content. Log hashes.
