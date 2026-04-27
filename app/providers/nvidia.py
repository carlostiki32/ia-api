import logging

from openai import APIConnectionError, APIStatusError, APITimeoutError, AsyncOpenAI

from app.config import settings

logger = logging.getLogger(__name__)

# Errores que justifican fallback a Ollama: fallas transitorias o de cuota.
# 400 (prompt inválido) y 401/403 (credenciales) no se recuperan con Ollama.
_FALLBACK_STATUS_CODES = {404, 429, 500, 502, 503, 504}


class NvidiaUnavailableError(Exception):
    """Señal para que inference.py active el fallback a Ollama."""


def _get_client() -> AsyncOpenAI:
    return AsyncOpenAI(
        base_url=settings.nvidia_base_url,
        api_key=settings.nvidia_api_key,
        timeout=settings.nvidia_timeout,
        max_retries=0,  # El retry lo maneja inference.py con lógica de fallback
    )


async def call(system_prompt: str, user_prompt: str) -> str:
    """
    Llama a NVIDIA NIM y devuelve el texto generado.

    Lanza NvidiaUnavailableError si el error es recuperable con fallback.
    Reintenta internamente hasta nvidia_max_retries ante fallas transitorias.
    """
    if not settings.nvidia_api_key:
        raise NvidiaUnavailableError("NVIDIA_API_KEY no configurada")

    client = _get_client()
    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user",   "content": user_prompt},
    ]
    extra_body = {}
    if settings.nvidia_thinking:
        extra_body["chat_template_kwargs"] = {"thinking": True}

    for attempt in range(settings.nvidia_max_retries):
        try:
            completion = await client.chat.completions.create(
                model=settings.nvidia_model,
                messages=messages,
                temperature=settings.nvidia_temperature,
                top_p=settings.nvidia_top_p,
                max_tokens=settings.nvidia_max_tokens,
                stream=False,
                **({"extra_body": extra_body} if extra_body else {}),
            )

            raw_text = completion.choices[0].message.content or ""
            if not raw_text.strip():
                raise NvidiaUnavailableError("NVIDIA returned empty response")

            logger.info(
                "NVIDIA inference OK (model=%s, tokens_used=%s)",
                settings.nvidia_model,
                getattr(completion.usage, "total_tokens", "?"),
            )
            return raw_text

        except APITimeoutError as exc:
            if attempt < settings.nvidia_max_retries - 1:
                logger.warning("NVIDIA timeout attempt %d, retrying...", attempt + 1)
                continue
            logger.warning("NVIDIA timeout after %d attempts: %s", settings.nvidia_max_retries, exc)
            raise NvidiaUnavailableError(f"NVIDIA timeout: {exc}") from exc

        except APIConnectionError as exc:
            if attempt < settings.nvidia_max_retries - 1:
                logger.warning("NVIDIA connection error attempt %d, retrying...", attempt + 1)
                continue
            logger.warning("NVIDIA connection error: %s", exc)
            raise NvidiaUnavailableError(f"NVIDIA connection error: {exc}") from exc

        except APIStatusError as exc:
            status = exc.status_code
            if status in _FALLBACK_STATUS_CODES and attempt < settings.nvidia_max_retries - 1:
                logger.warning(
                    "NVIDIA HTTP %d attempt %d, retrying...", status, attempt + 1
                )
                continue
            if status in _FALLBACK_STATUS_CODES:
                logger.warning("NVIDIA HTTP %d after retries, activating fallback", status)
                raise NvidiaUnavailableError(f"NVIDIA HTTP {status}") from exc
            # 400, 401, 403: error de configuración o prompt — no recuperable
            logger.error("NVIDIA non-recoverable error HTTP %d: %s", status, exc)
            raise
