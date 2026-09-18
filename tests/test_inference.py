import asyncio

import pytest

from app.config import settings
from app.inference import (
    CONTEXT_OVERFLOW_PREFIX,
    _ensure_emergency_preserved,
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
    assert _estimate_tokens("x" * 33) == 10
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


def test_ensure_emergency_preserved_when_already_present():
    payload = ImpresionClinicaRequest(
        receta_id="test-emerg-ok",
        clinica={"fondo_de_ojo": "Desgarro retiniano en herradura en sector temporal"},
    )
    text = "Se detecta desgarro retiniano periferico que amerita valoracion urgente por retinologo."
    result = _ensure_emergency_preserved(text, payload)
    assert result == text


def test_ensure_emergency_preserved_injects_if_dropped():
    payload = ImpresionClinicaRequest(
        receta_id="test-emerg-dropped",
        clinica={"fondo_de_ojo": "Desgarro retiniano en herradura en sector temporal"},
    )
    text = "Paciente acude a control optometrico rutinario. Se prescribe correccion aerea."
    result = _ensure_emergency_preserved(text, payload)
    assert "Hallazgo urgente" in result or "desgarro" in result.lower()
    assert result.startswith("Paciente acude a control optometrico rutinario.")


def test_h01_emergency_negation_purged_and_injected():
    """H01: La guarda de urgencias no debe aceptar la negacion del hallazgo ni de la urgencia."""
    payload = ImpresionClinicaRequest(
        receta_id="test-h01-neg",
        clinica={"fondo_de_ojo": "desgarro retiniano"},
    )
    text = "No hay desgarro ni urgencia."
    result = _ensure_emergency_preserved(text, payload)
    assert "No hay desgarro" not in result
    assert "ni urgencia" not in result
    assert "Hallazgo urgente" in result
    assert "desgarro retiniano" in result.lower()
    assert "urgente" in result.lower()


def test_h01_emergency_incompatible_timeframe_purged():
    """H01: La guarda de urgencias debe purgar plazos rutinarios incompatibles (ej. 'Control anual.')."""
    payload = ImpresionClinicaRequest(
        receta_id="test-h01-timeframe",
        clinica={"fondo_de_ojo": "desgarro retiniano"},
    )
    text = "Se observa desgarro retiniano. Control anual."
    result = _ensure_emergency_preserved(text, payload)
    assert "Control anual" not in result
    assert "Hallazgo urgente" in result or "urgente" in result.lower()
    assert "retinolog" in result.lower()


def test_h01_emergency_omitted_action_injected():
    """H01: Si el modelo menciona la patologia pero omite la conducta de urgencia, se debe inyectar la conducta."""
    payload = ImpresionClinicaRequest(
        receta_id="test-h01-omitted-action",
        clinica={"fondo_de_ojo": "desgarro retiniano"},
    )
    text = "Se documenta desgarro retiniano en la periferia temporal."
    result = _ensure_emergency_preserved(text, payload)
    assert "urgente" in result.lower()
    assert "retinolog" in result.lower()


def test_h01_emergency_conflicting_laterality_purged():
    """H01: Si el hallazgo es en OD y el modelo lo adjudica a OI, debe corregirse."""
    payload = ImpresionClinicaRequest(
        receta_id="test-h01-laterality",
        clinica={"fondo_de_ojo": "OD: desgarro retiniano. OI: retina aplicada sin lesiones."},
    )
    text = "En ojo izquierdo se aprecia desgarro retiniano que amerita valoracion urgente."
    result = _ensure_emergency_preserved(text, payload)
    assert "ojo izquierdo" not in result.lower()
    assert "desgarro retiniano" in result.lower()
    assert "urgente" in result.lower()


def test_h01_emergency_suppresses_routine_follow_up():
    """H01: Una recomendacion rutinaria de seguimiento en el payload no debe contradecir una alerta de urgencia."""
    from app.inference import _ensure_follow_up_last
    payload = ImpresionClinicaRequest(
        receta_id="test-h01-followup",
        clinica={
            "fondo_de_ojo": "desgarro retiniano",
            "recomendacion_seguimiento": "Control anual en 1 año.",
        },
    )
    text = "Hallazgo urgente: en la retina periferica se documenta desgarro retiniano, que amerita valoracion retinologica urgente y posible tratamiento profilactico."
    result = _ensure_follow_up_last(text, payload.clinica.recomendacion_seguimiento, payload=payload)
    assert "Control anual" not in result
    assert "1 año" not in result
    assert "urgente" in result


def test_h02_dpar_in_pupilas_alteradas_preserved():
    """H02: El DPAR aislado en pupilas_alteradas debe preservarse y purgar 'Examen normal.'."""
    payload = ImpresionClinicaRequest(
        receta_id="test-h02-dpar",
        clinica={"reflejos_pupilares": "DPAR positivo en OD"},
    )
    text = "Examen normal."
    result = _ensure_emergency_preserved(text, payload)
    assert "Examen normal" not in result
    assert "defecto pupilar aferente relativo" in result.lower() or "dpar" in result.lower()
    assert "urgente" in result.lower()


def test_h02_sintomas_alarma_traccion_vitreoretina_preserved():
    """H02: sintomas_alarma_traccion_vitreoretina debe preservarse y purgar 'Control anual.'."""
    payload = ImpresionClinicaRequest(
        receta_id="test-h02-traccion",
        paciente={"motivo_consulta": "destellos y miodesopsias agudas de inicio reciente"},
    )
    text = "Paciente acude por molestias. Se recomienda control anual."
    result = _ensure_emergency_preserved(text, payload)
    assert "control anual" not in result.lower()
    assert "traccion vitreorretiniana" in result.lower() or "midriasis" in result.lower() or "desgarros" in result.lower()


def test_h02_multiple_emergencies_combined():
    """H02: Multiples urgencias (desgarro retiniano + DPAR) deben preservarse simultaneamente."""
    payload = ImpresionClinicaRequest(
        receta_id="test-h02-multi",
        clinica={
            "fondo_de_ojo": "desgarro retiniano en herradura",
            "reflejos_pupilares": "DPAR positivo",
        },
    )
    text = "Paciente acude a revision. Examen normal."
    result = _ensure_emergency_preserved(text, payload)
    assert "Examen normal" not in result
    # Ambas urgencias deben estar presentes en el parrafo final
    assert "desgarro retiniano" in result.lower()
    assert "defecto pupilar aferente relativo" in result.lower() or "dpar" in result.lower()
    assert "urgente" in result.lower()


def test_h02_dpar_already_preserved():
    """H02: Si DPAR ya fue redactado con urgencia adecuada, se preserva sin inyeccion duplicada."""
    payload = ImpresionClinicaRequest(
        receta_id="test-h02-dpar-ok",
        clinica={"reflejos_pupilares": "DPAR positivo"},
    )
    text = "Se identifica defecto pupilar aferente relativo que amerita evaluacion neurooftalmologica urgente."
    result = _ensure_emergency_preserved(text, payload)
    assert result == text


def test_h02_false_normality_purged():
    """H02: Afirmaciones de normalidad frente a una urgencia activa deben ser purgadas."""
    payload = ImpresionClinicaRequest(
        receta_id="test-h02-normality",
        clinica={"fondo_de_ojo": "papiledema marcado con borramiento de bordes"},
    )
    text = "Fondo de ojo normal. Sin hallazgos patológicos."
    result = _ensure_emergency_preserved(text, payload)
    assert "normal" not in result.lower()
    assert "sin hallazgos" not in result.lower()
    assert "papila" in result.lower() or "papiledema" in result.lower() or "edema de papila" in result.lower()
    assert "urgente" in result.lower()


def test_h03_lattice_con_destellos_inference_guard_purges_contradiction():
    """H03: En paciente con lattice y destellos nuevos, purga contradicciones y asegura urgencia."""
    payload = ImpresionClinicaRequest(
        receta_id="test-h03-lattice-urgente",
        paciente={"motivo_consulta": "destellos nuevos desde ayer"},
        clinica={"fondo_de_ojo": "degeneracion lattice"},
    )
    text = "Fondo de ojo normal. Se recomienda control anual."
    result = _ensure_emergency_preserved(text, payload)
    assert "normal" not in result.lower()
    assert "control anual" not in result.lower()
    assert "urgente" in result.lower()
    assert "lattice" in result.lower() or "traccion vitreorretiniana" in result.lower()


def test_h03_lattice_con_destellos_already_preserved():
    """H03: Si el texto ya integra la urgencia de lattice y traccion, se preserva adecuadamente."""
    payload = ImpresionClinicaRequest(
        receta_id="test-h03-lattice-ok",
        paciente={"motivo_consulta": "destellos nuevos desde ayer"},
        clinica={"fondo_de_ojo": "degeneracion lattice"},
    )
    text = "Se identifica degeneracion lattice en la retina periferica con destellos de traccion que ameritan valoracion retinologica urgente con examen bajo midriasis."
    result = _ensure_emergency_preserved(text, payload)
    assert "urgente" in result.lower()
    assert "lattice" in result.lower()




