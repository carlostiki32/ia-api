from __future__ import annotations

import contextvars
import functools
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import Callable

from app.schemas import ImpresionClinicaRequest

logger = logging.getLogger(__name__)

_eval_cache: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "_eval_cache", default=None
)


def _memoize_cond(fn):
    """Cachea el resultado de una condicion durante una evaluacion de evaluar_correlaciones.

    Fuera de ese scope (cache is None), la funcion se ejecuta sin memoizar para
    preservar el comportamiento en llamadas directas desde tests.
    """
    name = fn.__name__

    @functools.wraps(fn)
    def wrapper(req):
        cache = _eval_cache.get()
        if cache is None:
            return fn(req)
        if name not in cache:
            cache[name] = fn(req)
        return cache[name]

    return wrapper


@dataclass(frozen=True)
class Correlacion:
    nombre: str
    condicion: Callable[[ImpresionClinicaRequest], bool]
    texto: str | Callable[[ImpresionClinicaRequest], str]

    def render(self, req: ImpresionClinicaRequest) -> str:
        texto = self.texto
        return texto if isinstance(texto, str) else texto(req)


_NEGACIONES = (
    "sin ",
    "no se observa",
    "no se documenta",
    "no presenta",
    "sin evidencia",
    "negativ",
    "ausenc",
    "ausente",
)
# El SaaS compone cover_test como "OD: Tipo [y Sub] | OI: Tipo [y Sub]"
# con tipo ∈ {Orto, Endo, Exo, Hiper, Hipo} y sub ∈ {Tropia, Foria}.
# Las correlaciones buscan keywords unidas (exoforia, endotropia, etc.);
# esta regex reconoce los pares para expandirlos a la forma unida.
_COVER_PAIR_RE = re.compile(r"\b(endo|exo|hiper|hipo)\s+y\s+(foria|tropia)\b")
_KEYWORDS_BINOCULAR = (
    "diplopia", "vision doble",
    "cefalea", "dolor de cabeza",
    "astenopia", "fatiga visual", "vista cansada",
    "mareo", "vertigo",
    "ardor con lectura", "lagrimeo con lectura",
    "perdida del renglon", "salto de letras",
    "vision borrosa intermitente",
)
_KEYWORDS_CERCANIA = (
    "lectura", "leer", "estudiar", "cerca", "astenopia", "fatiga", "cefalea",
)
_KEYWORDS_CVS = (
    "ardor ocular", "sequedad ocular",
    "vision borrosa intermitente", "dolor ocular",
    "ardor", "sequedad",
)
_KEYWORDS_ANEXOS = {
    "blefaritis": "blefaritis",
    "chalazion": "chalazion",
    "orzuelo": "orzuelo",
    "pterigion": "pterigion",
    "pinguecula": "pinguecula",
    "conjuntivitis": "conjuntivitis",
    "hiperemia": "hiperemia conjuntival",
    "queratitis": "queratitis",
    "erosion": "erosion corneal",
    "leucoma": "leucoma corneal",
    "opacidad corneal": "opacidad corneal",
    "edema corneal": "edema corneal",
    "distriquiasis": "distriquiasis",
    "triquiasis": "triquiasis",
    "ectropion": "ectropion",
    "entropion": "entropion",
    "ptosis": "ptosis palpebral",
}
_KEYWORDS_OPACIDAD_CRISTALINO = (
    "catarata",
    "cataratas",
    "opacidad cristaliniana",
    "opacidad del cristalino",
    "facoesclerosis",
    "pseudofaquia",
    "pseudofaco",
    "pseudofaquico",
    "afaquia",
    "afaquico",
)
_KEYWORDS_PUPILAS = {
    "anisocoria": "anisocoria",
    "midriasis": "midriasis",
    "miosis": "miosis",
    "dpar": "defecto pupilar aferente relativo",
    "marcus gunn": "defecto pupilar aferente relativo",
    "no reactivo": "pupila no reactiva",
    "no reactiva": "pupila no reactiva",
    "irregular": "pupila irregular",
    "discoria": "discoria",
    "ausente": "respuesta pupilar ausente",
}
_KEYWORDS_MOTILIDAD = (
    "limitacion", "paresia", "paralisis", "restriccion", "nistagmo", "nistagmus",
    "dolor con movimiento", "dolor al movimiento", "sobreacti", "hiperfuncion",
    "hipoaccion", "hipofuncion", "sincinesia", "duane", "oftalmoplejia",
    "oftalmoplegia",
)
_KEYWORDS_CAMPOS_POSITIVOS = (
    "escotoma", "defecto", "hemianopsia", "cuadrantopsia",
    "constriccion", "alteracion", "no responde",
)
_KEYWORDS_CAMPOS_NEGATIVOS = ("sin defect", "sin alteracion", "normal", "integro")
_KEYWORDS_AMSLER_POSITIVOS = (
    "distorsion", "metamorfopsia", "escotoma central", "escotoma",
    "alterado", "alteracion", "ondulacion", "lineas torcidas",
)
_KEYWORDS_AMSLER_NEGATIVOS = ("sin distorsion", "sin alteracion", "normal", "negativo")
_KEYWORDS_VASCULARES_DIABETICOS = (
    "microaneurisma", "microaneurismas",
    "exudado",
    "hemorragia retiniana", "hemorragia en llama", "hemorragia intraretin",
    "hemorragia en mancha", "hemorragia puntiforme",
    "neovas", "rubeosis",
)
_KEYWORDS_FONDO_GLAUCOMATOSO = (
    "c/d 0.6", "c/d 0.7", "c/d 0.8", "c/d 0.9",
    "cup/disc 0.6", "cup/disc 0.7", "cup/disc 0.8", "cup/disc 0.9",
    "excavacion", "papila asimetrica", "asimetria c/d", "muesca", "notch",
    "hemorragia peripapilar", "rima neural adelgazada",
)
_KEYWORDS_FONDO_DMAE = (
    "drusas", "drusen", "alteracion pigmentaria", "alteracion del epr",
    "atrofia geografica", "membrana neovascular", "mnvc", "cnv",
    "epiteliopatia", "dmae", "degeneracion macular",
)
_KEYWORDS_PAPILA_NO_GLAUCOMA = (
    "palidez papilar", "palidez de papila",
    "atrofia optica", "atrofia papilar",
    "edema de papila", "papiledema",
    "neuritis optica",
    "borramiento de bordes", "bordes borrosos",
)
_KEYWORDS_FONDO_MACULAR_OTROS = (
    "edema macular", "membrana epirretiniana", "mer", "pucker",
    "agujero macular", "quiste macular", "coroidopatia serosa",
)
_KEYWORDS_FONDO_PERIFERICO = (
    "desgarro", "agujero retiniano", "lattice", "degeneracion reticular",
    "blanco con presion", "desprendimiento", "schisis", "retinosquisis",
)
_KEYWORDS_FONDO_HIPERTENSIVO = (
    "tortuosidad vascular", "tortuosidad", "cruces arteriovenosos", "cruces av",
    "signo de gunn", "estrechamiento arterial", "hilos de cobre",
    "hilos de plata", "algodonoso", "cotton wool", "salus",
    "ingurgitacion venosa",
)
_KEYWORDS_DESVIACION_VERTICAL = ("hiperforia", "hipoforia", "hipertropia", "hipotropia")
_KEYWORDS_FONDO_PERIFERICO_MAP = {
    "desgarro": "desgarro retiniano",
    "agujero retiniano": "agujero retiniano",
    "lattice": "degeneracion lattice",
    "degeneracion reticular": "degeneracion reticular",
    "blanco con presion": "blanco con presion",
    "desprendimiento": "desprendimiento de retina",
    "schisis": "schisis periferica",
    "retinosquisis": "retinosquisis",
}


