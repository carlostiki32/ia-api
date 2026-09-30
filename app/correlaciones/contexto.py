"""Dominio: edad, lente, motivo y agudeza (5 correlaciones activas).

cvs_sospecha, ambliopia_sospecha, ambliopia_isoametropica_bilateral,
deficit_visual_inexplicado_refractivo y adulto_mayor_screening. Los identificadores legacy resumen
datos registrados para revision; no infieren ambliopia, etiologia refractiva,
BCVA ni normalidad de exploraciones no documentadas.
"""
from __future__ import annotations

import re

from app.correlaciones.base import _memoize_cond
from app.correlaciones.binocularidad import _con_prioridad_visual, _cover_descripcion, _cover_registros_detalle, _sintomas_visuales_actuales
from app.correlaciones.refraccion_utils import _av_denominator, _av_es_limitada
from app.correlaciones.texto import _normalize_text, _is_match_negated
from app.correlaciones.hechos_textuales import _sujeto_es_paciente, _es_hipotetico
from app.schemas import ImpresionClinicaRequest

_KEYWORDS_TROPIA = ("endotropia", "exotropia", "hipertropia", "hipotropia")

def _hay_tropia(req: ImpresionClinicaRequest) -> bool:
    return any(h.hallazgo in _KEYWORDS_TROPIA and not h.incierto and not h.por_descartar for h in _cover_registros_detalle(req))


def _ojos_av_para_revision(req: ImpresionClinicaRequest) -> list[tuple[str, str, str | None]]:
    """Seleccion operativa de AV registrada >20/25, sin adjudicar normalidad/BCVA por edad."""
    if req.refraccion is None:
        return []
    return [(label, ojo.av_cc, ojo.av_sc) for label, ojo in (("OD", req.refraccion.od), ("OI", req.refraccion.oi))
            if _av_denominator(ojo.av_cc) is not None and _av_denominator(ojo.av_cc) > 25]


def _diferencia_refraccion_completa(req: ImpresionClinicaRequest) -> bool:
    if req.refraccion is None:
        return False
    od, oi = req.refraccion.od, req.refraccion.oi
    if any(v is None for v in (od.esfera, od.cilindro, oi.esfera, oi.cilindro)):
        return False
    # Corte operativo heredado para seleccionar una comparacion, no ambliogenicidad.
    return abs((od.esfera + od.cilindro / 2) - (oi.esfera + oi.cilindro / 2)) > 1.0


def _refraccion_registrada(req: ImpresionClinicaRequest) -> str:
    if req.refraccion is None:
        return ""
    partes = []
    for label, ojo in (("OD", req.refraccion.od), ("OI", req.refraccion.oi)):
        datos = []
        if ojo.esfera is not None:
            datos.append(f"esfera {ojo.esfera:+.2f} D")
        if ojo.cilindro is not None:
            datos.append(f"cilindro {ojo.cilindro:+.2f} D")
        if ojo.eje is not None:
            datos.append(f"eje {ojo.eje} grados")
        if datos:
            partes.append(label + " " + ", ".join(datos))
    return "; ".join(partes)


