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
            cover_test="OD: Orto | OI: Orto",
            ppc_cm=10,
        )
    )
    prompt = build_user_prompt(req)
    assert "Reflejos pupilares: normales OU" in prompt
    assert "Fondo de ojo: papila nitida" in prompt
    assert "Ojo seco (BUT): 8 segundos" in prompt
    assert "Cover test: OD: Orto | OI: Orto" in prompt
    assert "PPC: 10 cm" in prompt


def test_tipo_lente_included():
    req = _make_request(tipo_lente="progresivo")
    prompt = build_user_prompt(req)
    assert "Diseno de lente prescrito: progresivo" in prompt



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


def test_user_prompt_incluye_correlacion_compuesta_y_suprime_fallbacks():
    req = _make_request(
        paciente=ContextoPaciente(motivo_consulta="cefalea y fatiga con lectura"),
        clinica=DatosClinica(ppc_cm=12, cover_test="OD: Exo y Foria | OI: Orto"),
    )

    prompt = build_user_prompt(req)

    assert "Correlaciones clinicas aplicables" in prompt
    assert "insuficiencia de convergencia" in prompt
    assert "tendencia divergente en el cover test" not in prompt
