"""Dominio: pupilas y motilidad ocular (2 correlaciones).

pupilas_alteradas (anisocoria, DPAR, midriasis...) y motilidad_alterada
(limitacion, nistagmo, paresia...). pupilas_alteradas se suprime cuando ya
activa glaucoma_asimetrico (que integra el DPAR en su propio enunciado).
"""
from __future__ import annotations

from app.correlaciones.base import _memoize_cond
from app.correlaciones.fondo_de_ojo import _cond_glaucoma_asimetrico
from app.correlaciones.texto import (
    _contains_keyword,
    _extract_normalized_findings,
    _join_hallazgos,
    _keyword_matches,
    _normalize_text,
)
from app.schemas import ImpresionClinicaRequest

_KEYWORDS_PUPILAS = {
    "anisocoria": "anisocoria",
    "midriasis": "midriasis",
    "miosis": "miosis",
    "dpar": "defecto pupilar aferente relativo",
    "rapd": "defecto pupilar aferente relativo",
    "defecto pupilar aferente": "defecto pupilar aferente relativo",
    "marcus gunn": "defecto pupilar aferente relativo",
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


def _pupilas_hallazgos(clinica) -> list[str]:
    """Extrae hallazgos pupilares, descartando anisocoria explicitamente calificada
    de fisiologica/benigna/simple (hallazgo prevalente y benigno, ~15-30% de la
    poblacion)."""
    if clinica is None:
        return []
    hallazgos = _extract_normalized_findings(
        clinica.reflejos_pupilares,
        _KEYWORDS_PUPILAS,
        allow_negation_window=True,
    )
    texto_norm = _normalize_text(clinica.reflejos_pupilares)
    if "anisocoria" in hallazgos:
        if any(term in texto_norm for term in ("fisiologic", "benign", "simple", "esencial")):
            hallazgos = [h for h in hallazgos if h != "anisocoria"]
    # Midriasis/miosis inducida por farmacos o dilatacion no es un hallazgo clinico.
    if any(k in texto_norm for k in _KEYWORDS_PUPILA_FARMACOLOGICA):
        hallazgos = [h for h in hallazgos if h not in ("midriasis", "miosis")]
    return hallazgos


@_memoize_cond
def _cond_horner_o_tercer_par_sospecha(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico urgente: alteracion pupilar (anisocoria) y ptosis palpebral combinadas
    sugieren compromiso simpatico (sindrome de Horner) o del III par craneal."""
    if req.clinica is None:
        return False
    hallazgos = _pupilas_hallazgos(req.clinica)
    hay_pupila = any(h in hallazgos for h in ("anisocoria", "midriasis", "miosis"))
    if not hay_pupila:
        return False
    return _contains_keyword(
        req.clinica.anexos_oculares,
        _KEYWORDS_PTOSIS,
        allow_negation_window=True,
    )


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
