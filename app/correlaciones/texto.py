"""Normalizacion de texto libre y matching de keywords con ventana de negacion.

Base de las correlaciones cualitativas (fondo, pupilas, anexos, campos, amsler,
cover test). No conoce dominios clinicos concretos: solo normaliza, compila y
busca keywords respetando negaciones por oracion.
"""
from __future__ import annotations

import functools
import re
import unicodedata

from app.schemas import ImpresionClinicaRequest

_NEGACIONES_PRE = (
    "sin ",
    "no ",
    "no se observa",
    "no se observan",
    "no se documenta",
    "no se detecta",
    "no se detectan",
    "no presenta",
    "sin evidencia",
    "negativ",
    "ausenc",
    "niega",
    "se descarta ",
    "sospecha descartada de ",
    "libre de",
    "tampoco ",
    "ningun ",
    "ninguno ",
    "ninguna ",
    "antecedente familiar de ",
    "antecedentes familiares de ",
    "historia familiar de ",
    "familiar con ",
    "familiares con ",
    "madre con ",
    "padre con ",
    "no se aprecia",
    "no se aprecian",
    "no se evidencia",
    "no se evidencian",
    "no se visualiza",
    "no se visualizan",
    "no se identifica",
    "no se identifican",
    "no se constata",
    "no se encuentra",
    "no se encuentran",
    "no muestra",
    "no muestran",
    "no hay",
    "no impresiona",
    # "ni" es siempre conjuncion negativa: "sin A ni B", "ni A ni B".
    "ni ",
)

_NEGACIONES_POST = (
    "ausente",
    "ausentes",
    "descartad",
    "negativ",
    "fisiologic",
    "normal",
    "normales",
    "libre",
    "libres",
    "ninguno",
    "ninguna",
    "ningun",
)

# El SaaS compone cover_test como "OD: Tipo [y Sub] | OI: Tipo [y Sub]"
# con tipo ∈ {Orto, Endo, Exo, Hiper, Hipo} y sub ∈ {Tropia, Foria}.
# Las correlaciones buscan keywords unidas (exoforia, endotropia, etc.);
# esta regex reconoce los pares para expandirlos a la forma unida.
_COVER_PAIR_RE = re.compile(r"\b(endo|exo|hiper|hipo)\s+y\s+(foria|tropia)\b")
# Parser estructurado del formato canonico por ojo. El sub es OPCIONAL en la UI
# (radios sin default): "OD: Endo | OI: Orto" es un estado real del formulario.
_COVER_EYE_RE = re.compile(
    r"\b(od|oi)\s*:\s*(orto|endo|exo|hiper|hipo)\b(?:\s+y\s+(foria|tropia))?"
)

# Cronologia compartida por las reglas cualitativas (pupilas, motilidad, campos,
# Amsler, integracion A2 de #8): una sola convencion de "reciente" y de "antiguo".
_DIAS_RECIENTES = r"(?:[1-9]|1[0-4]|un|una|uno|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez|once|doce|trece|catorce)"
_CAMBIO_RE = re.compile(
    r"\b(?:nuev[oa]s?|recientes?|subit[oa]s?|brusc[oa]s?|agud[oa]s?|"
    r"empeor\w*|agrav\w*|de inicio (?:hoy|ayer)|desde (?:hoy|ayer|anoche|esta manana)|"
    r"(?:inicio|aparicion) (?:hace|en las ultimas) \d+ (?:horas?|dias?)|"
    # Antiguedad relativa: horas o hasta dos semanas; meses/anos no son recientes.
    r"hace (?:\d+|un|una|unos|unas|algunos|algunas|pocos|pocas|varios|varias) (?:minutos?|horas?)|"
    rf"hace {_DIAS_RECIENTES} dias?|hace (?:unos|algunos|pocos|varios) dias|"
    r"hace (?:1|una|2|dos) semanas?|en las ultimas (?:\d+ )?(?:horas|dias)|ultimos dias)\b"
)
# Referencia deictica sin antiguedad explicita ("perdida visual hoy"): solo
# fecha el sintoma si nada lo declara antiguo.
_CAMBIO_DEICTICO_RE = re.compile(r"\b(?:hoy|ayer|anoche|esta (?:manana|noche|tarde))\b")
_ANTIGUO_RE = re.compile(
    r"\b(?:congenit\w*|de nacimiento|desde (?:nin\w*|la infancia)|"
    r"cronic\w*|antigu[oa]s?|larga evolucion|senil|aponeurotic\w*|involutiv\w*|"
    r"(?:desde )?hace (?:\d+|diez|varios|muchos) anos)\b"
)

