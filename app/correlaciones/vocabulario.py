"""Formas léxicas compartidas; comparte brusquedad e inicio reciente propio.

Las etiquetas y decisiones clínicas pertenecen a cada consumidor. Las pérdidas
súbitas o recientes exigen un marcador propio en la misma cláusula.
"""
from __future__ import annotations

import re

DIPLOPIA = (
    "diplopia", "vision doble", "veo doble", "imagenes dobles", "viendo doble",
    "ve doble", "veia doble", "ver doble", "vio doble", "ha visto doble",
    "doble vision", "imagen doble", "vi doble", "he visto doble",
)
# Los adjetivos posteriores se leen como calificadores: no alargar una
# coincidencia previa evita cambiar el span que recibe el negador vigente.
PERDIDA_VISION = tuple(dict.fromkeys((
    "perdida visual", "perdida de vision", "perdida de la vision",
    "perdida de vista", "perdida de la vista", "dejo de ver", "deje de ver",
    *(f"{verbo} {articulo}{objeto}" for verbo in (
        "perdio", "perdi", "pierde", "pierdo", "perdiendo", "ha perdido", "he perdido"
    ) for articulo in ("", "la ") for objeto in ("vision", "vista")),
    *(f"perdida {modo} {objeto}" for modo in ("subita", "brusca", "repentina")
      for objeto in ("visual", "de vision", "de la vision", "de vista", "de la vista")),
)))


# Objetos y mejorías no son pérdida visual. Se conserva el span del verbo.
COMPLEMENTO_VISUAL = (
    r"(?=\s*(?:$|[.,;:!?|\n]|\b(?:hoy|ayer|anoche|esta|hace|desde|"
    r"subit\w*|brusc\w*|repentin\w*|de\s+(?:repente|golpe|un\s+momento)|"
    r"(?:con|por|en)\s+(?:(?:el|la)\s+)?(?:od|oi|ao|ojos?)|"
    r"(?:(?:la|su)\s+)?mitad|(?:el\s+)?campo(?:\s+visual)?|"
    r"de\s+(?:lejos|cerca)|nada|bien)\b))"
)


def patron_formas(formas: tuple[str, ...]) -> str:
    return r"\b(?:" + "|".join((r"\s+".join(map(re.escape, f.split()))
                                + (COMPLEMENTO_VISUAL if f in ("dejo de ver", "deje de ver") else ""))
                               for f in sorted(formas, key=len, reverse=True)) + r")\b"


DIPLOPIA_PATRON = patron_formas(DIPLOPIA)
PERDIDA_VISION_PATRON = patron_formas(PERDIDA_VISION)
SOMBRA_CORTINA_PATRON = (
    r"\b(?:cortinas?|telon|nube|sombras?\s+que\s+(?:avanza|sube|baja|cubre)|"
    r"sombras?\s+(?:(?:sobre|en)\s+(?:(?:la\s+)?(?:vision|vista)|el\s+campo\s+visual|"
    r"(?:el\s+)?ojo|od|oi|ao))|(?:ve|veo|veia|vio|vi|ver|viendo)\s+(?:una\s+)?sombras?)\b"
)
BRUSQUEDAD_PATRON = (
    r"\b(?:subit[ao]s?|subitamente|repentin[ao]s?|repentinamente|de repente|de golpe|"
    r"brusc[ao]s?|bruscamente|de un momento a otro)\b"
)
BRUSQUEDAD_RE = re.compile(BRUSQUEDAD_PATRON)
_PERDIDA_RE = re.compile(PERDIDA_VISION_PATRON)
_CORTE_RE = re.compile(r"[.;:!?|\n]|\b(?:pero|sin embargo)\b")


_NUMERO = r"(?:\d+|un[ao]?|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)"
_INICIO_RECIENTE_RE = re.compile(
    rf"\b(?:hoy|ayer|anoche|esta\s+(?:manana|tarde|noche)|"
    rf"hace\s+{_NUMERO}\s+(?:horas?|minutos?)|"
    r"hace\s+(?:[1-7]|un[ao]?|dos|tres|cuatro|cinco|seis|siete)\s+dias?|"
    r"desde\s+el\s+(?:lunes|martes|miercoles|jueves|viernes|sabado|domingo)|"
    r"desde\s+hace\s+unas\s+horas)\b"
)
_OTRO_HECHO_RE = re.compile(
    r",\s*|\b(?:y|e|mientras|aunque)\s+"
    r"(?=(?:(?:desde|hoy|ayer|anoche|esta|hace)\b.*?\s+)?"
    r"(?:(?:tiene|presenta|refiere|comenzo|inicio)\s+)?"
    r"(?:cefalea|dolor|revision|control|consulta|nauseas?|vomitos?|fiebre)\b)"
)
_REVISION_RE = re.compile(r"\b(?:revision|control|consulta)\b")


def _inicio_reciente_propio(texto: str, inicio: int, fin: int) -> bool:
    from app.correlaciones.texto import _is_match_negated

    cortes = list(_CORTE_RE.finditer(texto)) + list(_OTRO_HECHO_RE.finditer(texto))
    izq = max((c.end() for c in cortes if c.end() <= inicio), default=0)
    der = min((c.start() for c in cortes if c.start() >= fin), default=len(texto))
    if _REVISION_RE.search(texto, izq, der):
        return False
    return any(not _is_match_negated(texto, t.start(), t.end())
               for t in _INICIO_RECIENTE_RE.finditer(texto, izq, der))


def perdidas_subitas(texto: str):
    """Devuelve spans de la pérdida; el negador nunca queda dentro del match.

    Se usa el matcher de negación vigente tanto para pérdida como calificador.
    El inicio reciente propio accede a la misma ruta de evaluación.
    """
    from app.correlaciones.texto import _is_match_negated

    cortes = list(_CORTE_RE.finditer(texto))
    for m in _PERDIDA_RE.finditer(texto):
        inicio = max((c.end() for c in cortes if c.end() <= m.start()), default=0)
        fin = min((c.start() for c in cortes if c.start() >= m.end()), default=len(texto))
        if (not _is_match_negated(texto, m.start(), m.end()) and any(
            not _is_match_negated(texto, b.start(), b.end())
            for b in BRUSQUEDAD_RE.finditer(texto, inicio, fin)
        ) or (not _is_match_negated(texto, m.start(), m.end())
              and _inicio_reciente_propio(texto, m.start(), m.end()))):
            yield m
