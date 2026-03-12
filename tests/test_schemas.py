import pytest
from pydantic import ValidationError

from app.schemas import (
    AkrOjo,
    AkrSnapshot,
    ContextoPaciente,
    DatosClinica,
    GraduacionOjo,
    ImpresionClinicaRequest,
    Refraccion,
)


def test_graduacion_ojo_defaults():
    ojo = GraduacionOjo()
    assert ojo.esfera is None
    assert ojo.cilindro is None
    assert ojo.eje is None
    assert ojo.add is None
    assert ojo.av_sc is None
    assert ojo.av_cc is None


def test_graduacion_ojo_with_values():
    ojo = GraduacionOjo(esfera=-1.50, cilindro=-0.75, eje=180, av_sc="20/200", av_cc="20/20")
    assert ojo.esfera == -1.50
    assert ojo.cilindro == -0.75
    assert ojo.eje == 180
    assert ojo.av_sc == "20/200"
    assert ojo.av_cc == "20/20"


def test_akr_ojo_defaults():
    ojo = AkrOjo()
    assert ojo.esfera is None


def test_datos_clinica_uso_pantallas_valid():
    for val in ["lt2", "btw2_6", "gt6"]:
        c = DatosClinica(uso_pantallas=val)
        assert c.uso_pantallas == val


def test_datos_clinica_uso_pantallas_invalid():
    with pytest.raises(ValidationError):
        DatosClinica(uso_pantallas="invalid")


def test_datos_clinica_ojo_seco_range():
    c = DatosClinica(ojo_seco_but_seg=1)
    assert c.ojo_seco_but_seg == 1
    c = DatosClinica(ojo_seco_but_seg=15)
    assert c.ojo_seco_but_seg == 15


def test_datos_clinica_ojo_seco_out_of_range():
    with pytest.raises(ValidationError):
        DatosClinica(ojo_seco_but_seg=0)
    with pytest.raises(ValidationError):
        DatosClinica(ojo_seco_but_seg=16)


def test_datos_clinica_ppc_range():
    c = DatosClinica(ppc_cm=1)
    assert c.ppc_cm == 1
    c = DatosClinica(ppc_cm=15)
    assert c.ppc_cm == 15


def test_datos_clinica_ppc_out_of_range():
    with pytest.raises(ValidationError):
        DatosClinica(ppc_cm=0)
    with pytest.raises(ValidationError):
        DatosClinica(ppc_cm=16)


def test_contexto_paciente_defaults():
    p = ContextoPaciente()
    assert p.edad is None
    assert p.ocupacion is None
    assert p.motivo_consulta is None


def test_contexto_paciente_with_values():
    p = ContextoPaciente(edad=42, ocupacion="diseñador gráfico", motivo_consulta="cefalea frontal")
    assert p.edad == 42
    assert p.ocupacion == "diseñador gráfico"
    assert p.motivo_consulta == "cefalea frontal"


def test_full_request():
    req = ImpresionClinicaRequest(
        receta_id="test-001",
        paciente=ContextoPaciente(edad=42, ocupacion="diseñador gráfico", motivo_consulta="cefalea frontal"),
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-1.50, cilindro=-0.75, eje=180, av_sc="20/200", av_cc="20/20"),
            oi=GraduacionOjo(esfera=-1.25),
        ),
        akr=AkrSnapshot(
            od=AkrOjo(esfera=-1.75, cilindro=-0.50, eje=175),
        ),
        clinica=DatosClinica(
            uso_pantallas="gt6",
            fondo_de_ojo="papila de bordes nítidos",
            ojo_seco_but_seg=6,
            ppc_cm=8,
        ),
        tipo_lente="progresivo",
    )
    assert req.receta_id == "test-001"
    assert req.paciente.edad == 42
    assert req.refraccion.od.esfera == -1.50
    assert req.clinica.uso_pantallas == "gt6"
    assert req.tipo_lente == "progresivo"


def test_minimal_request():
    req = ImpresionClinicaRequest(receta_id="min-001")
    assert req.paciente.edad is None
    assert req.paciente.ocupacion is None
    assert req.paciente.motivo_consulta is None
    assert req.refraccion.od.esfera is None
    assert req.clinica.uso_pantallas is None
    assert req.tipo_lente is None
