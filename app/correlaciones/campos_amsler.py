"""Dominio: campos visuales por confrontacion y test de Amsler (2 correlaciones).

campos_visuales_alterados (#15) extrae por mencion el objeto visual, el ojo o
sector, la afirmacion, la certeza, la fiabilidad y el tiempo, y ademas tiene una
ruta independiente por sintomas agudos del motivo (perdida de campo o hemicampo,
episodios transitorios recientes) que una confrontacion normal no anula.
amsler_alterado (#16) sigue la mecanica anterior hasta su propia orden.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

from app.correlaciones.base import _memoize_cond
from app.correlaciones.hechos_textuales import _certeza_local, _es_hipotetico, _sujeto_es_paciente
from app.correlaciones.pupilas_motilidad import (
    _ANTIGUO_RE,
    _CAMBIO_DEICTICO_RE,
    _CAMBIO_RE,
    _HallazgoOcular,
    _afirmado_local,
    _calificador_afirmado,
    _conocido_y_estable,
    _cronologia_de_clausula,
    _contexto_temporal,
    _describir_ocurrencia,
    _ocurrencias_oculares,
    _patron_ocurrencias,
)
from app.correlaciones.texto import _dedupe, _join_hallazgos, _normalize_text
from app.schemas import ImpresionClinicaRequest

_KEYWORDS_AMSLER_POSITIVOS = (
    "distorsion", "metamorfopsia", "micropsia", "macropsia",
    "escotoma central", "escotoma", "alterado", "alteracion",
    "ondulacion", "lineas torcidas", "lineas onduladas", "lineas distorsionadas",
    "lineas quebradas", "area faltante", "zona faltante",
)

# --------------------------------------------------------------------------- #15
_SIGNOS_CAMPO: dict[str, str] = {}


def _reg(diccionario: dict[str, str], familia: str, etiqueta: str, *claves: str) -> None:
    for clave in claves:
        diccionario[clave] = f"{familia}|{etiqueta}"


_reg(_SIGNOS_CAMPO, "hemianopsia", "hemianopsia", "hemianopsia", "hemianopia")
_reg(_SIGNOS_CAMPO, "cuadrantanopsia", "cuadrantanopsia", "cuadrantanopsia", "cuadrantopsia", "cuadrantanopia")
_reg(_SIGNOS_CAMPO, "altitudinal", "defecto altitudinal", "defecto altitudinal", "altitudinal")
_reg(_SIGNOS_CAMPO, "escalon", "escalon nasal", "escalon nasal")
_reg(_SIGNOS_CAMPO, "escotoma", "escotoma", "escotoma")
_reg(_SIGNOS_CAMPO, "defecto", "defecto del campo", "defecto", "defecto campimetrico", "defecto de campo",
     "defecto del campo", "defecto periferico")
_reg(_SIGNOS_CAMPO, "reduccion", "reduccion del campo", "campo reducido", "campo visual reducido",
     "reduccion del campo", "reduccion del campo visual", "estrechamiento del campo", "vision tubular",
     "campo tubular", "constriccion del campo", "constriccion periferica", "constriccion concentrica",
     "constriccion campimetrica", "restriccion del campo", "restriccion campimetrica",
     "restriccion periferica", "restriccion concentrica", "restriccion superior", "restriccion inferior",
     "restriccion nasal", "restriccion temporal", "restriccion generalizada", "restriccion bilateral")
_reg(_SIGNOS_CAMPO, "perdida", "perdida del campo", "perdida del campo", "perdida de campo",
     "perdida del campo visual", "perdida de campo visual", "perdida de la vision periferica",
     "perdida de vision periferica")
_reg(_SIGNOS_CAMPO, "perdida", "disminucion del campo visual", "campo visual disminuido", "campo disminuido",
     "disminucion del campo", "disminucion del campo visual")
_reg(_SIGNOS_CAMPO, "respuesta", "falta de respuesta al estimulo visual", "falta de percepcion",
     "no percibe el estimulo", "no percibe estimulo", "no responde al estimulo", "no responde a estimulo",
     "no responde a los estimulos", "sin respuesta al estimulo", "no ve el estimulo")
_reg(_SIGNOS_CAMPO, "alteracion", "alteracion del campo visual", "alteracion campimetrica",
     "alteracion del campo", "alteracion de campo", "campo alterado", "campo visual alterado")

_AMPLIOS = frozenset({"hemianopsia", "cuadrantanopsia", "altitudinal"})
_DETALLE_CAMPO_RE = re.compile(
    r"\b(central|paracentral|arqueado|arcuato|temporal|nasal|superior|inferior|superiormente|inferiormente|"
    r"homonima|heteronima|bitemporal|binasal|concentrica|periferica|generalizada|"
    r"en cuadrante(?: superior| inferior)?(?: nasal| temporal)?)\b")
_LADO_HEMICAMPO_RE = re.compile(r"\b(derecha|izquierda)\b")
_DEFECTO_NO_CAMPIMETRICO_RE = re.compile(
    r"\bdefecto\s+(?:refractiv\w*|de refraccion|de correccion|corregid\w*|visual corregid\w*|de fijacion|"
    r"epitelial\w*|pupilar\w*|de cierre|palpebral\w*)")
_FISIOLOGICO_RE = re.compile(r"\b(?:fisiologic\w*|mancha ciega)\b")
_PLAN_SIN_EXAMEN_RE = re.compile(
    r"\b(?:no evaluad[oa]s?|no se evaluo|sin evaluar|no realizad[oa]s?|pendiente|proxima consulta|"
    r"proxima cita|proxima revision|por realizar|a realizar)\b")
_NO_INTERPRETABLE_RE = re.compile(
    r"\b(?:no valorables?|no evaluables?|no interpretables?|poco confiables?|no confiables?|poco fiables?|"
    r"no fiables?|baja fiabilidad|mala colaboracion|poca colaboracion|colaboracion (?:deficiente|pobre|limitada)|"
    r"no colabora|no coopera|no comprende|falta de comprension|incomprension|no reproducibles?|"
    r"inconsistentes?|inconcluso|no concluyente)\b")
_CAUSA_LOCAL_RE = re.compile(
    r"\bpor\s+(ptosis(?:\s+palpebral)?|dermatochalasis|parpado\s+\w+|cejas?|montura|armazon)\b")


@dataclass(frozen=True)
class _SignoCampo:
    base: _HallazgoOcular
    familia: str
    texto: str
    causa: str | None = None


def _etiqueta_campo(h: _HallazgoOcular, familia: str, etiqueta: str) -> str:
    detalles = []
    for d in _DETALLE_CAMPO_RE.findall(h.contexto):
        d = {"superiormente": "superior", "inferiormente": "inferior"}.get(d, d)
        if d not in detalles and d not in etiqueta:
            detalles.append(d)
    if familia in ("hemianopsia", "cuadrantanopsia"):
        detalles += [d for d in _LADO_HEMICAMPO_RE.findall(h.contexto) if d not in detalles]
    return " ".join([etiqueta, *detalles])


def _signos_confrontacion(req: ImpresionClinicaRequest) -> list[_SignoCampo]:
    clinica = req.clinica
    if clinica is None or not clinica.confrontacion_campos_visuales:
        return []
    signos = []
    for h in _ocurrencias_oculares(clinica.confrontacion_campos_visuales, _SIGNOS_CAMPO, "campos",
                                   lado_es_ojo=False):
        familia, etiqueta = h.hallazgo.split("|", 1)
        ctx = h.contexto
        if not h.afirmado or _FISIOLOGICO_RE.search(ctx) or _PLAN_SIN_EXAMEN_RE.search(ctx):
            continue
        if familia == "defecto" and _DEFECTO_NO_CAMPIMETRICO_RE.search(ctx):
            continue                     # «defecto refractivo corregido» no es un defecto de campo
        no_interpretable = bool(_NO_INTERPRETABLE_RE.search(ctx))
        if familia == "respuesta" and no_interpretable:
            continue                     # sin respuesta por incomprension/atencion/hipoacusia: no es un defecto
        if _conocido_y_estable(h):
            continue                     # secuela o diagnostico ya conocido: contexto, no hallazgo nuevo
        if no_interpretable and not h.incierto:
            h = replace(h, incierto=True)
        causa = _CAUSA_LOCAL_RE.search(ctx)
        signos.append(_SignoCampo(h, familia, _etiqueta_campo(h, familia, etiqueta), causa[1] if causa else None))
    return signos


# --- sintomas del motivo (ruta independiente del examen) -------------------------
_PERDIDA = (r"(?:perdida|perdio|perdi|pierde|perdiendo|dejo de ver|deje de ver|deja de ver|dejar de ver|"
            r"ya no veo|ya no ve|no veo|no ve|no vio|no vi|ausencia de vision|falta de vision)")
_OBJETO_AMPLIO = (r"(?:la mitad|una mitad|(?:el |del |de un |por un )?lado(?: derecho| izquierdo)?|hemicampo|"
                  r"(?:la )?vision (?:lateral|periferica)|(?:la )?parte (?:de arriba|de abajo|lateral|superior|inferior)|"
                  r"cuadrante|sector)")
# «campo» sin calificador visual puede ser terreno o ambito laboral: se exige el calificador.
_OBJETO_CAMPO = (r"(?:(?:el |del |de |en )?campo(?: visual| de vision| periferico| superior| inferior| nasal| "
                 r"temporal| central| lateral))")
_PATRON_PERDIDA_AMPLIA = re.compile(rf"\b{_PERDIDA}\b(?:\s+\w+){{0,3}}?\s+{_OBJETO_AMPLIO}\b")
_PATRON_PERDIDA_CAMPO = re.compile(rf"\b{_PERDIDA}\b(?:\s+\w+){{0,3}}?\s+{_OBJETO_CAMPO}\b")
_TRANSITORIO_RE = re.compile(
    r"\b(?:durante|por) (?:\d+|unos|algunos|varios) (?:minutos?|segundos?)|transitori\w*|ya paso|"
    r"ahora veo (?:como antes|normal|bien)|se (?:recupero|resolvio|normalizo)|cedio|recupero\b")

_NEURO_FOCAL: dict[str, str] = {}
for _etiqueta, _claves in (
    ("dificultad del habla referida", ("dificultad para hablar", "dificultad del habla", "dificultad de habla",
                                       "dificultad al hablar", "habla arrastrada", "disartria", "afasia")),
    ("dificultad del lenguaje referida", ("pierde palabras", "perdida de palabras", "no encuentra palabras")),
    ("debilidad referida", ("debilidad", "perdida de fuerza")),
    ("hormigueo o adormecimiento referido", ("hormigueo", "adormecimiento", "entumecimiento")),
    ("asimetria facial referida", ("cara torcida", "asimetria facial")),
    ("confusion referida", ("confusion", "desorientacion")),
):
    for _c in _claves:
        _NEURO_FOCAL[_c] = _etiqueta


@dataclass(frozen=True)
class _SintomaCampo:
    texto: str
    amplio: bool
    reciente: bool
    transitorio: bool
    antiguo: bool
    ojo: str | None = None
    certeza: str | None = None


def _sintomas_de_campo(req: ImpresionClinicaRequest) -> list[_SintomaCampo]:
    motivo = req.paciente.motivo_consulta if req.paciente else None
    norm = _normalize_text(motivo)
    if not norm:
        return []
    hallazgos = []
    # La mancha o el escotoma central fijo son vision central: los recoge #16.
    for patron, amplio, etiqueta in ((_PATRON_PERDIDA_AMPLIA, True, "perdida de la mitad o de un lado del campo visual"),
                                     (_PATRON_PERDIDA_CAMPO, False, "perdida del campo visual")):
        for m in patron.finditer(norm):
            if not _sujeto_es_paciente(norm, m.start(), m.end()) or _es_hipotetico(norm, m.start(), m.end()):
                continue
            if any(m.start() >= a and m.end() <= b for a, b, *_ in hallazgos):
                continue                 # ya cubierto por un patron mas especifico
            a = max(norm.rfind(sep, 0, m.start()) for sep in ".;!?") + 1
            finales = [p for p in (norm.find(sep, m.end()) for sep in ".;!?") if p != -1]
            b = min(finales) if finales else len(norm)
            clausula = norm[a:b]
            if not _afirmado_local(clausula, m.start() - a, m.end() - a):
                continue
            hallazgos.append((a, b, m, clausula, amplio, etiqueta))
    resultado = []
    for a, b, m, clausula, amplio, etiqueta in sorted(hallazgos, key=lambda x: x[2].start()):
        clausula = _contexto_temporal(clausula, m.start() - a, m.end() - a)
        antiguo = _calificador_afirmado(clausula, _ANTIGUO_RE)
        conocido = bool(re.search(r"\b(?:conocid\w*|en seguimiento|antecedente)\b", clausula)) and not \
            _calificador_afirmado(clausula, re.compile(r"\b(?:empeor\w*|agrav\w*|nuev[oa]s?)\b"))
        reciente = not antiguo and (_calificador_afirmado(clausula, _CAMBIO_RE)
                                    or _calificador_afirmado(clausula, _CAMBIO_DEICTICO_RE))
        ojo_od = bool(re.search(r"\b(?:od|ojo derecho)\b", clausula))
        ojo_oi = bool(re.search(r"\b(?:oi|ojo izquierdo)\b", clausula))
        ojo = "OD" if ojo_od and not ojo_oi else "OI" if ojo_oi and not ojo_od else None
        lado = re.search(r"\b(?:mitad|lado)\s+(derech[oa]|izquierd[oa])\b", clausula)
        if amplio and re.search(r"\bmitad\b", clausula):
            texto = "perdida de la mitad " + (f"{lado[1]} " if lado else "") + "del campo visual"
        elif amplio:
            texto = "perdida de la vision de un lado" + (f" ({lado[1]})" if lado else "")
        else:
            texto = etiqueta
        resultado.append(_SintomaCampo(texto, amplio, reciente, bool(_TRANSITORIO_RE.search(clausula)),
                                       antiguo or conocido, ojo, _certeza_local(norm, m.start(), m.end())))
    return resultado


def _neurologicos_focales(req: ImpresionClinicaRequest) -> list[str]:
    motivo = req.paciente.motivo_consulta if req.paciente else None
    hallazgos = _cronologia_de_clausula(_ocurrencias_oculares(motivo, _NEURO_FOCAL, "motivo_consulta"), motivo)
    return _dedupe([h.hallazgo for h in hallazgos if h.afirmado and not h.incierto
                   and not h.por_descartar and h.evolucion != "antigua"])


@dataclass(frozen=True)
class _AnalisisCampos:
    signos: tuple[_SignoCampo, ...]
    sintomas: tuple[_SintomaCampo, ...]
    neurologicos: tuple[str, ...]
    prioridad: str          # "inmediata" | "mismo dia" | ""


@_memoize_cond
def _analisis_campos(req: ImpresionClinicaRequest) -> _AnalisisCampos:
    signos = tuple(_signos_confrontacion(req))
    # Un sintoma antiguo/conocido y sin cambio no crea una ruta nueva; un empeoramiento si.
    sintomas = tuple(s for s in _sintomas_de_campo(req) if not s.antiguo)
    neuro = tuple(_neurologicos_focales(req))
    recientes_exam = [s for s in signos if s.base.evolucion == "cambio reciente"
                      and not s.base.incierto and not s.base.por_descartar]
    recientes_sint = [s for s in sintomas if s.reciente and s.certeza != "a descartar"]
    prioridad = ""
    if recientes_exam or recientes_sint:
        amplio = (any(s.familia in _AMPLIOS for s in recientes_exam)
                  or any(s.amplio and not s.transitorio for s in recientes_sint))
        prioridad = "inmediata" if amplio or neuro else "mismo dia"
    return _AnalisisCampos(signos, sintomas, neuro, prioridad)


def _cond_campos_visuales_alterados(req: ImpresionClinicaRequest) -> bool:
    """Defecto documentado en la confrontacion o sintoma agudo de campo en el motivo."""
    analisis = _analisis_campos(req)
    return bool(analisis.signos or analisis.sintomas)


def _descripcion_campo(signo: _SignoCampo, con_prefijo: bool = True) -> str:
    h = signo.base
    texto = signo.texto
    if h.ojo in ("AO", "AMBOS"):
        texto += " en ambos ojos"
    prefijo = ("sospecha por descartar de " if h.por_descartar
               else "resultado no concluyente para " if h.incierto else "")
    h = replace(h, hallazgo=texto, ojo=None if h.ojo in ("AO", "AMBOS") else h.ojo)
    causa = f" (atribuido en el registro a {signo.causa})" if signo.causa else ""
    return (prefijo if con_prefijo else "") + _describir_ocurrencia(h) + causa


def _descripcion_sintoma(s: _SintomaCampo) -> str:
    prefijo = "sospecha por descartar de " if s.certeza == "a descartar" else (s.certeza + " " if s.certeza else "")
    texto = prefijo + s.texto + (f" {s.ojo}" if s.ojo else "")
    if s.transitorio and s.reciente:
        return texto + " de inicio reciente, en episodio transitorio"
    return texto + (" de inicio reciente" if s.reciente else "")


def _texto_campos_visuales_alterados(req: ImpresionClinicaRequest) -> str:
    a = _analisis_campos(req)
    firmes = [s for s in a.signos if not (s.base.incierto or s.base.por_descartar)]
    dudosos = [s for s in a.signos if s.base.incierto or s.base.por_descartar]
    sintomas = [s for s in a.sintomas if s.certeza != "a descartar"]
    solicitudes = [s for s in a.sintomas if s.certeza == "a descartar"]
    partes = []
    if a.signos:
        partes.append("la confrontacion documenta " + _join_hallazgos(
            _dedupe([_descripcion_campo(s) for s in a.signos])))
    if sintomas:
        partes.append("el paciente refiere " + _join_hallazgos(_dedupe([_descripcion_sintoma(s) for s in sintomas])))
    cuerpo = " y ".join(partes)
    if a.prioridad:
        texto = "Hallazgo urgente: " + cuerpo
        if a.neurologicos:
            texto += f", con {_join_hallazgos(list(a.neurologicos))}"
        plazo = "inmediata en urgencias" if a.prioridad == "inmediata" else "el mismo dia"
        texto += (f"; esta informacion amerita valoracion medica {plazo} para estudiar su causa, "
                  "sin esperar la perimetria programada.")
        registrada = bool(req.clinica and req.clinica.confrontacion_campos_visuales)
        if a.sintomas and not firmes and registrada:
            # Redaccion que H01 no juzga «falsa normalidad» si el LLM la copia (autoconsistencia).
            texto += " Que la confrontacion no muestre defectos no descarta el sintoma referido."
        return texto
    frases = []
    if firmes:
        frases.append("Se documenta " + _join_hallazgos(_dedupe([_descripcion_campo(s) for s in firmes]))
                      + " durante la confrontacion de campos visuales.")
    if sintomas:
        frases.append("El paciente refiere " + _join_hallazgos(_dedupe([_descripcion_sintoma(s) for s in sintomas]))
                      + ".")
    if solicitudes:
        frases.append("El registro plantea, sin establecer, " + _join_hallazgos(
            _dedupe([_descripcion_sintoma(s) for s in solicitudes]))
            + ". Verificar el episodio y completar la evaluacion del campo visual.")
    if firmes or sintomas:
        frases.append("Este hallazgo requiere evaluacion especializada y caracterizacion mediante "
                      "perimetria formal segun corresponda.")
        if any(s.base.evolucion == "indeterminada" for s in firmes) or (a.sintomas and not firmes):
            frases.append("Verificar inicio y sintomas asociados para decidir la prioridad de atencion.")
    # Un resultado dudoso, no reproducible o solo planteado nunca se declara como alteracion.
    inciertos = [s for s in dudosos if not s.base.por_descartar]
    por_descartar = [s for s in dudosos if s.base.por_descartar]
    if inciertos:
        frases.append("La confrontacion deja un resultado no concluyente ("
                      + _join_hallazgos(_dedupe([_descripcion_campo(s, con_prefijo=False) for s in inciertos]))
                      + "). Repetir la confrontacion o realizar perimetria formal para verificar o descartar el hallazgo.")
    if por_descartar:
        frases.append("La confrontacion plantea, sin establecer, "
                      + _join_hallazgos(_dedupe([_descripcion_campo(s, con_prefijo=False) for s in por_descartar]))
                      + ". Completar la confrontacion o realizar perimetria formal para verificar o descartar el hallazgo.")
    return " ".join(frases)


# --------------------------------------------------------------------------- #16
# Percepcion referida por el paciente durante la rejilla (o en el motivo). No hay
# tecnica, correccion de cerca, fijacion ni fiabilidad en el contrato: no se suponen.
_PERCEPCIONES_AMSLER: dict[str, str] = {}
for _etiqueta, _claves in (
    ("distorsion", ("distorsion", "distorsionada", "distorsionado")),
    ("metamorfopsia", ("metamorfopsia",)),
    ("lineas onduladas", ("lineas onduladas", "linea ondulada", "onduladas las lineas", "ondulacion", "veo ondulado",
                          "veo ondulada")),
    ("lineas torcidas", ("lineas torcidas", "linea torcida", "torcidas las lineas", "lineas rectas torcidas")),
    ("lineas quebradas", ("lineas quebradas", "linea quebrada", "quebradas las lineas")),
    ("lineas distorsionadas", ("lineas distorsionadas", "distorsionadas las lineas")),
    ("lineas curvas o deformadas", ("lineas curvas", "lineas deformadas", "objetos deformados", "cosas deformadas")),
    ("lineas interrumpidas", ("lineas interrumpidas", "lineas cortadas", "lineas faltantes")),
    ("micropsia", ("micropsia", "objetos mas pequenos", "cosas mas pequenas")),
    ("macropsia", ("macropsia", "objetos mas grandes", "cosas mas grandes")),
    ("escotoma central", ("escotoma central",)),
    ("escotoma", ("escotoma",)),
    ("mancha central", ("mancha central", "mancha fija central", "mancha fija", "punto negro central",
                        "mancha en el centro")),
    ("zona borrosa central", ("zona borrosa central", "area borrosa central")),
    ("zona faltante", ("zona faltante", "area faltante", "zona ausente", "cuadrado faltante")),
    ("cuadrados de distinto tamano", ("cuadrados de distinto tamano", "cuadros de distinto tamano",
                                      "cuadrados de diferente tamano", "cuadros de diferente tamano",
                                      "cuadrados mas pequenos", "cuadrados mas grandes")),
    ("alteracion referida en la rejilla", ("amsler alterado", "amsler anormal", "rejilla alterada", "rejilla anormal",
                                           "test alterado", "grid alterado", "alteracion en la rejilla",
                                           "alteracion del amsler", "alteracion en amsler")),
):
    for _c in _claves:
        _PERCEPCIONES_AMSLER[_c] = _etiqueta

# Expresion de las percepciones para quien solo necesita localizarlas (A2 de #8).
_RE_PERCEPCION_AMSLER = _patron_ocurrencias(tuple(sorted(_PERCEPCIONES_AMSLER, key=len, reverse=True)))

_ARTEFACTO_RE = re.compile(
    r"\b(?:defecto de impresion|impresion defectuosa|error de impresion|mal impres\w*|rejilla impresa|"
    r"impresa torcida|rejilla (?:rota|danada|arrugada|deformada))\b")
_NO_INTERPRETABLE_AMSLER_RE = re.compile(
    r"\b(?:prueba no (?:confiable|fiable|valorable|interpretable)|no (?:confiable|fiable|valorable|interpretable)|"
    r"poco (?:confiable|fiable)|baja fiabilidad|no logra fijar|no fija|sin correccion de cerca|"
    r"no uso correccion|falta de correccion|no comprende|comprension alterada|falta de comprension|"
    r"incomprension|no reproducible|inconsistente|mala colaboracion|no colabora)\b")


@dataclass(frozen=True)
class _PercepcionAmsler:
    base: _HallazgoOcular
    texto: str
    fuente: str            # "rejilla" | "motivo"
    transitorio: bool = False


def _percepciones_de(texto: str | None, fuente: str, *, incluir_contexto: bool = False) -> list[_PercepcionAmsler]:
    if not texto:
        return []
    origen = "grid_de_amsler" if fuente == "rejilla" else "motivo_consulta"
    hallazgos = _ocurrencias_oculares(texto, _PERCEPCIONES_AMSLER, origen)
    if fuente == "motivo":
        hallazgos = _cronologia_de_clausula(hallazgos, texto)
    resultado = []
    for h in hallazgos:
        ctx = h.contexto
        if not h.afirmado or _ARTEFACTO_RE.search(ctx) or _PLAN_SIN_EXAMEN_RE.search(ctx):
            continue                      # error material o prueba no realizada: no es una percepcion
        if not incluir_contexto and (_conocido_y_estable(h) or (fuente == "motivo" and h.evolucion == "antigua")):
            continue                      # secuela o diagnostico ya conocido y estable: contexto, no aviso nuevo
        if _NO_INTERPRETABLE_AMSLER_RE.search(ctx) and not h.incierto:
            h = replace(h, incierto=True)
        etiqueta = h.hallazgo
        resultado.append(_PercepcionAmsler(h, etiqueta, fuente, bool(_TRANSITORIO_RE.search(ctx))))
    return resultado


@dataclass(frozen=True)
class _AnalisisAmsler:
    firmes: tuple[_PercepcionAmsler, ...]       # percepciones afirmadas y actuales en la rejilla
    episodios: tuple[_PercepcionAmsler, ...]    # sintomas del motivo o episodios transitorios referidos
    dudosos: tuple[_PercepcionAmsler, ...]
    prioridad: str                              # "urgente" | ""
    contextos: tuple[_PercepcionAmsler, ...] = () # antecedentes pertinentes; no disparan alerta


@_memoize_cond
def _analisis_amsler(req: ImpresionClinicaRequest) -> _AnalisisAmsler:
    rejilla = req.clinica.grid_de_amsler if req.clinica else None
    motivo = req.paciente.motivo_consulta if req.paciente else None
    de_rejilla = _percepciones_de(rejilla, "rejilla")
    del_motivo = _percepciones_de(motivo, "motivo")
    dudosos = tuple(p for p in de_rejilla + del_motivo if p.base.incierto or p.base.por_descartar)
    ciertos = [p for p in de_rejilla + del_motivo if not (p.base.incierto or p.base.por_descartar)]
    # Un episodio transitorio anotado en la rejilla es un sintoma referido, no una lectura actual.
    firmes = tuple(p for p in ciertos if p.fuente == "rejilla" and not p.transitorio)
    episodios = tuple(p for p in ciertos if p.fuente == "motivo" or p.transitorio)
    recientes = [p for p in firmes + episodios if p.base.evolucion == "cambio reciente"]
    todos = _percepciones_de(rejilla, "rejilla", incluir_contexto=True) + _percepciones_de(
        motivo, "motivo", incluir_contexto=True)
    contextos = tuple(p for p in todos if p not in de_rejilla + del_motivo)
    return _AnalisisAmsler(firmes, episodios, dudosos, "urgente" if recientes else "", contextos)


def _se_refiere(descripciones: list[str]) -> str:
    plural = len(descripciones) > 1 or any(d.startswith(("lineas", "cuadrados")) for d in descripciones)
    return "se refieren" if plural else "se refiere"


def _describir_percepcion(p: _PercepcionAmsler, con_prefijo: bool = True) -> str:
    h = p.base
    ojo = None if h.ojo in ("AO", "AMBOS") else h.ojo
    texto = p.texto + (" en ambos ojos" if h.ojo in ("AO", "AMBOS") else "")
    if p.transitorio:
        texto += " transitorio"
    prefijo = ("sospecha por descartar de " if h.por_descartar
               else "resultado no concluyente para " if h.incierto else "")
    return (prefijo if con_prefijo else "") + _describir_ocurrencia(replace(h, hallazgo=texto, ojo=ojo))


@_memoize_cond
def _cond_amsler_alterado(req: ImpresionClinicaRequest) -> bool:
    """Percepcion alterada referida en la rejilla o en el motivo (vision central)."""
    if req.clinica is None and req.paciente is None:
        return False
    a = _analisis_amsler(req)
    if not (a.firmes or a.episodios or a.dudosos):
        return False
    # Integracion A2 de #8: cuando su aviso ya recoge TODA la evidencia (ojos, tiempos,
    # fuentes) con fiabilidad, no se repite. Si la evidencia es dudosa o no cabe, #16 se conserva.
    if req.clinica is not None:
        from app.correlaciones.fondo_de_ojo import _eval_fondo_macular_dmae_info
        dmae_info = _eval_fondo_macular_dmae_info(req)
        if dmae_info.get("nivel") == "A2" and dmae_info.get("amsler_absorbido", False):
            return False
    return True


def _texto_amsler_alterado(req: ImpresionClinicaRequest) -> str:
    a = _analisis_amsler(req)
    descripcion_firmes = _dedupe([_describir_percepcion(p) for p in a.firmes])
    descripcion_episodios = _dedupe([_describir_percepcion(p) for p in a.episodios])
    registrada = bool(req.clinica and req.clinica.grid_de_amsler)
    inciertos = [p for p in a.dudosos if not p.base.por_descartar]
    por_descartar = [p for p in a.dudosos if p.base.por_descartar]
    frases = []
    if a.prioridad:
        partes = []
        if descripcion_firmes:
            partes.append(f"en la rejilla de Amsler {_se_refiere(descripcion_firmes)} "
                          + _join_hallazgos(descripcion_firmes))
        if descripcion_episodios:
            partes.append("el paciente refiere " + _join_hallazgos(descripcion_episodios))
        frases.append("Hallazgo urgente: " + " y ".join(partes) + "; este cambio reciente de la vision central "
                      "amerita valoracion oftalmologica urgente, con OCT macular segun los hallazgos.")
        if descripcion_episodios and not descripcion_firmes and registrada:
            frases.append("Que la rejilla de Amsler no muestre alteraciones no descarta el sintoma referido.")
    else:
        if descripcion_firmes:
            frases.append(f"En la rejilla de Amsler {_se_refiere(descripcion_firmes)} "
                          + _join_hallazgos(descripcion_firmes) + ".")
        if descripcion_episodios:
            frases.append("El paciente refiere " + _join_hallazgos(descripcion_episodios) + ".")
        if descripcion_firmes or descripcion_episodios:
            frases.append("Este hallazgo amerita evaluacion oftalmologica de la vision central y estudios "
                          "complementarios segun los hallazgos.")
            frases.append("Verificar inicio y sintomas asociados para decidir la prioridad de atencion.")
    # Un resultado dudoso, no interpretable o solo planteado nunca se declara alteracion.
    if inciertos:
        frases.append("El test de Amsler deja un resultado no concluyente ("
                      + _join_hallazgos(_dedupe([_describir_percepcion(p, con_prefijo=False) for p in inciertos]))
                      + "). Repetir la prueba para verificar o descartar el hallazgo.")
    if por_descartar:
        frases.append("El registro plantea, sin establecer, "
                      + _join_hallazgos(_dedupe([_describir_percepcion(p, con_prefijo=False) for p in por_descartar]))
                      + ". Completar la prueba para verificar o descartar el hallazgo.")
    return " ".join(frases)
