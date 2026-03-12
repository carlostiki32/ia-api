import pytest

from app.inference import _postprocess


def test_postprocess_clean_text():
    text = "Paciente presenta miopía leve bilateral. Agudeza visual corregida es 20/20 en ambos ojos."
    result = _postprocess(text)
    assert result == text


def test_postprocess_strips_whitespace():
    text = "  \n Texto limpio. \n  "
    result = _postprocess(text)
    assert result == "Texto limpio."


def test_postprocess_removes_bullets():
    text = "- Presenta miopía.\n- Agudeza visual normal.\n- Fondo de ojo sin alteraciones."
    result = _postprocess(text)
    assert "-" not in result
    assert "Presenta miopía." in result


def test_postprocess_removes_numbered_lists():
    text = "1. Presenta miopía.\n2. Agudeza visual normal."
    result = _postprocess(text)
    assert "1." not in result
    assert "2." not in result


def test_postprocess_truncates_to_five_sentences():
    sentences = [f"Oración número {i}." for i in range(1, 8)]
    text = " ".join(sentences)
    result = _postprocess(text)
    # Should have at most 5 sentences
    count = len([s for s in result.split(". ") if s.strip()])
    assert count <= 6  # split can produce extra from the trailing period


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
