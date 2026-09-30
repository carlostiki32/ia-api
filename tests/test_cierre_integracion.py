"""Invariantes transversales en todo el corpus oficial, incluidas ramas no golden."""
import json
from pathlib import Path
import re

import pytest

from app.correlaciones.registry import evaluar_correlaciones_con_nombres
from app.correlaciones.texto import _normalize_text
from app.inference import _get_active_emergency_alerts, _ensure_emergency_preserved
from tests.test_auditoria_correlaciones import _req

ROOT = Path(__file__).resolve().parents[1]
CORPUS = json.loads((ROOT / "auditoria/2026-09-21/casos.json").read_text(encoding="utf-8"))
T5 = re.compile(r"\b(?:compatible\s+con|confirma\w*|patron\s+sugestivo\s+de|patron\s+compatible|diagnostico\s+de)\b", re.I)
T12 = re.compile(r"\b(?:urgent\w*|inmediat\w*|prioritari\w*|grave|emergencia\w*)\b", re.I)


def texto_propio(texto, req):
    """Distingue inferencia nueva de cita exacta explícita del capturista.

    Única excepción a T5: texto entre comillas angulares que se encuentre
    íntegramente en un campo del payload. No se excepciona texto generado por
    parecer negación, recomendación o un diagnóstico previamente conocido.
    """
    fuentes = [v for bloque in (req.paciente.model_dump(), req.clinica.model_dump())
               for v in bloque.values() if isinstance(v, str)]
    def quitar_cita(m):
        cita = _normalize_text(m.group(1))
        return " " if any(cita in _normalize_text(f) for f in fuentes) else m.group()
    return re.sub(r"«([^»]+)»", quitar_cita, texto)


@pytest.mark.parametrize("caso", CORPUS, ids=lambda c: c["id"])
def test_ordenes_transversales_corpus_completo(caso):
    req = _req(**caso["entrada"])
    salidas = dict(evaluar_correlaciones_con_nombres(req))
    alertas = _get_active_emergency_alerts(req)
    urgentes = {nombre for nombre, texto in salidas.items() if texto.startswith("Hallazgo urgente:")}
    assert {a.id for a in alertas} == urgentes
    for nombre, texto in salidas.items():
        assert not T5.search(texto_propio(_normalize_text(texto), req)), (nombre, texto)
        if nombre not in urgentes:
            assert not T12.search(_normalize_text(texto)), (nombre, texto)
    if alertas:
        final = _ensure_emergency_preserved("Se recomienda control anual.", req)
        assert "control anual" not in final.lower()
        # Con una salida que omite todos los hechos debe conservarse cada aviso
        # completo: números, ojo, incertidumbre y plazo vienen del motor validado.
        for alerta in alertas:
            assert _normalize_text(alerta.texto_determinista) in _normalize_text(final)
        assert _ensure_emergency_preserved(final, req) == final


def test_t5_excepcion_no_admite_cita_inventada():
    req = _req(motivo="Diagnostico de catarata ya registrado.")
    assert not T5.search(texto_propio("Contexto: «Diagnostico de catarata ya registrado.»", req))
    assert T5.search(texto_propio("Contexto: «Diagnostico de glaucoma nuevo.»", req))
    assert T5.search(texto_propio("Diagnostico de glaucoma.", req))
