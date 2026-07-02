"""Utilidades refractivas compartidas: agudeza visual Snellen, equivalente
esferico y formateo de valores por ojo."""
from __future__ import annotations

import re

from app.correlaciones.texto import _join_hallazgos


def _snellen_denominator(av: str | None) -> int | None:
    if av is None:
        return None
    match = re.match(r"^\s*20\s*/\s*(\d{1,3})\s*$", av)
    if match is None:
        return None
    return int(match.group(1))


def _av_es_limitada(av: str | None) -> bool:
    denominator = _snellen_denominator(av)
    return denominator is not None and denominator > 20


def _av_categoria(av: str | None) -> str | None:
    denominator = _snellen_denominator(av)
    if denominator is None or denominator <= 20:
        return None
    if 21 <= denominator <= 30:
        return "leve reduccion de la agudeza visual con correccion"
    if 31 <= denominator <= 50:
        return "reduccion moderada de la agudeza visual con correccion"
    if 51 <= denominator <= 100:
        return "reduccion marcada de la agudeza visual con correccion"
    return "deficit visual severo con correccion optima"


def _equivalente_esferico(esf: float | None, cil: float | None) -> float | None:
    if esf is None:
        return None
    return esf + (cil or 0.0) / 2.0


def _format_eyes_with_values(values: list[tuple[str, float]], label: str) -> str:
    partes = [f"{ojo} ({label} {valor:+.2f}D)" for ojo, valor in values]
    return _join_hallazgos(partes)
