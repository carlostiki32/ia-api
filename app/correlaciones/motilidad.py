"""Dominio: motilidad ocular (1 correlacion): motilidad_alterada.

Extrae signos motores del campo `motilidad_ocular` por seccion (versiones,
ducciones, sacadicos, seguimiento) y por ocurrencia, con ojo, afirmacion,
certeza y cronologia, reutilizando el extractor compartido con #12/#13. El
aviso describe el hallazgo exacto y pide valoracion; no diagnostica paresia,
lesion ni causa. La prioridad nace de combinaciones explicitas (deficit nuevo
con diplopia, trauma reciente, dolor con deterioro visual reciente, nistagmo
nuevo con sintomas vestibulares), nunca de una palabra aislada.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

from app.correlaciones.base import _memoize_cond
from app.correlaciones.pupilas_motilidad import (
    _HallazgoOcular,
    _MOVIMIENTO_RE,
    _calificador_afirmado,
    _combinaciones_ptosis,
    _conocido_y_estable,
    _cronologia_de_clausula,
    _describir_ocurrencia,
    _ocurrencias_oculares,
    _son_hallazgos_contralaterales,
)
from app.correlaciones.texto import _dedupe, _join_hallazgos, _normalize_text
from app.schemas import ImpresionClinicaRequest

_ETIQUETA_SECCION_RE = re.compile(
    r"\b(versiones|ducciones|movimientos sacadicos|sacadicos|movimientos de seguimiento|seguimiento)\s*:"
)
_SECCION_CANONICA = {"movimientos sacadicos": "sacadicos", "movimientos de seguimiento": "seguimiento"}


def _mapa(pares: dict[str, tuple[str, str]]) -> dict[str, str]:
    """clave -> 'familia|etiqueta' (el extractor compartido solo transporta una cadena)."""
    return {clave: f"{familia}|{etiqueta}" for clave, (familia, etiqueta) in pares.items()}


def _pares(familia: str, etiqueta: str, *claves: str) -> dict[str, tuple[str, str]]:
    return {clave: (familia, etiqueta) for clave in claves}


# --- vocabulario --------------------------------------------------------------
_GENERAL: dict[str, tuple[str, str]] = {}
for _e, _cs in (
    ("limitacion", ("limitacion", "limitado", "limitada")),
    ("restriccion", ("restriccion", "restringido", "restringida")),
    ("hipofuncion muscular", ("hipoaccion", "hipofuncion")),
    ("paresia", ("paresia", "paretico", "paretica")),
    ("paralisis", ("paralisis", "paralitico", "paralitica")),
    ("oftalmoparesia", ("oftalmoparesia",)),
    ("oftalmoplejia", ("oftalmoplejia", "oftalmoplegia")),
    ("incomitancia", ("incomitancia", "incomitante")),
):
    _GENERAL.update(_pares("deficit", _e, *_cs))
_GENERAL.update(_pares("nistagmo", "nistagmo", "nistagmo", "nistagmus"))
_GENERAL.update(_pares(
    "dolor", "dolor con el movimiento ocular",
    "dolor con movimiento", "dolor con el movimiento", "dolor al movimiento", "dolor con los movimientos",
    "dolor a los movimientos", "dolor al mover", "dolor a la movilizacion", "dolor con la movilizacion",
    "dolor al mirar", "duele al mover", "duele con el movimiento",
))
_GENERAL.update(_pares(
    "postura", "posicion compensadora de la cabeza",
    "posicion compensadora", "postura compensadora", "posicion anomala de la cabeza",
    "cabeza ladeada", "cabeza inclinada",
))
_GENERAL.update(_pares("postura", "torticolis", "torticolis"))
_GENERAL.update(_pares("sobreaccion", "sobreaccion muscular",
                       "sobreaccion", "sobreactuacion", "hiperfuncion"))
_GENERAL.update(_pares("sincinesia", "sincinesia", "sincinesia"))
_GENERAL.update(_pares("sincinesia", "sindrome de Duane", "duane", "sindrome de duane"))
# Sacadicos y seguimiento descritos con la frase completa (texto libre).
for _e, _cs in (
    ("movimientos sacadicos lentos", ("sacadico lento",)),
    ("hipometria sacadica", ("sacadico hipometrico", "hipometria sacadica")),
    ("hipermetria sacadica", ("sacadico hipermetrico", "hipermetria sacadica")),
    ("dismetria sacadica", ("sacadico dismetrico", "dismetria sacadica")),
    ("latencia sacadica aumentada", ("latencia sacadica aumentada",)),
    ("movimientos sacadicos imprecisos", ("sacadico impreciso",)),
    ("movimientos sacadicos alterados", ("sacadico alterado", "sacadico anormal")),
):
    _GENERAL.update(_pares("sacadico", _e, *_cs))
for _e, _cs in (
    ("seguimiento entrecortado", ("seguimiento entrecortado", "persecucion entrecortada")),
    ("seguimiento sacadico", ("seguimiento sacadico", "persecucion sacadica")),
    ("seguimiento discontinuo", ("seguimiento no continuo", "seguimiento discontinuo")),
    ("seguimiento fragmentado", ("seguimiento fragmentado",)),
    ("seguimiento irregular", ("seguimiento irregular",)),
    ("seguimiento lento", ("seguimiento lento",)),
    ("seguimiento limitado", ("seguimiento limitado",)),
    ("seguimiento asimetrico", ("seguimiento asimetrico",)),
    ("seguimiento alterado", ("seguimiento alterado", "seguimiento anormal")),
):
    _GENERAL.update(_pares("seguimiento", _e, *_cs))
# Respuesta optocinetica ANORMAL: la normal/fisiologica no es un hallazgo.
for _adj_m, _adj_f in (("asimetrico", "asimetrica"), ("ausente", "ausente"), ("alterado", "alterada"),
                       ("anormal", "anormal"), ("disminuido", "disminuida")):
    _etiqueta = f"respuesta optocinetica {_adj_f}"
    _GENERAL.update(_pares(
        "optocinetico", _etiqueta,
        f"nistagmo optocinetico {_adj_m}", f"optocinetico {_adj_m}", f"okn {_adj_m}",
        f"respuesta optocinetica {_adj_f}",
    ))

_POR_SECCION: dict[str, dict[str, tuple[str, str]]] = {
    "sacadicos": {
        **_pares("sacadico", "movimientos sacadicos lentos", "lento", "lenta"),
        **_pares("sacadico", "hipometria sacadica", "hipometrico", "hipometrica", "hipometria"),
        **_pares("sacadico", "hipermetria sacadica", "hipermetrico", "hipermetrica", "hipermetria"),
        **_pares("sacadico", "dismetria sacadica", "dismetrico", "dismetrica", "dismetria"),
        **_pares("sacadico", "latencia sacadica aumentada", "latencia aumentada", "latencia prolongada"),
        **_pares("sacadico", "movimientos sacadicos imprecisos", "impreciso", "imprecisa", "inexacto"),
        **_pares("sacadico", "movimientos sacadicos alterados", "alterado", "alterada", "anormal"),
    },
    "seguimiento": {
        **_pares("seguimiento", "seguimiento entrecortado", "entrecortado", "entrecortada"),
        **_pares("seguimiento", "seguimiento discontinuo", "no continuo", "no continua", "discontinuo",
                 "discontinua"),
        **_pares("seguimiento", "seguimiento sacadico", "sacadico", "sacadica"),
        **_pares("seguimiento", "seguimiento fragmentado", "fragmentado", "fragmentada"),
        **_pares("seguimiento", "seguimiento irregular", "irregular"),
        **_pares("seguimiento", "seguimiento lento", "lento", "lenta"),
        **_pares("seguimiento", "seguimiento limitado", "limitado", "limitada"),
        **_pares("seguimiento", "seguimiento asimetrico", "asimetrico", "asimetrica"),
        **_pares("seguimiento", "seguimiento con saltos", "con saltos", "escalonado", "escalonada"),
        **_pares("seguimiento", "seguimiento alterado", "alterado", "alterada", "anormal"),
    },
    "versiones": {
        **_pares("otro", "movimientos desconjugados", "desconjugado", "desconjugada", "no conjugado",
                 "no conjugada"),
        **_pares("otro", "versiones asimetricas", "asimetrico", "asimetrica"),
    },
    "ducciones": {
        **_pares("deficit", "limitacion de ducciones", "incompleto", "incompleta", "no completo",
                 "no completa"),
    },
}

# Sintomas del motivo que participan en las rutas de prioridad.
_SINTOMAS: dict[str, str] = {}
for _e, _cs in (
    ("diplopia referida", ("diplopia", "vision doble", "veo doble", "imagenes dobles")),
    ("vertigo referido", ("vertigo",)),
    ("mareo referido", ("mareo",)),
    ("inestabilidad referida", ("inestabilidad", "desequilibrio", "ataxia")),
    ("traumatismo referido", ("traumatismo", "trauma", "golpe", "contusion")),
    ("fractura orbitaria referida", ("fractura orbitaria", "fractura de orbita")),
    ("nausea referida", ("nausea",)),
    ("vomito referido", ("vomito",)),
    ("dolor ocular referido", ("dolor ocular", "dolor orbitario", "dolor periocular")),
    ("dolor cervical referido", ("dolor cervical", "dolor de cuello")),
    ("dolor referido", ("dolor",)),
    ("cefalea referida", ("cefalea", "dolor de cabeza")),
    ("disminucion visual referida", ("disminucion visual", "disminucion de la vision", "perdida visual",
                                     "perdida de vision", "vision disminuida", "baja visual",
                                     "baja de vision", "vision borrosa")),
    ("disartria referida", ("disartria",)),
    ("debilidad referida", ("debilidad",)),
):
    for _c in _cs:
        _SINTOMAS[_c] = _e

_TRAUMA = frozenset({"traumatismo referido", "fractura orbitaria referida"})
_VESTIBULAR = frozenset({"vertigo referido", "mareo referido", "inestabilidad referida", "nausea referida",
                         "vomito referido"})
_VISUAL = frozenset({"disminucion visual referida"})
_SIN_FECHA = frozenset({"dolor ocular referido", "dolor cervical referido", "disartria referida",
                        "debilidad referida"})
_TRAUMA_EN_TEXTO_RE = re.compile(
    r"\b(?:traumatismo|trauma|golpe|contusion|impacto|fractura(?: de)?(?: la)? orbita|fractura orbitaria)\b")
_PAR_CRANEAL_RE = re.compile(
    r"\b(?:del|de)\s+(?:(?:iii|iv|vi|3|4|6|tercer|cuarto|sexto)\s+par(?:\s+craneal)?|"
    r"nervio\s+(?:motor\s+ocular\s+comun|troclear|abducens|abducente|oculomotor)|"
    r"(?:iii|iv|vi)\s+nervio\s+craneal)\b")
_CALIFICADOR_LIMITACION_RE = re.compile(
    r"\b(mecanic[oa]|parcial|leve|moderad[oa]|marcad[oa]|severa|completa|total)\b")
_DESCRIPTORES_NISTAGMO_RE = re.compile(
    r"\b(vertical|horizontal|rotatorio|torsional|pendular|espontaneo|adquirido|latente|"
    r"evocado por la mirada|en mirada extrema|en mirada excentrica|en mirada lateral|en posicion primaria)\b")
_EXTREMO_RE = re.compile(
    r"\b(?:mirada extrema|mirada excentrica|extremo de la mirada|agotable|terminal|fin de (?:la )?mirada)\b")
_NO_OCULAR_RE = re.compile(r"\b(?:cervical|muscular|postural|contractura|esternocleido|columna|cuello)\b")
_VINCULO_OCULAR_RE = re.compile(
    r"\b(?:ocular|compensador\w*|compensatori\w*|diplopia|paresia|paralisis|nistagmo|estrabismo|"
    r"motilidad|oblicuo|abduccion|aduccion|troclear|vertical)\b")


@dataclass(frozen=True)
class _SignoMotor:
    base: _HallazgoOcular
    familia: str
    texto: str
    extremo: bool = False


def _secciones(texto: str | None) -> list[tuple[str, str]]:
    norm = _normalize_text(texto)
    if not norm:
        return []
    marcas = list(_ETIQUETA_SECCION_RE.finditer(norm))
    if not marcas:
        return [("libre", norm)]
    secciones = []
    if norm[:marcas[0].start()].strip():
        secciones.append(("libre", norm[:marcas[0].start()]))
    for i, marca in enumerate(marcas):
        fin = marcas[i + 1].start() if i + 1 < len(marcas) else len(norm)
        nombre = _SECCION_CANONICA.get(marca[1], marca[1])
        secciones.append((nombre, norm[marca.end():fin]))
    return secciones


def _es_fisiologico(h: _HallazgoOcular, familia: str) -> bool:
    """Excluye solo la respuesta afirmada como fisiologica de ESTA ocurrencia."""
    if _calificador_afirmado(h.contexto, re.compile(r"\bfisiologic\w*\b")):
        return True
    # Nistagmo optocinetico sin calificador anormal (esos tienen clave propia).
    return familia == "nistagmo" and bool(re.search(r"\boptocinetic\w*|\bokn\b", h.contexto))


def _torticolis_ocular(h: _HallazgoOcular) -> bool:
    if _NO_OCULAR_RE.search(h.contexto):
        return False
    return h.ojo is not None or bool(_VINCULO_OCULAR_RE.search(h.contexto))


def _texto_signo(h: _HallazgoOcular, familia: str, etiqueta: str) -> str:
    contexto = h.contexto
    if familia == "deficit" and etiqueta in ("limitacion", "restriccion"):
        calificador = _CALIFICADOR_LIMITACION_RE.search(contexto)
        if calificador:
            etiqueta += f" {calificador[1]}"
        movimientos = _dedupe(_MOVIMIENTO_RE.findall(contexto))
        if movimientos:
            etiqueta += f" de {_join_hallazgos(movimientos)}"
        elif re.search(r"\btodas las (?:direcciones|posiciones)\b", contexto):
            etiqueta += " en todas las direcciones de la mirada"
    elif familia == "sincinesia" and etiqueta == "sincinesia" and re.search(r"\bmandibul\w*", contexto):
        etiqueta += " mandibulopalpebral"
    elif familia == "deficit" and etiqueta in ("paresia", "paralisis", "oftalmoparesia"):
        # Se conserva la denominacion del registro (p. ej. «del VI par»); no se infiere otra.
        par = _PAR_CRANEAL_RE.search(contexto)
        if par:
            etiqueta += " " + re.sub(r"\b(iii|iv|vi)\b", lambda m: m[1].upper(), par[0])
        else:
            movimientos = _dedupe(_MOVIMIENTO_RE.findall(contexto))
            if movimientos:
                etiqueta += f" de {_join_hallazgos(movimientos)}"
    elif familia == "nistagmo":
        descriptores = _dedupe(_DESCRIPTORES_NISTAGMO_RE.findall(contexto))
        if descriptores:
            etiqueta += " " + " ".join(descriptores)
    return etiqueta


@_memoize_cond
def _signos_motores(req: ImpresionClinicaRequest) -> tuple[_SignoMotor, ...]:
    """Signos afirmados, no explicados como fisiologicos ni antecedentes estables."""
    clinica = req.clinica
    if clinica is None or not clinica.motilidad_ocular:
        return ()
    signos: list[_SignoMotor] = []
    for seccion, texto in _secciones(clinica.motilidad_ocular):
        mapa = _mapa({**_GENERAL, **_POR_SECCION.get(seccion, {})})
        for h in _ocurrencias_oculares(texto, mapa, f"motilidad_ocular:{seccion}"):
            familia, etiqueta = h.hallazgo.split("|", 1)
            if not h.afirmado or _es_fisiologico(h, familia) or _conocido_y_estable(h):
                continue
            if etiqueta == "torticolis" and not _torticolis_ocular(h):
                continue
            signos.append(_SignoMotor(
                h, familia, _texto_signo(h, familia, etiqueta), bool(_EXTREMO_RE.search(h.contexto)),
            ))
    return tuple(signos)


def _sintomas_del_motivo(req: ImpresionClinicaRequest) -> list[_HallazgoOcular]:
    motivo = req.paciente.motivo_consulta if req.paciente else None
    sintomas = _cronologia_de_clausula(_ocurrencias_oculares(motivo, _SINTOMAS, "motivo_consulta"), motivo)
    return [s for s in sintomas if s.afirmado and not s.incierto and not s.por_descartar
            and s.evolucion != "antigua"]


def _cubiertos_por_12(req: ImpresionClinicaRequest) -> set[str | None]:
    """Ojos cuya limitacion motora ya describe la ruta motora aguda de #12."""
    return {c.acompanante.ojo for c in _combinaciones_ptosis(req)
            if c.acompanante.origen.startswith("motilidad_ocular")}