_WHITESPACE_RE = re.compile(r"[^\S\n]+")

# Keywords que DEBEN coincidir como palabra completa. Son abreviaturas clinicas
# cortas que, con el matching por substring por defecto, aparecen dentro de
# palabras comunes ("mer" en "primero", "irma" en "afirma", "adie" en "nadie",
# "iol" en "violeta") y dispararian falsos positivos. Solo se listan tokens que son
# abreviaturas atomicas, nunca raices/prefijos intencionales (p. ej. "negativ",
# "ausenc", "neovas").
_WHOLE_WORD_KEYWORDS = frozenset({
    "mer", "cnv", "mev", "mnvc", "crsc",
    "isnt", "dmre", "cscr", "emq", "rdnp", "rdp", "irma",
    "dgm", "iol", "rapd", "adie", "papiledema",
    # Acrónimos vasculares, secundarios y pupilares protegidos contra falsos positivos:
    "obar", "obvr", "ovcr", "oacr", "crvo", "crao", "brvo", "brao",
    "pex", "pxf", "dpar", "dmae", "lio",
    # Acrónimos maculares protegidos:
    "mnv", "dep", "csc", "csr", "emd", "emcs", "emc", "tvm",
})


@functools.lru_cache(maxsize=512)
def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    normalized = unicodedata.normalize("NFKD", str(value))
    ascii_only = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    # La linea nueva delimita hechos; conservarla tambien tras normalizar CRLF.
    ascii_only = ascii_only.replace("\r\n", "\n").replace("\r", "\n")
    return _WHITESPACE_RE.sub(" ", ascii_only).strip().lower()


@functools.lru_cache(maxsize=1024)
def _compiled_keyword(keyword: str) -> re.Pattern:
    if keyword in ("dejo de ver", "deje de ver"):
        from app.correlaciones.vocabulario import COMPLEMENTO_VISUAL
        return re.compile(r"\s+".join(map(re.escape, keyword.split())) + COMPLEMENTO_VISUAL)
    if " " in keyword:
        parts = [
            f"{re.escape(w)}(?:s|es)?" if len(w) >= 4 else re.escape(w)
            for w in keyword.split()
        ]
        return re.compile(r"\s+".join(parts))
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


@functools.lru_cache(maxsize=256)
def _cover_desviaciones(value: str | None) -> frozenset[str]:
    """Desviaciones del cover test segun el formato canonico del SaaS.

    Devuelve tokens unidos ('exoforia', 'endotropia', 'hiperforia', ...) y,
    cuando el optometrista dejo el sub sin clasificar (eligio Tipo pero no
    Tropia/Foria), el tipo suelto ('exo', 'endo', 'hiper', 'hipo'). 'orto' no
    genera token. Texto libre legacy que no siga el formato canonico no matchea
    aqui: lo cubren las keywords sobre _normalize_cover_text.
    """
    text = _normalize_text(value)
    if not text:
        return frozenset()
    tokens: set[str] = set()
    for match in _COVER_EYE_RE.finditer(text):
        tipo, sub = match.group(2), match.group(3)
        if tipo == "orto":
            continue
        tokens.add(f"{tipo}{sub}" if sub else tipo)
    return frozenset(tokens)


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


def _is_word_bounded(text: str, start: int, end: int) -> bool:
    before = text[start - 1] if start > 0 else ""
    after = text[end] if end < len(text) else ""
    return not before.isalnum() and not after.isalnum()


