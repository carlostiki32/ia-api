from itertools import combinations, product
import pytest

from app.seguimiento.catalogo import HECHOS, PUEDE_CAMBIAR, COMODIDAD_ARMAZON
from app.seguimiento.combinacion import combinacion_valida, seleccionar_respaldo

TODOS = [h.id for h in HECHOS]
PROHIBIDAS = list(product(PUEDE_CAMBIAR, ("pantallas_muchas", "pantallas_ratos", "vencida_retomar", "general_periodica")))
PROHIBIDAS += [("vencida_retomar", "con_costo_claro")]
PROHIBIDAS += list(product(("cerca_adecuado", "cerca_distancias"), ("progresivo_zonas", "progresivo_ajuste", "bifocal_zonas")))
PROHIBIDAS += list(combinations(COMODIDAD_ARMAZON, 2))


@pytest.mark.parametrize("pareja", PROHIBIDAS)
def test_parejas_prohibidas(pareja):
    assert not combinacion_valida(list(pareja), TODOS)


@pytest.mark.parametrize("ids", [[], ["miopia_lejos"], ["miopia_lejos", "pantallas_muchas"], ["pantallas_muchas", "incluida_sin_costo"]])
def test_combinaciones_validas(ids):
    assert combinacion_valida(ids, TODOS)


@pytest.mark.parametrize("ids", [["miopia_lejos", "cerca_adecuado"], ["pantallas_muchas", "pantallas_ratos"],
                                      ["traer_lentes"] * 2, ["traer_lentes", "con_costo_claro", "comodidad_general"], ["inventado"]])
def test_limites_temas_duplicados_e_ids(ids):
    assert not combinacion_valida(ids, TODOS)


def test_excepcion_periodica_traer_y_elegibilidad():
    ids = ["general_periodica", "traer_lentes"]
    assert combinacion_valida(ids, ids)
    assert not combinacion_valida(ids, TODOS)
    assert not combinacion_valida(["miopia_lejos"], ["traer_lentes"])


def test_rangos_y_paridad():
    ids = ["miopia_ajuste", "miopia_lejos", "incluida_sin_costo", "traer_lentes"]
    assert seleccionar_respaldo(ids, 2) == ["miopia_ajuste", "incluida_sin_costo"]
    assert seleccionar_respaldo(ids, 3) == ["miopia_lejos", "incluida_sin_costo"]
    # Ausente cuenta len(B)=1: empate en suma, gana el menor rango A.
    assert seleccionar_respaldo(["miopia_ajuste", "miopia_lejos", "pantallas_muchas"], 2) == ["miopia_ajuste"]
