from itertools import product
import re
import pytest

from app.patient_profile import word_count
from app.seguimiento.servicio import respaldo
from app.seguimiento.validador import validar
from tests.seguimiento_helpers import request, fixture, sin_variables
from tests.test_seguimiento_elegibilidad import rx


@pytest.mark.parametrize("n", [1, 2, 3])
def test_respaldo_dorado(n):
    actual = respaldo(request(n)).model_dump()
    assert re.fullmatch("[a-f0-9]{64}", actual["generacion"]["base_hash_api"])
    assert sin_variables(actual, plantilla=True) == sin_variables(fixture(f"g{n}-respuesta-plantilla"), plantilla=True)


RX = [None, {"od": dict(esfera=None, cilindro=0, add=None), "oi": rx()["oi"]}, rx(-2), rx(2), rx(1, -2),
      {"od": rx(-2)["od"], "oi": rx(2)["oi"]}, rx(-2, -1, 2), rx(-3, 1)]
PERFILES = list(product(("18_39", "40_59", "60_mas"), ("proximo", "vencido"), ("incluida", "con_costo"),
                        (False, True), (None, "monofocal", "bifocal", "progresivo", "otro"),
                        (None, "lt2", "btw2_6", "gt6"), range(len(RX)), (2, 3), (None, True)))


@pytest.mark.parametrize("perfil", PERFILES)
def test_matriz_respaldo(perfil):
    tramo, estado, costo, notificado, lente, pantallas, rxidx, previas, armazon = perfil
    req = request(tramo_edad=tramo, estado_seguimiento=estado, costo=costo, ya_notificado_en_ciclo=notificado,
                  tipo_lente=lente, uso_pantallas=pantallas, rx_lejos=RX[rxidx], recetas_previas=previas, usa_armazon=armazon)
    r = respaldo(req)
    assert 50 <= word_count(r.mensaje.rsplit("\n\n", 1)[0]) <= 110
    assert validar(req, r.partes.apertura, r.partes.hechos, r.partes.invitacion, r.hechos_elegibles, mensaje=r.mensaje) is None
