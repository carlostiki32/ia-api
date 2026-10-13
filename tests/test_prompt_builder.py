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


def test_dual_format_keeps_clinical_rules_without_literal_replacement(monkeypatch):
    import app.prompt_builder as builder
    legacy = build_system_prompt()
    dual = builder.build_dual_system_prompt()
    clinical_dual = dual.split("\nREGLAS EXCLUSIVAS DEL STRING explicacion_paciente:", 1)[0]
    assert legacy.split("\n\n", 2)[2] == clinical_dual.split("\n\n", 2)[2]
    # La instrucción clínica puede cambiar sin contaminar el modo dual.
    monkeypatch.setitem(builder._OUTPUT_INSTRUCTIONS, "clinical", "Instruccion clinica actualizada.")
    assert "Instruccion clinica actualizada." in builder.build_system_prompt()
    assert "Instruccion clinica actualizada." not in builder.build_dual_system_prompt()
    assert "objeto JSON valido" in builder.build_dual_system_prompt()


def test_dual_user_prompt_reuses_clinical_generation_suffix(monkeypatch):
    import app.prompt_builder as builder
    monkeypatch.setattr(builder, "_CLINICAL_GENERATION_SUFFIX", "\n\nFinal clinico actualizado.")
    clinical = builder.build_user_prompt(_make_request())
    assert clinical.endswith("\n\nFinal clinico actualizado.")
    dual = builder.build_dual_user_prompt(clinical, {"estado": "datos_incompletos"})
    assert "Final clinico actualizado." not in dual
    assert dual.endswith("Genera los dos strings dentro del objeto JSON.")


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
    assert "su diferencia no demuestra un ajuste" in prompt
    assert "la diferencia indica el ajuste" not in prompt


def test_akr_keratometry_included():
    req = _make_request(
        akr=AkrSnapshot(
            pd=62.0,
            vd=12.0,
            ker_index=1.3375,
            od=AkrOjo(
                k1_d=41.25,
                k1_mm=8.18,
                k1_eje=180,
                k2_d=43.75,
                k2_mm=7.71,
                k2_eje=90,
                k_promedio_d=42.50,
                k_promedio_mm=7.94,
                k_cilindro=-2.50,
                k_cilindro_eje=180,
            ),
        ),
    )

    prompt = build_user_prompt(req)

    assert "Datos AKR/queratometria y refraccion final" in prompt
    assert "PD 62.00 mm" in prompt
    assert "VD 12.00 mm" in prompt
    assert "Indice queratometrico 1.3375" in prompt
    assert "Queratometria OD" in prompt
    assert "K1 41.25D/8.18mm @ 180 grados" in prompt
    assert "Cil corneal -2.50D x 180 grados" in prompt


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
    assert "Tiempo de ruptura lagrimal (BUT): 8 segundos" in prompt
    assert "Cover test: OD: Orto | OI: Orto" in prompt
    assert "Punto proximo de convergencia (PPC): 10 cm" in prompt


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
    assert "PPC de 12 cm y exoforia en OD" in prompt
    assert "insuficiencia de convergencia" not in prompt
    assert "tendencia divergente en el cover test" not in prompt
