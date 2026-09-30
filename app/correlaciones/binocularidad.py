"""Dominio: binocularidad y convergencia (7 correlaciones).

insuficiencia_convergencia (compuesta), ppc_exoforia, cover_exoforia_sintomatica,
cover_endoforia_sintomatica, desviacion_vertical, endotropia_lente, exotropia_lente.
Jerarquia: insuficiencia_convergencia suprime ppc_exoforia y
cover_exoforia_sintomatica para evitar redundancia.
"""
from __future__ import annotations

import re
from dataclasses import replace

from app.correlaciones.base import _memoize_cond
from app.correlaciones.pupilas_motilidad import _cronologia_de_clausula, _ocurrencias_oculares
from app.correlaciones.texto import (
    _contains_keyword,
    _normalize_text,
)
from app.correlaciones.hechos_textuales import _sujeto_es_paciente, _es_hipotetico, _certeza_local
from app.schemas import ImpresionClinicaRequest

_KEYWORDS_DESVIACION_VERTICAL = ("hiperforia", "hipoforia", "hipertropia", "hipotropia")

def _cover_registros_detalle(req: ImpresionClinicaRequest):
    """Conserva lado, afirmacion y duda; el prefijo previo a OD/OI no se descarta."""
    text = _normalize_text(req.clinica.cover_test if req.clinica else None)
    registros = []
    mapa = {}
    for tipo in ("endo", "exo", "hiper", "hipo"):
        mapa[tipo] = tipo
        for sub in ("foria", "tropia"):
            mapa[tipo + sub] = tipo + sub
            mapa[tipo + " y " + sub] = tipo + sub
            mapa[tipo + " - " + sub] = tipo + sub
    secciones = re.split(r"\s*\|\s*", text)
    for seccion in secciones:
        ojo_match = re.search(r"\b(od|oi|ao)\s*:\s*", seccion)
        ojo = ojo_match.group(1).upper() if ojo_match else None
        valor = (seccion[:ojo_match.start()] + " " + seccion[ojo_match.end():]) if ojo_match else seccion
        for h in _ocurrencias_oculares(valor, mapa, "cover_test"):
            if h.afirmado:
                registros.append(replace(h, ojo=ojo or h.ojo))
    return registros


def _cover_registros(req: ImpresionClinicaRequest) -> list[tuple[str | None, str]]:
    """Las entradas planteadas se conservan como registros, sin afirmarlas como medidas."""
    return list(dict.fromkeys((h.ojo, h.hallazgo) for h in _cover_registros_detalle(req)))


def _cover_descripcion(req: ImpresionClinicaRequest, tokens: tuple[str, ...] | None = None) -> str:
    partes = []
    for h in _cover_registros_detalle(req):
        ojo, token = h.ojo, h.hallazgo
        if tokens is not None and token not in tokens:
            continue
        nombres = {"exo": "exodesviacion no clasificada", "endo": "endodesviacion no clasificada",
                   "hiper": "hiperdesviacion no clasificada", "hipo": "hipodesviacion no clasificada"}
        hallazgo = nombres.get(token, token)
        if h.incierto or h.por_descartar:
            hallazgo = "posible " + hallazgo + " (registro por verificar)"
        lado = "ambos ojos" if ojo == "AO" else ojo or "lateralidad no especificada"
        partes.append(f"{hallazgo} en {lado}")
    return "; ".join(partes)


def _fragmentos_paciente(texto: str | None) -> list[str]:
    """Delimita episodios; la pertenencia al paciente se resuelve por ocurrencia."""
    return [f.strip(" ,") for f in re.split(r"[.;!?]+|\b(?:pero|sin embargo|ahora|actualmente)\b", texto or "", flags=re.I)
            if f.strip(" ,")]


def _fragmentos_con_offsets(texto: str | None):
    norm = _normalize_text(texto)
    cursor = 0
    for fragmento in _fragmentos_paciente(texto):
        local = _normalize_text(fragmento)
        inicio = norm.find(local, cursor)
        if inicio >= 0:
            yield fragmento, local, inicio
            cursor = inicio + len(local)


