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

_NEGACIONES_PRE = (
    "sin ",
    "no ",
    "no se observa",
    "no se observan",
    "no se documenta",
    "no se detecta",
    "no se detectan",
    "no presenta",
    "sin evidencia",
    "negativ",
    "ausenc",
    "niega",
    "descarte de",
    "libre de",
)

_NEGACIONES_POST = (
    "ausente",
    "ausentes",
    "descartad",
    "negativ",
    "fisiologic",
    "normal",
    "normales",
    "libre",
    "libres",
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
    "dgm", "iol", "rapd", "adie", "papiledema",
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


_AFFIRMATIVE_TRANSITIONS = (
    "se observa", "se observan", "se aprecia", "se aprecian",
    "se evidencia", "se evidencian", "se constata", "se constat",
    "se identifica", "se identifican", "se detecta", "se detectan",
    "se visualiza", "se visualizan", "presenta", "presentan",
    "muestra", "muestran", "evidencia", "evidencian",
    "con hallazgo",
    "pero ", "empero", "sin embargo", "mas bien",
    "con ",
)

_CAUSAL_CONNECTORS = (
    " por ", " debido a ", " secundario a ", " a causa de ",
    " motivado por ", " por presencia de ",
)

_EYE_MARKERS_RE = re.compile(r"\b(od|oi|ojo derecho|ojo izquierdo)\b")

_POSITIVE_CONFIRMATIONS = (
    "positivo", "positiva", "positivos", "positivas",
    "presente", "presentes", "patologico", "patologica",
    "alterado", "alterada", "evidente", "evidentes",
)

_SEVERITY_QUALIFIERS = (
    "moderado", "moderada", "moderados", "moderadas",
    "severo", "severa", "severos", "severas",
    "marcado", "marcada", "marcados", "marcadas",
    "bilateral", "bilaterales", "leve", "leves",
    "anterior", "posterior", "profuso", "profusa",
    "cronico", "cronica", "agudo", "aguda",
    "temporal", "temporales", "nasal", "nasales",
    "superior", "superiores", "inferior", "inferiores",
    "periferico", "periferica", "perifericos", "perifericas", "periferia",
    "herradura", "retiniano", "retiniana", "retinianos", "retinianas",
    "macular", "maculares", "foveal", "foveales",
    "papilar", "papilares",
)


def _keyword_matches(text: str, keyword: str, *, allow_negation_window: bool) -> bool:
    whole_word = keyword in _WHOLE_WORD_KEYWORDS
    for match in _compiled_keyword(keyword).finditer(text):
        if whole_word and not _is_word_bounded(text, match.start(), match.end()):
            continue
        if not allow_negation_window:
            return True
        sentence_start = max(text.rfind(sep, 0, match.start()) for sep in ".;:!?") + 1
        sentence_prefix = text[sentence_start:match.start()]

        sentence_end_candidates = [text.find(sep, match.end()) for sep in ".;:!?"]
        valid_ends = [pos for pos in sentence_end_candidates if pos != -1]
        sentence_end = min(valid_ends) if valid_ends else len(text)
        sentence_suffix = text[match.end():sentence_end].strip()
        suffix_words = sentence_suffix.split()

        # Si el hallazgo esta calificado expresamente como positivo (ej. "dpar positivo"),
        # anula cualquier prefijo negativo anterior.
        is_positively_confirmed = any(
            w.strip(",.;:") in _POSITIVE_CONFIRMATIONS for w in suffix_words[:2]
        )

        if not is_positively_confirmed:
            last_neg_pos = -1
            last_neg_len = 0
            for neg in _NEGACIONES_PRE:
                pos = sentence_prefix.rfind(neg)
                if pos != -1 and (pos > last_neg_pos or (pos == last_neg_pos and len(neg) > last_neg_len)):
                    last_neg_pos = pos
                    last_neg_len = len(neg)

            if last_neg_pos != -1:
                intervening = sentence_prefix[last_neg_pos + last_neg_len:]
                # 1. Transicion afirmativa posterior al negador
                has_affirmative_break = any(t in intervening for t in _AFFIRMATIVE_TRANSITIONS)
                # 2. Conector causal tras "descarte de"
                neg_text = sentence_prefix[last_neg_pos:last_neg_pos + last_neg_len]
                has_causal_break = (
                    "descarte de" in neg_text and any(c in intervening for c in _CAUSAL_CONNECTORS)
                )
                # 3. Transicion de ojo interocular (el negador estaba en el otro ojo)
                has_eye_break = _EYE_MARKERS_RE.search(intervening) is not None
                # 4. Negacion acotada a un solo sustantivo sin conjuncion y con calificador
                intervening_words = intervening.split()
                has_scope_break = (
                    len(intervening_words) >= 1
                    and not any(c in intervening_words for c in ("ni", "o", "tampoco"))
                    and any(w.strip(",.;:") in _SEVERITY_QUALIFIERS for w in suffix_words[:3])
                )
                if not (has_affirmative_break or has_causal_break or has_eye_break or has_scope_break):
                    continue

        # Evaluacion de negacion sufija (hasta 8 palabras)
        suffix_words_window = suffix_words[:8]
        negated_post = False
        for idx, word in enumerate(suffix_words_window):
            w_clean = word.strip(",.;:")
            if any(neg in w_clean for neg in _NEGACIONES_POST):
                # Si hay una coma o punto y coma, o un marcador de cambio de ojo entre el hallazgo
                # y el negador sufijo, el calificador negativo pertenece a otra clausula u ojo.
                if any("," in w or ";" in w for w in suffix_words_window[:idx]):
                    continue
                prev_words = [w.strip(",.;:") for w in suffix_words_window[:idx]]
                if any(_EYE_MARKERS_RE.search(pw) for pw in prev_words):
                    continue
                # "resto normal" o "demas normal" califica a otras estructuras, no al hallazgo
                if w_clean.startswith("normal"):
                    if any(pw in ("resto", "demas", "polo") for pw in prev_words):
                        continue
                negated_post = True
                break

        if negated_post:
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
