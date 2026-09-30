"""Utilidades refractivas compartidas: agudeza visual Snellen, equivalente
esferico y formateo de valores por ojo."""
from __future__ import annotations

import re

from app.correlaciones.texto import _join_hallazgos, _normalize_text


# Seleccion operativa de AV registrada: denominador Snellen >25 (20/30 o peor).
# No valida gravedad, discapacidad, normalidad por debajo ni protocolo de BCVA.
_AV_DENOM_LIMITE = 25

# Categorias clinicas formales de baja vision profunda (sub-Snellen):
CATEGORIA_NO_PERCEPCION_LUZ = "NPL"
CATEGORIA_PERCEPCION_LUZ = "PL"
CATEGORIA_MOVIMIENTO_MANOS = "MM"
CATEGORIA_CUENTA_DEDOS = "CD"

# Centinelas numericos internos para ordenamiento y evaluacion de severidad:
# NOTA CLINICA (agency-clinical-evidence-agent):
# Estos valores numericos (1000, 2000, 4000, 8000) son unicamente centinelas internos
# para permitir la evaluacion ordinal de severidad (ej. > 25) en el arbol de reglas.
# NO representan denominadores Snellen medidos opticamente ni equivalencias legales de ceguera.
AV_DENOM_CUENTA_DEDOS = 1000
AV_DENOM_MOVIMIENTO_MANOS = 2000
AV_DENOM_PERCEPCION_LUZ = 4000
AV_DENOM_NO_PERCEPCION_LUZ = 8000

_SUB_SNELLEN_DENOM_MAP: dict[str, int] = {
    CATEGORIA_CUENTA_DEDOS: AV_DENOM_CUENTA_DEDOS,
    CATEGORIA_MOVIMIENTO_MANOS: AV_DENOM_MOVIMIENTO_MANOS,
    CATEGORIA_PERCEPCION_LUZ: AV_DENOM_PERCEPCION_LUZ,
    CATEGORIA_NO_PERCEPCION_LUZ: AV_DENOM_NO_PERCEPCION_LUZ,
}

_AV_FEET_RE = re.compile(r"^\s*20\s*/\s*(\d+)\s*$")
_AV_METRIC_RE = re.compile(r"^\s*6\s*/\s*(\d+(?:\.\d+)?)\s*$")
_AV_DECIMAL_RE = re.compile(r"^\s*(0?\.\d+|1(?:\.0+)?)\s*$")