def _hecho_visual_actual(h, texto: str, offset: int = 0) -> bool:
    inicio, fin = offset + h.inicio, offset + h.fin
    if (not h.afirmado or h.incierto or h.por_descartar
            or not _sujeto_es_paciente(texto, inicio, fin)
            or _es_hipotetico(texto, inicio, fin) or _certeza_local(texto, inicio, fin)):
        return False
    if h.evolucion == "antigua":
        return False
    if re.search(r"\b(?:resuelt\w*|asintomatic\w*|tenia|tuvo|presentaba|referia)\b", h.contexto):
        return False
    # Un antecedente fechado («conocida desde 2020») no niega un cambio brusco actual y
    # explicito del mismo sintoma («empeoro subitamente hoy»): se conservan ambos.
    cambio_actual = (h.evolucion == "cambio reciente"
                     and re.search(r"\b(?:empeor\w*|agrav\w*|brusc\w*|subit\w*|repentin\w*|aument\w*|nuev[oa]s?)\b",
                                   h.contexto))
    if cambio_actual:
        return True
    return not re.search(r"\b(?:antecedente\w*|en (?:19|20)\d{2}|desde (?:19|20)\d{2})\b", h.contexto)


def _tarea_de_cerca(texto: str) -> bool:
    return bool(re.search(r"\b(?:al|con|durante|en|de|tras)\s+(?:(?:la|el|usar|uso de|trabajo de)\s+){0,3}"
                          r"(?:leer|lectura|cerca|computadora|pantallas?|celular|estudiar|escribir)\b", texto))


def _sintomas_visuales_actuales(req: ImpresionClinicaRequest, *, cerca: bool = False, binocular: bool = True) -> list[str]:
    """Fragmentos afirmados: fatiga general/cefalea aislada no son sintomas visuales."""
    motivo = req.paciente.motivo_consulta if req.paciente else None
    if not motivo:
        return []
    especificos = ("diplopia", "vision doble", "veo doble", "imagenes dobles", "astenopia",
                   "perdida visual", "perdida de vision", "perdida subita de vision", "perdida repentina de vision", "perdida de la vision",
                   "fatiga visual", "fatiga ocular", "vista cansada", "cansancio visual", "cansancio ocular",
                   "ojos cansados", "vision borrosa", "borroso", "borrosa", "dificultad para enfocar",
                   "ardor ocular", "dolor ocular", "sequedad ocular", "resequedad ocular", "arenilla",
                   "ojo rojo", "ojos rojos", "fotofobia", "lagrimeo", "prurito ocular", "picazon ocular",
                   "molestias oculares", "perdida del renglon", "salto de renglon",
                   "pierde el renglon", "salto de letras", "se juntan las letras", "letras que bailan")
    contextualizables = ("fatiga", "cansancio", "cefalea", "dolor de cabeza", "ardor", "molestia", "molestias", "mareo")
    resultados = []
    completo = _normalize_text(motivo)
    for fragmento, norm, offset in _fragmentos_con_offsets(motivo):
        if binocular and "monocular" in norm:
            continue
        if re.search(r"\b(?:gastric\w*|cutane\w*|muscular\w*|piernas)\b", norm) and not re.search(r"\b(?:ocular\w*|visual\w*|ojos|vision|enfocar|letras)\b", norm):
            continue
        tarea = _tarea_de_cerca(norm)
        visual = _contains_keyword(norm, especificos, allow_negation_window=True)
        visual = visual or (tarea and _contains_keyword(norm, contextualizables, allow_negation_window=True))
        claves = especificos + (contextualizables if tarea else ())
        ocurrencias = _ocurrencias_oculares(fragmento, {k: k for k in claves}, "motivo_consulta")
        actuales = [h for h in ocurrencias if _hecho_visual_actual(h, completo, offset)
                    and (h.hallazgo in especificos or _tarea_de_cerca(h.contexto))]
        visual = visual and bool(actuales)
        if visual and (not cerca or any(_tarea_de_cerca(h.contexto) for h in actuales)):
            resultados.append(fragmento.strip())
    return resultados


def _episodios_visuales(req: ImpresionClinicaRequest):
    """Hechos del paciente con certeza y cronologia propia; 'hoy revision' no fecha el sintoma."""
    motivo = req.paciente.motivo_consulta if req.paciente else None
    mapa = {k: etiqueta for etiqueta, claves in (
        ("diplopia", ("diplopia", "vision doble", "veo doble")),
        ("perdida visual", ("perdida visual", "perdida de vision", "perdida subita de vision",
                            "perdida repentina de vision", "perdida de la vision")),
        ("dolor ocular", ("dolor ocular", "dolor en el ojo", "dolor en los ojos")),
        ("traumatismo", ("traumatismo", "trauma", "golpe")),
        ("ojo rojo", ("ojo rojo", "ojos rojos")),
        ("fotofobia", ("fotofobia",)),
        # Delimitar calificadores de sintomas distintos evita fechar la diplopia
        # antigua con una cefalea nueva en la misma oracion.
        ("otro sintoma", ("cefalea", "dolor de cabeza", "fatiga visual", "fatiga ocular", "dolor cervical")),
    ) for k in claves}
    resultado = []
    completo = _normalize_text(motivo)
    for fragmento, norm, offset in _fragmentos_con_offsets(motivo):
        # Mantener offsets al quitar la fecha de la consulta, que no fecha el sintoma.
        norm = re.sub(r"\b(?:hoy|ayer)\s+(?:revision|control|consulta)\b|\b(?:revision|control|consulta)\s+(?:hoy|ayer)\b", lambda m: "_"*len(m[0]), norm)
        signos = _cronologia_de_clausula(_ocurrencias_oculares(norm, mapa, "motivo_consulta"), norm)
        resultado.extend(h for h in signos if _hecho_visual_actual(h, completo, offset))
    return resultado


