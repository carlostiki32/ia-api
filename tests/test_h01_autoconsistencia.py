"""Autoconsistencia de H01 sobre los 1356 casos historicos.

Revision independiente 2026-09-29: dos oraciones deterministas de #15/#16 («Una confrontacion sin defectos no
descarta…», «Una rejilla de Amsler sin alteraciones no descarta…») coincidian con la deteccion de «falsa
normalidad» de la propia salvaguarda: si el LLM las copiaba, H01 las purgaba y reinyectaba el texto completo
(duplicado). Ninguna oracion del texto determinista de una alerta puede ser juzgada contradictoria por H01, y
para las alertas con especificacion propia la salvaguarda debe ser idempotente.
"""
import json
from pathlib import Path

import pytest

from app.inference import (
    _ensure_emergency_preserved,
    _get_active_emergency_alerts,
    _is_sentence_contradictory,
    _split_sentences,
)
from tests.test_auditoria_correlaciones import _req

_CASOS = json.loads((Path(__file__).parents[1] / "auditoria/2026-09-21/casos.json").read_text(encoding="utf-8"))
_RUTINA = "Se recomienda revision optometrica anual de control. Proxima cita en: 12 meses."

def _con_alertas():
    casos = []
    for c in _CASOS:
        if _get_active_emergency_alerts(_req(**c["entrada"])):
            casos.append(pytest.param(c, id=c["id"]))
    return casos


_CASOS_CON_ALERTA = _con_alertas()


def test_hay_casos_con_alerta():
    assert len(_CASOS_CON_ALERTA) >= 90


@pytest.mark.parametrize("caso", _CASOS_CON_ALERTA)
def test_h01_no_purga_su_propio_texto_determinista(caso):
    alertas = _get_active_emergency_alerts(_req(**caso["entrada"]))
    ofensoras = [s for a in alertas for s in _split_sentences(a.texto_determinista)
                 if any(_is_sentence_contradictory(s, otra) for otra in alertas)]
    assert ofensoras == []


@pytest.mark.parametrize("caso", _CASOS_CON_ALERTA)
def test_h01_idempotente_para_alertas_activas(caso):
    req = _req(**caso["entrada"])
    alertas = _get_active_emergency_alerts(req)
    uno = _ensure_emergency_preserved(_RUTINA, req)
    assert _ensure_emergency_preserved(uno, req) == uno
