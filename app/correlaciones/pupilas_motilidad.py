"""Dominio: pupilas y motilidad ocular (3 correlaciones).

horner_o_tercer_par_sospecha (combinaciones pupilares/motoras con ptosis), pupilas_alteradas
(anisocoria, DPAR, midriasis...) y motilidad_alterada (limitacion, nistagmo,
paresia...). #12 comparte ocurrencias con #13 y solo suprime hallazgos redundantes.
"""
from __future__ import annotations

import functools
import re
from dataclasses import dataclass, replace

from app.correlaciones.base import _memoize_cond
from app.correlaciones.fondo_de_ojo import _cond_glaucoma_asimetrico
from app.correlaciones.hechos_textuales import _certeza_local, _es_hipotetico, _sujeto_es_paciente
from app.correlaciones.texto import (
    _ANTIGUO_RE,
    _CAMBIO_DEICTICO_RE,
    _CAMBIO_RE,
    _EYE_MARKERS_RE,
    _compiled_keyword,
    _contains_keyword,
    _dedupe,
    _join_hallazgos,
    _is_match_negated,
    _keyword_matches,
    _normalize_text,
)
from app.schemas import ImpresionClinicaRequest

_EYE_MARKERS_EXPLICIT_RE = re.compile(
    r"\b(ao|ambos ojos|bilateral|bilaterales|bilateralmente|od|oi|ojo derecho|ojo izquierdo|derecho|derecha|izquierdo|izquierda)\b"
)
_AO_MARKERS_RE = re.compile(r"\b(ao|ambos ojos|bilateral|bilaterales|bilateralmente)\b")
_OD_MARKERS_RE = re.compile(r"\b(od|ojo derecho|derecho|derecha)\b")
_OI_MARKERS_RE = re.compile(r"\b(oi|ojo izquierdo|izquierdo|izquierda)\b")

_KEYWORDS_PUPILAS = {
    "anisocoria": "anisocoria",
    "midriasis": "midriasis",
    "miosis": "miosis",
    "dpar": "defecto pupilar aferente relativo",
    "rapd": "defecto pupilar aferente relativo",
    "defecto pupilar aferente": "defecto pupilar aferente relativo",
    "pupila de marcus gunn": "defecto pupilar aferente relativo",
    "marcus gunn pupilar": "defecto pupilar aferente relativo",
    "pupila marcus gunn": "defecto pupilar aferente relativo",
    "signo de marcus gunn": "defecto pupilar aferente relativo",
    "no reactivo": "pupila no reactiva",
    "no reactiva": "pupila no reactiva",
    "arreactiva": "pupila no reactiva",
    "pupila fija": "pupila no reactiva",
    "hiporreactiva": "respuesta pupilar disminuida",
    "irregular": "pupila irregular",
    "discoria": "discoria",
    "corectopia": "corectopia",
    "pupila tonica": "pupila tonica",
    "adie": "pupila tonica de adie",
    "reflejo ausente": "respuesta pupilar ausente",
    "reflejos ausentes": "respuesta pupilar ausente",
    "reflejo pupilar ausente": "respuesta pupilar ausente",
    "sin reflejo pupilar": "respuesta pupilar ausente",
    "ausencia de reflejo pupilar": "respuesta pupilar ausente",
}
# Ausencia de una funcion normal (fotomotor, consensual, acomodativo): es un
# hallazgo positivo, distinto de la ausencia de una anomalia y de DPAR. Cada
# funcion conserva su nombre exacto; "reflejo corneal ausente" no es pupilar.
for _etiqueta, _cortas, _sustantivos in (
    ("respuesta fotomotora ausente", ("fotomotor ausente", "fotomotor abolido"),
     ("reflejo fotomotor", "respuesta fotomotora")),
    ("respuesta consensual ausente", ("consensual ausente", "consensual abolido"),
     ("reflejo consensual", "respuesta consensual")),
    ("respuesta acomodativa ausente", ("acomodativo ausente",),
     ("reflejo acomodativo", "respuesta acomodativa")),
):
    for _forma in _cortas:
        _KEYWORDS_PUPILAS[_forma] = _etiqueta
    for _sustantivo in _sustantivos:
        for _forma in (f"{_sustantivo} ausente", f"{_sustantivo} abolido", f"{_sustantivo} abolida",
                       f"sin {_sustantivo}", f"no hay {_sustantivo}", f"ausencia de {_sustantivo}"):
            _KEYWORDS_PUPILAS[_forma] = _etiqueta
for _forma in ("sin respuesta a la luz", "no hay respuesta a la luz", "sin reaccion a la luz",
               "no reacciona a la luz", "no responde a la luz"):
    _KEYWORDS_PUPILAS[_forma] = "respuesta fotomotora ausente"
for _forma in ("fotomotor y consensual ausentes", "fotomotor y consensual abolidos",
               "reflejos fotomotor y consensual ausentes"):
    _KEYWORDS_PUPILAS[_forma] = "respuestas fotomotora y consensual ausentes"
_REACCION_PUPILAR = frozenset({
    "pupila no reactiva", "respuesta pupilar disminuida", "respuesta pupilar ausente",
    "respuesta fotomotora ausente", "respuesta consensual ausente", "respuesta acomodativa ausente",
    "respuestas fotomotora y consensual ausentes",
})
_KEYWORDS_PTOSIS = ("ptosis", "blefaroptosis", "caida del parpado", "parpado caido")
_KEYWORDS_PTOSIS_CONGENITA_O_CRONICA = (
    "congenit", "de nacimiento", "desde nin", "desde la infancia",
    "cronica", "cronico", "antigua", "antiguo", "larga evolucion",
    "senil", "aponeurotic", "involutiv",
)
_KEYWORDS_ANISOCORIA_BENIGNA = (
    "anisocoria fisiologica", "anisocoria benigna", "anisocoria simple",
    "anisocoria esencial",
)
# Calificadores que indican midriasis/miosis inducida (no un hallazgo patologico):
# examen bajo dilatacion o efecto de farmacos.
_KEYWORDS_PUPILA_FARMACOLOGICA = (
    "farmacologic", "post dilatacion", "post-dilatacion", "bajo dilatacion",
    "midriatic", "dilatacion pupilar", "cicloplej", "tropicamida", "fenilefrina",
    "pilocarpina",
)


@dataclass(frozen=True)
class _HallazgoOcular:
    """Una ocurrencia; los offsets corresponden al campo normalizado.

    Mantener signo, ojo y contexto juntos impide recuperar un ojo desde una
    ocurrencia negada o farmacologica al renderizar una combinacion distinta.
    """

    hallazgo: str
    inicio: int
    fin: int
    ojo: str | None
    afirmado: bool
    explicacion: str | None
    evolucion: str
    origen: str
    contexto: str
    evolucion_origen: str | None = None
    incierto: bool = False
    por_descartar: bool = False
    certeza: str | None = None


