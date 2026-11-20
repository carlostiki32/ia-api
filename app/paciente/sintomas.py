"""Síntomas personales ciertos; offsets en el motivo original, nunca inferidos."""
from dataclasses import dataclass
import re
import unicodedata

from app.correlaciones.hechos_textuales import _sujeto_es_paciente, _es_hipotetico, _certeza_local
from app.correlaciones.texto import _is_match_negated
from app.correlaciones.vocabulario import (
    DIPLOPIA_PATRON, PERDIDA_VISION_PATRON, SOMBRA_CORTINA_PATRON,
)

VERSION = "sintomas-v1"
PATRONES = {
    "diplopia": DIPLOPIA_PATRON,
    "perdida_visual": PERDIDA_VISION_PATRON,
    "sombra_cortina": SOMBRA_CORTINA_PATRON,
    "vision_borrosa": r"\b(?:vision\s+borrosa|v(?:e|eo)\s+borroso|borrosidad)\b",
    "fatiga_visual": r"\b(?:cansancio|fatiga)\s+(?:visual|ocular)|\bastenopia\b",
    "cefalea": r"\b(?:dolor(?:es)?\s+de\s+cabeza|cefaleas?)\b",
    "ardor": r"\b(?:ardor|escozor)(?:\s+(?:ocular|en\s+(?:los|sus)\s+ojos))?\b",
    "lagrimeo": r"\b(?:lagrimeo|ojos\s+llorosos)\b",
    "comezon": r"\b(?:comezon|picazon|prurito)(?:\s+(?:ocular|en\s+(?:los|sus)\s+ojos))?\b",
}
IDS = ("vision_borrosa_lejos", "vision_borrosa_cerca", *PATRONES)


def normalizar(texto):
    return " ".join("".join(c for c in unicodedata.normalize("NFD", texto.lower())
                            if not unicodedata.combining(c)).split())


def _con_offsets(texto):
    letras, posiciones = [], []
    for i, c in enumerate(texto):
        for letra in unicodedata.normalize("NFD", c.lower()):
            if not unicodedata.combining(letra):
                letras.append(letra); posiciones.append(i)
    return "".join(letras), posiciones


@dataclass(frozen=True)
class OcurrenciaSintoma:
    sintoma: str
    literal: str
    inicio: int
    fin: int
    sujeto: str = "paciente"
    certeza: str = "afirmado"
    negado: bool = False
    hipotetico: bool = False


def ocurrencias(texto):
    """Encuentra candidatos léxicos, conservando la distancia solo si está escrita."""
    norm, offsets = _con_offsets(texto)
    for id, patron in PATRONES.items():
        for m in re.finditer(patron, norm):
            fin, canon = m.end(), id
            if id == "vision_borrosa":
                sufijo = re.match(r"\s+(?:(?:al\s+(?:mirar|leer|ver|observar)|de|a|los\s+objetos)\s+)?(?:lo\s+)?(lejos|cerca|lejanos|cercanos)\b", norm[fin:])
                if sufijo:
                    fin += sufijo.end()
                    canon += "_lejos" if sufijo[1] in ("lejos", "lejanos") else "_cerca"
            yield canon, m.start(), fin, norm, offsets


def extraer_sintomas(texto: str | None) -> tuple[OcurrenciaSintoma, ...]:
    if not texto:
        return ()
    encontrados = []
    for canon, inicio, fin, norm, offsets in ocurrencias(texto):
        if (not _sujeto_es_paciente(norm, inicio, fin) or _es_hipotetico(norm, inicio, fin)
                or _certeza_local(norm, inicio, fin) or _is_match_negated(norm, inicio, fin)):
            continue
        # Una duda o una alternativa coordinada no acredita una vivencia cierta.
        izquierda = re.split(r"[.!?;]|\bpero\b", norm[:inicio])[-1]
        if re.search(r"\b(?:quizas|tal vez|no sabe si|podria|puede que|duda|posible|probable|sospecha)\b", izquierda):
            continue
        if canon.startswith("vision_borrosa") and re.match(r"\s+(?:o|y)\s+(?:de\s+)?(?:cerca|lejos)\b", norm[fin:]):
            continue
        a, b = offsets[inicio], offsets[fin - 1] + 1
        encontrados.append(OcurrenciaSintoma(canon, texto[a:b], a, b))
    return tuple(sorted(encontrados, key=lambda x: x.inicio))
