"""Lectura descriptiva de queratometria/AKR y filtros operativos de coherencia.

Los valores pueden seleccionar avisos corneales propios; no identifican causas
refractivas ni sustituyen exploraciones, mapas corneales o datos de temporalidad.
"""
from __future__ import annotations

import re

from app.correlaciones.texto import _join_hallazgos, _normalize_text
from app.schemas import ImpresionClinicaRequest

_K_SOSPECHOSA_D = 47.20
_K_ECTASIA_D = 48.70
_CIL_CORNEAL_RELEVANTE_D = 0.75
_CIL_CORNEAL_MUY_ALTO_D = 4.00
_DIF_EJE_RELEVANTE_GRADOS = 20
_K_PLANA_D = 41.00

# Tolerancias operativas de coherencia interna; no acreditan precision del
# instrumento ni simultaneidad de las lecturas.
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


def _contexto_mediciones(req: ImpresionClinicaRequest) -> str:
    """Conserva contexto literal, sin convertir menciones o negaciones en diagnosticos.

    El seguimiento libre puede ser extenso: se seleccionan frases completas
    relacionadas con interpretacion de las mediciones, sin inferir lateralidad.
    """
    campos = [("motivo", req.paciente.motivo_consulta if req.paciente else None)]
    if req.clinica:
        campos.extend((nombre, getattr(req.clinica, nombre)) for nombre in
                      ("anexos_oculares", "fondo_de_ojo", "recomendacion_seguimiento"))
    claves = ("provisional", "fiable", "repetir", "estable", "conocid", "seguimiento",
              "evaluad", "dilatacion", "gonioscop", "pseudofa", "afaqui", "lasik",
              "cirugia", "ortoquerat", "lentes de contacto", "adaptad", "tolerancia",
              "correccion completa", "reduc", "prescri", "queratocono", "ectasia",
              "topogra", "tomogra", "inestable", "crosslink", "cornea plana",
              "lente de contacto", "curvatura elevada", "habitual", "pendiente", "optotipo")
    partes = []
    for nombre, texto in campos:
        if not texto:
            continue
        frases = [f.strip() for f in re.split(r"(?<=[.!?;])\s+", texto)
                  if any(k in _normalize_text(f) for k in claves)]
        if frases:
            partes.append(f"{nombre}: «{' '.join(frases)}»")
    if not partes:
        return ""
    return (" Interpretar con el contexto consignado: " + "; ".join(partes)
            + ". Verificar cualquier lectura declarada provisional o poco fiable antes de clasificarla.")


def _axis_distance(a: int | None, b: int | None) -> int | None:
    if a is None or b is None:
        return None
    diff = abs((a % 180) - (b % 180))
    return min(diff, 180 - diff)


def _queratometria_contradictoria(ojo) -> bool:
    """Valida la consistencia interna de las lecturas queratometricas de un ojo.

    Retorna True si las discrepancias superan los filtros operativos internos;
    se abstiene de comparar esas lecturas sin establecer su causa o validez clinica:
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

    Si no pasan los filtros de coherencia, retorna None. Conserva la precision
    de los datos para seleccionar avisos; el redondeo solo corresponde a la salida.
    """
    if ojo is None or _queratometria_contradictoria(ojo):
        return None
    if ojo.k1_d is not None and ojo.k2_d is not None:
        return abs(ojo.k1_d - ojo.k2_d)
    if ojo.k_cilindro is not None:
        return abs(ojo.k_cilindro)
    return None


def _keratometry_axis(ojo) -> int | None:
    """Orientacion del meridiano plano documentado para comparar con Rx negativa.

    El signo de k_cilindro no documenta la convencion de k_cilindro_eje.
    No se rota ni reutiliza ese eje aislado como si fuese cilindro refractivo.
    """
    if ojo is None or _queratometria_contradictoria(ojo):
        return None
    if ojo.k1_d is not None and ojo.k2_d is not None:
        return ojo.k1_eje if ojo.k1_d <= ojo.k2_d else ojo.k2_eje
    if ojo.k1_d is not None:
        return ojo.k1_eje
    return None


def _keratometry_supports_astigmatism(ojo, min_cyl: float = _CIL_CORNEAL_RELEVANTE_D) -> bool:
    cyl = _corneal_cyl_abs(ojo)
    return cyl is not None and cyl >= min_cyl


def _keratometry_axis_matches(ojo, eje: int | None) -> bool:
    distance = _axis_distance(_keratometry_axis(ojo), eje)
    return distance is not None and distance <= _DIF_EJE_RELEVANTE_GRADOS


def _keratometry_suggests_corneal_irregularity(ojo) -> bool:
    """Seleccion numerica para revision; no identifica irregularidad ni ectasia.

    El nombre se conserva por compatibilidad interna. Un dato ausente nunca
    satisface un criterio positivo; el cilindro elevado conserva su valor
    descriptivo aunque se completen meridianos de menor curvatura.
    """
    if ojo is None or _queratometria_contradictoria(ojo):
        return False
    # La media explicita sigue siendo un dato registrado cuando solo se agrega
    # un meridiano compatible; no es ese meridiano ni desaparece por parcialidad.
    valores_k = _k_values(ojo)
    kmax = max(valores_k) if valores_k else None
    cyl = _corneal_cyl_abs(ojo)
    if kmax is not None and kmax >= _K_ECTASIA_D:
        return True
    if kmax is not None and kmax >= _K_SOSPECHOSA_D and cyl is not None and cyl >= 1.50:
        return True
    if cyl is not None and cyl >= _CIL_CORNEAL_MUY_ALTO_D:
        return True
    return False


def _req_has_corneal_irregularity(req: ImpresionClinicaRequest) -> bool:
    return any(
        _keratometry_suggests_corneal_irregularity(_ojo_akr(req, side))
        for side in ("od", "oi")
    )


def _k_promedio(ojo) -> float | None:
    """Media completa sin redondeo previo a los umbrales de seleccion."""
    if ojo is None or _queratometria_contradictoria(ojo):
        return None
    if ojo.k1_d is not None and ojo.k2_d is not None:
        return (ojo.k1_d + ojo.k2_d) / 2.0
    if ojo.k_promedio_d is not None:
        return ojo.k_promedio_d
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
        cyl = _corneal_cyl_abs(ojo)
        meridianos = [v for v in (ojo.k1_d, ojo.k2_d) if v is not None]
        if meridianos:
            details.append(f"mayor meridiano registrado {max(meridianos):.2f}D")
            for campo, nombre in (("k1_d", "K1"), ("k2_d", "K2")):
                valor = getattr(ojo, campo)
                if valor is not None:
                    details.append(f"{nombre} registrada {valor:.2f}D")
            if (ojo.k1_d is None) != (ojo.k2_d is None):
                details.append("queratometria parcial")
        if ojo.k_promedio_d is not None:
            details.append(f"K promedio registrada {ojo.k_promedio_d:.2f}D")
        if cyl is not None:
            details.append(f"cilindro corneal {cyl:.2f}D")
        parts.append(f"{label} ({', '.join(details)})")
    return parts


def _format_corneal_irregularity(req: ImpresionClinicaRequest) -> str:
    parts = _corneal_irregularity_parts(req)
    if not parts:
        return ""
    return _join_hallazgos(parts)

