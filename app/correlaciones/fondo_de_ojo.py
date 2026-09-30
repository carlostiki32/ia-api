"""Dominio: fondo de ojo (11 correlaciones).

fondo_periferico_riesgo, sintomas_alarma_traccion_vitreoretina,
fondo_oclusion_vascular_urgente, fondo_embolo_retiniano, papila_patologica,
glaucoma_asimetrico, fondo_glaucomatoso, fondo_macular_dmae, fondo_macular_otros,
fondo_hipertensivo, fondo_vascular_diabetico. Todas leen `clinica.fondo_de_ojo`
(o `motivo_consulta`) con ventana de negacion por oracion; la jerarquia de supresion
se resuelve dentro del dominio.
"""
from __future__ import annotations

import re

from app.correlaciones.base import _memoize_cond
from app.correlaciones.texto import (
    _compiled_keyword,
    _dedupe,
    _extract_normalized_findings,
    _find_neg_bounded,
    _fondo_contains,
    _is_match_negated,
    _join_hallazgos,
    _keyword_matches,
    _normalize_text,
)
from app.correlaciones.refraccion_utils import _equivalente_esferico
from app.schemas import ImpresionClinicaRequest


def _texto_hechos_paciente(text: str | None) -> str:
    """Conserva los offsets y resuelve sujeto/hipotesis antes de separar hechos.

    Una coordinacion hereda su sujeto: dividir primero ``mi madre tiene X y Y``
    haria que Y pareciera propio. Los espacios permiten reutilizar los extractores
    locales sin trasladar el sujeto ni la cronologia de esas menciones.
    """
    from app.correlaciones.hechos_textuales import _sujeto_es_paciente, _es_hipotetico
    norm = _normalize_text(text)
    spans = [(m.start(), m.end()) for m in re.finditer(r"\w+", norm)
             if m.group() not in ("y", "e", "pero")
             and (not _sujeto_es_paciente(norm, m.start(), m.end())
                  or _es_hipotetico(norm, m.start(), m.end()))]
    chars = list(norm)
    for start, end in spans:
        chars[start:end] = " " * (end - start)
    return "".join(chars)


def _certeza_hallazgo(text: str, match: re.Match) -> str | None:
    return _certeza_local_span(text, match.start(), match.end())


def _certeza_local_span(text: str, start: int, end: int) -> str | None:
    from app.correlaciones.hechos_textuales import _certeza_local
    return _certeza_local(text, start, end)

_CD_PREFIXES = (
    "c/d", "cd", "cup/disc", "cup disc", "cup-disc", "e/p",
    "relacion c/d", "relacion cd",
    "relacion copa/disco", "relacion copa disco",
    "copa/disco", "copa disco",
)
_CD_SEPARATORS = (" ", ": ", ":", " de ", " del ")
_CD_PATOLOGICOS_VALS = (
    "0.6", "0.7", "0.8", "0.9", "1.0",
    "0,6", "0,7", "0,8", "0,9", "1,0",
    "6/10", "7/10", "8/10", "9/10",
)

_KEYWORDS_FONDO_GLAUCOMATOSO: tuple[str, ...] = tuple(
    f"{p}{s}{v}"
    for p in _CD_PREFIXES
    for s in _CD_SEPARATORS
    for v in _CD_PATOLOGICOS_VALS
) + (
    "relacion copa/disco aumentada", "copa/disco aumentada", "copa disco aumentada",
    "relacion c/d aumentada", "relacion cd aumentada",
    "relacion copa/disco amplia", "copa/disco amplia", "copa disco amplia", "relacion c/d amplia",
    "asimetria c/d", "asimetria de la excavacion", "muesca", "escotadura", "notch",
    "hemorragia peripapilar", "hemorragia de disco", "hemorragia en astilla",
    "rima neural adelgazada", "anillo neurorretiniano adelgazado",
    "adelgazamiento del anillo", "adelgazamiento neurorretiniano",
    "violacion de la regla isnt", "violacion isnt", "isnt violada",
)

_KEYWORDS_ISNT_VIOLADA = (
    "isnt violada", "regla isnt violada", "violacion isnt", "violacion de isnt",
    "violacion de la regla isnt", "violacion de regla isnt", "viola la regla isnt",
    "viola regla isnt", "viola isnt", "regla isnt no se cumple", "isnt no se cumple",
    "no se cumple la regla isnt", "no se cumple regla isnt", "no se cumple isnt",
    "no cumple la regla isnt", "no cumple regla isnt", "no cumple isnt",
    "incumple la regla isnt", "incumple regla isnt", "incumple isnt",
    "incumplimiento de la regla isnt", "no respeta la regla isnt", "no respeta regla isnt",
    "no respeta isnt", "isnt no respetada", "regla isnt no respetada",
    "isnt alterada", "regla isnt alterada", "isnt invertida",
    "isnt: no se cumple", "isnt: no cumple", "isnt: alterada", "isnt: violada", "isnt: no respetada",
    "anillo temporal mas grueso que el inferior", "anillo temporal mas grueso que el superior",
    "anillo temporal mas ancho que el inferior", "anillo temporal mas ancho que el superior",
)


def _es_excavacion_fisiologica_pura(fondo_norm: str) -> bool:
    """Descarta excavacion normal/fisiologica (0.1, 0.2, 0.3, 0.4, 0.5 o calificada de fisiologica)
    cuando no hay signos glaucomatosos patologicos asociados."""
    tokens_patologicos = (
        "0.6", "0.7", "0.8", "0.9", "1.0", "0,6", "0,7", "0,8", "0,9", "1,0",
        "6/10", "7/10", "8/10", "9/10",
        "asimetr", "muesca", "notch", "astilla", "adelgaz", "violacion", "aumentad", "amplia",
    )
    if any(p in fondo_norm for p in tokens_patologicos):
        return False
    return any(b in fondo_norm for b in ("0.1", "0.2", "0.3", "0.4", "0.5", "fisiologic", "normal"))


_KEYWORDS_FONDO_DMAE = (
    "drusas", "drusa", "drusen", "pseudodrusas", "pseudodrusa",
    "alteracion pigmentaria", "cambios pigmentarios",
    "alteracion del epr", "atrofia del epr", "hiperplasia del epr",
    "atrofia geografica", "membrana neovascular", "membrana neovascular coroidea",
    "neovascularizacion coroidea", "neovascularizacion macular", "neovascularizacion subretiniana",
    "neovasos coroideos", "neovaso coroideo", "neovasos maculares", "neovasos subretinianos",
    "mnvc", "mnv", "cnv",
    "dmae", "dmre", "degeneracion macular",
    "maculopatia relacionada con la edad", "maculopatia senil",
    "liquido subretiniano", "liquido intrarretiniano", "fluido subretiniano",
    "desprendimiento del epitelio pigmentario", "dep",
    "hemorragia subretiniana", "hemorragia submacular", "cicatriz disciforme",
)

_KEYWORDS_PAPILA_EMERGENCIA = (
    "papiledema", "edema de papila", "edema papilar", "edema del disco",
    "papila edematosa", "disco edematoso", "papilas edematosas", "discos edematosos",
    "papila elevada", "papilas elevadas", "disco elevado", "discos elevados",
    "borramiento de bordes", "borramiento de los bordes",
    "bordes borrosos", "bordes difuminados", "bordes mal definidos",
    "margenes borrosos", "limites borrosos", "noia", "neuropatia optica isquemica",
)

_KEYWORDS_PAPILA_NO_GLAUCOMA = (
    "palidez papilar", "palidez de papila", "papila palida", "disco palido",
    "papilas palidas", "discos palidos", "disco optico palido",
    "atrofia optica", "atrofia papilar", "atrofia del nervio optico",
    "neuritis optica", "neuropatia optica",
) + _KEYWORDS_PAPILA_EMERGENCIA

_KEYWORDS_FONDO_MACULAR_OTROS = (
    "edema macular", "edema de macula", "edema en macula", "macula con edema", "macula edematosa",
    "macula engrosada", "engrosamiento macular", "engrosamiento foveal", "edema foveal",
    "edema cistoide", "edema quistico", "irvine-gass", "irvine gass", "maculopatia diabetica",
    "emq", "emc", "emd", "emcs",
    "quiste macular", "quistes maculares", "quiste foveal", "quistes foveales",
    "quistes intrarretinianos", "espacios quisticos",
    "membrana epirretiniana", "membrana epiretiniana", "mer",
    "gliosis macular", "gliosis premacular", "pucker", "celofan", "maculopatia en celofan",
    "traccion vitreomacular", "traccion vitreo macular", "tvm",
    "agujero macular", "agujero foveal", "agujero de espesor completo",
    "agujero lamelar", "pseudoagujero", "pseudoagujero macular", "seudoagujero",
    "foveosquisis", "maculosquisis", "retinosquisis macular", "schisis macular",
    "coroidopatia serosa", "corioretinopatia serosa", "coriorretinopatia serosa",
    "retinopatia serosa", "serosa central", "desprendimiento seroso",
    "desprendimiento neurosensorial", "crsc", "cscr", "csc", "csr",
    "desgarro del epitelio pigmentario", "desgarro del epr", "rotura del epr",
    "maculopatia miopica", "miopia patologica", "degeneracion miopica",
    "estria de laca", "estrias de laca", "estafiloma posterior", "mancha de fuchs",
    "atrofia coriorretiniana difusa",
)

# ---------------------------------------------------------------------------
# #1: fondo_periferico_riesgo (6 niveles jerarquicos)
# DR > ROTURA > VITREO > PREDISPONENTE+SINTOMAS > PREDISPONENTE > ANTECEDENTE
# ---------------------------------------------------------------------------

_RE_ANTECEDENTE_PERIFERICO = re.compile(
    r"\b("
    r"antecedentes?|historia\s+de|operad\w*|vitrectom\w*|cerclaje\w*|"
    r"retinopexia\w*|pexia\w*|laser|fotocoagul\w*|crio\w*|tratad\w*|"
    r"cicatriz\w*|pigmentad\w*|demarcacion\w*|antigu\w*|silicon\w*"
    r")\b",
    re.IGNORECASE,
)

_PERIFERICO_DR_TERMS = (
    ("desprendimiento neurosensorial", "desprendimiento de retina"),
    ("desprendimiento regmatogeno de retina", "desprendimiento de retina"),
    ("desprendimiento regmatogeno", "desprendimiento de retina"),
    ("desprendimiento de retina", "desprendimiento de retina"),
    ("desprendimiento retiniano", "desprendimiento de retina"),
    ("drr", "desprendimiento de retina"),
)

_PERIFERICO_ROTURA_TERMS = (
    ("desgarro en herradura", "desgarro retiniano"),
    ("rotura en herradura", "rotura retiniana"),
    ("ruptura en herradura", "rotura retiniana"),
    ("desgarro retiniano", "desgarro retiniano"),
    ("desgarro", "desgarro retiniano"),
    ("rotura retiniana", "rotura retiniana"),
    ("ruptura retiniana", "rotura retiniana"),
    ("dialisis retiniana", "dialisis retiniana"),
    ("dialisis", "dialisis retiniana"),
)

_PERIFERICO_VITREO_TERMS = (
    ("hemorragia vitrea", "hemorragia vitrea"),
    ("hemovitreo", "hemorragia vitrea"),
    ("pigmento en vitreo", "pigmento en vitreo"),
    ("polvo de tabaco", "polvo de tabaco"),
    ("signo de shafer", "signo de Shafer"),
)

_PERIFERICO_PREDISPONENTE_TERMS = (
    ("degeneracion en empalizada", "degeneracion lattice"),
    ("lattice", "degeneracion lattice"),
    ("empalizada", "degeneracion lattice"),
    ("palizada", "degeneracion lattice"),
    ("degeneracion reticular", "degeneracion reticular"),
    ("baba de caracol", "degeneracion en baba de caracol"),
    ("huella de caracol", "degeneracion en baba de caracol"),
    ("agujero atrofico", "agujero atrofico"),
    ("agujero operculado", "agujero operculado"),
    ("agujero retiniano", "agujero retiniano"),
    ("retinosquisis", "retinosquisis"),
    ("schisis", "schisis periferica"),
)

_KEYWORDS_FOTOPSIA = (
    "fotopsias", "fotopsia", "destellos", "destello", "flashes", "flash",
    "centelleos", "centelleo", "luces intermitentes", "luz intermitente",
    "relampagos", "relampago",
)

_KEYWORDS_MIODESOPSIA = (
    "miodesopsias", "miodesopsia", "moscas volantes", "mosca volante",
    "telaranas", "telarana", "manchas negras flotantes", "puntos negros flotantes",
    "cuerpos flotantes",
)

_PATTERNS_ALARMA = (
    (r"\b(?:cortina|telon)\b", "sombra o cortina en el campo visual"),
    (r"\bsombra\s+que\s+(?:avanza|sube|baja|cubre)\b", "sombra o cortina en el campo visual"),
    (r"\bperdida\s+(?:subita|brusca|repentina)\s+de\s+(?:la\s+)?vision\b", "perdida subita de vision"),
    (r"\bperdida\s+visual\s+(?:subita|brusca|repentina)\b", "perdida subita de vision"),
    (r"\bperdida\s+(?:subita|brusca|repentina)\s+visual\b", "perdida subita de vision"),
    (r"\bperdida\s+de\s+(?:la\s+)?vision\s+(?:subita|brusca|repentina)\b", "perdida subita de vision"),
    (r"\bperdida\s+de\s+(?:campo|vision)\s+periferic\w*\b", "perdida subita de vision"),
    (r"\bnube\b", "sombra o cortina en el campo visual"),
    (r"\blluvia\s+de\s+(?:manchas|moscas|puntos)\b", "lluvia de miodesopsias"),
    (r"\b(?:muchas|multiples)\s+(?:moscas|manchas|puntos)\b", "lluvia de miodesopsias"),
)

_EXCLUSIONES_HALOS = (
    "alrededor de las luces", "con las luces", "luces de los autos", "luces de los carros",
    "luces de los coches", "faros", "halo", "deslumbr", "encandil", "resplandor",
    "al manejar", "al conducir",
)

_EXCLUSIONES_AURA = (
    "migran", "jaqueca", "aura", "zigzag", "zig zag", "escotoma centelleante",
    "fortificacion", "antes del dolor de cabeza",
)

_RE_RECIENTE = re.compile(
    r"\b("
    r"agud\w*|subit\w*|repentin\w*|brusc\w*|recientes?|de\s+novo|ahora|"
    r"hace\s+\d+\s+(?:horas?|dias?|semanas?)|"
    r"hace\s+(?:unas?|unos|pocas?|pocos)\s+(?:horas?|dias?|semanas?)|"
    r"desde\s+(?:ayer|anoche|hoy|esta\s+manana)|"
    r"aumentaron|han\s+aumentado|mas\s+moscas"
    r")\b",
    re.IGNORECASE,
)

_RE_NUEVO_ADYACENTE = re.compile(
    r"\b("
    r"(?:nuevas?|nuevos?)\s+(?:moscas|miodesopsias|telaranas|fotopsias|destellos|flashes|centelleos|relampagos|manchas|puntos)|"
    r"(?:moscas|miodesopsias|telaranas|fotopsias|destellos|flashes|centelleos|relampagos|manchas|puntos|moscas\s+volantes)\s+(?:nuevas?|nuevos?)"
    r")\b",
    re.IGNORECASE,
)

_RE_CRONICO_GENERAL = re.compile(
    r"\b("
    r"desde\s+hace\s+(?:anos|\d+\s+anos|meses|\d+\s+meses)|"
    r"hace\s+(?:anos|\d+\s+anos|meses|\d+\s+meses|mucho\s+tiempo)|"
    r"de\s+siempre|de\s+larga\s+evolucion|cronic\w*|antigu\w*"
    r")\b",
    re.IGNORECASE,
)

_RE_SIN_CAMBIOS_ESTABLE = re.compile(
    r"\b(sin\s+cambios|estables?)\b",
    re.IGNORECASE,
)


def _hay_cronico_adyacente(norm: str) -> bool:
    tokens = norm.split()
    sintoma_indices = []
    for i, tok in enumerate(tokens):
        if any(tok.startswith(k.split()[0]) for k in _KEYWORDS_MIODESOPSIA + _KEYWORDS_FOTOPSIA):
            sintoma_indices.append(i)
    if not sintoma_indices:
        return False
    for m in _RE_SIN_CAMBIOS_ESTABLE.finditer(norm):
        tok_idx = len(norm[:m.start()].split())
        if any(abs(tok_idx - s_idx) <= 4 for s_idx in sintoma_indices):
            return True
    return False


_RE_TRACCION_HISTORIA = re.compile(
    r"\b(?:antecedentes?|historia\s+de|resuelt\w*|desapareci\w*)\b"
)
_RE_TRACCION_OTRO_MOTIVO = re.compile(
    r"\b(?:cefalea|dolor|graduacion|lentes|revision|control|cita|consulta)\b"
)


def _clausulas_traccion(norm: str) -> list[str]:
    """Conserva juntos sintoma y tiempo; otra queja no presta su cronologia."""
    partes = re.split(
        r"[.,;!?]+|\bpero\b|\bsin\s+embargo\b|(?=\bahora\b)|"
        r"\s+(?:y|con)\s+(?=(?:cefalea|dolor|graduacion|revision|control|cita)\b)",
        norm,
    )
    salida = []
    for parte in partes:
        inicio = 0
        for union in re.finditer(
            r"\s+y\s+(?=(?:fotopsias?|destellos?|miodesopsias?|moscas?|flashes?|telaranas?)\b)",
            parte,
        ):
            previo = parte[inicio:union.start()]
            if (_RE_RECIENTE.search(previo) or _RE_CRONICO_GENERAL.search(previo)
                    or _RE_TRACCION_HISTORIA.search(previo)):
                salida.append(previo.strip())
                inicio = union.end()
        salida.append(parte[inicio:].strip())
    return [parte for parte in salida if parte]


def _calificador_temporal_traccion(clausula: str) -> bool:
    """Solo una clausula temporal independiente puede completar a la inmediata."""
    if _RE_TRACCION_OTRO_MOTIVO.search(clausula):
        return False
    resto = _RE_RECIENTE.sub(" ", clausula)
    resto = _RE_CRONICO_GENERAL.sub(" ", resto)
    resto = _RE_SIN_CAMBIOS_ESTABLE.sub(" ", resto)
    resto = _RE_TRACCION_HISTORIA.sub(" ", resto)
    resto = re.sub(
        r"\b(?:de|desde|inicio|evolucion|son|estan|se|mantienen|en|od|oi|ao)\b", " ", resto
    )
    return not resto.strip()


