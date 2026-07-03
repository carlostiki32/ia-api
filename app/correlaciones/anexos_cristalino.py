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


def _cond_anexos_patologicos(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: blefaritis, pterigion o queratitis en anexos activan correlacion."""
    clinica = req.clinica
    if clinica is None:
        return False
    return bool(
        _extract_normalized_findings(
            clinica.anexos_oculares,
            _KEYWORDS_ANEXOS,
            allow_negation_window=True,
        )
    )


def _texto_anexos_patologicos(req: ImpresionClinicaRequest) -> str:
    hallazgos = _extract_normalized_findings(
        req.clinica.anexos_oculares,
        _KEYWORDS_ANEXOS,
        allow_negation_window=True,
    )
    return f"En anexos oculares se documenta {_join_hallazgos(hallazgos)}."


@_memoize_cond
def _cond_opacidad_cristaliniana(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: catarata o pseudofaquia documentadas activan correlacion cristaliniana."""
    clinica = req.clinica
    if clinica is None:
        return False
    texto = " ".join(filter(None, [clinica.anexos_oculares, clinica.fondo_de_ojo]))
    return _contains_keyword(texto, _KEYWORDS_OPACIDAD_CRISTALINO, allow_negation_window=True)


_texto_opacidad_cristaliniana = (
    "Se documenta alteracion del cristalino, ameritando evaluacion biomicroscopica "
    "para caracterizacion y estadificacion de la opacidad."
)
