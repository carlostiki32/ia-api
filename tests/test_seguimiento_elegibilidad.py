import pytest

from app.seguimiento.catalogo import HECHOS
from app.seguimiento.elegibilidad import hechos_elegibles
from tests.seguimiento_helpers import request, fixture


def rx(esfera=-2, cilindro=0, add=None):
    return {lado: dict(esfera=esfera, cilindro=cilindro, add=add) for lado in ("od", "oi")}


@pytest.mark.parametrize("id,uso,cambios", [
    ("hipermetropia_cerca", "desconocido", {"rx_lejos": rx(2)}),
    ("astigmatismo_comodidad", "desconocido", {"rx_lejos": rx(1, -2), "usa_armazon": True}),
    ("progresivo_zonas", "computadora", {"rx_lejos": rx(add=2), "tipo_lente": "progresivo"}),
    ("progresivo_ajuste", "computadora", {"rx_lejos": rx(add=2), "tipo_lente": "progresivo", "usa_armazon": True}),
    ("bifocal_zonas", "computadora", {"rx_lejos": rx(add=2), "tipo_lente": "bifocal"}),
    ("ajuste_armazon", "desconocido", {"usa_armazon": True, "tipo_lente": "monofocal"}),
])
def test_tabla_por_hecho(id, uso, cambios):
    req = request(rx_lejos=rx(), tipo_lente=None, uso_pantallas=None)
    req = request(**{**req.model_dump(), **cambios})
    assert id in hechos_elegibles(req, uso)


@pytest.mark.parametrize("n", [1, 2, 3])
def test_elegibles_dorados(n):
    resp = fixture(f"g{n}-respuesta-plantilla")
    req = request(n)
    assert hechos_elegibles(req, resp["uso_lentes"]) == resp["hechos_elegibles"]


@pytest.mark.parametrize("incompleta", [None, {"od": {"esfera": None, "cilindro": 0, "add": 2}, "oi": rx()["oi"]}])
def test_incompletos_sin_hechos(incompleta):
    ids = hechos_elegibles(request(rx_lejos=incompleta, tipo_lente="progresivo", usa_armazon=True), "desconocido")
    assert not {h.id for h in HECHOS} & set(ids)


def test_antimetropia_con_add_y_armazon():
    req = request(rx_lejos={"od": rx(-2, -1, 2)["od"], "oi": rx(3, -1, 2)["oi"]}, tipo_lente="progresivo", usa_armazon=True)
    ids = hechos_elegibles(req, "desconocido")
    assert not any(id.startswith(("miopia_", "hipermetropia_", "astigmatismo_")) for id in ids)
    assert {"progresivo_zonas", "progresivo_ajuste"} <= set(ids)


def test_r5_hipermetropia_astigmatismo_mixto():
    # R5: hipermetropia_cerca exige hipermetropía sin antimetropía ni astigmatismo mixto
    # Caso 1: Hipermetropía pura bilateral -> hipermetropia_cerca elegible
    req_pura = request(rx_lejos=rx(2, 0), estado_seguimiento="proximo")
    assert "hipermetropia_cerca" in hechos_elegibles(req_pura, "desconocido")

    # Caso 2: OD hipermetropía (+2.0), OI astigmatismo mixto (+1.0, -2.0 -> potencias +1 y -1)
    req_mixto = request(rx_lejos={"od": rx(2, 0)["od"], "oi": rx(1, -2)["oi"]}, estado_seguimiento="proximo")
    ids_mixto = hechos_elegibles(req_mixto, "desconocido")
    assert "hipermetropia_cerca" not in ids_mixto


def test_cilindro_positivo_invariante():
    assert hechos_elegibles(request(rx_lejos=rx(-3, 1, 2), tipo_lente="progresivo"), "desconocido") == \
           hechos_elegibles(request(rx_lejos=rx(-2, -1, 2), tipo_lente="progresivo"), "desconocido")


@pytest.mark.parametrize("tipo,id", [("monofocal", "ajuste_armazon"), ("bifocal", "ajuste_armazon"), ("progresivo", "progresivo_ajuste")])
def test_armazon_exige_true(tipo, id):
    for valor in (None, False, True):
        ids = hechos_elegibles(request(rx_lejos=rx(-2, -1, 2), tipo_lente=tipo, usa_armazon=valor), "desconocido")
        assert (id in ids) == (valor is True)
        assert ("astigmatismo_comodidad" in ids) == (valor is True)


@pytest.mark.parametrize("tipo_lente", ["otro", "progresivo", None])
def test_hechos_exigen_tipo_de_lente(tipo_lente):
    # miopia_lejos y miopia_ajuste fueron retirados en v2 (§F.2). ajuste_armazon exige monofocal o bifocal.
    ids = hechos_elegibles(request(rx_lejos=rx(-2), tipo_lente=tipo_lente, usa_armazon=True), "desconocido")
    assert "ajuste_armazon" not in ids


def test_reglas_etiqueta_uso_en_hechos():
    # progresivo_zonas y bifocal_zonas no elegibles si uso_lentes == "lejos_y_cerca"
    req_prog = request(rx_lejos=rx(add=2), tipo_lente="progresivo")
    assert "progresivo_zonas" not in hechos_elegibles(req_prog, "lejos_y_cerca")
    assert "progresivo_zonas" in hechos_elegibles(req_prog, "computadora")

    req_bif = request(rx_lejos=rx(add=2), tipo_lente="bifocal")
    assert "bifocal_zonas" not in hechos_elegibles(req_bif, "lejos_y_cerca")
    assert "bifocal_zonas" in hechos_elegibles(req_bif, "computadora")

    # hipermetropia_cerca no elegible si lejos_y_cerca, ver_de_cerca o vencido
    req_hip = request(rx_lejos=rx(2), estado_seguimiento="proximo")
    assert "hipermetropia_cerca" not in hechos_elegibles(req_hip, "lejos_y_cerca")
    assert "hipermetropia_cerca" not in hechos_elegibles(req_hip, "ver_de_cerca")
    assert "hipermetropia_cerca" in hechos_elegibles(req_hip, "ver_de_lejos")

    req_hip_venc = request(rx_lejos=rx(2), estado_seguimiento="vencido")
    assert "hipermetropia_cerca" not in hechos_elegibles(req_hip_venc, "ver_de_lejos")
