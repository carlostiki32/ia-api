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

# Tolerancias instrumentales aceptables entre lecturas simultaneas:
_TOLERANCIA_CILINDRO_QUERATOMETRICO_D = 0.50
_TOLERANCIA_PROMEDIO_QUERATOMETRICO_D = 0.50
_TOLERANCIA_EJES_ORTOGONALES_GRADOS = 25
_TOLERANCIA_EJE_CILINDRO_GRADOS = 20

# NOTA CLINICA Y METROLOGICA SOBRE RADIOS EN MM Y KER_INDEX:
# Los campos k1_mm, k2_mm, k_promedio_mm y ker_index estan admitidos en el
# esquema para recepcion y almacenamiento de datos biometricos. Sin embargo,
# no se realiza conversion automatica de mm a dioptrias porque la potencia
# equivalente depende del indice queratometrico de calibracion de cada equipo
# (p. ej. 1.3375 en queratometros estandar, 1.332 en topografos, 1.3315 en IOLMaster).
# Las reglas clinicas operan estrictamente sobre lecturas en dioptrias (k1_d, k2_d,
# k_promedio_d, k_cilindro) sin asumir una equivalencia operacional universal.


def _ojo_akr(req: ImpresionClinicaRequest, side: str):
    akr = req.akr
    if akr is None:
        return None
    return getattr(akr, side)


def _axis_distance(a: int | None, b: int | None) -> int | None:
    if a is None or b is None:
        return None
    diff = abs((a % 180) - (b % 180))
    return min(diff, 180 - diff)


def _queratometria_contradictoria(ojo) -> bool:
    """Valida la consistencia interna de las lecturas queratometricas de un ojo.

    Retorna True si existen contradicciones fisicas o metrologicas que superan
    las tolerancias instrumentales, lo que suspende e invalida cualquier inferencia
    etiologica dependiente de la superficie corneal (p. ej. astigmatismo lenticular
    puro, ectasia o cornea plana):
    1. Discordancia entre cilindro informado (k_cilindro) y diferencia entre
       meridianos principales |K1 - K2| > 0.50 D.
    2. Discordancia entre K promedio informado y el promedio aritmetico (K1 + K2)/2 > 0.50 D.
    3. Discordancia entre ejes principales (k1_eje y k2_eje) en presencia de
       astigmatismo relevante (>= 0.75 D): deben ser aproximadamente ortogonales
       (distancia angular ciclica >= 65 grados).
    4. Discordancia del eje de cilindro corneal (k_cilindro_eje) con respecto a
       los meridianos principales (> 20 grados con respecto al eje mas proximo).
    """
    if ojo is None:
        return False

    # 1. Contradiccion entre cilindro corneal explicito y |K1 - K2|
    if ojo.k_cilindro is not None and ojo.k1_d is not None and ojo.k2_d is not None:
        cil_informado = abs(ojo.k_cilindro)
        cil_calculado = abs(ojo.k1_d - ojo.k2_d)
        if abs(cil_informado - cil_calculado) > _TOLERANCIA_CILINDRO_QUERATOMETRICO_D:
            return True

    # 2. Contradiccion entre K promedio informado y (K1 + K2) / 2
    if ojo.k_promedio_d is not None and ojo.k1_d is not None and ojo.k2_d is not None:
        prom_calculado = (ojo.k1_d + ojo.k2_d) / 2.0
        if abs(ojo.k_promedio_d - prom_calculado) > _TOLERANCIA_PROMEDIO_QUERATOMETRICO_D:
            return True

    # 3. Contradiccion en ejes principales (deben ser ortogonales en queratometria regular)
    if ojo.k1_d is not None and ojo.k2_d is not None:
        cil_calc = abs(ojo.k1_d - ojo.k2_d)
        if cil_calc >= _CIL_CORNEAL_RELEVANTE_D:
            if ojo.k1_eje is not None and ojo.k2_eje is not None:
                dist = _axis_distance(ojo.k1_eje, ojo.k2_eje)
                # En un sistema ciclico 0..180, la distancia maxima entre ejes es 90 grados (ortogonales).
                # Si la distancia angular es menor a (90 - 25) = 65 grados, no son ortogonales.
                if dist is not None and dist < (90 - _TOLERANCIA_EJES_ORTOGONALES_GRADOS):
                    return True

            # 4. Eje de cilindro informado vs meridianos principales
            if ojo.k_cilindro_eje is not None and ojo.k1_eje is not None:
                d1 = _axis_distance(ojo.k_cilindro_eje, ojo.k1_eje)
                if d1 is not None:
                    # Debe alinearse o bien con k1_eje (dist <= 20) o con el eje ortogonal k2 (dist >= 70)
                    dist_min_meridiano = min(d1, 90 - d1)
                    if dist_min_meridiano > _TOLERANCIA_EJE_CILINDRO_GRADOS:
                        return True

    return False


