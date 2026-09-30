"""Aceptacion #12: episodios, ocurrencias y conservacion de avisos independientes."""
import json
from pathlib import Path

import pytest

from app.correlaciones.registry import evaluar_correlaciones_con_nombres
from app.correlaciones.pupilas_motilidad import (
    _ocurrencias_oculares,
    _PTOSIS_MAP,
    _pupilas_ocurrencias,
)
from app.schemas import ImpresionClinicaRequest


_ID = "horner_o_tercer_par_sospecha"
_CASOS = [c for c in json.loads((Path(__file__).parents[1] / "auditoria/2026-09-21/casos.json").read_text(encoding="utf-8"))
          if c["id"].startswith("C12-")]
_AUSENTES = {2, 6, 9, 10, 12, 13, 15, 20, 22, 23, 26, 29, 31}
_URGENTES = {4, 5, 7, 8, 11, 25, 27, 28, 30, 32, 33}


def _req(pupilas=None, anexos=None, motilidad=None, motivo=None, seguimiento=None):
    assert all(v is None or len(v) <= 255 for v in (pupilas, anexos, motilidad))
    assert motivo is None or len(motivo) <= 1000
    return ImpresionClinicaRequest.model_validate({
        "receta_id": "aceptacion-c12",
        "paciente": {"motivo_consulta": motivo},
        "clinica": {"reflejos_pupilares": pupilas, "anexos_oculares": anexos,
                    "motilidad_ocular": motilidad, "recomendacion_seguimiento": seguimiento},
        "tipo_lente": "monofocal",
    })


def _act(**kwargs):
    return dict(evaluar_correlaciones_con_nombres(_req(**kwargs)))


@pytest.mark.parametrize("caso", _CASOS, ids=lambda c: c["id"])
def test_c12_reproduce_33_casos_contrato(caso):
    datos = {k: v for k, v in caso["entrada"].items() if k != "lente"}
    activas = _act(**datos)
    numero = int(caso["id"].split("-")[1])
    assert (_ID in activas) == (numero not in _AUSENTES)
    if _ID in activas:
        texto = activas[_ID]
        assert ("Hallazgo urgente:" in texto) == (numero in _URGENTES)
        assert not any(diagnostico in texto.lower() for diagnostico in ("horner", "iii par", "aneurisma", "diseccion"))
        if numero in _URGENTES:
            assert "valoracion medica el mismo dia" in texto
        else:
            assert "valoracion especializada" in texto
    if numero in (14, 16, 21, 30):
        assert "ptosis OI" in activas[_ID]
        assert "miosis OI" in activas[_ID]
        assert "OD" not in activas[_ID]
    if numero in (17, 18):
        assert "anisocoria OD" not in activas[_ID]
        assert "anisocoria OI" not in activas[_ID]
    if numero == 5:
        assert "limitacion de la motilidad OD" in activas[_ID]
        assert "anisocoria" not in activas[_ID]
    if numero == 22:
        assert "Hallazgo urgente:" in activas["pupilas_alteradas"]
        assert "ptosis" not in activas["pupilas_alteradas"]
    if numero == 33:
        assert "defecto pupilar aferente relativo OI" in activas["pupilas_alteradas"]
        assert "miosis" not in activas["pupilas_alteradas"]


@pytest.mark.parametrize("anexos", ["Proptosis OD", "Sin ptosis OD", "OD: ptosis ausente", "Madre con ptosis OD"])
def test_c12_no_inventa_ptosis_ni_sujeto(anexos):
    assert _ID not in _act(pupilas="Miosis OD nueva", anexos=anexos, motivo="Dolor cervical nuevo")


@pytest.mark.parametrize("pupilas", [
    "Midriasis OD farmacologica", "OD: midriasis farmacologica", "Midriasis farmacologica OD",
    "Midriasis OD por tropicamida", "Midriasis OD tras aplicacion de tropicamida",
])
def test_c12_farmaco_causal_se_filtra_con_cualquier_posicion_ocular(pupilas):
    assert _ID not in _act(pupilas=pupilas, anexos="Ptosis OD")


@pytest.mark.parametrize("pupilas", [
    "Midriasis OD no farmacologica", "OD: midriasis sin tropicamida",
    "Midriasis OD espontanea; prueba con pilocarpina pendiente",
    "Midriasis OD; refiere usar tropicamida previamente",
])
def test_c12_mencionar_farmaco_o_negar_causa_no_excluye_hallazgo(pupilas):
    assert _ID in _act(pupilas=pupilas, anexos="Ptosis OD nueva")


@pytest.mark.parametrize("ptosis", ["Ptosis", "Blefaroptosis", "Caida del parpado", "Parpado caido"])
def test_c12_sinonimos_palpebrales_afirmados(ptosis):
    assert _ID in _act(pupilas="Miosis OD", anexos=f"{ptosis} OD")


@pytest.mark.parametrize("pupilas", [
    "Sin miosis OD; miosis OI", "OD: sin miosis, OI: miosis",
    "Miosis OD: ausente. Miosis OI: presente", "Miosis OD farmacologica, miosis OI",
])
def test_c12_lado_de_ocurrencia_valida_nunca_del_primer_match(pupilas):
    assert _ID not in _act(pupilas=pupilas, anexos="Ptosis OD")
    texto = _act(pupilas=pupilas, anexos="Ptosis OI")[_ID]
    assert "miosis OI" in texto and "OD" not in texto


