"""Helpers de queratometria/AKR: lectura de valores corneales y deteccion de
irregularidad, curvatura plana y soporte astigmatico. La queratometria (dato
estatico corneal) actua como confirmacion o supresor en las correlaciones
refractivas y de AKR, nunca como via de disparo independiente."""
from __future__ import annotations

from app.correlaciones.texto import _join_hallazgos
from app.schemas import ImpresionClinicaRequest

_K_SOSPECHOSA_D = 47.20
_K_ECTASIA_D = 48.70
_CIL_CORNEAL_RELEVANTE_D = 0.75
_CIL_CORNEAL_MUY_ALTO_D = 4.00
_DIF_EJE_RELEVANTE_GRADOS = 20
_K_PLANA_D = 41.00


def _ojo_akr(req: ImpresionClinicaRequest, side: str):
    akr = req.akr
    if akr is None:
        return None
    return getattr(akr, side)


def _k_values(ojo) -> list[float]:
    if ojo is None:
        return []
    return [
        value
        for value in (ojo.k1_d, ojo.k2_d, ojo.k_promedio_d)
        if value is not None
    ]


def _has_keratometry(ojo) -> bool:
    if ojo is None:
        return False
    return bool(_k_values(ojo)) or ojo.k_cilindro is not None


def _k_max(ojo) -> float | None:
    values = _k_values(ojo)
    return max(values) if values else None


def _corneal_cyl_abs(ojo) -> float | None:
    if ojo is None or ojo.k_cilindro is None:
        return None
    return abs(ojo.k_cilindro)


def _axis_distance(a: int | None, b: int | None) -> int | None:
    if a is None or b is None:
        return None
    diff = abs((a % 180) - (b % 180))
    return min(diff, 180 - diff)


def _keratometry_axis(ojo) -> int | None:
    if ojo is None:
        return None
    return ojo.k_cilindro_eje if ojo.k_cilindro_eje is not None else ojo.k1_eje


def _keratometry_supports_astigmatism(ojo, min_cyl: float = _CIL_CORNEAL_RELEVANTE_D) -> bool:
    cyl = _corneal_cyl_abs(ojo)
    return cyl is not None and cyl >= min_cyl


def _keratometry_axis_matches(ojo, eje: int | None) -> bool:
    distance = _axis_distance(_keratometry_axis(ojo), eje)
    return distance is not None and distance <= _DIF_EJE_RELEVANTE_GRADOS


def _keratometry_suggests_corneal_irregularity(ojo) -> bool:
    if ojo is None:
        return False
    kmax = _k_max(ojo)
    cyl = _corneal_cyl_abs(ojo)
    if kmax is not None and kmax >= _K_ECTASIA_D:
        return True
    if kmax is not None and kmax >= _K_SOSPECHOSA_D and (cyl is None or cyl >= 1.50):
        return True
    return cyl is not None and cyl >= _CIL_CORNEAL_MUY_ALTO_D


def _req_has_corneal_irregularity(req: ImpresionClinicaRequest) -> bool:
    return any(
        _keratometry_suggests_corneal_irregularity(_ojo_akr(req, side))
        for side in ("od", "oi")
    )


def _flat_keratometry_parts(req: ImpresionClinicaRequest) -> list[str]:
    parts = []
    for label, side in [("OD", "od"), ("OI", "oi")]:
        ojo = _ojo_akr(req, side)
        if ojo is None or ojo.k_promedio_d is None or ojo.k_promedio_d >= _K_PLANA_D:
            continue
        parts.append(f"{label} (K promedio {ojo.k_promedio_d:.2f}D)")
    return parts


def _format_flat_keratometry(req: ImpresionClinicaRequest) -> str:
    parts = _flat_keratometry_parts(req)
    if not parts:
        return ""
    return _join_hallazgos(parts)


def _corneal_irregularity_parts(req: ImpresionClinicaRequest) -> list[str]:
    parts = []
    for label, side in [("OD", "od"), ("OI", "oi")]:
        ojo = _ojo_akr(req, side)
        if not _keratometry_suggests_corneal_irregularity(ojo):
            continue
        details = []
        kmax = _k_max(ojo)
        cyl = _corneal_cyl_abs(ojo)
        if kmax is not None:
            details.append(f"Kmax {kmax:.2f}D")
        if cyl is not None:
            details.append(f"cilindro corneal {cyl:.2f}D")
        parts.append(f"{label} ({', '.join(details)})")
    return parts


def _format_corneal_irregularity(req: ImpresionClinicaRequest) -> str:
    parts = _corneal_irregularity_parts(req)
    if not parts:
        return ""
    return _join_hallazgos(parts)
