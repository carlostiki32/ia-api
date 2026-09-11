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
    _k_promedio,
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
        texto += f" La queratometria muestra curvatura corneal plana en {plana}, sugestivo de un componente corneal (y no exclusivamente axial) de la hipermetropia."
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
        od_k = _k_promedio(od_akr)
        oi_k = _k_promedio(oi_akr)
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
                ", con queratometria que orienta a irregularidad de la superficie corneal, "
                "lo que puede explicar la limitacion de la agudeza visual pese a la correccion"
            )
        partes.append(detalle)
    return "; ".join(partes) + "."


def _es_eje_oblicuo(eje: int) -> bool:
    eje_norm = eje % 180 or 180
    return (20 < eje_norm < 70) or (110 < eje_norm < 160)


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


def _asimetria_k_interocular(req: ImpresionClinicaRequest) -> float | None:
    od_akr = _ojo_akr(req, "od")
    oi_akr = _ojo_akr(req, "oi")
    if od_akr is None or oi_akr is None:
        return None
    od_k = _k_promedio(od_akr)
    oi_k = _k_promedio(oi_akr)
    if od_k is None or oi_k is None:
        return None
    return abs(od_k - oi_k)


@_memoize_cond
def _cond_aniseiconia_queratometrica_severa(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: anisometropia con asimetria queratometrica interocular significativa (>= 1.50 D),
    concordante en direccion con la ley de Knapp (la cornea mas curva se encuentra en el ojo
    con equivalente esferico mas miope / menos hipermetrope)."""
    if not _cond_anisometropia(req):
        return False
    if req.refraccion is None:
        return False
    od_rx = req.refraccion.od
    oi_rx = req.refraccion.oi
    ee_od = _equivalente_esferico(od_rx.esfera, od_rx.cilindro)
    ee_oi = _equivalente_esferico(oi_rx.esfera, oi_rx.cilindro)
    if ee_od is None or ee_oi is None:
        return False
    od_akr = _ojo_akr(req, "od")
    oi_akr = _ojo_akr(req, "oi")
    if od_akr is None or oi_akr is None:
        return False
    od_k = _k_promedio(od_akr)
    oi_k = _k_promedio(oi_akr)
    if od_k is None or oi_k is None:
        return False
    diff = abs(od_k - oi_k)
    if diff < 1.50:
        return False
    # Ley de Knapp: para que la anisometropia tenga un componente corneal / refractivo
    # que justifique la adaptacion de lentes de contacto para reducir aniseiconia,
    # la cornea de mayor poder refractivo (K mas alto) debe corresponder al ojo mas miope
    # (o menos hipermetrope). Si la cornea mas plana esta en el ojo mas miope,
    # la diferencia refractiva es preponderantemente axial en direccion contraria.
    delta_ee = ee_od - ee_oi
    delta_k = od_k - oi_k
    return (delta_ee * delta_k) < 0


def _texto_aniseiconia_queratometrica_severa(req: ImpresionClinicaRequest) -> str:
    diff = _asimetria_k_interocular(req)
    val = f"{diff:.2f}D" if diff is not None else "relevante"
    return (
        f"La asimetria queratometrica interocular significativa ({val}) sugiere que la "
        "anisometropia posee un fuerte componente corneal, lo que predispone a aniseiconia "
        "sintomatica con lentes aereos; se sugiere considerar la adaptacion de lentes de contacto "
        "para optimizar la fusion binocular."
    )


def _vertice_parts(req: ImpresionClinicaRequest) -> list[str]:
    if req.refraccion is None:
        return []
    parts = []
    for label, eye in [("OD", req.refraccion.od), ("OI", req.refraccion.oi)]:
        if eye is not None and eye.esfera is not None and abs(eye.esfera) >= 4.00:
            parts.append(f"{label} ({eye.esfera:+.2f}D)")
    return parts


@_memoize_cond
def _cond_distancia_vertice_alta_ametropia(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: ametropia esferica >= 4.00 D hace que la distancia al vertice sea clinicamente relevante."""
    return bool(_vertice_parts(req))


def _texto_distancia_vertice_alta_ametropia(req: ImpresionClinicaRequest) -> str:
    partes = _vertice_parts(req)
    ojos = ", ".join(partes) if partes else "la refraccion prescrita"
    return (
        f"La magnitud de la ametropia en {ojos} (|esfera| >= 4.00D) hace que la distancia al vertice "
        "tenga impacto optico clinicamente significativo; se recomienda registrar la distancia al vertice "
        "de examen para la elaboracion del lente aereo o calcular la potencia efectiva compensada en caso "
        "de adaptacion de lentes de contacto."
    )


@_memoize_cond
def _cond_antimetropia_pura_acomodativa(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: un ojo miopico (EE <= -0.75 D) y contralateral hipermetropico (EE >= +0.75 D)."""
    if req.refraccion is None:
        return False
    od = req.refraccion.od
    oi = req.refraccion.oi
    od_ee = _equivalente_esferico(od.esfera, od.cilindro)
    oi_ee = _equivalente_esferico(oi.esfera, oi.cilindro)
    if od_ee is None or oi_ee is None:
        return False
    return (od_ee <= -0.75 and oi_ee >= 0.75) or (oi_ee <= -0.75 and od_ee >= 0.75)


def _texto_antimetropia_pura_acomodativa(req: ImpresionClinicaRequest) -> str:
    od = req.refraccion.od
    oi = req.refraccion.oi
    od_ee = _equivalente_esferico(od.esfera, od.cilindro)
    oi_ee = _equivalente_esferico(oi.esfera, oi.cilindro)
    od_str = f"OD ({od_ee:+.2f}D)" if od_ee is not None else "OD"
    oi_str = f"OI ({oi_ee:+.2f}D)" if oi_ee is not None else "OI"
    return (
        f"Se documenta antimetropia ({od_str} vs {oi_str}), condicion con un ojo miope y el contralateral "
        "hipermetrope que induce demandas acomodativas asimetricas y anisoforia con lentes aereos; se recomienda "
        "vigilar el balance binocular y considerar lentes de contacto para facilitar la fusion."
    )


def _astig_contra_regla_parts(req: ImpresionClinicaRequest) -> list[str]:
    if req.refraccion is None or req.paciente is None or req.paciente.edad is None:
        return []
    if req.paciente.edad >= 40:
        return []
    parts = []
    for label, eye in [("OD", req.refraccion.od), ("OI", req.refraccion.oi)]:
        if eye is not None and eye.cilindro is not None and eye.eje is not None:
            if eye.cilindro <= -1.00 and (70 <= eye.eje <= 110):
                parts.append(f"{label} ({eye.cilindro:+.2f} x {eye.eje})")
    return parts


@_memoize_cond
def _cond_astigmatismo_contra_regla_joven(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: astigmatismo contra la regla (cilindro <= -1.00 D, eje 70-110) en menor de 40 anos."""
    return bool(_astig_contra_regla_parts(req))


def _texto_astigmatismo_contra_regla_joven(req: ImpresionClinicaRequest) -> str:
    partes = _astig_contra_regla_parts(req)
    ojos = ", ".join(partes) if partes else "la refraccion"
    return (
        f"Se documenta astigmatismo contra la regla en paciente joven en {ojos}, orientacion no habitual "
        "para el grupo etario que amerita valoracion del segmento anterior y topografia corneal para descartar "
        "irregularidad corneal o ectasia incipiente."
    )


