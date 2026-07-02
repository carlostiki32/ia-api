"""Dominio: superficie ocular - tiempo de ruptura lagrimal (3 correlaciones).

but_critico (BUT < 5), but_pantallas y but_limitrofe (ambas cubren 5-9 s segun
exposicion a pantallas). Son mutuamente excluyentes por construccion.
"""
from __future__ import annotations

from app.schemas import ImpresionClinicaRequest


def _cond_but_critico(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: BUT menor de 5 segundos activa sospecha de ojo seco clinico."""
    clinica = req.clinica
    if clinica is None:
        return False
    but = clinica.ojo_seco_but_seg
    return but is not None and but < 5


def _texto_but_critico(req: ImpresionClinicaRequest) -> str:
    but = req.clinica.ojo_seco_but_seg
    return (
        f"El tiempo de ruptura lagrimal de {but}s es patologicamente bajo, compatible "
        "con ojo seco clinico que amerita evaluacion."
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