def _texto_revision_av(req: ImpresionClinicaRequest, ojos=None) -> str:
    ojos = _ojos_av_para_revision(req) if ojos is None else ojos
    partes = [f"AV con correccion {av_cc} en {label}" + (f" (sin correccion {av_sc})" if av_sc else "")
              for label, av_cc, av_sc in ojos]
    texto = "Se registra " + "; ".join(partes) + ". "
    edad = req.paciente.edad if req.paciente else None
    if edad is not None:
        texto += f"Edad registrada: {edad} anos. "
    texto += "La medicion debe interpretarse segun la edad y el metodo utilizado, sin equipararla a la mejor AV corregida. "
    mejores = [label for label, av_cc, av_sc in ojos if _av_denominator(av_sc) is not None
               and _av_denominator(av_sc) < _av_denominator(av_cc)]
    if mejores:
        texto += (f"La AV sin correccion registrada es mejor que la AV con correccion en {' y '.join(mejores)}; "
                  "revisar la concordancia de las mediciones y la correccion. ")
    texto += "Conviene verificar la medicion y la correccion utilizada, y completar la evaluacion oftalmologica para aclarar estos hallazgos."
    fuentes = [("motivo", req.paciente.motivo_consulta if req.paciente else None)]
    if req.clinica:
        fuentes += [("anexos", req.clinica.anexos_oculares), ("seguimiento",req.clinica.recomendacion_seguimiento)]
    for origen, valor in fuentes:
        norm = _normalize_text(valor)
        claves = r"\b(?:maxima|mejor|bcva|adaptacion|parcial|reducida|fiable|confiable|cooperacion|colaboracion|diagnosticad\w*|conocid\w*|estable|estenopeico|occipital)\b"
        relevantes = [m for m in re.finditer(claves, norm)
                      if _sujeto_es_paciente(norm,m.start(),m.end()) and not _es_hipotetico(norm,m.start(),m.end())]
        # Una nota sobre otra prueba no modifica la interpretacion de la AV.
        propia = bool(re.search(r"\b(?:av|agudeza|bcva|graduacion|receta|correccion|refraccion|estenopeico)\b",norm))
        ajena = bool(re.search(r"\b(?:but|amsler|cover|campimetria|lagrimal)\b",norm))
        if relevantes and (propia or (origen=="motivo" and not ajena)):
            etiqueta = "Contexto referido" if origen=="motivo" else f"Contexto referido en {origen}"
            texto += f" {etiqueta}: {valor.rstrip('.')}."
            dudosa = False
            for frase in re.split(r"[.;]",norm):
                medicion_av = bool(re.search(r"\b(?:av|agudeza|bcva)\b",frase))
                otra_prueba = bool(re.search(r"\b(?:but|amsler|cover|campimetria)\b",frase))
                for m in re.finditer(r"\b(?:poco confiable|no confiable|no fiable|fiabilidad reducida)\b",frase):
                    if (medicion_av or not otra_prueba) and not _is_match_negated(frase,m.start(),m.end()):
                        dudosa = True
            if dudosa:
                texto += " Conviene repetir la medicion de AV antes de interpretarla."
    return _con_prioridad_visual(req, texto)


@_memoize_cond
def _cond_ambliopia_sospecha(req: ImpresionClinicaRequest) -> bool:
    """AV y diferencia entre recetas completas y/o tropia registradas; no infiere ambliopia."""
    return bool(_ojos_av_para_revision(req)) and (_diferencia_refraccion_completa(req) or _hay_tropia(req))


def _texto_ambliopia_sospecha(req: ImpresionClinicaRequest) -> str:
    texto = _texto_revision_av(req)
    if _diferencia_refraccion_completa(req):
        texto += f" Coexiste una diferencia entre las recetas registradas: {_refraccion_registrada(req)}."
    elif _refraccion_registrada(req):
        texto += f" Graduaciones registradas: {_refraccion_registrada(req)}."
    if _hay_tropia(req):
        texto += f" En el cover test se registra {_cover_descripcion(req)}."
    return texto


@_memoize_cond
def _cond_ambliopia_isoametropica_bilateral(req: ImpresionClinicaRequest) -> bool:
    """AV y graduaciones bilaterales en menor: seleccion de datos para revision, sin etiologia."""
    if req.refraccion is None or req.paciente is None or req.paciente.edad is None:
        return False
    if req.paciente.edad >= 18:
        return False
    od = req.refraccion.od
    oi = req.refraccion.oi
    if not (_av_es_limitada(od.av_cc) and _av_es_limitada(oi.av_cc)):
        return False
    # El resumen54 ya describe ambos ojos, sus recetas y la tropia/diferencia.
    if _cond_ambliopia_sospecha(req):
        return False
    ambos_hiper = (od.esfera is not None and od.esfera >= 4.00) and (oi.esfera is not None and oi.esfera >= 4.00)
    ambos_astig = (od.cilindro is not None and od.cilindro <= -2.50) and (oi.cilindro is not None and oi.cilindro <= -2.50)
    return ambos_hiper or ambos_astig


