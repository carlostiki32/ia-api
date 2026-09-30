"""#48 conserva exotropia y contexto sin asumir intermitencia, respuesta optica ni terapia."""
import pytest
from app.correlaciones import binocularidad as dominio
from tests.test_ajuste_c42 import cases, request
from app.inference import _get_active_emergency_alerts

CASOS = cases(48)
EXPECTATIVAS = {n: n not in {"05", "06", "07", "08"} for n in CASOS}


@pytest.mark.parametrize("numero", CASOS)
def test_c48_reproduccion(numero):
    req = request(**CASOS[numero]["entrada"])
    assert dominio._cond_exotropia_lente(req) == EXPECTATIVAS[numero]
    if EXPECTATIVAS[numero]:
        texto = dominio._texto_exotropia_lente(req)
        assert "correccion optica prescrita" not in texto and "terapia visual" not in texto
        assert texto.startswith("Hallazgo urgente:") == (numero in {"11", "12"})
        assert not dominio._cover_has(req, "exo")
        if numero == "03":
            assert "exotropia en OI" in texto and "exotropia en OD" not in texto
        if numero == "04":
            assert "exotropia en OD" in texto and "exotropia en OI" in texto
        if numero in {"09", "10", "14"}:
            assert "Contexto referido:" in texto


def test_c48_urgencia_neurologica_preexistente_sigue_activa():
    req = request(**CASOS["12"]["entrada"])
    assert _get_active_emergency_alerts(req)


def test_c48_sin_contexto_no_infiere_control_o_intermitencia():
    texto = dominio._texto_exotropia_lente(request(cover="OD: Exo y Tropia"))
    assert "intermitente" not in texto and "buen control" not in texto and "mal control" not in texto
