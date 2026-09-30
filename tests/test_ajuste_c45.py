"""#45 no confunde Endo con foria y no borra registros contralaterales."""
import pytest
from app.correlaciones import binocularidad as dominio
from tests.test_ajuste_c42 import cases, request

CASOS = cases(45)
EXPECTATIVAS = {n: n in {"01", "08", "10", "11", "12", "13", "14", "16", "18"} for n in CASOS}


@pytest.mark.parametrize("numero", CASOS)
def test_c45_reproduccion(numero):
    req = request(**CASOS[numero]["entrada"])
    assert dominio._cond_cover_endoforia_sintomatica(req) == EXPECTATIVAS[numero]
    if EXPECTATIVAS[numero]:
        texto = dominio._texto_cover_endoforia_sintomatica(req)
        assert not any(p in texto for p in ("exceso de convergencia", "sugestiva de disfuncion", "terapia"))
        if numero in {"10", "11"}:
            assert "OD" in texto and "endotropia en OI" in texto
        if numero == "08":
            assert "endodesviacion no clasificada en OD" in texto and "endoforia" not in texto
        assert texto.startswith("Hallazgo urgente:") == (numero == "16")


def test_c45_no_asume_distancia_ni_ac_a():
    texto = dominio._texto_cover_endoforia_sintomatica(request(cover="OD: Orto | OI: Endo y Foria", motivo="Fatiga visual"))
    assert "endoforia en OI" in texto and "cerca" not in texto and "AC/A" not in texto


@pytest.mark.parametrize("motivo", ["Diplopia monocular", "Cefalea cervical", "Antecedente de fatiga visual resuelta"])
def test_c45_sintomas_que_no_sustentan_relacion_binocular(motivo):
    assert not dominio._cond_cover_endoforia_sintomatica(request(cover="OD: Endo y Foria", motivo=motivo))