# La cronologia (_CAMBIO_RE, _CAMBIO_DEICTICO_RE, _ANTIGUO_RE) vive en texto.py:
# la comparten pupilas, motilidad, campos, Amsler y la integracion A2 de #8.
_FARMACO_PUPILAR = r"(?:tropicamida|fenilefrina|atropina|pilocarpina|ciclopentolato|homatropina|midriatic\w*|colirio\w*)"
_EXPLICACION_PUPILAR_RE = re.compile(
    r"\b(?:farmacologic\w*|(?:post[- ]|bajo )dilatacion|cicloplej\w*|"
    r"(?:por|tras|debido a|secundari[oa] a|inducid[oa] por|efecto de) "
    r"(?:la |el |uso de |aplicacion de |instilacion de |gotas de )*" + _FARMACO_PUPILAR + r"|"
    + _FARMACO_PUPILAR + r" (?:instilad|aplicad|colocad|administrad)\w*|"
    r"(?:instilacion|aplicacion|gotas?) de " + _FARMACO_PUPILAR + r"|"
    r"dilatad[oa]s? con " + _FARMACO_PUPILAR + r")\b"
)
# Formulas que dejan el hallazgo por confirmar: no es una medicion firme.
_DUDA_RE = re.compile(
    r"\b(?:dudos[oa]|no concluyente|no confirmad[oa]|por confirmar|posible|probable|"
    r"presunt[oa]|sospecha(?: de)?)\b"
)
_POR_DESCARTAR_RE = re.compile(r"\b(?:a descartar|para descartar|descartar|descarte de)\b")
_EXPLICACION_PTOSIS_RE = re.compile(
    r"\b(?:mecanic\w*|(?:por|secundaria a|debida a) (?:un |una |el |la )*"
    r"(?:edema|picadura|trauma palpebral|masa palpebral))\b"
)
_TAMANO_PUPILAR = frozenset({"anisocoria", "midriasis", "miosis"})
_PTOSIS_MAP = {k: "ptosis" for k in _KEYWORDS_PTOSIS}
_MOTOR_MAP = {
    "limitacion": "limitacion de la motilidad",
    "ducciones limitadas": "limitacion de ducciones",
    "versiones limitadas": "limitacion de versiones",
    "movimientos oculares limitados": "limitacion de la motilidad",
    "oftalmoparesia": "oftalmoparesia descrita",
    "oftalmoplejia": "oftalmoplejia descrita",
    "oftalmoplegia": "oftalmoplejia descrita",
}
_SINTOMAS_EPISODIO = {
    "dolor cervical": "dolor cervical referido",
    "dolor de cuello": "dolor cervical referido",
    "dolor ocular": "dolor ocular referido",
    "cefalea": "cefalea referida",
    "diplopia": "diplopia referida",
    "vision doble": "diplopia referida",
    "traumatismo craneal": "traumatismo craneal referido",
    "trauma cervical": "trauma cervical referido",
    "debilidad de extremidades": "debilidad de extremidades referida",
    "disartria": "disartria referida",
    "perdida visual": "perdida visual referida",
    "perdida de vision": "perdida visual referida",
}


_NEGACION_DE_EXPLICACION_RE = re.compile(
    r"\bno\s+(?:es\s+)?(?:fisiologic\w*|farmacologic\w*|congenit\w*)\b"
)


def _afirmado_local(texto: str, inicio: int, fin: int) -> bool:
    # El marcador del propio ojo no rompe una negacion ("sin miosis OD").
    sin_ojos = _EYE_MARKERS_EXPLICIT_RE.sub(lambda m: " " * len(m[0]), texto)

    # "No fisiologico" niega la explicacion, no lo que sigue ("no fisiologico de
    # nueva aparicion"). Se ignora salvo que el propio fragmento evaluado este
    # dentro de esa frase (para que "no congenita" siga negando "congenita").
    def enmascarar(m: re.Match) -> str:
        return m[0] if m.start() < fin and m.end() > inicio else " " * len(m[0])

    sin_ojos = _NEGACION_DE_EXPLICACION_RE.sub(enmascarar, sin_ojos)
    return not _is_match_negated(sin_ojos, inicio, fin)


def _signo_afirmado(texto: str, inicio: int, fin: int) -> bool:
    # "Anisocoria no fisiologica" niega la explicacion, no la anisocoria.
    # Conservar offsets para evaluar precisamente esta ocurrencia.
    assertion = re.sub(r"\bno\s+(?:es\s+)?(?:fisiologic\w*|farmacologic\w*|congenit\w*)\b",
                       lambda m: " " * len(m[0]), texto)
    cola = _EYE_MARKERS_EXPLICIT_RE.sub("", texto[fin:]).strip(" :")
    if re.match(r"(?:no\s+(?:se\s+)?(?:evaluo|evaluad\w*|exploro|explorad\w*)|sin evaluar)\b", cola):
        return False
    return _afirmado_local(assertion, inicio, fin)


def _calificador_afirmado(texto: str, patron: re.Pattern) -> bool:
    return any(_afirmado_local(texto, m.start(), m.end()) for m in patron.finditer(texto))


@functools.lru_cache(maxsize=32)
def _patron_ocurrencias(claves: tuple[str, ...]) -> re.Pattern:
    """Alternancia de palabras clave con plural opcional (regla T9 del motor de
    texto: cada palabra de 4+ letras admite s/es), un grupo nombrado por clave
    para recuperar la clave canonica de cada coincidencia."""
    def con_plurales(clave: str) -> str:
        return r"\s+".join(f"{re.escape(w)}(?:s|es)?" if len(w) >= 4 else re.escape(w)
                           for w in clave.split())
    return re.compile(r"\b(?:" + "|".join(
        f"(?P<k{i}>{con_plurales(k)})" for i, k in enumerate(claves)
    ) + r")\b")


# Claves que ya nombran a los dos ojos en plural ("reflejos ausentes").
_CLAVES_PLURALES = frozenset({
    "reflejos ausentes", "fotomotor y consensual ausentes", "fotomotor y consensual abolidos",
    "reflejos fotomotor y consensual ausentes",
})


_OD_ESTRICTO_RE = re.compile(r"\b(od|ojo derecho)\b")
_OI_ESTRICTO_RE = re.compile(r"\b(oi|ojo izquierdo)\b")

