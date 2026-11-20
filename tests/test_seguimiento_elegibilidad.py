import pytest

from app.seguimiento.catalogo import HECHOS
from app.seguimiento.elegibilidad import hechos_elegibles
from tests.seguimiento_helpers import request, fixture


def rx(esfera=-2, cilindro=0, add=None):
    return {lado: dict(esfera=esfera, cilindro=cilindro, add=add) for lado in ("od", "oi")}


@pytest.mark.parametrize("id,cambios", [
    ("miopia_ajuste", {}), ("miopia_lejos", {"tipo_lente": "otro"}),
    ("hipermetropia_ajuste", {"rx_lejos": rx(2)}), ("hipermetropia_cerca", {"rx_lejos": rx(2)}),
    ("astigmatismo_detalle", {"rx_lejos": rx(1, -2)}),
    ("astigmatismo_comodidad", {"rx_lejos": rx(1, -2), "usa_armazon": True}),
    ("cerca_adecuado", {"rx_lejos": rx(add=2)}), ("cerca_distancias", {"rx_lejos": rx(add=2)}),
    ("progresivo_zonas", {"rx_lejos": rx(add=2), "tipo_lente": "progresivo"}),
    ("progresivo_ajuste", {"rx_lejos": rx(add=2), "tipo_lente": "progresivo", "usa_armazon": True}),
    ("bifocal_zonas", {"rx_lejos": rx(add=2), "tipo_lente": "bifocal"}),
    ("ajuste_armazon", {"usa_armazon": True, "tipo_lente": "monofocal"}),
    ("pantallas_muchas", {"uso_pantallas": "gt6", "tipo_lente": "otro"}),
    ("pantallas_ratos", {"uso_pantallas": "btw2_6"}), ("vencida_retomar", {"estado_seguimiento": "vencido"}),
    ("incluida_sin_costo", {"costo": "incluida"}), ("con_costo_claro", {"costo": "con_costo"}),
    ("comodidad_general", {"tipo_lente": "otro"}), ("general_periodica", {"tipo_lente": "otro"}),
    ("traer_lentes", {}),
])
def test_tabla_por_hecho(id, cambios):
    req = request(rx_lejos=rx(), tipo_lente=None, uso_pantallas=None, **{})
    req = request(**{**req.model_dump(), **cambios})
    assert id in hechos_elegibles(req)


@pytest.mark.parametrize("n", [1, 2, 3])
def test_elegibles_dorados(n):
    assert hechos_elegibles(request(n)) == fixture(f"g{n}-respuesta-plantilla")["hechos_elegibles"]


@pytest.mark.parametrize("incompleta", [None, {"od": {"esfera": None, "cilindro": 0, "add": 2}, "oi": rx()["oi"]}])
def test_incompletos_sin_grupo_a(incompleta):
    ids = hechos_elegibles(request(rx_lejos=incompleta, tipo_lente="progresivo", usa_armazon=True))
    assert not {h.id for h in HECHOS if h.grupo == "A"} & set(ids)


def test_antimetropia_con_add_y_armazon():
    req = request(rx_lejos={"od": rx(-2, -1, 2)["od"], "oi": rx(3, -1, 2)["oi"]}, tipo_lente="progresivo", usa_armazon=True)
    ids = hechos_elegibles(req)
    assert not any(id.startswith(("miopia_", "hipermetropia_", "astigmatismo_")) for id in ids)
    assert {"cerca_adecuado", "progresivo_ajuste"} <= set(ids)


def test_cilindro_positivo_invariante_y_add_no_positiva():
    assert hechos_elegibles(request(rx_lejos=rx(-3, 1, -1))) == hechos_elegibles(request(rx_lejos=rx(-2, -1)))


@pytest.mark.parametrize("tipo,id", [("monofocal", "ajuste_armazon"), ("bifocal", "ajuste_armazon"), ("progresivo", "progresivo_ajuste")])
def test_armazon_exige_true(tipo, id):
    for valor in (None, False, True):
        ids = hechos_elegibles(request(rx_lejos=rx(-2, -1, 2), tipo_lente=tipo, usa_armazon=valor))
        assert (id in ids) == (valor is True)
        assert ("astigmatismo_comodidad" in ids) == (valor is True)