_AFFIRMATIVE_TRANSITIONS = (
    "se observa", "se observan", "se aprecia", "se aprecian",
    "se evidencia", "se evidencian", "se constata", "se constat",
    "se identifica", "se identifican", "se detecta", "se detectan",
    "se visualiza", "se visualizan", "presenta", "presentan",
    "muestra", "muestran", "evidencia", "evidencian",
    "con ", "con hallazgo",
    "pero ", "empero", "sin embargo", "mas bien", "aunque ", "no obstante", "sino ",
    "refiere", "reporta", "nota ", "percibe",
)

# Texto normalizado: acentos eliminados, limites de palabra obligatorios.
_NUEVA_CLAUSULA_RE = re.compile(
    r"\b(?:acude|consulta|viene|presenta|refiere|reporta|manifiesta|comenta|describe|"
    r"nota|percibe|siente|ve|observa|aqueja|tiene|padece|sufre|inicia|inicio|comenzo|empezo|"
    r"desde|hoy|ayer|anoche|actualmente|ahora|recientemente|de repente|"
    r"subitamente|posteriormente|luego|despues)\b"
)

# Solo el inicio/tiempo explicito corta tambien si aparece DESPUES del hallazgo.
# Subita, nuevos, reciente y brusca solos pueden pertenecer a una lista negada.
_INICIO_TIEMPO_RE = re.compile(
    r"\b(?:desde|hoy|ayer|anoche|esta\s+(?:manana|tarde|noche)|de\s+inicio|"
    r"inicio|comenzo|empezo|actualmente|ahora|hace\s+(?:\d+|un[oa]?s?|dos|tres|cuatro|"
    r"cinco|seis|siete|ocho|nueve|diez|once|doce|trece|catorce|quince|dieciseis|"
    r"diecisiete|dieciocho|diecinueve|veinte|veinti\w*|treinta|cuarenta|cincuenta|"
    r"sesenta|setenta|ochenta|noventa|cien(?:to)?|mil|poc[oa]s?|vari[oa]s?|"
    r"algun[oa]s?|much[oa]s?))\b"
)
_NUCLEO_ANTECEDENTES_RE = re.compile(
    r"\b(?:antecedentes?|cirugias?|traumatismos?|alergias?|enfermedad(?:es)?|"
    r"padecimientos?|medicamentos?|tratamientos?|uso\s+de|lentes\s+previos)\b"
)

_EYE_MARKERS_RE = re.compile(r"\b(od|oi|ojo derecho|ojo izquierdo)\b")

_POSITIVE_CONFIRMATIONS = (
    "positivo", "positiva", "positivos", "positivas",
    "presente", "presentes", "patologico", "patologica",
    "alterado", "alterada",
)

# T13: Transiciones afirmativas negadas por 'no ' que no deben romper una negacion previa
_NEGATED_TRANSITION_RE = re.compile(
    r"\bno\s+(?:se\s+)?(?:aprecia|evidencia|visualiza|identifica|constata|observa|detecta|muestra|presenta|refiere|reporta|nota|percibe)n?\b"
)

# T10: Formulas de descarte que expresan sospecha activa salvo resolucion posterior
_DISCARD_FORMULAS_RE = re.compile(
    r"\b(?:a\s+descartar|descartar|descarte\s+de|para\s+descartar)\b"
)
_RESOLUTION_MARKERS_RE = re.compile(
    r"\b(?:sin\s+hallazgos|negativ\w*|normal\w*|se\s+descarta|descartad\w*|no\s+se\s+observa\w*|ausente\w*)\b"
)

# T11: Deteccion de formato "etiqueta: valor" con negador posterior
_LABEL_VALUE_RE = re.compile(
    r"^(?:s|es)?(?:\s+(?:od|oi|ao|ojo\s+derecho|ojo\s+izquierdo))?\s*[:\-]\s*(.*)",
    re.IGNORECASE,
)
_LABEL_NEGATORS_RE = re.compile(
    r"^(?:no\s+se\s+(?:observa|aprecia|evidencia)n?|no\b|negativ\w*|ausente\w*|sin\b|ningun\w*|nulo\w*|descartad\w*|normal\w*|0\b)",
    re.IGNORECASE,
)
# Resultado negativo en notacion abreviada justo tras el hallazgo: "DPAR (-)",
# "Desgarro [neg]", "Edema de papila -" (guion aislado al final o antes de
# puntuacion). "(+)" o un guion seguido de descripcion no se ven afectados.
_SHORT_NEGATIVE_RE = re.compile(
    # hasta 5 palabras (ojo, localizacion, complemento nominal) sin cruzar coma ni conector
    r"^(?:\s+(?!(?:con|y|e|pero|sin)\b)[^\s,;.:()\[\]-]+){0,5}\s*"
    r"(?:[(\[]\s*(?:-|neg\w*|no|ausente)\s*[)\]]|-\s*(?:$|[,;.)]))"
)

