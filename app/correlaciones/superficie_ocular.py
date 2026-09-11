"""Dominio: superficie ocular - tiempo de ruptura lagrimal (3 correlaciones).

but_critico (BUT < 5), but_pantallas y but_limitrofe (ambas cubren 5-9 s segun
exposicion a pantallas). Son mutuamente excluyentes por construccion.
"""
from __future__ import annotations

from app.correlaciones.base import _memoize_cond
from app.correlaciones.texto import (
    _contains_keyword,
    _keyword_matches,
    _normalize_text,
)
from app.schemas import ImpresionClinicaRequest

_KEYWORDS_DGM_BLEFARITIS = (
    "blefaritis", "meibomitis", "disfuncion de meibomio",
    "disfuncion de glandulas de meibomio", "glandulas de meibomio",
    "meibomio", "disfuncion glandular", "dgm",
)


def _cond_but_critico(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: BUT menor de 5 segundos sugiere sospecha de disfuncion lagrimal marcada."""
    clinica = req.clinica
    if clinica is None:
        return False
    but = clinica.ojo_seco_but_seg
    return but is not None and but < 5


def _texto_but_critico(req: ImpresionClinicaRequest) -> str:
    but = req.clinica.ojo_seco_but_seg
    return (
        f"El tiempo de ruptura lagrimal de {but}s es marcadamente reducido, sugiriendo sospecha "
        "de disfuncion de la pelicula lagrimal que amerita evaluacion clinica de la superficie ocular."
    )


def _cond_but_pantallas(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    but = clinica.ojo_seco_but_seg
    return but is not None and 5 <= but <= 9 and clinica.uso_pantallas in ("btw2_6", "gt6")


def _texto_but_pantallas(req: ImpresionClinicaRequest) -> str:
    but = req.clinica.ojo_seco_but_seg
    return (
        f"El tiempo de ruptura lagrimal de {but} segundos es reducido en el contexto "
        "del uso de pantallas, lo que indica inestabilidad de la pelicula lagrimal."
    )


def _cond_but_limitrofe(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: BUT suboptimo sin alta exposicion a pantallas activa hallazgo leve."""
    clinica = req.clinica
    if clinica is None:
        return False
    but = clinica.ojo_seco_but_seg
    return but is not None and 5 <= but <= 9 and clinica.uso_pantallas in (None, "lt2")


def _texto_but_limitrofe(req: ImpresionClinicaRequest) -> str:
    but = req.clinica.ojo_seco_but_seg
    return (
        f"El tiempo de ruptura lagrimal de {but}s se encuentra en rango suboptimo, "
        "sugiriendo inestabilidad leve de la pelicula lagrimal."
    )


@_memoize_cond
def _cond_ojo_seco_evaporativo_dgm(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: alteracion en glandulas de Meibomio o blefaritis + BUT reducido (<10s)
    orienta a sospecha de ojo seco evaporativo segun criterios TFOS DEWS II."""
    clinica = req.clinica
    if clinica is None or clinica.ojo_seco_but_seg is None:
        return False
    if clinica.ojo_seco_but_seg >= 10:
        return False
    if not _contains_keyword(
        clinica.anexos_oculares,
        _KEYWORDS_DGM_BLEFARITIS,
        allow_negation_window=True,
    ):
        return False
    anexos = _normalize_text(clinica.anexos_oculares)
    if any(k in anexos for k in ("permeable", "buena expresibilidad", "expresion normal")):
        otras_dgm = ("blefaritis", "meibomitis", "disfuncion de meibomio", "dgm", "taponamiento", "obstruc")
        return any(_keyword_matches(anexos, k, allow_negation_window=True) for k in otras_dgm)
    return True


_texto_ojo_seco_evaporativo_dgm = (
    "La presencia de alteracion en glandulas de Meibomio o blefaritis asociada a un tiempo "
    "de ruptura lagrimal reducido orienta a sospecha de ojo seco de predominio "
    "evaporativo, ameritando valoracion dirigida a la superficie palpebral y estabilidad lagrimal."
)

