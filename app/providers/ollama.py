import logging

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


def build_options() -> dict:
    return {
        "temperature":    settings.ollama_temperature,
        "num_predict":    settings.ollama_num_predict,
        "num_ctx":        settings.ollama_num_ctx,
        "repeat_penalty": settings.ollama_repeat_penalty,
        "top_p":          settings.ollama_top_p,
        "top_k":          settings.ollama_top_k,
        "min_p":          settings.ollama_min_p,
        "seed":           settings.ollama_seed,
    }


_OLLAMA_OPTIONS = build_options()


async def call(
    system_prompt: str,
    user_prompt: str,
    client: httpx.AsyncClient,
) -> tuple[str, dict]:
    """
    Llama a Ollama /api/chat y devuelve (raw_text, response_data).
    Reintenta ante ReadTimeout o 5xx hasta ollama_max_retries.
    """
    request_body = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "stream": False,
        "think":  False,
        "options": _OLLAMA_OPTIONS,
    }

    data: dict = {}
    raw_text = ""

    for attempt in range(settings.ollama_max_retries):
        try:
            response = await client.post(
                f"{settings.ollama_url}/api/chat",
                json=request_body,
            )
            response.raise_for_status()
            data = response.json()
            raw_text = data.get("message", {}).get("content", "")

            if not raw_text.strip():
                raise ValueError(
                    f"Ollama returned empty response "
                    f"(done_reason={data.get('done_reason', 'unknown')})"
                )
            break

        except (httpx.ReadTimeout, ValueError) as exc:
            if attempt < settings.ollama_max_retries - 1:
                logger.warning(
                    "Ollama attempt %d failed (%s), retrying...",
                    attempt + 1, type(exc).__name__,
                )
                continue
            raise

        except httpx.HTTPStatusError as exc:
            if (
                exc.response.status_code in (500, 503)
                and attempt < settings.ollama_max_retries - 1
            ):
                logger.warning(
                    "Ollama attempt %d failed (HTTP %d), retrying...",
                    attempt + 1, exc.response.status_code,
                )
                continue
            raise

    done_reason = data.get("done_reason", "")
    if done_reason == "length":
        logger.warning(
            "Ollama output truncated by num_predict limit (%d tokens). "
            "Output length: %d chars.",
            settings.ollama_num_predict,
            len(raw_text),
        )

    prompt_eval_count = data.get("prompt_eval_count", 0)
    if prompt_eval_count:
        ctx_margin = settings.ollama_num_ctx - settings.ollama_num_predict - prompt_eval_count
        logger.debug(
            "Ollama context: %d input tokens, %d margin (num_ctx=%d)",
            prompt_eval_count, ctx_margin, settings.ollama_num_ctx,
        )
        if ctx_margin < 100:
            logger.warning(
                "Ollama context margin critically low: %d tokens. "
                "Consider increasing OLLAMA_NUM_CTX.",
                ctx_margin,
            )

    return raw_text, data
