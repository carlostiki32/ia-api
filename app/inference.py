import logging
import re
from difflib import SequenceMatcher

import httpx

from app.config import settings
from app.prompt_builder import build_system_prompt, build_user_prompt, clean_impresion
from app.providers import ollama as ollama_provider
from app.schemas import ImpresionClinicaRequest

logger = logging.getLogger(__name__)

ABBREVIATIONS = {
    "O.D.":  "__ABBR_OD__",
    "O.I.":  "__ABBR_OI__",
    "A.O.":  "__ABBR_AO__",
    "Esf.":  "__ABBR_ESF__",
    "Cil.":  "__ABBR_CIL__",
    "Eje.":  "__ABBR_EJE__",
    "D.":    "__ABBR_D__",
    "s.c.":  "__ABBR_SC__",
    "c.c.":  "__ABBR_CC__",
}
_TOKEN_TO_ABBR = {token: abbr for abbr, token in ABBREVIATIONS.items()}
_ABBR_RE = re.compile(
    "|".join(re.escape(abbr) for abbr in sorted(ABBREVIATIONS, key=len, reverse=True))
)
_TOKEN_RE = re.compile("|".join(re.escape(token) for token in _TOKEN_TO_ABBR))

LIST_BULLET_RE      = re.compile(r"^(?:[-*•])\s+")
LIST_NUMBER_RE      = re.compile(r"^\d{1,2}\.\s+(?=[A-ZÁÉÍÓÚÑ])")
MULTISPACE_RE       = re.compile(r"\s+")
SENTENCE_END_RE     = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ])")
THINK_BLOCK_RE      = re.compile(r"<think>.*?</think>", re.DOTALL)
CODEFENCE_OPEN_RE   = re.compile(r"^```\w*\n?")
CODEFENCE_CLOSE_RE  = re.compile(r"\n?```\s*$")

# Heuristico calibrado para español con tokenizer Qwen (~3.3 chars/token).
# Es mas conservador ante datos tabulares, signos (+/-) y abreviaturas clinicas.
# Se usa solo para validacion preemptiva; el conteo real viene del
# prompt_eval_count que Ollama devuelve tras la inferencia.
_CHARS_PER_TOKEN_ES = 3.3

# Prefijo que marca ValueError de oversized prompt para que main.py
# lo pueda distinguir de otros ValueError y responder 413 en vez de 500.
CONTEXT_OVERFLOW_PREFIX = "context_overflow:"


def _estimate_tokens(text: str) -> int:
    return int(len(text) / _CHARS_PER_TOKEN_ES)


def _protect_abbreviations(text: str) -> str:
    return _ABBR_RE.sub(lambda m: ABBREVIATIONS[m.group(0)], text)


def _restore_abbreviations(text: str) -> str:
    return _TOKEN_RE.sub(lambda m: _TOKEN_TO_ABBR[m.group(0)], text)


def _split_sentences(text: str) -> list[str]:
    if not text:
        return []
    clean = MULTISPACE_RE.sub(" ", text).strip()
    if not clean:
        return []
    protected = _protect_abbreviations(clean)
    parts = SENTENCE_END_RE.split(protected)
    sentences = []
    for part in parts:
        restored = _restore_abbreviations(part).strip()
        if restored:
            sentences.append(restored)
    return sentences


