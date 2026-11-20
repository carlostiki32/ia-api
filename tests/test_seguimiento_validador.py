import pytest

from app.seguimiento.catalogo import APERTURAS_POR_ID, CIERRES_POR_ID
from app.seguimiento.servicio import respaldo
from app.seguimiento.validador import validar, validar_estilo, LEXICO
from tests.seguimiento_helpers import request


@pytest.mark.parametrize("apertura", APERTURAS_POR_ID.values())
def test_todas_las_muestras_pasan_estilo(apertura):
    assert validar_estilo(apertura) is None


@pytest.mark.parametrize("termino", LEXICO)
def test_lexico_inicio_de_palabra(termino):
    base = "Hola, :paciente, le saludamos de :clinica. Queremos saber de usted."
    assert validar_estilo(f"{base} {termino}.") == "lexico"


@pytest.mark.parametrize("palabra", ["vista", "visión", "ojo", "ojos", "graduación", "graduaciones"])
def test_palabras_completas(palabra):
    base = "Hola, :paciente, le saludamos de :clinica. Queremos saber de usted."
    assert validar_estilo(f"{base} Su {palabra}.") == "lexico"
    assert validar_estilo(f"{base} X{palabra}x.") is None


@pytest.mark.parametrize("cambio,regla", [
    ({"apertura": ""}, "palabras"),
    ({"apertura_extra": "\n"}, "apertura"),
    ({"apertura_extra": " ¿Cómo está?"}, "apertura"),
    ({"apertura_extra": " :paciente"}, "placeholders"),
    ({"apertura_extra": " :fecha"}, "placeholders"),
    ({"apertura_extra": " http"}, "placeholders"),
    ({"apertura_extra": " {hola}"}, "placeholders"),
    ({"apertura_extra": " <hola>"}, "placeholders"),
    ({"apertura_extra": " *hola*"}, "placeholders"),
    ({"apertura_extra": " www"}, "placeholders"),
    ({"apertura_extra": " 12"}, "cifras"),
    ({"apertura_extra": " Te esperamos."}, "tuteo"),
    ({"apertura_extra": " Su vista."}, "lexico"),
    ({"cierre": "Puede venir cuando le resulte cómodo."}, "cierre"),
    ({"cierre": "¿Cómo le va con sus lentes? ¿Le apartamos un horario?"}, "cierre"),
    ({"cierre_id": "CI_COS_1", "cierre": CIERRES_POR_ID["CI_COS_1"]}, "cierre"),  # En incluida, cierre con costo es invalido
    ({"frase_uso": "Frase de uso inventada que no existe en el catálogo."}, "uso"),
    ({"frase_fecha": "Frase de fecha inventada que no existe en el catálogo."}, "fecha"),
    ({"ids": ["progresivo_zonas", "bifocal_zonas"]}, "hechos"),
    ({"ids": ["inventado"]}, "hechos"),
    ({"mensaje_extra": " texto ajeno"}, "hechos"),
])
def test_una_mutacion_por_regla(cambio, regla):
    req = request(1)
    r = respaldo(req)
    a = cambio.get("apertura", r.partes.apertura) + cambio.get("apertura_extra", "")
    fu = cambio.get("frase_uso", r.partes.frase_uso)
    ff = cambio.get("frase_fecha", r.partes.frase_fecha)
    ids = cambio.get("ids", r.partes.hechos)
    c = cambio.get("cierre", r.partes.cierre)
    c_id = cambio.get("cierre_id", r.partes.cierre_id)
    partes = {
        "apertura": a,
        "frase_uso": fu,
        "frase_fecha": ff,
        "hechos": ids,
        "cierre": c,
        "cierre_id": c_id,
    }
    mensaje = (r.mensaje + cambio["mensaje_extra"]) if "mensaje_extra" in cambio else None
    assert validar(req, partes, r.hechos_elegibles, r.uso_lentes, mensaje=mensaje) == regla
