"""Anexos: lesion exacta por ojo, certeza y prioridad sustentada (#19)."""
from __future__ import annotations

import re
from dataclasses import replace

from app.correlaciones.base import _memoize_cond
from app.correlaciones.pupilas_motilidad import _cronologia_de_clausula, _ocurrencias_oculares
from app.correlaciones.segmento_anterior import (
    _SINTOMAS_SEGMENTO, _admisible, _descripcion_hallazgo, _etiqueta_sintoma,
    _ojo_de, _reciente, _sindrome_doloroso_agudo, _sintoma_con_ojo,
)
from app.correlaciones.texto import _dedupe, _join_hallazgos, _normalize_text
from app.schemas import ImpresionClinicaRequest

_KEYWORDS_ANEXOS = {
    "blefaritis": "blefaritis",
    "meibomitis": "meibomitis",
    "disfuncion de meibomio": "disfuncion de glandulas de meibomio",
    "disfuncion glandular": "disfuncion glandular",
    "dgm": "disfuncion de glandulas de meibomio",
    "chalazion": "chalazion",
    "calacio": "chalazion",
    "calazio": "chalazion",
    "orzuelo": "orzuelo",
    "perrilla": "orzuelo",
    "pterigion": "pterigion",
    "pterigio": "pterigion",
    "carnosidad": "carnosidad",
    "pinguecula": "pinguecula",
    "conjuntivitis": "conjuntivitis",
    "hiperemia": "hiperemia",
    "inyeccion conjuntival": "inyeccion conjuntival",
    "inyeccion ciliar": "inyeccion ciliar",
    "queratitis": "queratitis",
    "queratopatia punteada": "queratopatia punteada",
    "erosion": "erosion",
    "abrasion corneal": "abrasion corneal",
    "defecto epitelial": "defecto epitelial",
    "leucoma": "leucoma",
    "nubecula": "nubecula",
    "opacidad corneal": "opacidad corneal",
    "edema corneal": "edema corneal",
    "queratopatia bullosa": "queratopatia bullosa",
    "distriquiasis": "distiquiasis",
    "distiquiasis": "distiquiasis",
    "triquiasis": "triquiasis",
    "ectropion": "ectropion",
    "entropion": "entropion",
    "ptosis": "ptosis",
    "proptosis": "proptosis",
    "dermatochalasis": "dermatochalasis",
    "lagoftalmos": "lagoftalmos",
    "madarosis": "madarosis",
    "dacriocistitis": "dacriocistitis",
    "xantelasma": "xantelasma",
    "ulcera corneal": "ulcera corneal",
    "infiltrado corneal": "infiltrado corneal",
    "cuerpo extrano corneal": "cuerpo extrano corneal",
    "hipopion": "hipopion",
}
_KEYWORDS_OPACIDAD_CRISTALINO = (
    "catarata",
    "cataratas",
    "opacidad cristaliniana",
    "opacidad del cristalino",
    "opacidad lenticular",
    "opacidad subcapsular",
    "facoesclerosis",
    "esclerosis nuclear",
    "nucleoesclerosis",
    "esclerosis del cristalino",
    "pseudofaquia",
    "pseudofaco",
    "pseudofaquico",
    "lente intraocular",
    "iol",
    "afaquia",
    "afaquico",
)


_CALIFICADORES_ANEXO = re.compile(
    r"\b(?:lagrimal|del borde palpebral|cutanea palpebral|cutane[oa]|conjuntival|"
    r"corneal|palpebral|superficial|anterior|superior|inferior|externo|nasal|temporal|central|"
    r"leve|con roce corneal|con exposicion corneal|sobre lesion palpebral ulcerada recurrente)\b")
# Un calificador pertenece al hallazgo solo si va pegado a su nombre: lo separan una coma, una
# conjuncion o una preposicion («dacriocistitis OI con fiebre y edema palpebral» no es una
# «dacriocistitis palpebral»).
_LIMITE_CALIFICADOR = re.compile(
    r"[,;.:|]|\bcon\b(?!\s+(?:roce|exposicion)\s+corneal)|\b(?:y|e|pero|sin|por|tras|desde|hace|ni)\b")