_WHITESPACE_RE = re.compile(r"\s+")


@functools.lru_cache(maxsize=512)
def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return _WHITESPACE_RE.sub(" ", ascii_only).strip().lower()


@functools.lru_cache(maxsize=1024)
def _compiled_keyword(keyword: str) -> re.Pattern:
    return re.compile(re.escape(keyword))


@functools.lru_cache(maxsize=64)
def _compiled_union(keywords: tuple[str, ...]) -> re.Pattern:
    return re.compile("|".join(re.escape(k) for k in keywords))


@functools.lru_cache(maxsize=256)
def _normalize_cover_text(value: str | None) -> str:
    """Normaliza cover_test y expande los pares 'tipo y sub' a su forma unida.

    La UI del SaaS compone cover_test como 'OD: Exo y Foria | OI: Orto'. Las
    correlaciones buscan keywords unidas como 'exoforia' o 'endotropia'.
    Esta funcion agrega las formas unidas al texto normalizado para que
    ambas convenciones (unida o separada por ' y ') matcheen.
    """
    text = _normalize_text(value)
    if not text:
        return ""
    expanded = _COVER_PAIR_RE.sub(lambda m: f"{m.group(1)}{m.group(2)}", text)
    if expanded == text:
        return text
    return f"{text} {expanded}"


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def _join_hallazgos(values: list[str]) -> str:
    if not values:
        return ""
    if len(values) == 1:
        return values[0]
    return ", ".join(values[:-1]) + f" y {values[-1]}"