def _prioridad_visual_aguda(req: ImpresionClinicaRequest) -> bool:
    return any(h.hallazgo in ("diplopia", "perdida visual") and h.evolucion == "cambio reciente"
               for h in _episodios_visuales(req))


def _perdida_visual_aguda(req: ImpresionClinicaRequest) -> bool:
    return any(h.hallazgo == "perdida visual" and h.evolucion == "cambio reciente" for h in _episodios_visuales(req))


def _emergencia_dolor_ocular(req: ImpresionClinicaRequest) -> bool:
    """Dolor ocular con traumatismo actual o dolor/ojo rojo/fotofobia documentados."""
    sintomas = _episodios_visuales(req)
    compatibles = lambda a,b: a.ojo is None or b.ojo is None or a.ojo==b.ojo or a.ojo in ("AO","AMBOS") or b.ojo in ("AO","AMBOS")
    for dolor in (s for s in sintomas if s.hallazgo=="dolor ocular"):
        otros = [s for s in sintomas if compatibles(dolor,s)]
        if any(s.hallazgo=="traumatismo" and s.evolucion=="cambio reciente" for s in otros):
            return True
        if any(s.hallazgo=="ojo rojo" for s in otros) and any(s.hallazgo=="fotofobia" for s in otros):
            return True
    return False


def _prioridad_sintomas_agudos(req: ImpresionClinicaRequest) -> str | None:
    """Prioridad independiente de Rx/AV/BUT, solo desde episodios reales del paciente."""
    if _emergencia_dolor_ocular(req) or _perdida_visual_aguda(req):
        return "inmediata"
    if _prioridad_visual_aguda(req):
        return "mismo dia"
    return None


def _con_prioridad_visual(req: ImpresionClinicaRequest, texto: str) -> str:
    prioridad = _prioridad_sintomas_agudos(req)
    if prioridad == "inmediata":
        return ("Hallazgo urgente: " + texto[0].lower() + texto[1:] +
                " Por los sintomas oculares documentados, requiere valoracion oftalmologica inmediata en urgencias, sin esperar el control periodico.")
    if prioridad == "mismo dia":
        return ("Hallazgo urgente: " + texto[0].lower() + texto[1:] +
                " Por el inicio agudo referido, requiere valoracion oftalmologica el mismo dia, sin esperar el control periodico.")
    return texto


def _contexto_cover(req: ImpresionClinicaRequest) -> str:
    motivo = req.paciente.motivo_consulta if req.paciente else None
    if motivo and re.search(r"\b(?:conocid\w*|antigu\w*|estable\w*|congenit\w*|control|compensad\w*|concluyente|aclarar|correccion|sensorial|sin cambios|ya evaluad\w*|cover|ortoforia|rotura|recuperacion|blanco)\b", _normalize_text(motivo)):
        return f" Contexto referido: {motivo.rstrip('.')}."
    return ""


def _cover_has(req: ImpresionClinicaRequest, deviation: str) -> bool:
    """Consulta registros; no vuelve al 'Exo' original tras reconocer Exo y Tropia."""
    return any(token == deviation for _, token in _cover_registros(req))


def _has_binocular_symptoms(req: ImpresionClinicaRequest) -> bool:
    return bool(_sintomas_visuales_actuales(req))


@_memoize_cond
def _cond_insuficiencia_convergencia(req: ImpresionClinicaRequest) -> bool:
    """Coocurrencia PPC registrado, exoforia y molestias visuales de cerca; no diagnostica IC."""
    if req.clinica is None or req.paciente is None:
        return False
    if req.clinica.ppc_cm is None:
        return False
    if not any(token == "exoforia" for _, token in _cover_registros(req)):
        return False
    return bool(_sintomas_visuales_actuales(req, cerca=True))


