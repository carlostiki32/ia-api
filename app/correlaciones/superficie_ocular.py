"""Dominio: superficie ocular - BUT y hallazgos meibomianos (4 correlaciones).

but_critico (BUT < 5), but_pantallas y but_limitrofe (ambas cubren 5-9 s segun
exposicion a pantallas). Son mutuamente excluyentes por construccion.
"""
from __future__ import annotations

import re

from app.correlaciones.base import _memoize_cond
from app.correlaciones.hechos_textuales import _sujeto_es_paciente, _es_hipotetico, _certeza_local
from app.correlaciones.texto import (
    _contains_keyword,
    _keyword_matches,
    _normalize_text,
    _is_match_negated,
)
from app.schemas import ImpresionClinicaRequest

_KEYWORDS_DGM_BLEFARITIS = (
    "blefaritis", "meibomitis", "disfuncion de meibomio",
    "disfuncion de glandulas de meibomio", "glandulas de meibomio",
    "meibomio", "disfuncion glandular", "dgm",
)


def _cond_but_critico(req: ImpresionClinicaRequest) -> bool:
    """Seleccion operativa de BUT <5; no determina enfermedad ni gravedad."""
    clinica = req.clinica
    if clinica is None:
        return False
    but = clinica.ojo_seco_but_seg
    return but is not None and but < 5 and not _cond_ojo_seco_evaporativo_dgm(req)


def _texto_but_critico(req: ImpresionClinicaRequest) -> str:
    return _aviso_but(req)


def _contexto_medicion_but(req: ImpresionClinicaRequest) -> tuple[bool, str | None]:
    """Solo el contexto de la medicion, sin inventar ojo, promedio o tecnica."""
    dudosa, tecnica = False, None
    fuentes = [req.paciente.motivo_consulta if req.paciente else None]
    if req.clinica:
        fuentes += [req.clinica.anexos_oculares, req.clinica.recomendacion_seguimiento]
    for frase in (f for fuente in fuentes for f in re.split(r"[.;]", _normalize_text(fuente))):
        medicion = re.search(r"\b(?:but|ruptura|medicion|prueba)\b", frase)
        if not medicion:
            continue
        if not _sujeto_es_paciente(frase, medicion.start(), medicion.end()) or _es_hipotetico(frase, medicion.start(), medicion.end()):
            continue
        # Una limitacion de otra prueba no se atribuye al BUT.
        if re.search(r"\b(?:amsler|cover|campimetria|refraccion|av|agudeza|pupilas|motilidad)\b", frase) and not re.search(r"\b(?:but|ruptura)\b", frase):
            continue
        for m in re.finditer(r"\b(?:poco confiable|no confiable|no fiable|mala cooperacion|no sostuvo la apertura ocular)\b", frase):
            if (not _is_match_negated(frase, m.start(), m.end())
                    and _sujeto_es_paciente(frase,m.start(),m.end())
                    and not _es_hipotetico(frase,m.start(),m.end())):
                dudosa = True
        if re.search(r"\b(?:but|ruptura)\b", frase):
            for patron, etiqueta in ((r"\bno invasiv[oa]\b", "no invasiva"), (r"\bcon fluoresceina\b", "con fluoresceina")):
                for m in re.finditer(patron, frase):
                    if (not _is_match_negated(frase,m.start(),m.end())
                            and _sujeto_es_paciente(frase,m.start(),m.end())
                            and not _es_hipotetico(frase,m.start(),m.end())):
                        tecnica = etiqueta if tecnica in (None, etiqueta) else "discordante en el registro"
    return dudosa, tecnica


def _aviso_but(req: ImpresionClinicaRequest) -> str:
    but = req.clinica.ojo_seco_but_seg
    dudosa, tecnica = _contexto_medicion_but(req)
    texto = f"Se registra un tiempo de ruptura lagrimal de {but} segundos"
    if tecnica:
        texto += f", con tecnica {tecnica} descrita"
    if dudosa:
        return texto + " en una medicion referida como poco confiable; conviene repetirla antes de interpretarla y valorar la superficie ocular." + _contexto_pantallas(req)
    texto += ", reducido" if but < 5 else ""
    return texto + ". Conviene corroborar la medicion y valorar la estabilidad lagrimal en el contexto de los sintomas y la exploracion." + _contexto_pantallas(req)


def _contexto_pantallas(req: ImpresionClinicaRequest) -> str:
    etiquetas = {"lt2": "menos de 2 horas", "btw2_6": "entre 2 y 6 horas", "gt6": "mas de 6 horas"}
    categoria = req.clinica.uso_pantallas if req.clinica else None
    texto = f" Uso de pantallas declarado: {etiquetas[categoria]} al dia." if categoria in etiquetas else ""
    motivo = req.paciente.motivo_consulta if req.paciente else None
    # Conservar las dos fuentes; nunca reemplazar el dropdown por una estimacion.
    for frase in re.split(r"[.;]", motivo or ""):
        norm = _normalize_text(frase)
        if re.search(r"\bhoras?\b", norm) and re.search(r"pantalla|computador|ordenador", norm):
            texto += f" Exposicion referida en el motivo: «{frase.strip()}»; contrastar con la categoria registrada."
    return texto


