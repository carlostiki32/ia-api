import re

import httpx

from app.config import settings
from app.prompt_builder import build_system_prompt, build_user_prompt
from app.schemas import ImpresionClinicaRequest

SENTENCE_SPLIT_RE = re.compile(r"(?<=\.)\s+")
FOLLOW_UP_KEYWORDS = (
    "seguimiento",
    "control",
    "programa",
    "cita",
    "revision",
    "consulta",
    "proxima",
    "recomienda",
    "indica",
    "sugiere",
    "meses",
    "semanas",
    "año",
    "años",
)


def _split_sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in SENTENCE_SPLIT_RE.split(text)
        if sentence.strip()
    ]


def _postprocess(text: str) -> str:
    """Clean and constrain model output."""
    text = text.strip().strip("`").strip()

    cleaned_lines = []
    for line in text.splitlines():
        line = line.strip()
        line = re.sub("^(?:-|\\*|\\u2022)\\s+", "", line)
        line = re.sub(r"^\d+\.\s+", "", line)
        if line:
            cleaned_lines.append(line)
    text = " ".join(cleaned_lines)

    sentences = _split_sentences(text)
    if len(sentences) > settings.max_sentences:
        sentences = sentences[: settings.max_sentences]
        text = " ".join(sentences)

    if text and not text.endswith("."):
        text = f"{text.rstrip()}."

    if not text:
        raise ValueError("Model returned empty output after postprocessing")

    return text


def _looks_like_follow_up(sentence: str) -> bool:
    sentence_lower = sentence.lower()
    return any(keyword in sentence_lower for keyword in FOLLOW_UP_KEYWORDS)


def _append_follow_up(text: str, recommendation: str | None) -> str:
    """Ensure the follow-up sentence is last without exceeding the sentence cap."""
    if not recommendation:
        return text

    follow_up = recommendation.strip()
    if not follow_up:
        return text
    if not follow_up.endswith("."):
        follow_up = f"{follow_up}."

    sentences = _split_sentences(text)
    if sentences and _looks_like_follow_up(sentences[-1]):
        sentences = sentences[:-1]

    if settings.max_sentences > 0 and len(sentences) >= settings.max_sentences:
        sentences = sentences[: settings.max_sentences - 1]

    sentences.append(follow_up)
    return " ".join(sentences)


async def run_inference(
    payload: ImpresionClinicaRequest,
    client: httpx.AsyncClient,
) -> str:
    user_prompt = build_user_prompt(payload)

    request_body = {
        "model": settings.ollama_model,
        "prompt": user_prompt,
        "system": build_system_prompt(),
        "stream": False,
        "options": {
            "temperature": settings.ollama_temperature,
            "num_predict": settings.ollama_num_predict,
        },
    }

    response = await client.post(
        f"{settings.ollama_url}/api/generate",
        json=request_body,
    )
    response.raise_for_status()

    data = response.json()
    raw_text = data.get("response", "")
    text = _postprocess(raw_text)

    return _append_follow_up(text, payload.clinica.recomendacion_seguimiento)