def _texto_insuficiencia_convergencia(req: ImpresionClinicaRequest) -> str:
    sintomas = "; ".join(_sintomas_visuales_actuales(req, cerca=True))
    texto = (f"Se registra PPC de {req.clinica.ppc_cm} cm y {_cover_descripcion(req)} en el cover test; "
             f"se refiere: {sintomas}. Conviene completar la evaluacion binocular, verificar el protocolo del PPC "
             "y cuantificar desviacion cerca/lejos y reservas fusionales para determinar la posible relacion con las molestias.")
    return _con_prioridad_visual(req, texto + _contexto_cover(req))


def _cond_ppc_exoforia(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    if _cond_insuficiencia_convergencia(req):
        return False
    return clinica.ppc_cm is not None or _cover_has(req, "exoforia") or _cover_has(req, "exo")


def _texto_ppc_exoforia(req: ImpresionClinicaRequest) -> str:
    partes = []
    clinica = req.clinica
    ppc = clinica.ppc_cm if clinica is not None else None
    if ppc is not None:
        partes.append(f"PPC de {ppc} cm")
    cover = _cover_descripcion(req, ("exoforia", "exo"))
    if cover:
        partes.append(cover + " en el cover test")
    texto = "Se registra " + "; ".join(partes) + "."
    if ppc is not None:
        texto += " Verificar el protocolo de medicion antes de interpretar el PPC."
    if _cover_has(req, "exo"):
        texto += " Conviene precisar el subtipo de la exodesviacion."
    return _con_prioridad_visual(req, texto + _contexto_cover(req))


def _cond_cover_exoforia_sintomatica(req: ImpresionClinicaRequest) -> bool:
    """Exoforia y molestias visuales actuales coexisten; no demuestra descompensacion."""
    if req.clinica is None or req.paciente is None:
        return False
    if _cond_insuficiencia_convergencia(req):
        return False
    return _cover_has(req, "exoforia") and _has_binocular_symptoms(req)


def _texto_cover_exoforia_sintomatica(req: ImpresionClinicaRequest) -> str:
    sintomas = "; ".join(_sintomas_visuales_actuales(req))
    texto = (f"Se registra {_cover_descripcion(req, ('exoforia',))} en el cover test; se refiere: {sintomas}. "
             "Conviene completar la evaluacion binocular para determinar la posible relacion entre los hallazgos y las molestias.")
    return _con_prioridad_visual(req, texto)


def _cond_cover_endoforia_sintomatica(req: ImpresionClinicaRequest) -> bool:
    """Endoforia o Endo sin subtipo junto con molestias visuales actuales."""
    if req.clinica is None or req.paciente is None:
        return False
    hay_endo = _cover_has(req, "endoforia") or _cover_has(req, "endo")
    return hay_endo and _has_binocular_symptoms(req)


def _texto_cover_endoforia_sintomatica(req: ImpresionClinicaRequest) -> str:
    sintomas = "; ".join(_sintomas_visuales_actuales(req))
    texto = (f"Se registra {_cover_descripcion(req)} en el cover test; se refiere: {sintomas}. "
             "Conviene verificar y cuantificar las desviaciones registradas, precisar subtipos pendientes "
             "y completar la evaluacion binocular para determinar la posible relacion con las molestias.")
    return _con_prioridad_visual(req, texto)


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
    tokens = _KEYWORDS_DESVIACION_VERTICAL + ("hiper", "hipo")
    texto = (f"Se registra {_cover_descripcion(req, tokens)} en el cover test. "
             "Conviene verificar y cuantificar la desviacion, precisar los subtipos pendientes "
             "y valorar su relevancia funcional mediante evaluacion binocular.")
    return _con_prioridad_visual(req, texto + _contexto_cover(req))


def _cond_endotropia_lente(req: ImpresionClinicaRequest) -> bool:
    return _cover_has(req, "endotropia")


def _texto_endotropia_lente(req: ImpresionClinicaRequest) -> str:
    texto = (f"Se registra {_cover_descripcion(req, ('endotropia',))} en el cover test. "
             "Conviene cuantificar la desviacion y completar la evaluacion de estrabismo, incluida la valoracion refractiva.")
    return _con_prioridad_visual(req, texto + _contexto_cover(req))


def _cond_exotropia_lente(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: exotropia manifiesta amerita estudio binocular."""
    return _cover_has(req, "exotropia")


def _texto_exotropia_lente(req: ImpresionClinicaRequest) -> str:
    texto = (f"Se registra {_cover_descripcion(req, ('exotropia',))} en el cover test. "
             "Conviene completar la evaluacion de estrabismo, cuantificar la desviacion "
             "y caracterizar frecuencia, control, funcion binocular y refraccion.")
    return _con_prioridad_visual(req, texto + _contexto_cover(req))
