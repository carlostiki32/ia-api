"""Dominio: pupilas y motilidad ocular (2 correlaciones).

pupilas_alteradas (anisocoria, DPAR, midriasis...) y motilidad_alterada
(limitacion, nistagmo, paresia...). pupilas_alteradas se suprime cuando ya
activa glaucoma_asimetrico (que integra el DPAR en su propio enunciado).
"""
from __future__ import annotations

import re

from app.correlaciones.base import _memoize_cond
from app.correlaciones.fondo_de_ojo import _cond_glaucoma_asimetrico
from app.correlaciones.texto import (
    _EYE_MARKERS_RE,
    _compiled_keyword,
    _contains_keyword,
    _dedupe,
    _extract_normalized_findings,
    _join_hallazgos,
    _keyword_matches,
    _normalize_text,
)
from app.schemas import ImpresionClinicaRequest

_EYE_MARKERS_EXPLICIT_RE = re.compile(
    r"\b(ao|ambos ojos|bilateral|bilaterales|od|oi|ojo derecho|ojo izquierdo|derecho|derecha|izquierdo|izquierda)\b"
)
_AO_MARKERS_RE = re.compile(r"\b(ao|ambos ojos|bilateral|bilaterales)\b")
_OD_MARKERS_RE = re.compile(r"\b(od|ojo derecho|derecho|derecha)\b")
_OI_MARKERS_RE = re.compile(r"\b(oi|ojo izquierdo|izquierdo|izquierda)\b")

_KEYWORDS_PUPILAS = {
    "anisocoria": "anisocoria",
    "midriasis": "midriasis",
    "miosis": "miosis",
    "dpar": "defecto pupilar aferente relativo",
    "rapd": "defecto pupilar aferente relativo",
    "defecto pupilar aferente": "defecto pupilar aferente relativo",
    "pupila de marcus gunn": "defecto pupilar aferente relativo",
    "marcus gunn pupilar": "defecto pupilar aferente relativo",
    "pupila marcus gunn": "defecto pupilar aferente relativo",
    "signo de marcus gunn": "defecto pupilar aferente relativo",
    "no reactivo": "pupila no reactiva",
    "no reactiva": "pupila no reactiva",
    "arreactiva": "pupila no reactiva",
    "pupila fija": "pupila no reactiva",
    "hiporreactiva": "respuesta pupilar disminuida",
    "irregular": "pupila irregular",
    "discoria": "discoria",
    "corectopia": "corectopia",
    "pupila tonica": "pupila tonica",
    "adie": "pupila tonica de adie",
    "reflejo ausente": "respuesta pupilar ausente",
    "reflejos ausentes": "respuesta pupilar ausente",
    "reflejo fotomotor ausente": "respuesta pupilar ausente",
    "fotomotor ausente": "respuesta pupilar ausente",
}
_KEYWORDS_PTOSIS = ("ptosis", "blefaroptosis", "caida del parpado", "parpado caido")
_KEYWORDS_PTOSIS_CONGENITA_O_CRONICA = (
    "congenit", "de nacimiento", "desde nin", "desde la infancia",
    "cronica", "cronico", "antigua", "antiguo", "larga evolucion",
    "senil", "aponeurotic", "involutiv",
)
_KEYWORDS_ANISOCORIA_BENIGNA = (
    "anisocoria fisiologica", "anisocoria benigna", "anisocoria simple",
    "anisocoria esencial",
)
# Calificadores que indican midriasis/miosis inducida (no un hallazgo patologico):
# examen bajo dilatacion o efecto de farmacos.
_KEYWORDS_PUPILA_FARMACOLOGICA = (
    "farmacologic", "post dilatacion", "post-dilatacion", "bajo dilatacion",
    "midriatic", "dilatacion pupilar", "cicloplej", "tropicamida", "fenilefrina",
    "pilocarpina",
)
_KEYWORDS_MOTILIDAD = (
    "limitacion", "movimientos oculares limitados", "ducciones limitadas",
    "versiones limitadas", "mirada limitada",
    "paresia", "paretic", "paralisis", "paralitic", "oftalmoparesia",
    "restriccion", "incomitancia", "incomitante",
    "nistagmo", "nistagmus", "torticolis", "posicion compensadora",
    "dolor con movimiento", "dolor al movimiento", "sobreacti", "hiperfuncion",
    "hipoaccion", "hipofuncion", "sincinesia", "duane", "oftalmoplejia",
    "oftalmoplegia",
)


