"""Dominio: binocularidad y convergencia (7 correlaciones).

insuficiencia_convergencia (compuesta), ppc_exoforia, cover_exoforia_sintomatica,
cover_endoforia_sintomatica, desviacion_vertical, endotropia_lente, exotropia_lente.
Jerarquia: insuficiencia_convergencia suprime ppc_exoforia y
cover_exoforia_sintomatica para evitar redundancia.
"""
from __future__ import annotations

from app.correlaciones.base import _memoize_cond
from app.correlaciones.texto import _contains_keyword, _normalize_cover_text
from app.schemas import ImpresionClinicaRequest

_KEYWORDS_BINOCULAR = (
    "diplopia", "vision doble",
    "cefalea", "dolor de cabeza",
    "astenopia", "fatiga visual", "vista cansada",
    "ardor con lectura", "lagrimeo con lectura",
    "perdida del renglon", "salto de letras",
    "vision borrosa intermitente",
)
_KEYWORDS_CERCANIA = (
    "lectura", "leer", "estudiar", "cerca", "astenopia", "fatiga", "cefalea",
)
_KEYWORDS_DESVIACION_VERTICAL = ("hiperforia", "hipoforia", "hipertropia", "hipotropia")


def _has_binocular_symptoms(req: ImpresionClinicaRequest) -> bool:
    paciente = req.paciente
    motivo = paciente.motivo_consulta if paciente is not None else None
    return _contains_keyword(motivo, _KEYWORDS_BINOCULAR)


@_memoize_cond
def _cond_insuficiencia_convergencia(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: PPC alejado, exoforia y sintomas de lectura activan insuficiencia de convergencia."""
    if req.clinica is None or req.paciente is None:
        return False
    if req.clinica.ppc_cm is None or req.clinica.ppc_cm <= 10:
        return False
    cover = _normalize_cover_text(req.clinica.cover_test)
    if "exoforia" not in cover:
        return False
    return _contains_keyword(req.paciente.motivo_consulta, _KEYWORDS_CERCANIA)


_texto_insuficiencia_convergencia = (
    "La combinacion de punto proximo de convergencia alejado, exoforia y sintomatologia de "
    "vision proxima es compatible con insuficiencia de convergencia, ameritando evaluacion "
    "binocular completa para confirmar el diagnostico y plantear terapia visual si procede."
)


def _cond_ppc_exoforia(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    if _cond_insuficiencia_convergencia(req):
        return False
    ppc_alto = clinica.ppc_cm is not None and clinica.ppc_cm > 10
    cover = _normalize_cover_text(clinica.cover_test)
    return ppc_alto or ("exoforia" in cover)


def _texto_ppc_exoforia(req: ImpresionClinicaRequest) -> str:
    partes = []
    clinica = req.clinica
    ppc = clinica.ppc_cm if clinica is not None else None
    cover = _normalize_cover_text(clinica.cover_test if clinica is not None else None)
    if ppc is not None and ppc > 10:
        partes.append(f"punto proximo de convergencia alejado ({ppc} cm)")
    if "exoforia" in cover:
        if any(token in cover for token in ("vp", "cerca", "proxima")):
            partes.append("exoforia en vision proxima")
        elif any(token in cover for token in ("vl", "lejos")):
            partes.append("exoforia en vision lejana")
        else:
            partes.append("tendencia divergente en el cover test")
    return "El paciente presenta " + " y ".join(partes) + "."


def _cond_cover_exoforia_sintomatica(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: exoforia en cover test con cefalea o diplopia sugiere disfuncion divergente."""
    if req.clinica is None or req.paciente is None:
        return False
    if _cond_insuficiencia_convergencia(req):
        return False
    cover = _normalize_cover_text(req.clinica.cover_test)
    return "exoforia" in cover and _has_binocular_symptoms(req)


_texto_cover_exoforia_sintomatica = (
    "Se documenta exoforia con sintomatologia binocular asociada, compatible con "
    "disfuncion binocular de tipo divergente que amerita evaluacion funcional."
)


def _cond_cover_endoforia_sintomatica(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: endoforia sintomatica sin endotropia sugiere exceso de convergencia."""
    if req.clinica is None or req.paciente is None:
        return False
    cover = _normalize_cover_text(req.clinica.cover_test)
    return "endoforia" in cover and "endotropia" not in cover and _has_binocular_symptoms(req)


_texto_cover_endoforia_sintomatica = (
    "Se documenta endoforia con sintomatologia binocular asociada, compatible con "
    "exceso de convergencia o disfuncion acomodativa que amerita evaluacion funcional."
)


def _cond_desviacion_vertical(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: hiperforia, hipoforia o tropias verticales ameritan cuantificacion."""
    clinica = req.clinica
    if clinica is None:
        return False
    cover = _normalize_cover_text(clinica.cover_test)
    return any(keyword in cover for keyword in _KEYWORDS_DESVIACION_VERTICAL)


def _texto_desviacion_vertical(req: ImpresionClinicaRequest) -> str:
    cover = _normalize_cover_text(req.clinica.cover_test if req.clinica is not None else None)
    forias = [k for k in _KEYWORDS_DESVIACION_VERTICAL if k in cover and "foria" in k]
    tropias = [k for k in _KEYWORDS_DESVIACION_VERTICAL if k in cover and "tropia" in k]
    partes = []
    if forias:
        partes.append(", ".join(forias))
    if tropias:
        partes.append(", ".join(tropias))
    texto_hallazgo = " y ".join(partes) if partes else "desviacion vertical"
    if tropias:
        cierre = (
            "que representa una desviacion manifiesta y amerita cuantificacion "
            "prismatica inmediata con evaluacion binocular completa."
        )
    else:
        cierre = (
            "que puede generar sintomatologia binocular especifica y amerita "
            "cuantificacion prismatica para evaluar compensacion."
        )
    return f"Se documenta {texto_hallazgo}, {cierre}"


def _cond_endotropia_lente(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    cover = _normalize_cover_text(clinica.cover_test)
    return "endotropia" in cover and req.tipo_lente is not None


_texto_endotropia_lente = (
    "Se documenta endotropia en el cover test, ameritando evaluacion de la respuesta "
    "a la correccion optica prescrita, con cover test bajo correccion para clasificar "
    "el tipo de desviacion."
)


def _cond_exotropia_lente(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: exotropia manifiesta con lente prescrito amerita estudio binocular."""
    clinica = req.clinica
    if clinica is None:
        return False
    cover = _normalize_cover_text(clinica.cover_test)
    return "exotropia" in cover and req.tipo_lente is not None


_texto_exotropia_lente = (
    "Se documenta exotropia en el cover test, ameritando evaluacion binocular completa "
    "para determinar frecuencia y magnitud de la desviacion, asi como la respuesta a "
    "la correccion optica prescrita."
)
