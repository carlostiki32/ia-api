import pytest

from app.seguimiento.catalogo import HECHOS
from app.seguimiento.combinacion import combinacion_valida, seleccionar_respaldo

TODOS = [h.id for h in HECHOS]


@pytest.mark.parametrize("ids", [
    [],
    ["progresivo_zonas"],
    ["bifocal_zonas"],
    ["hipermetropia_cerca"],
    ["astigmatismo_comodidad"],
    ["ajuste_armazon"],
])
def test_combinaciones_validas(ids):
    assert combinacion_valida(ids, TODOS)


@pytest.mark.parametrize("ids", [
    ["progresivo_zonas", "hipermetropia_cerca"],
    ["bifocal_zonas", "ajuste_armazon"],
    ["progresivo_zonas"] * 2,
    ["inventado"],
    ["miopia_lejos"],  # retirado en v2
])
def test_limites_y_maximo_un_hecho(ids):
    assert not combinacion_valida(ids, TODOS)


def test_elegibilidad_estricta():
    assert combinacion_valida(["progresivo_zonas"], ["progresivo_zonas"])
    assert not combinacion_valida(["progresivo_zonas"], ["bifocal_zonas"])


def test_prioridad_y_paridad():
    # Progresivo gana sobre hipermetropía
    elegibles = ["progresivo_zonas", "hipermetropia_cerca"]
    assert seleccionar_respaldo(elegibles, 0) == ["progresivo_zonas"]
    assert seleccionar_respaldo(elegibles, 1) == ["progresivo_zonas"]

    # Bifocal gana sobre hipermetropía
    elegibles_bi = ["bifocal_zonas", "hipermetropia_cerca"]
    assert seleccionar_respaldo(elegibles_bi, 0) == ["bifocal_zonas"]

    # Vacío devuelve lista vacía
    assert seleccionar_respaldo([], 0) == []