def _clause_has_qualifier(
    text_norm: str,
    match_start: int,
    match_end: int,
    qualifiers: tuple[str, ...],
) -> bool:
    """Verifica si en la clausula local del match existe algun calificador,
    sin que medie un marcador de cambio de ojo entre ellos."""
    clause_start = max([text_norm.rfind(sep, 0, match_start) for sep in ".;:|\n"] or [-1]) + 1
    ends = [pos for pos in [text_norm.find(sep, match_end) for sep in ".;:|\n"] if pos != -1]
    clause_end = min(ends) if ends else len(text_norm)

    clause_before = text_norm[clause_start:match_start]
    clause_after = text_norm[match_end:clause_end]

    # Revisar calificadores antes del match (sin cambio de ojo intermedio)
    for q in qualifiers:
        pos = clause_before.rfind(q)
        if pos != -1:
            intervening = clause_before[pos + len(q):]
            if not _EYE_MARKERS_RE.search(intervening):
                return True

    # Revisar calificadores despues del match (sin cambio de ojo intermedio)
    for q in qualifiers:
        pos = clause_after.find(q)
        if pos != -1:
            intervening = clause_after[:pos]
            if not _EYE_MARKERS_RE.search(intervening):
                return True

    return False


def _extract_finding_eye(
    text: str | None,
    finding_keywords: tuple[str, ...] | list[str],
) -> str | None:
    """Extrae el ojo ('OD', 'OI', 'AO', 'AMBOS', o None) al que corresponde
    el hallazgo clinico en el texto. Si el texto compara ambos ojos (ej. 'OD > OI')
    o no especifica lateralidad, devuelve 'AMBOS' o None."""
    if not text:
        return None
    norm = _normalize_text(text)
    if not norm:
        return None

    for kw in finding_keywords:
        for m in _compiled_keyword(kw).finditer(norm):
            if not _keyword_matches(norm, kw, allow_negation_window=True):
                continue

            # Delimitar la clausula local del match
            clause_start = max([norm.rfind(sep, 0, m.start()) for sep in ".;:|\n"] or [-1]) + 1
            ends = [pos for pos in [norm.find(sep, m.end()) for sep in ".;:|\n"] if pos != -1]
            clause_end = min(ends) if ends else len(norm)
            clause_text = norm[clause_start:clause_end]

            # Comparacion explicita entre ojos (ej. 'od > oi', 'od mayor que oi')
            if (">" in clause_text or "<" in clause_text or "mayor" in clause_text or "menor" in clause_text) and (
                _OD_MARKERS_RE.search(clause_text) and _OI_MARKERS_RE.search(clause_text)
            ):
                return "AMBOS"

            # Marcador bilateral explicito en la clausula
            if _AO_MARKERS_RE.search(clause_text):
                return "AO"

            # Marcadores especificos en la clausula
            has_od = bool(_OD_MARKERS_RE.search(clause_text))
            has_oi = bool(_OI_MARKERS_RE.search(clause_text))
            if has_od and not has_oi:
                return "OD"
            if has_oi and not has_od:
                return "OI"
            if has_od and has_oi:
                return "AMBOS"

            # Buscar marcador anterior mas cercano si la clausula no tenia marcador
            prev_markers = list(_EYE_MARKERS_EXPLICIT_RE.finditer(norm[:m.start()]))
            if prev_markers:
                last_marker = prev_markers[-1].group(1)
                if last_marker in ("ao", "ambos ojos", "bilateral", "bilaterales"):
                    return "AO"
                if last_marker in ("od", "ojo derecho", "derecho", "derecha"):
                    return "OD"
                if last_marker in ("oi", "ojo izquierdo", "izquierdo", "izquierda"):
                    return "OI"

    return None


