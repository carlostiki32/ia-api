"""Sujeto y modalidad de una ocurrencia, con offsets del texto normalizado.

No resuelve diagnósticos ni completa temporalidad. Los consumidores conservan el
campo de origen, lateralidad y estado de cada hallazgo, antes de combinarlo.
"""
from __future__ import annotations

import re

_FAMILIAR = r"(?:madre|padre|herman[oa]|hij[oa]|abuel[oa]|espos[oa]|pareja|ti[oa]|prim[oa]|familiar)"
_SUJETO_FAMILIAR = re.compile(
    rf"\b(?:(?:mi|su|la|el|una?|del?)\s+)?{_FAMILIAR}\b"
    r"(?:\s+(?:del?\s+paciente|de\s+la\s+paciente))?"
    r"(?:\s+que)?\s+(?:se\s+)?(?:tiene|tuvo|tenia|ha\s+tenido|presenta|presento|ha\s+presentado|padece|padecio|refiere|refirio|con|"
    r"sufre|sufrio|describe|reporta|perdio|perdia|nota|noto|ha\s+notado|desarrollo|experimenta|operad[oa]|diagnosticad[oa]|"
    r"es|esta|fue|queja|quejo|quejaba|comenzo|comienza|empezo|empieza|inicio|inicia|siente|sintio|ve|veia|vio|acusa|acuso|"
    r"manifiesta|manifesto|cursa|lleva|llevaba|sigue|continua)\b"
    # «familiares?» exigia la «e» y no reconocia el singular «antecedente familiar».
    r"|\bantecedentes?\s+(?:familiar(?:es)?|heredofamiliar(?:es)?)\b"
)
_SUJETO_PACIENTE = re.compile(
    r"\b(?:el\s+paciente|la\s+paciente|paciente|yo)\s+"
    r"(?:tiene|tuvo|tenia|presenta|presento|refiere|reporta|con|sin|niega|describe|padece|tengo|refiero|noto|siento|padezco)\b"
    r"|\b(?:(?:el|la)\s+)?paciente\s*:\s*"
    r"|(?:^|[,;]\s*|\b(?:y|pero|ahora)\s+)(?:presento|tengo|refiero|noto|siento|padezco)\b"
)
_ATRIBUCION_POSTERIOR = re.compile(
    r"^\s*(?:(?:od|oi|ao|maxima|mejor|corregida|registrada|grado|i{1,3}|positiv[oa]|"
    r"bilateral|estable|\d+(?:[./]\d+)?)\s+){0,6}"
    rf"(?:en|de|del)\s+(?:(?:la|el|mi|su|una?)\s+)?{_FAMILIAR}\b"
)
_CONDICIONAL = re.compile(
    r"\bsi\s+(?!(?:bien|no\s+es)\b)"
    r"(?:(?:se|yo|el paciente|la paciente)\s+)?(?:presentara|presentase|apareciera|apareciese|tuviera|tuviese|notara|notase|"
    r"desarrollara|desarrollase|ocurriera|ocurriese|presenta|presento|tengo|noto|veo|aparece|tiene|nota|hay|hubiera|hubiese|midiera|midiese|mediera|mediese|mide)\b"
    r"|\ben\s+caso\s+de(?:\s+que)?\b"
    r"|\b(?:volver|acudir|regresar|consultar)\s+(?:de\s+inmediato\s+)?si\b"
    r"|\b(?:explican?|explicaron|educacion\s+sobre)\s+(?:los\s+)?signos\s+de\s+alarma\b"
)
_CERTEZA = re.compile(r"\b(posibles?|probables?|sospecha(?:\s+de)?|(?:para\s+|a\s+)?descartar|descarte\s+de)\b")
_REINICIO = re.compile(r"[,;]|\b(?:pero|sin\s+embargo|mientras|ahora)\b|\b(?:y|e)\s+(?:se\s+)?(?:observa|presenta|refiere|reporta|documenta)\b")


def _limites(texto: str, inicio: int, fin: int) -> tuple[int, int]:
    # Un punto decimal no cambia el sujeto de C/D 0.7 ni de una medición.
    cortes = list(re.finditer(r"(?<!\d)[.!?;|\n]|[.!?;|\n](?!\d)", texto))
    anteriores = [m.end() for m in cortes if m.end() <= inicio]
    siguientes = [m.start() for m in cortes if m.start() >= fin]
    return max(anteriores, default=0), min(siguientes, default=len(texto))


def _sujeto_es_paciente(texto: str, inicio: int, fin: int) -> bool:
    """No atribuye al paciente antecedentes de terceros ni pierde su sujeto
    cuando un familiar es objeto (p. ej. «mientras cuido a mi madre»).
    """
    izq, der = _limites(texto, inicio, fin)
    prefijo = texto[izq:inicio]
    # El verbo puede ser parte del propio hallazgo («mi padre perdió la mitad
    # del campo»). Leer hasta fin evita perder al sujeto justo en ese límite.
    familiar = [m for m in _SUJETO_FAMILIAR.finditer(texto[izq:fin]) if m.start() < inicio - izq]
    # «madre del paciente presenta»: «paciente» completa al familiar, no es un sujeto nuevo.
    paciente = [m for m in _SUJETO_PACIENTE.finditer(prefijo)
                if not re.search(r"\b(?:del|de\s+la)\s*$", prefijo[:m.start()])]
    if familiar and (not paciente or familiar[-1].start() > paciente[-1].start()):
        return False
    if _ATRIBUCION_POSTERIOR.search(texto[fin:der]):
        return False
    # «Mi madre: DGM» / «antecedentes de mi padre: ...» también explicitan sujeto.
    etiqueta = re.search(rf"\b{_FAMILIAR}\s*:\s*", prefijo)
    if etiqueta and (not paciente or etiqueta.start() > paciente[-1].start()):
        return False
    return True


def _es_hipotetico(texto: str, inicio: int, fin: int) -> bool:
    """Condicional/educación; posible y probable siguen siendo hallazgos dudosos."""
    izq, _ = _limites(texto, inicio, fin)
    prefijo = texto[izq:inicio]
    condiciones = list(_CONDICIONAL.finditer(prefijo))
    if not condiciones:
        return False
    ultimo = condiciones[-1]
    # Una afirmación explícita posterior abre un episodio del paciente distinto.
    return not _SUJETO_PACIENTE.search(prefijo, ultimo.end())


def _certeza_local(texto: str, inicio: int, fin: int) -> str | None:
    """Calificador ligado a la ocurrencia; no al último plan del campo entero."""
    izq, der = _limites(texto, inicio, fin)
    prefijo = texto[izq:inicio]
    cortes = list(_REINICIO.finditer(prefijo))
    if cortes:
        prefijo = prefijo[cortes[-1].end():]
    candidatos = list(_CERTEZA.finditer(prefijo))
    if candidatos:
        valor = candidatos[-1].group()
    else:
        sufijo = re.match(r"\s*(?:(?:od|oi|ao)\s+)?(posibles?|probables?|sospechosos?|sospechosas?)\b", texto[fin:der])
        if not sufijo:
            return None
        valor = sufijo.group(1)
    if "descart" in valor:
        return "a descartar"
    if valor.startswith("sospech"):
        return "sospecha"
    return valor.removesuffix("s")
