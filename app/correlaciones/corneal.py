"""Hallazgos de cornea y queratometria: cuatro correlaciones activas.

La comparacion de Rx y queratometria no identifica una causa lenticular.
"""
from __future__ import annotations

from app.correlaciones.base import _memoize_cond
from app.correlaciones.queratometria import (
    _axis_distance,
    _corneal_cyl_abs,
    _corneal_irregularity_parts,
    _contexto_mediciones,
    _k_flat_d,
    _k_promedio,
    _keratometry_axis,
    _ojo_akr,
    _queratometria_contradictoria,
    _req_has_corneal_irregularity,
)
from app.correlaciones.texto import _join_hallazgos
from app.schemas import ImpresionClinicaRequest

# Umbrales operativos de revision de discrepancias cornea vs Rx final.
# No identifican etiologia; pendientes de validacion clinica (auditoria #36).
_CIL_RX_MINIMO_D = 0.75          # la Rx debe tener cilindro no trivial
_DIF_MAGNITUD_RELEVANTE_D = 1.25  # criterio operativo; no umbral de enfermedad lenticular
_CIL_PARA_COMPARAR_EJE_D = 1.00   # ambos cilindros deben ser reales para comparar eje
_DIF_EJE_RELEVANTE_GRADOS = 15


@_memoize_cond
def _cond_queratocono_ectasia_sospecha(req: ImpresionClinicaRequest) -> bool:
    """Selecciona valores queratometricos elevados para revision descriptiva."""
    return _req_has_corneal_irregularity(req)


def _texto_queratocono_ectasia_sospecha(req: ImpresionClinicaRequest) -> str:
    partes = _corneal_irregularity_parts(req)
    detalle = _join_hallazgos(partes) if partes else "la queratometria"
    return (
        f"La queratometria registrada presenta valores elevados en {detalle}. "
        "Verificar repetibilidad, condiciones de medicion y antecedentes; si persisten "
        "sin explicacion o coexisten hallazgos clinicos, valorar evaluacion corneal "
        "especializada y la necesidad de topografia/tomografia. Estos valores aislados "
        "no establecen la anatomia ni la causa del hallazgo."
        + _contexto_mediciones(req)
    )


def _mismatch_parts(req: ImpresionClinicaRequest) -> list[str]:
    partes: list[str] = []
    for label, side in [("OD", "od"), ("OI", "oi")]:
        akr_eye = _ojo_akr(req, side)
        rx_eye = getattr(req.refraccion, side) if req.refraccion is not None else None
        if akr_eye is None or rx_eye is None or _queratometria_contradictoria(akr_eye):
            continue
        corneal = _corneal_cyl_abs(akr_eye)
        rx_cyl = rx_eye.cilindro
        if corneal is None or rx_cyl is None or abs(rx_cyl) < _CIL_RX_MINIMO_D:
            continue
        rx_abs = abs(rx_cyl)
        diferencia_magnitud = abs(corneal - rx_abs)
        magnitud_discrepa = diferencia_magnitud >= _DIF_MAGNITUD_RELEVANTE_D
        eje_discrepa = False
        eje_corneal = _keratometry_axis(akr_eye)
        distancia = None
        if corneal >= _CIL_PARA_COMPARAR_EJE_D and rx_abs >= _CIL_PARA_COMPARAR_EJE_D:
            distancia = _axis_distance(eje_corneal, rx_eye.eje)
            eje_discrepa = distancia is not None and distancia >= _DIF_EJE_RELEVANTE_GRADOS
        if magnitud_discrepa or eje_discrepa:
            detalle = (
                f"cilindro de la prescripcion final {rx_cyl:+.2f}D; "
                f"cilindro corneal queratometrico {corneal:.2f}D; "
                f"diferencia de magnitudes {diferencia_magnitud:.2f}D"
            )
            if distancia is not None:
                detalle += (f"; eje Rx {rx_eye.eje % 180} grados; "
                            f"meridiano plano K {eje_corneal % 180} grados; "
                            f"diferencia de orientacion {distancia} grados")
            else:
                detalle += "; orientacion no comparada por datos insuficientes"
            partes.append(
                f"{label} ({detalle})"
            )
    return partes