def _son_hallazgos_contralaterales(ojo1: str | None, ojo2: str | None) -> bool:
    """Determina si dos hallazgos estan en ojos estrictamente opuestos
    (uno en OD y el otro en OI), lo que excluye un sindrome neurooftalmico
    ipsilateral como Horner o paresia del III par."""
    if not ojo1 or not ojo2:
        return False
    o1, o2 = ojo1.upper(), ojo2.upper()
    return (o1 == "OD" and o2 == "OI") or (o1 == "OI" and o2 == "OD")


def _es_ptosis_congenita_o_cronica(text: str | None) -> bool:
    """Determina si las manifestaciones de ptosis palpebral en el texto estan
    identificadas como congenitas, seniles, aponeuroticas o cronicas de larga evolucion,
    lo que descarta la presentacion de una emergencia neurooftalmica aguda."""
    if not text:
        return False
    norm = _normalize_text(text)
    if not norm:
        return False
    matches_ptosis = []
    for kw in _KEYWORDS_PTOSIS:
        for m in _compiled_keyword(kw).finditer(norm):
            if _keyword_matches(norm, kw, allow_negation_window=True):
                matches_ptosis.append(m)
    if not matches_ptosis:
        return False
    return all(
        _clause_has_qualifier(norm, m.start(), m.end(), _KEYWORDS_PTOSIS_CONGENITA_O_CRONICA)
        for m in matches_ptosis
    )


def _pupilas_hallazgos(clinica) -> list[str]:
    """Extrae hallazgos pupilares, descartando anisocoria fisiologica,
    desambiguando Marcus Gunn (pupilar/DPAR vs mandibulopalpebral/ambiguo)
    y excluyendo alteraciones pupilares farmacologicas acotadas a su clausula."""
    if clinica is None:
        return []
    texto_norm = _normalize_text(clinica.reflejos_pupilares)
    if not texto_norm:
        return []
    hallazgos = _extract_normalized_findings(
        clinica.reflejos_pupilares,
        _KEYWORDS_PUPILAS,
        allow_negation_window=True,
    )
    # Desambiguacion Marcus Gunn
    if "marcus gunn" in texto_norm:
        es_mandibulopalpebral = any(
            m in texto_norm for m in (
                "mandibulopalpebral", "mandibulo-palpebral", "mandibulo palpebral",
                "sincinesia", "mandibula", "jaw-winking", "jaw winking",
                "fenomeno de marcus gunn", "fenomeno marcus gunn",
            )
        )
        if es_mandibulopalpebral:
            hallazgos = [h for h in hallazgos if h != "defecto pupilar aferente relativo"]
        else:
            es_dpar_confirmado = any(
                _keyword_matches(texto_norm, tok, allow_negation_window=True)
                for tok in ("pupila", "pupilar", "dpar", "rapd", "defecto", "positivo", "+", "anormal", "patologic")
            )
            if es_dpar_confirmado:
                if "defecto pupilar aferente relativo" not in hallazgos:
                    hallazgos.append("defecto pupilar aferente relativo")
            else:
                hallazgos.append(
                    "sospecha de alteracion pupilar (registro de Marcus Gunn; requiere desambiguar "
                    "pupila de Marcus Gunn vs fenomeno mandibulopalpebral)"
                )

    if "anisocoria" in hallazgos:
        ocurrencias_patologicas = []
        for kw in ("anisocoria",):
            for m in _compiled_keyword(kw).finditer(texto_norm):
                if _keyword_matches(texto_norm, kw, allow_negation_window=True):
                    if not _clause_has_qualifier(texto_norm, m.start(), m.end(), _KEYWORDS_ANISOCORIA_BENIGNA):
                        ocurrencias_patologicas.append(m)
        if not ocurrencias_patologicas:
            hallazgos = [h for h in hallazgos if h != "anisocoria"]

    # Midriasis/miosis inducida por farmacos o dilatacion: filtrar por clausula
    # evitando contaminar hallazgos del ojo contralateral
    for pupila_kw, norm_h in (("midriasis", "midriasis"), ("miosis", "miosis")):
        if norm_h in hallazgos:
            ocurrencias_clinicas = []
            for m in _compiled_keyword(pupila_kw).finditer(texto_norm):
                if _keyword_matches(texto_norm, pupila_kw, allow_negation_window=True):
                    if not _clause_has_qualifier(texto_norm, m.start(), m.end(), _KEYWORDS_PUPILA_FARMACOLOGICA):
                        ocurrencias_clinicas.append(m)
            if not ocurrencias_clinicas:
                hallazgos = [h for h in hallazgos if h != norm_h]

    return hallazgos