# T9: Conectores, marcadores de corte y palabras funcionales para ventana sufija
_POST_WINDOW_STOP_WORDS = frozenset({"con", "y", "e", "pero", "sin"})
_POST_WINDOW_EYE_TOKENS = frozenset({"od", "oi", "ao", "ojo", "derecho", "izquierdo"})
_POST_WINDOW_GRAMMATICAL_WORDS = frozenset({
    "de", "del", "en", "el", "la", "los", "las", "un", "una", "unos", "unas",
    "que", "es", "son", "resulta", "resultan", "se", "por", "al", "este", "esta", "momento",
})


def _find_neg_bounded(prefix: str, neg: str) -> int:
    """Busca la ultima aparicion de neg en prefix exigiendo limite de palabra previo.

    Evita que 'no ' coincida con la terminacion de palabras como 'retiniano ' o 'alumno ',
    o que 'niega' coincida dentro de 'despliega'.
    """
    start = 0
    best = -1
    while True:
        pos = prefix.find(neg, start)
        if pos == -1:
            break
        if pos == 0 or not prefix[pos - 1].isalnum():
            # Los conectores adversativos no abren una negacion.
            adversativo = ((neg == "sin " and prefix[pos:].startswith("sin embargo"))
                           or (neg == "no " and prefix[pos:].startswith("no obstante")))
            # "No proliferativa", "no continuo" y "no invasivo" califican una entidad o
            # funcion; no niegan otros hallazgos coordinados posteriores.
            calificador = neg == "no " and re.match(r"no (?:proliferativ\w*|continu[oa]s?|invasiv[oa]s?)\b", prefix[pos:])
            if not adversativo and not calificador:
                best = pos
        start = pos + 1
    return best


