from itertools import combinations

from app.seguimiento.catalogo import (
    HECHOS, POR_ID, PUEDE_CAMBIAR, COMODIDAD_ARMAZON, PRIORIDAD_A, PRIORIDAD_B,
)


def combinacion_valida(ids: list[str], elegibles: list[str]) -> bool:
    if len(ids) > 2 or len(set(ids)) != len(ids) or not set(ids) <= set(elegibles) or not set(ids) <= POR_ID.keys():
        return False
    hechos = [POR_ID[id] for id in ids]
    if len({h.tema for h in hechos}) != len(hechos) or sum(h.grupo == "A" for h in hechos) > 1:
        return False
    s = set(ids)
    if s & PUEDE_CAMBIAR and s & {"pantallas_muchas", "pantallas_ratos", "vencida_retomar", "general_periodica"}:
        return False
    if {"vencida_retomar", "con_costo_claro"} <= s:
        return False
    if s & {"cerca_adecuado", "cerca_distancias"} and s & {"progresivo_zonas", "progresivo_ajuste", "bifocal_zonas"}:
        return False
    if len(s & COMODIDAD_ARMAZON) > 1:
        return False
    if s == {"general_periodica", "traer_lentes"} and set(elegibles) != s:
        return False
    return True


def ordenar_hechos(ids: list[str]) -> list[str]:
    # Los ids desconocidos se conservan para que el validador los rechace.
    return sorted(ids, key=lambda id: (0, 0) if id in POR_ID and POR_ID[id].grupo == "A"
                  else (1, PRIORIDAD_B.index(id)) if id in PRIORIDAD_B else (2, 0))


def seleccionar_respaldo(elegibles: list[str], recetas_previas: int) -> list[str]:
    a = []
    for tema in PRIORIDAD_A:
        opciones = [h.id for h in HECHOS if h.grupo == "A" and h.tema == tema]
        if recetas_previas % 2:
            opciones.reverse()
        a.extend(id for id in opciones if id in elegibles)
    b = [id for id in PRIORIDAD_B if id in elegibles]
    if a:
        candidatos = [(ai + bi, ai, bi, [x, y]) for ai, x in enumerate(a) for bi, y in enumerate(b)
                      if combinacion_valida([x, y], elegibles)]
        candidatos += [(ai + len(b), ai, len(b), [x]) for ai, x in enumerate(a)]
        return min(candidatos)[3]
    pares = [(bi + bj, bi, bj, [x, y]) for (bi, x), (bj, y) in combinations(enumerate(b), 2)
             if combinacion_valida([x, y], elegibles)]
    return min(pares)[3] if pares else b[:1]