@_memoize_cond
def _cond_horner_o_tercer_par_sospecha(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico urgente: alteracion pupilar (anisocoria, midriasis o miosis)
    y ptosis palpebral combinadas ipsilaterales sugieren compromiso de la
    inervacion simpatica (sindrome de Horner) o del III par craneal.

    Descarta:
    1. Ptosis congenita, senil, aponeurotica o cronica (no urgente).
    2. Hallazgos contralaterales demostrados (ej. miosis en OD con ptosis en OI,
       anatomicamente incompatibles con sindrome ipsilateral agudo).
    """
    if req.clinica is None:
        return False
    hallazgos = _pupilas_hallazgos(req.clinica)
    hay_pupila = any(h in hallazgos for h in ("anisocoria", "midriasis", "miosis"))
    if not hay_pupila:
        return False

    hay_ptosis = _contains_keyword(
        req.clinica.anexos_oculares,
        _KEYWORDS_PTOSIS,
        allow_negation_window=True,
    )
    if not hay_ptosis:
        return False

    # Ptosis congenita o cronica no constituye emergencia neurooftalmica aguda
    if _es_ptosis_congenita_o_cronica(req.clinica.anexos_oculares):
        return False

    # Verificar correspondencia de ojo (deben ser ipsilaterales o indeterminados)
    pupil_eye = _extract_finding_eye(
        req.clinica.reflejos_pupilares,
        ("anisocoria", "midriasis", "miosis"),
    )
    ptosis_eye = _extract_finding_eye(
        req.clinica.anexos_oculares,
        _KEYWORDS_PTOSIS,
    )
    if _son_hallazgos_contralaterales(pupil_eye, ptosis_eye):
        return False

    return True


_texto_horner_o_tercer_par_sospecha = (
    "Hallazgo urgente: la presencia simultanea de alteracion pupilar y ptosis palpebral "
    "sugiere compromiso de la inervacion simpatica u oculomotora (sospecha de sindrome de Horner "
    "o paresia del III par craneal), ameritando valoracion neurooftalmologica urgente."
)


def _cond_pupilas_alteradas(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: anisocoria o DPAR en reflejos pupilares ameritan alerta neurooftalmica."""
    if _cond_glaucoma_asimetrico(req) or _cond_horner_o_tercer_par_sospecha(req):
        return False
    return bool(_pupilas_hallazgos(req.clinica))


def _texto_pupilas_alteradas(req: ImpresionClinicaRequest) -> str:
    hallazgos = _pupilas_hallazgos(req.clinica)
    texto = (
        f"En la exploracion pupilar se documenta {_join_hallazgos(hallazgos)}, "
        "lo que amerita valoracion neurooftalmologica."
    )
    if "defecto pupilar aferente relativo" in hallazgos:
        texto += (
            " Hallazgo urgente: la presencia de defecto pupilar aferente relativo es "
            "indicativa de patologia de via optica y requiere evaluacion urgente."
        )
    return texto


def _cond_motilidad_alterada(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: limitacion, nistagmo o dolor al movimiento activan estudio motor."""
    clinica = req.clinica
    if clinica is None or clinica.motilidad_ocular is None:
        return False
    texto = _normalize_text(clinica.motilidad_ocular)
    # Nistagmo optocinetico es una respuesta fisiologica normal (reflejo de seguimiento)
    if "optocinetico" in texto or "okn" in texto:
        otras = tuple(k for k in _KEYWORDS_MOTILIDAD if "nistagmo" not in k and "nistagmus" not in k)
        return any(_keyword_matches(texto, k, allow_negation_window=True) for k in otras)
    return _contains_keyword(
        clinica.motilidad_ocular,
        _KEYWORDS_MOTILIDAD,
        allow_negation_window=True,
    )


_texto_motilidad_alterada = (
    "Se documenta alteracion de la motilidad ocular, lo que amerita estudio de vias "
    "motoras y posible interconsulta neurooftalmologica."
)
