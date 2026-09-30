"""Dominio: refraccion final prescrita y recordatorio tecnico de vertice.

miopia_magna, hipermetropia_alta, anisometropia, astig_oblicuo, av_cc_limitada.
Se seleccionan por datos registrados de Rx (esfera/cilindro/eje/AV).
La queratometria solo aporta mediciones independientes o coincidencia angular;
no determina mecanismo refractivo ni causa de la AV registrada.
"""
from __future__ import annotations

from app.correlaciones.base import _memoize_cond
from app.correlaciones.queratometria import (
    _corneal_cyl_abs,
    _contexto_mediciones,
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
    _av_denominator,
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
        if (ee is not None and ee <= -6.00) or (ojo.esfera is not None and ojo.esfera <= -6.00 and ojo.cilindro is None):
            return True
    return False


def _texto_miopia_magna(req: ImpresionClinicaRequest) -> str:
    ojos = []
    for label, ojo in [("OD", req.refraccion.od), ("OI", req.refraccion.oi)]:
        ee = _equivalente_esferico(ojo.esfera, ojo.cilindro)
        if ee is not None and ee <= -6.00:
            ojos.append(f"{label} (EE {ee:+.2f}D)")
        elif ojo.esfera is not None and ojo.esfera <= -6.00 and ojo.cilindro is None:
            ojos.append(f"{label} (esfera {ojo.esfera:+.2f}D; cilindro no registrado, EE exacto no calculable)")
    texto = (
        f"La refraccion final registrada presenta {' y '.join(ojos)}, dentro del rango refractivo "
        "de miopia alta. Este dato amerita valoracion de retina central y periferica y seguimiento "
        "segun los hallazgos y los controles ya documentados. La graduacion no determina por si sola "
        "lesiones, mecanismo axial ni progresion."
    )
    return texto + _contexto_mediciones(req)


# Seleccion operativa por magnitud de la Rx; no es un clasificador angular.
_HIPERMETROPIA_EE_MIN = 5.00


def _es_hipermetropia_alta(ojo) -> bool:
    ee = _equivalente_esferico(ojo.esfera, ojo.cilindro)
    return ee is not None and ee >= _HIPERMETROPIA_EE_MIN


def _cond_hipermetropia_alta(req: ImpresionClinicaRequest) -> bool:
    if req.refraccion is None:
        return False
    return any(_es_hipermetropia_alta(ojo) for ojo in (req.refraccion.od, req.refraccion.oi))


def _texto_hipermetropia_alta(req: ImpresionClinicaRequest) -> str:
    ojos = [(label, _equivalente_esferico(ojo.esfera, ojo.cilindro))
            for label, ojo in (("OD", req.refraccion.od), ("OI", req.refraccion.oi))
            if _es_hipermetropia_alta(ojo)]
    texto = (
        f"La refraccion final registrada presenta {_format_eyes_with_values(ojos, 'EE')}, "
        "de magnitud hipermetropica elevada. Conviene completar la valoracion ocular y ajustar "
        "el seguimiento a la agudeza visual, alineacion y examen del segmento anterior. "
        "Valorar la camara anterior y el angulo segun antecedentes y exploraciones documentadas; "
        "la graduacion no demuestra estrechez angular ni esfuerzo acomodativo residual."
    )
    edad = req.paciente.edad if req.paciente else None
    if edad is not None and edad < 18:
        texto += " En edad pediatrica, revisar el desarrollo visual y la alineacion con la correccion indicada."
    return texto + _contexto_mediciones(req)



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
    texto = (
        f"Las refracciones finales registradas difieren {diff:.2f}D en equivalente esferico "
        f"entre OD ({ee_od:+.2f}D) y OI ({ee_oi:+.2f}D). Conviene valorar la agudeza visual "
        "de cada ojo y la tolerancia binocular con la correccion indicada."
    )
    if ee_od * ee_oi < 0:
        texto += " Los equivalentes esfericos registrados tienen signos opuestos (antimetropia)."
    edad = req.paciente.edad if req.paciente is not None else None
    if edad is not None and edad < 18:
        texto += (
            " En edad pediatrica, revisar el desarrollo visual y valorar evaluacion especializada "
            "segun agudeza visual y alineacion; la diferencia aislada no diagnostica ambliopia."
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
            texto += f" La queratometria agrega diferencia de cilindro corneal de {abs(_corneal_cyl_abs(od_akr) - _corneal_cyl_abs(oi_akr)):.2f}D (OD {_corneal_cyl_abs(od_akr):.2f}D; OI {_corneal_cyl_abs(oi_akr):.2f}D)."
    return texto + _contexto_mediciones(req)


def _cond_av_cc_limitada(req: ImpresionClinicaRequest) -> bool:
    refraccion = req.refraccion
    if refraccion is None:
        return False
    return _av_es_limitada(refraccion.od.av_cc) or _av_es_limitada(refraccion.oi.av_cc)


def _texto_av_cc_limitada(req: ImpresionClinicaRequest) -> str:
    partes = []
    for label, ojo in [("OD", req.refraccion.od), ("OI", req.refraccion.oi)]:
        av = ojo.av_cc
        if not _av_es_limitada(av):
            continue
        detalle = f"{label}: AV con correccion registrada de {av}"
        av_sc = _av_denominator(ojo.av_sc)
        av_cc = _av_denominator(av)
        if av_sc is not None and av_cc is not None and av_sc < av_cc:
            detalle += (
                f"; la AV sin correccion registrada ({ojo.av_sc}) es mejor: "
                "revisar esta inconsistencia antes de interpretar la diferencia"
            )
        partes.append(detalle)
    texto = "; ".join(partes) + (
        ". Verificar medicion y correccion utilizada; el registro no acredita mejor AV corregida. "
        "Si persiste reducida sin explicacion documentada, requiere evaluacion oftalmologica; "
        "ajustar el seguimiento a las causas y controles ya consignados."
    )
    edad = req.paciente.edad if req.paciente else None
    if edad is not None and edad < 18:
        texto += (
            " En edad pediatrica, interpretar la cifra con pruebas adecuadas a la edad "
            "y al desarrollo visual; esta seleccion numerica no diagnostica enfermedad."
        )
    elif edad is None:
        texto += " La edad no esta registrada; limitar la interpretacion hasta completar ese contexto."
    return texto + _contexto_mediciones(req)


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
        descripcion = f"{label}: la prescripcion registra cilindro de {cil:+.2f}D a {eje % 180} grados, con orientacion oblicua"
        akr_eye = _ojo_akr(req, side)
        if (
            _keratometry_supports_astigmatism(akr_eye, min_cyl=1.00)
            and _keratometry_axis_matches(akr_eye, eje)
        ):
            descripcion += "; la orientacion queratometrica es aproximadamente coincidente, sin establecer igual magnitud ni origen exclusivo"
        partes.append(descripcion)
    texto = "; ".join(partes) + "."
    edad = req.paciente.edad if req.paciente else None
    if edad is not None and edad < 18:
        texto += " Comprobar agudeza visual monocular y desarrollo visual con la correccion indicada."
    return texto + _contexto_mediciones(req)


def _vertice_parts(req: ImpresionClinicaRequest) -> list[str]:
    if req.refraccion is None:
        return []
    parts = []
    for label, eye in [("OD", req.refraccion.od), ("OI", req.refraccion.oi)]:
        if eye is None or eye.esfera is None:
            continue
        meridianos = [("S", eye.esfera)]
        if eye.cilindro is not None:
            meridianos.append(("S+C", eye.esfera + eye.cilindro))
        valores = [f"{nombre} {potencia:+.2f}D" for nombre, potencia in meridianos if abs(potencia) >= 4.00]
        if valores:
            parts.append(f"{label} ({'; '.join(valores)})")
    return parts


@_memoize_cond
def _cond_distancia_vertice_alta_ametropia(req: ImpresionClinicaRequest) -> bool:
    """Recordatorio optico operativo; no es una correlacion medica."""
    return bool(_vertice_parts(req))


def _texto_distancia_vertice_alta_ametropia(req: ImpresionClinicaRequest) -> str:
    ojos = ", ".join(_vertice_parts(req))
    return (
        f"Recordatorio tecnico: la potencia registrada en {ojos} aconseja comprobar la distancia "
        "al vertice al adaptar la correccion y valorar compensacion si cambia el plano de uso. "
        "Se requieren las distancias de origen y destino de esta prescripcion; la VD del AKR "
        "no las sustituye. Considerar las verificaciones de adaptacion ya documentadas."
    ) + _contexto_mediciones(req)