def _coincidencia_traccion(clausula: str, keywords: tuple[str, ...]) -> bool:
    return any(
        not _is_match_negated(clausula, m.start(), m.end())
        and _certeza_hallazgo(clausula, m) is None
        for keyword in keywords
        for m in re.finditer(r"\b" + re.escape(keyword) + r"\b", clausula)
    )


def _eval_sintomas_traccion(req: ImpresionClinicaRequest) -> dict:
    vacio = {"nivel": None, "sintomas_str": "", "dato_alarma": None}
    if req.paciente is None or not req.paciente.motivo_consulta:
        return vacio
    norm = _texto_hechos_paciente(req.paciente.motivo_consulta)
    if not norm:
        return vacio

    clausulas = _clausulas_traccion(norm)
    hallazgos = []
    dato_alarma = None
    for indice, clausula in enumerate(clausulas):
        # Sujeto/hipotesis se resolvieron antes de dividir. Un plan para
        # descartar catarata no borra moscas volantes afirmadas en la misma frase.
        contexto = clausula
        # "Fotopsias, desde ayer" comparte tiempo; "cefalea desde ayer" no.
        for vecino in (indice - 1, indice + 1):
            if 0 <= vecino < len(clausulas) and _calificador_temporal_traccion(clausulas[vecino]):
                contexto += " " + clausulas[vecino]
        reciente = any(
            not _is_match_negated(contexto, m.start(), m.end())
            for m in _RE_RECIENTE.finditer(contexto)
        ) or bool(_RE_NUEVO_ADYACENTE.search(contexto))
        historico = bool(_RE_TRACCION_HISTORIA.search(contexto))
        cronico = bool(_RE_CRONICO_GENERAL.search(contexto)) or _hay_cronico_adyacente(contexto)
        # "Perdida subita hace anos" describe el inicio antiguo, no un evento nuevo.
        remoto = bool(_RE_CRONICO_GENERAL.search(contexto))
        if not historico and not remoto:
            for patron, etiqueta in _PATTERNS_ALARMA:
                for m in re.finditer(patron, clausula):
                    if (not _is_match_negated(clausula, m.start(), m.end())
                            and _certeza_hallazgo(clausula, m) is None):
                        dato_alarma = dato_alarma or etiqueta

        fotopsia = _coincidencia_traccion(clausula, _KEYWORDS_FOTOPSIA)
        miodesopsia = _coincidencia_traccion(clausula, _KEYWORDS_MIODESOPSIA)
        if not (fotopsia or miodesopsia) or historico:
            continue
        if cronico and not reciente:
            continue
        excluida = any(ex in clausula for ex in _EXCLUSIONES_HALOS + _EXCLUSIONES_AURA)
        hallazgos.append((fotopsia, miodesopsia, reciente, excluida))

    # La excepcion de aura/halos requiere otro sintoma realmente reciente.
    anuladas = dato_alarma is not None or any(mio and reciente for _, mio, reciente, _ in hallazgos)
    observaciones = [
        (foto and (not excluida or anuladas), mio, reciente)
        for foto, mio, reciente, excluida in hallazgos
    ]
    recientes = [(foto, mio) for foto, mio, rec in observaciones if rec and (foto or mio)]
    if dato_alarma is not None:
        nivel = "A"
        seleccion = [(foto, mio) for foto, mio, _ in observaciones]
    elif recientes:
        nivel = "B"
        seleccion = recientes
    else:
        nivel = "C"
        seleccion = [(foto, mio) for foto, mio, _ in observaciones]
    foto = any(f for f, _ in seleccion)
    mio = any(m for _, m in seleccion)
    if not (foto or mio or dato_alarma):
        return vacio
    sintomas = ("fotopsias y miodesopsias" if foto and mio else
                "fotopsias" if foto else "miodesopsias" if mio else "sintomas visuales")
    return {"nivel": nivel, "sintomas_str": sintomas, "dato_alarma": dato_alarma}


def _eval_sintomas_traccion_agudos(req: ImpresionClinicaRequest) -> bool:
    """Evalua si el paciente refiere sintomas agudos de traccion vitreorretiniana (Nivel A o B)."""
    info = _eval_sintomas_traccion(req)
    return info["nivel"] in ("A", "B")


def _get_clause_around_span(text: str, start: int, end: int) -> str:
    clause_start = max([text.rfind(sep, 0, start) for sep in ".,;:\n"] or [-1]) + 1
    ends = [pos for pos in [text.find(sep, end) for sep in ".,;:\n"] if pos != -1]
    clause_end = min(ends) if ends else len(text)
    return text[clause_start:clause_end]


def _es_termino_periferico_excluido(term: str, clause: str) -> bool:
    # 1. hemodialisis no cuenta como dialisis retiniana
    if "dialisis" in term and re.search(r"hemodialisis|dialisis\s+(?:peritoneal|renal)", clause):
        return True
    if "desgarro" in term and re.search(r"desgarros?\s+(?:iridian\w*|corneal\w*|conjuntival\w*)", clause):
        return True
    # 2. Desprendimiento neurosensorial seroso / macular (CSC)
    if ("desprendimiento" in term and "neurosensorial" in clause
            and not re.search(r"\b(?:de\s+retina|regmatogen\w*|periferic\w*|desgarro|cuadrante|bolsa)\b", clause)):
        return True
    # 3. Desgarro del epitelio pigmentario / EPR macular
    if "desgarro" in term and any(x in clause for x in ("epitelio pigmentario", "epr", "dep")):
        return True
    # 4. Rotura/ruptura de membrana de Bruch
    if any(r in term for r in ("rotura", "ruptura")) and ("bruch" in clause or "membrana de bruch" in clause):
        return True
    # 5. Schisis/retinosquisis foveolar o macular (foveosquisis)
    if any(s in term for s in ("schisis", "retinosquisis")) and re.search(
        r"(?:schisis|retinosquisis)\s+(?:(?:de|la|region)\s+)*(?:fove\w*|macul\w*)", clause
    ):
        return True
    return False


def _periferico_es_antecedente(text: str, start: int, end: int, group: str) -> bool:
    """Asocia el antecedente a la lesion, no a otra intervencion en el mismo ojo."""
    left = max(text.rfind(sep, 0, start) for sep in ('.', ',', ';', ':', '\n', ' y '))
    begin = left + (3 if text[left:left + 3] == ' y ' else 1)
    ends = [p for sep in ('.', ',', ';', ':', '\n', ' y ')
            if (p := text.find(sep, end)) >= 0]
    stop = min(ends) if ends else len(text)
    clause = text[begin:stop]
    for match in re.finditer(r"\b(?:nuev\w*|agud\w*|reciente\w*)\b", clause):
        if not _is_match_negated(clause, match.start(), match.end()):
            return False
    for match in _RE_ANTECEDENTE_PERIFERICO.finditer(clause):
        if _is_match_negated(clause, match.start(), match.end()):
            continue
        # Una cirugia de catarata no convierte una hemorragia vitrea en secuela.
        if group == 'VITREO' and not re.match(r'antecedente|historia|antigu', match.group()):
            continue
        if re.match(r'operad', match.group()) and re.search(r'catarata|cristalino|cornea', clause[match.end():]):
            continue
        return True
    return False


def _eval_fondo_periferico(req: ImpresionClinicaRequest) -> dict:
    if req.clinica is None or not req.clinica.fondo_de_ojo:
        return {"nivel": None, "hallazgos": [], "texto": ""}
    fondo = _texto_hechos_paciente(req.clinica.fondo_de_ojo)
    if not fondo:
        return {"nivel": None, "hallazgos": [], "texto": ""}

    dr_findings: list[str] = []
    rotura_findings: list[str] = []
    vitreo_findings: list[str] = []
    predisponente_findings: list[str] = []
    antecedente_findings: list[str] = []
    seen_spans: list[tuple[int, int]] = []

    groups = (
        ("DR", _PERIFERICO_DR_TERMS),
        ("ROTURA", _PERIFERICO_ROTURA_TERMS),
        ("VITREO", _PERIFERICO_VITREO_TERMS),
        ("PREDISPONENTE", _PERIFERICO_PREDISPONENTE_TERMS),
    )

    for group_name, term_list in groups:
        for kw, normalized_name in term_list:
            whole_word = kw in ("drr", "dialisis", "schisis", "lattice")
            pat = r"\b" + re.escape(kw) + r"\b" if whole_word else _compiled_keyword(kw).pattern
            for m in re.finditer(pat, fondo):
                if any(start <= m.start() and m.end() <= end for start, end in seen_spans):
                    continue
                if _is_match_negated(fondo, m.start(), m.end()):
                    continue
                clause = _get_clause_around_span(fondo, m.start(), m.end())
                if _es_termino_periferico_excluido(kw, clause):
                    continue
                seen_spans.append((m.start(), m.end()))
                certainty = _certeza_hallazgo(fondo, m)
                name = f"{certainty} {normalized_name}" if certainty else normalized_name
                if _periferico_es_antecedente(fondo, m.start(), m.end(), group_name):
                    antecedente_findings.append(name)
                else:
                    if group_name == "DR":
                        dr_findings.append(name)
                    elif group_name == "ROTURA":
                        rotura_findings.append(name)
                    elif group_name == "VITREO":
                        vitreo_findings.append(name)
                    elif group_name == "PREDISPONENTE":
                        predisponente_findings.append(name)

    dr_findings = _dedupe(dr_findings)
    rotura_findings = _dedupe(rotura_findings)
    vitreo_findings = _dedupe(vitreo_findings)
    predisponente_findings = _dedupe(predisponente_findings)
    antecedente_findings = _dedupe(antecedente_findings)

    # Prioridad: DR > ROTURA > VITREO > PREDISPONENTE+SINTOMAS > PREDISPONENTE > ANTECEDENTE
    if dr_findings:
        verbo = "describe" if any(re.match(r"(?:posible|probable|sospecha|a descartar)\b", h) for h in dr_findings) else "documenta"
        texto = (
            f"Hallazgo urgente: en el fondo de ojo se {verbo} {_join_hallazgos(dr_findings)}, "
            "que amerita valoracion retinologica urgente el mismo dia."
        )
        return {"nivel": "DR", "hallazgos": dr_findings, "texto": texto}

    if rotura_findings:
        h = _join_hallazgos(rotura_findings)
        texto = (
            f"Hallazgo urgente: en el fondo de ojo se documenta {h}, "
            "que amerita valoracion retinologica urgente con exploracion de la retina "
            "periferica bajo midriasis e indentacion escleral."
        )
        return {"nivel": "ROTURA", "hallazgos": rotura_findings, "texto": texto}

    if vitreo_findings:
        h = _join_hallazgos(vitreo_findings)
        texto = (
            f"Hallazgo urgente: en el vitreo se documenta {h}, "
            "que amerita valoracion retinologica urgente para descartar rotura retiniana."
        )
        return {"nivel": "VITREO", "hallazgos": vitreo_findings, "texto": texto}

    if predisponente_findings:
        h = _join_hallazgos(predisponente_findings)
        if _eval_sintomas_traccion_agudos(req):
            texto = (
                f"Hallazgo urgente: en la retina periferica se documenta {h} "
                "y el paciente refiere sintomas visuales de inicio reciente, lo que amerita "
                "valoracion retinologica urgente con exploracion de la retina periferica bajo midriasis."
            )
            return {"nivel": "PREDISPONENTE_SINTOMAS", "hallazgos": predisponente_findings, "texto": texto}
        else:
            texto = (
                f"En la retina periferica se documenta {h}, que amerita exploracion programada "
                "de la periferia bajo midriasis y educacion al paciente para acudir a revision "
                "sin esperar a la cita programada si presenta fotopsias, miodesopsias nuevas "
                "o sombra en el campo visual."
            )
            return {"nivel": "PREDISPONENTE", "hallazgos": predisponente_findings, "texto": texto}

    if antecedente_findings:
        h = _join_hallazgos(antecedente_findings)
        texto = (
            f"Se documenta antecedente de {h} tratado o de larga evolucion, que amerita "
            "mantener el seguimiento retinologico programado y educacion sobre sintomas de alarma."
        )
        return {"nivel": "ANTECEDENTE", "hallazgos": antecedente_findings, "texto": texto}

    return {"nivel": None, "hallazgos": [], "texto": ""}


