"""Dominio: autorrefractometro/queratometria vs refraccion final (4 correlaciones).

ar_rx_espasmo_acomodativo, ar_rx_cambio_cristalino, ar_rx_variabilidad_inespecifica,
ar_detecta_astigmatismo_no_prescrito. Solo aplican cuando existen valores en AR y
Rx del mismo ojo; jerarquia: primero el patron especifico (espasmo, cristalino),
la variabilidad inespecifica actua como red de seguridad.
"""
from __future__ import annotations

from app.correlaciones.base import _memoize_cond
from app.correlaciones.queratometria import (
    _corneal_cyl_abs,
    _format_corneal_irregularity,
    _has_keratometry,
    _keratometry_supports_astigmatism,
    _req_has_corneal_irregularity,
)
from app.correlaciones.texto import _join_hallazgos, _keyword_matches, _normalize_text
from app.schemas import ImpresionClinicaRequest

# La red de seguridad de variabilidad inespecifica exige una discrepancia AR-Rx
# amplia (>= 1.50 D). Los autorrefractometros sobre-miopizan de forma rutinaria
# ~0.50-1.00 D respecto a la refraccion subjetiva; disparar por debajo de 1.50 D
# convertiria un comportamiento normal del instrumento en un "hallazgo" y anadiria
# ruido a casi todos los casos con AKR. Los patrones etarios especificos (espasmo,
# cambio cristalino) mantienen sus propios umbrales mas sensibles.
_UMBRAL_VARIABILIDAD_D = 1.50