def _cond_astigmatismo_corneal_vs_refractivo(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: el cilindro corneal queratometrico y el cilindro refractivo
    prescrito discrepan en magnitud o eje, sin establecer la causa de la diferencia."""
    if req.refraccion is None or req.akr is None:
        return False
    return bool(_mismatch_parts(req))


def _texto_astigmatismo_corneal_vs_refractivo(req: ImpresionClinicaRequest) -> str:
    partes = _mismatch_parts(req)
    return (
        f"Se registra diferencia entre el astigmatismo corneal queratometrico y el cilindro "
        f"de la prescripcion final en {_join_hallazgos(partes)}. Revisar mediciones, "
        "condiciones de captura y criterio de prescripcion e interpretar con la exploracion. "
        "Esta comparacion descriptiva no calcula un residual optico, no acredita "
        "simultaneidad de las mediciones ni establece la causa de la diferencia."
        + _contexto_mediciones(req)
    )


_K_PLANA_EXTREMA_D = 38.00


def _cornea_plana_parts(req: ImpresionClinicaRequest) -> list[str]:
    parts = []
    for label, side in [("OD", "od"), ("OI", "oi")]:
        ojo = _ojo_akr(req, side)
        if ojo is None or _queratometria_contradictoria(ojo):
            continue
        # La media explícita sigue siendo un dato al agregar un solo meridiano.
        # No se reconstruye el meridiano ausente ni se cambia la fuente de la media.
        fuentes = [("K1 registrada", ojo.k1_d), ("K2 registrada", ojo.k2_d),
                   ("K promedio registrada", ojo.k_promedio_d)]
        bajas = [(nombre, valor) for nombre, valor in fuentes
                 if valor is not None and valor < _K_PLANA_EXTREMA_D]
        if bajas:
            fuente, k_val = min(bajas, key=lambda dato: dato[1])
            parcial = ", queratometria parcial" if (ojo.k1_d is None) != (ojo.k2_d is None) else ""
            parts.append(f"{label} ({fuente} {k_val:.2f}D{parcial})")
    return parts


@_memoize_cond
def _cond_cornea_plana_extrema(req: ImpresionClinicaRequest) -> bool:
    """Selecciona una K registrada <38 D sin establecer etiologia ni anatomia global."""
    return bool(_cornea_plana_parts(req))


def _texto_cornea_plana_extrema(req: ImpresionClinicaRequest) -> str:
    partes = _cornea_plana_parts(req)
    ojos = _join_hallazgos(partes) if partes else "la queratometria"
    return (
        f"La queratometria registra un valor de curvatura bajo en {ojos}. "
        "Verificar lectura, repetibilidad y antecedentes corneales; si persiste sin "
        "explicacion o coexisten hallazgos clinicos, valorar el segmento anterior. "
        "Esta medicion aislada no establece la anatomia global ni su causa."
        + _contexto_mediciones(req)
    )


def _asimetria_k_parts(req: ImpresionClinicaRequest) -> tuple[float, float, float] | None:
    od = _ojo_akr(req, "od")
    oi = _ojo_akr(req, "oi")
    if od is None or oi is None:
        return None
    if _queratometria_contradictoria(od) or _queratometria_contradictoria(oi):
        return None
    od_k = _k_promedio(od)
    oi_k = _k_promedio(oi)
    if od_k is None or oi_k is None:
        return None
    diff = abs(od_k - oi_k)
    return (diff, od_k, oi_k)


@_memoize_cond
def _cond_queratometria_asimetrica_interocular(req: ImpresionClinicaRequest) -> bool:
    """Diferencia operativa >=1 D entre medias completas; no diagnostica ectasia."""
    datos = _asimetria_k_parts(req)
    if datos is None:
        return False
    diff, _, _ = datos
    return diff >= 1.00


def _texto_queratometria_asimetrica_interocular(req: ImpresionClinicaRequest) -> str:
    datos = _asimetria_k_parts(req)
    val = f"{datos[0]:.2f}D (OD {datos[1]:.2f}D vs OI {datos[2]:.2f}D)" if datos else "relevante"
    return (
        f"Diferencia de K media registrada entre ojos de {val}. "
        "Verificar mediciones, repetibilidad y antecedentes; si persiste sin explicacion "
        "o coexisten hallazgos clinicos, valorar evaluacion corneal especializada. "
        "La diferencia numerica aislada no establece una enfermedad ni su ausencia."
        + _contexto_mediciones(req)
    )