def _k_values(ojo) -> list[float]:
    if ojo is None or _queratometria_contradictoria(ojo):
        return []
    return [
        value
        for value in (ojo.k1_d, ojo.k2_d, ojo.k_promedio_d)
        if value is not None
    ]


def _has_keratometry(ojo) -> bool:
    if ojo is None or _queratometria_contradictoria(ojo):
        return False
    return bool(_k_values(ojo)) or ojo.k_cilindro is not None


def _k_steepest_d(ojo) -> float | None:
    """Retorna la potencia dioptrica del meridiano queratometrico mas curvo (K steep).

    NOTA CLINICA Y METROLOGICA: Este valor corresponde al meridiano mas curvo
    medido por queratometria/AKR en la zona optica paracentral (habitualmente ~3 mm).
    NO debe confundirse con el Kmax tomografico/topografico, que mide la curvatura
    puntual maxima en el vertice de una ectasia/cono mediante elevacion o Scheimpflug.
    """
    if ojo is None or _queratometria_contradictoria(ojo):
        return None
    meridianos = [v for v in (ojo.k1_d, ojo.k2_d) if v is not None]
    if meridianos:
        return max(meridianos)
    return ojo.k_promedio_d


# Alias por compatibilidad interna de helpers y tests existentes
_k_max = _k_steepest_d


def _k_flat_d(ojo) -> float | None:
    """Retorna la potencia dioptrica del meridiano queratometrico mas plano (K flat)."""
    if ojo is None or _queratometria_contradictoria(ojo):
        return None
    meridianos = [v for v in (ojo.k1_d, ojo.k2_d) if v is not None]
    if meridianos:
        return min(meridianos)
    return ojo.k_promedio_d


def _corneal_cyl_abs(ojo) -> float | None:
    """Retorna la magnitud absoluta del cilindro corneal queratometrico.

    Si los datos de queratometria son contradictorios entre si, retorna None para
    suspender cualquier inferencia etiologica falsa dependiente de este valor.
    """
    if ojo is None or _queratometria_contradictoria(ojo):
        return None
    if ojo.k1_d is not None and ojo.k2_d is not None:
        return round(abs(ojo.k1_d - ojo.k2_d), 2)
    if ojo.k_cilindro is not None:
        return abs(ojo.k_cilindro)
    return None


def _keratometry_axis(ojo) -> int | None:
    if ojo is None or _queratometria_contradictoria(ojo):
        return None
    return ojo.k_cilindro_eje if ojo.k_cilindro_eje is not None else ojo.k1_eje


def _keratometry_supports_astigmatism(ojo, min_cyl: float = _CIL_CORNEAL_RELEVANTE_D) -> bool:
    cyl = _corneal_cyl_abs(ojo)
    return cyl is not None and cyl >= min_cyl


def _keratometry_axis_matches(ojo, eje: int | None) -> bool:
    distance = _axis_distance(_keratometry_axis(ojo), eje)
    return distance is not None and distance <= _DIF_EJE_RELEVANTE_GRADOS


def _keratometry_suggests_corneal_irregularity(ojo) -> bool:
    if ojo is None or _queratometria_contradictoria(ojo):
        return False
    kmax = _k_steepest_d(ojo)
    cyl = _corneal_cyl_abs(ojo)
    if kmax is not None and kmax >= _K_ECTASIA_D:
        return True
    if kmax is not None and kmax >= _K_SOSPECHOSA_D and (cyl is None or cyl >= 1.50):
        return True
    if cyl is not None and cyl >= _CIL_CORNEAL_MUY_ALTO_D:
        return kmax is None or kmax >= _K_SOSPECHOSA_D
    return False


def _req_has_corneal_irregularity(req: ImpresionClinicaRequest) -> bool:
    return any(
        _keratometry_suggests_corneal_irregularity(_ojo_akr(req, side))
        for side in ("od", "oi")
    )


def _k_promedio(ojo) -> float | None:
    if ojo is None or _queratometria_contradictoria(ojo):
        return None
    if ojo.k1_d is not None and ojo.k2_d is not None:
        return round((ojo.k1_d + ojo.k2_d) / 2.0, 2)
    if ojo.k_promedio_d is not None:
        return ojo.k_promedio_d
    if ojo.k1_d is not None:
        return ojo.k1_d
    if ojo.k2_d is not None:
        return ojo.k2_d
    return None


def _flat_keratometry_parts(req: ImpresionClinicaRequest) -> list[str]:
    parts = []
    for label, side in [("OD", "od"), ("OI", "oi")]:
        ojo = _ojo_akr(req, side)
        if ojo is None or _queratometria_contradictoria(ojo):
            continue
        k_prom = _k_promedio(ojo)
        if k_prom is None or k_prom >= _K_PLANA_D:
            continue
        parts.append(f"{label} (K promedio {k_prom:.2f}D)")
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
        if ojo is None or _queratometria_contradictoria(ojo):
            continue
        if not _keratometry_suggests_corneal_irregularity(ojo):
            continue
        details = []
        kmax = _k_steepest_d(ojo)
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