# Marca de normalidad o negacion del tramo del otro ojo («Limitacion OD, OI normal»).
# «sin cambios/variacion...» y «no normal/fisiologico...» no la constituyen.
_NORMALIDAD_OJO_RE = re.compile(
    r"(?<!\bno )\b(?:normal\w*|transparent\w*|clar[oa]s?|limpi[oa]s?|conservad[oa]s?|san[oa]s?|"
    r"fisiologic[oa]s?|integr[oa]s?|dentro de limites)\b"
    r"|\b(?:ausent\w*|negativ[oa]s?|libre)\b"
    r"|\bsin\b(?!\s+(?:cambio|variacion|progresion|empeoramiento))"
    r"|\bno\b(?!\s+(?:normal|fisiologic|conservad|transparent|clar|integr))")

# Estos nombres delimitan episodios clínicos aunque un extractor especializado
# no los incluya en su mapa. Una fecha del dolor no fecha una metamorfopsia.
_OTRO_EVENTO_RE = re.compile(
    r"\b(?:dolor(?: de cabeza| ocular| cervical| intenso)?|cefalea|diplopia|vision doble|"
    r"perdida (?:visual|de vision)|disminucion visual|vision (?:reducida|disminuida)|"
    r"metamorfopsia|micropsia|macropsia|distorsion|escotoma|debilidad|nistagmo|"
    r"ptosis|miosis|midriasis|anisocoria|halos|nausea|vomito|vertigo|inestabilidad)\b")


def _contexto_temporal(contexto: str, inicio: int, fin: int) -> str:
    """Recorta un evento independiente posterior; conserva calificadores propios."""
    cortes = list(re.finditer(r",|\b(?:y|e|pero|mientras|ahora|con|sin|ni)\b", contexto[fin:]))
    for corte in cortes:
        cola = contexto[fin + corte.end():]
        if _OTRO_EVENTO_RE.match(cola.lstrip()):
            return contexto[:fin + corte.start()]
    return contexto


def _ojo_solo_en_tramos_normales(contexto: str, inicio: int, fin: int, ojo: str, lado_es_ojo: bool) -> bool:
    """El unico ojo nombrado esta en tramos vecinos (entre comas) marcados como normales/negados."""
    if lado_es_ojo:
        re_ojo = _OD_MARKERS_RE if ojo == "OD" else _OI_MARKERS_RE
    else:
        re_ojo = _OD_ESTRICTO_RE if ojo == "OD" else _OI_ESTRICTO_RE
    izquierda = contexto.rfind(",", 0, inicio) + 1
    derecha = contexto.find(",", fin)
    derecha = len(contexto) if derecha == -1 else derecha
    if re_ojo.search(contexto[izquierda:derecha]):
        return False
    con_ojo = [t for t in contexto[:izquierda].split(",") + contexto[derecha:].split(",") if re_ojo.search(t)]
    return bool(con_ojo) and all(_NORMALIDAD_OJO_RE.search(t) for t in con_ojo)


def _ojos_estrictos(texto: str) -> frozenset[str]:
    return frozenset(e for e, r in (("OD", _OD_ESTRICTO_RE), ("OI", _OI_ESTRICTO_RE)) if r.search(texto))


def _ojo_del_tramo(contexto: str, inicio: int, fin: int, lado_es_ojo: bool) -> str | None:
    """Ojo del tramo (entre comas) que contiene el hallazgo, cuando el otro ojo solo se
    nombra en tramos vecinos con marca de normalidad o negacion: «Catarata OD, cristalino
    OI transparente» pertenece solo a OD. Sin esa marca (elipsis «nuclear OD, cortical
    OI», «sin cambios en OI») no decide: el llamador conserva ambos ojos."""
    od_re = _OD_MARKERS_RE if lado_es_ojo else _OD_ESTRICTO_RE
    oi_re = _OI_MARKERS_RE if lado_es_ojo else _OI_ESTRICTO_RE
    izquierda = contexto.rfind(",", 0, inicio) + 1
    derecha = contexto.find(",", fin)
    derecha = len(contexto) if derecha == -1 else derecha
    tramo = contexto[izquierda:derecha]
    en_od, en_oi = bool(od_re.search(tramo)), bool(oi_re.search(tramo))
    if en_od == en_oi:
        return None
    otro = oi_re if en_od else od_re
    con_otro_ojo = [t for t in contexto[:izquierda].split(",") + contexto[derecha:].split(",") if otro.search(t)]
    if con_otro_ojo and all(_NORMALIDAD_OJO_RE.search(t) for t in con_otro_ojo):
        return "OD" if en_od else "OI"
    return None


