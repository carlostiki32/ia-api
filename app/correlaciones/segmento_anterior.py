"""Dominio: segmento anterior y cristalino (#17, #18 y #19).

Cada campo (`anexos_oculares`, `fondo_de_ojo`) se evalua por separado, con sus
propios limites de negacion; nunca se concatenan. Cada hallazgo conserva su ojo,
afirmacion, certeza y cronologia (extractor compartido con pupilas/motilidad).
Los avisos describen el signo registrado y la evaluacion que amerita; no
diagnostican ni declaran realizadas biomicroscopia, gonioscopia ni PIO.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, replace

from app.correlaciones.base import _memoize_cond
from app.correlaciones.pupilas_motilidad import (
    _HallazgoOcular,
    _calificador_afirmado,
    _conocido_y_estable,
    _cronologia_de_clausula,
    _describir_ocurrencia,
    _ocurrencias_oculares,
)
from app.correlaciones.texto import _dedupe, _join_hallazgos, _normalize_text
from app.schemas import ImpresionClinicaRequest

_ORIGEN_LEGIBLE = {"anexos": "anexos oculares", "fondo": "fondo de ojo"}


def _reg(diccionario: dict[str, str], familia: str, etiqueta: str, *claves: str) -> None:
    for clave in claves:
        diccionario[clave] = f"{familia}|{etiqueta}"


# --------------------------------------------------------------------------- comun
_PLAN_RE = re.compile(
    r"\b(?:no evaluad[oa]s?|no se evaluo|sin evaluar|pendiente de (?:evaluar|realizar|examen)|"
    r"proxima (?:consulta|cita|revision|valoracion|visita)|"
    r"siguiente (?:consulta|cita|revision|valoracion)|por realizar|a realizar|en (?:el )?proximo control)\b")
_RESUELTO_RE = re.compile(
    r"\b(?:resuelt[oa]s?|desaparecid[oa]s?|curad[oa]s?|remitid[oa]s?|cicatrizad[oa]s?|epitelizad[oa]s?|"
    r"ya sin \w+|sin \w+ actual(?:es)?)\b")

_SINTOMAS_SEGMENTO: dict[str, str] = {}
for _etiqueta, _claves in (
    ("dolor ocular intenso", ("dolor ocular intenso", "dolor intenso", "dolor profundo", "dolor severo")),
    ("dolor ocular", ("dolor ocular", "dolor", "duele")),
    ("halos", ("halos", "halo")),
    ("nausea", ("nausea", "nauseas")),
    ("vomito", ("vomito", "vomitos")),
    ("fotofobia", ("fotofobia",)),
    ("ojo rojo", ("ojo rojo", "enrojecimiento")),
    ("perdida o disminucion visual", ("perdida visual", "perdida de vision", "disminucion visual", "baja visual",
                                        "baja de vision", "vision borrosa", "vision disminuida", "vision reducida")),
    ("fiebre", ("fiebre", "febril")),
    ("diplopia", ("diplopia", "vision doble")),
    ("uso de lentes de contacto", ("lentes de contacto", "lente de contacto", "lentillas")),
    ("traumatismo", ("traumatismo", "golpe", "contusion")),
):
    for _c in _claves:
        _SINTOMAS_SEGMENTO[_c] = f"sintoma|{_etiqueta}"
_SINTOMAS_SEGMENTO["dolor profundo"] = "sintoma|dolor profundo"


def _sintomas_segmento(req: ImpresionClinicaRequest) -> list[_HallazgoOcular]:
    """Sintomas afirmados por fuente, con ojo/cronologia de su propia clausula."""
    textos = [("motivo_consulta", req.paciente.motivo_consulta if req.paciente else None)]
    if req.clinica:
        textos += [("anexos", req.clinica.anexos_oculares), ("fondo", req.clinica.fondo_de_ojo)]
    resultado = []
    for origen, texto in textos:
        norm = _normalize_text(texto)
        for s in _cronologia_de_clausula(_ocurrencias_oculares(texto, _SINTOMAS_SEGMENTO, origen), texto):
            if not s.afirmado or s.incierto or s.evolucion == "antigua":
                continue
            if s.ojo is None:
                inicio = max(norm.rfind(sep, 0, s.inicio) for sep in ".;!?") + 1
                fines = [p for p in (norm.find(sep, s.fin) for sep in ".;!?") if p >= 0]
                ojo = _ojo_de(norm[inicio:min(fines) if fines else len(norm)])
                if ojo in ("OD", "OI"):
                    s = replace(s, ojo=ojo)
            resultado.append(s)
    return resultado


def _etiqueta_sintoma(s: _HallazgoOcular) -> str:
    return s.hallazgo.split("|", 1)[1]


def _sintoma_con_ojo(s: _HallazgoOcular) -> str:
    etiqueta = _etiqueta_sintoma(s)
    return etiqueta + (f" {s.ojo}" if s.ojo in ("OD", "OI") else " en ambos ojos" if s.ojo == "AO" else "")


def _ojos_compatibles(a: str | None, b: str | None) -> bool:
    return not (a in ("OD", "OI") and b in ("OD", "OI") and a != b)


def _reciente(h: _HallazgoOcular) -> bool:
    return h.evolucion == "cambio reciente"


def _sindrome_doloroso_agudo(req: ImpresionClinicaRequest, acompanantes: frozenset[str]) -> list[str]:
    """Dolor ocular reciente acompanado de alguno de `acompanantes` tambien reciente.

    Describe sintomas realmente presentes; no diagnostica cierre angular ni fija PIO.
    """
    sintomas = _sintomas_segmento(req)
    dolor = [s for s in sintomas if _etiqueta_sintoma(s).startswith("dolor") and _reciente(s)]
    otros = [s for s in sintomas if _etiqueta_sintoma(s) in acompanantes and _reciente(s)]
    pares = [(d, o) for d in dolor for o in otros if _ojos_compatibles(d.ojo, o.ojo)]
    if not pares:
        return []
    dolor = [d for d, _ in pares]
    otros = [o for _, o in pares]
    intenso = [_sintoma_con_ojo(s) for s in dolor if "intenso" in _etiqueta_sintoma(s)]
    etiquetas = (intenso or [_sintoma_con_ojo(dolor[0])]) + [_sintoma_con_ojo(s) for s in otros]
    return _dedupe(etiquetas)


def _admisible(h: _HallazgoOcular) -> bool:
    """Hallazgo actual: afirmado, no solo planteado, no resuelto, no conocido y estable."""
    ctx = h.contexto
    if not h.afirmado or _PLAN_RE.search(ctx) or _RESUELTO_RE.search(ctx):
        return False
    return not _conocido_y_estable(h)


def _ojo_de(clausula: str) -> str | None:
    od = bool(re.search(r"\b(?:od|ojo derecho)\b", clausula))
    oi = bool(re.search(r"\b(?:oi|ojo izquierdo)\b", clausula))
    if re.search(r"\b(?:ao|ambos ojos|bilateral\w*)\b", clausula) or (od and oi):
        return "AO"
    return "OD" if od else "OI" if oi else None


def _descripcion_hallazgo(h: _HallazgoOcular, etiqueta: str, origen: str | None = None,
                          diagnostico_referido: bool = False) -> str:
    ojo = None if h.ojo in ("AO", "AMBOS") else h.ojo
    texto = etiqueta + (" en ambos ojos" if h.ojo in ("AO", "AMBOS") else "")
    descripcion = _describir_ocurrencia(replace(h, hallazgo=texto, ojo=ojo))
    if not origen:
        return descripcion
    campo = _ORIGEN_LEGIBLE[origen]
    # Un nombre de sindrome es un diagnostico referido; un signo describe lo observado.
    return descripcion + (f" (diagnostico referido en {campo})" if diagnostico_referido else f" en {campo}")


def _se_registra(descripciones: list[str]) -> str:
    plural = len(descripciones) > 1 or any(d.startswith(("depositos", "signos", "lineas")) for d in descripciones)
    return "se registran" if plural else "se registra"


# --------------------------------------------------------------------------- #17
_SIGNOS_GLAUCOMA: dict[str, str] = {}
_reg(_SIGNOS_GLAUCOMA, "signo", "huso de Krukenberg", "huso de krukenberg", "krukenberg")
_reg(_SIGNOS_GLAUCOMA, "sindrome", "dispersion pigmentaria", "dispersion pigmentaria", "sindrome de dispersion pigmentaria")
_reg(_SIGNOS_GLAUCOMA, "sindrome", "pseudoexfoliacion", "pseudoexfoliacion", "pseudoexfoliativo", "pxf", "pex")
_reg(_SIGNOS_GLAUCOMA, "signo", "material pseudoexfoliativo", "material pseudoexfoliativo")
_reg(_SIGNOS_GLAUCOMA, "signo", "linea de Sampaolesi", "linea de sampaolesi", "sampaolesi")
_NO_SEGMENTO_ANTERIOR_RE = re.compile(r"\b(?:retinian\w*|retina|macul\w*|papil\w*|coroid\w*)\b")

# Combinaciones descriptivas con anatomia explicita (sin nombrar el sindrome).
_COMBOS_GLAUCOMA = (
    ("pigmento en endotelio corneal con defectos de transiluminacion iridiana",
     (r"\bpigmento\b", r"\bendotel\w*", r"\btransiluminacion\b")),
    ("depositos blanquecinos en capsula anterior y margen pupilar",
     (r"\b(?:depositos?|material)\b", r"\bblanquecin\w*", r"\bcapsula anterior\b", r"\b(?:borde|margen) pupilar\b")),
)


@dataclass(frozen=True)
class _SignoGlaucoma:
    base: _HallazgoOcular
    etiqueta: str
    familia: str
    origen: str


def _combos_glaucoma(norm: str, origen: str) -> list[_SignoGlaucoma]:
    """Combina solo hechos anatómicos afirmados; conserva ojos y duda por signo."""
    resultado = []
    mapa = {"pigmento": "pigmento", "defectos de transiluminacion": "transiluminacion",
            "iris con defectos de transiluminacion": "transiluminacion",
            "depositos blanquecinos": "depositos", "material blanquecino": "depositos",
            "margen pupilar": "margen", "borde pupilar": "margen"}
    hechos = [h for h in _ocurrencias_oculares(norm, mapa, origen) if _admisible(h)]
    def misma_clausula(a, b):
        return not re.search(r"[.;|]", norm[min(a.fin, b.fin):max(a.inicio, b.inicio)])
    pares = []
    for a in hechos:
        for b in hechos:
            pigmento = (a.hallazgo == "pigmento" and re.search(r"\bendotel\w*\b", a.contexto)
                        and re.search(r"\bcorneal\b", a.contexto)
                        and b.hallazgo == "transiluminacion"
                        and re.search(r"\b(?:iris|iridian\w*)\b", b.contexto))
            depositos = (a.hallazgo == "depositos" and re.search(r"\bcapsula anterior\b", a.contexto)
                         and b.hallazgo == "margen")
            if misma_clausula(a, b) and (pigmento or depositos):
                etiquetas = ("pigmento en endotelio corneal", "defectos de transiluminacion iridiana") if pigmento else (
                    "depositos blanquecinos en capsula anterior", "margen pupilar con depositos blanquecinos")
                pares.append((a, b, etiquetas, _COMBOS_GLAUCOMA[0 if pigmento else 1][0]))
    for a, b, etiquetas, conjunto in pares:
        if (a.ojo in ("OD", "OI") and b.ojo in ("OD", "OI") and a.ojo != b.ojo
                or a.evolucion != b.evolucion or a.incierto != b.incierto or a.por_descartar != b.por_descartar):
            for h, etiqueta in zip((a, b), etiquetas):
                resultado.append(_SignoGlaucoma(h, etiqueta, "descriptivo", origen))
        else:
            # Un único ojo escrito no identifica automáticamente el otro signo.
            ojo = a.ojo if a.ojo == b.ojo else None
            base = replace(a, hallazgo="combo|" + conjunto, fin=b.fin, ojo=ojo,
                           contexto=a.contexto + "; " + b.contexto,
                           incierto=a.incierto or b.incierto, por_descartar=a.por_descartar or b.por_descartar)
            resultado.append(_SignoGlaucoma(base, conjunto, "descriptivo", origen))
    return resultado


@_memoize_cond
def _signos_glaucoma_secundario(req: ImpresionClinicaRequest) -> tuple[_SignoGlaucoma, ...]:
    if req.clinica is None:
        return ()
    signos = []
    for origen, texto in (("anexos", req.clinica.anexos_oculares), ("fondo", req.clinica.fondo_de_ojo)):
        if not texto:
            continue
        for h in _ocurrencias_oculares(texto, _SIGNOS_GLAUCOMA, origen):
            familia, etiqueta = h.hallazgo.split("|", 1)
            if not _admisible(h):
                continue
            if etiqueta == "dispersion pigmentaria" and _NO_SEGMENTO_ANTERIOR_RE.search(h.contexto):
                continue                       # dispersion pigmentaria retiniana no es del segmento anterior
            signos.append(_SignoGlaucoma(h, etiqueta, familia, origen))
        for combo in _combos_glaucoma(_normalize_text(texto), origen):
            signos.append(combo)
    return tuple(signos)


@_memoize_cond
def _cond_anexos_riesgo_glaucoma_secundario(req: ImpresionClinicaRequest) -> bool:
    """Signo del segmento anterior registrado que amerita evaluar el riesgo glaucomatoso."""
    return bool(_signos_glaucoma_secundario(req))


def _sintomas_alarma_glaucoma(req: ImpresionClinicaRequest) -> list[str]:
    return _sindrome_doloroso_agudo(req, frozenset({"halos", "nausea", "vomito", "perdida o disminucion visual", "ojo rojo"}))


def _texto_anexos_riesgo_glaucoma_secundario(req: ImpresionClinicaRequest) -> str:
    signos = _signos_glaucoma_secundario(req)
    firmes = [s for s in signos if not (s.base.incierto or s.base.por_descartar)]
    dudosos = [s for s in signos if s.base.incierto or s.base.por_descartar]
    frases = []
    if firmes:
        descripciones = _dedupe([
            _descripcion_hallazgo(s.base, s.etiqueta, s.origen, diagnostico_referido=s.familia == "sindrome")
            for s in firmes])
        verbo = _se_registra(descripciones)
        alarma = _sintomas_alarma_glaucoma(req)
        if alarma:
            frases.append(f"Hallazgo urgente: {verbo} {_join_hallazgos(descripciones)}, con {_join_hallazgos(alarma)}; "
                          "esta combinacion amerita valoracion oftalmologica el mismo dia para aclarar su causa, "
                          "sin esperar el control periodico.")
        else:
            que = "que ameritan" if verbo == "se registran" else "que amerita"
            frases.append(f"{verbo.capitalize()} {_join_hallazgos(descripciones)}, {que} evaluacion oftalmologica del "
                          "segmento anterior y del riesgo glaucomatoso, incluyendo presion intraocular y gonioscopia "
                          "segun corresponda.")
    if dudosos:
        frases.append("El registro plantea, sin establecer, "
                      + _join_hallazgos(_dedupe([_descripcion_hallazgo(s.base, s.etiqueta, s.origen) for s in dudosos]))
                      + ". Verificar el hallazgo en la evaluacion del segmento anterior antes de clasificarlo.")
    return " ".join(frases)


# --------------------------------------------------------------------------- #18
# Estados distintos que no se infieren unos de otros: opacidad del cristalino,
# lesion capsular, anomalia de posicion, leucocoria (alertan) y afaquia,
# pseudofaquia/LIO, implante faquico (solo contexto).
_ESTADOS_CRISTALINO: dict[str, str] = {}
_reg(_ESTADOS_CRISTALINO, "opacidad", "opacidad del cristalino", "catarata", "opacidad cristaliniana",
     "opacidad del cristalino", "opacidad de cristalino", "opacidad lenticular", "opacidad subcapsular",
     "opacidad nuclear", "opacidad cortical", "facoesclerosis", "nucleoesclerosis", "esclerosis nuclear",
     "esclerosis del cristalino", "cristalino opaco", "cristalino opacificado")
_reg(_ESTADOS_CRISTALINO, "capsular", "opacidad de capsula posterior", "opacidad de capsula posterior",
     "opacidad de la capsula posterior", "opacidad capsular posterior", "opacidad capsular",
     "opacificacion de capsula posterior", "opacificacion de la capsula posterior", "opacificacion capsular",
     "capsula posterior opaca", "fibrosis de capsula posterior", "fibrosis de la capsula posterior",
     "fibrosis capsular")
_reg(_ESTADOS_CRISTALINO, "catarata_por_caracterizar", "catarata secundaria de localizacion por verificar",
     "catarata secundaria")
_reg(_ESTADOS_CRISTALINO, "posicion", "lente intraocular subluxado", "lente intraocular subluxado",
     "lente intraocular luxado", "lente intraocular descentrado", "lente intraocular decentrado",
     "lente intraocular dislocado", "lio subluxado", "lio luxado", "lio descentrado", "iol subluxado",
     "iol descentrado")
_reg(_ESTADOS_CRISTALINO, "posicion", "cristalino subluxado", "cristalino subluxado", "cristalino luxado",
     "cristalino ectopico", "subluxacion del cristalino", "luxacion del cristalino", "ectopia lentis")
_reg(_ESTADOS_CRISTALINO, "leucocoria", "leucocoria", "leucocoria", "reflejo rojo ausente", "reflejo rojo anormal",
     "reflejo rojo blanco", "reflejo rojo asimetrico", "reflejo pupilar blanco", "ausencia de reflejo rojo")
_reg(_ESTADOS_CRISTALINO, "afaquia", "afaquia", "afaquia", "afaquico", "afaquica")
_reg(_ESTADOS_CRISTALINO, "faquico", "implante faquico", "lente intraocular faquica", "lente faquica",
     "implante faquico", "lente intraocular faquico")
_reg(_ESTADOS_CRISTALINO, "pseudofaquia", "pseudofaquia", "pseudofaquia", "pseudofaco", "pseudofaquico",
     "pseudofaquica", "lente intraocular", "lio", "iol")
# Preservar el tipo documentado: luxacion, descentramiento y reflejo rojo
# anormal no se convierten en subluxacion ni en leucocoria.
for _clave in tuple(_ESTADOS_CRISTALINO):
    _familia = _ESTADOS_CRISTALINO[_clave].split("|", 1)[0]
    if _familia in ("posicion", "leucocoria", "capsular"):
        # La lesion se conserva con la frase del registro; las siglas de lente van en mayuscula
        # («lio subluxado» se leeria como la palabra «lio»).
        _ESTADOS_CRISTALINO[_clave] = f"{_familia}|" + re.sub(r"^(lio|iol)\b", lambda m: m[1].upper(), _clave)

_CIRUGIA_PREVIA_RE = re.compile(
    r"\b(?:operad[oa]s?|cirugia(?: de catarata)?|extraccion|facoemulsificacion|operacion|posoperatori\w*|postoperatori\w*)\b")
_NO_SIGNIFICATIVA_RE = re.compile(
    r"\b(?:no (?:es )?significativ\w*|sin repercusion visual|asintomatic\w*)\b")
# «posterior»/«anterior» sueltos pertenecen a otra estructura («capsula posterior transparente»):
# solo cuentan dentro de «subcapsular posterior/anterior».
_DETALLE_CRISTALINO_RE = re.compile(
    r"\b(nuclear|cortical|subcapsular(?: posterior| anterior)?|leve|incipiente|moderada|densa|"
    r"madura|hipermadura|central)\b")
_CIRUGIA_CATARATA_RE = re.compile(
    r"\b(?:cirugia de catarata|cirugia de cataratas|operacion de catarata|operad[oa] de catarata|facoemulsificacion|"
    r"implante de lente intraocular|cirugia ocular)\b")
_CIRUGIAS = {
    "cirugia de catarata": "cirugia de catarata",
    "cirugia de cataratas": "cirugia de catarata",
    "operacion de catarata": "cirugia de catarata",
    "operado de catarata": "cirugia de catarata",
    "operada de catarata": "cirugia de catarata",
    "facoemulsificacion": "facoemulsificacion",
    "implante de lente intraocular": "implante de lente intraocular",
    "cirugia ocular": "cirugia ocular",
}
# «No se logra observar fondo OD por catarata densa», «Fondo no visible por catarata OI», «Sin vision de
# fondo por catarata»: la negacion recae sobre la observacion, no sobre la opacidad que la impide.
_VISUALIZACION_IMPEDIDA = tuple(
    (re.compile(p), s) for p, s in (
        (r"\b(?:no|sin)\s+(?:se\s+)?(?:logra\w*|pudo|puede|consigue\w*|es\s+posible|fue\s+posible)\s+"
         r"(?:observar|visualizar|ver|explorar|valorar|evaluar)\b(?=[^.;]*\b(?:por|debido a|secundari[oa] a)\b)",
         "visualizacion impedida de"),
        (r"\b(?:fondo|retina|polo posterior|papila|macula)(?:\s+(?:de\s+)?(?:od|oi))?\s+no\s+"
         r"(?:visible|valorable|explorable|observable|evaluable)s?\b(?=[^.;]*\b(?:por|debido a|secundari[oa] a)\b)",
         "fondo impedido"),
        (r"\bsin\s+(?:vision|visualizacion)\s+de\b(?=[^.;]*\b(?:por|debido a|secundari[oa] a)\b)",
         "visualizacion impedida de"),
    ))
# Cirugia reciente sin «hace N dias»: «operado ayer/hoy», «cirugia de catarata reciente», «recien operado».
_CIRUGIA_RECIENTE_RE = re.compile(
    r"\b(?:cirugia|operacion|facoemulsificacion|operad[oa])(?: de cataratas?)?(?:\s+(?:od|oi|ao))?\s+"
    r"(?:ayer|hoy|anoche|esta\s+(?:manana|semana)|reciente|recientemente)\b"
    r"|\brecien\s+operad[oa]\b|\bposoperatorio\s+(?:inmediato|reciente|temprano)\b"
    r"|\bpostoperatorio\s+(?:inmediato|reciente|temprano)\b")
_TIEMPO_ATRAS_RE = re.compile(
    r"\bhace (\d+|un|una|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez) (dia|dias|semana|semanas|mes|meses)\b")
_NUMERO_PALABRA = {"un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7,
                   "ocho": 8, "nueve": 9, "diez": 10}
_DIAS_POSOPERATORIO = 42


@dataclass(frozen=True)
class _EstadoCristalino:
    base: _HallazgoOcular
    familia: str
    etiqueta: str
    origen: str


def _detalle_cristalino(h: _HallazgoOcular, familia: str, norm: str = "") -> str:
    """Calificadores literales del propio hallazgo: se toman del tramo entre comas que lo contiene
    (no de toda la clausula) y un calificador negado («no densa») no cuenta."""
    if familia != "opacidad":
        return ""
    contexto = h.contexto
    frase = norm[h.inicio:h.fin] if norm else ""
    pos = contexto.find(frase) if frase else -1
    if pos >= 0:
        izquierda = contexto.rfind(",", 0, pos) + 1
        derecha = contexto.find(",", pos + len(frase))
        contexto = contexto[izquierda:len(contexto) if derecha == -1 else derecha]
    detalles = [m[1] for m in re.finditer(_DETALLE_CRISTALINO_RE, contexto)
                if not re.search(r"\b(?:no|sin)\s+$", contexto[:m.start()])]
    detalles = _dedupe(detalles)
    return (" " + " ".join(detalles)) if detalles else ""


@_memoize_cond
def _estados_cristalino(req: ImpresionClinicaRequest) -> tuple[_EstadoCristalino, ...]:
    """Estados del cristalino/implante por ojo y por campo (sin concatenar campos)."""
    if req.clinica is None:
        return ()
    estados = []
    for origen, texto in (("anexos", req.clinica.anexos_oculares), ("fondo", req.clinica.fondo_de_ojo)):
        if not texto:
            continue
        # La imposibilidad de observar el fondo no niega la causa afirmada
        # despues de «por». Se limita a esta construccion, conservando cualquier
        # negacion de la propia catarata («por ... sin catarata»).
        texto_extraccion = _normalize_text(texto)
        for patron, sustituto in _VISUALIZACION_IMPEDIDA:
            texto_extraccion = patron.sub(sustituto, texto_extraccion)
        for h in _ocurrencias_oculares(texto_extraccion, _ESTADOS_CRISTALINO, origen):
            familia, etiqueta = h.hallazgo.split("|", 1)
            if familia == "catarata_por_caracterizar" and re.search(r"\bsecundaria a\b", h.contexto):
                # Catarata secundaria A trauma/otra causa no nombra una cápsula posterior.
                familia, etiqueta = "opacidad", "opacidad del cristalino"
                h = replace(h, hallazgo=familia + "|" + etiqueta)
            if not h.afirmado or _PLAN_RE.search(h.contexto) or _RESUELTO_RE.search(h.contexto):
                continue
            if familia == "opacidad":
                # «Catarata operada» es historia quirurgica, no una opacidad presente; una catarata
                # conocida y estable o no significativa es contexto, no un aviso nuevo.
                prefijo = texto_extraccion[max(0, h.inicio - 45):h.inicio]
                mencion_quirurgica = re.search(r"\b(?:cirugia|operacion|extraccion|operad[oa]s?)\s+(?:de\s+)?$", prefijo)
                futuro = bool(re.search(r"\b(?:programad\w*|pendiente|planificad\w*|plan de|se planea)\b", h.contexto))
                cirugia_previa = _calificador_afirmado(h.contexto, _CIRUGIA_PREVIA_RE) and not futuro
                if mencion_quirurgica or cirugia_previa or _NO_SIGNIFICATIVA_RE.search(h.contexto):
                    continue
                if _conocido_y_estable(h):
                    continue
            elif familia in ("capsular", "posicion", "leucocoria", "catarata_por_caracterizar") and _conocido_y_estable(h):
                continue
            estados.append(_EstadoCristalino(h, familia, etiqueta + _detalle_cristalino(h, familia, texto_extraccion), origen))
    return tuple(estados)


def _cirugias_recientes(req: ImpresionClinicaRequest):
    """Procedimiento ocular afirmado del paciente, con intervalo explicito."""
    textos = [req.paciente.motivo_consulta if req.paciente else None]
    if req.clinica:
        textos += [req.clinica.anexos_oculares, req.clinica.fondo_de_ojo]
    cirugias = []
    for texto in textos:
        for h in _ocurrencias_oculares(texto, _CIRUGIAS, "cirugia"):
            if not h.afirmado or h.incierto or h.por_descartar or _PLAN_RE.search(h.contexto):
                continue
            tiempos = list(_TIEMPO_ATRAS_RE.finditer(h.contexto))
            for m in tiempos:
                n = int(m[1]) if m[1].isdigit() else _NUMERO_PALABRA[m[1]]
                dias = n * (1 if m[2].startswith("dia") else 7 if m[2].startswith("semana") else 30)
                if dias <= _DIAS_POSOPERATORIO:
                    cirugias.append((h, dias))
            # Solo cuando la cirugia no trae un intervalo explicito («hace 3 meses» manda sobre un «hoy» ajeno).
            if not tiempos and _calificador_afirmado(h.contexto, _CIRUGIA_RECIENTE_RE):
                cirugias.append((h, 0))
    return cirugias


def _alarma_posoperatoria(req: ImpresionClinicaRequest) -> list[str]:
    cirugias = _cirugias_recientes(req)
    if not cirugias:
        return []
    sintomas = [s for s in _sintomas_segmento(req) if any(
        not (h.ojo in ("OD", "OI") and s.ojo in ("OD", "OI") and h.ojo != s.ojo) for h, _ in cirugias)]
    # Dolor intenso dentro de la ventana posoperatoria basta aunque no traiga fecha propia (no antiguo);
    # la perdida visual exige un cambio reciente («desde hoy»): una vision borrosa estable no alarma.
    dolor = [s for s in sintomas if _etiqueta_sintoma(s) == "dolor ocular intenso"]
    perdida = [s for s in sintomas if _etiqueta_sintoma(s) == "perdida o disminucion visual" and _reciente(s)]
    return _dedupe([_sintoma_con_ojo(s) for s in dolor + perdida])


def _alarma_traumatica(req: ImpresionClinicaRequest, ojo: str | None = None) -> list[str]:
    sintomas = _sintomas_segmento(req)
    if req.clinica:
        for origen, texto in (("anexos", req.clinica.anexos_oculares), ("fondo", req.clinica.fondo_de_ojo)):
            sintomas += [s for s in _cronologia_de_clausula(
                _ocurrencias_oculares(texto, _SINTOMAS_SEGMENTO, origen), texto)
                if s.afirmado and not s.incierto and s.evolucion != "antigua"]
    return _dedupe([_sintoma_con_ojo(s) for s in sintomas if _reciente(s)
                    and not s.incierto
                    and not (ojo in ("OD", "OI") and s.ojo in ("OD", "OI") and ojo != s.ojo)
                    and _etiqueta_sintoma(s) in ("traumatismo", "dolor ocular intenso", "perdida o disminucion visual")])


@_memoize_cond
def _cond_opacidad_cristaliniana(req: ImpresionClinicaRequest) -> bool:
    """Opacidad, lesion capsular, posicion anomala o leucocoria registradas, o alarma posoperatoria.

    Pseudofaquia, LIO, afaquia e implante faquico normales son contexto, no aviso.
    """
    if any(e.familia in ("opacidad", "capsular", "posicion", "leucocoria", "catarata_por_caracterizar") for e in _estados_cristalino(req)):
        return True
    return bool(_alarma_posoperatoria(req))


def _describir_estado(e: _EstadoCristalino) -> str:
    h = e.base
    if h.evolucion == "antigua" and re.search(r"\bcongenit\w*\b", h.contexto):
        # «congenita» no es «de evolucion antigua descrita»: se conserva la palabra del registro.
        return _descripcion_hallazgo(replace(h, evolucion="indeterminada"), e.etiqueta) + " descrita como congenita"
    return _descripcion_hallazgo(h, e.etiqueta)


def _texto_opacidad_cristaliniana(req: ImpresionClinicaRequest) -> str:
    estados = [e for e in _estados_cristalino(req) if e.familia in ("opacidad", "capsular", "posicion", "leucocoria", "catarata_por_caracterizar")]
    firmes = [e for e in estados if not (e.base.incierto or e.base.por_descartar)]
    dudosos = [e for e in estados if e.base.incierto or e.base.por_descartar]
    edad = req.paciente.edad if req.paciente else None
    frases = []
    leucocoria = [e for e in firmes if e.familia == "leucocoria"]
    posicion = [e for e in firmes if e.familia == "posicion"]
    resto = [e for e in firmes if e.familia in ("opacidad", "capsular", "catarata_por_caracterizar")]
    posop = _alarma_posoperatoria(req)
    if leucocoria:
        descripcion = _join_hallazgos(_dedupe([_describir_estado(e) for e in leucocoria]))
        pediatrico = " pediatrica" if edad is not None and edad < 18 else ""
        frases.append(f"Hallazgo urgente: se registra {descripcion}; amerita valoracion oftalmologica{pediatrico} "
                      "urgente el mismo dia para estudiar su causa.")
    if posop:
        pseudofaquia = [e for e in _estados_cristalino(req) if e.familia == "pseudofaquia"]
        contexto = (", " + _join_hallazgos(_dedupe([_describir_estado(e) for e in pseudofaquia]))) if pseudofaquia else ""
        # La fecha de la cirugia es «reciente»; el «hoy» de los sintomas no fecha el procedimiento.
        procedimientos = _join_hallazgos(_dedupe([
            _descripcion_hallazgo(replace(h, evolucion="indeterminada"), h.hallazgo + " reciente")
            for h, _ in _cirugias_recientes(req)]))
        frases.append(f"Hallazgo urgente: se registra {procedimientos}{contexto}, con {_join_hallazgos(posop)}; "
                      "esta combinacion amerita valoracion oftalmologica el mismo dia para aclarar su causa.")
    if posicion:
        descripcion = _join_hallazgos(_dedupe([_describir_estado(e) for e in posicion]))
        alarma = _dedupe([s for e in posicion for s in _alarma_traumatica(req, e.base.ojo)])
        if alarma:
            frases.append(f"Hallazgo urgente: se registra {descripcion}, con {_join_hallazgos(alarma)}; "
                          "esta combinacion amerita valoracion oftalmologica el mismo dia para aclarar su causa.")
        else:
            frases.append(f"Se registra {descripcion}, que amerita valoracion oftalmologica para caracterizar la posicion "
                          "y valorar su repercusion.")
    if resto:
        descripciones = _dedupe([_describir_estado(e) for e in resto])
        plural = len(descripciones) > 1
        menor = edad is not None and edad < 18
        pediatrico = " pediatrica" if menor else ""
        desarrollo = " y el desarrollo visual" if menor else ""
        verbo = "se documentan" if plural else "se documenta"
        que = "que ameritan" if plural else "que amerita"
        pron = "caracterizarlas" if plural else "caracterizarla"
        frases.append(f"{verbo.capitalize()} {_join_hallazgos(descripciones)}, {que} valoracion oftalmologica{pediatrico} "
                      f"para {pron} y valorar su repercusion{desarrollo}.")
    if dudosos:
        # La leucocoria no se orienta al cristalino: su causa no se infiere.
        solo_leucocoria = all(e.familia == "leucocoria" for e in dudosos)
        verificacion = ("Verificar el hallazgo con la exploracion del reflejo rojo antes de clasificarlo."
                        if solo_leucocoria else
                        "Verificar el hallazgo en la evaluacion del cristalino antes de clasificarlo.")
        frases.append("El registro plantea, sin establecer, "
                      + _join_hallazgos(_dedupe([_describir_estado(e) for e in dudosos]))
                      + ". " + verificacion)
    return " ".join(frases)
