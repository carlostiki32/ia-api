"""Integración de los ajustes pendientes con la salida determinista de H01."""
import pytest

from app.inference import _ensure_emergency_preserved, _ensure_follow_up_last, _get_active_emergency_alerts
from tests.test_auditoria_correlaciones import _req, _ANUAL, _N


def test_c12_h01_usa_el_ojo_del_hallazgo_filtrado():
    req = _req(lente="monofocal", pupilas=f"{_N}: Midriasis OD farmacologica por tropicamida; miosis OI.",
               anexos="Ptosis OI de inicio hoy.")
    alerts = [a for a in _get_active_emergency_alerts(req) if a.id == "horner_o_tercer_par_sospecha"]
    assert len(alerts) == 1
    assert alerts[0].ojo == "OI"


@pytest.mark.parametrize("text", ["Ptosis OD. Valoracion oftalmologica.",
    "Ptosis OD, se indica revision anual.", "Ptosis OI. Valoracion el mismo dia."])
def test_c12_h01_conserva_plazo_y_lateralidad(text):
    req = _req(lente="monofocal", pupilas=f"{_N}: Miosis OD.", anexos="Ptosis OD de inicio hoy.",
               motivo="Dolor cervical derecho de inicio hoy.", seguimiento=_ANUAL)
    result = _ensure_emergency_preserved(text, req)
    assert "mismo dia" in result.lower()
    assert "OD" in result
    assert "anual" not in result.lower()
    assert "horner" not in result.lower()
    assert "iii par" not in result.lower()
    assert "anual" not in _ensure_follow_up_last(result, _ANUAL, payload=req).lower()


def test_c12_h01_no_convierte_evolucion_desconocida_en_urgencia():
    req = _req(lente="monofocal", pupilas=f"{_N}: Anisocoria.", anexos="Ptosis OD.")
    assert "horner_o_tercer_par_sospecha" not in {a.id for a in _get_active_emergency_alerts(req)}