def _ocurrencias_oculares(
    texto: str | None, mapa: dict[str, str], origen: str, *, lado_es_ojo: bool = True,
) -> list[_HallazgoOcular]:
    """Extraccion compartida por #12/#13; no atribuye etiologia ni ojo por tamano.

    Las clausulas y encabezados de ojo delimitan negacion y calificadores. La
    comparacion OD>OI queda indeterminada: no elige la pupila patologica.
    """
    norm = _normalize_text(texto)
    if not norm or not mapa:
        return []
    claves = tuple(sorted(mapa, key=len, reverse=True))
    patron = _patron_ocurrencias(claves)
    hallazgos: list[_HallazgoOcular] = []
    cortes = {0, len(norm)}
    for limite in re.finditer(r"[.;|!?]|\b(?:od|oi|ao)\s*:", norm):
        if len(limite[0]) > 1 and re.match(r"\s*(?:ausentes?|presentes?|positiv\w*|negativ\w*)\b", norm[limite.end():]):
            # "Miosis OD: ausente" es un valor del signo, no otro encabezado.
            continue
        cortes.add(limite.start())
        if len(limite[0]) == 1:
            cortes.add(limite.end())
    limites = sorted(cortes)
    for a, b in zip(limites, limites[1:]):
        clausula = norm[a:b]
        matches = list(patron.finditer(clausula))
        neg_izq: list[int] = []  # inicio del tramo sobre el que se evalua la negacion de cada ocurrencia
        for indice, match in enumerate(matches):
            izquierda, derecha = 0, len(clausula)
            if indice:
                previo = matches[indice - 1]
                tramo = clausula[previo.end():match.start()]
                conectores = list(re.finditer(r",|\b(?:y|e|pero|con|sin|ni|no)\b", tramo))
                if conectores:
                    conector = conectores[-1]
                    offset = conector.start() if conector[0] in ("sin", "ni", "no") else conector.end()
                    izquierda = previo.end() + offset
                else:
                    izquierda = match.start()
            if indice + 1 < len(matches):
                siguiente = matches[indice + 1]
                tramo = clausula[match.end():siguiente.start()]
                conector = re.search(r",|\b(?:y|e|pero|con)\b", tramo)
                derecha = match.end() + conector.start() if conector else siguiente.start()
            contexto = clausula[izquierda:derecha]
            inicio, fin = match.start() - izquierda, match.end() - izquierda
            # «Sin cefalea y diplopia», «sin DPAR o anisocoria»: una lista unida por y/e/o/ni sigue
            # bajo el mismo negador. No se hereda ante coma, pero/con/sin/no ni entre ojos distintos.
            neg_ini = izquierda
            if indice:
                tramo_lista = clausula[matches[indice - 1].end():match.start()]
                if (re.search(r"\b(?:y|e|o|ni)\b", tramo_lista)
                        and not re.search(r",|\b(?:pero|con|sin|no|aunque|mientras|ahora|sino)\b", tramo_lista)):
                    ojos_previos = _ojos_estrictos(clausula[neg_izq[indice - 1]:match.start()])
                    ojos_actuales = _ojos_estrictos(contexto)
                    if not (ojos_previos and ojos_actuales and ojos_previos != ojos_actuales):
                        neg_ini = neg_izq[indice - 1]
            neg_izq.append(neg_ini)
            # `lado_es_ojo=False`: "derecha/izquierda" nombran un hemicampo, no un ojo.
            tiene_od = bool((_OD_MARKERS_RE if lado_es_ojo else _OD_ESTRICTO_RE).search(contexto))
            tiene_oi = bool((_OI_MARKERS_RE if lado_es_ojo else _OI_ESTRICTO_RE).search(contexto))
            ojo = ("AMBOS" if tiene_od and tiene_oi else "AO" if _AO_MARKERS_RE.search(contexto)
                   else "OD" if tiene_od else "OI" if tiene_oi else None)
            if ojo == "AMBOS":
                ojo = _ojo_del_tramo(contexto, inicio, fin, lado_es_ojo) or ojo
            elif ojo in ("OD", "OI") and _ojo_solo_en_tramos_normales(contexto, inicio, fin, ojo, lado_es_ojo):
                # «diplopia desde hoy, OD normal»: el OD normal no localiza la diplopia.
                ojo = None
            clave = claves[int(match.lastgroup[1:])]
            hallazgo = mapa[clave]
            # «<ojo> con <hallazgo>» liga ese ojo al hallazgo, aunque haya otro ojo antes
            # («Sin alteracion OD OI con metamorfopsia» -> OI). Solo cuando el hallazgo
            # no lleva un ojo propio detras.
            if ojo in ("AMBOS", None):
                previo_ojo = re.search(r"\b(od|oi|ojo derecho|ojo izquierdo)\s+con\s*$",
                                       contexto[:inicio] if ojo == "AMBOS" else clausula[:izquierda].rstrip())
                if previo_ojo and (ojo is None or not (_OD_ESTRICTO_RE if previo_ojo[1] in ("od", "ojo derecho")
                                                        else _OI_ESTRICTO_RE).search(contexto[fin:])):
                    ojo = "OD" if previo_ojo[1] in ("od", "ojo derecho") else "OI"
            # Un encabezado puede compartir varios hallazgos del mismo ojo.
            if ojo is None:
                encabezado = re.match(r"\s*(od|oi|ao)\s*:", clausula)
                if encabezado:
                    ojo = encabezado[1].upper()
                elif (indice and origen == "motivo_consulta" and hallazgos and hallazgos[-1].afirmado
                      and hallazgos[-1].ojo in ("OD", "OI")
                      and re.search(r"\by\b", clausula[matches[indice - 1].end():match.start()])):
                    # Sintomas coordinados del episodio: "dolor OI y diplopia".
                    ojo = hallazgos[-1].ojo
            if (ojo is None and origen == "reflejos_pupilares" and hallazgo != "anisocoria"
                    and (match[0] != clave or clave in _CLAVES_PLURALES)):
                # Plural sin ojo explicito ("pupilas arreactivas"): ambos ojos.
                # La anisocoria es una diferencia entre ojos, no un signo bilateral.
                ojo = "AO"
            temporal = _contexto_temporal(contexto, inicio, fin)
            cambio = _calificador_afirmado(temporal, _CAMBIO_RE)
            antiguo = _calificador_afirmado(temporal, _ANTIGUO_RE)
            if re.search(r"\b(?:conocid\w*|cirugia)\b", temporal) and re.search(r"\b(?:sin cambios|estable)\b", temporal):
                antiguo = True
            # "hoy/ayer" solo fecha un signo cuando nada lo declara antiguo.
            cambio = cambio or (not antiguo and _calificador_afirmado(temporal, _CAMBIO_DEICTICO_RE))
            explicacion = None
            if hallazgo in _TAMANO_PUPILAR or hallazgo in _REACCION_PUPILAR:
                if _calificador_afirmado(contexto, _EXPLICACION_PUPILAR_RE):
                    explicacion = "efecto farmacologico descrito"
                elif hallazgo in _TAMANO_PUPILAR and _calificador_afirmado(
                    contexto, re.compile(r"\b(?:fisiologic\w*|benign\w*|esencial|simple)\b")
                ):
                    explicacion = "variante fisiologica descrita"
                elif ((hallazgo == "midriasis" and ojo == "AO" and re.search(r"\b(?:en|con la) oscuridad\b", contexto))
                      or (hallazgo == "miosis" and ojo == "AO" and re.search(r"\bcon la luz\b", contexto))):
                    explicacion = "adaptacion luminosa descrita"
            elif hallazgo == "ptosis" and _calificador_afirmado(contexto, _EXPLICACION_PTOSIS_RE):
                explicacion = "explicacion palpebral local descrita"
            # "descartar DPAR" o "DPAR?" plantean el hallazgo, no lo miden.
            # Una clausula que termina en "?" plantea todo su contenido, no lo mide.
            certeza = _certeza_local(norm, a + match.start(), a + match.end())
            por_descartar = (certeza == "a descartar" or bool(_POR_DESCARTAR_RE.search(contexto[:inicio]))
                             or norm[b:b + 1] == "?")
            hallazgos.append(_HallazgoOcular(
                hallazgo, a + match.start(), a + match.end(), ojo,
                (_signo_afirmado(clausula[neg_ini:derecha], match.start() - neg_ini, match.end() - neg_ini)
                 and _sujeto_es_paciente(norm, a + match.start(), a + match.end())
                 and not _es_hipotetico(norm, a + match.start(), a + match.end())), explicacion,
                "cambio reciente" if cambio else "antigua" if antiguo else "indeterminada",
                origen, contexto,
                incierto=por_descartar or certeza is not None or _calificador_afirmado(contexto, _DUDA_RE),
                por_descartar=por_descartar,
                certeza=certeza,
            ))
    return hallazgos


