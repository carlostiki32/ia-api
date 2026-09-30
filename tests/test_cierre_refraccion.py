"""Reproduce las expectativas independientes #24–41 de la segunda auditoría."""
import json
from pathlib import Path

import pytest

from app.correlaciones.registry import evaluar_correlaciones_con_nombres, evaluar_recordatorios_tecnicos
from app.inference import _get_active_emergency_alerts
from app.schemas import ImpresionClinicaRequest
from tests.test_auditoria_correlaciones import _req

ROOT = Path(__file__).resolve().parents[1]
MATRIZ = json.loads((ROOT / "auditoria/conformidad-2026-09-29/refraccion/matriz.json").read_text(encoding="utf-8"))
NOMBRES = dict(zip(range(24, 42), (
    "miopia_magna", "hipermetropia_alta", "anisometropia", "antimetropia_pura_acomodativa",
    "aniseiconia_queratometrica_severa", "distancia_vertice_alta_ametropia", "astig_oblicuo",
    "astigmatismo_contra_regla_joven", "av_cc_limitada", "queratocono_ectasia_sospecha",
    "queratometria_asimetrica_interocular", "cornea_plana_extrema", "astigmatismo_corneal_vs_refractivo",
    "astigmatismo_lenticular_puro", "ar_rx_espasmo_acomodativo", "ar_rx_cambio_cristalino",
    "ar_rx_variabilidad_inespecifica", "ar_detecta_astigmatismo_no_prescrito")))
ADICIONALES = [dict(c, numero=int(n), id=f"C{int(n):02d}-A{i:02d}")
               for n, s in MATRIZ.items() for i, c in enumerate(s["adicionales"], 1)]
CORPUS = json.loads((ROOT / "auditoria/2026-09-21/casos.json").read_text(encoding="utf-8"))
RETIRADAS = {NOMBRES[n] for n in (27, 28, 31, 37, 38, 39)}


@pytest.mark.parametrize("caso", ADICIONALES, ids=lambda c: c["id"])
def test_contraprueba_independiente(caso):
    req = ImpresionClinicaRequest.model_validate({"receta_id": caso["id"], **caso["payload"]})
    activas = dict(evaluar_correlaciones_con_nombres(req))
    observaciones = {
        "activo": NOMBRES[caso["numero"]] in activas,
        "tecnico": bool(evaluar_recordatorios_tecnicos(req)),
        "h01": bool(_get_active_emergency_alerts(req)),
        "esfera_ar": req.akr.od.esfera,
        "cilindro_rx": req.refraccion.od.cilindro,
        "sin_esfera_ar_inventada_en_40": "esfera AR" not in activas.get(NOMBRES[40], ""),
    }
    for campo, esperado in caso.get("esperado", {}).items():
        assert observaciones[campo] == esperado, (caso["id"], campo, activas)


@pytest.mark.parametrize("caso", [c for c in CORPUS if int(c["id"][1:3]) in (27, 28, 31, 37, 38, 39)], ids=lambda c: c["id"])
def test_retiradas_no_reintroducen_causalidad(caso):
    activas = dict(evaluar_correlaciones_con_nombres(_req(**caso["entrada"])))
    assert not RETIRADAS.intersection(activas)
