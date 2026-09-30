"""#44 conserva molestias visuales, su contexto y foria por ojo."""
import pytest
from app.correlaciones import binocularidad as dominio
from tests.test_ajuste_c42 import cases, request

CASOS = cases(44)
# Con PPC registrado + molestias de cerca el resumen42 conserva ambos datos.
EXPECTATIVAS = {n: n in {"07", "10", "16"} for n in CASOS}


@pytest.mark.parametrize("numero", CASOS)
def test_c44_reproduccion(numero):
    req = request(**CASOS[numero]["entrada"])
    assert dominio._cond_cover_exoforia_sintomatica(req) == EXPECTATIVAS[numero]
    if EXPECTATIVAS[numero]:
        texto = dominio._texto_cover_exoforia_sintomatica(req)
        assert "exoforia en OD" in texto
        assert "descompensacion" not in texto and "sugestiva" not in texto


@pytest.mark.parametrize("motivo", ["Fatiga muscular", "Cefalea al despertar, lectura comoda",
                                    "Diplopia monocular que persiste al cubrir el otro ojo",
                                    "Antecedente de diplopia resuelta", "Exoforia compensada. Cefalea cervical"])
def test_c44_no_convierte_sintoma_extravisual_o_resuelto(motivo):
    assert not dominio._cond_cover_exoforia_sintomatica(request(cover="OD: Exo y Foria", motivo=motivo))


def test_c44_diplopia_subita_exige_valoracion_hoy():
    req = request(cover="OD: Orto | OI: Exo y Foria", motivo="Diplopía binocular de inicio súbito hoy")
    assert dominio._cond_cover_exoforia_sintomatica(req)
    texto = dominio._texto_cover_exoforia_sintomatica(req)
    assert texto.startswith("Hallazgo urgente:") and "el mismo dia" in texto and "exoforia en OI" in texto


def test_c44_registro_mixto_no_convierte_tropia_en_forias():
    req = request(cover="OD: Exo y Foria | OI: Endo y Tropia", motivo="Fatiga visual")
    texto = dominio._texto_cover_exoforia_sintomatica(req)
    assert "exoforia en OD" in texto and "exoforia en OI" not in texto


@pytest.mark.parametrize("motivo", [
    "Mi madre presenta diplopia subita desde hoy; yo acudo a revision sin molestias.",
    "Descartar diplopia subita en el estudio actual.",
    "Mi padre tiene fatiga visual al leer; yo sin molestias.",
    "Descartar fatiga visual al leer.",
])
def test_c44_sujeto_e_hipotesis_no_son_sintomas_del_paciente(motivo):
    req = request(cover="OD: Exo y Foria", motivo=motivo)
    assert not dominio._cond_cover_exoforia_sintomatica(req)
    assert not dominio._prioridad_visual_aguda(req)


def test_c44_antecedente_resuelto_no_borra_sintoma_actual_tras_contraste():
    req = request(ppc=6, cover="OD: Exo y Foria",
                  motivo="Antecedente de diplopia resuelta, pero hoy fatiga visual al leer.")
    assert dominio._cond_insuficiencia_convergencia(req)
    assert "fatiga visual al leer" in dominio._texto_insuficiencia_convergencia(req)


@pytest.mark.parametrize("motivo", ["Diplopia binocular de nueva aparicion desde ayer.",
                                   "Mi madre tuvo diplopia antigua; yo tengo diplopia nueva desde ayer."])
def test_c44_inicio_ayer_del_paciente_conserva_prioridad(motivo):
    req = request(cover="OD: Exo y Foria", motivo=motivo)
    assert dominio._prioridad_visual_aguda(req)
    assert "el mismo dia" in dominio._texto_cover_exoforia_sintomatica(req)
