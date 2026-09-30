"""#47 describe endotropia; lente obligatorio no acredita correccion ni mecanismo."""
import pytest
from app.correlaciones import binocularidad as dominio
from tests.test_ajuste_c42 import cases, request

CASOS = cases(47)
EXPECTATIVAS = {n: n not in {"05", "06", "09", "10"} for n in CASOS}


@pytest.mark.parametrize("numero", CASOS)
def test_c47_reproduccion(numero):
    req = request(**CASOS[numero]["entrada"])
    assert dominio._cond_endotropia_lente(req) == EXPECTATIVAS[numero]
    if EXPECTATIVAS[numero]:
        texto = dominio._texto_endotropia_lente(req)
        assert "correccion optica prescrita" not in texto and "acomodativa" not in texto
        assert texto.startswith("Hallazgo urgente:") == (numero in {"12", "13"})
        if numero == "07":
            assert "endotropia en OI" in texto and "endotropia en OD" not in texto
        if numero == "08":
            assert "endotropia en OD" in texto and "endotropia en OI" in texto
        if numero in {"11", "14"}:
            assert "Contexto referido:" in texto


@pytest.mark.parametrize("lente", ["monofocal", "progresivo", "bifocal_blended", "flat_top"])
def test_c47_tipo_lente_no_establece_respuesta_optica(lente):
    req = request(cover="OD: Endo y Tropia", lente=lente,
                  rx_od={"esfera": None, "cilindro": None})
    texto = dominio._texto_endotropia_lente(req)
    assert "respuesta" not in texto and "prescrita" not in texto