@_memoize_cond
def _cond_ar_rx_espasmo_acomodativo(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: joven con pantallas y AR mas miope que Rx sugiere espasmo acomodativo."""
    if req.refraccion is None or req.akr is None or req.paciente is None or req.clinica is None:
        return False
    edad = req.paciente.edad
    if edad is None or edad >= 40:
        return False
    if req.clinica.uso_pantallas not in ("btw2_6", "gt6"):
        return False
    for ojo in ("od", "oi"):
        esf_ar = getattr(req.akr, ojo).esfera
        esf_rx = getattr(req.refraccion, ojo).esfera
        if esf_ar is None or esf_rx is None:
            continue
        if (esf_rx - esf_ar) >= 0.75:
            return True
    return False


_texto_ar_rx_espasmo_acomodativo = (
    "El autorrefractometro documenta mayor componente miopico que la refraccion subjetiva "
    "final en un paciente joven con uso intensivo de pantallas, patron compatible con "
    "espasmo acomodativo que amerita control posterior y eventual refraccion bajo cicloplejia."
)


@_memoize_cond
def _cond_ar_rx_cambio_cristalino(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: mayor de 55 anos con discrepancia esferica amplia entre AR y Rx."""
    if req.refraccion is None or req.akr is None or req.paciente is None:
        return False
    edad = req.paciente.edad
    if edad is None or edad < 55:
        return False
    if _req_has_corneal_irregularity(req):
        return False
    textos = []
    if req.paciente is not None and req.paciente.motivo_consulta:
        textos.append(req.paciente.motivo_consulta)
    if req.clinica is not None:
        if req.clinica.anexos_oculares:
            textos.append(req.clinica.anexos_oculares)
        if req.clinica.fondo_de_ojo:
            textos.append(req.clinica.fondo_de_ojo)
    if textos:
        texto_norm = _normalize_text(" ".join(textos))
        pseudofaquico_tokens = ("pseudofaquia", "pseudofaco", "pseudofaquico", "lente intraocular", "lio", "iol", "afaquia", "afaquico")
        if any(_keyword_matches(texto_norm, t, allow_negation_window=True) for t in pseudofaquico_tokens):
            return False
    for ojo in ("od", "oi"):
        esf_ar = getattr(req.akr, ojo).esfera
        esf_rx = getattr(req.refraccion, ojo).esfera
        if esf_ar is None or esf_rx is None:
            continue
        if abs(esf_ar - esf_rx) > 1.00:
            return True
    return False


_texto_ar_rx_cambio_cristalino = (
    "Se documenta discrepancia entre autorrefractometro y refraccion final en un "
    "paciente mayor de 55 anos, sin patron queratometrico que explique primariamente "
    "la diferencia refractiva, lo que puede reflejar cambios en el indice refractivo "
    "del cristalino y amerita evaluacion biomicroscopica del segmento anterior."
)


def _cond_ar_rx_variabilidad_inespecifica(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: discrepancia AR-Rx sin patron etario especifico sugiere variabilidad."""
    if req.refraccion is None or req.akr is None:
        return False
    if _cond_ar_rx_espasmo_acomodativo(req) or _cond_ar_rx_cambio_cristalino(req):
        return False
    for ojo in ("od", "oi"):
        esf_ar = getattr(req.akr, ojo).esfera
        esf_rx = getattr(req.refraccion, ojo).esfera
        cil_ar = getattr(req.akr, ojo).cilindro
        cil_rx = getattr(req.refraccion, ojo).cilindro
        if esf_ar is not None and esf_rx is not None and abs(esf_ar - esf_rx) >= _UMBRAL_VARIABILIDAD_D:
            return True
        if cil_ar is not None and cil_rx is not None and abs(cil_ar - cil_rx) >= _UMBRAL_VARIABILIDAD_D:
            return True
    return False


def _texto_ar_rx_variabilidad_inespecifica(req: ImpresionClinicaRequest) -> str:
    cornea = _format_corneal_irregularity(req)
    if cornea:
        return (
            "Se documenta discrepancia entre autorrefractometro y refraccion final, "
            "compatible con variabilidad refractiva durante la exploracion, "
            f"con queratometria de curvatura corneal pronunciada en {cornea}."
        )
    return (
        "Se documenta discrepancia entre autorrefractometro y refraccion final, "
        "compatible con variabilidad refractiva durante la exploracion."
    )


def _cond_ar_detecta_astigmatismo_no_prescrito(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: AR detecta cilindro relevante y la Rx final no lo prescribe."""
    if req.refraccion is None or req.akr is None:
        return False
    for ojo in ("od", "oi"):
        akr_eye = getattr(req.akr, ojo)
        cil_ar = akr_eye.cilindro
        cil_rx = getattr(req.refraccion, ojo).cilindro
        if cil_ar is None or abs(cil_ar) < 0.75:
            continue
        if _has_keratometry(akr_eye) and not _keratometry_supports_astigmatism(akr_eye):
            continue
        if cil_rx is None or abs(cil_rx) < 0.50:
            return True
    return False


def _texto_ar_detecta_astigmatismo_no_prescrito(req: ImpresionClinicaRequest) -> str:
    partes = []
    for label, side in [("OD", "od"), ("OI", "oi")]:
        akr_eye = getattr(req.akr, side)
        rx_eye = getattr(req.refraccion, side)
        cil_ar = akr_eye.cilindro
        if cil_ar is None or abs(cil_ar) < 0.75:
            continue
        if rx_eye.cilindro is not None and abs(rx_eye.cilindro) >= 0.50:
            continue
        if _has_keratometry(akr_eye) and _keratometry_supports_astigmatism(akr_eye):
            partes.append(
                f"{label} (AKR {cil_ar:+.2f}D; cilindro corneal {_corneal_cyl_abs(akr_eye):.2f}D)"
            )
        elif not _has_keratometry(akr_eye):
            partes.append(f"{label} (AKR {cil_ar:+.2f}D)")
    sufijo = (
        " lo que puede corresponder a astigmatismo subumbral con tolerancia clinica "
        "adecuada o variabilidad de la medicion automatizada."
    )
    if partes:
        return (
            "El autorrefractometro detecta astigmatismo no incluido en la refraccion "
            f"subjetiva final en {_join_hallazgos(partes)},{sufijo}"
        )
    return (
        "El autorrefractometro detecta un componente astigmatico que no fue incluido "
        f"en la refraccion subjetiva final,{sufijo}"
    )
