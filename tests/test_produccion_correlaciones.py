"""Contrapruebas de la auditoria de produccion (2026-09-29) para #1 y #27 D6, con controles positivos.

Cada caso negativo es un texto libre valido del contrato (fondo_de_ojo/motivo_consulta); el aviso no debe
activarse ni generar H01. Los controles positivos impiden "arreglar" esto silenciando la ruta.
"""
import pytest

from tests.test_auditoria_correlaciones import activas, alertas_h01

FONDO = "fondo_periferico_riesgo"
DIPLOPIA = "diplopia_aguda"


# --------------------------------------------------------------------------------- #1
@pytest.mark.parametrize("texto", [
    "Sin evidencia en OD ni en OI de desgarro retiniano periferico.",
    "Sin signos en OD ni OI de desprendimiento de retina.",
    "No se observa desgarro OD ni desgarro OI.",
    "Sin evidencia en OD, ni en OI, de desgarro retiniano.",
    "No hay evidencia en ojo derecho ni en ojo izquierdo de desgarro retiniano.",
    "Sin desgarros ni desprendimiento en OD ni en OI.",
    "Ausencia de desgarro en OD y OI.",
    "OD y OI sin desgarros retinianos.",
    "No se aprecia en OD ni en OI ningun desgarro retiniano.",
])
def test_negacion_bilateral_de_desgarro_no_activa_ni_h01(texto):
    assert FONDO not in activas(fondo=texto)
    assert FONDO not in alertas_h01(fondo=texto)


@pytest.mark.parametrize("texto", [
    "Sin desgarro en OD, desgarro en herradura en OI.",
    "Sin evidencia en OD; desgarro retiniano OI.",
    "Desgarro retiniano OD, sin evidencia en OI.",
    "Sin evidencia en OD ni OI de lesion, pero desgarro retiniano en OI.",
    "Sin desgarro en OD con desgarro en OI.",
    "Sin evidencia en OD de desgarro; en OI se observa desgarro retiniano.",
    "Desgarro retiniano en OD y OI.",
])
def test_desgarro_afirmado_en_un_ojo_sigue_siendo_urgente(texto):
    assert activas(fondo=texto)[FONDO].startswith("Hallazgo urgente:")
    assert FONDO in alertas_h01(fondo=texto)


# ------------------------------------------------------------------------------- #27 D6
@pytest.mark.parametrize("motivo", [
    "La madre del paciente se queja de diplopia desde ayer. El paciente no tiene molestias visuales.",
    "Mi madre comenzo con vision doble desde hoy. Yo no tengo molestias.",
    "La madre del paciente presenta diplopia desde ayer. El paciente no tiene molestias visuales.",
    "Mi madre presenta diplopia desde ayer. El paciente no tiene molestias visuales.",
    "Mi hermano empezo con diplopia hoy.",
    "Mi padre tuvo diplopia y perdio la vision de un ojo ayer.",
    "Su esposa se quejo de vision doble desde anoche.",
    "Diplopia en mi madre desde ayer.",
    "Acompana a su madre que tiene diplopia desde ayer.",
])
def test_sintoma_de_un_familiar_no_es_diplopia_del_paciente(motivo):
    assert DIPLOPIA not in activas(motivo=motivo)
    assert DIPLOPIA not in alertas_h01(motivo=motivo)


@pytest.mark.parametrize("motivo,empeoramiento", [
    ("Diplopia conocida desde 2020, empeoro subitamente hoy.", True),
    ("Diplopia cronica desde 2020, con empeoramiento brusco desde esta manana.", True),
    ("Diplopia cronica de anos de evolucion, con empeoramiento brusco desde esta manana.", True),
    ("Mi madre tiene diplopia. Yo tengo vision doble desde hoy.", False),
    ("Cuido a mi madre y presento diplopia desde ayer.", False),
    ("Mi madre me acompana; tengo diplopia desde hoy.", False),
    ("Diplopia desde ayer.", False),
])
def test_diplopia_propia_reciente_o_empeorada_conserva_la_ruta_urgente(motivo, empeoramiento):
    texto = activas(motivo=motivo)[DIPLOPIA]
    assert texto.startswith("Hallazgo urgente:") and "el mismo dia" in texto
    assert DIPLOPIA in alertas_h01(motivo=motivo)
    # Un antecedente que empeora no se describe como diplopia de inicio nuevo.
    assert ("empeoramiento reciente de diplopia" in texto) is empeoramiento
    assert ("diplopia de inicio reciente" in texto) is not empeoramiento
    # La refraccion registrada no se usa como causa (la inferencia refractiva de #27 sigue retirada).
    assert "no determina la causa" in texto


@pytest.mark.parametrize("motivo", [
    "Diplopia conocida desde 2020, sin cambios.",
    "Diplopia cronica desde 2019, estable; hoy revision de rutina.",
    "Diplopia desde 2020.",
    "Antecedente de diplopia en 2018 ya resuelta.",
])
def test_diplopia_antigua_estable_no_es_urgente(motivo):
    assert DIPLOPIA not in activas(motivo=motivo)
    assert DIPLOPIA not in alertas_h01(motivo=motivo)
