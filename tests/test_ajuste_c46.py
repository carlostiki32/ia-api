"""#46 conserva verticales por ojo sin inventar sintomas ni convertir foria en tropia."""
import pytest
from app.correlaciones import binocularidad as dominio
from tests.test_ajuste_c42 import cases, request

CASOS = cases(46)
EXPECTATIVAS = {n: n not in {"12", "13", "14"} for n in CASOS}


@pytest.mark.parametrize("numero", CASOS)
def test_c46_reproduccion(numero):
    req = request(**CASOS[numero]["entrada"])
    assert dominio._cond_desviacion_vertical(req) == EXPECTATIVAS[numero]
    if EXPECTATIVAS[numero]:
        texto = dominio._texto_desviacion_vertical(req)
        assert "puede generar" not in texto and "manifiesta" not in texto
        for ojo, token in dominio._cover_registros(req):
            assert (ojo or "lateralidad no especificada") in texto
        assert texto.startswith("Hallazgo urgente:") == (numero == "15")
        if numero in {"09", "10"}:
            assert "no clasificada" in texto and "OD" in texto and "OI" in texto
        if numero in {"16", "17", "18"}:
            assert "Contexto referido:" in texto


def test_c46_datos_ausentes_no_crean_urgencia():
    texto = dominio._texto_desviacion_vertical(request(cover="OD: Hiper y Foria | OI: Hipo y Tropia"))
    assert "hiperforia en OD" in texto and "hipotropia en OI" in texto
    assert "Hallazgo urgente" not in texto and "diplopia" not in texto


def test_c46_negacion_legacy_no_activa():
    assert not dominio._cond_desviacion_vertical(request(cover="Sin hipertropia ni hiperforia"))


def test_c46_incertidumbre_libre_permanece_por_verificar():
    req = request(cover="OD: posible Hiper y Tropia | OI: Orto")
    assert dominio._cond_desviacion_vertical(req)
    texto = dominio._texto_desviacion_vertical(req)
    assert "posible hipertropia" in texto and "registro por verificar" in texto
    assert "Hallazgo urgente" not in texto


def test_c46_negacion_antes_del_marcador_no_se_pierde():
    assert not dominio._cond_desviacion_vertical(request(cover="No OD: Hiper y Tropia | OI: Orto"))


@pytest.mark.parametrize("motivo", ["Diplopia desde hace 10 anos, hoy revision rutinaria.",
                                   "Descartar diplopia subita en el estudio actual.",
                                   "Mi madre presenta diplopia subita desde hoy; yo sin molestias.",
                                   "Diplopia cronica y cefalea nueva hoy."])
def test_c46_fecha_del_control_o_familiar_no_crea_urgencia(motivo):
    texto = dominio._texto_desviacion_vertical(request(cover="OD: Hiper y Foria | OI: Orto", motivo=motivo))
    assert "Hallazgo urgente" not in texto