def _av_sub_snellen_categoria(av: str | None) -> str | None:
    """Identifica la categoria clinica estandarizada de agudeza visual profunda (sub-Snellen):
    - 'NPL': No Percepcion de Luz (amaurosis / ceguera total).
    - 'PL': Percepcion de Luz (con o sin proyeccion luminosa).
    - 'MM': Movimiento de Manos (a cualquier distancia o aislado).
    - 'CD': Cuenta Dedos (a cualquier distancia o aislado).

    Normaliza Unicode (eliminando tildes y diacriticos) y prioriza estrictamente
    la evaluacion de NPL antes que PL para evitar que 'no percepcion de luz'
    coincida con la subcadena 'percepcion de luz'. Retorna None si no es sub-Snellen.
    """
    if av is None:
        return None
    raw = str(av).strip()
    if not raw:
        return None
    norm = _normalize_text(raw)
    if not norm:
        return None
    # Elimina puntos de abreviaturas (ej. 'c.d.' -> 'cd', 'p.l.' -> 'pl', 'n.p.l.' -> 'npl')
    norm_clean = re.sub(r"\.(?=[a-z]|\s|$)", "", norm)

    # 1. No Percepcion de Luz (NPL / NLP / amaurosis)
    # DEBE evaluarse antes de PL porque 'no percepcion de luz' contiene 'percepcion de luz'
    if (
        re.search(r"\b(no|sin)\s+percepcion\s+(de\s+)?(luz|luminica)\b", norm_clean)
        or re.search(r"\b(no|sin)\s+luz\b", norm_clean)
        or re.search(r"\b(npl|nlp|amaurosis|ceguera\s+total)\b", norm_clean)
        or norm_clean in ("npl", "nlp", "no luz", "sin luz", "amaurosis")
    ):
        return CATEGORIA_NO_PERCEPCION_LUZ

    # 2. Percepcion de Luz (PL / LP / proyeccion luminosa)
    if (
        re.search(r"\bpercepcion\s+(de\s+)?(luz|luminica)\b", norm_clean)
        or re.search(r"\bproyeccion\s+(de\s+)?(luz|luminosa|luminica)\b", norm_clean)
        or re.search(r"\blight\s+perception\b", norm_clean)
        or re.search(r"\b(pl|lp)\b", norm_clean)
        or norm_clean in ("pl", "lp", "luz", "proyeccion luz")
    ):
        return CATEGORIA_PERCEPCION_LUZ

    # 3. Movimiento de Manos (MM / HM)
    if (
        re.search(r"\bmovimiento\s+(de\s+)?(manos|bultos)\b", norm_clean)
        or re.search(r"\bhand\s+motions?\b", norm_clean)
        or re.search(r"\bhand\s+movements?\b", norm_clean)
        or re.search(r"(?<!\d\s)(?<!\d)\b(mm|hm)\b", norm_clean)
        or norm_clean in ("mm", "hm", "movimiento manos", "movimiento de manos")
    ):
        return CATEGORIA_MOVIMIENTO_MANOS

    # 4. Cuenta Dedos (CD / CF / Counting Fingers)
    if (
        re.search(r"\b(?:cuenta|contar)\s+dedos\b", norm_clean)
        or re.search(r"\bcounting\s+fingers\b", norm_clean)
        or re.search(r"(?<!\d\s)(?<!\d)\b(cd|cf)\b", norm_clean)
        or norm_clean in ("cd", "cf", "cuenta dedos", "contar dedos")
    ):
        return CATEGORIA_CUENTA_DEDOS

    return None


def _av_denominator(av: str | None) -> int | None:
    """Denominador Snellen equivalente en pie (20/xx) a partir de las tres
    notaciones que emiten los frontends: pie (20/40), metrica (6/12) y decimal
    (0.5 / 0,5). Denominadores <= 0 o notaciones no interpretables -> None.

    Para agudeza visual sub-Snellen (CD, MM, PL, NPL), asigna centinelas numericos
    internos (1000, 2000, 4000, 8000) destinados exclusivamente al ordenamiento
    relativo y filtros de severidad en reglas clinicas.
    """
    if av is None:
        return None
    text = str(av).strip().replace(",", ".")

    match = _AV_FEET_RE.match(text)
    if match:
        denom = int(match.group(1))
        return denom if denom > 0 else None

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

    # Notaciones de baja vision profunda (sub-Snellen)
    sub_cat = _av_sub_snellen_categoria(text)
    if sub_cat is not None:
        return _SUB_SNELLEN_DENOM_MAP.get(sub_cat)

    return None


def _av_es_limitada(av: str | None) -> bool:
    denominator = _av_denominator(av)
    return denominator is not None and denominator > _AV_DENOM_LIMITE


def _av_categoria(av: str | None) -> str | None:
    """Descripcion numerica; no clasifica discapacidad ni gravedad clinica."""
    denominator = _av_denominator(av)
    if denominator is None or denominator <= _AV_DENOM_LIMITE:
        return None
    return "AV con correccion registrada inferior a 20/25; pendiente de verificacion"


def _equivalente_esferico(esf: float | None, cil: float | None) -> float | None:
    """Calcula el equivalente esferico (esfera + cilindro / 2).

    Requiere ambos componentes registrados. Un cero explicito es valido;
    un dato no capturado no equivale a cero (diccionario, seccion 1.2).
    """
    if esf is None or cil is None:
        return None
    return esf + cil / 2.0


def _format_eyes_with_values(values: list[tuple[str, float]], label: str) -> str:
    partes = [f"{ojo} ({label} {valor:+.2f}D)" for ojo, valor in values]
    return _join_hallazgos(partes)