def _pupilas_ocurrencias(clinica) -> list[_HallazgoOcular]:
    if clinica is None:
        return []
    return _hallazgos_pupilares(clinica.reflejos_pupilares)


def _hallazgos_pupilares(texto: str | None) -> list[_HallazgoOcular]:
    mapa = dict(_KEYWORDS_PUPILAS)
    mapa["marcus gunn"] = "defecto pupilar aferente relativo"
    mapa["pupila tonica de adie"] = "pupila tonica de adie"
    norm = _normalize_text(texto)
    hallazgos = []
    for h in _ocurrencias_oculares(texto, mapa, "reflejos_pupilares"):
        if not h.afirmado or h.explicacion is not None:
            continue
        if norm[h.inicio:h.fin] == "marcus gunn" and any(
            _calificador_afirmado(h.contexto, re.compile(re.escape(t))) for t in _TOKENS_MANDIBULOPALPEBRAL
        ):
            continue
        if h.hallazgo == "pupila irregular":
            if re.search(r"\b(?:respuesta|reflejo)\b[^.;]*\birregular\b", h.contexto):
                h = replace(h, hallazgo="respuesta pupilar irregular",
                            incierto=h.incierto or "distraccion" in h.contexto)
            elif not re.search(r"\b(?:pupilas?|pupilares?|iris|contornos?|bordes?)\b", h.contexto):
                continue
        # Historia local conocida y estable: no fabricar una nueva indicacion.
        if h.evolucion == "antigua" and h.hallazgo != "defecto pupilar aferente relativo" and (
            re.search(r"\b(?:cirugia|conocid\w*)\b", h.contexto)
            and re.search(r"\b(?:sin cambios|estable)\b", h.contexto)
        ):
            continue
        if hallazgos and h.hallazgo == hallazgos[-1].hallazgo and re.fullmatch(
            r"\s*[:=() -]*\s*", norm[hallazgos[-1].fin:h.inicio]
        ):
            # Chip seguido de su expansion ("Marcus Gunn: DPAR OD") es un
            # mismo dato; preferir la ocurrencia que conserva la lateralidad.
            if hallazgos[-1].ojo is None or hallazgos[-1].ojo == h.ojo:
                hallazgos.pop()
        hallazgos.append(h)
    return hallazgos


def _clause_has_qualifier(
    text_norm: str,
    match_start: int,
    match_end: int,
    qualifiers: tuple[str, ...],
) -> bool:
    """Verifica si en la clausula local del match existe algun calificador,
    sin que medie un marcador de cambio de ojo entre ellos."""
    clause_start = max([text_norm.rfind(sep, 0, match_start) for sep in ".;:|\n"] or [-1]) + 1
    ends = [pos for pos in [text_norm.find(sep, match_end) for sep in ".;:|\n"] if pos != -1]
    clause_end = min(ends) if ends else len(text_norm)

    clause_before = text_norm[clause_start:match_start]
    clause_after = text_norm[match_end:clause_end]

    # Revisar calificadores antes del match (sin cambio de ojo intermedio)
    for q in qualifiers:
        pos = clause_before.rfind(q)
        if pos != -1:
            intervening = clause_before[pos + len(q):]
            if not _EYE_MARKERS_RE.search(intervening):
                return True

    # Revisar calificadores despues del match (sin cambio de ojo intermedio)
    for q in qualifiers:
        pos = clause_after.find(q)
        if pos != -1:
            intervening = clause_after[:pos]
            if not _EYE_MARKERS_RE.search(intervening):
                return True

    return False


def _extract_finding_eye(
    text: str | None,
    finding_keywords: tuple[str, ...] | list[str],
) -> str | None:
    """Extrae el ojo ('OD', 'OI', 'AO', 'AMBOS', o None) al que corresponde
    el hallazgo clinico en el texto. Si el texto compara ambos ojos (ej. 'OD > OI')
    o no especifica lateralidad, devuelve 'AMBOS' o None."""
    if any(k in _TOKENS_DPAR_EXPLICITOS or k == "marcus gunn" for k in finding_keywords):
        lados = {h.ojo for h in _hallazgos_pupilares(text)
                 if h.hallazgo == "defecto pupilar aferente relativo" and not h.incierto}
        return next(iter(lados)) if len(lados) == 1 else "AMBOS" if lados else None
    if not text:
        return None
    norm = _normalize_text(text)
    if not norm:
        return None

    for kw in finding_keywords:
        for m in _compiled_keyword(kw).finditer(norm):
            if not _keyword_matches(norm, kw, allow_negation_window=True):
                continue

            # Delimitar la clausula local del match
            clause_start = max([norm.rfind(sep, 0, m.start()) for sep in ".;:|\n"] or [-1]) + 1
            ends = [pos for pos in [norm.find(sep, m.end()) for sep in ".;:|\n"] if pos != -1]
            clause_end = min(ends) if ends else len(norm)
            clause_text = norm[clause_start:clause_end]

            # Comparacion explicita entre ojos (ej. 'od > oi', 'od mayor que oi')
            if (">" in clause_text or "<" in clause_text or "mayor" in clause_text or "menor" in clause_text) and (
                _OD_MARKERS_RE.search(clause_text) and _OI_MARKERS_RE.search(clause_text)
            ):
                return "AMBOS"

            # Marcador bilateral explicito en la clausula
            if _AO_MARKERS_RE.search(clause_text):
                return "AO"

            # Marcadores especificos en la clausula
            has_od = bool(_OD_MARKERS_RE.search(clause_text))
            has_oi = bool(_OI_MARKERS_RE.search(clause_text))
            if has_od and not has_oi:
                return "OD"
            if has_oi and not has_od:
                return "OI"
            if has_od and has_oi:
                return "AMBOS"

            # Buscar marcador anterior mas cercano si la clausula no tenia marcador
            prev_markers = list(_EYE_MARKERS_EXPLICIT_RE.finditer(norm[:m.start()]))
            if prev_markers:
                last_marker = prev_markers[-1].group(1)
                if last_marker in ("ao", "ambos ojos", "bilateral", "bilaterales"):
                    return "AO"
                if last_marker in ("od", "ojo derecho", "derecho", "derecha"):
                    return "OD"
                if last_marker in ("oi", "ojo izquierdo", "izquierdo", "izquierda"):
                    return "OI"

            # Buscar marcador posterior dentro del mismo enunciado (ej. "marcus gunn: positivo od", "dpar: od")
            next_boundary = min([pos for pos in [norm.find(sep, m.end()) for sep in ".\n"] if pos != -1] or [len(norm)])
            next_markers = list(_EYE_MARKERS_EXPLICIT_RE.finditer(norm[m.end():next_boundary]))
            if next_markers:
                first_marker = next_markers[0].group(1)
                if first_marker in ("ao", "ambos ojos", "bilateral", "bilaterales"):
                    return "AO"
                if first_marker in ("od", "ojo derecho", "derecho", "derecha"):
                    return "OD"
                if first_marker in ("oi", "ojo izquierdo", "izquierdo", "izquierda"):
                    return "OI"

    return None


