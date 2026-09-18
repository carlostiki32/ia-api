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
    _keyword_matches,
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
# Sintomas astenopicos y de disfuncion binocular en vision proxima / lectura / pantallas.
# Diferenciados estrictamente de la simple demanda visual u ocupacion.
_KEYWORDS_SINTOMAS_PROXIMOS = (
    # Sintomas binoculares clasicos
    "diplopia", "vision doble", "veo doble", "imagenes dobles",
    "cefalea", "dolor de cabeza",
    "astenopia", "fatiga visual", "fatiga ocular", "vista cansada",
    "cansancio visual", "cansancio ocular", "ojos cansados",
    "ardor con lectura", "lagrimeo con lectura", "ardor al leer", "dolor al leer",
    "perdida del renglon", "salto de renglon", "pierde el renglon",
    "salto de letras", "se juntan las letras", "letras que bailan",
    "letras se mueven", "dificultad para enfocar",
    "mareo al leer", "mareo con lectura", "sueno al leer",
    "vision borrosa intermitente",
    # Quejas astenopicas directas en vision proxima / lectura / pantallas
    "fatiga al leer", "fatiga de cerca", "fatiga con lectura", "fatiga al usar",
    "cansancio al leer", "cansancio de cerca", "cansancio con lectura", "cansancio al usar",
    "cansancio al usar la computadora", "fatiga en computadora", "cansancio en computadora",
    "borroso de cerca", "borrosa de cerca", "borroso al leer", "borrosa al leer",
    "molestia al leer", "molestias al leer", "molestias de cerca",
    "fatiga", "cansancio", "astenopia",
)
_KEYWORDS_TAREAS_CERCANIA = (
    "lectura", "leer", "estudiar", "estudio", "cerca", "vision proxima",
    "vision cercana", "trabajo de cerca", "computadora", "pantalla", "celular",
    "escribir",
)
# La demanda de vision proxima por ocupacion representa contexto de exposicion/riesgo,
# pero no sustituye la existencia de sintomas referidos por el paciente.
_KEYWORDS_OCUPACION_PROXIMA = (
    "estudiante", "oficina", "oficinista", "programador", "desarrollador",
    "contador", "contabilidad", "capturista", "digitador", "secretaria",
    "disenador", "editor", "escritor", "costura", "costurera", "sastre",
    "relojero", "dentista", "cajera", "cajero", "computadora", "lectura",
)
_KEYWORDS_DESVIACION_VERTICAL = ("hiperforia", "hipoforia", "hipertropia", "hipotropia")

# Punto proximo de convergencia (PPC):
# - En pre-presbitas (edad < 40): segun la literatura CITT (Convergence Insufficiency
#   Treatment Trial), el punto de rotura anormal se define en >= 6 cm (receded near point of convergence).
# - En presbitas (edad >= 40) o sin edad especificada: se aplica un umbral conservador de > 10 cm,
#   el cual queda formalmente registrado como pendiente de validacion mediante protocolo clinico.
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
    paciente = req.paciente
    edad = paciente.edad if paciente is not None else None
    if edad is not None and edad < 40:
        return clinica.ppc_cm >= _PPC_UMBRAL_JOVEN_CM
    return clinica.ppc_cm > _PPC_UMBRAL_PRESBITA_CM


def _cover_tokens(req: ImpresionClinicaRequest) -> frozenset[str]:
    """Tokens estructurados del cover test canonico del SaaS. Incluye los tipos
    sin clasificar ('exo', 'endo', 'hiper', 'hipo') que las keywords unidas no
    ven, porque la UI permite elegir Tipo sin elegir Tropia/Foria."""
    clinica = req.clinica
    return _cover_desviaciones(clinica.cover_test if clinica is not None else None)


def _cover_has(req: ImpresionClinicaRequest, deviation: str) -> bool:
    """Verifica si una desviacion del cover test esta presente y afirmada,
    reconociendo tanto el formato canonico estructurado del SaaS como texto libre
    con ventana de negacion (ej. 'sin endotropia ni exotropia').
    """
    clinica = req.clinica
    if clinica is None or not clinica.cover_test:
        return False
    tokens = _cover_tokens(req)
    if deviation in tokens:
        return True
    cover = _normalize_cover_text(clinica.cover_test)
    return _keyword_matches(cover, deviation, allow_negation_window=True)


def _has_binocular_symptoms(req: ImpresionClinicaRequest) -> bool:
    paciente = req.paciente
    motivo = paciente.motivo_consulta if paciente is not None else None
    if not motivo:
        return False
    return _contains_keyword(motivo, _KEYWORDS_SINTOMAS_PROXIMOS, allow_negation_window=True)


def _has_near_symptoms(req: ImpresionClinicaRequest) -> bool:
    """Sintomas reales en vision proxima o disfuncion binocular referidos por el paciente."""
    return _has_binocular_symptoms(req)