def _motilidad_independiente(req: ImpresionClinicaRequest) -> tuple[_SignoMotor, ...]:
    # El ojo solo no acredita redundancia: una paresia descrita puede coexistir
    # con la limitacion que #12 ya recoge. Comparar la ocurrencia motora real.
    cubiertos = [c.acompanante for c in _combinaciones_ptosis(req)
                 if c.acompanante.origen.startswith("motilidad_ocular")]
    return tuple(s for s in _signos_motores(req) if not (
        s.familia == "deficit" and any(
            s.base.ojo == c.ojo and s.base.contexto.strip() == _ETIQUETA_SECCION_RE.sub("", c.contexto).strip()
            and (s.texto.startswith("limitacion") and c.hallazgo.startswith("limitacion")
                 or s.texto.startswith("oftalmoparesia") and c.hallazgo.startswith("oftalmoparesia")
                 or s.texto.startswith("oftalmoplejia") and c.hallazgo.startswith("oftalmoplejia"))
            for c in cubiertos)))


def _reciente(s: _HallazgoOcular) -> bool:
    return s.evolucion == "cambio reciente"


def _sintomas_alarma(signo: _SignoMotor, req: ImpresionClinicaRequest) -> list[str]:
    """Sintomas explicitos que elevan la prioridad de ESTE signo (ruta por familia)."""
    h = signo.base
    if signo.familia not in ("deficit", "nistagmo", "dolor") or h.evolucion == "antigua":
        return []
    sintomas =[s for s in _sintomas_del_motivo(req) if not _son_hallazgos_contralaterales(s.ojo, h.ojo)]
    elegidos: list[str] = []
    for s in sintomas:
        etiqueta = s.hallazgo
        if signo.familia == "deficit":
            # Diplopia: reciente ella o el deficit; el resto exige inicio reciente,
            # salvo dolor ocular/cervical, disartria o debilidad (alarma sin fecha).
            ok = ((etiqueta == "diplopia referida" and (_reciente(s) or _reciente(h)))
                  or (etiqueta in _TRAUMA | _VISUAL | _VESTIBULAR | {"cefalea referida"} and _reciente(s))
                  or etiqueta in _SIN_FECHA)
        elif signo.familia == "nistagmo":
            ok = ((etiqueta in _VESTIBULAR | _VISUAL | _TRAUMA | {"diplopia referida", "cefalea referida"}
                   and _reciente(s))
                  or etiqueta in {"disartria referida", "debilidad referida"})
        else:  # dolor con el movimiento: solo con deterioro visual (o diplopia) reciente
            ok = etiqueta in _VISUAL | {"diplopia referida"} and _reciente(s)
        if ok:
            elegidos.append(etiqueta)
    # Trauma reciente descrito en la propia exploracion ("tras fractura orbitaria reciente").
    if (signo.familia == "deficit" and _TRAUMA_EN_TEXTO_RE.search(h.contexto)
            and (_reciente(h) or re.search(r"\breciente\b", h.contexto))):
        elegidos.append("traumatismo referido")
    if signo.familia == "deficit" and "traumatismo referido" in elegidos:
        # Con trauma reciente, dolor/nausea/vomito sin fecha acompanan la restriccion.
        elegidos += [s.hallazgo for s in sintomas if s.hallazgo in {"nausea referida", "vomito referido",
                                                                     "dolor referido"}]
    return _dedupe(elegidos)


