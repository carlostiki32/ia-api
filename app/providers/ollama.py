import logging

import httpx

from app.config import settings
from app.tareas.presupuesto import verificar, politica_actual, contador, tarea_actual

logger = logging.getLogger(__name__)


def build_options() -> dict:
    return {
        "temperature":    settings.ollama_temperature,
        "num_predict":    settings.ollama_num_predict,
        "num_ctx":        min(settings.ollama_num_ctx, settings.limite_contexto_tokens, 8192),
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
    *,
    num_predict: int | None = None,
    options: dict | None = None,
    format: dict | None = None,
    max_retries: int | None = None,
    tarea: str | None = None,
    etapa: str = "clinica",
    politica: str | None = None,
    max_tokens_entrada: int | None = None,
) -> tuple[str, dict]:
    """
    Llama a Ollama /api/chat y devuelve (raw_text, response_data).
    Reintenta ante ReadTimeout o 5xx hasta ollama_max_retries.
    `num_predict` sustituye el limite de tokens de salida (reintento tras truncamiento).
    `options` se mezcla por llamada; `format=None` conserva el cuerpo clínico.
    `max_retries` sustituye el número total de intentos (1 significa sin reintentos).
    """
    options = {**build_options(), "num_ctx": min(settings.ollama_num_ctx, settings.limite_contexto_tokens, 8192), **({"num_predict": num_predict} if num_predict is not None else {}), **(options or {})}
    esperado_ctx = min(settings.ollama_num_ctx, settings.limite_contexto_tokens, 8192)
    if options.get("num_ctx") != esperado_ctx:
        raise ValueError("num_ctx no se puede sobrescribir")
    options["num_ctx"] = esperado_ctx
    politica = "estricto" if tarea == "explicacion-paciente" else politica or politica_actual.get()
    await contador.actualizar(client)
    cota = verificar(system_prompt, user_prompt, options['num_predict'], max_tokens_entrada, politica=politica)
    attempts = settings.ollama_max_retries if max_retries is None else max_retries
    request_body = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user",   "content": user_prompt},
        ],
        "stream": False,
        "think":  False,
        "options": options,
    }

    if format is not None:
        request_body["format"] = format

    data: dict = {}
    raw_text = ""

    for attempt in range(attempts):
        data = {}
        try:
            response = await client.post(
                f"{settings.ollama_url}/api/chat",
                json=request_body,
            )
            response.raise_for_status()
            data = response.json()
            raw_text = data.get("message", {}).get("content", "")

            if not isinstance(raw_text, str) or not raw_text.strip():
                raise ValueError(
                    f"Ollama returned empty or invalid content "
                    f"(done_reason={data.get('done_reason', 'unknown')})"
                )
            break

        except (httpx.ReadTimeout, ValueError) as exc:
            if attempt < attempts - 1:
                logger.warning(
                    "Ollama attempt %d failed (%s), retrying...",
                    attempt + 1, type(exc).__name__,
                )
                continue
            raise

        except httpx.HTTPStatusError as exc:
            if (
                exc.response.status_code in (500, 503)
                and attempt < attempts - 1
            ):
                logger.warning(
                    "Ollama attempt %d failed (HTTP %d), retrying...",
                    attempt + 1, exc.response.status_code,
                )
                continue
            raise

        finally:
            # Un intento físico cuenta incluso si falla, es cancelado o se reintenta.
            nombre_tarea = tarea or tarea_actual.get()
            if nombre_tarea:
                from app.tareas.nucleo import metricas
                metricas.llamada(nombre_tarea, etapa, cota, data if isinstance(data, dict) else {})

    # Metricas de la inferencia (Ollama reporta duraciones en nanosegundos).
    eval_count = data.get("eval_count", 0)
    eval_s = data.get("eval_duration", 0) / 1e9
    total_s = data.get("total_duration", 0) / 1e9
    load_s = data.get("load_duration", 0) / 1e9
    prompt_eval_s = data.get("prompt_eval_duration", 0) / 1e9
    logger.info(
        "Ollama OK: %d tok entrada, %d tok salida, %.1f tok/s, "
        "%.1fs total (%.1fs carga, %.1fs prompt), done_reason=%s",
        data.get("prompt_eval_count", 0),
        eval_count,
        (eval_count / eval_s) if eval_s > 0 else 0.0,
        total_s,
        load_s,
        prompt_eval_s,
        data.get("done_reason", "?"),
    )

    done_reason = data.get("done_reason", "")
    if done_reason == "length":
        logger.warning(
            "Ollama output truncated by num_predict limit (%d tokens). "
            "Output length: %d chars.",
            options["num_predict"],
            len(raw_text),
        )

    prompt_eval_count = data.get("prompt_eval_count", 0)
    if prompt_eval_count > cota:
        logger.warning("prompt_eval_count supera la cota: real=%d cota=%d", prompt_eval_count, cota)
    if prompt_eval_count:
        ctx_margin = settings.ollama_num_ctx - options["num_predict"] - prompt_eval_count
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