def _detalle_anexo(h, norm: str = "") -> str:
    """Calificadores explicitamente escritos y adyacentes al hallazgo; nunca completar anatomia ausente."""
    if norm:
        despues = norm[h.fin:h.fin + 80]
        corte = _LIMITE_CALIFICADOR.search(despues)
        despues = despues[:corte.start()] if corte else despues
        antes = norm[max(0, h.inicio - 30):h.inicio]
        cortes = list(_LIMITE_CALIFICADOR.finditer(antes))
        antes = antes[cortes[-1].end():] if cortes else antes
        ventana = antes + " " + despues
    else:
        ventana = h.contexto
    detalles = _CALIFICADORES_ANEXO.findall(ventana)
    texto = h.hallazgo
    for detalle in _dedupe(detalles):
        if detalle not in texto:
            texto += " " + detalle
    return _descripcion_hallazgo(h, texto)


@_memoize_cond
def _anexos_ocurrencias(req: ImpresionClinicaRequest):
    if req.clinica is None:
        return ()
    from app.correlaciones.pupilas_motilidad import _combinaciones_ptosis
    cubiertas = {c.ptosis.ojo for c in _combinaciones_ptosis(req)}
    return tuple(h for h in _ocurrencias_oculares(req.clinica.anexos_oculares, _KEYWORDS_ANEXOS, "anexos")
                 if _admisible(h)
                 and not (h.evolucion != "cambio reciente" and re.search(r"\b(?:estable|asintomatic\w*)\b", h.contexto))
                 and not (h.hallazgo == "ptosis" and h.ojo in cubiertas))


def _norm_anexos(req: ImpresionClinicaRequest) -> str:
    return _normalize_text(req.clinica.anexos_oculares) if req.clinica else ""


def _anexos_hallazgos(req: ImpresionClinicaRequest) -> list[str]:
    norm = _norm_anexos(req)
    return _dedupe([_detalle_anexo(h, norm) for h in _anexos_ocurrencias(req)])


def _sintomas_anexos(req: ImpresionClinicaRequest):
    textos = [("motivo_consulta", req.paciente.motivo_consulta if req.paciente else None)]
    if req.clinica:
        textos.append(("anexos", req.clinica.anexos_oculares))
    resultado = []
    for origen, texto in textos:
        norm = _normalize_text(texto)
        for s in _cronologia_de_clausula(_ocurrencias_oculares(texto, _SINTOMAS_SEGMENTO, origen), texto):
            if not s.afirmado or s.incierto or s.por_descartar or s.evolucion == "antigua":
                continue
            # Un unico ojo final fecha/localiza los sintomas coordinados de su
            # clausula («dolor y fotofobia OI»); con dos ojos no se propaga.
            # La fiebre, las nauseas y el vomito son sistemicos: el ojo de la lesion no los localiza.
            if _etiqueta_sintoma(s) in ("fiebre", "nausea", "vomito"):
                resultado.append(replace(s, ojo=None))
                continue
            if s.ojo is None:
                inicio = max(norm.rfind(sep, 0, s.inicio) for sep in ".;!?") + 1
                fines = [p for p in (norm.find(sep, s.fin) for sep in ".;!?") if p >= 0]
                ojo = _ojo_de(norm[inicio:min(fines) if fines else len(norm)])
                if ojo in ("OD", "OI"):
                    s = replace(s, ojo=ojo)
            resultado.append(s)
    return resultado


def _lesion_corneal_explicita(h):
    """Erosión/defecto genéricos no acreditan córnea por estar en anexos."""
    if re.search(r"\b(?:conjuntival|cutane\w*|palpebral|piel)\b", h.contexto):
        return False
    lesion = r"(?:erosion(?:es)?|defectos? epitelial(?:es)?)"
    return bool(re.search(rf"\b{lesion}\b\s+(?:(?:od|oi)\s+)?(?:(?:de|en) (?:la )?)?corneal?\b", h.contexto)
                or re.search(rf"\bcornea\b[^,.;]{{0,30}}\b{lesion}\b", h.contexto))