def _keyword_matches(text: str, keyword: str, *, allow_negation_window: bool) -> bool:
    for match in _compiled_keyword(keyword).finditer(text):
        if not allow_negation_window:
            return True
        sentence_start = max(text.rfind(sep, 0, match.start()) for sep in ".;!?") + 1
        sentence_prefix = text[sentence_start:match.start()]
        if any(neg in sentence_prefix for neg in _NEGACIONES):
            continue
        return True
    return False


def _contains_keyword(
    value: str | None,
    keywords: tuple[str, ...] | list[str],
    *,
    allow_negation_window: bool = False,
) -> bool:
    text = _normalize_text(value)
    if not text:
        return False
    if not allow_negation_window:
        # Path rapido: una sola busqueda sobre la union de keywords.
        kw_tuple = tuple(keywords)
        return _compiled_union(kw_tuple).search(text) is not None
    return any(
        _keyword_matches(text, keyword, allow_negation_window=allow_negation_window)
        for keyword in keywords
    )


def _extract_normalized_findings(
    value: str | None,
    keyword_map: dict[str, str],
    *,
    allow_negation_window: bool = False,
) -> list[str]:
    text = _normalize_text(value)
    findings = [
        normalized
        for keyword, normalized in keyword_map.items()
        if _keyword_matches(text, keyword, allow_negation_window=allow_negation_window)
    ]
    return _dedupe(findings)


def _fondo_contains(req: ImpresionClinicaRequest, keywords: tuple[str, ...]) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    return _contains_keyword(
        clinica.fondo_de_ojo,
        keywords,
        allow_negation_window=True,
    )


def _snellen_denominator(av: str | None) -> int | None:
    if av is None:
        return None
    match = re.match(r"^\s*20\s*/\s*(\d{1,3})\s*$", av)
    if match is None:
        return None
    return int(match.group(1))


def _av_es_limitada(av: str | None) -> bool:
    denominator = _snellen_denominator(av)
    return denominator is not None and denominator > 20


def _av_categoria(av: str | None) -> str | None:
    denominator = _snellen_denominator(av)
    if denominator is None or denominator <= 20:
        return None
    if 21 <= denominator <= 30:
        return "leve reduccion de la agudeza visual con correccion"
    if 31 <= denominator <= 50:
        return "reduccion moderada de la agudeza visual con correccion"
    if 51 <= denominator <= 100:
        return "reduccion marcada de la agudeza visual con correccion"
    return "deficit visual severo con correccion optima"


def _equivalente_esferico(esf: float | None, cil: float | None) -> float | None:
    if esf is None:
        return None
    return esf + (cil or 0.0) / 2.0


def _format_eyes_with_values(values: list[tuple[str, float]], label: str) -> str:
    partes = [f"{ojo} ({label} {valor:+.2f}D)" for ojo, valor in values]
    return _join_hallazgos(partes)


def _has_binocular_symptoms(req: ImpresionClinicaRequest) -> bool:
    paciente = req.paciente
    motivo = paciente.motivo_consulta if paciente is not None else None
    return _contains_keyword(motivo, _KEYWORDS_BINOCULAR)


