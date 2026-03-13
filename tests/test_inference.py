import asyncio

import pytest

from app.config import settings
from app.inference import _postprocess, _split_sentences, run_inference
from app.schemas import ImpresionClinicaRequest


class DummyResponse:
    def __init__(self, payload: dict):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class DummyClient:
    def __init__(self, response_text: str):
        self.calls = []
        self.response_text = response_text

    async def post(self, url: str, json: dict):
        self.calls.append({"url": url, "json": json})
        return DummyResponse({"response": self.response_text})


def test_postprocess_clean_text():
    text = (
        "Paciente presenta miopia leve bilateral. "
        "Agudeza visual corregida es 20/20 en ambos ojos."
    )
    result = _postprocess(text)
    assert result == text


def test_postprocess_strips_whitespace():
    text = "  \n Texto limpio. \n  "
    result = _postprocess(text)
    assert result == "Texto limpio."


def test_postprocess_removes_bullets():
    text = "- Presenta miopia.\n- Agudeza visual normal.\n- Fondo de ojo sin alteraciones."
    result = _postprocess(text)
    assert "-" not in result
    assert "Presenta miopia." in result


def test_postprocess_removes_numbered_lists():
    text = "1. Presenta miopia.\n2. Agudeza visual normal."
    result = _postprocess(text)
    assert "1." not in result
    assert "2." not in result


def test_postprocess_truncates_to_configured_sentences():
    sentences = [f"Oracion numero {i}." for i in range(1, settings.max_sentences + 3)]
    text = " ".join(sentences)
    result = _postprocess(text)
    assert len(_split_sentences(result)) == settings.max_sentences


def test_postprocess_adds_trailing_period():
    text = "Texto sin punto final"
    result = _postprocess(text)
    assert result.endswith(".")


def test_postprocess_empty_raises():
    with pytest.raises(ValueError, match="empty"):
        _postprocess("")


def test_postprocess_whitespace_only_raises():
    with pytest.raises(ValueError, match="empty"):
        _postprocess("   \n\n  ")


def test_postprocess_strips_code_fences():
    text = "```\nTexto dentro de fences.\n```"
    result = _postprocess(text)
    assert "```" not in result
    assert "Texto dentro de fences." in result


def test_run_inference_uses_shared_client_and_config():
    payload = ImpresionClinicaRequest(
        receta_id="test-001",
        refraccion={"od": {"esfera": -1.25}},
        clinica={"recomendacion_seguimiento": "Control en 6 meses"},
    )
    client = DummyClient(
        "Hallazgo principal. Hallazgo secundario. Control en 3 meses."
    )

    result = asyncio.run(run_inference(payload, client))

    assert client.calls
    request = client.calls[0]
    assert request["url"] == f"{settings.ollama_url}/api/generate"
    assert request["json"]["model"] == settings.ollama_model
    assert request["json"]["options"]["temperature"] == settings.ollama_temperature
    assert request["json"]["options"]["num_predict"] == settings.ollama_num_predict
    assert f"Maximo {settings.max_sentences} oraciones" in request["json"]["system"]
    assert result.endswith("Control en 6 meses.")
    assert "Control en 3 meses." not in result
    assert len(_split_sentences(result)) <= settings.max_sentences