def _is_match_negated(text: str, start: int, end: int, *, fin_sufijo: int | None = None) -> bool:
    """Evalua si una ocurrencia span (start, end) en text esta negada
    segun las reglas T1, T9, T10, T11 y T13."""
    # T11: Formato "etiqueta: valor" (ej. "Edema de papila: negativo", "Desgarros: no")
    after_kw = text[end:fin_sufijo]
    if _SHORT_NEGATIVE_RE.match(after_kw):
        return True
    m_label = _LABEL_VALUE_RE.match(after_kw)
    if m_label:
        val_text = m_label.group(1).strip()
        if _LABEL_NEGATORS_RE.match(val_text):
            return True

    # Los encabezados de ojo, como los demas dos puntos, cortan el alcance.
    sentence_start = max(text.rfind(sep, 0, start) for sep in ".;:!?|\n") + 1
    sentence_prefix = text[sentence_start:start]

    sentence_end_candidates = [text.find(sep, end) for sep in ".;:!?|\n"]
    valid_ends = [pos for pos in sentence_end_candidates if pos != -1]
    sentence_end = min(valid_ends) if valid_ends else len(text)
    # Los extractores por ocurrencia pueden limitar los calificadores del
    # sufijo sin ocultar el coordinador que cierra una enumeracion posterior.
    suffix_end = sentence_end if fin_sufijo is None else min(sentence_end, fin_sufijo)
    sentence_suffix = text[end:suffix_end].strip()
    suffix_words = sentence_suffix.split()

    # T10: Formula de descarte ("descartar X", "a descartar X", "descarte de X")
    # Cuenta como sospecha activa SALVO que en el resto del campo haya marcador de resolucion negativa.
    if _DISCARD_FORMULAS_RE.search(sentence_prefix):
        rest_of_field = text[end:fin_sufijo]
        if _RESOLUTION_MARKERS_RE.search(rest_of_field):
            return True

    # Si el hallazgo esta calificado expresamente como positivo (ej. "dpar positivo"),
    # anula cualquier prefijo negativo anterior.
    is_positively_confirmed = any(
        w.strip(",.;:") in _POSITIVE_CONFIRMATIONS for w in suffix_words[:2]
    )

    if not is_positively_confirmed:
        last_neg_pos = -1
        last_neg_len = 0
        last_neg = ""
        for neg in _NEGACIONES_PRE:
            pos = _find_neg_bounded(sentence_prefix, neg)
            if pos != -1 and (pos > last_neg_pos or (pos == last_neg_pos and len(neg) > last_neg_len)):
                last_neg_pos = pos
                last_neg_len = len(neg)
                last_neg = neg

        if last_neg_pos != -1:
            intervening = sentence_prefix[last_neg_pos + last_neg_len:]
            # «Sin evidencia en OD ni en OI de desgarro»: el ultimo negador es la conjuncion
            # «ni» y el primero (sin/no) ya abarca ambos ojos; no es un cambio interocular.
            coordinated_negation = last_neg == "ni " and any(
                _find_neg_bounded(sentence_prefix[:last_neg_pos], other) != -1
                for other in _NEGACIONES_PRE if other != "ni ")
            # 1. Transicion afirmativa posterior al negador (T13: que no este negada por "no ")
            clean_intervening = _NEGATED_TRANSITION_RE.sub(" ", intervening)
            if _NEGATED_TRANSITION_RE.match(sentence_prefix[last_neg_pos:]):
                clean_intervening = _NEGATED_TRANSITION_RE.sub(" ", sentence_prefix[last_neg_pos:])
            has_affirmative_break = any(
                re.search(r"\b" + re.escape(t.rstrip()) + r"\b", clean_intervening)
                for t in _AFFIRMATIVE_TRANSITIONS
            )
            # 2. Transicion de ojo interocular (el negador estaba en el otro ojo)
            # Un ojo interpuesto puede localizar el hallazgo negado: «sin
            # evidencia en OD de desgarro». Solo dos ojos diferentes permiten
            # hablar de transición interocular, nunca la mera presencia de OD.
            def ojo_canonico(match):
                return "od" if match.group() in ("od", "ojo derecho") else "oi"
            previos = list(_EYE_MARKERS_RE.finditer(sentence_prefix[:last_neg_pos]))
            intermedios = list(_EYE_MARKERS_RE.finditer(intervening))
            posterior = re.match(
                r"\s*(?:(?!(?:od|oi|ojo|y|e|con|sin|no|pero|refiere|presenta|reporta)\b)\w+\s+){0,5}"
                r"(od|oi|ojo derecho|ojo izquierdo)\b", text[end:fin_sufijo],
            )
            ojos = {ojo_canonico(m) for m in intermedios}
            if previos:
                ojos.add(ojo_canonico(previos[-1]))
            if posterior:
                ojos.add("od" if posterior.group(1) in ("od", "ojo derecho") else "oi")
            has_eye_break = (bool(intermedios) and len(ojos) > 1
                             and re.search(r"\b(?:ni|o)\b", intervening) is None
                             and not coordinated_negation)
            # La coma corta salvo lista cerrada por coordinador. Un reporte
            # previo, tiempo en cualquier punto posterior o antecedentes
            # negados abren otro hecho. En duda, detectar.
            inicio_negado = last_neg_pos + last_neg_len
            if coordinated_negation:
                # Sin antecedentes ni dolor, ...: ni conserva el nucleo
                # negado por sin/no, aunque este preceda al ultimo negador.
                inicio_negado = max(
                    _find_neg_bounded(sentence_prefix[:last_neg_pos], neg)
                    for neg in _NEGACIONES_PRE if neg != "ni "
                )
            has_comma_break = False
            for coma in re.finditer(",", intervening):
                tras_coma = intervening[coma.end():]
                resto_clausula = tras_coma + text[start:sentence_end]
                # "y consulta/refiere/ayer..." coordina otra clausula; no
                # cierra una lista de hallazgos bajo el negador anterior.
                lista_cerrada = any(
                    not _NUEVA_CLAUSULA_RE.match(re.sub(r"^\s*(?:se\s+)?", "", resto_clausula[c.end():]))
                    for c in re.finditer(r"\b(?:ni|o|u|y|e)\b", resto_clausula)
                )
                nueva_clausula = bool(_NUEVA_CLAUSULA_RE.search(tras_coma))
                hasta_coma = sentence_prefix[inicio_negado:last_neg_pos + last_neg_len + coma.start()]
                corte_tiempo = bool(_INICIO_TIEMPO_RE.search(resto_clausula))
                corte_antecedentes = bool(_NUCLEO_ANTECEDENTES_RE.search(hasta_coma))
                has_comma_break = not lista_cerrada or nueva_clausula or corte_tiempo or corte_antecedentes
                # "ni en OI, de desgarro": la coma solo separa el localizador.
                if (coordinated_negation and not (corte_tiempo or corte_antecedentes)
                        and re.match(r"\s*(?:de|del)\b", tras_coma)):
                    has_comma_break = False
                if has_comma_break:
                    break
            if not (has_affirmative_break or has_eye_break or has_comma_break):
                return True

    # T9: Evaluacion de negacion sufija (hasta 3 palabras clinicas de contenido)
    negated_post = False
    counted_words = 0
    for word in suffix_words:
        has_punct_cut = "," in word or ";" in word
        w_clean = word.strip(",.;:")
        if w_clean in _POST_WINDOW_STOP_WORDS:
            break
        if w_clean in _POST_WINDOW_EYE_TOKENS or w_clean in _POST_WINDOW_GRAMMATICAL_WORDS:
            if has_punct_cut:
                break
            continue
        counted_words += 1
        if counted_words > 3:
            break
        if any(neg in w_clean for neg in _NEGACIONES_POST):
            negated_post = True
            break
        if has_punct_cut:
            break

    if negated_post:
        return True

    return False


