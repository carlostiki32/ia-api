"""#57 integra AV/edad sin cribado de enfermedades ni causa exclusiva."""
import pytest
from app.correlaciones import contexto as dominio
from tests.test_ajuste_c42 import cases, request

CASOS = cases(57)
EXPECTATIVAS = {n: n not in {"02", "04", "06", "07", "20", "21", "29"} for n in CASOS}


@pytest.mark.parametrize("numero", CASOS)
def test_c57_reproduccion(numero):
    req = request(**CASOS[numero]["entrada"])
    assert dominio._cond_adulto_mayor_screening(req) == EXPECTATIVAS[numero]
    if EXPECTATIVAS[numero]:
        texto = dominio._texto_adulto_mayor_screening(req)
        assert not any(p in texto.lower() for p in ("sin causa identificada", "descarte activo", "glaucoma", "maculopatia asociada a la edad", "catarata"))
        for label, av_cc, av_sc in dominio._ojos_deficit_inexplicado(req):
            assert f"AV con correccion {av_cc} en {label}" in texto
        assert texto.startswith("Hallazgo urgente:") == (numero in {"24", "25"})
        if numero in {"24", "25"}:
            assert "inmediata en urgencias" in texto
        if numero == "09":
            assert "sin correccion 20/20" in texto and "es mejor" in texto
        if numero in {"22", "23", "26"}:
            assert "Contexto referido:" in texto


@pytest.mark.parametrize("av", ["20/30", "20/40"])
def test_c57_frontera_59_60_conserva_mismos_hechos_y_recomendacion(av):
    joven = request(edad=59, rx_od={"av_cc": av, "av_sc": "20/60"})
    mayor = request(edad=60, rx_od={"av_cc": av, "av_sc": "20/60"})
    assert dominio._cond_deficit_visual_inexplicado_refractivo(joven)
    assert dominio._cond_adulto_mayor_screening(mayor)
    texto_59 = dominio._texto_deficit_visual_inexplicado_refractivo(joven).replace("59 anos", "EDAD")
    texto_60 = dominio._texto_adulto_mayor_screening(mayor).replace("60 anos", "EDAD")
    assert texto_59 == texto_60


def test_c57_oi_y_coexistencia_organica_no_borran_av():
    req = request(edad=70, rx_oi={"av_cc": "20/40"}, anexos="Catarata OD", fondo="MER minima OI")
    assert dominio._cond_adulto_mayor_screening(req)
    texto = dominio._texto_adulto_mayor_screening(req)
    assert "20/40 en OI" in texto and "20/40 en OD" not in texto


def test_c57_dedupe_con54_conserva_av_y_tropia_contralateral():
    req = request(**CASOS["21"]["entrada"])
    texto = dominio._texto_ambliopia_sospecha(req)
    assert "20/30 en OD" in texto and "exotropia en OI" in texto
