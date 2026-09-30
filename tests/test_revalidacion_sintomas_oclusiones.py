"""Regresiones de contexto clinico para las ordenes #2 y #3."""
import pytest

from app.correlaciones.fondo_de_ojo import (
    _eval_sintomas_traccion, _eval_fondo_oclusion,
    _ojo_tiene_oclusion_vascular_retiniana,
)
from tests.test_auditoria_correlaciones import _req, activas, alertas_h01


def test_oclusion_no_transfiere_lado_de_hemorragia_independiente():
    fondo = "Hemorragia retiniana OD y OVCR OI"
    assert not _ojo_tiene_oclusion_vascular_retiniana(fondo, "OD")
    assert _ojo_tiene_oclusion_vascular_retiniana(fondo, "OI")


@pytest.mark.parametrize("motivo,nivel", [
    ("Moscas volantes de siempre. Revision de lentes. Cefalea desde ayer.", None),
    ("Fotopsias. Revision de lentes. Cefalea cronica de siempre.", "C"),
    ("Niega moscas volantes desde ayer. Fotopsias ocasionales sin tiempo conocido.", "C"),
    ("Fotopsias, desde ayer.", "B"),
    ("Desde ayer, fotopsias.", "B"),
    ("Fotopsias de siempre y miodesopsias nuevas.", "B"),
    ("Perdida visual subita OD desde hoy", "A"),
    ("Perdida subita de vision OD esta manana", "A"),
    ("Perdida brusca visual en OI", "A"),
    ("Perdida de vision repentina OD", "A"),
    ("Antecedente de perdida subita de vision hace 10 anos, resuelta.", None),
    ("Fotopsias resueltas. Revision rutinaria.", None),
    ("Antecedente de cortina visual resuelta. Ahora fotopsias desde ayer.", "B"),
    ("Niega perdida visual subita.", None),
    ("Perdida visual subita: negativo.", None),
    ("No tiene fotopsias. Fotopsias en contexto de aura migranosa.", None),
    ("No tengo perdida de vision. Mi padre tuvo perdida visual subita hoy.", None),
    ("Mi madre presenta cortina visual desde hoy. Yo acudo a revision sin molestias.", None),
    ("Descartar perdida visual subita en el estudio actual.", None),
    ("Posibles fotopsias desde ayer, aun por confirmar.", None),
    ("Mi madre tuvo fotopsias. Ahora yo tengo miodesopsias nuevas desde ayer.", "B"),
])
def test_traccion_temporalidad_y_negacion_por_hallazgo(motivo, nivel):
    req = _req(motivo=motivo, lente="monofocal")
    assert _eval_sintomas_traccion(req)["nivel"] == nivel
    h01 = alertas_h01(motivo=motivo, lente="monofocal")
    assert ("sintomas_alarma_traccion_vitreoretina" in h01) == (nivel in ("A", "B"))


def test_traccion_no_presta_cronologia_a_lattice():
    kw = dict(
        fondo="Lattice OI",
        motivo="Moscas volantes de siempre. Revision de lentes. Cefalea desde ayer.",
        lente="monofocal",
    )
    salida = activas(**kw)
    assert not salida["fondo_periferico_riesgo"].startswith("Hallazgo urgente:")
    assert "sintomas_alarma_traccion_vitreoretina" not in salida
    assert "fondo_periferico_riesgo" not in alertas_h01(**kw)


def test_traccion_no_llama_reciente_a_fotopsia_antigua():
    kw = dict(motivo="Fotopsias de siempre y miodesopsias nuevas.", lente="monofocal")
    texto = activas(**kw)["sintomas_alarma_traccion_vitreoretina"]
    assert "miodesopsias de inicio reciente" in texto
    assert "fotopsias" not in texto


@pytest.mark.parametrize("fondo,subtipo", [
    ("Antecedente de catarata operada con lente intraocular centrada y transparente OD y OVCR OI", "VENOSA"),
    ("OVCR estable desde hace anos con control de presion intraocular programado en dos dias", "SECUELA"),
    ("OVCR estable, cita en dos dias", "SECUELA"),
    ("Antecedente de OVCR aguda hace 2 anos", "SECUELA"),
    ("OVCR de inicio reciente OD", "VENOSA"),
    ("OACR aguda OD", "ARTERIAL"),
    ("Oclusion de la vena central de la retina OD", "VENOSA"),
    ("Trombosis de rama venosa OD", "VENOSA"),
    ("Trombosis de arteria carotida izquierda; retina aplicada sin lesiones", None),
    ("Trombosis de vena yugular", None),
    ("Oclusion de arteria cerebral media", None),
    ("Oclusion arterial sin localizacion documentada", None),
    ("Sin evidencia de oclusion venosa temporal", None),
    ("OACR: negativo", None),
    ("OACR descartada", None),
    ("Antecedente de OVCR OD. OACR aguda OI", "ARTERIAL"),
])
def test_occlusion_contexto_del_evento(fondo, subtipo):
    req = _req(fondo=fondo, lente="monofocal")
    assert _eval_fondo_oclusion(req)["subtipo"] == subtipo
    urgente = subtipo in ("ARTERIAL", "VENOSA", "SIN_TIPIFICAR")
    assert ("fondo_oclusion_vascular_urgente" in alertas_h01(
        fondo=fondo, lente="monofocal"
    )) == urgente


def test_occlusion_sospechada_no_es_causa_organica_demostrada():
    fondo = "Hemorragias en llama en 4 cuadrantes OD, descartar OVCR OD"
    assert "fondo_oclusion_vascular_urgente" in activas(fondo=fondo, lente="monofocal")
    assert not _ojo_tiene_oclusion_vascular_retiniana(fondo, "OD")
    assert _ojo_tiene_oclusion_vascular_retiniana("OVCR OD", "OD")
    assert not _ojo_tiene_oclusion_vascular_retiniana("OVCR OD", "OI")
