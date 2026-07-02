"""Dominio: edad, lente y uso de pantallas (3 correlaciones).

presbicia_multifocal, cvs_sospecha y adulto_mayor_screening. Este ultimo es una
red de seguridad: solo dispara si no hay ya una causa especifica documentada que
explique la reduccion visual del adulto mayor (de ahi los imports de otros dominios).
"""
from __future__ import annotations

from app.correlaciones.anexos_cristalino import _cond_opacidad_cristaliniana
from app.correlaciones.fondo_de_ojo import (
    _cond_fondo_glaucomatoso,
    _cond_fondo_hipertensivo,
    _cond_fondo_macular_dmae,
    _cond_fondo_macular_otros,
    _cond_fondo_vascular_diabetico,
    _cond_papila_patologica,
)
from app.correlaciones.queratometria import _req_has_corneal_irregularity
from app.correlaciones.refraccion_utils import _av_es_limitada
from app.correlaciones.refractivas import _cond_miopia_magna
from app.correlaciones.texto import _contains_keyword, _normalize_text
from app.schemas import ImpresionClinicaRequest

_KEYWORDS_CVS = (
    "ardor ocular", "sequedad ocular",
    "vision borrosa intermitente", "vision borrosa", "dolor ocular",
    "ardor", "sequedad", "cefalea", "picazon", "prurito", "lagrimeo",
)
_MULTIFOCAL_TOKENS = ("bifocal", "progresivo", "multifocal")


def _es_lente_multifocal(req: ImpresionClinicaRequest) -> bool:
    tipo = _normalize_text(req.tipo_lente)
    return any(token in tipo for token in _MULTIFOCAL_TOKENS)


def _cond_presbicia_multifocal(req: ImpresionClinicaRequest) -> bool:
    paciente = req.paciente
    refraccion = req.refraccion
    if paciente is None or refraccion is None:
        return False
    es_multifocal = _es_lente_multifocal(req)
    edad = paciente.edad
    hay_edad = edad is not None and edad >= 40
    hay_add = refraccion.od.add is not None or refraccion.oi.add is not None
    return (es_multifocal and (hay_edad or hay_add)) or (hay_edad and hay_add)


def _texto_presbicia_multifocal(req: ImpresionClinicaRequest) -> str:
    edad = req.paciente.edad if req.paciente is not None else None
    sufijo_lente = " y el lente multifocal indicado" if _es_lente_multifocal(req) else ""
    if edad is not None:
        return (
            f"El paciente de {edad} anos presenta reduccion fisiologica de la amplitud "
            f"acomodativa propia de la edad, lo que justifica la adicion prescrita{sufijo_lente}."
        )
    return (
        "Se documenta reduccion fisiologica de la amplitud acomodativa, lo que justifica "
        f"la adicion prescrita{sufijo_lente}."
    )


def _cond_cvs_sospecha(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: pantallas y ardor o cefalea sugieren sindrome visual informatico."""
    if req.clinica is None or req.paciente is None:
        return False
    if req.clinica.uso_pantallas not in ("btw2_6", "gt6"):
        return False
    return _contains_keyword(req.paciente.motivo_consulta, _KEYWORDS_CVS)


_texto_cvs_sospecha = (
    "El perfil de uso de pantallas se correlaciona con la sintomatologia visual "
    "referida, compatible con sindrome visual informatico, ameritando recomendaciones "
    "ergonomicas y eventual correccion optica para vision intermedia."
)


def _cond_adulto_mayor_screening(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: adulto mayor con AV corregida reducida amerita descarte dirigido."""
    if req.paciente is None or req.refraccion is None:
        return False
    edad = req.paciente.edad
    if edad is None or edad < 60:
        return False
    if not (_av_es_limitada(req.refraccion.od.av_cc) or _av_es_limitada(req.refraccion.oi.av_cc)):
        return False
    return not any(
        cond(req) for cond in (
            _cond_opacidad_cristaliniana,
            _cond_fondo_glaucomatoso,
            _cond_fondo_macular_dmae,
            _cond_fondo_macular_otros,
            _cond_fondo_vascular_diabetico,
            _cond_fondo_hipertensivo,
            _cond_miopia_magna,
            _cond_papila_patologica,
            _req_has_corneal_irregularity,
        )
    )


def _texto_adulto_mayor_screening(req: ImpresionClinicaRequest) -> str:
    edad = req.paciente.edad
    return (
        f"En paciente de {edad} anos con reduccion de agudeza visual sin causa "
        "identificada en el examen actual, se recomienda descarte activo de catarata, "
        "glaucoma y maculopatia asociada a la edad mediante exploracion dirigida."
    )