def test_c12_ocurrencias_conservan_procedencia_intervalo_y_estado():
    texto = "OD: sin ptosis; OI: ptosis no congenita, nueva"
    ocurrencias = _ocurrencias_oculares(texto, _PTOSIS_MAP, "anexos_oculares")
    assert len(ocurrencias) == 2
    assert [o.afirmado for o in ocurrencias] == [False, True]
    assert [o.ojo for o in ocurrencias] == ["OD", "OI"]
    assert ocurrencias[1].evolucion == "cambio reciente"
    assert all(texto.lower()[o.inicio:o.fin] == "ptosis" for o in ocurrencias)
    assert all(o.origen == "anexos_oculares" for o in ocurrencias)


def test_c12_edad_de_un_signo_no_fecha_el_otro():
    texto = _act(pupilas="Miosis OD nueva", anexos="Ptosis OD congenita")[_ID]
    assert "Hallazgo urgente:" in texto
    assert "ptosis OD de evolucion antigua descrita" in texto
    assert "miosis OD de inicio reciente" in texto


@pytest.mark.parametrize("motivo", ["Cefalea cronica sin cambios", "Sin dolor cervical ni cefalea", "Revision anual hoy"])
def test_c12_motivo_sin_cambio_no_crea_urgencia(motivo):
    texto = _act(pupilas="Miosis OD", anexos="Ptosis OD", motivo=motivo)[_ID]
    assert "Hallazgo urgente:" not in texto
    assert "inicio reciente" not in texto


def test_c12_estabilidad_antigua_de_toda_combinacion_no_urgencia():
    texto = _act(pupilas="Miosis OD desde hace 10 anos sin cambios",
                 anexos="Ptosis OD desde hace 10 anos sin cambios")[_ID]
    assert "Hallazgo urgente:" not in texto
    assert "benigna" not in texto


@pytest.mark.parametrize("motilidad", ["Limitacion de aduccion OI", "Limitacion de aduccion", "Sin limitacion de aduccion OD"])
def test_c12_no_inventa_concordancia_motor(motilidad):
    assert _ID not in _act(pupilas="Reflejo fotomotor, consensual, acomodativo",
                          anexos="Ptosis OD nueva", motilidad=motilidad)


def test_c12_diplopia_nueva_con_ptosis_nueva_sin_anormalidad_pupilar():
    texto = _act(pupilas="Reflejo fotomotor, consensual, acomodativo",
                 anexos="Ptosis OD nueva", motivo="Diplopia nueva")[_ID]
    assert "Hallazgo urgente:" in texto and "diplopia referida" in texto
    assert "anisocoria" not in texto and "paresia" not in texto


def test_c12_preserva_anomalia_reactiva_independiente():
    textos = _act(pupilas="Miosis OD. Pupila no reactiva OI", anexos="Ptosis OD nueva")
    assert "pupila no reactiva OI" in textos["pupilas_alteradas"]
    assert "miosis" not in textos["pupilas_alteradas"]


def test_c12_comparacion_no_se_transforma_en_miosis_relativa():
    req = _req(pupilas="Anisocoria OD > OI", anexos="Ptosis OI")
    ocurrencias = _pupilas_ocurrencias(req.clinica)
    assert [(o.hallazgo, o.ojo) for o in ocurrencias] == [("anisocoria", "AMBOS")]
    texto = dict(evaluar_correlaciones_con_nombres(req))[_ID]
    assert "miosis" not in texto


def test_c12_bilateral_se_describe_sin_convertir_a_unilateral():
    texto = _act(pupilas="Miosis bilateral", anexos="Ptosis bilateral")[_ID]
    assert "ptosis bilateral" in texto and "miosis bilateral" in texto
    assert " OD" not in texto and " OI" not in texto


def test_c12_no_importa_sintoma_contralateral_al_par():
    texto = _act(pupilas="Miosis OD", anexos="Ptosis OD", motivo="Dolor ocular izquierdo nuevo")[_ID]
    assert "Hallazgo urgente:" not in texto and "dolor" not in texto


def test_c12_negar_fisiologia_no_niega_anisocoria():
    assert _ID in _act(pupilas="Anisocoria no fisiologica", anexos="Ptosis OD")


def test_c12_contexto_mandibular_no_suprime_dpar_en_otra_clausula():
    textos = _act(pupilas="Miosis OD. DPAR OI. Fenomeno de Marcus Gunn mandibulopalpebral",
                  anexos="Ptosis OD nueva")
    assert "defecto pupilar aferente relativo OI" in textos["pupilas_alteradas"]


def test_c12_motivo_fecha_ptosis_motora_del_mismo_ojo():
    texto = _act(anexos="Ptosis OD", motilidad="Limitacion de aduccion OD",
                 motivo="Ptosis OD nueva")[_ID]
    assert "ptosis OD de inicio reciente" in texto
    assert "Hallazgo urgente:" in texto


def test_c12_motivo_con_fecha_de_otro_ojo_no_fecha_ptosis_motora():
    assert _ID not in _act(anexos="Ptosis OD", motilidad="Limitacion de aduccion OD",
                          motivo="Ptosis OI nueva")


def test_c12_empeoramiento_en_motivo_no_se_pierde_por_ptosis_cronica():
    texto = _act(anexos="Ptosis cronica OD", pupilas="Miosis OD",
                 motivo="Ptosis OD que empeoro hoy")[_ID]
    assert "Hallazgo urgente:" in texto
    assert "empeoramiento documentado" in texto


def test_c12_motivo_fecha_pupila_sin_duplicarla_en_13():
    textos = _act(anexos="Ptosis OD", pupilas="Miosis OD", motivo="Miosis OD de inicio hoy")
    assert "miosis OD de inicio reciente" in textos[_ID]
    assert "pupilas_alteradas" not in textos