def _cond_but_pantallas(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None:
        return False
    but = clinica.ojo_seco_but_seg
    return but is not None and 5 <= but <= 9 and clinica.uso_pantallas in ("btw2_6", "gt6") and not _cond_ojo_seco_evaporativo_dgm(req)


def _texto_but_pantallas(req: ImpresionClinicaRequest) -> str:
    return _aviso_but(req)


def _cond_but_limitrofe(req: ImpresionClinicaRequest) -> bool:
    """Intervalo contractual intermedio; null no es exposicion baja."""
    clinica = req.clinica
    if clinica is None:
        return False
    but = clinica.ojo_seco_but_seg
    return but is not None and 5 <= but <= 9 and clinica.uso_pantallas in (None, "lt2") and not _cond_ojo_seco_evaporativo_dgm(req)


def _texto_but_limitrofe(req: ImpresionClinicaRequest) -> str:
    return _aviso_but(req)


def _hallazgos_meibomianos(req: ImpresionClinicaRequest) -> list[str]:
    """Anomalias afirmadas, no menciones anatomicas ni blefaritis inespecifica."""
    if not req.clinica:
        return []
    norm = _normalize_text(req.clinica.anexos_oculares)
    hallazgos = []
    from app.correlaciones.pupilas_motilidad import _ocurrencias_oculares
    patrones = [
        (r"\b(?:dgm|meibomitis|disfuncion (?:de )?(?:glandulas de )?meibomio|disfuncion meibomiana)\b", "alteracion meibomiana descrita", True),
        (r"\b(?:obstruc\w*|obstruid\w*|taponamiento|no permeables?)\b", "obstruccion meibomiana descrita", False),
        (r"\b(?:secrecion (?:meibomiana )?espesa|meibum espeso)\b", "secrecion meibomiana espesa", False),
        (r"\b(?:mala expresibilidad|expresibilidad reducida)\b", "expresibilidad meibomiana reducida", False),
        (r"\b(?:atrofia|atroficas?)\b", "atrofia meibomiana descrita", False),
    ]
    # Una elipsis puede continuar la misma estructura tras punto y coma, pero
    # no tomar anatomia de otra oracion ni de conjuntiva/Zeis/lagrimal.
    estructura = re.compile(r"meibom\w*|meibum|\bdgm\b|conjuntiv\w*|lagrimal\w*|\bzeis\b|\bmoll\b|corne\w*|cristalin\w*")
    for frase in re.split(r"[.!?|]", norm):
        estructuras = list(estructura.finditer(frase))
        mapa = {m[0]: label for patron, label, _ in patrones for m in re.finditer(patron, frase)}
        if not mapa:
            continue
        for h in _ocurrencias_oculares(frase, mapa, "anexos_oculares"):
            if not h.afirmado or h.incierto or h.por_descartar:
                continue
            if not _sujeto_es_paciente(frase,h.inicio,h.fin) or _es_hipotetico(frase,h.inicio,h.fin) or _certeza_local(frase,h.inicio,h.fin):
                continue
            if (h.evolucion=="antigua" or re.search(r"\b(?:resuelt\w*|controlad\w*|antecedente\w*|previ\w*|estable\w*|"
                                                   r"tenia|tuvo|presentaba|en (?:19|20)\d{2}|desde (?:19|20)\d{2})\b",h.contexto)):
                continue
            directa = h.hallazgo == "alteracion meibomiana descrita"
            if not directa:
                if not estructuras:
                    continue
                # La estructura mas proxima al atributo tiene precedencia.
                anchor = min(estructuras, key=lambda m: min(abs(m.start()-h.fin), abs(h.inicio-m.end())))
                if not re.match(r"meibom|meibum|dgm", anchor[0]):
                    continue
                tramo = frase[anchor.end():h.inicio] if anchor.end()<=h.inicio else ""
                if re.search(r"\b(?:normales?|sin alteraciones|permeables?)\b", tramo) and not re.search(r"\b(?:negad\w*|no permeable\w*)\b", tramo):
                    continue
            ojo = " ambos ojos" if h.ojo in ("AO", "AMBOS") else " " + h.ojo if h.ojo else ""
            label = h.hallazgo + ojo
            if label not in hallazgos:
                hallazgos.append(label)
    return hallazgos


@_memoize_cond
def _cond_ojo_seco_evaporativo_dgm(req: ImpresionClinicaRequest) -> bool:
    """ID historico: coexistencia descriptiva, sin mecanismo evaporativo inferido."""
    return bool(req.clinica and req.clinica.ojo_seco_but_seg is not None
                and req.clinica.ojo_seco_but_seg < 10 and _hallazgos_meibomianos(req))


def _texto_ojo_seco_evaporativo_dgm(req: ImpresionClinicaRequest) -> str:
    return (_aviso_but(req) + " En anexos se registra " + "; ".join(_hallazgos_meibomianos(req))
            + ". Conviene evaluar la funcion de las glandulas de Meibomio junto con la estabilidad lagrimal.")
