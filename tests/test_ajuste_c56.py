"""#56: comprobar datos AV sin suponer refraccion completa ni clasificacion causal."""
import pytest
from app.correlaciones import contexto as dominio
from tests.test_ajuste_c42 import cases, request

CASOS = cases(56)
EXPECTATIVAS = {n: n not in {"03", "07", "28", "29"} for n in CASOS}


@pytest.mark.parametrize("numero", CASOS)
def test_c56_reproduccion(numero):
    req = request(**CASOS[numero]["entrada"])
    assert dominio._cond_deficit_visual_inexplicado_refractivo(req) == EXPECTATIVAS[numero]
    if EXPECTATIVAS[numero]:
        texto = dominio._texto_deficit_visual_inexplicado_refractivo(req)
        assert not any(p in texto.lower() for p in ("subnormal", "no constar una causa", "factores ambliogenicos", "subclinica", "bajo ciclopejia"))
        for label, av_cc, av_sc in dominio._ojos_deficit_inexplicado(req):
            assert f"AV con correccion {av_cc} en {label}" in texto
        assert texto.startswith("Hallazgo urgente:") == (numero == "24")
        if numero == "10":
            assert "sin correccion 20/20" in texto and "es mejor" in texto
        if numero in {"20", "21", "22", "23"}:
            assert "Contexto referido:" in texto


def test_c56_numero_rx_no_es_requisito_de_av_con_correccion():
    req = request(**CASOS["13"]["entrada"])
    assert dominio._cond_deficit_visual_inexplicado_refractivo(req)


def test_c56_hechos_bilaterales_cubiertos_por54_no_se_pierden():
    for numero in ("28", "29"):
        req = request(**CASOS[numero]["entrada"])
        texto = dominio._texto_ambliopia_sospecha(req)
        assert "20/40 en OD" in texto and "20/80 en OI" in texto
        assert not dominio._ojos_deficit_inexplicado(req)


def test_c56_estenopeico_sin_mejoria_no_descarta_refraccion():
    req = request(edad=35, rx_od={"av_cc": "20/60"}, motivo="Estenopeico sin mejoria documentada")
    texto = dominio._texto_deficit_visual_inexplicado_refractivo(req)
    assert "Contexto referido: Estenopeico sin mejoria" in texto
    assert "descarta" not in texto and "sin beneficio" not in texto


@pytest.mark.parametrize("motivo", ["Niega perdida visual subita hoy", "Antecedente de perdida visual subita ya resuelta"])
def test_c56_perdida_negada_o_resuelta_no_crea_prioridad(motivo):
    texto = dominio._texto_deficit_visual_inexplicado_refractivo(request(rx_od={"av_cc": "20/60"}, motivo=motivo))
    assert "Hallazgo urgente" not in texto


@pytest.mark.parametrize("motivo", [
    "No tengo perdida de vision. Mi padre tuvo perdida visual subita hoy.",
    "Mi madre presenta diplopia subita desde hoy; yo acudo a revision sin molestias.",
    "Descartar perdida visual subita en el estudio actual.",
    "Diplopia desde hace 10 anos, hoy revision rutinaria.",
    "Perdida visual de larga evolucion, hoy revision.",
])
def test_c56_prioridad_respeta_sujeto_certeza_y_cronologia(motivo):
    texto = dominio._texto_deficit_visual_inexplicado_refractivo(request(rx_od={"av_cc": "20/40"}, motivo=motivo))
    assert "Hallazgo urgente" not in texto


def test_c56_perdida_visual_desde_ayer_es_prioritaria():
    req = request(rx_od={"av_cc": "20/40"}, motivo="Perdida visual OD desde ayer.")
    texto = dominio._texto_deficit_visual_inexplicado_refractivo(req)
    assert texto.startswith("Hallazgo urgente:") and "inmediata en urgencias" in texto
