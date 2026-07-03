"""Dominio: cornea / queratometria como disparador (2 correlaciones).

queratocono_ectasia_sospecha y astigmatismo_corneal_vs_refractivo. Son la
EXCEPCION explicita a la regla general "la queratometria solo confirma o matiza":
aqui el dato corneal SI dispara de forma independiente, porque describe un proceso
propio (ectasia corneal, astigmatismo lenticular) que ninguna otra correlacion
cubre. Solo aplican cuando existen valores queratometricos; son none-safe.
"""
from __future__ import annotations

from app.correlaciones.base import _memoize_cond
from app.correlaciones.queratometria import (
    _axis_distance,
    _corneal_cyl_abs,
    _corneal_irregularity_parts,
    _keratometry_axis,
    _ojo_akr,
    _req_has_corneal_irregularity,
)
from app.correlaciones.texto import _join_hallazgos
from app.schemas import ImpresionClinicaRequest

# Umbrales del contraste cornea vs refraccion final (deteccion de astigmatismo
# lenticular o de un posible error de transposicion/registro del cilindro).
_CIL_RX_MINIMO_D = 0.75          # la Rx debe tener cilindro no trivial
_DIF_MAGNITUD_RELEVANTE_D = 1.25  # generoso: la regla de Javal ya espera ~0.5D lenticular ATR
_CIL_PARA_COMPARAR_EJE_D = 1.00   # ambos cilindros deben ser reales para comparar eje
_DIF_EJE_RELEVANTE_GRADOS = 15


@_memoize_cond
def _cond_queratocono_ectasia_sospecha(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: curvatura corneal muy pronunciada o cilindro corneal muy alto
    en la queratometria sugieren irregularidad/ectasia y ameritan topografia."""
    return _req_has_corneal_irregularity(req)


def _texto_queratocono_ectasia_sospecha(req: ImpresionClinicaRequest) -> str:
    partes = _corneal_irregularity_parts(req)
    detalle = _join_hallazgos(partes) if partes else "la queratometria"
    return (
        f"La queratometria documenta curvatura corneal pronunciada o cilindro corneal elevado "
        f"en {detalle}, hallazgo compatible con irregularidad de la superficie corneal o posible "
        "ectasia que amerita topografia/tomografia corneal para descarte de queratocono."
    )


def _mismatch_parts(req: ImpresionClinicaRequest) -> list[str]:
    partes: list[str] = []
    for label, side in [("OD", "od"), ("OI", "oi")]:
        akr_eye = _ojo_akr(req, side)
        rx_eye = getattr(req.refraccion, side) if req.refraccion is not None else None
        if akr_eye is None or rx_eye is None:
            continue
        corneal = _corneal_cyl_abs(akr_eye)
        rx_cyl = rx_eye.cilindro
        if corneal is None or rx_cyl is None or abs(rx_cyl) < _CIL_RX_MINIMO_D:
            continue
        rx_abs = abs(rx_cyl)
        magnitud_discrepa = abs(corneal - rx_abs) >= _DIF_MAGNITUD_RELEVANTE_D
        eje_discrepa = False
        if corneal >= _CIL_PARA_COMPARAR_EJE_D and rx_abs >= _CIL_PARA_COMPARAR_EJE_D:
            distancia = _axis_distance(_keratometry_axis(akr_eye), rx_eye.eje)
            eje_discrepa = distancia is not None and distancia >= _DIF_EJE_RELEVANTE_GRADOS
        if magnitud_discrepa or eje_discrepa:
            partes.append(
                f"{label} (cilindro refractivo {rx_cyl:+.2f}D vs cilindro corneal {corneal:.2f}D)"
            )
    return partes


def _cond_astigmatismo_corneal_vs_refractivo(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: el cilindro corneal queratometrico y el cilindro refractivo
    prescrito discrepan en magnitud o eje, lo que orienta a astigmatismo lenticular
    o a una revision de la transposicion/registro del cilindro."""
    if req.refraccion is None or req.akr is None:
        return False
    return bool(_mismatch_parts(req))


def _texto_astigmatismo_corneal_vs_refractivo(req: ImpresionClinicaRequest) -> str:
    partes = _mismatch_parts(req)
    return (
        f"Se documenta discrepancia entre el astigmatismo corneal queratometrico y el cilindro "
        f"refractivo prescrito en {_join_hallazgos(partes)}, lo que puede corresponder a un "
        "componente astigmatico lenticular o ameritar la revision de la transposicion y el "
        "registro del cilindro en la refraccion final."
    )