def _similitud(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _normalize_sentence(text: str) -> str:
    text = MULTISPACE_RE.sub(" ", text.strip())
    text = text.rstrip(".!?")
    return text.lower()


def _strip_leading_list_markers(line: str) -> str:
    line = LIST_BULLET_RE.sub("", line)
    line = LIST_NUMBER_RE.sub("", line)
    return line.strip()


def _postprocess(text: str) -> str:
    # Qwen 3.5 puede emitir <think>..</think> aun con think=False.
    text = text.strip()

    if "<think>" in text or "</think>" in text:
        logger.info("Output crudo contenia tags <think>; se remueven")

    # Caso 1: bloques completos — eliminarlos.
    text = THINK_BLOCK_RE.sub("", text).strip()

    # Caso 2: </think> residual (apertura implicita al inicio, cierre presente).
    # Conservar solo lo posterior al ultimo </think>.
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[-1].strip()

    # Caso 3: <think> sin cerrar (num_predict agoto el budget dentro del
    # razonamiento). Conservar solo lo ANTERIOR al primer <think>: si hay
    # parrafo valido antes se mantiene, si no queda vacio y cae al ValueError
    # final para disparar retry.
    if "<think>" in text:
        text = text.split("<think>", 1)[0].strip()

    text = CODEFENCE_OPEN_RE.sub("", text)
    text = CODEFENCE_CLOSE_RE.sub("", text)
    text = text.strip("`").strip()

    cleaned_lines = []
    for line in text.splitlines():
        line = _strip_leading_list_markers(line.strip())
        if line:
            cleaned_lines.append(line)

    text = " ".join(cleaned_lines)
    text = MULTISPACE_RE.sub(" ", text).strip()
    sentences = _split_sentences(text)
    text = " ".join(sentences).strip()

    if text and not text.endswith("."):
        text = f"{text}."

    if not text:
        raise ValueError("Model returned empty output after postprocessing")

    return text


def _ensure_follow_up_last(text: str, recommendation: str | None) -> str:
    """
    Agrega la recomendación de seguimiento al final del párrafo.

    El system prompt ya fue construido con effective_max = max_sentences - 1
    cuando hay recomendación, así que el modelo dejó espacio y no hay truncamiento.
    Esta función solo remueve duplicados y asegura posición final.
    """
    if not recommendation:
        return text

    follow_up = MULTISPACE_RE.sub(" ", recommendation.strip())
    if not follow_up:
        return text
    if not follow_up.endswith("."):
        follow_up = f"{follow_up}."

    sentences = _split_sentences(text)

    # Remover si el modelo ya incluyó la recomendación (detección exacta)
    normalized_follow_up = _normalize_sentence(follow_up)
    if sentences and _normalize_sentence(sentences[-1]) == normalized_follow_up:
        logger.info("Removed duplicate follow-up sentence generated by model")
        sentences = sentences[:-1]

    if sentences:
        similitud = _similitud(_normalize_sentence(sentences[-1]),
                               _normalize_sentence(follow_up))
        if similitud >= 0.70:
            logger.warning(
                "Removed semantically similar follow-up from model output "
                "(similarity: %.2f)", similitud
            )
            sentences = sentences[:-1]

    sentences.append(follow_up)

    final_text = " ".join(s.strip() for s in sentences if s.strip()).strip()
    final_text = MULTISPACE_RE.sub(" ", final_text)

    if final_text and not final_text.endswith("."):
        final_text += "."

    return final_text


async def run_inference(
    payload: ImpresionClinicaRequest,
    client: httpx.AsyncClient,
) -> str:
    """
    Orquesta la inferencia contra Ollama (qwen3.5:9b): construye los prompts,
    valida el contexto de forma preemptiva, llama al modelo y aplica el
    postprocesado + guardarraíles. Devuelve el párrafo final.
    """
    # System prompt inmutable: permite que Ollama mantenga y reutilice el KV Prefix Cache
    # de los ~1595 tokens a traves de peticiones consecutivas (reduciendo TTFT).
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(payload)

    # Logging detallado del prompt renderizado antes de enviar a inferencia
    logger.debug(
        "\n"
        "╔═══════════════════════════════════════════════════════════════════════╗\n"
        "║          PROMPT RENDERIZADO ANTES DE INFERENCIA                      ║\n"
        "╚═══════════════════════════════════════════════════════════════════════╝\n"
        "\n📋 SYSTEM PROMPT (%d caracteres, ~%d tokens):\n"
        "────────────────────────────────────────────────────────────────────────\n"
        "%s\n"
        "────────────────────────────────────────────────────────────────────────\n"
        "\n📝 USER PROMPT (%d caracteres, ~%d tokens):\n"
        "────────────────────────────────────────────────────────────────────────\n"
        "%s\n"
        "────────────────────────────────────────────────────────────────────────\n"
        "\n⚙️  TOTALES: ~%d tokens estimados\n",
        len(system_prompt),
        _estimate_tokens(system_prompt),
        system_prompt,
        len(user_prompt),
        _estimate_tokens(user_prompt),
        user_prompt,
        _estimate_tokens(system_prompt) + _estimate_tokens(user_prompt),
    )

    # Validacion preemptiva de contexto: el prompt + la salida deben caber en num_ctx.
    est_input = _estimate_tokens(system_prompt + user_prompt)
    est_total = est_input + settings.ollama_num_predict
    ctx_budget = int(settings.ollama_num_ctx * 0.95)
    if est_total > ctx_budget:
        raise ValueError(
            f"{CONTEXT_OVERFLOW_PREFIX} prompt estimado ({est_input} tok) + "
            f"salida ({settings.ollama_num_predict} tok) excede num_ctx "
            f"({settings.ollama_num_ctx}). Revisar longitud de campos "
            "clinicos de texto libre."
        )

    raw_text, _ = await ollama_provider.call(system_prompt, user_prompt, client)

    try:
        text = _postprocess(raw_text)
    except ValueError:
        logger.error(
            "Model output empty after postprocessing. Raw length: %d chars",
            len(raw_text),
        )
        raise

    text = clean_impresion(text)  # ← aquí, después de postprocess y antes de follow-up

    return _ensure_follow_up_last(text, payload.clinica.recomendacion_seguimiento)