def _hay_demanda_proxima(req: ImpresionClinicaRequest) -> bool:
    """Contexto de demanda de vision proxima por ocupacion o tareas continuas de cerca."""
    paciente = req.paciente
    if paciente is None:
        return False
    return _contains_keyword(
        paciente.motivo_consulta, _KEYWORDS_TAREAS_CERCANIA, allow_negation_window=True
    ) or _contains_keyword(
        paciente.ocupacion, _KEYWORDS_OCUPACION_PROXIMA, allow_negation_window=True
    )


@_memoize_cond
def _cond_insuficiencia_convergencia(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: PPC alejado (>= 6 cm en pre-presbita segun umbral de rotura CITT,
    o > 10 cm en presbita), exoforia en cover test y sintomatologia real de vision proxima.

    Exige sintomas astenopicos/binoculares activos referidos por el paciente; la ocupacion
    o demanda laboral de cerca por si solas NO constituyen sintomatologia.
    """
    if req.clinica is None or req.paciente is None:
        return False
    if not _ppc_alejado(req):
        return False
    if not _cover_has(req, "exoforia"):
        return False
    return _has_near_symptoms(req)


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
    return _ppc_alejado(req) or _cover_has(req, "exoforia") or _cover_has(req, "exo")


def _texto_ppc_exoforia(req: ImpresionClinicaRequest) -> str:
    partes = []
    clinica = req.clinica
    ppc = clinica.ppc_cm if clinica is not None else None
    cover = _normalize_cover_text(clinica.cover_test if clinica is not None else None)
    if _ppc_alejado(req):
        partes.append(f"punto proximo de convergencia alejado ({ppc} cm)")
    if _cover_has(req, "exoforia"):
        if any(token in cover for token in ("vp", "cerca", "proxima")):
            partes.append("exoforia en vision proxima")
        elif any(token in cover for token in ("vl", "lejos")):
            partes.append("exoforia en vision lejana")
        else:
            partes.append("tendencia divergente en el cover test")
    elif _cover_has(req, "exo"):
        partes.append(
            "exodesviacion no clasificada en el cover test (conviene precisar foria o tropia)"
        )
    if _ppc_alejado(req) and (_cover_has(req, "exoforia") or _cover_has(req, "exo")):
        return f"El paciente presenta {' y '.join(partes)}, ameritando evaluacion binocular completa."
    return "El paciente presenta " + " y ".join(partes) + "."


def _cond_cover_exoforia_sintomatica(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: exoforia en cover test con cefalea o diplopia sugiere disfuncion divergente."""
    if req.clinica is None or req.paciente is None:
        return False
    if _cond_insuficiencia_convergencia(req):
        return False
    return _cover_has(req, "exoforia") and _has_binocular_symptoms(req)


_texto_cover_exoforia_sintomatica = (
    "Se documenta exoforia con sintomatologia binocular asociada, sugestiva de "
    "descompensacion forica que amerita evaluacion funcional."
)


def _cond_cover_endoforia_sintomatica(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: endoforia (o endodesviacion sin clasificar) sintomatica sin
    endotropia sugiere exceso de convergencia."""
    if req.clinica is None or req.paciente is None:
        return False
    hay_endo = _cover_has(req, "endoforia") or _cover_has(req, "endo")
    hay_tropia = _cover_has(req, "endotropia")
    return hay_endo and not hay_tropia and _has_binocular_symptoms(req)


def _texto_cover_endoforia_sintomatica(req: ImpresionClinicaRequest) -> str:
    if _cover_has(req, "endoforia"):
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
    if clinica is None or not clinica.cover_test:
        return False
    if any(_cover_has(req, keyword) for keyword in _KEYWORDS_DESVIACION_VERTICAL):
        return True
    return _cover_has(req, "hiper") or _cover_has(req, "hipo")


def _texto_desviacion_vertical(req: ImpresionClinicaRequest) -> str:
    forias = [k for k in _KEYWORDS_DESVIACION_VERTICAL if _cover_has(req, k) and "foria" in k]
    tropias = [k for k in _KEYWORDS_DESVIACION_VERTICAL if _cover_has(req, k) and "tropia" in k]
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
    return _cover_has(req, "endotropia")


_texto_endotropia_lente = (
    "Se documenta endotropia en el cover test, ameritando evaluacion de la respuesta "
    "a la correccion optica prescrita, con cover test bajo correccion para clasificar "
    "el tipo de desviacion."
)


def _cond_exotropia_lente(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: exotropia manifiesta amerita estudio binocular."""
    return _cover_has(req, "exotropia")


_texto_exotropia_lente = (
    "Se documenta exotropia en el cover test, ameritando evaluacion binocular completa "
    "para determinar frecuencia y magnitud de la desviacion, asi como la respuesta a "
    "la correccion optica prescrita."
)