def _prioridad(signo: _SignoMotor, req: ImpresionClinicaRequest) -> str:
    if _sintomas_alarma(signo, req):
        return "mismo dia"
    h = signo.base
    if (signo.familia in ("deficit", "nistagmo") and _reciente(h) and not h.incierto
            and not (signo.familia == "nistagmo" and signo.extremo)):
        return "urgente"
    return ""


@_memoize_cond
def _cond_motilidad_alterada(req: ImpresionClinicaRequest) -> bool:
    return bool(_motilidad_independiente(req))


def _descripcion(signo: _SignoMotor) -> str:
    base = signo.base
    texto = signo.texto
    if base.ojo in ("AO", "AMBOS"):
        texto += " en ambos ojos"
    # «Torticolis ocular derecho» nombra el lado de la inclinacion, no el ojo.
    sin_ojo = base.ojo in ("AO", "AMBOS") or signo.familia == "postura"
    h = replace(base, hallazgo=texto, ojo=None if sin_ojo else base.ojo)
    prefijo = ("sospecha por descartar de " if h.por_descartar
               else "hallazgo no concluyente de " if h.incierto else "")
    return prefijo + _describir_ocurrencia(h)


def _fusionar_seguimiento(descripciones: list[str]) -> list[str]:
    """«seguimiento discontinuo» + «seguimiento entrecortado» -> una sola frase."""
    seguimiento = [d for d in descripciones if d.startswith("seguimiento ")]
    if len(seguimiento) < 2:
        return descripciones
    fusion = seguimiento[0] + "".join(" y " + d[len("seguimiento "):] for d in seguimiento[1:])
    resto = [d for d in descripciones if not d.startswith("seguimiento ")]
    return [fusion] + resto