def _son_hallazgos_contralaterales(ojo1: str | None, ojo2: str | None) -> bool:
    """Determina si dos hallazgos estan en ojos estrictamente opuestos
    (uno en OD y el otro en OI), lo que excluye un sindrome neurooftalmico
    ipsilateral como Horner o paresia del III par."""
    if not ojo1 or not ojo2:
        return False
    o1, o2 = ojo1.upper(), ojo2.upper()
    return (o1 == "OD" and o2 == "OI") or (o1 == "OI" and o2 == "OD")


def _es_ptosis_congenita_o_cronica(text: str | None) -> bool:
    """Determina si las manifestaciones de ptosis palpebral en el texto estan
    identificadas como congenitas, seniles, aponeuroticas o cronicas de larga evolucion,
    lo que descarta la presentacion de una emergencia neurooftalmica aguda."""
    if not text:
        return False
    norm = _normalize_text(text)
    if not norm:
        return False
    matches_ptosis = []
    for kw in _KEYWORDS_PTOSIS:
        for m in _compiled_keyword(kw).finditer(norm):
            if _keyword_matches(norm, kw, allow_negation_window=True):
                matches_ptosis.append(m)
    if not matches_ptosis:
        return False
    return all(
        _clause_has_qualifier(norm, m.start(), m.end(), _KEYWORDS_PTOSIS_CONGENITA_O_CRONICA)
        for m in matches_ptosis
    )


_TOKENS_MANDIBULOPALPEBRAL: tuple[str, ...] = (
    "mandibulopalpebral",
    "mandibulo-palpebral",
    "mandibulo palpebral",
    "sincinesia",
    "mandibula",
    "jaw-winking",
    "jaw winking",
    "fenomeno de marcus gunn",
    "fenomeno marcus gunn",
)

_TOKENS_DPAR_EXPLICITOS: tuple[str, ...] = (
    "dpar",
    "rapd",
    "defecto pupilar aferente",
    "pupila de marcus gunn",
    "marcus gunn pupilar",
    "pupila marcus gunn",
    "signo de marcus gunn",
)


def _hay_dpar(texto_pupilas: str | None) -> bool:
    """DPAR afirmado: tokens explicitos (dpar, rapd, defecto pupilar aferente,
    pupila/signo de marcus gunn) o el chip 'Marcus Gunn' de la UI, salvo que el
    campo mencione el fenomeno mandibulopalpebral."""
    return any(h.hallazgo == "defecto pupilar aferente relativo" and not h.incierto
               for h in _hallazgos_pupilares(texto_pupilas))


def _pupilas_hallazgos(clinica) -> list[str]:
    """Compatibilidad para consumidores: etiquetas del mismo conjunto filtrado."""
    return _dedupe([h.hallazgo for h in _pupilas_ocurrencias(clinica)])


@dataclass(frozen=True)
class _CombinacionPtosis:
    ptosis: _HallazgoOcular
    acompanante: _HallazgoOcular
    urgente: bool
    sintomas: tuple[str, ...]


_CONOCIDO_RE = re.compile(r"\b(?:conocid\w*|en seguimiento|previ[oa]s?|antecedente)\b")
_ESTABLE_RE = re.compile(
    r"\b(?:estable|sin cambios|sin progresion|sin diplopia nueva|sin sintomas nuevos|en seguimiento|controlad\w*)\b")
_CAMBIO_DECLARADO_RE = re.compile(r"\b(?:empeor\w*|agrav\w*|progres\w*|aument\w*|nuev[oa]s?|recientes?)\b")


def _conocido_y_estable(h: _HallazgoOcular) -> bool:
    """Diagnostico o secuela ya conocida: contexto, no un hallazgo nuevo.

    Basta que el registro lo presente como conocido/en seguimiento/antecedente
    (o antiguo y estable) y no declare cambio; un empeoramiento, una progresion
    o un signo nuevo en la misma clausula lo devuelven a hallazgo actual.
    """
    if h.evolucion == "cambio reciente" or _calificador_afirmado(h.contexto, _CAMBIO_DECLARADO_RE):
        return False
    return bool(_CONOCIDO_RE.search(h.contexto)) or (
        h.evolucion == "antigua" and bool(_ESTABLE_RE.search(h.contexto)))


def _cronologia_de_clausula(sintomas: list[_HallazgoOcular], motivo: str | None) -> list[_HallazgoOcular]:
    """Una expresion temporal ("... desde hoy") fecha los sintomas coordinados de
    su clausula: en «vertigo e inestabilidad desde hoy» ambos son recientes.

    Solo completa los sintomas sin fecha propia; uno declarado antiguo o con
    su propia expresion temporal no cambia, y otra oracion no lo contagia.
    """
    norm = _normalize_text(motivo)
    resultado = []
    for s in sintomas:
        if s.evolucion == "indeterminada" and s.afirmado:
            a = max(norm.rfind(sep, 0, s.inicio) for sep in ".;!?") + 1
            finales = [p for p in (norm.find(sep, s.fin) for sep in ".;!?") if p != -1]
            clausula = norm[a:min(finales) if finales else len(norm)]
            ajenos = [m for m in _OTRO_EVENTO_RE.finditer(clausula) if not any(
                h.inicio <= a + m.start() and a + m.end() <= h.fin for h in sintomas)]
            if ajenos:
                resultado.append(s)
                continue  # la fecha de un evento fuera del mapa no fecha este hallazgo
            if (not _calificador_afirmado(clausula, _ANTIGUO_RE)
                    and (_calificador_afirmado(clausula, _CAMBIO_RE)
                         or _calificador_afirmado(clausula, _CAMBIO_DEICTICO_RE))):
                s = replace(s, evolucion="cambio reciente", evolucion_origen="clausula")
        resultado.append(s)
    return resultado