@_memoize_cond
def _cond_fondo_periferico_riesgo(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: fondo con lattice o desgarro periferico activa urgencia retinologica."""
    return _fondo_contains(req, _KEYWORDS_FONDO_PERIFERICO)


def _texto_fondo_periferico_riesgo(req: ImpresionClinicaRequest) -> str:
    hallazgos = _extract_normalized_findings(
        req.clinica.fondo_de_ojo if req.clinica is not None else None,
        _KEYWORDS_FONDO_PERIFERICO_MAP,
        allow_negation_window=True,
    )
    hallazgo = _join_hallazgos(hallazgos) if hallazgos else "hallazgo periferico de riesgo"
    return f"Hallazgo urgente: en la retina periferica se documenta {hallazgo}."


@_memoize_cond
def _cond_glaucoma_asimetrico(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: DPAR + fondo glaucomatoso confirman neuropatia optica glaucomatosa asimetrica con compromiso funcional."""
    if req.clinica is None:
        return False
    txt_pupilas = _normalize_text(req.clinica.reflejos_pupilares)
    hay_dpar = any(k in txt_pupilas for k in ("dpar", "marcus gunn"))
    if not hay_dpar:
        return False
    return _fondo_contains(req, _KEYWORDS_FONDO_GLAUCOMATOSO)


_texto_glaucoma_asimetrico = (
    "Hallazgo urgente: se documenta excavacion papilar aumentada con defecto pupilar "
    "aferente relativo, lo que indica compromiso asimetrico del nervio optico con "
    "repercusion funcional confirmada."
)


@_memoize_cond
def _cond_fondo_glaucomatoso(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: excavacion aumentada o notch papilar activa sospecha glaucomatosa."""
    if _cond_glaucoma_asimetrico(req):
        return False
    return _fondo_contains(req, _KEYWORDS_FONDO_GLAUCOMATOSO)


_texto_fondo_glaucomatoso = (
    "Se documentan hallazgos papilares con excavacion aumentada y/o alteracion "
    "del anillo neurorretiniano."
)


@_memoize_cond
def _cond_papila_patologica(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: palidez, edema o neuritis papilar activan alerta neurooftalmica."""
    return _fondo_contains(req, _KEYWORDS_PAPILA_NO_GLAUCOMA)


def _texto_papila_patologica(req: ImpresionClinicaRequest) -> str:
    fondo = _normalize_text(req.clinica.fondo_de_ojo if req.clinica is not None else None)
    es_emergencia = any(
        token in fondo
        for token in ("papiledema", "edema de papila", "borramiento de bordes", "bordes borrosos")
    )
    if es_emergencia:
        return (
            "Hallazgo urgente: se documenta alteracion del nervio optico con bordes "
            "papilares difusos."
        )
    return (
        "Se documenta alteracion del nervio optico no asociada a excavacion glaucomatosa."
    )


@_memoize_cond
def _cond_fondo_macular_dmae(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: drusas o alteracion del EPR en fondo sugieren patron de DMAE."""
    return _fondo_contains(req, _KEYWORDS_FONDO_DMAE)


_texto_fondo_macular_dmae = (
    "Se documentan hallazgos maculares degenerativos en fondo de ojo."
)


@_memoize_cond
def _cond_fondo_macular_otros(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: edema macular o MER en fondo activa correlacion macular no DMAE."""
    return _fondo_contains(req, _KEYWORDS_FONDO_MACULAR_OTROS)


_texto_fondo_macular_otros = (
    "En la region macular se documenta alteracion estructural."
)


@_memoize_cond
def _cond_fondo_hipertensivo(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: cruces AV o tortuosidad vascular sugieren retinopatia hipertensiva."""
    return _fondo_contains(req, _KEYWORDS_FONDO_HIPERTENSIVO)


_texto_fondo_hipertensivo = (
    "Se documentan hallazgos vasculares en fondo de ojo con alteraciones "
    "arteriovenosas."
)


@_memoize_cond
def _cond_fondo_vascular_diabetico(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: microaneurismas o exudados activan correlacion vascular metabolica."""
    if any((
        _cond_fondo_periferico_riesgo(req),
        _cond_fondo_glaucomatoso(req),
        _cond_fondo_macular_dmae(req),
        _cond_fondo_macular_otros(req),
        _cond_fondo_hipertensivo(req),
    )):
        return False
    return _fondo_contains(req, _KEYWORDS_VASCULARES_DIABETICOS)


_texto_fondo_vascular_diabetico = (
    "Se documentan hallazgos vasculares en fondo de ojo con presencia de "
    "alteraciones microvasculares."
)


def _cond_pupilas_alteradas(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: anisocoria o DPAR en reflejos pupilares ameritan alerta neurooftalmica."""
    if _cond_glaucoma_asimetrico(req):
        return False
    clinica = req.clinica
    if clinica is None:
        return False
    hallazgos = _extract_normalized_findings(
        clinica.reflejos_pupilares,
        _KEYWORDS_PUPILAS,
        allow_negation_window=True,
    )
    return bool(hallazgos)


def _texto_pupilas_alteradas(req: ImpresionClinicaRequest) -> str:
    hallazgos = _extract_normalized_findings(
        req.clinica.reflejos_pupilares,
        _KEYWORDS_PUPILAS,
        allow_negation_window=True,
    )
    texto = f"En la exploracion pupilar se documenta {_join_hallazgos(hallazgos)}."
    if "defecto pupilar aferente relativo" in hallazgos:
        texto += (
            " Hallazgo urgente: se identifica defecto pupilar aferente relativo, "
            "indicador de asimetria funcional en la via optica aferente."
        )
    return texto


def _cond_motilidad_alterada(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: limitacion, nistagmo o dolor al movimiento activan estudio motor."""
    clinica = req.clinica
    if clinica is None:
        return False
    return _contains_keyword(
        clinica.motilidad_ocular,
        _KEYWORDS_MOTILIDAD,
        allow_negation_window=True,
    )


_texto_motilidad_alterada = (
    "Se documenta alteracion de la motilidad ocular."
)


def _cond_campos_visuales_alterados(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: escotoma o hemianopsia en confrontacion ameritan perimetria formal."""
    clinica = req.clinica
    if clinica is None:
        return False
    texto = _normalize_text(clinica.confrontacion_campos_visuales)
    if not texto:
        return False
    if any(neg in texto for neg in _KEYWORDS_CAMPOS_NEGATIVOS):
        return False
    return _contains_keyword(
        clinica.confrontacion_campos_visuales,
        _KEYWORDS_CAMPOS_POSITIVOS,
        allow_negation_window=True,
    )


_texto_campos_visuales_alterados = (
    "La confrontacion de campos visuales revela alteracion."
)


@_memoize_cond
def _cond_opacidad_cristaliniana(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: catarata o pseudofaquia documentadas activan correlacion cristaliniana."""
    clinica = req.clinica
    if clinica is None:
        return False
    texto = " ".join(filter(None, [clinica.anexos_oculares, clinica.fondo_de_ojo]))
    return _contains_keyword(texto, _KEYWORDS_OPACIDAD_CRISTALINO, allow_negation_window=True)


_texto_opacidad_cristaliniana = (
    "Se documenta alteracion del cristalino."
)


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
    return (
        f"Se documenta miopia de magnitud {severidad} en {_format_eyes_with_values(ojos, 'EE')}."
    )


def _cond_hipermetropia_alta(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: equivalente esferico de +5.00D o mayor activa hipermetropia alta."""
    refraccion = req.refraccion
    if refraccion is None:
        return False
    for ojo in (refraccion.od, refraccion.oi):
        ee = _equivalente_esferico(ojo.esfera, ojo.cilindro)
        if ee is not None and ee >= 5.00:
            return True
    return False


def _texto_hipermetropia_alta(req: ImpresionClinicaRequest) -> str:
    ojos = []
    for label, ojo in [("OD", req.refraccion.od), ("OI", req.refraccion.oi)]:
        ee = _equivalente_esferico(ojo.esfera, ojo.cilindro)
        if ee is not None and ee >= 5.00:
            ojos.append((label, ee))
    base = f"Se documenta hipermetropia alta en {_format_eyes_with_values(ojos, 'EE')}"
    edad = req.paciente.edad if req.paciente is not None else None
    if edad is None or edad >= 40:
        return f"{base}."
    return f"{base}, con demanda acomodativa significativa."


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
    return (
        f"Existe anisometropia {severidad} por diferencia de equivalente esferico de {diff:.2f}D "
        f"entre OD ({ee_od:+.2f}) y OI ({ee_oi:+.2f}); {cierre}."
    )


def _cond_av_cc_limitada(req: ImpresionClinicaRequest) -> bool:
    refraccion = req.refraccion
    if refraccion is None:
        return False
    return _av_es_limitada(refraccion.od.av_cc) or _av_es_limitada(refraccion.oi.av_cc)


def _texto_av_cc_limitada(req: ImpresionClinicaRequest) -> str:
    partes = []
    for label, av in [("OD", req.refraccion.od.av_cc), ("OI", req.refraccion.oi.av_cc)]:
        if not _av_es_limitada(av):
            continue
        partes.append(f"{label} ({av}): {_av_categoria(av)}")
    return "; ".join(partes) + "."


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
        if (esf_rx - esf_ar) >= 0.50:
            return True
    return False


_texto_ar_rx_espasmo_acomodativo = (
    "El autorrefractometro documenta mayor componente miopico que la refraccion "
    "subjetiva final en un paciente joven con uso de pantallas."
)


@_memoize_cond
def _cond_ar_rx_cambio_cristalino(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: mayor de 55 anos con discrepancia esferica amplia entre AR y Rx."""
    if req.refraccion is None or req.akr is None or req.paciente is None:
        return False
    edad = req.paciente.edad
    if edad is None or edad < 55:
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
    "paciente mayor de 55 anos."
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
        if esf_ar is not None and esf_rx is not None and abs(esf_ar - esf_rx) > 1.00:
            return True
        if cil_ar is not None and cil_rx is not None and abs(cil_ar - cil_rx) > 1.00:
            return True
    return False


_texto_ar_rx_variabilidad_inespecifica = (
    "Se documenta discrepancia entre autorrefractometro y refraccion final."
)


def _cond_ar_detecta_astigmatismo_no_prescrito(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: AR detecta cilindro relevante y la Rx final no lo prescribe."""
    if req.refraccion is None or req.akr is None:
        return False
    for ojo in ("od", "oi"):
        cil_ar = getattr(req.akr, ojo).cilindro
        cil_rx = getattr(req.refraccion, ojo).cilindro
        if cil_ar is None or abs(cil_ar) < 0.75:
            continue
        if cil_rx is None or abs(cil_rx) < 0.50:
            return True
    return False


_texto_ar_detecta_astigmatismo_no_prescrito = (
    "El autorrefractometro detecta un componente astigmatico que no fue incluido en la "
    "refraccion subjetiva final, lo que puede corresponder a astigmatismo subumbral "
    "con tolerancia clinica adecuada o variabilidad de la medicion automatizada."
)


def _es_eje_oblicuo(eje: int) -> bool:
    return (20 <= eje <= 70) or (110 <= eje <= 160)


def _cond_astig_oblicuo(req: ImpresionClinicaRequest) -> bool:
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
    for label, ojo in [("OD", req.refraccion.od), ("OI", req.refraccion.oi)]:
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
        partes.append(f"{label} ({cil:+.2f} x {eje}): {descripcion}")
    return "; ".join(partes) + "."


def _cond_amsler_alterado(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: metamorfopsia o lineas torcidas en Amsler ameritan OCT macular."""
    clinica = req.clinica
    if clinica is None:
        return False
    texto = _normalize_text(clinica.grid_de_amsler)
    if not texto:
        return False
    if any(neg in texto for neg in _KEYWORDS_AMSLER_NEGATIVOS):
        return False
    return _contains_keyword(
        clinica.grid_de_amsler,
        _KEYWORDS_AMSLER_POSITIVOS,
        allow_negation_window=True,
    )


_texto_amsler_alterado = (
    "El test de Amsler revela alteracion."
)


def _cond_anexos_patologicos(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: blefaritis, pterigion o queratitis en anexos activan correlacion."""
    clinica = req.clinica
    if clinica is None:
        return False
    return bool(
        _extract_normalized_findings(
            clinica.anexos_oculares,
            _KEYWORDS_ANEXOS,
            allow_negation_window=True,
        )
    )


def _texto_anexos_patologicos(req: ImpresionClinicaRequest) -> str:
    hallazgos = _extract_normalized_findings(
        req.clinica.anexos_oculares,
        _KEYWORDS_ANEXOS,
        allow_negation_window=True,
    )
    return f"En anexos oculares se documenta {_join_hallazgos(hallazgos)}."


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
        if ppc > 15:
            partes.append(f"punto proximo de convergencia marcadamente alejado ({ppc} cm)")
        else:
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
    "Se documenta exoforia con sintomatologia binocular asociada."
)


def _cond_cover_endoforia_sintomatica(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: endoforia sintomatica sin endotropia sugiere exceso de convergencia."""
    if req.clinica is None or req.paciente is None:
        return False
    cover = _normalize_cover_text(req.clinica.cover_test)
    return "endoforia" in cover and "endotropia" not in cover and _has_binocular_symptoms(req)


_texto_cover_endoforia_sintomatica = (
    "Se documenta endoforia con sintomatologia binocular asociada."
)


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
    "Se documenta punto proximo de convergencia alejado con tendencia exoforica "
    "y sintomatologia asociada a vision proxima."
)


def _cond_cvs_sospecha(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: pantallas y ardor o cefalea sugieren sindrome visual informatico."""
    if req.clinica is None or req.paciente is None:
        return False
    if req.clinica.uso_pantallas not in ("btw2_6", "gt6"):
        return False
    return _contains_keyword(req.paciente.motivo_consulta, _KEYWORDS_CVS)


_texto_cvs_sospecha = (
    "El perfil de uso de pantallas se correlaciona con la sintomatologia "
    "visual referida."
)


def _cond_endotropia_lente(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    cover = _normalize_cover_text(clinica.cover_test)
    return "endotropia" in cover and req.tipo_lente is not None


_texto_endotropia_lente = (
    "Se documenta endotropia en el cover test."
)


def _cond_exotropia_lente(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: exotropia manifiesta con lente prescrito amerita estudio binocular."""
    clinica = req.clinica
    if clinica is None:
        return False
    cover = _normalize_cover_text(clinica.cover_test)
    return "exotropia" in cover and req.tipo_lente is not None


_texto_exotropia_lente = (
    "Se documenta exotropia en el cover test."
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
        cierre = "desviacion manifiesta vertical."
    else:
        cierre = "desviacion vertical latente."
    return f"Se documenta {texto_hallazgo}, {cierre}"


def _cond_but_critico(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: BUT menor de 5 segundos activa sospecha de ojo seco clinico."""
    clinica = req.clinica
    if clinica is None:
        return False
    but = clinica.ojo_seco_but_seg
    return but is not None and but < 5


def _texto_but_critico(req: ImpresionClinicaRequest) -> str:
    but = req.clinica.ojo_seco_but_seg
    return f"El tiempo de ruptura lagrimal de {but}s se encuentra significativamente reducido."


def _cond_but_pantallas(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    but = clinica.ojo_seco_but_seg
    return but is not None and 5 <= but <= 9 and clinica.uso_pantallas in ("btw2_6", "gt6")


def _texto_but_pantallas(req: ImpresionClinicaRequest) -> str:
    but = req.clinica.ojo_seco_but_seg
    return (
        f"El tiempo de ruptura lagrimal de {but} segundos es reducido en el contexto "
        "del uso de pantallas, lo que indica inestabilidad de la pelicula lagrimal."
    )


def _cond_but_limitrofe(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: BUT suboptimo sin alta exposicion a pantallas activa hallazgo leve."""
    clinica = req.clinica
    if clinica is None:
        return False
    but = clinica.ojo_seco_but_seg
    return but is not None and 5 <= but <= 9 and clinica.uso_pantallas in (None, "lt2")


def _texto_but_limitrofe(req: ImpresionClinicaRequest) -> str:
    but = req.clinica.ojo_seco_but_seg
    return f"El tiempo de ruptura lagrimal de {but}s se encuentra en rango suboptimo."


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
        )
    )


def _texto_adulto_mayor_screening(req: ImpresionClinicaRequest) -> str:
    edad = req.paciente.edad
    return (
        f"Paciente de {edad} anos con reduccion de agudeza visual sin causa "
        "identificada en el examen actual."
    )


CORRELACIONES: list[Correlacion] = [
    Correlacion("fondo_periferico_riesgo", _cond_fondo_periferico_riesgo, _texto_fondo_periferico_riesgo),
    Correlacion("papila_patologica", _cond_papila_patologica, _texto_papila_patologica),
    Correlacion("glaucoma_asimetrico", _cond_glaucoma_asimetrico, _texto_glaucoma_asimetrico),
    Correlacion("pupilas_alteradas", _cond_pupilas_alteradas, _texto_pupilas_alteradas),
    Correlacion("fondo_glaucomatoso", _cond_fondo_glaucomatoso, _texto_fondo_glaucomatoso),
    Correlacion("fondo_macular_dmae", _cond_fondo_macular_dmae, _texto_fondo_macular_dmae),
    Correlacion("fondo_macular_otros", _cond_fondo_macular_otros, _texto_fondo_macular_otros),
    Correlacion("fondo_hipertensivo", _cond_fondo_hipertensivo, _texto_fondo_hipertensivo),
    Correlacion("fondo_vascular_diabetico", _cond_fondo_vascular_diabetico, _texto_fondo_vascular_diabetico),
    Correlacion("motilidad_alterada", _cond_motilidad_alterada, _texto_motilidad_alterada),
    Correlacion("campos_visuales_alterados", _cond_campos_visuales_alterados, _texto_campos_visuales_alterados),
    Correlacion("opacidad_cristaliniana", _cond_opacidad_cristaliniana, _texto_opacidad_cristaliniana),
    Correlacion("but_critico", _cond_but_critico, _texto_but_critico),
    Correlacion("miopia_magna", _cond_miopia_magna, _texto_miopia_magna),
    Correlacion("hipermetropia_alta", _cond_hipermetropia_alta, _texto_hipermetropia_alta),
    Correlacion("anisometropia", _cond_anisometropia, _texto_anisometropia),
    Correlacion("av_cc_limitada", _cond_av_cc_limitada, _texto_av_cc_limitada),
    Correlacion("ar_rx_espasmo_acomodativo", _cond_ar_rx_espasmo_acomodativo, _texto_ar_rx_espasmo_acomodativo),
    Correlacion("ar_rx_cambio_cristalino", _cond_ar_rx_cambio_cristalino, _texto_ar_rx_cambio_cristalino),
    Correlacion("ar_rx_variabilidad_inespecifica", _cond_ar_rx_variabilidad_inespecifica, _texto_ar_rx_variabilidad_inespecifica),
    Correlacion("ar_detecta_astigmatismo_no_prescrito", _cond_ar_detecta_astigmatismo_no_prescrito, _texto_ar_detecta_astigmatismo_no_prescrito),
    Correlacion("astig_oblicuo", _cond_astig_oblicuo, _texto_astig_oblicuo),
    Correlacion("amsler_alterado", _cond_amsler_alterado, _texto_amsler_alterado),
    Correlacion("anexos_patologicos", _cond_anexos_patologicos, _texto_anexos_patologicos),
    Correlacion("insuficiencia_convergencia", _cond_insuficiencia_convergencia, _texto_insuficiencia_convergencia),
    Correlacion("ppc_exoforia", _cond_ppc_exoforia, _texto_ppc_exoforia),
    Correlacion("cover_exoforia_sintomatica", _cond_cover_exoforia_sintomatica, _texto_cover_exoforia_sintomatica),
    Correlacion("cover_endoforia_sintomatica", _cond_cover_endoforia_sintomatica, _texto_cover_endoforia_sintomatica),
    Correlacion("desviacion_vertical", _cond_desviacion_vertical, _texto_desviacion_vertical),
    Correlacion("cvs_sospecha", _cond_cvs_sospecha, _texto_cvs_sospecha),
    Correlacion("endotropia_lente", _cond_endotropia_lente, _texto_endotropia_lente),
    Correlacion("exotropia_lente", _cond_exotropia_lente, _texto_exotropia_lente),
    Correlacion("but_pantallas", _cond_but_pantallas, _texto_but_pantallas),
    Correlacion("but_limitrofe", _cond_but_limitrofe, _texto_but_limitrofe),
    Correlacion("presbicia_multifocal", _cond_presbicia_multifocal, _texto_presbicia_multifocal),
    Correlacion("adulto_mayor_screening", _cond_adulto_mayor_screening, _texto_adulto_mayor_screening),
]


def evaluar_correlaciones(req: ImpresionClinicaRequest) -> list[str]:
    token = _eval_cache.set({})
    try:
        activas = [
            (correlacion.nombre, correlacion.render(req))
            for correlacion in CORRELACIONES
            if correlacion.condicion(req)
        ]
    finally:
        _eval_cache.reset(token)
    if activas:
        logger.debug(
            "Correlaciones activadas [%s]: %s",
            req.receta_id,
            [nombre for nombre, _ in activas],
        )
    return [texto for _, texto in activas]
