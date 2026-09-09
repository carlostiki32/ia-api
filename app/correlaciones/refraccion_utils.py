"""Utilidades refractivas compartidas: agudeza visual Snellen, equivalente
esferico y formateo de valores por ojo."""
from __future__ import annotations

import re

from app.correlaciones.texto import _join_hallazgos


# Umbral de AV con correccion "limitada": denominador Snellen (en pie) > 25, es
# decir 20/30 o peor. 20/20 y 20/25 se consideran dentro de limites normales y no
# disparan la correlacion (evita el ruido y el screening del adulto mayor por una
# reduccion clinicamente trivial).
_AV_DENOM_LIMITE = 25

_AV_FEET_RE = re.compile(r"^\s*20\s*/\s*(\d{1,3})\s*$")
_AV_METRIC_RE = re.compile(r"^\s*6\s*/\s*(\d{1,2}(?:\.\d+)?)\s*$")
_AV_DECIMAL_RE = re.compile(r"^\s*(0?\.\d+|1(?:\.0+)?)\s*$")


def _av_denominator(av: str | None) -> int | None:
    """Denominador Snellen equivalente en pie (20/xx) a partir de las tres
    notaciones que emiten los frontends: pie (20/40), metrica (6/12) y decimal
    (0.5 / 0,5). Notaciones no interpretables (CF, MM, cuenta dedos) -> None."""
    if av is None:
        return None
    text = str(av).strip().replace(",", ".")

    match = _AV_FEET_RE.match(text)
    if match:
        return int(match.group(1))

    match = _AV_METRIC_RE.match(text)
    if match:
        metric_denominator = float(match.group(1))
        if metric_denominator <= 0:
            return None
        return round(metric_denominator * 20.0 / 6.0)

    match = _AV_DECIMAL_RE.match(text)
    if match:
        decimal = float(match.group(1))
        if decimal <= 0:
            return None
        return round(20.0 / decimal)

    # Notaciones de baja vision profunda (ceguera legal o sub-Snellen)
    norm = text.strip().lower()
    if norm in ("cuenta dedos", "cd", "cf", "counting fingers") or "cuenta dedos" in norm:
        return 1000
    if norm in ("mm", "movimiento de manos", "movimiento manos", "hand motion", "hm") or "movimiento de manos" in norm:
        return 2000
    if norm in ("pl", "percepcion de luz", "percepcion luz", "lp", "light perception") or "percepcion de luz" in norm:
        return 4000
    if norm in ("npl", "no percepcion de luz", "nlp", "no luz"):
        return 8000

    return None


def _av_es_limitada(av: str | None) -> bool:
    denominator = _av_denominator(av)
    return denominator is not None and denominator > _AV_DENOM_LIMITE


def _av_categoria(av: str | None) -> str | None:
    denominator = _av_denominator(av)
    if denominator is None or denominator <= _AV_DENOM_LIMITE:
        return None
    if denominator <= 30:
        return "leve reduccion de la agudeza visual con correccion"
    if denominator <= 50:
        return "reduccion moderada de la agudeza visual con correccion"
    if denominator <= 100:
        return "reduccion marcada de la agudeza visual con correccion"
    return "deficit visual severo con correccion optima"


def _equivalente_esferico(esf: float | None, cil: float | None) -> float | None:
    if esf is None:
        return None
    return esf + (cil or 0.0) / 2.0


def _format_eyes_with_values(values: list[tuple[str, float]], label: str) -> str:
    partes = [f"{ojo} ({label} {valor:+.2f}D)" for ojo, valor in values]
    return _join_hallazgos(partes)
