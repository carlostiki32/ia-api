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
    _k_promedio,
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
        f"en {detalle}, hallazgo sugestivo de irregularidad en la curvatura corneal o sospecha de "
        "ectasia incipiente que amerita topografia/tomografia corneal para descarte de queratocono."
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
    if _cond_astigmatismo_lenticular_puro(req):
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


_K_PLANA_EXTREMA_D = 38.00


def _cornea_plana_parts(req: ImpresionClinicaRequest) -> list[str]:
    parts = []
    for label, side in [("OD", "od"), ("OI", "oi")]:
        ojo = _ojo_akr(req, side)
        if ojo is None:
            continue
        if ojo.k_promedio_d is not None:
            k_val = ojo.k_promedio_d
        elif ojo.k1_d is not None and ojo.k2_d is not None:
            k_val = min(ojo.k1_d, ojo.k2_d)
        else:
            k_val = ojo.k1_d if ojo.k1_d is not None else ojo.k2_d
        if k_val is not None and k_val < _K_PLANA_EXTREMA_D:
            parts.append(f"{label} ({k_val:.2f}D)")
    return parts


@_memoize_cond
def _cond_cornea_plana_extrema(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: queratometria marcadamente plana (<38.00 D) indica cornea plana verdadera (CNA1/CNA2)
    y variante anatomica de relevancia refractiva."""
    return bool(_cornea_plana_parts(req))


def _texto_cornea_plana_extrema(req: ImpresionClinicaRequest) -> str:
    partes = _cornea_plana_parts(req)
    ojos = _join_hallazgos(partes) if partes else "la queratometria"
    return (
        f"La queratometria revela curvatura corneal marcadamente plana en {ojos}, "
        "variante anatomica de relevancia refractiva que amerita valoracion del segmento "
        "anterior y monitorizacion biometrica."
    )


def _lenticular_parts(req: ImpresionClinicaRequest) -> list[str]:
    parts = []
    for label, side in [("OD", "od"), ("OI", "oi")]:
        akr_eye = _ojo_akr(req, side)
        rx_eye = getattr(req.refraccion, side) if req.refraccion is not None else None
        if akr_eye is None:
            continue
        cyl_cornea = _corneal_cyl_abs(akr_eye)
        if cyl_cornea is None or cyl_cornea > 0.50:
            continue
        cyl_rx = abs(rx_eye.cilindro) if rx_eye is not None and rx_eye.cilindro is not None else 0.0
        if cyl_rx >= 1.50:
            parts.append(f"{label} (cilindro refractivo {cyl_rx:.2f}D vs cilindro corneal {cyl_cornea:.2f}D)")
    return parts


@_memoize_cond
def _cond_astigmatismo_lenticular_puro(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: astigmatismo refractivo relevante (>= 1.50 D) con cornea queratometricamente esferica
    sugiere componente lenticular/interno (catarata, subluxacion)."""
    return bool(_lenticular_parts(req))


def _texto_astigmatismo_lenticular_puro(req: ImpresionClinicaRequest) -> str:
    partes = _lenticular_parts(req)
    ojos = _join_hallazgos(partes) if partes else "la exploracion"
    return (
        f"Se documenta astigmatismo refractivo relevante en presencia de una superficie corneal "
        f"queratometricamente esferica en {ojos}, lo que sugiere un componente cristaliniano/interno "
        "del defecto y amerita valoracion del segmento anterior para descartar asimetria "
        "cristaliniana o ectopia lentis."
    )


def _asimetria_k_parts(req: ImpresionClinicaRequest) -> tuple[float, float, float] | None:
    od = _ojo_akr(req, "od")
    oi = _ojo_akr(req, "oi")
    if od is None or oi is None:
        return None
    od_k = _k_promedio(od)
    oi_k = _k_promedio(oi)
    if od_k is None or oi_k is None:
        return None
    diff = abs(od_k - oi_k)
    return (diff, od_k, oi_k)


@_memoize_cond
def _cond_queratometria_asimetrica_interocular(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: asimetria queratometrica interocular significativa (>= 1.00 D)
    sin queratocono manifiesto activa tamizaje de ectasia incipiente/forme fruste."""
    if _cond_queratocono_ectasia_sospecha(req):
        return False
    datos = _asimetria_k_parts(req)
    if datos is None:
        return False
    diff, _, _ = datos
    return diff >= 1.00


def _texto_queratometria_asimetrica_interocular(req: ImpresionClinicaRequest) -> str:
    datos = _asimetria_k_parts(req)
    val = f"{datos[0]:.2f}D (OD {datos[1]:.2f}D vs OI {datos[2]:.2f}D)" if datos else "relevante"
    return (
        f"Se documenta asimetria queratometrica interocular significativa ({val}) "
        "sin ectasia corneal manifiesta en el examen actual, hallazgo que amerita monitorizacion "
        "biometrica periodica y estudio tomografico/topografico corneal para descarte de ectasia "
        "asimetrica incipiente o queratocono frustro."
    )


