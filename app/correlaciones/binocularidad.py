"""Dominio: binocularidad y convergencia (7 correlaciones).

insuficiencia_convergencia (compuesta), ppc_exoforia, cover_exoforia_sintomatica,
cover_endoforia_sintomatica, desviacion_vertical, endotropia_lente, exotropia_lente.
Jerarquia: insuficiencia_convergencia suprime ppc_exoforia y
cover_exoforia_sintomatica para evitar redundancia.
"""
from __future__ import annotations

from app.correlaciones.base import _memoize_cond
from app.correlaciones.texto import (
    _contains_keyword,
    _cover_desviaciones,
    _normalize_cover_text,
)
from app.schemas import ImpresionClinicaRequest

_KEYWORDS_BINOCULAR = (
    "diplopia", "vision doble", "veo doble", "imagenes dobles",
    "cefalea", "dolor de cabeza",
    "astenopia", "fatiga visual", "fatiga ocular", "vista cansada",
    "cansancio visual", "cansancio ocular", "ojos cansados",
    "ardor con lectura", "lagrimeo con lectura",
    "perdida del renglon", "salto de renglon", "pierde el renglon",
    "salto de letras", "se juntan las letras", "letras que bailan",
    "letras se mueven", "dificultad para enfocar",
    "mareo al leer", "mareo con lectura", "sueno al leer",
    "vision borrosa intermitente",
)
_KEYWORDS_CERCANIA = (
    "lectura", "leer", "estudiar", "estudio", "cerca", "vision proxima",
    "vision cercana", "trabajo de cerca", "computadora", "pantalla", "celular",
    "escribir", "astenopia", "fatiga", "cefalea",
)
# La demanda de vision proxima tambien puede inferirse de la ocupacion (no solo del
# motivo de consulta): un trabajo intensivo de cerca es contexto valido para la
# insuficiencia de convergencia.
_KEYWORDS_OCUPACION_PROXIMA = (
    "estudiante", "oficina", "oficinista", "programador", "desarrollador",
    "contador", "contabilidad", "capturista", "digitador", "secretaria",
    "disenador", "editor", "escritor", "costura", "costurera", "sastre",
    "relojero", "dentista", "cajera", "cajero", "computadora", "lectura",
)
_KEYWORDS_DESVIACION_VERTICAL = ("hiperforia", "hipoforia", "hipertropia", "hipotropia")

# Punto proximo de convergencia (PPC): el corte de "alejado" depende de la edad.
# La evidencia (criterios CITT) fija el punto de ruptura anormal en >6 cm para el
# pre-presbita; en el presbita el PPC se aleja fisiologicamente y el corte sube a
# >10 cm. Sin edad se usa el corte conservador (>10) para no sobre-disparar en un
# posible presbita no declarado.
_PPC_UMBRAL_JOVEN_CM = 6
_PPC_UMBRAL_PRESBITA_CM = 10


def _ppc_umbral(req: ImpresionClinicaRequest) -> int:
    paciente = req.paciente
    edad = paciente.edad if paciente is not None else None
    if edad is not None and edad < 40:
        return _PPC_UMBRAL_JOVEN_CM
    return _PPC_UMBRAL_PRESBITA_CM