@_memoize_cond
def _cond_fondo_periferico_riesgo(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: fondo con hallazgo periferico activo (DR, rotura, vitreo, predisponente o antecedente)."""
    return _eval_fondo_periferico(req)["nivel"] is not None


@_memoize_cond
def _cond_fondo_periferico_rotura_o_desgarro(req: ImpresionClinicaRequest) -> bool:
    """Verifica si en retina periferica hay rotura, desgarro o desprendimiento comprobado."""
    return _eval_fondo_periferico(req)["nivel"] in ("DR", "ROTURA")


def _texto_fondo_periferico_riesgo(req: ImpresionClinicaRequest) -> str:
    return _eval_fondo_periferico(req)["texto"]


# ---------------------------------------------------------------------------
# C/D extractor por ojo y helpers
# ---------------------------------------------------------------------------

_RE_CD_PREFIX = re.compile(
    r"\b(?:relacion\s+)?(?:c\s*/\s*d|cd|e\s*/\s*p|cup[\s/-]*disc|copa[\s/-]*disco|excavacion(?:\s+papilar)?)(?:\s+vertical)?\b",
    re.IGNORECASE,
)
_RE_CD_NUMBER = re.compile(r"(?<![\d.])(0(?:\.\d{1,2})?|1(?:\.0+)?)(?![\d.])")
_RE_CD_STOP = re.compile(r"\b(?:macula|retina|vasos|arterias?|venas?|periferia)\b", re.IGNORECASE)

_RE_EYE_OD = re.compile(r"\b(?:od|ojo\s+derecho)\b", re.IGNORECASE)
_RE_EYE_OI = re.compile(r"\b(?:oi|os|ojo\s+izquierdo)\b", re.IGNORECASE)
_RE_EYE_AO = re.compile(r"\b(?:ao|ambos\s+ojos|ambos|bilateral(?:es)?)\b", re.IGNORECASE)


def _cd_por_ojo(fondo_text: str | None) -> dict[str, float]:
    """C/D por ojo explicitado; clave vacia conserva un valor sin lateralidad."""
    norm = _texto_hechos_paciente(fondo_text)
    if not norm:
        return {}
    norm = re.sub(r"\b([1-9]|10)/10\b", lambda m: str(int(m.group(1)) / 10), norm)
    norm = re.sub(r"\b(0|1),(\d{1,2})\b", r"\1.\2", norm)
    norm = re.sub(r"(^|[\s/:=,-])\.(\d+)\b", r"\g<1>0.\2", norm)
    resultados: dict[str, list[float]] = {}
    eye_re = re.compile(r"\b(?:od|oi|os|ojo\s+derecho|ojo\s+izquierdo|ao|ambos(?:\s+ojos)?|bilaterales?)\b")
    for clause in re.split(r"(?<!\d)\.|\.(?!\d)|[;\n]", norm):
        prefixes = list(_RE_CD_PREFIX.finditer(clause))
        for indice, pref in enumerate(prefixes):
            if _is_match_negated(clause, pref.start(), pref.end()):
                continue
            fin = prefixes[indice + 1].start() if indice + 1 < len(prefixes) else len(clause)
            if indice + 1 < len(prefixes):
                next_header = re.search(
                    r"\b(?:od|oi|os|ojo\s+derecho|ojo\s+izquierdo|ao|ambos\s+ojos)\s*[:=]?\s*$",
                    clause[pref.end():fin],
                )
                if next_header:
                    fin = pref.end() + next_header.start()
            tail = clause[pref.end():fin]
            stop = _RE_CD_STOP.search(tail)
            if stop:
                tail = tail[:stop.start()]
            nums = list(_RE_CD_NUMBER.finditer(tail))
            eyes = list(eye_re.finditer(tail))
            before = clause[:pref.start()]
            header = re.search(r"(od|oi|os|ojo\s+derecho|ojo\s+izquierdo|ao|ambos\s+ojos)\s*[:=]?\s*$", before)
            orientacion_prefija = bool(eyes and nums and eyes[0].start() < nums[0].start())
            for n, numero in enumerate(nums):
                if re.search(r"\b(?:pio|mmhg|dp|a/v)\s*[:=]?\s*$", tail[:numero.start()]):
                    continue
                anterior = nums[n - 1].end() if n else 0
                siguiente = nums[n + 1].start() if n + 1 < len(nums) else len(tail)
                candidatos = [
                    ojo for ojo in eyes
                    if (anterior <= ojo.start() < numero.start() if orientacion_prefija
                        else numero.end() <= ojo.start() < siguiente)
                    and len(tail[min(ojo.end(), numero.end()):max(ojo.start(), numero.start())].split()) <= 3
                ]
                ocular = (candidatos[-1] if orientacion_prefija else candidatos[0]) if candidatos else None
                label = ocular.group(0) if ocular else header.group(1) if header else ""
                if _RE_EYE_AO.fullmatch(label):
                    lados = ("OD", "OI")
                elif _RE_EYE_OD.fullmatch(label):
                    lados = ("OD",)
                elif _RE_EYE_OI.fullmatch(label):
                    lados = ("OI",)
                else:
                    lados = ("",)
                for lado in lados:
                    resultados.setdefault(lado, []).append(float(numero.group(1)))
    return {ojo: max(valores) for ojo, valores in resultados.items()}


def _cd_pares_sin_ojo(text: str) -> list[tuple[float, float]]:
    """Compara pares registrados sin convertir su orden tipografico en ojos."""
    text = re.sub(r"\b(0|1),(\d{1,2})\b", r"\1.\2", text)
    text = re.sub(r"\b([1-9]|10)/10\b", lambda m: str(int(m.group(1)) / 10), text)
    pairs = []
    for clause in _papilar_clausulas(text):
        if _papilar_ojos(clause):
            continue
        for pref in _RE_CD_PREFIX.finditer(clause):
            if not _papilar_actual(clause, pref):
                continue
            tail = clause[pref.end():]
            stop = _RE_CD_STOP.search(tail)
            if stop:
                tail = tail[:stop.start()]
            numbers = list(_RE_CD_NUMBER.finditer(tail))
            if len(numbers) == 2 and re.fullmatch(r"\s*(?:/|y|,)\s*", tail[numbers[0].end():numbers[1].start()]):
                pairs.append(tuple(float(m.group()) for m in numbers))
    return pairs


def _has_high_myopia(req: ImpresionClinicaRequest, eye: str | None = None, threshold: float = -3.00) -> bool:
    if req.refraccion is None:
        return False
    if eye:
        ojo = req.refraccion.od if eye.upper() == "OD" else req.refraccion.oi
        if ojo is None:
            return False
        ee = _equivalente_esferico(ojo.esfera, ojo.cilindro)
        return ee is not None and ee <= threshold
    ee_od = _equivalente_esferico(req.refraccion.od.esfera, req.refraccion.od.cilindro) if req.refraccion.od else None
    ee_oi = _equivalente_esferico(req.refraccion.oi.esfera, req.refraccion.oi.cilindro) if req.refraccion.oi else None
    return (ee_od is not None and ee_od <= threshold) or (ee_oi is not None and ee_oi <= threshold)


# ---------------------------------------------------------------------------
# #4: papila_patologica (A > PALIDEZ+EXCAVACION > PALIDEZ > B > ANTECEDENTE)
# ---------------------------------------------------------------------------

_RE_PAPILA_EDEMA_EXPLICITO = re.compile(
    r"\b("
    r"papiledema|edema\s+de\s+papilas?|edema\s+papilar|edema\s+del\s+disco|"
    r"papilas?\s+edematosas?|discos?\s+edematosos?|papilas?\s+elevadas?|discos?\s+elevados?|"
    r"noia|neuropatia\s+optica\s+isquemica"
    r")\b",
    re.IGNORECASE,
)

_RE_BORDES_ANCLADOS = re.compile(
    r"\b("
    r"(?:bordes|margenes|limites)\s+(?:borrosos|mal\s+definidos|poco\s+definidos|no\s+nitidos|poco\s+nitidos|difuminados)|"
    r"borramiento\s+de\s+(?:los\s+)?bordes"
    r")\b",
    re.IGNORECASE,
)

_RE_SIGNO_EDEMA_VERDADERO = re.compile(
    r"\b("
    r"elevad[ao]s?|hiperemi[ao]s?|congesti[oó]n|congestiv[ao]s?|"
    r"hemorragias?\s+peripapilar(?:es)?|hemorragias?\s+en\s+(?:llama|flama)|"
    r"vasos\s+(?:oscurecidos|obscurecidos|ocultos)|pliegues(?:\s+retinianos)?|exudados\s+peripapilares"
    r")\b",
    re.IGNORECASE,
)

_RE_ATRIBUCION_BENIGNA_PAPILA = re.compile(
    r"\b("
    r"pseudopapiledema|pseudoedema|drusas?\s+(?:del?\s+)?(?:nervio|papila|disco|papilares?)|"
    r"(?:disco|papila)s?\s+inclinad[ao]s?|tilted|fibras?\s+de\s+mielina|mielinizad[ao]s?|"
    r"(?:disco|papila)s?\s+(?:pequeno|pequena|pequenos|pequenas|lleno|llena|crowded)|microdisco|"
    r"hipermetr[oó]p\w*|por\s+miopia|congenit[ao]s?|mala\s+midriasis|sin\s+midriasis"
    r")\b",
    re.IGNORECASE,
)

_RE_SINTOMA_HIC = re.compile(
    r"\b("
    r"o[b]?scurecimientos?\s+visual(?:es)?|zumbido\s+pulsatil|acufeno\s+pulsatil|tinnitus\s+pulsatil|"
    r"diplopia|vision\s+doble|nauseas?|vomitos?|perdida\s+(?:subita|brusca)\s+de\s+(?:la\s+)?vision"
    r")\b",
    re.IGNORECASE,
)

_RE_PALIDEZ = re.compile(
    r"\b("
    r"palidez\s+(?:papilar|de\s+papila|del\s+disco|del\s+anillo|temporal\s+de\s+papila)|"
    r"papilas?\s+palidas?|discos?\s+palidos?|disco\s+optico\s+palido|"
    r"atrofia\s+(?:optica|papilar|del\s+nervio\s+optico)|neuritis\s+optica|"
    r"neuropatia\s+optica(?!\s+glaucomatosa)"
    r")\b",
    re.IGNORECASE,
)

_RE_ANTECEDENTE_OPTICO = re.compile(
    r"\b("
    r"antecedentes?|historia\s+de|previa?|secuela|antigu[ao]s?|conocid[ao]s?|en\s+seguimiento|tratad[ao]s?"
    r")\b",
    re.IGNORECASE,
)

_RE_CLAUSE_SPLIT = re.compile(r"(?<!\d)[.,]|[.,](?!\d)|[;\n]")


def _eval_papila_patologica_info(req: ImpresionClinicaRequest) -> dict:
    if req.clinica is None or not req.clinica.fondo_de_ojo:
        return {"nivel": None, "texto": ""}
    fondo = _texto_hechos_paciente(req.clinica.fondo_de_ojo)
    if not fondo:
        return {"nivel": None, "texto": ""}

    clauses = _RE_CLAUSE_SPLIT.split(fondo)

    has_edema_explicito = False
    has_bordes = False
    has_bordes_con_signo = False
    has_atribucion_benigna = False
    has_palidez = False
    has_antecedente = False
    all_findings_antecedente = True
    any_finding = False
    palidez_clauses = []
    antecedentes = []

    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue
        bordes_locales = False
        signos_locales = False

        for m in _RE_PAPILA_EDEMA_EXPLICITO.finditer(clause):
            if _is_match_negated(clause, m.start(), m.end()):
                continue
            if re.search(r"\bpseudo\s*$", clause[:m.start()]):
                continue
            any_finding = True
            is_ant = bool(_RE_ANTECEDENTE_OPTICO.search(clause))
            if is_ant:
                has_antecedente = True
                antecedentes.append(m.group(0))
            else:
                has_edema_explicito = True
                all_findings_antecedente = False

        for m in _RE_BORDES_ANCLADOS.finditer(clause):
            if _is_match_negated(clause, m.start(), m.end()):
                continue
            if not re.search(r"\b(papilas?|discos?|nervio\s+optico|c\s*/\s*d|cd|e\s*/\s*p)\b", clause):
                continue
            words_before = clause[:m.start()].split()[-4:]
            words_before_str = " ".join(words_before)
            if re.search(r"\b(drusas?|nevus|exudados?|cicatriz(?:es)?|manchas?|atrofia\s+peripapilar|lesion(?:es)?|placas?)\b", words_before_str):
                continue
            any_finding = True
            is_ant = bool(_RE_ANTECEDENTE_OPTICO.search(clause))
            if is_ant:
                has_antecedente = True
            else:
                has_bordes = True
                bordes_locales = True
                all_findings_antecedente = False

        for m in _RE_SIGNO_EDEMA_VERDADERO.finditer(clause):
            if _is_match_negated(clause, m.start(), m.end()):
                continue
            signos_locales = True

        for m in _RE_ATRIBUCION_BENIGNA_PAPILA.finditer(clause):
            if _is_match_negated(clause, m.start(), m.end()):
                continue
            # Ametropia o tecnica de exploracion no describen una papila anomala.
            if re.match(r"(?:hipermetrop|por miopia|congenit|mala midriasis|sin midriasis)", m.group(0)):
                if not bordes_locales:
                    continue
            any_finding = True
            has_atribucion_benigna = True
            all_findings_antecedente = False

        for m in _RE_PALIDEZ.finditer(clause):
            if _is_match_negated(clause, m.start(), m.end()):
                continue
            any_finding = True
            is_ant = bool(_RE_ANTECEDENTE_OPTICO.search(clause))
            if is_ant:
                has_antecedente = True
                antecedentes.append(m.group(0))
            else:
                has_palidez = True
                palidez_clauses.append(clause)
                all_findings_antecedente = False

        if "palidez temporal" in clause:
            m_pt = re.search(r"\bpalidez\s+temporal\b", clause)
            if m_pt and not _is_match_negated(clause, m_pt.start(), m_pt.end()):
                if re.search(r"\b(papilas?|discos?|copa[\s/-]*disco|c\s*/\s*d|cd|e\s*/\s*p)\b", clause):
                    any_finding = True
                    is_ant = bool(_RE_ANTECEDENTE_OPTICO.search(clause))
                    if is_ant:
                        has_antecedente = True
                    else:
                        has_palidez = True
                        palidez_clauses.append(clause)
                        all_findings_antecedente = False
        has_bordes_con_signo |= bordes_locales and signos_locales

    if not any_finding:
        return {"nivel": None, "texto": ""}

    has_sintoma_hic = False
    if req.paciente and req.paciente.motivo_consulta:
        motivo = _texto_hechos_paciente(req.paciente.motivo_consulta)
        for m in _RE_SINTOMA_HIC.finditer(motivo):
            if (not _is_match_negated(motivo, m.start(), m.end())
                    and _certeza_hallazgo(motivo, m) is None):
                has_sintoma_hic = True
                break

    edad = req.paciente.edad if req.paciente else None

    es_nivel_a = (
        has_edema_explicito
        or has_bordes_con_signo
        or ((has_bordes or has_atribucion_benigna) and has_sintoma_hic)
    )
    if es_nivel_a:
        acg = " y, por la edad, el descarte de arteritis de celulas gigantes" if edad is not None and edad >= 50 else ""
        texto = (
            "Hallazgo urgente: se documenta aspecto de edema de papila en el fondo de ojo, "
            "hallazgo que amerita valoracion oftalmologica o neurooftalmologica dentro de las 24 horas "
            f"para verificar si se trata de edema verdadero y, en ese caso, estudiar su causa, incluida la hipertension intracraneal{acg}."
        )
        return {"nivel": "A", "texto": texto}

    if has_palidez:
        cd = _cd_por_ojo(fondo)
        has_excavacion_aumentada = False
        for clause in palidez_clauses:
            ojos = ({"OD", "OI"} if _RE_EYE_AO.search(clause) else
                    {eye for eye, pat in (("OD", _RE_EYE_OD), ("OI", _RE_EYE_OI)) if pat.search(clause)})
            local_cd = _cd_por_ojo(clause)
            has_excavacion_aumentada |= any(cd.get(eye, 0) >= 0.70 for eye in ojos)
            has_excavacion_aumentada |= any(value >= 0.70 for value in local_cd.values())
            has_excavacion_aumentada |= bool(re.search(
                r"\bexcavacion\s+(?:papilar\s+)?(?:aumentada|amplia|glaucomatosa)\b", clause
            ))
        if has_excavacion_aumentada:
            texto = (
                "Se documenta excavacion papilar aumentada acompanada de palidez papilar, "
                "combinacion que amerita valoracion oftalmologica preferente con tonometria, "
                "campimetria e imagen del nervio optico para diferenciar neuropatia glaucomatosa de no glaucomatosa."
            )
            return {"nivel": "PALIDEZ_EXCAVACION", "texto": texto}
        texto = (
            "Se documenta alteracion del nervio optico (palidez, atrofia o neuropatia referida), "
            "hallazgo que amerita valoracion oftalmologica preferente con campimetria e imagen del nervio optico "
            "para determinar su causa, incluida neuroimagen a criterio del especialista."
        )
        return {"nivel": "PALIDEZ", "texto": texto}

    if has_bordes or has_atribucion_benigna:
        texto = (
            "Se documentan bordes papilares poco definidos o sospecha de pseudoedema de papila; "
            "la oftalmoscopia no distingue con fiabilidad pseudoedema de edema verdadero, por lo que amerita "
            "valoracion oftalmologica preferente con imagen del nervio optico (OCT o ecografia) y campimetria, "
            "indicando al paciente adelantarla si presenta oscurecimientos visuales transitorios, zumbido pulsatil o vision doble."
        )
        return {"nivel": "B", "texto": texto}

    if has_antecedente and all_findings_antecedente:
        hallazgo = _join_hallazgos(_dedupe(antecedentes)) or "alteracion papilar"
        texto = (
            f"Se documenta antecedente referido de {hallazgo}, que amerita "
            "verificar su seguimiento oftalmologico o neurologico y adelantar la valoracion si aparece "
            "nueva disminucion visual o dolor con los movimientos oculares."
        )
        return {"nivel": "ANTECEDENTE", "texto": texto}

    return {"nivel": None, "texto": ""}


@_memoize_cond
def _cond_papila_patologica(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: palidez, edema, pseudoedema o antecedente de neuropatia optica."""
    return _eval_papila_patologica_info(req)["nivel"] is not None


def _texto_papila_patologica(req: ImpresionClinicaRequest) -> str:
    return _eval_papila_patologica_info(req)["texto"]


# ---------------------------------------------------------------------------
# #5: glaucoma_asimetrico (Preferente, DPAR lateralizado + asimetria concordante)
# ---------------------------------------------------------------------------

_RE_RED_FLAGS_FONDO = re.compile(r"\b(palid\w*|atrofia|edema|borramiento)\b", re.IGNORECASE)
_RE_RED_FLAGS_CAMPOS = re.compile(r"\b(hemianop\w*|cuadrantanop\w*|bitemporal|homonim\w*|meridiano\s+vertical)\b", re.IGNORECASE)


def _eval_glaucoma_asimetrico_info(req: ImpresionClinicaRequest) -> dict:
    if req.clinica is None or not req.clinica.reflejos_pupilares:
        return {"activa": False, "texto": ""}

    from app.correlaciones.pupilas_motilidad import _hay_dpar, _extract_finding_eye, _TOKENS_DPAR_EXPLICITOS
    pupilas = _texto_hechos_paciente(req.clinica.reflejos_pupilares)
    if not _hay_dpar(pupilas):
        return {"activa": False, "texto": ""}

    tokens_dpar = _TOKENS_DPAR_EXPLICITOS + ("marcus gunn", "marcus-gunn", "dpar", "rapd")
    ojo_dpar = _extract_finding_eye(pupilas, tokens_dpar)
    if ojo_dpar not in ("OD", "OI"):
        return {"activa": False, "texto": ""}

    if not req.clinica.fondo_de_ojo:
        return {"activa": False, "texto": ""}
    fondo = _texto_hechos_paciente(req.clinica.fondo_de_ojo)

    for m in _RE_RED_FLAGS_FONDO.finditer(fondo):
        if not _is_match_negated(fondo, m.start(), m.end()):
            return {"activa": False, "texto": ""}

    if req.paciente and req.paciente.edad is not None and req.paciente.edad < 50:
        return {"activa": False, "texto": ""}

    if req.refraccion:
        from app.correlaciones.refraccion_utils import _av_denominator
        ojo_rx = req.refraccion.od if ojo_dpar == "OD" else req.refraccion.oi
        if ojo_rx and ojo_rx.av_cc:
            denom = _av_denominator(ojo_rx.av_cc)
            if denom is not None and denom > 40:
                return {"activa": False, "texto": ""}

    if req.clinica.confrontacion_campos_visuales:
        campos = _normalize_text(req.clinica.confrontacion_campos_visuales)
        for m in _RE_RED_FLAGS_CAMPOS.finditer(campos):
            if not _is_match_negated(campos, m.start(), m.end()):
                return {"activa": False, "texto": ""}

    contra = "OI" if ojo_dpar == "OD" else "OD"
    cd = _cd_por_ojo(fondo)

    hallazgo_papilar = None

    if ojo_dpar in cd and contra in cd:
        diff = cd[ojo_dpar] - cd[contra]
        if diff >= 0.20 - 1e-6:
            hallazgo_papilar = f"relacion copa/disco de {cd[ojo_dpar]:g}, mayor que la del ojo contralateral ({cd[contra]:g})"

    if hallazgo_papilar is None:
        focales: dict[str, set[str]] = {}
        patrones = (
            (_RE_FOCAL_MUESCA, "muesca del anillo neurorretiniano"),
            (_RE_FOCAL_ADELGAZAMIENTO, "adelgazamiento del anillo neurorretiniano"),
            (re.compile("|".join(re.escape(kw) for kw in _KEYWORDS_ISNT_VIOLADA)),
             "violacion de la regla ISNT"),
        )
        for sub in _RE_CLAUSE_SPLIT.split(fondo):
            if re.search(r"\b(?:palpebral|iridiana?|corneal|pupilar)\b", sub):
                continue
            lados = ({"OD", "OI"} if _RE_EYE_AO.search(sub) else
                     {eye for eye, pat in (("OD", _RE_EYE_OD), ("OI", _RE_EYE_OI)) if pat.search(sub)})
            for patron, nombre in patrones:
                if any(not _is_match_negated(sub, m.start(), m.end())
                       and _certeza_hallazgo(sub, m) is None for m in patron.finditer(sub)):
                    focales.setdefault(nombre, set()).update(lados)
        for nombre, lados in focales.items():
            if ojo_dpar in lados and contra not in lados:
                hallazgo_papilar = nombre
                break

    if not hallazgo_papilar:
        return {"activa": False, "texto": ""}

    ojo_str = "el ojo derecho" if ojo_dpar == "OD" else "el ojo izquierdo"
    certeza = next((c for kw in tokens_dpar for m in _compiled_keyword(kw).finditer(pupilas)
                    if not _is_match_negated(pupilas, m.start(), m.end())
                    and (c := _certeza_hallazgo(pupilas, m))), None)
    defecto = f"{certeza} defecto pupilar aferente relativo" if certeza else "defecto pupilar aferente relativo"
    combinacion = "esta combinacion referida de hallazgos" if certeza else "esta asimetria funcional y estructural de la via visual aferente"
    verbo = "describe" if certeza else "documenta"
    texto = (
        f"Se {verbo} {defecto} en {ojo_str} junto con {hallazgo_papilar} en el mismo ojo; "
        f"{combinacion} amerita valoracion oftalmologica preferente "
        "con tonometria, perimetria y OCT de capa de fibras nerviosas para establecer si su origen es glaucomatoso o de otra causa."
    )
    return {"activa": True, "texto": texto}


@_memoize_cond
def _cond_glaucoma_asimetrico(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: DPAR lateralizado con dano papilar concordante en el mismo ojo."""
    return _eval_glaucoma_asimetrico_info(req)["activa"]


def _texto_glaucoma_asimetrico(req: ImpresionClinicaRequest) -> str:
    return _eval_glaucoma_asimetrico_info(req)["texto"]


# ---------------------------------------------------------------------------
# #6: fondo_glaucomatoso (Funde #7 isnt_violada_papila, niveles A y B)
# ---------------------------------------------------------------------------

_RE_FOCAL_HEMORRAGIA_DISCO = re.compile(
    r"\b(hemorragias?\s+de\s+disco|hemorragias?\s+papilar(?:es)?|hemorragias?\s+peripapilar(?:es)?|hemorragias?\s+del?\s+borde\s+del?\s+disco|hemorragias?\s+de\s+drance)\b",
    re.IGNORECASE,
)
_RE_FOCAL_MUESCA = re.compile(r"\b(muescas?|escotaduras?|notch(?:es)?)\b", re.IGNORECASE)
_RE_FOCAL_ADELGAZAMIENTO = re.compile(
    r"\b(adelgazamiento(?:\s+focal)?(?:\s+del)?\s+(?:anillo|rima)|rima\s+neural\s+adelgazada|anillo\s+neurorretiniano\s+adelgazad[ao]|adelgazamiento\s+neurorretiniano)\b",
    re.IGNORECASE,
)
_RE_FOCAL_CFNR = re.compile(
    r"\b(defecto(?:\s+en\s+cuna)?\s+de\s+(?:la\s+)?capa\s+de\s+fibras|defecto\s+(?:de\s+)?cfnr)\b",
    re.IGNORECASE,
)
_RE_FOCAL_EXCAVACION_AUMENTADA = re.compile(
    r"\b(excavaci[oó]n\s+(?:aumentada|profunda|asimetrica|glaucomatosa)|(?:relacion\s+)?(?:c\s*/\s*d|cd|copa[\s/-]*disco)\s+(?:aumentada|amplia)|asimetria\s+(?:de\s+(?:la\s+)?excavacion|c\s*/\s*d|cd))\b",
    re.IGNORECASE,
)


def _papilar_ojos(clause: str) -> set[str]:
    if _RE_EYE_AO.search(clause):
        return {"OD", "OI"}
    return {eye for eye, pat in (("OD", _RE_EYE_OD), ("OI", _RE_EYE_OI)) if pat.search(clause)}


def _papilar_clausulas(text: str):
    for clause in _RE_CLAUSE_SPLIT.split(text):
        if len(_papilar_ojos(clause)) == 2 and not _RE_EYE_AO.search(clause):
            yield from re.split(r"\s+y\s+|\s+pero\s+", clause)
        else:
            yield clause


def _papilar_actual(clause: str, match: re.Match) -> bool:
    if _is_match_negated(clause, match.start(), match.end()):
        return False
    # La certeza se conserva en el detalle; un plan posterior para otra entidad
    # no niega una muesca o un valor C/D actualmente registrado.
    return not re.search(r"\b(?:antecedente|historia\s+de|resuelt[ao]s?|desaparecid[ao]s?)\b", clause)


def _eval_fondo_glaucomatoso_info(req: ImpresionClinicaRequest) -> dict:
    if _cond_glaucoma_asimetrico(req):
        return {"activa": False, "nivel": None, "texto": ""}

    papila_info = _eval_papila_patologica_info(req)
    if papila_info.get("nivel") == "PALIDEZ_EXCAVACION":
        return {"activa": False, "nivel": None, "texto": ""}

    if req.clinica is None or not req.clinica.fondo_de_ojo:
        return {"activa": False, "nivel": None, "texto": ""}
    fondo = _texto_hechos_paciente(req.clinica.fondo_de_ojo)
    if not fondo:
        return {"activa": False, "nivel": None, "texto": ""}

    cd = _cd_por_ojo(fondo)
    thresholds = {eye: 0.70 for eye in cd}
    for clause in _papilar_clausulas(fondo):
        size = re.search(r"\b(microdiscos?|(?:discos?|papilas?)\s+pequen[oa]s?|macrodiscos?|(?:discos?|papilas?)\s+grandes?)\b", clause)
        if size and _papilar_actual(clause, size):
            eyes = _papilar_ojos(clause)
            threshold = 0.60 if re.search(r"micro|pequen", size.group()) else 0.80
            for eye in cd:
                if not eyes or eye in eyes:
                    thresholds[eye] = threshold

    has_cd_threshold = False
    cd_val_max = 0.0
    cd_eye_max = ""
    for eye_lbl, val in cd.items():
        if val >= thresholds[eye_lbl] - 1e-6:
            has_cd_threshold = True
            if val > cd_val_max:
                cd_val_max = val
                cd_eye_max = eye_lbl

    has_asymmetry = False
    diff_cd = 0.0
    unlabeled_pairs = _cd_pares_sin_ojo(fondo)
    unnamed_asymmetry = next((pair for pair in unlabeled_pairs if abs(pair[0] - pair[1]) >= 0.20 - 1e-6), None)
    if "OD" in cd and "OI" in cd:
        unnamed_asymmetry = None
        diff_cd = abs(cd["OD"] - cd["OI"])
        tamano_distinto = bool(re.search(r"\b(tamano\s+distinto|tamanos\s+distintos|diferente\s+tamano|diferentes\s+tamanos|asimetria\s+de\s+tamano)\b", fondo))
        if diff_cd >= 0.20 - 1e-6 and not tamano_distinto:
            has_asymmetry = True
    elif unnamed_asymmetry and not re.search(r"\b(?:tamano\s+distinto|tamanos\s+distintos|diferente\s+tamano|diferentes\s+tamanos|asimetria\s+de\s+tamano)\b", fondo):
        has_asymmetry = True
        diff_cd = abs(unnamed_asymmetry[0] - unnamed_asymmetry[1])

    clauses = _papilar_clausulas(fondo)
    has_hemorragia = False
    has_muesca = False
    muesca_detail = ""
    has_adelgazamiento = False
    has_cfnr = False
    has_excavacion_aumentada = False
    has_isnt = False
    focal_eyes: set[str] = set()
    detail_eyes: dict[str, set[str]] = {}
    focal_details: dict[str, list[str]] = {}

    def remember(kind: str, clause: str, match: re.Match, detail: str):
        eyes = _papilar_ojos(clause)
        focal_eyes.update(eyes)
        detail_eyes.setdefault(kind, set()).update(eyes)
        suffix = " en AO" if eyes == {"OD", "OI"} else f" en {next(iter(eyes))}" if eyes else ""
        certainty = _certeza_hallazgo(clause, match)
        description = (f"{certainty} " if certainty else "") + detail + suffix
        focal_details.setdefault(kind, []).append(description)

    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue

        m = next((m for m in _RE_FOCAL_HEMORRAGIA_DISCO.finditer(clause) if _papilar_actual(clause, m)), None)
        if m:
            has_hemorragia = True
            remember("hemorragia", clause, m, "hemorragia en el borde del disco optico")

        m_ast = re.search(r"\bhemorragias?\s+en\s+astilla\b", clause)
        if m_ast and _papilar_actual(clause, m_ast):
            if re.search(r"\b(papilas?|discos?|peripapilar(?:es)?|anillo|rima|muesca|escotadura|notch|excavaci[oó]n|c\s*/\s*d|cd|e\s*/\s*p)\b", clause):
                has_hemorragia = True
                remember("hemorragia", clause, m_ast, m_ast.group())

        muescas = list(_RE_FOCAL_MUESCA.finditer(clause))
        for index, m in enumerate(muescas):
            if not _papilar_actual(clause, m) or re.search(r"\b(palpebral|iridiana|corneal|pupilar)\b", clause):
                continue
            has_muesca = True
            end = muescas[index + 1].start() if index + 1 < len(muescas) else len(clause)
            local = clause[m.end():end] if len(muescas) > 1 else clause
            sec_m = re.search(r"\b(inferotemporal|inferonasal|superotemporal|superonasal|inferior|superior|temporal|nasal)\b", local)
            term = m.group(1).lower()
            if sec_m:
                muesca_detail = f"{term} {sec_m.group(1)}"
            else:
                muesca_detail = f"{term} del anillo neurorretiniano"
            remember("muesca", clause, m, muesca_detail)

        m = next((m for m in _RE_FOCAL_ADELGAZAMIENTO.finditer(clause) if _papilar_actual(clause, m)), None)
        if m:
            has_adelgazamiento = True
            remember("adelgazamiento", clause, m, m.group())

        m = _RE_FOCAL_CFNR.search(clause)
        if m and _papilar_actual(clause, m):
            has_cfnr = True
            remember("cfnr", clause, m, m.group())

        m = _RE_FOCAL_EXCAVACION_AUMENTADA.search(clause)
        if m and _papilar_actual(clause, m):
            if "fisiologic" not in clause:
                has_excavacion_aumentada = True
                remember("excavacion", clause, m, m.group())

        for kw in _KEYWORDS_ISNT_VIOLADA:
            pat = r"\b" + re.escape(kw) + r"\b"
            m_isnt = re.search(pat, clause)
            if m_isnt and _papilar_actual(clause, m_isnt):
                has_isnt = True
                remember("isnt", clause, m_isnt, "violacion de la regla ISNT")
                break

    has_focal_sign = has_hemorragia or has_muesca or has_adelgazamiento or has_cfnr or has_excavacion_aumentada

    if not (has_cd_threshold or has_asymmetry or has_focal_sign or has_isnt):
        return {"activa": False, "nivel": None, "texto": ""}

    if has_isnt and not (has_cd_threshold or has_asymmetry or has_focal_sign):
        texto = (
            "Se documenta en el fondo de ojo violacion de la regla ISNT como hallazgo papilar aislado, "
            "que amerita completar estudio de glaucoma con tonometria, campimetria y OCT de nervio optico, "
            "con valoracion oftalmologica si alguno resulta alterado."
        )
        return {"activa": True, "nivel": "B", "texto": texto}

    detalles = []
    if has_cd_threshold:
        vertical_str = " vertical" if "vertical" in fondo else ""
        if "OD" in cd and "OI" in cd and cd["OD"] == cd["OI"]:
            detalles.append(f"relacion copa/disco{vertical_str} de {cd_val_max:g} en AO")
        elif cd_eye_max:
            detalles.append(f"relacion copa/disco{vertical_str} de {cd_val_max:g} en {cd_eye_max}")
        else:
            detalles.append(f"relacion copa/disco{vertical_str} de {cd_val_max:g}")

    if has_asymmetry:
        if unnamed_asymmetry:
            detalles.append(f"asimetria entre los valores copa/disco {unnamed_asymmetry[0]:g} y {unnamed_asymmetry[1]:g}, con diferencia de {diff_cd:g} y sin lateralidad documentada")
        else:
            detalles.append(f"asimetria de la relacion copa/disco de {diff_cd:g} entre ojos")

    for kind in ("hemorragia", "muesca", "adelgazamiento", "cfnr", "excavacion", "isnt"):
        detalles.extend(_dedupe(focal_details.get(kind, [])))

    detalle_str = _join_hallazgos(detalles)

    tamano_str = ""
    if has_cd_threshold or has_asymmetry:
        tamano_str = "; la relacion copa/disco debe interpretarse segun el tamano del disco"

    miopia_str = ""
    affected_eyes = {eye for eye, val in cd.items() if eye and val >= thresholds[eye] - 1e-6} | focal_eyes
    if has_asymmetry and "OD" in cd and "OI" in cd:
        affected_eyes.update(eye for eye in ("OD", "OI") if cd[eye] == max(cd["OD"], cd["OI"]))
    if any(_has_high_myopia(req, eye=eye, threshold=-3.00) for eye in affected_eyes):
        miopia_str = " La miopia registrada constituye un factor de riesgo adicional."

    texto = (
        f"Se documenta en el fondo de ojo {detalle_str}, hallazgo papilar que amerita valoracion oftalmologica "
        f"para estudio de glaucoma con tonometria, gonioscopia, paquimetria, campimetria y OCT de nervio optico{tamano_str}.{miopia_str}"
    )
    return {"activa": True, "nivel": "A", "texto": texto}


@_memoize_cond
def _cond_fondo_glaucomatoso(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: sospecha papilar de glaucoma (C/D aumentada, asimetria, signos focales o regla ISNT)."""
    return _eval_fondo_glaucomatoso_info(req)["activa"]


def _texto_fondo_glaucomatoso(req: ImpresionClinicaRequest) -> str:
    return _eval_fondo_glaucomatoso_info(req)["texto"]


# ---------------------------------------------------------------------------
# #8: fondo_macular_dmae (A > A2 > B-TRATADA > C > B)
# ---------------------------------------------------------------------------

_EXCLUSIONES_DRUSAS_NO_MACULARES = (
    "drusas de papila", "drusas papilar", "drusas papilares",
    "drusas del disco", "drusa de papila", "drusa del disco",
    "drusas en papila", "drusas del nervio optico", "drusas de nervio optico",
    "drusas en nervio optico", "drusas peripapilares", "drusa peripapilar",
)
_DRUSAS_MACULARES_EXPLICITAS = (
    "drusas maculares", "drusa macular", "drusas en macula", "drusa en macula",
    "drusas paramaculares", "drusa paramacular", "drusas blandas", "drusa blanda",
    "drusas duras", "drusa dura",
)

_RE_MACULAR_NEOVASCULAR = re.compile(
    r"\b("
    r"membranas?\s+neovascular(?:es)?(?:\s+(?:coroidea|macular|subretiniana))?|"
    r"neovascularizacion\s+(?:coroidea|macular|subretiniana)|"
    r"neovasos\s+(?:coroideos?|maculares?|subretinianos?)|"
    r"mnvc|mnv|cnv|(?:dmae|dmre)\s+(?:humeda|exudativa|neovascular)|"
    r"hemorragias?\s+(?:subretinianas?|submacular(?:es)?)"
    r")\b",
    re.IGNORECASE,
)

_RE_MACULAR_EXUDATIVO = re.compile(
    r"\b("
    r"liquido\s+(?:subretiniano|intrarretiniano|intraretiniano)|fluido\s+subretiniano|"
    r"desprendimiento\s+(?:del?\s+epitelio\s+pigmentario|neurosensorial|del?\s+neuroepitelio)|dep|"
    r"coroidopatia\s+serosa|corioretinopatia\s+serosa|coriorretinopatia\s+serosa|"
    r"retinopatia\s+serosa|serosa\s+central|desprendimiento\s+seroso|csc|cscr|crsc|csr|"
    r"hemorragias?\s+macular(?:es)?|exudados\s+(?:duros|lipidicos)\s+macular(?:es)?"
    r")\b",
    re.IGNORECASE,
)

_RE_TRATADA_INACTIVA = re.compile(
    r"\b(inactiv[ao]s?|cicatriz(?:\s+disciforme)?|fibrosis(?:\s+subretiniana)?|tratad[ao]s?|en\s+tratamiento|antiangiog[eé]nic\w*|anti-?vegf)\b",
    re.IGNORECASE,
)

_RE_DRUSAS_ALL = re.compile(r"\b(drusas?|drusen|pseudodrusas?|drusas?\s+reticulares?)\b", re.IGNORECASE)
_RE_DRUSAS_BENIGNAS = re.compile(r"\b(duras?|peque[nñ]as?|finas?|aisladas?|escasas?|puntiformes?)\b", re.IGNORECASE)
_RE_DRUSAS_PATOLOGICAS = re.compile(r"\b(blandas?|grandes?|medianas?|confluentes?|reticulares?)\b", re.IGNORECASE)

_RE_PIGMENTO_EPR = re.compile(
    r"\b(alteraci[oó]n\s+pigmentaria|alteraciones\s+pigmentarias|cambios\s+pigmentarios|hiperpigmentaci[oó]n|hipopigmentaci[oó]n|moteado\s+pigmentario|alteraci[oó]n\s+del\s+epr|atrofia\s+del\s+epr|hiperplasia\s+del\s+epr)\b",
    re.IGNORECASE,
)

_RE_MACULAR_SECA_DIAGNOSTICA = re.compile(
    r"\b(atrofia\s+geografica|cicatriz\s+disciforme|fibrosis\s+subretiniana|dmae|dmre|degeneracion\s+macular|maculopatia\s+(?:relacionada|asociada)\s+(?:con|a)\s+la\s+edad|maculopatia\s+senil)\b",
    re.IGNORECASE,
)

_RE_CONTEXTO_MIOPICO = re.compile(r"\b(miop[ií]\w*|miope\w*|fuchs|estrias?\s+de\s+laca)\b", re.IGNORECASE)


def _macular_compatible(eyes_a: set[str], eyes_b: set[str]) -> bool:
    return not eyes_a or not eyes_b or bool(eyes_a & eyes_b)


def _macular_miopia(req: ImpresionClinicaRequest, eyes: set[str]) -> bool:
    # Sin lateralidad no se transfiere el factor de riesgo de un solo ojo.
    targets = eyes or {"OD", "OI"}
    return bool(targets) and all(_has_high_myopia(req, eye=eye, threshold=-6.00) for eye in targets)


def _macular_factual(clause: str, match: re.Match, admitir_incierto: bool = True) -> bool:
    certeza = _certeza_hallazgo(clause, match)
    return not _is_match_negated(clause, match.start(), match.end()) and not re.search(
        r"\b(antecedente|resuelt[ao]s?|desaparecid[ao]s?)\b", clause,
    ) and certeza != "a descartar" and (admitir_incierto or certeza is None)


def _macular_sintomas(req: ImpresionClinicaRequest) -> list[dict]:
    """Evidencia usada por A2. Comparte con #16 el vocabulario de percepciones de la
    rejilla y con todas las reglas cualitativas la convencion de cronologia."""
    from app.correlaciones.campos_amsler import _analisis_amsler
    analysis = _analisis_amsler(req)
    records = []
    for p in analysis.firmes + analysis.episodios + analysis.dudosos + analysis.contextos:
        h = p.base
        eyes = {"OD", "OI"} if h.ojo in ("AO", "AMBOS") else {h.ojo} if h.ojo in ("OD", "OI") else set()
        reliable = not (h.incierto or h.por_descartar)
        records.append({"fuente": "Amsler" if p.fuente == "rejilla" else "motivo de consulta",
                        "clausula": h.contexto.strip(), "ojos": eyes,
                        "reciente": reliable and h.evolucion == "cambio reciente", "fiable": reliable})
    return records


def _eval_fondo_macular_dmae_info(req: ImpresionClinicaRequest) -> dict:
    fondo = _texto_hechos_paciente(req.clinica.fondo_de_ojo) if req.clinica else ""
    empty = {"activa": False, "nivel": None, "texto": ""}
    if not fondo:
        return empty
    edad = req.paciente.edad if req.paciente else None
    clauses = list(_papilar_clausulas(fondo))
    drusas = []
    secos = []
    pigmentos = []
    activos = []
    tratados = []

    # Primero los hechos B: no se usa una palabra drusa negada o papilar como factor.
    for clause in clauses:
        eyes = _papilar_ojos(clause)
        for m in _RE_DRUSAS_ALL.finditer(clause):
            if not _macular_factual(clause, m):
                continue
            if any(dp in clause for dp in _EXCLUSIONES_DRUSAS_NO_MACULARES):
                continue
            if re.search(r"\b(periferic\w*|peripapilar\w*)\b", clause):
                continue
            benign = bool(_RE_DRUSAS_BENIGNAS.search(clause)) and not _RE_DRUSAS_PATOLOGICAS.search(clause)
            drusas.append({"ojos": eyes, "clausula": clause.strip(), "benigna": benign})
        for m in _RE_PIGMENTO_EPR.finditer(clause):
            if (_macular_factual(clause, m)
                    and re.search(r"\b(macula|maculares?|fovea|foveal|parafoveal|perifoveal|yuxtafoveal|polo\s+posterior)\b", clause)
                    and not re.search(r"\b(periferi\w*|peripapilar|sal\s+y\s+pimienta|espicula)\b", clause)):
                pigmentos.append({"ojos": eyes, "clausula": clause.strip()})
        for m in _RE_MACULAR_SECA_DIAGNOSTICA.finditer(clause):
            if _macular_factual(clause, m) and not _RE_CONTEXTO_MIOPICO.search(clause):
                secos.append({"ojos": eyes, "clausula": clause.strip()})

    tokens_b = [d for d in drusas if not d["benigna"] and not _RE_CONTEXTO_MIOPICO.search(d["clausula"])] + secos
    for pigmento in pigmentos:
        if any(_macular_compatible(pigmento["ojos"], d["ojos"]) for d in drusas):
            tokens_b.append(pigmento)

    for clause in clauses:
        eyes = _papilar_ojos(clause)
        local_drusas = any(_macular_compatible(eyes, d["ojos"]) for d in drusas)
        for pattern, conditional in ((_RE_MACULAR_NEOVASCULAR, False), (_RE_MACULAR_EXUDATIVO, True)):
            for m in pattern.finditer(clause):
                if not _macular_factual(clause, m):
                    continue
                term = m.group(1).lower()
                if re.search(r"\b(iris|iridiana|corneal|cornea|angulo\s+iridocorneal)\b", clause):
                    continue
                if conditional:
                    if "hemorragia" in term and re.search(r"\b(puntiforme|en\s+mancha|en\s+punto|en\s+llama|en\s+flama|en\s+astilla)\b", clause):
                        continue
                    if "exudados" in term and not local_drusas:
                        continue
                    if "desprendimiento" in term and re.search(r"\b(de\s+retina|regmatogeno|periferic\w*|desgarro|bolsa|cuadrante)\b", clause):
                        continue
                    if not (edad is None or edad >= 50 or local_drusas or _macular_miopia(req, eyes)):
                        continue
                treated = any(
                    not _is_match_negated(clause, t.start(), t.end()) for t in _RE_TRATADA_INACTIVA.finditer(clause)
                )
                # Tratamiento no cancela una actividad nueva expresamente registrada.
                new_activity = bool(re.search(r"\b(?:activ[ao]|reactivad[ao]|nuev[oa]s?|recientes?)\b", clause))
                target = tratados if treated and not new_activity else activos
                target.append({"ojos": eyes, "clausula": clause.strip(), "termino": term, "neovascular": not conditional})

    def detalles(records):
        return _join_hallazgos(_dedupe(r["clausula"] for r in records))

    # Actividad hemorragica/exudativa dentro de una lesion macular miopica:
    # #9 no debe descartarla dejando el caso sin la evaluacion prioritaria de #8.
    for clause in clauses:
        if not (_RE_CONTEXTO_MIOPICO.search(clause) and re.search(r"\b(macul\w*|fuchs|estrias?\s+de\s+laca)\b", clause)):
            continue
        for m in re.finditer(r"\b(hemorragias?|liquido|fluido)\b", clause):
            if _macular_factual(clause, m):
                record = {"ojos": _papilar_ojos(clause), "clausula": clause.strip(), "termino": m.group(), "neovascular": False}
                target = tratados if _RE_TRATADA_INACTIVA.search(clause) and not re.search(r"\b(nuev[oa]s?|activ[ao])\b", clause) else activos
                target.append(record)

    if activos:
        texto = (
            "Hallazgo urgente: se documentan en la region macular hallazgos exudativos, hemorragicos o neovasculares "
            f"({detalles(activos)}), que ameritan derivacion prioritaria a retina gestionada en un plazo maximo de 1 dia habil "
            "para OCT macular y valoracion de tratamiento."
        )
        return {"activa": True, "nivel": "A", "texto": texto}

    sintomas = _macular_sintomas(req) if tokens_b else []
    nuevos = [s for s in sintomas if s["reciente"] and any(_macular_compatible(s["ojos"], b["ojos"]) for b in tokens_b)]
    if nuevos:
        # Conservar tambien evidencia independiente, con su ojo y tiempo originales.
        evidencia = _join_hallazgos(_dedupe(f'{s["fuente"]}: {s["clausula"]}' for s in sintomas))
        texto = (
            f"Hallazgo urgente: se documentan hallazgos maculares ({detalles(tokens_b)}) y se refiere {evidencia}. "
            "El cambio visual reciente en este contexto amerita derivacion prioritaria a retina gestionada en un plazo maximo "
            "de 1 dia habil para OCT macular."
        )
        return {"activa": True, "nivel": "A2", "texto": texto,
                "amsler_absorbido": bool(sintomas) and all(s["fiable"] for s in sintomas)}

    if tratados:
        if all(r["neovascular"] for r in tratados):
            texto = (
                "Se documenta enfermedad macular neovascular referida como tratada o inactiva, "
                "que amerita mantener el seguimiento retinologico establecido y acudir a revision "
                "sin esperar a la cita programada ante cambios visuales."
            )
        else:
            texto = (
                f"Se documenta antecedente macular referido como tratado o inactivo ({detalles(tratados)}), "
                "que amerita mantener el seguimiento retinologico establecido y reconsultar ante cambios visuales."
            )
        return {"activa": True, "nivel": "B-TRATADA", "texto": texto}

    if tokens_b:
        if edad is not None and edad < 50:
            hallazgo = "depositos tipo drusas" if drusas else "una alteracion macular"
            texto = (
                f"Se documentan {hallazgo} en la region macular en paciente menor de 50 anos, "
                "hallazgo atipico para la edad que amerita valoracion retinologica programada con OCT e imagen multimodal para caracterizacion."
            )
            return {"activa": True, "nivel": "C", "texto": texto}
        texto = (
            "Se documentan drusas o alteraciones pigmentarias o atroficas maculares, que ameritan valoracion oftalmologica programada "
            "con retinografia u OCT macular para estadificacion y para definir la indicacion de suplementacion antioxidante segun estadio, "
            "junto con educacion en autocontrol con rejilla de Amsler para acudir a revision sin esperar a la cita programada si aparece distorsion o mancha central nueva."
        )
        return {"activa": True, "nivel": "B", "texto": texto}
    return empty

@_memoize_cond
def _cond_fondo_macular_dmae(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: DMAE exudativa/neovascular, drusas con distorsion o degeneracion seca."""
    return _eval_fondo_macular_dmae_info(req)["activa"]


def _texto_fondo_macular_dmae(req: ImpresionClinicaRequest) -> str:
    return _eval_fondo_macular_dmae_info(req)["texto"]


# ---------------------------------------------------------------------------
# #9: fondo_macular_otros (Preferente P vs Programado R)
# ---------------------------------------------------------------------------

_RE_MACULAR_OTROS_P = re.compile(
    r"\b("
    r"edema\s+(?:macular|de\s+(?:la\s+)?macula|en\s+(?:la\s+)?macula|foveal|cistoide|quistico)|"
    r"macula\s+(?:con\s+edema|edematosa|engrosada)|engrosamiento\s+(?:macular|foveal)|"
    r"irvine[\s-]*gass|maculopatia\s+diabetica|emq|emc|emd|emcs|"
    r"quistes?\s+(?:macular(?:es)?|foveal(?:es)?|intrarretinianos?)|espacios\s+quisticos|"
    r"agujeros?\s+de\s+espesor\s+completo|agujeros?\s+foveal(?:es)?|agujeros?\s+macular(?:es)?|"
    r"desgarro\s+del?\s+(?:epitelio\s+pigmentario|epr)|rotura\s+del?\s+epr|"
    r"desprendimiento\s+(?:seroso|neurosensorial|del?\s+neuroepitelio)|"
    r"liquido\s+subretiniano|fluido\s+subretiniano|"
    r"coroidopatia\s+serosa|corioretinopatia\s+serosa|coriorretinopatia\s+serosa|retinopatia\s+serosa|serosa\s+central|"
    r"csc|cscr|crsc|csr"
    r")\b",
    re.IGNORECASE,
)

_RE_MACULAR_OTROS_R = re.compile(
    r"\b("
    r"membranas?\s+epirr?etinianas?|mer|gliosis\s+(?:macular|premacular|epirretiniana)|"
    r"pucker|celofan|maculopatia\s+en\s+celofan|traccion\s+v[ií]treo[\s-]*macular|tvm|"
    r"agujeros?\s+(?:macular(?:es)?\s+)?lamell?ar(?:es)?|pseudoagujeros?(?:\s+macular(?:es)?)?|seudoagujeros?(?:\s+macular(?:es)?)?|"
    r"foveosquisis|maculosquisis|retinosquisis\s+(?:macular|foveal)|schisis\s+macular|esquisis\s+macular|"
    r"maculopatia\s+miopica|miopia\s+patologica|degeneracion\s+miopica|estrias?\s+de\s+laca|estafiloma\s+posterior|mancha\s+de\s+fuchs|"
    r"atrofia\s+(?:coriorretiniana|corioretiniana)"
    r")\b",
    re.IGNORECASE,
)


def _eval_fondo_macular_otros_info(req: ImpresionClinicaRequest) -> dict:
    if req.clinica is None or not req.clinica.fondo_de_ojo:
        return {"activa": False, "nivel": None, "texto": ""}
    fondo = _texto_hechos_paciente(req.clinica.fondo_de_ojo)
    if not fondo:
        return {"activa": False, "nivel": None, "texto": ""}

    edad = req.paciente.edad if req.paciente else None
    clauses = _papilar_clausulas(fondo)
    has_p = False
    has_r = False

    for clause in clauses:
        clause = clause.strip()
        if not clause:
            continue
        eyes = _papilar_ojos(clause)
        is_myopic = _macular_miopia(req, eyes)
        for m in _RE_MACULAR_OTROS_P.finditer(clause):
            if not _macular_factual(clause, m, admitir_incierto=False):
                continue
            term = m.group(1).lower()

            # #3 recoge el edema macular actual del mismo ojo en su aviso.
            # Una MER, agujero u otro hallazgo independiente se conserva.
            if (any(t in term for t in ("edema", "edematosa", "engrosada", "engrosamiento", "emq", "emc", "emd"))
                    and eyes and all(_ojo_tiene_oclusion_vascular_retiniana(fondo, eye) for eye in eyes)):
                continue

            if "agujero" in term and re.search(r"\b(lamell?ar(?:es)?|pseudo|seudo)\b", clause):
                continue

            if "desprendimiento" in term and re.search(r"\b(de\s+retina|regmatogeno|periferic\w*|desgarro|bolsa|cuadrante)\b", clause):
                continue

            if any(k in term for k in ("liquido", "fluido", "seroso", "serosa", "csc", "csr", "neurosensorial", "neuroepitelio")):
                has_drusas = any(
                    _macular_factual(other, d)
                    and _macular_compatible(eyes, _papilar_ojos(other))
                    and not any(dp in other for dp in _EXCLUSIONES_DRUSAS_NO_MACULARES)
                    for other in _papilar_clausulas(fondo) for d in _RE_DRUSAS_ALL.finditer(other)
                )
                if edad is None or edad >= 50 or is_myopic or has_drusas:
                    continue

            has_p = True
            break

        for m in _RE_MACULAR_OTROS_R.finditer(clause):
            if not _macular_factual(clause, m, admitir_incierto=False):
                continue
            term = m.group(1).lower()

            if "atrofia" in term:
                if "periferic" in clause:
                    continue
                if not re.search(r"\b(macul\w*|difusa|parches|polo\s+posterior|miop\w*)\b", clause) and not is_myopic:
                    continue

            if _RE_CONTEXTO_MIOPICO.search(clause) and any(
                _macular_factual(clause, activity)
                for activity in re.finditer(r"\b(hemorragias?|liquido|fluido)\b", clause)
            ):
                continue

            has_r = True
            break

        # El pigmento macular aislado no acredita DMAE: #8C2 lo remite a #9.
        for m in _RE_PIGMENTO_EPR.finditer(clause):
            if (_macular_factual(clause, m, admitir_incierto=False)
                    and re.search(r"\b(?:macula|maculares?|fovea|foveal|polo\s+posterior)\b", clause)
                    and not re.search(r"\b(?:periferi\w*|peripapilar|sal\s+y\s+pimienta|espicula)\b", clause)
                    and not any(_macular_factual(other, d) and _macular_compatible(eyes, _papilar_ojos(other))
                                for other in _papilar_clausulas(fondo) for d in _RE_DRUSAS_ALL.finditer(other))):
                has_r = True

    if not has_p and not has_r:
        return {"activa": False, "nivel": None, "texto": ""}

    if has_p:
        texto = (
            "En la region macular se documenta alteracion estructural que puede comprometer "
            "la vision central y amerita OCT macular y valoracion retinologica preferente."
        )
        return {"activa": True, "nivel": "P", "texto": texto}

    if has_r:
        texto = (
            "En la region macular se documenta alteracion estructural que amerita OCT macular "
            "y valoracion retinologica programada, con reconsulta si aparece distorsion o disminucion de la vision central."
        )
        return {"activa": True, "nivel": "R", "texto": texto}

    return {"activa": False, "nivel": None, "texto": ""}


@_memoize_cond
def _cond_fondo_macular_otros(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: patologia macular no degenerativa senil (edema macular, MER, agujero, CSC)."""
    return _eval_fondo_macular_otros_info(req)["activa"]


def _texto_fondo_macular_otros(req: ImpresionClinicaRequest) -> str:
    return _eval_fondo_macular_otros_info(req)["texto"]


# ---------------------------------------------------------------------------
# #10: fondo_hipertensivo (NICE NG136 urgente / signos vasculares objetivos)
# ---------------------------------------------------------------------------

_RE_FONDO_HIPERTENSIVO_CLAUSE_SPLIT = re.compile(r"[\.\;\,\n\|]+|\by\b|\be\b|\bpero\b", re.IGNORECASE)
_RE_NEGADOR_INICIAL = re.compile(
    r"^\s*(sin(?:\s+evidencia(?:\s+de)?|\s+signos?\s+de|\s+datos\s+de)?|"
    r"no\s+(?:se\s+)?(?:observa\w*|aprecia\w*|evidencia\w*|documenta\w*|detecta\w*|hay)|niega|ausencia\s+de|libre\s+de)\b",
    re.IGNORECASE)


class _ClausulasHipertensivas:
    """Compatibilidad con `_RE_FONDO_HIPERTENSIVO_CLAUSE_SPLIT.split(texto)`, pero una lista unida por
    y/e (`Sin evidencia de A y B`) conserva el negador: las coordinadas siguen bajo la misma negacion."""

    @staticmethod
    def split(texto: str) -> list[str]:
        clausulas: list[str] = []
        for segmento in re.split(r"[\.\;\,\n\|]+", texto):
            partes = re.split(r"(\by\b|\be\b|\bpero\b)", segmento, flags=re.IGNORECASE)
            negador = None
            for i in range(0, len(partes), 2):
                parte, separador = partes[i], (partes[i - 1].lower() if i else None)
                if separador == "pero":
                    negador = None
                inicial = _RE_NEGADOR_INICIAL.match(parte)
                if inicial:
                    negador = inicial.group(1)
                elif (negador and separador in ("y", "e")
                      and not re.match(r"\s*(?:con|presenta\w*|se\s+observa\w*)\b", parte, re.IGNORECASE)):
                    parte = f"{negador} {parte.strip()}"
                clausulas.append(parte)
        return clausulas


_RE_FONDO_HIPERTENSIVO_CLAUSE_SPLIT = _ClausulasHipertensivas()

_RE_ESTRECHAMIENTO_ARTERIOLAR = re.compile(
    r"\b(?:estrechamiento|adelgazamiento|constricci[oó]n)\s+(?:focal\s+|generalizad\w*\s+)?(?:arteriolar\w*|arterial\w*)(?:\s+focal|\s+generalizad\w*)?\b"
    r"|\b(?:arteriolas?|arterias?)\s+(?:con\s+)?(?:estrechamiento|adelgazamiento|constricci[oó]n)(?:\s+(?:focal|generalizad\w*))?\b"
    r"|\b(?:estrechamiento|adelgazamiento)\s+(?:de\s+)?(?:calibre\s+)?arteriolar(?:\s+focal|\s+generalizad\w*)?\b",
    re.IGNORECASE,
)

_RE_RELACION_AV_DISMINUIDA = re.compile(
    r"\b(?:relaci[oó]n\s+)?(?:a[\/-]v|av|arteria[\s\/-]*vena|arteriovenosa)\s+(?:muy\s+)?(?:disminuida|reducida|invertida|<|menor|baja|\b1[\/:](?:3|4)\b)\b"
    r"|\b(?:relaci[oó]n\s+)(?:a[\/-]v|av)\s+(?:de\s+)?(?:1[\/:](?:3|4))\b",
    re.IGNORECASE,
)

_RE_CAMBIOS_PARED = re.compile(
    r"\b(?:(?:reflejo\s+en\s+|arteriolas?\s+en\s+)?(?:hilos?|alambres?)\s+de\s+(?:cobre|plata))\b"
    r"|\b(?:arteriolas?\s+hilos?\s+de\s+(?:cobre|plata))\b",
    re.IGNORECASE,
)

_RE_CRUCE_PATOLOGICO = re.compile(
    r"\b(?:cruces?|entrecruzamientos?)\s+(?:a[\/-]v|av|arteriovenos\w*)\s+(?:con\s+|y\s+)?(?:compresi[oó]n|pinzamiento|afilamiento|desviaci[oó]n|deflexi[oó]n|muesca|entalladura)\b"
    r"|\b(?:compresi[oó]n|pinzamiento|desviaci[oó]n|deflexi[oó]n|muesca)\s+(?:en\s+|a\s+nivel\s+de\s+)?(?:los?\s+)?(?:cruces?|entrecruzamientos?)\s+(?:a[\/-]v|av|arteriovenos\w*)\b",
    re.IGNORECASE,
)

_RE_SIGNOS_EPONIMOS = re.compile(
    r"\b(?:"
    r"(?:signo\s+de\s+gunn|gunn\s+(?:positivo|patol[oó]gico|\+|presente)|cruces?\s+(?:a[\/-]v\s+)?con\s+gunn)"
    r"|(?:signo\s+de\s+salus|salus\s+(?:positivo|patol[oó]gico|\+|en\s+cruce|presente)|cruces?\s+(?:a[\/-]v\s+)?con\s+salus)"
    r"|(?:signo\s+de\s+bonnet|bonnet\s+(?:positivo|patol[oó]gico|\+|en\s+cruce|presente)|cruces?\s+(?:a[\/-]v\s+)?con\s+bonnet)"
    r")\b",
    re.IGNORECASE,
)

_RE_NORMAL_OR_PRESERVED_CROSSINGS = re.compile(
    r"\b(?:cruces?|entrecruzamientos?)\s+(?:a[\/-]v|av|arteriovenos\w*)\s+(?:conservad\w*|normal\w*|fisiol[oó]gic\w*|sin\s+(?:compresi[oó]n|pinzamiento|alteraci[oó]n|patolog[ií]a)|presentes?,\s*sin\s+alteraciones?|libres)\b"
    r"|\b(?:cruces?|entrecruzamientos?)\s+(?:a[\/-]v|av|arteriovenos\w*)\s+presentes?\b(?!\s+(?:con\s+)?(?:compresi[oó]n|pinzamiento|afilamiento|desviaci[oó]n|deflexi[oó]n|muesca|entalladura))"
    r"|\b(?:sin|no\s+se\s+observan?)\s+(?:cruces?\s+(?:a[\/-]v\s+)?patol[oó]gicos?|pinzamiento|alteraciones?\s+vasculares?)\b",
    re.IGNORECASE,
)

_RE_ANTECEDENTE_RESUELTO = re.compile(
    r"\b(?:antecedentes?|historia)\s+de\s+[^.;,]*?(?:resuelt[ao]|remitid[ao]|curad[ao]|inactiv[ao]|pasad[ao])\b",
    re.IGNORECASE,
)

_RE_PA_VALUE = re.compile(
    r"\b(?:pa|ta|t\/a|presi[oó]n(?:\s+arterial)?|tensi[oó]n(?:\s+arterial)?|cifras?(?:\s+tensionales)?|toma|medici[oó]n|registro)\s*(?:hoy|actual|en\s+consulta|en\s+toma|registrada|segund\w*|de|:)?\s*(\d{2,3})\s*[\/xXyY\-y\s]+\s*(\d{2,3})(?:\s*mmHg)?\b"
    r"|\b(\d{2,3})\s*\/\s*(\d{2,3})\s*(?:mmHg)\b",
    re.IGNORECASE,
)

_RE_PA_HISTORICA_O_FAMILIAR = re.compile(
    r"\b(hace\s+\d+|hace\s+un|hace\s+a[nñ]os?|hace\s+meses?|antigu\w*|en\s+el\s+pasado|previa|previo|a[nñ]o\s+\d{4}|historia\s+de|antecedente\w*|"
    r"padre|madre|herman\w*|abuel\w*|familiar\w*|espos\w*|hijo|hija|"
    r"si\s+|meta\s+|objetivo|mantener|evitar|controlar|en\s+caso\s+de|instrucci\w*)\b",
    re.IGNORECASE,
)

_RE_PA_NEGADA_O_NO_MEDIDA = re.compile(
    r"\b(no|niega|sin|toma\s+no|no\s+se\s+midi[oó]|desconoce|no\s+refiere)\b",
    re.IGNORECASE,
)

_RE_HEMORRAGIA_RETINIANA = re.compile(
    r"\b(?:hemorragias?\s+(?:en\s+llama|en\s+flama|retiniana\w*|intrarretiniana\w*|intraretiniana\w*|en\s+mancha|en\s+astilla)|sangrado\s+retiniano|hemorragias?\s+(?:en\s+ao|bilaterales?|en\s+od|en\s+oi))\b"
    r"|\bhemorragias?\s+retinianas?\b",
    re.IGNORECASE,
)

_RE_EDEMA_PAPILA = re.compile(
    r"\b(?:edema\s+(?:de\s+)?papilas?|papiledema|papilas?\s+edematosas?)\b",
    re.IGNORECASE,
)

_RE_EYE_OD = re.compile(r"\b(?:od|ojo\s+derecho)\b", re.IGNORECASE)
_RE_EYE_OI = re.compile(r"\b(?:oi|ojo\s+izquierdo)\b", re.IGNORECASE)
_RE_EYE_AO = re.compile(r"\b(?:ao|ambos\s+ojos|bilateral\w*)\b", re.IGNORECASE)


def _extract_pa_critica(motivo: str | None, fondo: str | None, edad: int | None) -> tuple[str, int, int] | None:
    """Extrae PA contemporanea en adulto (edad >= 18) con sistolica >= 180 o diastolica >= 120 mmHg."""
    if edad is None or edad < 18:
        return None

    textos: list[tuple[str, str]] = []
    if motivo:
        textos.append(("motivo", motivo))
    if fondo:
        textos.append(("fondo", fondo))

    readings: list[tuple[str, int, int, str]] = []
    for _, raw_text in textos:
        txt = _texto_hechos_paciente(raw_text)
        for m in _RE_PA_VALUE.finditer(txt):
            left = max(txt.rfind(sep, 0, m.start()) for sep in ('.', ';', '|')) + 1
            left = max([left] + [part.end() for part in re.finditer(r'\s+y\s+', txt[:m.start()])])
            ends = [p for sep in ('.', ';', '|') if (p := txt.find(sep, m.end())) >= 0]
            right = min(ends) if ends else len(txt)
            clause_ctx = txt[left:right]
            if _is_match_negated(txt, m.start(), m.end()):
                continue
            if _RE_PA_HISTORICA_O_FAMILIAR.search(clause_ctx) or re.search(
                r'\b(?:descartar|ejemplo|hipotetic\w*|posible|no\s+(?:se\s+)?midi\w*)\b', clause_ctx
            ):
                continue

            if m.group(1) and m.group(2):
                sys_str, dia_str = m.group(1), m.group(2)
            else:
                # mmHg tambien se usa en exploracion ocular; cifras solas no
                # acreditan una PA arterial medida.
                if not re.search(r"\b(?:pa|ta|presion\s+arterial|tension\s+arterial)\b", clause_ctx[:m.start() - left]):
                    continue
                sys_str, dia_str = m.group(3), m.group(4)

            try:
                sys_val = int(sys_str)
                dia_val = int(dia_str)
            except (ValueError, TypeError):
                continue

            if dia_val >= sys_val:
                continue  # No invertir cifras ni fabricar una medicion interpretable.

            readings.append((f"{sys_val}/{dia_val}", sys_val, dia_val, m.group(0)))

    if not readings:
        return None

    if len({(r[1], r[2]) for r in readings}) > 1:
        return None

    severe_readings = [r for r in readings if (r[1] >= 180 or r[2] >= 120)]

    if severe_readings:
        return (severe_readings[0][0], severe_readings[0][1], severe_readings[0][2])

    return None


@_memoize_cond
def _eval_fondo_hipertensivo_info(req: ImpresionClinicaRequest) -> dict:
    """Evalua factual y deterministicamente los signos vasculares retinianos y la PA critica."""
    fondo_text = _texto_hechos_paciente(req.clinica.fondo_de_ojo if req.clinica is not None else None)
    motivo_text = req.paciente.motivo_consulta if req.paciente is not None else None
    edad = req.paciente.edad if req.paciente is not None else None

    if not fondo_text and not motivo_text:
        return {"activa": False, "nivel": None, "texto": "", "hallazgos": []}

    # 1. Chequeo de rama urgente: PA contemporanea >= 180/120 en adulto + (hemorragias retinianas o edema de papila)
    pa_critica = _extract_pa_critica(motivo_text, fondo_text, edad)
    if pa_critica is not None and fondo_text:
        pa_str, sys_val, dia_val = pa_critica
        has_hemorragia = False
        has_edema_papila = False

        clauses = _RE_FONDO_HIPERTENSIVO_CLAUSE_SPLIT.split(fondo_text)
        for clause in clauses:
            clause_str = clause.strip()
            if re.search(r'\b(?:antecedente\w*|historia\s+de|antigu\w*|resuelt\w*|hace\s+\d+\s+anos)\b', _normalize_text(clause_str)):
                continue
            if not clause_str:
                continue
            m_hem = next((m for m in _RE_HEMORRAGIA_RETINIANA.finditer(clause_str) if _vascular_confirmed(clause_str, m.start(), m.end())), None)
            if m_hem:
                has_hemorragia = True
            m_pap = next((m for m in _RE_EDEMA_PAPILA.finditer(clause_str) if _vascular_confirmed(clause_str, m.start(), m.end())), None)
            if m_pap:
                has_edema_papila = True

        if has_hemorragia or has_edema_papila:
            hallazgo_label = "hemorragias retinianas" if has_hemorragia else "edema de papila"
            texto_urgente = (
                f"Hallazgo urgente: se registra presion arterial de {pa_str} mmHg junto con {hallazgo_label}; "
                "esta combinacion amerita valoracion medica especializada el mismo dia."
            )
            return {
                "activa": True,
                "nivel": "URGENTE",
                "texto": texto_urgente,
                "hallazgos": [f"PA {pa_str} mmHg", hallazgo_label],
            }

    # 2. Rama no urgente: Deteccion de signos vasculares confirmados en fondo_de_ojo
    if not fondo_text:
        return {"activa": False, "nivel": None, "texto": "", "hallazgos": []}

    clauses = _RE_FONDO_HIPERTENSIVO_CLAUSE_SPLIT.split(fondo_text)
    findings: list[str] = []

    for clause in clauses:
        clause_str = clause.strip()
        if not clause_str:
            continue

        if _RE_ANTECEDENTE_RESUELTO.search(clause_str):
            continue

        eye_tag = None
        if _RE_EYE_OD.search(clause_str) and not _RE_EYE_OI.search(clause_str):
            eye_tag = "OD"
        elif _RE_EYE_OI.search(clause_str) and not _RE_EYE_OD.search(clause_str):
            eye_tag = "OI"
        elif _RE_EYE_AO.search(clause_str):
            eye_tag = "AO"

        clause_findings: list[tuple[int, str]] = []

        m_est = _RE_ESTRECHAMIENTO_ARTERIOLAR.search(clause_str)
        if m_est and _vascular_confirmed(clause_str, m_est.start(), m_est.end()):
            desc = "estrechamiento arteriolar focal" if "focal" in m_est.group(0).lower() else "estrechamiento arteriolar"
            if eye_tag and eye_tag != "AO":
                desc += f" en {eye_tag}"
            elif eye_tag == "AO" or "bilateral" in clause_str.lower():
                desc += " bilateral"
            clause_findings.append((m_est.start(), desc))

        m_av = _RE_RELACION_AV_DISMINUIDA.search(clause_str)
        if m_av and _vascular_confirmed(clause_str, m_av.start(), m_av.end()):
            desc = "relacion arteria/vena disminuida"
            if eye_tag and eye_tag != "AO":
                desc += f" en {eye_tag}"
            elif eye_tag == "AO" or "bilateral" in clause_str.lower():
                desc += " bilateral"
            clause_findings.append((m_av.start(), desc))

        m_pared = _RE_CAMBIOS_PARED.search(clause_str)
        if m_pared and _vascular_confirmed(clause_str, m_pared.start(), m_pared.end()):
            matched_raw = m_pared.group(0).lower()
            metal = "hilo de plata" if "plata" in matched_raw else "hilo de cobre"
            desc = f"{metal} arteriolar"
            if eye_tag and eye_tag != "AO":
                desc += f" en {eye_tag}"
            elif eye_tag == "AO" or "bilateral" in clause_str.lower():
                desc += " bilateral"
            clause_findings.append((m_pared.start(), desc))

        m_cruce = _RE_CRUCE_PATOLOGICO.search(clause_str)
        if m_cruce and _vascular_confirmed(clause_str, m_cruce.start(), m_cruce.end()):
            matched_cruce = m_cruce.group(0).lower()
            if "pinzamiento" in matched_cruce:
                tipo_c = "cruce arteriovenoso con pinzamiento"
            elif "compresi" in matched_cruce:
                tipo_c = "cruce arteriovenoso con compresion"
            elif "desviaci" in matched_cruce or "deflexi" in matched_cruce:
                tipo_c = "cruce arteriovenoso con desviacion"
            else:
                tipo_c = "cruce arteriovenoso patologico"
            if eye_tag and eye_tag != "AO":
                tipo_c += f" en {eye_tag}"
            elif eye_tag == "AO" or "bilateral" in clause_str.lower():
                tipo_c += " bilateral"
            clause_findings.append((m_cruce.start(), tipo_c))

        m_ep = _RE_SIGNOS_EPONIMOS.search(clause_str)
        if m_ep and _vascular_confirmed(clause_str, m_ep.start(), m_ep.end()):
            ep_text = m_ep.group(0).lower()
            start_ep = m_ep.start()
            pre_ep = clause_str[max(0, start_ep - 10):start_ep].lower()
            if "marcus" not in pre_ep and "charles" not in pre_ep:
                if "gunn" in ep_text:
                    desc = "signo de Gunn"
                elif "salus" in ep_text:
                    desc = "signo de Salus"
                else:
                    desc = "signo de Bonnet"
                if "cruce" in clause_str.lower() and "cruce" not in desc:
                    desc += " en cruce arteriovenoso"
                if eye_tag and eye_tag != "AO":
                    desc += f" en {eye_tag}"
                elif eye_tag == "AO" or "bilateral" in clause_str.lower():
                    desc += " bilateral"
                clause_findings.append((m_ep.start(), desc))

        clause_findings.sort(key=lambda x: x[0])
        for _, f_desc in clause_findings:
            findings.append(f_desc)

    if not findings:
        return {"activa": False, "nivel": None, "texto": "", "hallazgos": []}

    dedup: list[str] = []
    for f in findings:
        if f not in dedup:
            dedup.append(f)

    if len(dedup) == 1:
        hallazgos_texto = dedup[0]
    elif len(dedup) == 2:
        hallazgos_texto = f"{dedup[0]} y {dedup[1]}"
    else:
        hallazgos_texto = ", ".join(dedup[:-1]) + f" y {dedup[-1]}"

    texto = (
        f"Se describe {hallazgos_texto} en los vasos retinianos, "
        "lo que amerita valoracion oftalmologica y revision medica de la presion arterial."
    )
    return {"activa": True, "nivel": "R", "texto": texto, "hallazgos": dedup}


@_memoize_cond
def _cond_fondo_hipertensivo(req: ImpresionClinicaRequest) -> bool:
    """Signos arteriolares descritos o PA critica con hallazgos que requieren evaluacion."""
    return _eval_fondo_hipertensivo_info(req)["activa"]


def _texto_fondo_hipertensivo(req: ImpresionClinicaRequest) -> str:
    return _eval_fondo_hipertensivo_info(req)["texto"]



# ---------------------------------------------------------------------------
# #11: fondo_vascular_diabetico (aviso microvascular retiniano)
# ---------------------------------------------------------------------------

_RE_DM_CONFIRMADA = re.compile(
    r"\b(diabetes(?:\s+mellitus)?(?:\s+tipo\s+[12])?|diab[eé]tic[ao]|dm[12]?|dmt[12])\b",
    re.IGNORECASE,
)

_RE_RUBEOSIS = re.compile(
    r"\b(rubeosis(?:\s+iridis)?|rubeosis\s+de\s+iris|neovasos\s+(?:en\s+el\s+|en\s+)?iris|neovascularizaci[oó]n\s+(?:del?\s+|en\s+el\s+|en\s+)?iris)\b",
    re.IGNORECASE,
)

_RE_NVD = re.compile(r"\b(nvd|neovascularizaci[oó]n\s+papilar|neovasos\s+(?:en\s+)?papil(?:ares|a))\b", re.IGNORECASE)
_RE_NVE = re.compile(r"\b(nve|neovascularizaci[oó]n\s+retiniana|neovasos\s+retinianos?|neovascularizaci[oó]n\s+prerretiniana)\b", re.IGNORECASE)

_RE_OVCR = re.compile(r"\b(ovcr|obvr|ovr|orvr|crvo|brvo|rvo|hrvo|oclusi[oó]n\s+venosa)\b", re.IGNORECASE)

_LESION_PATTERNS = [
    ("hemorragia prerretiniana", re.compile(r"\bhemorragias?\s+pre(?:r)?retinianas?\b", re.IGNORECASE)),
    ("microaneurismas retinianos", re.compile(r"\bmicroaneurismas?\s+retinianos?\b", re.IGNORECASE)),
    ("microaneurismas", re.compile(r"\bmicroaneurismas?\b", re.IGNORECASE)),
    ("exudados duros maculares", re.compile(r"\bexudados?\s+duros?\s+maculares?\b", re.IGNORECASE)),
    ("exudados duros retinianos", re.compile(r"\bexudados?\s+duros?\s+retinianos?\b", re.IGNORECASE)),
    ("exudados duros", re.compile(r"\bexudados?\s+duros?\b", re.IGNORECASE)),
    ("exudados lipidicos", re.compile(r"\bexudados?\s+lip[ií]dicos?\b", re.IGNORECASE)),
    ("exudados algodonosos", re.compile(r"\b(exudados?\s+algodonosos?|exudado\s+algodonoso|manchas?\s+algodonosas?)\b", re.IGNORECASE)),
    ("microhemorragias intrarretinianas puntiformes", re.compile(r"\bmicrohemorragias?\s+intrarretinianas?\s+puntiformes\b", re.IGNORECASE)),
    ("hemorragias retinianas puntiformes", re.compile(r"\bhemorragias?\s+retinianas?\s+puntiformes\b", re.IGNORECASE)),
    ("hemorragia retiniana", re.compile(r"\bhemorragias?\s+retinianas?\b", re.IGNORECASE)),
    ("microhemorragias intrarretinianas", re.compile(r"\bmicrohemorragias?\s+intrarretinianas?\b", re.IGNORECASE)),
    ("hemorragias intrarretinianas", re.compile(r"\bhemorragias?\s+intrarretinianas?\b", re.IGNORECASE)),
    ("hemorragias en mancha", re.compile(r"\bhemorragias?\s+en\s+mancha\b", re.IGNORECASE)),
    ("hemorragias puntiformes", re.compile(r"\bhemorragias?\s+puntiformes?\b", re.IGNORECASE)),
    ("hemorragias en punto", re.compile(r"\bhemorragias?\s+en\s+punto\b", re.IGNORECASE)),
    ("hemorragias en llama", re.compile(r"\bhemorragias?\s+en\s+llama\b", re.IGNORECASE)),
    ("edema macular diabetico", re.compile(r"\bedema\s+macular\s+diab[eé]tico\b", re.IGNORECASE)),
    ("edema macular clinicamente significativo", re.compile(r"\bedema\s+macular\s+cl[ií]nicamente\s+significativo\b|\bemcs\b", re.IGNORECASE)),
    ("IRMA", re.compile(r"\birma\b", re.IGNORECASE)),
    ("arrosariamiento venoso", re.compile(r"\b(arrosariamiento\s+venoso|arrosariamiento|rosario\s+venoso)\b", re.IGNORECASE)),
]


def _has_confirmed_dm(req: ImpresionClinicaRequest) -> bool:
    texto = ""
    if req.paciente and req.paciente.motivo_consulta:
        texto += ". " + _texto_hechos_paciente(req.paciente.motivo_consulta)
    if req.clinica and req.clinica.fondo_de_ojo:
        texto += ". " + _texto_hechos_paciente(req.clinica.fondo_de_ojo)
    norm = _normalize_text(texto)
    if not norm:
        return False
    for clause in re.split(r"[.;,\n|]|\s+y\s+", norm):
        if re.search(r"\b(madre|padre|familiar\w*|abuel\w*|herman\w*|hij[ao]|sospecha|posible|descartar)\b", clause):
            continue
        for m in _RE_DM_CONFIRMADA.finditer(clause):
            if not _is_match_negated(clause, m.start(), m.end()) and not re.search(r"edema\s+macular\s+$", clause[:m.start()]):
                return True
    return False


def _vascular_clauses(text: str):
    """Separa hechos de ojos distintos; no hereda lateralidad entre oraciones."""
    for clause in re.split(r"[.;\n|]+", text):
        if _RE_EYE_OD.search(clause) and _RE_EYE_OI.search(clause):
            yield from re.split(r",|\s+y\s+", clause)
        else:
            yield clause


def _vascular_eye(clause: str) -> str | None:
    od, oi = bool(_RE_EYE_OD.search(clause)), bool(_RE_EYE_OI.search(clause))
    if _RE_EYE_AO.search(clause):
        return "AO"
    return "OD" if od and not oi else "OI" if oi and not od else None


def _vascular_event_clauses(text: str):
    clauses = (part for clause in _vascular_clauses(text) for part in re.split(r"\bpero\b|(?=\bahora\b)", clause))
    for clause in clauses:
        if re.search(r"\b(antecedente\w*|historia|madre|padre|familiar\w*)\b", clause):
            yield from re.split(r"\s+y\s+(?=(?:antecedente|historia|perdida|amaurosis|ceguera|vision|placa|embolo|dolor)\b)", clause)
        else:
            yield clause  # Mantener negaciones coordinadas: niega amaurosis y ceguera.


def _vascular_current(clause: str, start: int, end: int) -> bool:
    if _is_match_negated(clause, start, end):
        return False
    # Un antecedente/plan no demuestra una lesion presente. El limite es el hecho,
    # no todo el fondo; conserva lesiones actuales de otra clausula u otro ojo.
    left = max([0] + [m.end() for m in re.finditer(r",|\s+y\s+", clause[:start])])
    right_match = re.search(r",|\s+y\s+", clause[end:])
    right = end + right_match.start() if right_match else len(clause)
    local = clause[left:right]
    if _certeza_local_span(clause, start, end) == "a descartar":
        return False
    for marker in re.finditer(r"\b(antecedentes?|historia\s+de|antigu\w*|inactiv\w*|resuelt\w*|desaparecid\w*|hace\s+\d+\s+anos)\b", local):
        if not _is_match_negated(local, marker.start(), marker.end()):
            return False
    return True


def _vascular_confirmed(clause: str, start: int, end: int) -> bool:
    return _vascular_current(clause, start, end) and _certeza_local_span(clause, start, end) is None


def _vascular_sintomas_oculares_actuales(text: str) -> list[tuple[str, str | None]]:
    pattern = re.compile(r"\b(dolor\s+ocular|vision\s+borrosa\s+desde\s+hoy|perdida\s+(?:visual\s+subita|subita\s+de\s+(?:la\s+)?vision))\b")
    result = []
    for clause in _vascular_event_clauses(text):
        if any(not _is_match_negated(clause, m.start(), m.end()) for m in re.finditer(r"\b(cronic\w*|estable|hace\s+\w+\s+anos)\b", clause)):
            continue
        for m in pattern.finditer(clause):
            if _vascular_current(clause, m.start(), m.end()) and _certeza_hallazgo(clause, m) is None:
                result.append((m.group(), _vascular_eye(clause)))
    return result


def _lesion_es_retiniana(clause: str, match: re.Match) -> bool:
    """La anatomia explicita prevalece sobre la localizacion implicita del campo."""
    anterior = list(re.finditer(r"\b(?:retin\w*|macul\w*|papil\w*|cornea|corneal\w*|conjuntiv\w*|iris|iridian\w*|coroid\w*)\b", clause[:match.start()]))
    if anterior and re.match(r"cornea|conjuntiv|iris|iridian|coroid", anterior[-1].group()):
        return False
    return not re.match(r"\s+(?:(?:en|de|del)\s+(?:la\s+|el\s+)?)?(?:cornea\w*|conjuntival\w*|iridian\w*|iris|coroid\w*)\b", clause[match.end():])


@_memoize_cond
def _eval_fondo_vascular_diabetico_info(req: ImpresionClinicaRequest) -> dict:
    fondo = _texto_hechos_paciente(req.clinica.fondo_de_ojo if req.clinica else None)
    anexos = _texto_hechos_paciente(req.clinica.anexos_oculares if req.clinica else None)
    motivo = _texto_hechos_paciente(req.paciente.motivo_consulta if req.paciente else None)
    inactive = {"activa": False, "nivel": None, "texto": "", "hallazgos": []}
    neovasos: list[tuple[str, str | None]] = []
    nv_certezas: dict[tuple[str, str | None], str] = {}
    findings: list[tuple[str, str | None]] = []
    preretinal_nueva = False
    for source, text in (("fondo", fondo), ("anexos", anexos)):
        for clause in _vascular_clauses(text):
            eye = _vascular_eye(clause)
            for label, pattern in (("en iris", _RE_RUBEOSIS), ("papilar", _RE_NVD), ("retiniana", _RE_NVE)):
                if source == "anexos" and label != "en iris":
                    continue
                for m in pattern.finditer(clause):
                    if label != "en iris" and not _lesion_es_retiniana(clause, m):
                        continue
                    if _vascular_current(clause, m.start(), m.end()) and (label, eye) not in neovasos:
                        neovasos.append((label, eye))
                        if certainty := _certeza_hallazgo(clause, m):
                            nv_certezas[label, eye] = certainty
            if source != "fondo":
                continue
            matched: list[tuple[int, int]] = []
            local_findings = []
            for label, pattern in _LESION_PATTERNS:
                for m in pattern.finditer(clause):
                    if any(start <= m.start() and m.end() <= end for start, end in matched):
                        continue
                    if not _vascular_current(clause, m.start(), m.end()):
                        continue
                    # Nunca convierte anatomia explicitamente anterior en retina.
                    if not _lesion_es_retiniana(clause, m):
                        continue
                    if "hemorragia" in label and label != "hemorragia prerretiniana":
                        same_eye_ovcr = eye in ("OD", "OI") and any(
                            _vascular_eye(other) == eye and _vascular_current(other, v.start(), v.end())
                            for other in _vascular_clauses(fondo) for v in _RE_OVCR.finditer(other)
                        )
                        local_ovcr = any(_vascular_current(clause, v.start(), v.end()) for v in _RE_OVCR.finditer(clause))
                        if same_eye_ovcr or local_ovcr:
                            continue
                    matched.append((m.start(), m.end()))
                    certeza = _certeza_hallazgo(clause, m)
                    descripcion = f"{certeza} {label}" if certeza else label
                    local_findings.append((m.start(), descripcion, eye))
                    if label == "hemorragia prerretiniana":
                        preretinal_nueva |= any(not _is_match_negated(clause, t.start(), t.end()) for t in re.finditer(r"\b(nuev\w*|reciente|agud\w*)\b", clause))
            for _, label, eye in sorted(local_findings):
                if (label, eye) not in findings:
                    findings.append((label, eye))

    def join_labels(labels):
        return labels[0] if len(labels) == 1 else ", ".join(labels[:-1]) + " y " + labels[-1]

    # Colapsa sinonimos repetidos sin ojo solo cuando existe una unica atribucion
    # del mismo tipo en la misma descripcion (NVD OD, neovascularizacion papilar).
    neovasos = [(label, eye) for label, eye in neovasos
                if eye is not None or not any(l == label and e is not None for l, e in neovasos)]
    symptoms = _vascular_sintomas_oculares_actuales(". ".join((motivo, fondo, anexos)))

    def symptomatic(eyes):
        return any(eye is None or eye == "AO" or None in eyes or "AO" in eyes or eye in eyes for _, eye in symptoms)
    if neovasos:
        nv_descriptions = [(nv_certezas.get((label, eye), "") + " " if (label, eye) in nv_certezas else "")
                           + f"neovascularizacion {label}" + (f" en {eye}" if eye else "") for label, eye in neovasos]
        if any(label == "en iris" for label, _ in neovasos) and symptomatic({eye for label, eye in neovasos if label == "en iris"}):
            agudos = any("desde hoy" in label or "subita" in label for label, _ in symptoms)
            sintoma_label = "sintomas agudos" if agudos else "sintomas oculares actuales referidos"
            texto = f"Hallazgo urgente: se describe rubeosis de iris con {sintoma_label}, lo que amerita valoracion oftalmologica urgente el mismo dia."
            texto += " Hallazgos documentados: " + join_labels(nv_descriptions) + "."
            level = "URGENTE_RUBEOSIS_AGUDA"
        else:
            texto = "Hallazgo urgente: se describe " + join_labels(nv_descriptions) + ", que amerita contacto con oftalmologia para triage y valoracion especializada."
            level = "URGENTE_NEOVASCULAR"
            if symptoms:
                texto += " Se refieren por separado " + join_labels([label + (f" en {eye}" if eye else " sin lateralidad precisada") for label, eye in symptoms]) + "; evaluar tambien estos sintomas sin atribuirlos al ojo de la neovascularizacion."
        if findings:
            texto += " Coexisten " + join_labels([label + (f" en {eye}" if eye else " (sin lateralidad documentada)") for label, eye in findings]) + "; completar evaluacion medica sistemica, incluida glucemia y presion arterial."
        return {"activa": True, "nivel": level, "texto": texto, "hallazgos": nv_descriptions}
    if not findings:
        return inactive

    eyes = {eye for _, eye in findings}
    if len(eyes) == 1:
        eye = next(iter(eyes))
        desc = join_labels([label for label, _ in findings])
        desc += " bilateral" if eye == "AO" else f" en {eye}" if eye else ""
    else:
        desc = join_labels([label + (f" en {eye}" if eye else " (sin lateralidad documentada)") for label, eye in findings])
    if any(label == "hemorragia prerretiniana" for label, _ in findings) and (preretinal_nueva or symptomatic({eye for label, eye in findings if label == "hemorragia prerretiniana"})):
        texto = f"Hallazgo urgente: se documenta {desc}, con inicio reciente o sintomas oculares actuales referidos; amerita valoracion oftalmologica el mismo dia para determinar su causa."
        return {"activa": True, "nivel": "URGENTE_HEMORRAGIA", "texto": texto, "hallazgos": [desc]}

    preferente = any(any(term in label for term in ("IRMA", "arrosariamiento venoso", "hemorragia prerretiniana", "macular")) for label, _ in findings)
    valoracion = "valoracion retinologica preferente" if preferente else "valoracion retinologica"
    texto = (f"Se documentan hallazgos microvasculares retinianos ({desc}), "
             f"lo que amerita {valoracion} y evaluacion medica sistemica, "
             "incluida la glucemia y la presion arterial")
    if _has_confirmed_dm(req):
        texto += ", y valoracion con su medico tratante respecto al control glucemico"
    texto += "."
    if any("edema macular" in label for label, _ in findings):
        texto += " Integrar estos datos en la misma valoracion del hallazgo macular."
    return {"activa": True, "nivel": "MICROVASCULAR", "texto": texto, "hallazgos": [desc]}


@_memoize_cond
def _cond_fondo_vascular_diabetico(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: microaneurismas, exudados u otras alteraciones microvasculares retinianas."""
    return _eval_fondo_vascular_diabetico_info(req)["activa"]


def _texto_fondo_vascular_diabetico(req: ImpresionClinicaRequest) -> str:
    return _eval_fondo_vascular_diabetico_info(req)["texto"]



# ---------------------------------------------------------------------------
# #3: fondo_oclusion_vascular_urgente
# Subtipos: ARTERIAL > SIN TIPIFICAR > VENOSA > SECUELA
# ---------------------------------------------------------------------------

_RE_OCLUSION_ACRONIMOS_ARTERIAL = re.compile(r"\b(oacr|obar|crao|brao|rao)\b", re.IGNORECASE)
_RE_OCLUSION_ACRONIMOS_VENOSA = re.compile(r"\b(ovcr|obvr|ovr|orvr|crvo|brvo|rvo|hrvo)\b", re.IGNORECASE)

_RE_OCLUSION_SIGNOS_ARTERIALES = re.compile(
    r"\b(mancha\s+rojo\s+cereza|mancha\s+cereza|cherry\s+red|segmentacion\s+de\s+la\s+columna|boxcar)\b",
    re.IGNORECASE,
)

_RE_OCLUSION_FRASES_ARTERIAL = re.compile(
    r"\b(embolia\s+retiniana|embolia\s+de\s+arteria\s+retiniana)\b",
    re.IGNORECASE,
)

_RE_OCLUSION_FRASES_SIN_TIPIFICAR = re.compile(
    r"\b(oclusion\s+vascular\s+retiniana|oclusion\s+vascular\s+de\s+(?:la\s+)?retina)\b",
    re.IGNORECASE,
)

_RE_OCLUSION_VASO = re.compile(
    r"\b(oclusion|obstruccion|trombosis|embolia)\b(?:\s+\w+){0,4}?\s+(vena|venas|venos\w*|arteria|arterias|arterial\w*|arteriol\w*)\b",
    re.IGNORECASE,
)

_RE_OCLUSION_EXCLUSIONES = re.compile(
    r"\b(profunda|cerebral|intracraneal|seno|miembro|pulmonar|coronari\w*|"
    r"carotid\w*|aortic\w*|yugular|renal|iliac\w*|mesenteric\w*|femoral|tvp|tep)\b",
    re.IGNORECASE,
)

_RE_OCLUSION_CRONICO = re.compile(
    r"\b(antecedentes?|secuela|antigu\w*|cronic\w*|previ\w*|tratad\w*|en\s+tratamiento|laser|fotocoagul\w*|antiangiogenic\w*|anti-?vegf|antivegf|intravitre\w*|colateral\w*|estable|resuelt\w*|envainad\w*|hace\s+\d+\s+(?:meses|anos))\b",
    re.IGNORECASE,
)

_RE_OCLUSION_AGUDO = re.compile(
    r"\b(agud\w*|recientes?|subit\w*|de\s+novo|"
    r"desde\s+(?:ayer|hoy|anoche)|hace\s+(?:\d+|unos?|pocos?)\s+(?:horas?|dias?))\b",
    re.IGNORECASE,
)

_RE_OCLUSION_OCULAR = re.compile(
    r"\b(?:retin\w*|oftalmic\w*|ocul\w*|od|oi|ao|"
    r"rama|temporal|nasal|superotemporal|inferotemporal)\b"
)
_RE_OCLUSION_DUDA = re.compile(
    r"\b(?:descartar|descarte|sospech\w*|posible|probable|compatible|sugestiv\w*)\b"
)


def _contexto_local_occlusion(fondo: str, start: int, end: int) -> str:
    """Ventana del evento: seis palabras por lado, sin tomar citas futuras."""
    inicio = max(fondo.rfind(sep, 0, start) for sep in ".,;:\n") + 1
    finales = [fondo.find(sep, end) for sep in ".,;:\n"]
    fin = min((p for p in finales if p >= 0), default=len(fondo))
    antes = " ".join(fondo[inicio:start].split()[-6:])
    despues = " ".join(fondo[end:fin].split()[:6])
    return " ".join((antes, fondo[start:end], despues))


def _eval_fondo_oclusion_raw(fondo_text: str | None, edad: int | None = None) -> dict:
    if not fondo_text:
        return {"subtipo": None, "texto": "", "matched_keywords": ()}
    fondo = _texto_hechos_paciente(fondo_text)
    if not fondo:
        return {"subtipo": None, "texto": "", "matched_keywords": ()}

    matches_arterial = []
    matches_sin_tipificar = []
    matches_venosa = []
    matches_secuela = []
    all_matched_kws = []
    confirmed_kws = []
    confirmed_eyes: set[str] = set()
    doubtful_facts: list[str] = []

    def _check_and_register(
        m: re.Match, default_subtipo: str, is_sign: bool = False,
        requires_ocular: bool = False,
    ):
        start, end = m.start(), m.end()
        if _is_match_negated(fondo, start, end):
            return
        clause = _contexto_local_occlusion(fondo, start, end)
        if _RE_OCLUSION_EXCLUSIONES.search(clause):
            return
        if requires_ocular and not _RE_OCLUSION_OCULAR.search(clause):
            return
        kw_text = m.group(0).lower()
        all_matched_kws.append(kw_text)
        certainty = _certeza_hallazgo(fondo, m)
        if certainty:
            doubtful_facts.append(_get_clause_around_span(fondo, start, end).strip())
        if not certainty and not re.search(r"\b(?:compatible|sugestiv\w*)\b", clause):
            confirmed_kws.append(kw_text)
            confirmed_eyes.update(_papilar_ojos(_get_clause_around_span(fondo, start, end)))

        if is_sign:
            matches_arterial.append(kw_text)
            return

        remoto = bool(re.search(r"\bhace\s+(?:\d+\s+)?(?:meses|anos)\b", clause))
        is_chronic = remoto or (
            bool(_RE_OCLUSION_CRONICO.search(clause))
            and not bool(_RE_OCLUSION_AGUDO.search(clause))
        )
        if is_chronic:
            matches_secuela.append(kw_text)
        else:
            if default_subtipo == "ARTERIAL":
                matches_arterial.append(kw_text)
            elif default_subtipo == "SIN_TIPIFICAR":
                matches_sin_tipificar.append(kw_text)
            elif default_subtipo == "VENOSA":
                matches_venosa.append(kw_text)

    # 1. Signos arteriales agudos
    for m in _RE_OCLUSION_SIGNOS_ARTERIALES.finditer(fondo):
        _check_and_register(m, "ARTERIAL", is_sign=True)

    # 2. Acronimos arteriales
    for m in _RE_OCLUSION_ACRONIMOS_ARTERIAL.finditer(fondo):
        _check_and_register(m, "ARTERIAL")

    # 3. Frases arteriales
    for m in _RE_OCLUSION_FRASES_ARTERIAL.finditer(fondo):
        _check_and_register(m, "ARTERIAL")

    # 4. Acronimos venosos
    for m in _RE_OCLUSION_ACRONIMOS_VENOSA.finditer(fondo):
        _check_and_register(m, "VENOSA")

    # 5. Frases sin tipificar
    for m in _RE_OCLUSION_FRASES_SIN_TIPIFICAR.finditer(fondo):
        _check_and_register(m, "SIN_TIPIFICAR")

    # 6. Patron sintactico vaso
    for m in _RE_OCLUSION_VASO.finditer(fondo):
        vaso_word = m.group(2).lower()
        if any(vaso_word.startswith(art) for art in ("arteria", "arteriol")):
            _check_and_register(m, "ARTERIAL", requires_ocular=True)
        elif any(vaso_word.startswith(ven) for ven in ("vena", "venos")):
            _check_and_register(m, "VENOSA", requires_ocular=True)

    subtipo = None
    texto = ""

    if matches_arterial:
        subtipo = "ARTERIAL"
        acg = (
            ", incluido el descarte de arteritis de celulas gigantes"
            if (edad is None or edad >= 50)
            else ""
        )
        texto = (
            "Hallazgo urgente: el fondo de ojo registra signos descritos como oclusion arterial retiniana, "
            "hallazgo que amerita derivacion inmediata el mismo dia a un servicio de urgencias con "
            f"atencion de evento vascular cerebral para evaluacion neurovascular y oftalmologica{acg}."
        )
    elif matches_sin_tipificar:
        subtipo = "SIN_TIPIFICAR"
        texto = (
            "Hallazgo urgente: el fondo de ojo registra signos descritos como oclusion vascular retiniana "
            "sin tipificar, hallazgo que amerita valoracion oftalmologica el mismo dia y, si la perdida "
            "visual es subita y de horas de evolucion, derivacion inmediata a urgencias con atencion "
            "de evento vascular cerebral."
        )
    elif matches_venosa:
        subtipo = "VENOSA"
        hc = (
            "; en menores de 50 anos, valorar estudio de hipercoagulabilidad"
            if (edad is not None and edad < 50)
            else ""
        )
        texto = (
            "Hallazgo urgente: el fondo de ojo registra signos descritos como oclusion venosa retiniana, "
            "hallazgo que amerita valoracion oftalmologica prioritaria en los proximos dias, sin esperar "
            "a la siguiente cita programada, con medicion de presion intraocular y busqueda de edema "
            "macular y neovascularizacion, asi como evaluacion medica de presion arterial, glucosa "
            f"y lipidos{hc}."
        )
    elif matches_secuela:
        subtipo = "SECUELA"
        texto = (
            "Se documenta en fondo de ojo antecedente o secuela de oclusion vascular retiniana; "
            "amerita verificar seguimiento oftalmologico vigente para vigilancia de edema macular "
            "y neovascularizacion, y control medico de factores de riesgo vascular."
        )

    # La supresion macular solo es valida si no elimina el hecho realmente
    # consignado: integrar edema del mismo ojo sin atribuirle una causa.
    if texto and doubtful_facts:
        texto += " Datos referidos con incertidumbre: " + _join_hallazgos(_dedupe(doubtful_facts)) + "; verificar el hallazgo sin establecer un diagnostico."
    edema = []
    if subtipo and confirmed_eyes:
        for local in _papilar_clausulas(fondo):
            if not (_papilar_ojos(local) & confirmed_eyes):
                continue
            for m in _RE_MACULAR_OTROS_P.finditer(local):
                if (any(t in m.group() for t in ("edema", "edematosa", "engrosada", "engrosamiento", "emq", "emc", "emd"))
                        and _macular_factual(local, m, admitir_incierto=False)):
                    edema.append(local.strip())
        if edema:
            texto += " Coexiste el hallazgo macular registrado (" + _join_hallazgos(_dedupe(edema)) + "); integrarlo en la misma valoracion sin establecer causalidad."

    return {
        "subtipo": subtipo,
        "texto": texto,
        "matched_keywords": tuple(all_matched_kws),
        "confirmed_keywords": tuple(confirmed_kws),
    }


def _eval_fondo_oclusion(req: ImpresionClinicaRequest) -> dict:
    fondo_text = req.clinica.fondo_de_ojo if req.clinica else None
    edad = req.paciente.edad if req.paciente else None
    return _eval_fondo_oclusion_raw(fondo_text, edad)


@_memoize_cond
def _cond_fondo_oclusion_vascular_urgente(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: sospecha o confirmacion de oclusion vascular retiniana (arterial, venosa, sin tipificar o secuela)."""
    return _eval_fondo_oclusion(req)["subtipo"] is not None


def _texto_fondo_oclusion_vascular_urgente(req: ImpresionClinicaRequest) -> str:
    return _eval_fondo_oclusion(req)["texto"]


def _ojo_tiene_oclusion_vascular_retiniana(fondo_text: str | None, target_eye: str) -> bool:
    """Verifica si fondo_text contiene una oclusion vascular retiniana demostrada
    (arterial, venosa, sin tipificar o secuela) que aplique al ojo indicado ('OD' o 'OI').
    Excluye trombosis sistemicas (TVP, etc.)."""
    if not fondo_text:
        return False
    for clause in _papilar_clausulas(_normalize_text(fondo_text)):
        info = _eval_fondo_oclusion_raw(clause)
        if not info.get("confirmed_keywords"):
            continue
        eyes = _papilar_ojos(clause)
        # Una combinacion ambigua de ambos ojos no demuestra a cual pertenece.
        if len(eyes) == 2 and not _RE_EYE_AO.search(clause):
            continue
        if target_eye.upper() in eyes or not eyes:
            return True
    return False


# ---------------------------------------------------------------------------
# Nueva regla: fondo_embolo_retiniano
# Placas de Hollenhorst / embolia arteriolar
# Preventivo cardiovascular ambulatorio salvo amaurosis fugaz / perdida visual transitoria
# ---------------------------------------------------------------------------

_RE_EMBOLO_FONDO = re.compile(
    r"\b(hollenhorst|material\s+embolico|embolos?|placas?\s+(?:refringentes?|brillantes?|de\s+colesterol))\b"
)
_RE_AMAUROSIS_SINTOMA = re.compile(
    r"\b(amaurosis\s+fuga[zx]|perdida\s+(?:(?:transitoria|temporal|momentanea|subita)\s+de\s+(?:la\s+)?vision|visual\s+(?:transitoria|temporal|momentanea|subita))|"
    r"ceguera\s+transitoria|vision(?:\s+(?:od|oi))?\s+se\s+apago\b[^.;]*?\bminutos?)\b"
)
_RE_EMBOLO_REMOTE = re.compile(
    r"\b(antecedentes?|historia\s+de|congenit\w*|leber|infancia|hace\s+(?:\d+|un[ao]?|dos|tres|cuatro|cinco|diez|veinte)\s+anos?|en\s+(?:19|20)\d{2})\b"
)


def _embolo_sintomas(req: ImpresionClinicaRequest) -> dict:
    """Hechos reportados; no atribuye sintomas a la placa ni diagnostica isquemia."""
    sources = [("motivo de consulta", req.paciente.motivo_consulta if req.paciente else None)]
    if req.clinica:
        sources += [("fondo de ojo", req.clinica.fondo_de_ojo), ("anexos oculares", req.clinica.anexos_oculares)]
    symptoms = []
    neuro = False
    asintomatico = False
    for source, text in sources:
        for clause in _vascular_event_clauses(_texto_hechos_paciente(text)):
            for m in re.finditer(r"\b(asintomatic[ao]|sin\s+sintomas\s+visuales(?:\s+actuales)?)\b", clause):
                # 'sin sintomas' es una ausencia positiva; no usar negacion del hallazgo.
                if (not _is_match_negated(clause, m.start(), m.end())
                        and not _RE_EMBOLO_REMOTE.search(_get_clause_around_span(clause, m.start(), m.end()))):
                    asintomatico = True
            for m in _RE_AMAUROSIS_SINTOMA.finditer(clause):
                local = _get_clause_around_span(clause, m.start(), m.end())
                if (_vascular_current(clause, m.start(), m.end())
                        and not _RE_EMBOLO_REMOTE.search(local)
                        and _certeza_hallazgo(clause, m) is None):
                    eye = _vascular_eye(clause)
                    transient = not bool(re.search(r"\bsubita\b", m.group()))
                    label = "perdida visual transitoria" if transient else "perdida visual subita"
                    description = label + (f" en {eye}" if eye else " sin lateralidad precisada") + f" referida en {source}"
                    if description not in symptoms:
                        symptoms.append(description)
            for m in re.finditer(r"\b(debilidad\s+(?:derecha|izquierda|de\s+(?:un\s+)?(?:brazo|pierna)|de\s+un\s+lado)|dificultad\s+para\s+hablar|afasia)\b", clause):
                if _vascular_current(clause, m.start(), m.end()) and re.search(r"\b(subit\w*|hoy|ahora|reciente|hace\s+(?:una?|\d+)\s+(?:horas?|minutos?))\b", clause):
                    neuro = True
    return {"visuales": symptoms, "neurologicos": neuro, "asintomatico": asintomatico}


@_memoize_cond
def _eval_fondo_embolo(req: ImpresionClinicaRequest) -> dict:
    fondo = _texto_hechos_paciente(req.clinica.fondo_de_ojo if req.clinica else None)
    findings = []
    doubtful = False
    for clause in _vascular_event_clauses(fondo):
        for m in _RE_EMBOLO_FONDO.finditer(clause):
            if _is_match_negated(clause, m.start(), m.end()):
                continue
            if re.search(r"\b(antecedentes?|historia\s+de|antigu\w*|desaparecid\w*|resuelt\w*)\b", _get_clause_around_span(clause, m.start(), m.end())):
                continue
            if re.search(r"\b(pulmon\w*|carotid\w*|coroid\w*|extravascular\w*|conjuntiv\w*|corneal\w*)\b", clause):
                continue
            hollenhorst = m.group() == "hollenhorst"
            retinal = bool(re.search(r"\b(retinian\w*|retina|oacr|obar|crao|brao)\b", clause))
            vessel = bool(re.search(r"\b(arteriol\w*|intraarteriol\w*|arteria|vena|vaso\w*)\b", clause))
            # Hollenhorst lleva localizacion retinal implicita. El brillo solo no.
            if not hollenhorst and not (retinal and (vessel or m.group().startswith(("embolo", "material")))):
                continue
            certainty = _certeza_hallazgo(clause, m)
            if certainty == "a descartar":
                continue
            uncertain = bool(certainty) or bool(re.search(r"\bpendiente\s+de\s+confirmar\b", clause))
            doubtful |= uncertain
            if hollenhorst:
                label = "placa de Hollenhorst"
            elif re.search(r"\bembolos?\s+calcificad\w*", clause):
                label = "embolo calcificado"
            elif re.search(r"\bembolos?\s+plaquetari\w*", clause):
                label = "embolo plaquetario"
            elif re.search(r"\bembolos?\s+de\s+colesterol\b", clause):
                label = "embolo de colesterol"
            elif m.group().startswith("placa"):
                label = m.group()  # no transforma brillo en colesterol
            else:
                label = "material embolico"
            if not hollenhorst:
                if re.search(r"\bvena\b", clause):
                    label += " descrito en vena retiniana"
                elif re.search(r"\b(?:arteriol\w*|intraarteriol\w*)\b", clause):
                    label += " descrito en arteriola retiniana"
                else:
                    label += " retiniano"
            eye = _vascular_eye(clause)
            label += f" en {eye}" if eye else " sin lateralidad documentada"
            if uncertain:
                label = (certainty or "posible") + " " + label
            if label not in findings:
                findings.append(label)
    if not findings:
        return {"activa": False, "texto": ""}
    description = "; ".join(findings)
    prefix = f"Se documenta en el fondo de ojo {description}. "
    if doubtful:
        prefix += "Verificar el hallazgo mediante valoracion oftalmologica. "
    symptoms = _embolo_sintomas(req)
    oclusion = _eval_fondo_oclusion(req)["subtipo"]
    if symptoms["neurologicos"]:
        text = ("Hallazgo urgente: " + prefix + "Se refieren sintomas neurologicos de inicio agudo; "
                "requieren por si mismos derivacion inmediata a urgencias para evaluacion neurologica, "
                "sin atribuirlos automaticamente a la placa ni establecer un evento vascular cerebral.")
    elif symptoms["visuales"] or oclusion == "ARTERIAL":
        evidence = "; ".join(symptoms["visuales"]) if symptoms["visuales"] else "signos descritos como oclusion arterial retiniana en el fondo de ojo"
        text = ("Hallazgo urgente: " + prefix + f"Coexisten {evidence}; "
                "amerita derivacion inmediata el mismo dia a urgencias con atencion de evento vascular cerebral "
                "para evaluacion neurovascular y oftalmologica. La coexistencia no demuestra una relacion causal.")
    elif oclusion in ("SIN_TIPIFICAR", "VENOSA"):
        text = ("Hallazgo urgente: " + prefix + "Integrar la evaluacion medica del posible origen embolico "
                "en la misma valoracion oftalmologica indicada por los signos de oclusion vascular retiniana, sin demorar esa atencion.")
    elif symptoms["asintomatico"] and not doubtful:
        text = (prefix + "En ausencia de sintomas visuales explicitamente documentada, amerita evaluacion medica ambulatoria "
                "de riesgo cardiovascular y de posible fuente embolica, incluida valoracion carotidea segun criterio medico.")
    else:
        text = (prefix + "Es necesario precisar sintomas visuales y su temporalidad para definir la prioridad de atencion; "
                "la ausencia de ese dato no demuestra que sea asintomatico. Amerita valoracion oftalmologica y medica "
                "de riesgo cardiovascular y posible fuente embolica, sin establecer su origen.")
    return {"activa": True, "texto": text}


@_memoize_cond
def _cond_fondo_embolo_retiniano(req: ImpresionClinicaRequest) -> bool:
    return _eval_fondo_embolo(req)["activa"]


def _texto_fondo_embolo_retiniano(req: ImpresionClinicaRequest) -> str:
    return _eval_fondo_embolo(req)["texto"]


@_memoize_cond
def _cond_sintomas_alarma_traccion_vitreoretina(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: fotopsias y miodesopsias agudas sugieren traccion vitreorretiniana en evolucion.

    Se suprime cuando #1 fondo_periferico_riesgo emite un hallazgo urgente (DR, ROTURA, VITREO
    o PREDISPONENTE+SINTOMAS), para evitar duplicidad de alertas urgentes sobre el mismo cuadro.
    """
    perif = _eval_fondo_periferico(req)
    if perif["nivel"] in ("DR", "ROTURA", "VITREO", "PREDISPONENTE_SINTOMAS"):
        return False
    info = _eval_sintomas_traccion(req)
    return info["nivel"] is not None


def _texto_sintomas_alarma_traccion_vitreoretina(req: ImpresionClinicaRequest) -> str:
    info = _eval_sintomas_traccion(req)
    nivel = info["nivel"]
    sintomas = info["sintomas_str"]
    dato_alarma = info.get("dato_alarma") or "sombra o cortina en el campo visual"

    if nivel == "A":
        return (
            f"Hallazgo urgente: se refieren {sintomas} con {dato_alarma}, "
            "datos que ameritan referencia a oftalmologia el mismo dia para exploracion "
            "de retina periferica bajo midriasis y descarte de rotura o desprendimiento de retina."
        )
    elif nivel == "B":
        return (
            f"Hallazgo urgente: se refieren {sintomas} de inicio reciente, "
            "que ameritan exploracion de retina periferica bajo midriasis con oftalmoscopia indirecta, "
            "idealmente con indentacion escleral, en un plazo maximo de 48 horas, "
            "o referencia a oftalmologia si no puede realizarse en consulta."
        )
    else:
        # Nivel C
        return (
            f"Se refieren {sintomas} sin tiempo de evolucion documentado; "
            "si son de inicio reciente o han aumentado, ameritan exploracion de retina periferica "
            "bajo midriasis para descartar rotura retiniana."
        )