def _sintomas_del_episodio(req: ImpresionClinicaRequest) -> list[_HallazgoOcular]:
    motivo = req.paciente.motivo_consulta if req.paciente else None
    sintomas = _cronologia_de_clausula(
        _ocurrencias_oculares(motivo, _SINTOMAS_EPISODIO, "motivo_consulta"), motivo)
    return [s for s in sintomas if s.afirmado and not s.incierto and not s.por_descartar
            and s.evolucion != "antigua"]


def _evolucion_en_motivo(
    hallazgos: list[_HallazgoOcular], req: ImpresionClinicaRequest, mapa: dict[str, str],
) -> list[_HallazgoOcular]:
    """El motivo puede fechar un signo ya descrito en la exploracion.

    Exige el nombre del signo y concordancia de ojo; una cefalea nueva no
    convierte por si sola una ptosis antigua en una ptosis nueva.
    """
    motivo = req.paciente.motivo_consulta if req.paciente else None
    historia = _ocurrencias_oculares(motivo, mapa, "motivo_consulta")
    resultado = []
    for h in hallazgos:
        compatibles = [m for m in historia if m.afirmado and not m.incierto and not m.por_descartar
                       and m.hallazgo == h.hallazgo
                       and m.evolucion == "cambio reciente"
                       and (m.ojo == h.ojo or (m.ojo is None and len(hallazgos) == 1))]
        if h.evolucion != "cambio reciente" and compatibles:
            reciente = compatibles[0]
            # Ante conflicto "congenita" vs "nueva", no sobrescribir la
            # historia; un empeoramiento explicito si documenta el cambio.
            empeora = _calificador_afirmado(reciente.contexto, re.compile(r"\b(?:empeor\w*|agrav\w*)\b"))
            if h.evolucion != "antigua" or empeora:
                h = replace(h, evolucion="cambio reciente", evolucion_origen="motivo_consulta",
                            contexto=h.contexto + "; " + reciente.contexto)
        resultado.append(h)
    return resultado


@_memoize_cond
def _combinaciones_ptosis(req: ImpresionClinicaRequest) -> tuple[_CombinacionPtosis, ...]:
    """Propietario del patron motor agudo con ptosis, incluso con chip normal.

    Urgencia y texto consumen estas mismas ocurrencias. La falta de lado deja
    una combinacion indeterminada, nunca un sindrome ipsilateral demostrado.
    """
    if req.clinica is None:
        return ()
    ptosis = [p for p in _ocurrencias_oculares(req.clinica.anexos_oculares, _PTOSIS_MAP, "anexos_oculares")
              if p.afirmado and p.explicacion is None]
    pupilas = [p for p in _pupilas_ocurrencias(req.clinica) if p.hallazgo in _TAMANO_PUPILAR]
    ptosis = _evolucion_en_motivo(ptosis, req, _PTOSIS_MAP)
    pupilas = _evolucion_en_motivo(pupilas, req, _KEYWORDS_PUPILAS)
    motores = [m for m in _ocurrencias_oculares(req.clinica.motilidad_ocular, _MOTOR_MAP, "motilidad_ocular")
               if m.afirmado]
    sintomas = _sintomas_del_episodio(req)
    combinaciones: list[_CombinacionPtosis] = []
    for pt in ptosis:
        asociados = [s for s in sintomas if not _son_hallazgos_contralaterales(s.ojo, pt.ojo)]
        # Cefalea/diplopia requieren cambio documentado; dolor cervical/ocular
        # actual puede justificar triage urgente sin inventar cuando empezo.
        alarmas = [s for s in asociados if s.evolucion == "cambio reciente"
                   or s.hallazgo in ("dolor cervical referido", "dolor ocular referido",
                                      "disartria referida", "debilidad de extremidades referida")]
        for pup in pupilas:
            if _son_hallazgos_contralaterales(pt.ojo, pup.ojo):
                continue
            reciente = "cambio reciente" in (pt.evolucion, pup.evolucion)
            if pt.evolucion == "antigua" and pup.evolucion == "indeterminada" and not alarmas:
                # Una ptosis antigua por si sola no fecha ni explica la pupila.
                continue
            estable = pt.evolucion == pup.evolucion == "antigua"
            urgente = reciente or bool(alarmas)
            if estable and not alarmas:
                urgente = False
            combinaciones.append(_CombinacionPtosis(pt, pup, urgente, tuple(
                _dedupe([s.hallazgo for s in asociados if reciente or s in alarmas])
            )))
        if pt.evolucion != "cambio reciente":
            continue
        for motor in motores:
            # Sin lado motor no se declara concordancia a partir de su ausencia.
            if pt.ojo not in ("OD", "OI") or motor.ojo != pt.ojo or motor.evolucion == "antigua":
                continue
            combinaciones.append(_CombinacionPtosis(pt, motor, True, tuple(_dedupe(
                [s.hallazgo for s in asociados]
            ))))
        for diplopia in asociados:
            if diplopia.hallazgo == "diplopia referida" and diplopia.evolucion == "cambio reciente":
                combinaciones.append(_CombinacionPtosis(pt, diplopia, True, ()))
    return tuple(combinaciones)


@_memoize_cond
def _cond_horner_o_tercer_par_sospecha(req: ImpresionClinicaRequest) -> bool:
    """ID historico: hallazgos pupilares/motores con ptosis, sin diagnosticar."""
    return bool(_combinaciones_ptosis(req))


def _describir_ocurrencia(hallazgo: _HallazgoOcular) -> str:
    texto = hallazgo.hallazgo
    if hallazgo.ojo in ("OD", "OI"):
        texto += f" {hallazgo.ojo}"
    elif hallazgo.ojo == "AO" and hallazgo.hallazgo != "anisocoria":
        # La anisocoria compara ambos ojos: "bilateral" no la describe.
        texto += " bilateral"
    if hallazgo.evolucion == "cambio reciente":
        texto += (" con empeoramiento documentado" if _calificador_afirmado(
            hallazgo.contexto, re.compile(r"\b(?:empeor\w*|agrav\w*)\b")
        ) else " de inicio reciente")
    elif hallazgo.evolucion == "antigua":
        texto += " de evolucion antigua descrita"
    return texto


def _describir_certeza(hallazgo: _HallazgoOcular) -> str:
    """Modalidad del registro, conservada al combinar signos independientes."""
    if hallazgo.por_descartar:
        return "sospecha por descartar de "
    if hallazgo.certeza in ("posible", "probable"):
        return hallazgo.certeza + " "
    if hallazgo.incierto:
        return "resultado no concluyente para "
    return ""


_MOVIMIENTO_RE = re.compile(
    r"\b(abduccion|aduccion|elevacion|depresion|supraduccion|infraduccion|supraversion|infraversion|"
    r"dextroversion|levoversion)\b")