def _ppc_alejado(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None or clinica.ppc_cm is None:
        return False
    return clinica.ppc_cm > _ppc_umbral(req)


def _cover_tokens(req: ImpresionClinicaRequest) -> frozenset[str]:
    """Tokens estructurados del cover test canonico del SaaS. Incluye los tipos
    sin clasificar ('exo', 'endo', 'hiper', 'hipo') que las keywords unidas no
    ven, porque la UI permite elegir Tipo sin elegir Tropia/Foria."""
    clinica = req.clinica
    return _cover_desviaciones(clinica.cover_test if clinica is not None else None)


def _has_binocular_symptoms(req: ImpresionClinicaRequest) -> bool:
    paciente = req.paciente
    motivo = paciente.motivo_consulta if paciente is not None else None
    return _contains_keyword(motivo, _KEYWORDS_BINOCULAR, allow_negation_window=True)


def _hay_demanda_proxima(req: ImpresionClinicaRequest) -> bool:
    """Contexto de vision proxima: por sintoma en el motivo o por la ocupacion."""
    paciente = req.paciente
    if paciente is None:
        return False
    return _contains_keyword(paciente.motivo_consulta, _KEYWORDS_CERCANIA) or _contains_keyword(
        paciente.ocupacion, _KEYWORDS_OCUPACION_PROXIMA
    )


@_memoize_cond
def _cond_insuficiencia_convergencia(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: PPC alejado, exoforia y sintomas de lectura activan insuficiencia de convergencia."""
    if req.clinica is None or req.paciente is None:
        return False
    if not _ppc_alejado(req):
        return False
    cover = _normalize_cover_text(req.clinica.cover_test)
    if "exoforia" not in cover:
        return False
    return _hay_demanda_proxima(req)


_texto_insuficiencia_convergencia = (
    "La combinacion de punto proximo de convergencia alejado, exoforia y sintomatologia de "
    "vision proxima sugiere sospecha de insuficiencia de convergencia, ameritando evaluacion "
    "binocular completa para complementar la evaluacion funcional binocular y plantear terapia visual si procede."
)


def _cond_ppc_exoforia(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    if _cond_insuficiencia_convergencia(req):
        return False
    cover = _normalize_cover_text(clinica.cover_test)
    # "exo" suelto = el optometrista marco Exo sin clasificar Tropia/Foria:
    # sigue siendo una exodesviacion documentada que merece mencion.
    return _ppc_alejado(req) or ("exoforia" in cover) or ("exo" in _cover_tokens(req))


def _texto_ppc_exoforia(req: ImpresionClinicaRequest) -> str:
    partes = []
    clinica = req.clinica
    ppc = clinica.ppc_cm if clinica is not None else None
    cover = _normalize_cover_text(clinica.cover_test if clinica is not None else None)
    if _ppc_alejado(req):
        partes.append(f"punto proximo de convergencia alejado ({ppc} cm)")
    if "exoforia" in cover:
        if any(token in cover for token in ("vp", "cerca", "proxima")):
            partes.append("exoforia en vision proxima")
        elif any(token in cover for token in ("vl", "lejos")):
            partes.append("exoforia en vision lejana")
        else:
            partes.append("tendencia divergente en el cover test")
    elif "exo" in _cover_tokens(req):
        partes.append(
            "exodesviacion no clasificada en el cover test (conviene precisar foria o tropia)"
        )
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
    "Se documenta exoforia con sintomatologia binocular asociada, sugestiva de "
    "descompensacion forica que amerita evaluacion funcional."
)


def _cond_cover_endoforia_sintomatica(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: endoforia (o endodesviacion sin clasificar) sintomatica sin
    endotropia sugiere exceso de convergencia."""
    if req.clinica is None or req.paciente is None:
        return False
    cover = _normalize_cover_text(req.clinica.cover_test)
    hay_endo = "endoforia" in cover or "endo" in _cover_tokens(req)
    return hay_endo and "endotropia" not in cover and _has_binocular_symptoms(req)


def _texto_cover_endoforia_sintomatica(req: ImpresionClinicaRequest) -> str:
    cover = _normalize_cover_text(req.clinica.cover_test if req.clinica is not None else None)
    if "endoforia" in cover:
        hallazgo = "endoforia"
    else:
        hallazgo = "una endodesviacion no clasificada en el cover test"
    return (
        f"Se documenta {hallazgo} con sintomatologia binocular asociada, sugestiva de "
        "disfuncion de la vision binocular que amerita evaluacion funcional."
    )


def _cond_desviacion_vertical(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: hiperforia, hipoforia o tropias verticales ameritan cuantificacion.
    Un Hiper/Hipo sin clasificar (sin Tropia/Foria) tambien es desviacion vertical
    documentada y dispara con el texto generico."""
    clinica = req.clinica
    if clinica is None:
        return False
    cover = _normalize_cover_text(clinica.cover_test)
    if any(keyword in cover for keyword in _KEYWORDS_DESVIACION_VERTICAL):
        return True
    tokens = _cover_tokens(req)
    return "hiper" in tokens or "hipo" in tokens


def _texto_desviacion_vertical(req: ImpresionClinicaRequest) -> str:
    cover = _normalize_cover_text(req.clinica.cover_test if req.clinica is not None else None)
    forias = [k for k in _KEYWORDS_DESVIACION_VERTICAL if k in cover and "foria" in k]
    tropias = [k for k in _KEYWORDS_DESVIACION_VERTICAL if k in cover and "tropia" in k]
    partes = []
    if forias:
        partes.append(", ".join(forias))
    if tropias:
        partes.append(", ".join(tropias))
    texto_hallazgo = (
        " y ".join(partes)
        if partes
        else "una desviacion vertical no clasificada en el cover test"
    )
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
    return "endotropia" in cover


_texto_endotropia_lente = (
    "Se documenta endotropia en el cover test, ameritando evaluacion de la respuesta "
    "a la correccion optica prescrita, con cover test bajo correccion para clasificar "
    "el tipo de desviacion."
)


def _cond_exotropia_lente(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: exotropia manifiesta amerita estudio binocular."""
    clinica = req.clinica
    if clinica is None:
        return False
    cover = _normalize_cover_text(clinica.cover_test)
    return "exotropia" in cover


_texto_exotropia_lente = (
    "Se documenta exotropia en el cover test, ameritando evaluacion binocular completa "
    "para determinar frecuencia y magnitud de la desviacion, asi como la respuesta a "
    "la correccion optica prescrita."
)