def _texto_motilidad_alterada(req: ImpresionClinicaRequest) -> str:
    signos = _motilidad_independiente(req)
    exploracion = _fusionar_seguimiento(_dedupe([_descripcion(s) for s in signos if s.familia != "dolor"]))
    dolores = _dedupe([_descripcion(s) for s in signos if s.familia == "dolor"])
    partes = []
    if exploracion:
        partes.append("la exploracion documenta " + _join_hallazgos(exploracion))
    if dolores:
        partes.append("el paciente refiere " + _join_hallazgos(dolores))
    cuerpo = " y ".join(partes)
    prioridades = [_prioridad(s, req) for s in signos]
    if any(prioridades):
        sintomas = _dedupe([x for s in signos for x in _sintomas_alarma(s, req)])
        texto = "Hallazgo urgente: " + cuerpo
        if sintomas:
            texto += f", con {_join_hallazgos(sintomas)}"
        if "mismo dia" in prioridades:
            return texto + "; esta combinacion amerita valoracion medica el mismo dia para aclarar su origen."
        return texto + "; amerita valoracion especializada urgente para aclarar su origen."
    solo_extremo = all(s.familia == "nistagmo" and s.extremo for s in signos)
    verbo = "ameritan" if len(exploracion) + len(dolores) > 1 else "amerita"
    if solo_extremo:
        # Sin caracterizar, la mirada extrema no permite decidir si es fisiologico.
        return (cuerpo[0].upper() + cuerpo[1:] + ", que amerita caracterizarse (agotable y simetrico si es "
                "fisiologico) para decidir si requiere valoracion especializada.")
    texto = cuerpo[0].upper() + cuerpo[1:] + f", que {verbo} valoracion especializada para aclarar su origen."
    if any(s.familia in ("deficit", "nistagmo") and s.base.evolucion == "indeterminada"
           and not (s.familia == "nistagmo" and s.extremo) for s in signos):
        texto += " Verificar inicio y sintomas asociados (diplopia, dolor, vertigo) para decidir la prioridad de atencion."
    if any(s.base.por_descartar or s.base.incierto for s in signos):
        texto += " Repetir y completar la exploracion motora para verificar o descartar el hallazgo."
    return texto
