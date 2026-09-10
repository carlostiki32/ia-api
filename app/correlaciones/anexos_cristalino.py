"""Dominio: anexos oculares y cristalino (2 correlaciones).

anexos_patologicos (blefaritis, pterigion, queratitis...) y opacidad_cristaliniana
(catarata, pseudofaquia...). opacidad_cristaliniana busca en anexos + fondo
concatenados porque en la practica la opacidad cristaliniana se registra en
cualquiera de los dos campos.
"""
from __future__ import annotations

from app.correlaciones.base import _memoize_cond
from app.correlaciones.texto import (
    _contains_keyword,
    _extract_normalized_findings,
    _join_hallazgos,
    _keyword_matches,
    _normalize_text,
)
from app.schemas import ImpresionClinicaRequest

_KEYWORDS_ANEXOS = {
    "blefaritis": "blefaritis",
    "meibomitis": "disfuncion de glandulas de meibomio",
    "disfuncion de meibomio": "disfuncion de glandulas de meibomio",
    "disfuncion glandular": "disfuncion de glandulas de meibomio",
    "dgm": "disfuncion de glandulas de meibomio",
    "chalazion": "chalazion",
    "calacio": "chalazion",
    "calazio": "chalazion",
    "orzuelo": "orzuelo",
    "perrilla": "orzuelo",
    "pterigion": "pterigion",
    "pterigio": "pterigion",
    "carnosidad": "pterigion",
    "pinguecula": "pinguecula",
    "conjuntivitis": "conjuntivitis",
    "hiperemia": "hiperemia conjuntival",
    "inyeccion conjuntival": "hiperemia conjuntival",
    "inyeccion ciliar": "hiperemia conjuntival",
    "queratitis": "queratitis",
    "queratopatia punteada": "queratopatia punteada superficial",
    "erosion": "erosion corneal",
    "abrasion corneal": "erosion corneal",
    "defecto epitelial": "defecto epitelial corneal",
    "leucoma": "leucoma corneal",
    "nubecula": "nubecula corneal",
    "opacidad corneal": "opacidad corneal",
    "edema corneal": "edema corneal",
    "queratopatia bullosa": "queratopatia bullosa",
    "distriquiasis": "distiquiasis",
    "distiquiasis": "distiquiasis",
    "triquiasis": "triquiasis",
    "ectropion": "ectropion",
    "entropion": "entropion",
    "ptosis": "ptosis palpebral",
    "dermatochalasis": "dermatochalasis",
    "lagoftalmos": "lagoftalmos",
    "madarosis": "madarosis",
    "dacriocistitis": "dacriocistitis",
    "xantelasma": "xantelasma",
}
_KEYWORDS_OPACIDAD_CRISTALINO = (
    "catarata",
    "cataratas",
    "opacidad cristaliniana",
    "opacidad del cristalino",
    "opacidad lenticular",
    "opacidad subcapsular",
    "facoesclerosis",
    "esclerosis nuclear",
    "nucleoesclerosis",
    "esclerosis del cristalino",
    "pseudofaquia",
    "pseudofaco",
    "pseudofaquico",
    "lente intraocular",
    "iol",
    "afaquia",
    "afaquico",
)


def _anexos_hallazgos(req: ImpresionClinicaRequest) -> list[str]:
    clinica = req.clinica
    if clinica is None:
        return []
    hallazgos = _extract_normalized_findings(
        clinica.anexos_oculares,
        _KEYWORDS_ANEXOS,
        allow_negation_window=True,
    )
    from app.correlaciones.pupilas_motilidad import _cond_horner_o_tercer_par_sospecha
    if _cond_horner_o_tercer_par_sospecha(req):
        hallazgos = [h for h in hallazgos if h != "ptosis palpebral"]
    return hallazgos


def _cond_anexos_patologicos(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: blefaritis, pterigion o queratitis en anexos activan correlacion."""
    return bool(_anexos_hallazgos(req))


def _texto_anexos_patologicos(req: ImpresionClinicaRequest) -> str:
    hallazgos = _anexos_hallazgos(req)
    return f"En anexos oculares se documenta {_join_hallazgos(hallazgos)}."


@_memoize_cond
def _cond_opacidad_cristaliniana(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: catarata o pseudofaquia documentadas activan correlacion cristaliniana."""
    clinica = req.clinica
    if clinica is None:
        return False
    texto = " ".join(filter(None, [clinica.anexos_oculares, clinica.fondo_de_ojo]))
    return _contains_keyword(texto, _KEYWORDS_OPACIDAD_CRISTALINO, allow_negation_window=True)


def _texto_opacidad_cristaliniana(req: ImpresionClinicaRequest) -> str:
    texto = " ".join(filter(None, [
        req.clinica.anexos_oculares if req.clinica else None,
        req.clinica.fondo_de_ojo if req.clinica else None,
    ]))
    texto_norm = _normalize_text(texto)
    pseudofaquico_tokens = ("pseudofaquia", "pseudofaco", "pseudofaquico", "lente intraocular", "lio", "iol", "afaquia", "afaquico")
    catarata_tokens = ("catarata", "esclerosis", "facoesclerosis", "nucleoesclerosis", "opacidad del cristalino", "opacidad cristaliniana")

    es_pseudofaquico = any(_keyword_matches(texto_norm, t, allow_negation_window=True) for t in pseudofaquico_tokens)
    es_catarata = any(_keyword_matches(texto_norm, t, allow_negation_window=True) for t in catarata_tokens)

    if es_pseudofaquico and not es_catarata:
        return (
            "Se documenta condicion de pseudofaquia o presencia de lente intraocular, ameritando "
            "evaluacion biomicroscopica para verificar la transparencia capsular y la posicion del implante."
        )
    return (
        "Se documenta alteracion del cristalino, ameritando evaluacion biomicroscopica "
        "para caracterizacion y estadificacion de la opacidad."
    )


_KEYWORDS_GLAUCOMA_SECUNDARIO = (
    "krukenberg", "huso de krukenberg",
    "dispersion pigmentaria", "sindrome de dispersion pigmentaria",
    "pseudoexfoliacion", "pseudoexfoliativo", "material pseudoexfoliativo",
    "pxf", "pex", "sampaolesi", "linea de sampaolesi",
)


@_memoize_cond
def _cond_anexos_riesgo_glaucoma_secundario(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: signos en polo anterior compatibles con dispersion pigmentaria o pseudoexfoliacion."""
    if req.clinica is None:
        return False
    texto = " ".join(filter(None, [req.clinica.anexos_oculares, req.clinica.fondo_de_ojo]))
    if not texto:
        return False
    texto_norm = _normalize_text(texto)
    return any(_keyword_matches(texto_norm, k, allow_negation_window=True) for k in _KEYWORDS_GLAUCOMA_SECUNDARIO)


_texto_anexos_riesgo_glaucoma_secundario = (
    "En la biomicroscopia del segmento anterior se documentan signos compatibles con "
    "sindrome de dispersion pigmentaria o pseudoexfoliacion, entidades con predisposicion "
    "al desarrollo de glaucoma secundario de angulo abierto que ameritan gonioscopia y "
    "control periodico de la presion intraocular."
)

