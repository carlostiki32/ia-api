import asyncio

import pytest

from app.config import settings
from app.inference import (
    CONTEXT_OVERFLOW_PREFIX,
    _estimate_tokens,
    _postprocess,
    run_inference,
)
from app.schemas import ImpresionClinicaRequest


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


def test_estimate_tokens_scales_with_length():
    assert _estimate_tokens("") == 0
    assert _estimate_tokens("x" * 35) == 10
    # Monotonicidad basica
    assert _estimate_tokens("x" * 1000) > _estimate_tokens("x" * 500)


class _UnusedClient:
    """El cliente no debe ser invocado: la validacion preemptiva corta antes."""

    async def post(self, url, json):  # pragma: no cover - no debe llamarse
        raise AssertionError(
            "run_inference llamo a Ollama a pesar de exceder num_ctx"
        )


def test_run_inference_rejects_oversized_prompt(monkeypatch):
    # Forzar un num_ctx minusculo para que cualquier prompt realista excede.
    monkeypatch.setattr(settings, "ollama_num_ctx", 256)
    monkeypatch.setattr(settings, "ollama_num_predict", 128)

    # Payload minimamente valido para pasar has_clinical_data y construir prompt.
    payload = ImpresionClinicaRequest(
        receta_id="test-overflow",
        refraccion={"od": {"esfera": -1.25}},
        clinica={
            "anexos_oculares": "x" * 255,
            "fondo_de_ojo": "y" * 255,
        },
    )

    with pytest.raises(ValueError) as excinfo:
        asyncio.run(run_inference(payload, _UnusedClient()))

    msg = str(excinfo.value)
    assert msg.startswith(CONTEXT_OVERFLOW_PREFIX)
    assert "excede num_ctx" in msg
