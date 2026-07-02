"""Normalizacion de texto libre y matching de keywords con ventana de negacion.

Base de las correlaciones cualitativas (fondo, pupilas, anexos, campos, amsler,
cover test). No conoce dominios clinicos concretos: solo normaliza, compila y
busca keywords respetando negaciones por oracion.
"""
from __future__ import annotations

import functools
import re
import unicodedata

from app.schemas import ImpresionClinicaRequest

_NEGACIONES = (
    "sin ",
    "no se observa",
    "no se documenta",
    "no presenta",
    "sin evidencia",
    "negativ",
    "ausenc",
    "ausente",
)
# El SaaS compone cover_test como "OD: Tipo [y Sub] | OI: Tipo [y Sub]"
# con tipo ∈ {Orto, Endo, Exo, Hiper, Hipo} y sub ∈ {Tropia, Foria}.
# Las correlaciones buscan keywords unidas (exoforia, endotropia, etc.);
# esta regex reconoce los pares para expandirlos a la forma unida.
_COVER_PAIR_RE = re.compile(r"\b(endo|exo|hiper|hipo)\s+y\s+(foria|tropia)\b")

_WHITESPACE_RE = re.compile(r"\s+")


@functools.lru_cache(maxsize=512)
def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return _WHITESPACE_RE.sub(" ", ascii_only).strip().lower()


@functools.lru_cache(maxsize=1024)
def _compiled_keyword(keyword: str) -> re.Pattern:
    return re.compile(re.escape(keyword))


@functools.lru_cache(maxsize=64)
def _compiled_union(keywords: tuple[str, ...]) -> re.Pattern:
    return re.compile("|".join(re.escape(k) for k in keywords))


@functools.lru_cache(maxsize=256)
def _normalize_cover_text(value: str | None) -> str:
    """Normaliza cover_test y expande los pares 'tipo y sub' a su forma unida.

    La UI del SaaS compone cover_test como 'OD: Exo y Foria | OI: Orto'. Las
    correlaciones buscan keywords unidas como 'exoforia' o 'endotropia'.
    Esta funcion agrega las formas unidas al texto normalizado para que
    ambas convenciones (unida o separada por ' y ') matcheen.
    """
    text = _normalize_text(value)
    if not text:
        return ""
    expanded = _COVER_PAIR_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}", text)
    if expanded == text:
        return text
    return f"{text} {expanded}"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _join_hallazgos(values: list[str]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return ", ".join(values[:-1]) + f" y {values[-1]}"


def _keyword_matches(text: str, keyword: str, *, allow_negation_window: bool) -> bool:
    for match in _compiled_keyword(keyword).finditer(text):
        if not allow_negation_window:
            return True
        sentence_start = max(text.rfind(sep, 0, match.start()) for sep in ".;!?") + 1
        sentence_prefix = text[sentence_start:match.start()]
        if any(neg in sentence_prefix for neg in _NEGACIONES):
            continue
        return True
    return False


def _contains_keyword(
    value: str | None,
    keywords: tuple[str, ...] | list[str],
    *,
    allow_negation_window: bool = False,
) -> bool:
    text = _normalize_text(value)
    if not text:
        return False
    if not allow_negation_window:
        # Path rapido: una sola busqueda sobre la union de keywords.
        kw_tuple = tuple(keywords)
        return _compiled_union(kw_tuple).search(text) is not None
    return any(
        _keyword_matches(text, keyword, allow_negation_window=allow_negation_window)
        for keyword in keywords
    )


def _extract_normalized_findings(
    value: str | None,
    keyword_map: dict[str, str],
    *,
    allow_negation_window: bool = False,
) -> list[str]:
    text = _normalize_text(value)
    findings = [
        normalized
        for keyword, normalized in keyword_map.items()
        if _keyword_matches(text, keyword, allow_negation_window=allow_negation_window)
    ]
    return _dedupe(findings)


def _fondo_contains(req: ImpresionClinicaRequest, keywords: tuple[str, ...]) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    return _contains_keyword(
        clinica.fondo_de_ojo,
        keywords,
        allow_negation_window=True,
    )
