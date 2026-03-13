from app.config import settings
from app.prompt_builder import build_system_prompt, build_user_prompt
from app.schemas import (
    AkrOjo,
    AkrSnapshot,
    ContextoPaciente,
    DatosClinica,
    GraduacionOjo,
    ImpresionClinicaRequest,
    Refraccion,
)


def _make_request(**kwargs):
    defaults = {"receta_id": "test-001"}
    defaults.update(kwargs)
    return ImpresionClinicaRequest(**defaults)


def test_system_prompt_has_rules():
    prompt = build_system_prompt()
    assert f"Maximo {settings.max_sentences} oraciones" in prompt
    assert "NO agregues informacion" in prompt
    assert "tercera persona" in prompt


def test_user_prompt_with_refraction():
    req = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(
                esfera=-2.00,
                cilindro=-0.50,
                eje=90,
                av_sc="20/100",
                av_cc="20/20",
            ),
        )
    )
    prompt = build_user_prompt(req)
    assert "OD" in prompt
    assert "Esf -2.00" in prompt
    assert "Cil -0.50" in prompt
    assert "Eje 90 grados" in prompt
    assert "AV s/c 20/100" in prompt
    assert "AV c/c 20/20" in prompt


def test_user_prompt_omits_null_fields():
    req = _make_request(clinica=DatosClinica(uso_pantallas="gt6"))
    prompt = build_user_prompt(req)
    assert "mas de 6 horas diarias" in prompt
    assert "Anexos oculares" not in prompt
    assert "Fondo de ojo" not in prompt


def test_uso_pantallas_mapping():
    for value, expected in [
        ("lt2", "menos de 2 horas diarias"),
        ("btw2_6", "entre 2 y 6 horas diarias"),
        ("gt6", "mas de 6 horas diarias"),
    ]:
        req = _make_request(clinica=DatosClinica(uso_pantallas=value))
        prompt = build_user_prompt(req)
        assert expected in prompt


def test_user_prompt_ends_with_order_instruction():
    req = _make_request(refraccion=Refraccion(od=GraduacionOjo(esfera=-1.00)))
    prompt = build_user_prompt(req)
    assert "Redacta la impresion clinica en exactamente este orden:" in prompt
    assert "1. Motivo de consulta y agudeza visual sin correccion" in prompt
    assert prompt.endswith(
        "Redacta cada punto como una oracion continua, sin numeracion ni bullets."
    )


def test_akr_comparison_included():
    req = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-2.00, cilindro=-0.50, eje=90),
        ),
        akr=AkrSnapshot(
            od=AkrOjo(esfera=-2.25, cilindro=-0.75, eje=85),
        ),
    )
    prompt = build_user_prompt(req)
    assert "AKR OD" in prompt
    assert "Rx final OD" in prompt
    assert "ajuste del examen subjetivo" in prompt


def test_clinical_fields_included():
    req = _make_request(
        clinica=DatosClinica(
            reflejos_pupilares="normales OU",
            fondo_de_ojo="papila nitida",
            ojo_seco_but_seg=8,
            cover_test="ortoforia",
            ppc_cm=10,
        )
    )
    prompt = build_user_prompt(req)
    assert "Reflejos pupilares: normales OU" in prompt
    assert "Fondo de ojo: papila nitida" in prompt
    assert "Ojo seco (BUT): 8 segundos" in prompt
    assert "Cover test: ortoforia" in prompt
    assert "PPC: 10 cm" in prompt


def test_tipo_lente_included():
    req = _make_request(tipo_lente="progresivo")
    prompt = build_user_prompt(req)
    assert "Diseno de lente prescrito: progresivo" in prompt


def test_recomendacion_seguimiento():
    req = _make_request(
        clinica=DatosClinica(recomendacion_seguimiento="Control en 6 meses")
    )
    prompt = build_user_prompt(req)
    assert "Recomendacion de seguimiento: Control en 6 meses" in prompt


def test_paciente_context_included():
    req = _make_request(
        paciente=ContextoPaciente(
            edad=42,
            ocupacion="disenador grafico",
            motivo_consulta="cefalea frontal",
        )
    )
    prompt = build_user_prompt(req)
    assert "Edad: 42 anos" in prompt
    assert "Ocupacion: disenador grafico" in prompt
    assert "Motivo de consulta: cefalea frontal" in prompt
    assert "Contexto del paciente:" in prompt


def test_paciente_context_omitted_when_null():
    req = _make_request()
    prompt = build_user_prompt(req)
    assert "Contexto del paciente" not in prompt


def test_paciente_partial_fields():
    req = _make_request(paciente=ContextoPaciente(edad=65))
    prompt = build_user_prompt(req)
    assert "Edad: 65 anos" in prompt
    assert "Ocupacion: " not in prompt
    assert "Motivo de consulta: " not in prompt


def test_empty_request_still_has_instruction():
    req = _make_request()
    prompt = build_user_prompt(req)
    assert "Redacta la impresion clinica en exactamente este orden:" in prompt
