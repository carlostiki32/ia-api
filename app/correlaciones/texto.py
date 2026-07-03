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
# Parser estructurado del formato canonico por ojo. El sub es OPCIONAL en la UI
# (radios sin default): "OD: Endo | OI: Orto" es un estado real del formulario.
_COVER_EYE_RE = re.compile(
    r"\b(od|oi)\s*:\s*(orto|endo|exo|hiper|hipo)\b(?:\s+y\s+(foria|tropia))?"
)

_WHITESPACE_RE = re.compile(r"\s+")

# Keywords que DEBEN coincidir como palabra completa. Son abreviaturas clinicas
# cortas que, con el matching por substring por defecto, aparecen dentro de
# palabras comunes ("mer" en "primero", "irma" en "afirma", "adie" en "nadie",
# "iol" en "violeta") y dispararian falsos positivos. Solo se listan tokens que son
# abreviaturas atomicas, nunca raices/prefijos intencionales (p. ej. "negativ",
# "ausenc", "neovas").
_WHOLE_WORD_KEYWORDS = frozenset({
    "mer", "cnv", "mev", "mnvc", "crsc",
    "isnt", "dmre", "cscr", "emq", "rdnp", "rdp", "irma",
    "dgm", "iol", "rapd", "adie",
})


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


@functools.lru_cache(maxsize=256)
def _cover_desviaciones(value: str | None) -> frozenset[str]:
    """Desviaciones del cover test segun el formato canonico del SaaS.

    Devuelve tokens unidos ('exoforia', 'endotropia', 'hiperforia', ...) y,
    cuando el optometrista dejo el sub sin clasificar (eligio Tipo pero no
    Tropia/Foria), el tipo suelto ('exo', 'endo', 'hiper', 'hipo'). 'orto' no
    genera token. Texto libre legacy que no siga el formato canonico no matchea
    aqui: lo cubren las keywords sobre _normalize_cover_text.
    """
    text = _normalize_text(value)
    if not text:
        return frozenset()
    tokens: set[str] = set()
    for match in _COVER_EYE_RE.finditer(text):
        tipo, sub = match.group(2), match.group(3)
        if tipo == "orto":
            continue
        tokens.add(f"{tipo}{sub}" if sub else tipo)
    return frozenset(tokens)


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


def _is_word_bounded(text: str, start: int, end: int) -> bool:
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    return not before.isalnum() and not after.isalnum()


def _keyword_matches(text: str, keyword: str, *, allow_negation_window: bool) -> bool:
    whole_word = keyword in _WHOLE_WORD_KEYWORDS
    for match in _compiled_keyword(keyword).finditer(text):
        if whole_word and not _is_word_bounded(text, match.start(), match.end()):
            continue
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
