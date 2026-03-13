import re

import httpx

from app.config import settings
from app.prompt_builder import SYSTEM_PROMPT, build_user_prompt
from app.schemas import ImpresionClinicaRequest

MAX_SENTENCES = 10


def _postprocess(text: str) -> str:
    """Clean and constrain model output."""
    # Strip whitespace and special chars at edges
    text = text.strip().strip("```").strip()

    # Remove bullet/list markers and join as prose
    lines = text.splitlines()
    cleaned = []
    for line in lines:
        line = line.strip()
        # Remove bullet markers
        line = re.sub(r"^[-•*]\s+", "", line)
        # Remove numbered list markers
        line = re.sub(r"^\d+\.\s+", "", line)
        if line:
            cleaned.append(line)
    text = " ".join(cleaned)

    # Count sentences and truncate if needed
    sentences = re.split(r"(?<=\.)\s+", text)
    sentences = [s for s in sentences if s.strip()]
    if len(sentences) > MAX_SENTENCES:
        sentences = sentences[:MAX_SENTENCES]
        text = " ".join(sentences)

    # Ensure ends with period
    if text and not text.endswith("."):
        text = text.rstrip() + "."

    if not text:
        raise ValueError("Model returned empty output after postprocessing")

    return text


async def run_inference(payload: ImpresionClinicaRequest) -> str:
    user_prompt = build_user_prompt(payload)

    request_body = {
        "model": settings.ollama_model,
        "prompt": user_prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "options": {
            "temperature": 0.1,
            "num_predict": 768,
        },
    }

    async with httpx.AsyncClient(timeout=settings.ollama_timeout) as client:
        response = await client.post(
            f"{settings.ollama_url}/api/generate",
            json=request_body,
        )
        response.raise_for_status()

    data = response.json()
    raw_text = data.get("response", "")
    text = _postprocess(raw_text)

# Garantizar que recomendacion_seguimiento aparece al final, siempre
    recomendacion = payload.clinica.recomendacion_seguimiento
    if recomendacion:
        seguimiento = recomendacion if recomendacion.endswith(".") else recomendacion + "."
        sentences = re.split(r"(?<=\.)\s+", text)
        sentences = [s for s in sentences if s.strip()]
        last = sentences[-1].lower() if sentences else ""
        skip_last = any(w in last for w in [
            "seguimiento", "control", "programa", "cita",
            "revisión", "revision", "consulta", "próxima", "proxima",
            "recomienda", "indica", "sugiere", "meses", "semanas", "año", "anos"
        ])
        if skip_last:
            sentences = sentences[:-1]
        text = " ".join(sentences).rstrip(".") + ". " + seguimiento

    return text 