def _describir_con_movimientos(hallazgo: _HallazgoOcular) -> str:
    """Una limitacion motora conserva QUE movimientos se registraron limitados."""
    texto = _describir_certeza(hallazgo) + _describir_ocurrencia(hallazgo)
    if hallazgo.origen.startswith("motilidad_ocular"):
        movimientos = _dedupe(_MOVIMIENTO_RE.findall(hallazgo.contexto))
        if movimientos:
            texto += f" ({_join_hallazgos(movimientos)})"
    return texto


def _texto_horner_o_tercer_par_sospecha(req: ImpresionClinicaRequest) -> str:
    combinaciones = _combinaciones_ptosis(req)
    signos = _dedupe([_describir_con_movimientos(h) for c in combinaciones for h in (c.ptosis, c.acompanante)])
    sintomas = _dedupe([s for c in combinaciones for s in c.sintomas
                       if not any(s in signo for signo in signos)])
    texto = f"se documentan {_join_hallazgos(signos)}"
    if sintomas:
        texto += f", con {_join_hallazgos(sintomas)}"
    if any(c.urgente for c in combinaciones):
        return (f"Hallazgo urgente: {texto}; esta combinacion amerita valoracion medica "
                "el mismo dia para estudiar su causa y evaluar la respuesta pupilar y la motilidad.")
    return (f"{texto[0].upper() + texto[1:]}; estos hallazgos ameritan valoracion especializada "
            "para caracterizar la respuesta pupilar, la motilidad y su causa. "
            "Verificar lateralidad y evolucion para decidir la prioridad de atencion.")


def _pupilas_independientes(req: ImpresionClinicaRequest) -> list[_HallazgoOcular]:
    # Suprimir solo ocurrencias ya descritas en #12; DPAR/forma/reaccion y
    # cualquier hallazgo del otro ojo siguen su propia ruta #13.
    cubiertos = {(c.acompanante.origen, c.acompanante.inicio, c.acompanante.fin) for c in _combinaciones_ptosis(req)
                 if c.acompanante.origen == "reflejos_pupilares"}
    hallazgos = _evolucion_en_motivo(_pupilas_ocurrencias(req.clinica), req, _KEYWORDS_PUPILAS)
    restantes = [h for h in hallazgos if (h.origen, h.inicio, h.fin) not in cubiertos]
    if _cond_glaucoma_asimetrico(req):
        ojo_cubierto = _extract_finding_eye(req.clinica.reflejos_pupilares, _TOKENS_DPAR_EXPLICITOS + ("marcus gunn",))
        restantes = [h for h in restantes if not (
            h.hallazgo == "defecto pupilar aferente relativo" and h.ojo == ojo_cubierto
            and not _prioridad_pupilar(h, req)
        )]
    return restantes


# Sintomas cuyo caracter de alarma no depende de que consten sus fechas (mismo
# criterio que #12): la falta de fecha no autoriza a diferir la valoracion.
_ALARMA_SIN_FECHA = ("dolor cervical referido", "dolor ocular referido",
                     "disartria referida", "debilidad de extremidades referida")


def _sintomas_alarma_pupilar(hallazgo: _HallazgoOcular, req: ImpresionClinicaRequest) -> list[str]:
    """Sintomas del motivo que elevan la prioridad de un signo pupilar."""
    asociados = [s for s in _sintomas_del_episodio(req)
                 if not _son_hallazgos_contralaterales(s.ojo, hallazgo.ojo)]
    if hallazgo.evolucion == "antigua":
        # Un signo antiguo no se reactiva por sintomas ajenos; si una perdida
        # visual nueva coexiste, esa alarma conserva su prioridad.
        return _dedupe([s.hallazgo for s in asociados
                        if s.hallazgo == "perdida visual referida" and s.evolucion == "cambio reciente"])
    return _dedupe([s.hallazgo for s in asociados if s.evolucion == "cambio reciente"
                    or s.hallazgo in _ALARMA_SIN_FECHA
                    or (hallazgo.evolucion == "cambio reciente" and s.hallazgo == "cefalea referida")])


def _prioridad_pupilar(hallazgo: _HallazgoOcular, req: ImpresionClinicaRequest) -> str:
    if _sintomas_alarma_pupilar(hallazgo, req):
        return "mismo dia"
    if hallazgo.evolucion == "cambio reciente" and not hallazgo.incierto:
        return "urgente"
    return ""


def _cond_pupilas_alteradas(req: ImpresionClinicaRequest) -> bool:
    """Hallazgos pupilares no cubiertos: conserva tipo, ojo e incertidumbre."""
    return bool(_pupilas_independientes(req))


def _texto_pupilas_alteradas(req: ImpresionClinicaRequest) -> str:
    ocurrencias = _pupilas_independientes(req)
    descripciones = _dedupe([
        ("sospecha por descartar de " if h.por_descartar
         else "resultado no concluyente para " if h.incierto else "") + _describir_ocurrencia(h)
        for h in ocurrencias
    ])
    hay_aferente = any(h.hallazgo == "defecto pupilar aferente relativo" for h in ocurrencias)
    prioridad = [_prioridad_pupilar(h, req) for h in ocurrencias]
    examen = "de retina y via visual aferente" if hay_aferente else "de la respuesta y anatomia pupilar"
    texto = "Se registra " + _join_hallazgos(descripciones)
    if any(prioridad):
        plazo = "el mismo dia" if "mismo dia" in prioridad else "urgente"
        texto = "Hallazgo urgente: " + texto[0].lower() + texto[1:]
        sintomas = _dedupe([s for h in ocurrencias for s in _sintomas_alarma_pupilar(h, req)])
        if sintomas:
            texto += f", con {_join_hallazgos(sintomas)}"
        texto += f"; amerita valoracion oftalmologica {plazo}, con evaluacion {examen} para establecer su causa."
    else:
        texto += f"; amerita valoracion oftalmologica {examen} para establecer su causa y revisar su evolucion y seguimiento."
        if any(h.evolucion == "indeterminada" for h in ocurrencias):
            texto += " Verificar inicio y sintomas asociados para decidir la prioridad de atencion."
    if any(h.incierto and not h.por_descartar for h in ocurrencias):
        texto += " Repetir y verificar la prueba por su resultado incierto."
    if any(h.por_descartar for h in ocurrencias):
        texto += " Completar la prueba pupilar para verificar o descartar el hallazgo."
    return texto


# motilidad_alterada (#14) vive en motilidad.py: comparte con este modulo el
# extractor por ocurrencia (_ocurrencias_oculares) y la ruta motora aguda de #12.
