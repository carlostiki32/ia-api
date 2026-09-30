"""#53: exposicion y molestias actuales sin diagnostico CVS ni indicacion optica."""
import pytest
from app.correlaciones import contexto as dominio
from tests.test_ajuste_c42 import cases, request

CASOS = cases(53)
EXPECTATIVAS = {n: n not in {"04", "05", "06", "07", "08", "09", "10"} for n in CASOS}


@pytest.mark.parametrize("numero", CASOS)
def test_c53_reproduccion(numero):
    req = request(**CASOS[numero]["entrada"])
    assert dominio._cond_cvs_sospecha(req) == EXPECTATIVAS[numero]
    if EXPECTATIVAS[numero]:
        texto = dominio._texto_cvs_sospecha(req)
        assert not any(p in texto.lower() for p in ("sindrome", "se correlaciona", "sugestiva", "correccion optica", "vision intermedia"))
        assert texto.startswith("Hallazgo urgente:") == (numero in {"11", "12"})
        if numero in {"11", "12"}:
            assert "inmediata en urgencias" in texto
        if numero in {"13", "14", "17"}:
            assert "sin empeoramiento" in texto or "independiente" in texto or "no relacionada" in texto


@pytest.mark.parametrize("motivo", ["Ardor gastrico al usar computadora", "Fatiga muscular al leer",
                                    "Prurito cutaneo durante trabajo en pantalla", "Sin molestias oculares con computadora"])
def test_c53_no_equivale_tarea_a_organo_visual(motivo):
    assert not dominio._cond_cvs_sospecha(request(pantallas="gt6", motivo=motivo))


def test_c53_exposicion_baja_no_equivale_ausencia_sintomas():
    req = request(pantallas="lt2", motivo="Ardor ocular durante computadora")
    assert dominio._cond_cvs_sospecha(req)
    assert "menos de 2 horas" in dominio._texto_cvs_sospecha(req)


def test_c53_negacion_del_trauma_y_sintomas_resueltos_no_genera_urgencia():
    req = request(pantallas="gt6", motivo="Ardor ocular con computadora. Sin traumatismo ni dolor ocular")
    assert "Hallazgo urgente" not in dominio._texto_cvs_sospecha(req)


@pytest.mark.parametrize("motivo", ["Mi madre presenta fatiga visual al leer; yo sin molestias.",
                                   "Descartar fatiga visual al leer.",
                                   "Mi padre tiene dolor ocular, ojo rojo y fotofobia hoy."])
def test_c53_no_atribuye_sintomas_de_terceros_ni_hipotesis(motivo):
    assert not dominio._cond_cvs_sospecha(request(pantallas="gt6", motivo=motivo))


def test_c53_sintoma_actual_tras_antecedente_sigue_presente():
    req = request(pantallas="gt6", motivo="Antecedente de diplopia resuelta, pero hoy fatiga visual al leer.")
    assert dominio._cond_cvs_sospecha(req)
    assert "fatiga visual al leer" in dominio._texto_cvs_sospecha(req)