def _alarma_anexos(req: ImpresionClinicaRequest):
    hallazgos = [h for h in _anexos_ocurrencias(req) if not (h.incierto or h.por_descartar)]
    registro = _normalize_text(req.clinica.anexos_oculares) if req.clinica else ""
    urgentes, sintomas = [], []
    for h in hallazgos:
        # Un sintoma escrito en el propio campo de exploracion («dacriocistitis OI con fiebre») es
        # contemporaneo del examen aunque no traiga fecha; en el motivo se exige un cambio reciente.
        asociados = [s for s in _sintomas_anexos(req) if (_reciente(s) or s.origen == "anexos")
                     and not (h.ojo in ("OD", "OI") and s.ojo in ("OD", "OI") and h.ojo != s.ojo)]
        etiquetas = {_etiqueta_sintoma(s) for s in asociados}
        superficie = (h.hallazgo in {"queratitis", "queratopatia bullosa", "edema corneal", "abrasion corneal",
                                    "inyeccion ciliar", "ulcera corneal", "infiltrado corneal"}
                      or h.hallazgo in {"erosion", "defecto epitelial"} and _lesion_corneal_explicita(h))
        defectos = [d for d in hallazgos if d.hallazgo == "defecto epitelial" and (
                    _lesion_corneal_explicita(d)
                    or h.hallazgo == "infiltrado corneal" and h.fin <= d.inicio
                    and re.fullmatch(r"\s*(?:(?:od|oi|central|periferic[oa]|superior|inferior|nasal|temporal)\s+)*con\s*",
                                     registro[h.fin:d.inicio])
                    and not re.search(r"\b(?:conjuntival|cutane\w*|palpebral|piel)\b", d.contexto))
                    and (d.ojo == h.ojo or d.ojo is None or h.ojo is None)]
        alarma = (h.hallazgo in {"ulcera corneal", "cuerpo extrano corneal", "hipopion"}
                  or (h.hallazgo == "infiltrado corneal" and defectos)
                  or (superficie and bool(etiquetas & {"dolor ocular", "dolor ocular intenso", "dolor profundo", "fotofobia",
                                                       "perdida o disminucion visual"}))
                  or (h.hallazgo == "proptosis" and _reciente(h))
                  or (h.hallazgo == "dacriocistitis" and "fiebre" in etiquetas))
        if alarma:
            urgentes.append(h)
            if h.hallazgo == "infiltrado corneal":
                urgentes += defectos
            sintomas += [_sintoma_con_ojo(s) for s in asociados]
    # Esta combinacion de sintomas exige triaje incluso sin lesion o hipermetropia.
    sintomas += _sindrome_doloroso_agudo(req, frozenset({"halos", "nausea", "vomito", "fotofobia", "perdida o disminucion visual"}))
    return urgentes, _dedupe(sintomas)


def _cond_anexos_patologicos(req: ImpresionClinicaRequest) -> bool:
    """Lesion actual que amerita evaluacion, o sintomas de alarma independientes."""
    return bool(_anexos_ocurrencias(req) or _alarma_anexos(req)[1])


def _texto_anexos_patologicos(req: ImpresionClinicaRequest) -> str:
    urgentes, sintomas = _alarma_anexos(req)
    norm = _norm_anexos(req)
    frases = []
    if urgentes or sintomas:
        hechos = _dedupe([_detalle_anexo(h, norm) for h in urgentes] + sintomas)
        referente = "esta combinacion amerita" if len(hechos) > 1 else "este hallazgo amerita"
        frases.append(f"Hallazgo urgente: se registra {_join_hallazgos(hechos)}; {referente} "
                      "valoracion oftalmologica el mismo dia para aclarar su causa.")
    firmes = [h for h in _anexos_ocurrencias(req) if h not in urgentes and not (h.incierto or h.por_descartar)]
    if firmes:
        frases.append("En anexos oculares se documenta " + _join_hallazgos(_dedupe([_detalle_anexo(h, norm) for h in firmes]))
                      + ", que amerita evaluacion oftalmologica para caracterizar la lesion y valorar su repercusion.")
    dudosos = [h for h in _anexos_ocurrencias(req) if h.incierto or h.por_descartar]
    if dudosos:
        frases.append("El registro plantea, sin establecer, " + _join_hallazgos(_dedupe([_detalle_anexo(h, norm) for h in dudosos]))
                      + ". Verificar el hallazgo antes de clasificarlo.")
    return " ".join(frases)


# #17 (anexos_riesgo_glaucoma_secundario) y #18 (opacidad_cristaliniana) viven en
# segmento_anterior.py. `_KEYWORDS_OPACIDAD_CRISTALINO` se conserva solo para
# contexto.py (causas organicas de AV baja); su revision corresponde a #56.

