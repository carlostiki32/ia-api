"""Aceptacion independiente de los desvíos de las dos auditorías #12–19."""
import json
from pathlib import Path

import pytest

from app.correlaciones.registry import evaluar_correlaciones_con_nombres
from app.inference import _get_active_emergency_alerts, _ensure_follow_up_last
from tests.test_auditoria_correlaciones import _req

DEST = Path(__file__).parents[1] / "auditoria/certificacion-2026-09-29/segmento"
CASOS = json.loads((DEST / "casos.json").read_text(encoding="utf-8"))


def comprobar(caso):
    req = _req(lente="monofocal", **caso["entrada"])
    salidas = dict(evaluar_correlaciones_con_nombres(req))
    nombre = caso["nombre"]
    texto = salidas.get(nombre, "")
    h01 = {a.id for a in _get_active_emergency_alerts(req)}
    observado = {"activa": bool(texto), "urgente": texto.startswith("Hallazgo urgente:"),
                 "h01": nombre in h01}
    for clave, valor in caso["esperado"].items():
        if clave in observado:
            assert observado[clave] == valor, (caso["id"], clave, texto, h01)
        elif clave == "contiene":
            assert all(s.lower() in texto.lower() for s in valor), (caso["id"], valor, texto)
        elif clave == "no_contiene":
            assert all(s.lower() not in texto.lower() for s in valor), (caso["id"], valor, texto)
        elif clave == "activas":
            assert all(s in salidas for s in valor), (caso["id"], valor, salidas)
        elif clave == "no_activas":
            assert all(s not in salidas for s in valor), (caso["id"], valor, salidas)
        else:
            raise AssertionError(clave)
    if observado["urgente"]:
        assert observado["h01"], (caso["id"], texto, h01)
        salida = _ensure_follow_up_last("Datos revisados.", "Revisión anual de control.", payload=req)
        assert "anual" not in salida.lower(), (caso["id"], salida)
    return {"payload": req.model_dump(mode="json"), "observado": observado,
            "salidas": salidas, "h01": sorted(h01)}


@pytest.mark.parametrize("caso", CASOS, ids=lambda c: c["id"])
def test_cierre_segmento(caso):
    comprobar(caso)
