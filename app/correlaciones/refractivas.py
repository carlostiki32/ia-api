"""Dominio: refraccion final prescrita (5 correlaciones).

miopia_magna, hipermetropia_alta, anisometropia, astig_oblicuo, av_cc_limitada.
Se disparan por la Rx final (esfera/cilindro/eje/AV); la queratometria se usa
solo como confirmacion o matiz corneal, nunca como disparador independiente.
"""
from __future__ import annotations

from app.correlaciones.base import _memoize_cond
from app.correlaciones.queratometria import (
    _corneal_cyl_abs,
    _format_corneal_irregularity,
    _format_flat_keratometry,
    _has_keratometry,
    _keratometry_axis_matches,
    _keratometry_suggests_corneal_irregularity,
    _keratometry_supports_astigmatism,
    _ojo_akr,
)
from app.correlaciones.refraccion_utils import (
    _av_categoria,
    _av_es_limitada,
    _equivalente_esferico,
    _format_eyes_with_values,
)
from app.schemas import ImpresionClinicaRequest


@_memoize_cond
def _cond_miopia_magna(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: equivalente esferico de -6.00D o menor en un ojo activa miopia magna."""
    refraccion = req.refraccion
    if refraccion is None:
        return False
    for ojo in (refraccion.od, refraccion.oi):
        ee = _equivalente_esferico(ojo.esfera, ojo.cilindro)
        if ee is not None and ee <= -6.00:
            return True
    return False


def _texto_miopia_magna(req: ImpresionClinicaRequest) -> str:
    ojos = []
    for label, ojo in [("OD", req.refraccion.od), ("OI", req.refraccion.oi)]:
        ee = _equivalente_esferico(ojo.esfera, ojo.cilindro)
        if ee is not None and ee <= -6.00:
            ojos.append((label, ee))
    muy_alta = any(ee <= -8.00 for _, ee in ojos)
    severidad = "muy alta" if muy_alta else "alta"
    riesgo = "riesgo significativamente elevado" if muy_alta else "mayor riesgo"
    texto = (
        f"Se documenta miopia de magnitud {severidad} en {_format_eyes_with_values(ojos, 'EE')}, "
        f"lo que conlleva {riesgo} de patologia retiniana periferica y macular."
    )
    cornea = _format_corneal_irregularity(req)
    if cornea:
        texto += (
            f" La queratometria muestra curvatura corneal pronunciada en {cornea}, lo que sugiere "
            "un componente corneal (no exclusivamente axial) en la magnitud miopica, y amerita "
            "estudio topografico antes de asumir el mismo riesgo de patologia retiniana periferica "
            "asociado a la miopia axial pura."
        )
    return texto


# Hipermetropia alta: EE >= +5.00 D pero con un componente esferico genuinamente
# hipermetropico (>= +3.00 D). El piso de esfera evita clasificar como "hipermetropia
# alta" a un gran astigmata (p. ej. +1.00 esf +8.00 cil, EE +5.00) cuyo riesgo de
# cierre angular/acomodativo lo determina la esfera, no el cilindro.
_HIPERMETROPIA_EE_MIN = 5.00
_HIPERMETROPIA_ESFERA_MIN = 3.00


def _es_hipermetropia_alta(ojo) -> bool:
    ee = _equivalente_esferico(ojo.esfera, ojo.cilindro)
    return (
        ee is not None
        and ee >= _HIPERMETROPIA_EE_MIN
        and ojo.esfera is not None
        and ojo.esfera >= _HIPERMETROPIA_ESFERA_MIN
    )


def _cond_hipermetropia_alta(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: equivalente esferico de +5.00D o mayor (con esfera >= +3.00D) activa hipermetropia alta."""
    refraccion = req.refraccion
    if refraccion is None:
        return False
    return any(_es_hipermetropia_alta(ojo) for ojo in (refraccion.od, refraccion.oi))


def _texto_hipermetropia_alta(req: ImpresionClinicaRequest) -> str:
    ojos = []
    for label, ojo in [("OD", req.refraccion.od), ("OI", req.refraccion.oi)]:
        if _es_hipermetropia_alta(ojo):
            ee = _equivalente_esferico(ojo.esfera, ojo.cilindro)
            ojos.append((label, ee))
    base = f"Se documenta hipermetropia alta en {_format_eyes_with_values(ojos, 'EE')}"
    edad = req.paciente.edad if req.paciente is not None else None
    if edad is None or edad >= 40:
        texto = (
            f"{base}, lo que amerita evaluacion de la profundidad de camara anterior "
            "ante el riesgo asociado de angulo camerular estrecho."
        )
    else:
        texto = (
            f"{base}, con demanda acomodativa significativa que amerita vigilancia de "
            "esoforia o esotropia acomodativa."
        )
    cornea = _format_corneal_irregularity(req)
    plana = _format_flat_keratometry(req)
    if cornea:
        texto += f" La queratometria documenta curvatura corneal pronunciada en {cornea}, hallazgo que no explica por si solo la hipermetropia alta pero si modifica la interpretacion del astigmatismo asociado."
    elif plana:
        texto += f" La queratometria muestra curvatura corneal plana en {plana}, compatible con un componente corneal (y no exclusivamente axial) de la hipermetropia."
    return texto


def _cond_anisometropia(req: ImpresionClinicaRequest) -> bool:
    refraccion = req.refraccion
    if refraccion is None:
        return False
    ee_od = _equivalente_esferico(refraccion.od.esfera, refraccion.od.cilindro)
    ee_oi = _equivalente_esferico(refraccion.oi.esfera, refraccion.oi.cilindro)
    if ee_od is None or ee_oi is None:
        return False
    return abs(ee_od - ee_oi) > 1.00


def _texto_anisometropia(req: ImpresionClinicaRequest) -> str:
    ee_od = _equivalente_esferico(req.refraccion.od.esfera, req.refraccion.od.cilindro)
    ee_oi = _equivalente_esferico(req.refraccion.oi.esfera, req.refraccion.oi.cilindro)
    diff = abs(ee_od - ee_oi)
    if diff < 2.00:
        severidad = "leve"
        cierre = "con posible impacto en la fusion binocular"
    elif diff <= 3.00:
        severidad = "moderada"
        cierre = "con posible impacto en la fusion binocular"
    else:
        severidad = "severa"
        cierre = "con diferencia significativa entre ambos ojos"
    if ee_od * ee_oi < 0:
        cierre = "antimetropia con posible compromiso fusional"
    texto = (
        f"Existe anisometropia {severidad} por diferencia de equivalente esferico de {diff:.2f}D "
        f"entre OD ({ee_od:+.2f}) y OI ({ee_oi:+.2f}); {cierre}."
    )
    # La anisometropia es factor de ambliopia solo dentro del periodo de
    # maduracion visual (~hasta los 8-9 anos); en el adulto con anisometropia de
    # larga data el impacto suele limitarse a la fusion/aniseiconia. Se modula el
    # mensaje segun la edad cuando esta disponible.
    edad = req.paciente.edad if req.paciente is not None else None
    if edad is not None and edad <= 8:
        texto += (
            " En este grupo de edad la anisometropia es factor de riesgo de ambliopia, "
            "por lo que amerita correccion optica temprana y control del desarrollo visual."
        )
    od_akr = _ojo_akr(req, "od")
    oi_akr = _ojo_akr(req, "oi")
    if _has_keratometry(od_akr) and _has_keratometry(oi_akr):
        od_k = od_akr.k_promedio_d
        oi_k = oi_akr.k_promedio_d
        if od_k is not None and oi_k is not None and abs(od_k - oi_k) >= 1.00:
            texto += f" La queratometria agrega asimetria corneal interocular de {abs(od_k - oi_k):.2f}D en K promedio."
        elif (
            _corneal_cyl_abs(od_akr) is not None
            and _corneal_cyl_abs(oi_akr) is not None
            and abs(_corneal_cyl_abs(od_akr) - _corneal_cyl_abs(oi_akr)) >= 1.50
        ):
            texto += " La queratometria agrega asimetria interocular relevante del cilindro corneal."
    return texto


def _cond_av_cc_limitada(req: ImpresionClinicaRequest) -> bool:
    refraccion = req.refraccion
    if refraccion is None:
        return False
    return _av_es_limitada(refraccion.od.av_cc) or _av_es_limitada(refraccion.oi.av_cc)


def _texto_av_cc_limitada(req: ImpresionClinicaRequest) -> str:
    partes = []
    for label, side, av in [
        ("OD", "od", req.refraccion.od.av_cc),
        ("OI", "oi", req.refraccion.oi.av_cc),
    ]:
        if not _av_es_limitada(av):
            continue
        detalle = f"{label} ({av}): {_av_categoria(av)}"
        ojo_akr = _ojo_akr(req, side)
        if _keratometry_suggests_corneal_irregularity(ojo_akr):
            detalle += (
                ", con queratometria compatible con irregularidad de la superficie corneal, "
                "lo que puede explicar la limitacion de la agudeza visual pese a la correccion"
            )
        partes.append(detalle)
    return "; ".join(partes) + "."


def _es_eje_oblicuo(eje: int) -> bool:
    return (20 <= eje <= 70) or (110 <= eje <= 160)


def _cond_astig_oblicuo(req: ImpresionClinicaRequest) -> bool:
    """Astigmatismo oblicuo se define por el cilindro de la Rx final prescrita.

    La queratometria (dato estatico corneal) solo se usa como CONFIRMACION de un
    hallazgo ya disparado por la Rx, nunca como via de disparo independiente: un
    cilindro corneal oblicuo sin correlato en la Rx final es competencia de
    `ar_detecta_astigmatismo_no_prescrito` (si el AR tambien lo detecta) o no
    amerita correlato (si ni el AR lo detecta), pero no es "astigmatismo oblicuo
    prescrito".
    """
    refraccion = req.refraccion
    if refraccion is None:
        return False
    for ojo in (refraccion.od, refraccion.oi):
        cil = ojo.cilindro
        eje = ojo.eje
        if cil is None or eje is None:
            continue
        if abs(cil) > 2.00 and _es_eje_oblicuo(eje):
            return True
    return False


def _texto_astig_oblicuo(req: ImpresionClinicaRequest) -> str:
    partes = []
    for label, side in [("OD", "od"), ("OI", "oi")]:
        ojo = getattr(req.refraccion, side)
        cil = ojo.cilindro
        eje = ojo.eje
        if cil is None or eje is None or abs(cil) <= 2.00 or not _es_eje_oblicuo(eje):
            continue
        mag = abs(cil)
        if mag <= 3.00:
            descripcion = "astigmatismo elevado con eje oblicuo"
        elif mag <= 4.00:
            descripcion = "astigmatismo alto con eje oblicuo"
        else:
            descripcion = "astigmatismo de magnitud muy alta con eje oblicuo"
        akr_eye = _ojo_akr(req, side)
        if (
            _keratometry_supports_astigmatism(akr_eye, min_cyl=1.00)
            and _keratometry_axis_matches(akr_eye, eje)
        ):
            descripcion += " confirmado por queratometria"
        partes.append(f"{label} ({cil:+.2f} x {eje}): {descripcion}")
    return "; ".join(partes) + "."
