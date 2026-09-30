"""Prioridad sintomática independiente exigida por la retirada de #27 (D6)."""
import re

from app.correlaciones.binocularidad import _episodios_visuales, _prioridad_sintomas_agudos
from app.schemas import ImpresionClinicaRequest


def _diplopias_agudas(req: ImpresionClinicaRequest):
    return [h for h in _episodios_visuales(req)
            if h.hallazgo == "diplopia" and h.evolucion == "cambio reciente"]


def _cond_diplopia_aguda(req: ImpresionClinicaRequest) -> bool:
    return bool(_diplopias_agudas(req))


def _texto_diplopia_aguda(req: ImpresionClinicaRequest) -> str:
    def _detalle(h) -> str:
        # Un antecedente que empeora de forma brusca no es una diplopia de inicio nuevo.
        empeora = re.search(r"\b(?:empeor\w*|agrav\w*|aument\w*)\b", h.contexto) is not None
        return (("empeoramiento reciente de diplopia" if empeora else "diplopia de inicio reciente")
                + (f" en {h.ojo}" if h.ojo in ("OD", "OI") else ""))

    detalles = list(dict.fromkeys(_detalle(h) for h in _diplopias_agudas(req)))
    plazo = ("inmediata en urgencias" if _prioridad_sintomas_agudos(req) == "inmediata"
             else "el mismo dia")
    return (f"Hallazgo urgente: se refiere {'; '.join(detalles)}. "
            f"Requiere valoracion oftalmologica {plazo}, con evaluacion de la motilidad "
            "y alineacion ocular segun los hallazgos, sin esperar el control periodico. "
            "La refraccion registrada no determina la causa del sintoma.")
