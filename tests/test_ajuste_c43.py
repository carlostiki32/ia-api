"""#43: numero PPC y subtipo/campo por ojo, sin convertirlo en anormalidad."""
import pytest
from app.correlaciones import binocularidad as dominio
from tests.test_ajuste_c42 import cases, request

CASOS = cases(43)
EXPECTATIVAS = {n: n not in {"09", "11", "12", "13"} for n in CASOS}


@pytest.mark.parametrize("numero", CASOS)
def test_c43_reproduccion(numero):
    req = request(**CASOS[numero]["entrada"])
    assert dominio._cond_ppc_exoforia(req) == EXPECTATIVAS[numero]
    if EXPECTATIVAS[numero]:
        texto = dominio._texto_ppc_exoforia(req)
        if req.clinica.ppc_cm is not None:
            assert f"PPC de {req.clinica.ppc_cm} cm" in texto
        assert not any(p in texto.lower() for p in ("alejado", "anormal", "vision proxima", "presbicia"))


def test_c43_tropia_no_se_reinterpreta_como_sin_subtipo():
    req = request(cover="OD: Exo y Tropia | OI: Exo y Foria")
    assert dominio._cover_registros(req) == [("OD", "exotropia"), ("OI", "exoforia")]
    texto = dominio._texto_ppc_exoforia(req)
    assert "exoforia en OI" in texto and "no clasificada" not in texto and "OD" not in texto


def test_c43_suprimir_con42_conserva_ppc_y_ojos():
    req = request(ppc=5, cover="OD: Exo y Foria | OI: Exo y Tropia", motivo="Fatiga al leer")
    assert not dominio._cond_ppc_exoforia(req)
    texto = dominio._texto_insuficiencia_convergencia(req)
    assert "PPC de 5 cm" in texto and "OD" in texto and "OI" in texto


@pytest.mark.parametrize("cover", ["Sin exoforia ni exotropia", "OD: Orto | OI: Orto", None])
def test_c43_no_inventa_desviacion(cover):
    assert not dominio._cond_ppc_exoforia(request(cover=cover))
