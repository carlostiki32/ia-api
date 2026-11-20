"""Combinación y selección de hechos para seguimiento WhatsApp v2 (máx. 1 hecho)."""
from app.seguimiento.catalogo import HECHOS, POR_ID, PRIORIDAD_HECHOS


def combinacion_valida(ids: list[str], elegibles: list[str]) -> bool:
    """Valida que la lista de hechos contenga 0 o 1 hecho y pertenezca a los elegibles."""
    if len(ids) > 1 or len(set(ids)) != len(ids):
        return False
    if not set(ids) <= set(elegibles) or not set(ids) <= POR_ID.keys():
        return False
    return True


def ordenar_hechos(ids: list[str]) -> list[str]:
    """Conserva hasta 1 hecho válido en el catálogo."""
    return [id for id in ids if id in POR_ID][:1]


def seleccionar_respaldo(elegibles: list[str], recetas_previas: int) -> list[str]:
    """Selecciona 0–1 hecho según la prioridad v1 (progresivo/bifocal > hipermetropía)."""
    for tema in PRIORIDAD_HECHOS:
        candidatos = [h.id for h in HECHOS if h.tema == tema and h.id in elegibles]
        if candidatos:
            if recetas_previas % 2:
                candidatos.reverse()
            return [candidatos[0]]
    return []
