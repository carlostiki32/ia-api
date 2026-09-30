"""#54: AV+Rx/tropia como coocurrencia, nunca sospecha etiologica de ambliopia."""
import pytest
from app.correlaciones import contexto as dominio
from tests.test_ajuste_c42 import cases, request

CASOS = cases(54)
EXPECTATIVAS = {n: n not in {"08", "11", "13", "14", "17", "33"} for n in CASOS}


@pytest.mark.parametrize("numero", CASOS)
def test_c54_reproduccion(numero):
    req = request(**CASOS[numero]["entrada"])
    assert dominio._cond_ambliopia_sospecha(req) == EXPECTATIVAS[numero]
    if EXPECTATIVAS[numero]:
        texto = dominio._texto_ambliopia_sospecha(req)
        assert not any(p in texto.lower() for p in ("sospecha de ambliopia", "ausencia de patologia", "causa organica no evidente", "subnormal", "factor ambliogenico"))
        for label, av_cc, av_sc in dominio._ojos_av_para_revision(req):
            assert f"AV con correccion {av_cc} en {label}" in texto
        assert texto.startswith("Hallazgo urgente:") == (numero == "20")
        if numero == "20":
            assert "inmediata en urgencias" in texto
        if numero == "16":
            assert "AV con correccion 20/60 en OD" in texto and "exotropia en OI" in texto
        if numero == "32":
            assert "sin correccion 20/20" in texto and "es mejor" in texto
        if numero in {"18", "19", "21", "22"}:
            assert "Contexto referido:" in texto


def test_c54_20_30_a_tres_anos_es_registro_sin_calificacion_de_deficit():
    req = request(**CASOS["10"]["entrada"])
    texto = dominio._texto_ambliopia_sospecha(req)
    assert "segun la edad" in texto and "3 anos" in texto and "deficit" not in texto


def test_c54_no_suprime_av_por_pseudofaquia_opacidad_o_lesion_leve():
    for numero in ("23", "25", "27", "28", "30", "31"):
        req = request(**CASOS[numero]["entrada"])
        assert dominio._cond_ambliopia_sospecha(req)
        assert "20/60 en OD" in dominio._texto_ambliopia_sospecha(req)


@pytest.mark.parametrize("valor", [None, {}])
def test_c54_componente_desconocido_no_equivale_cero(valor):
    od = {"av_cc": "20/60", "cilindro": -3}
    if valor is None:
        od["esfera"] = None
    req = request(rx_od=od, rx_oi={"esfera": 0, "cilindro": 0})
    assert not dominio._cond_ambliopia_sospecha(req)