def _fragmentos_con_negacion(texto: str, patron: str | re.Pattern) -> list[str]:
    """Divide para localizar hechos sin convertir una coordinada negada en positiva.

    El prefijo solo se repone cuando el matcher con el texto completo niega el
    inicio del fragmento y el fragmento aislado ha perdido ese alcance. No se
    trasladan ojo, sujeto ni calificadores temporales de otro fragmento.
    """
    partes = re.split(patron, texto)
    salida = []
    cursor = 0
    for parte in partes:
        offset = texto.index(parte, cursor)
        cursor = offset + len(parte)
        primera = next((m for m in re.finditer(r"\w+", parte)
                        if m[0] not in {"con", "y", "e", "de", "del", "en", "el", "la", "los", "las", "un", "una",
                                        "od", "oi", "ao", "ojo", "derecho", "izquierdo"}), None)
        # Si el fragmento empieza por una señal de clausula nueva, evaluar
        # despues de la señal completa: en su propio inicio aun no esta en el
        # prefijo y se reintroduciria "sin" antes de un reporte afirmativo.
        senal = next((m for m in _NUEVA_CLAUSULA_RE.finditer(parte)
                      if primera and m.start() <= primera.start() < m.end()), None)
        if senal:
            primera = re.compile(r"\w+").search(parte, senal.end())
        if (primera and _is_match_negated(texto, offset + primera.start(), offset + primera.end())
                and not _is_match_negated(parte, primera.start(), primera.end())):
            parte = "sin " + parte
        salida.append(parte)
    return salida


def _keyword_matches(text: str, keyword: str, *, allow_negation_window: bool) -> bool:
    whole_word = keyword in _WHOLE_WORD_KEYWORDS
    for match in _compiled_keyword(keyword).finditer(text):
        if whole_word and not _is_word_bounded(text, match.start(), match.end()):
            continue
        if not allow_negation_window:
            return True
        if not _is_match_negated(text, match.start(), match.end()):
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