def _texto_ambliopia_isoametropica_bilateral(req: ImpresionClinicaRequest) -> str:
    texto = _texto_revision_av(req).replace("evaluacion oftalmologica", "evaluacion oftalmologica pediatrica")
    return texto + f" Graduaciones registradas: {_refraccion_registrada(req)}."


def _cond_cvs_sospecha(req: ImpresionClinicaRequest) -> bool:
    """Uso documentado de pantallas y molestias oculares/visuales; no acredita CVS."""
    if req.clinica is None or req.paciente is None:
        return False
    if req.clinica.uso_pantallas not in ("lt2", "btw2_6", "gt6"):
        return False
    return bool(_sintomas_visuales_actuales(req, binocular=False))


def _texto_cvs_sospecha(req: ImpresionClinicaRequest) -> str:
    exposicion = {"lt2": "menos de 2 horas diarias", "btw2_6": "entre 2 y 6 horas diarias", "gt6": "mas de 6 horas diarias"}
    sintomas = "; ".join(_sintomas_visuales_actuales(req, binocular=False))
    texto = (f"Se registra uso de pantallas de {exposicion[req.clinica.uso_pantallas]} y se refiere: {sintomas}. "
             "Conviene caracterizar las molestias y valorar la superficie ocular y la funcion visual; "
             "las condiciones de trabajo visual pueden revisarse segun el contexto referido.")
    return _con_prioridad_visual(req, texto)


def _ojos_deficit_inexplicado(req: ImpresionClinicaRequest) -> list[tuple[str, str, str | None]]:
    """AV pendientes de resumir por ojo; el nombre legacy no establece una causa."""
    ojos = _ojos_av_para_revision(req)
    descritos = set()
    if _cond_ambliopia_sospecha(req):
        descritos.update(label for label, _, _ in _ojos_av_para_revision(req))
    if _cond_ambliopia_isoametropica_bilateral(req):
        descritos.update(label for label, _, _ in _ojos_av_para_revision(req))
    return [dato for dato in ojos if dato[0] not in descritos]


def _ojo_deficit_inexplicado(req: ImpresionClinicaRequest):
    """Compatibilidad: tupla (label, av_cc, av_sc) del primer ojo inexplicado, o None."""
    ojos = _ojos_deficit_inexplicado(req)
    return ojos[0] if ojos else None


@_memoize_cond
def _cond_deficit_visual_inexplicado_refractivo(req: ImpresionClinicaRequest) -> bool:
    """Datos AV para comprobacion; no atribuye deficit refractivo, organico o inexplicado."""
    if req.refraccion is None:
        return False
    if req.paciente is not None and req.paciente.edad is not None and req.paciente.edad >= 60:
        return False
    return bool(_ojos_deficit_inexplicado(req))


def _texto_deficit_visual_inexplicado_refractivo(req: ImpresionClinicaRequest) -> str:
    return _texto_revision_av(req, _ojos_deficit_inexplicado(req))


def _cond_adulto_mayor_screening(req: ImpresionClinicaRequest) -> bool:
    """Mismo aviso factual de AV; >=60 solo enruta el contexto de edad legacy."""
    if req.paciente is None or req.refraccion is None:
        return False
    edad = req.paciente.edad
    if edad is None or edad < 60:
        return False

    return bool(_ojos_deficit_inexplicado(req))


def _texto_adulto_mayor_screening(req: ImpresionClinicaRequest) -> str:
    return _texto_revision_av(req, _ojos_deficit_inexplicado(req))

