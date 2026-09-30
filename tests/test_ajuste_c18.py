"""Aceptacion #18: estados distintos, anatomia, certeza y prioridades reales."""
import json
from pathlib import Path

import pytest

from app.inference import _ensure_emergency_preserved
from tests.test_auditoria_correlaciones import _req, activas, alertas_h01

ID = "opacidad_cristaliniana"
CASOS = {c["id"]: c for c in json.loads(
    (Path(__file__).parents[1] / "auditoria/2026-09-21/casos.json").read_text(encoding="utf-8"))
    if c["id"].startswith("C18-")}
# Expectativas de la tabla de la orden, no de las salidas historicas.
INACTIVAS = {3, 4, 5, 6, 11, 14, 16, 17, 18, 23, 26, 27, 28, 29, 32, 33, 34, 35, 36}
ESPERADAS = {
    1: ("opacidad del cristalino OD",), 2: ("opacidad del cristalino densa OD",),
    7: ("opacidad del cristalino OD",), 8: ("opacidad del cristalino OI",),
    9: ("opacidad del cristalino subcapsular OI",), 10: ("opacidad del cristalino OI",),
    12: ("opacidad del cristalino OI",), 13: ("opacidad del cristalino OI",),
    15: ("plantea, sin establecer", "Verificar el hallazgo"),
    19: ("opacidad del cristalino OI",), 20: ("opacidad de capsula posterior OD",),
    21: ("opacidad de capsula posterior OD",),
    22: ("Hallazgo urgente", "cirugia de catarata reciente", "dolor ocular intenso", "el mismo dia"),
    24: ("opacidad del cristalino central OD", "pediatrica", "desarrollo visual"),
    25: ("Hallazgo urgente", "leucocoria OD", "reflejo rojo ausente", "pediatrica", "el mismo dia"),
    30: ("lente intraocular subluxado OD", "caracterizar la posicion"),
    31: ("Hallazgo urgente", "cristalino subluxado OD", "traumatismo", "el mismo dia"),
}


@pytest.mark.parametrize("numero", range(1, 37))
def test_c18_historico(numero):
    entrada = CASOS[f"C18-{numero:02d}"]["entrada"]
    resultado = activas(**entrada)
    if numero in INACTIVAS:
        assert ID not in resultado
        assert ID not in alertas_h01(**entrada)
        return
    texto = resultado[ID]
    for fragmento in ESPERADAS[numero]:
        assert fragmento in texto
    assert (ID in alertas_h01(**entrada)) == (numero in {22, 25, 31})
    for prohibido in ("estadificacion", "cirugia indicada", "explica la", "retinoblastoma", "endoftalmitis"):
        assert prohibido not in texto
    if numero in {8, 9, 10, 19}:
        assert "OD" not in texto


def test_c18_cobertura_completa():
    assert len(CASOS) == 36
    assert INACTIVAS | set(ESPERADAS) == set(range(1, 37))


@pytest.mark.parametrize("edad,pediatrica", [(2, True), (17, True), (18, False), (65, False), (None, False)])
def test_c18_leucocoria_pediatrica_solo_con_edad_documentada(edad, pediatrica):
    texto = activas(anexos="Leucocoria OD y reflejo rojo ausente", edad=edad)[ID]
    assert ("pediatrica" in texto) == pediatrica
    assert "leucocoria OD y leucocoria" not in texto
    assert "reflejo rojo ausente" in texto


@pytest.mark.parametrize("signo", ["Cristalino luxado OD", "Cristalino ectopico OD",
                                   "Lente intraocular descentrado OD", "LIO luxado OI"])
def test_c18_posicion_no_se_convierte_en_subluxacion(signo):
    texto = activas(anexos=signo)[ID].lower()
    assert signo.lower() in texto
    assert "subluxad" not in texto


@pytest.mark.parametrize("campo", ["anexos", "fondo"])
def test_c18_no_observar_fondo_no_niega_catarata_que_lo_impide(campo):
    assert ID in activas(**{campo: "No se puede visualizar fondo OD por catarata densa"})
    assert ID not in activas(**{campo: "No se logra observar fondo OD por mala colaboracion; sin catarata"})
    assert ID not in activas(**{campo: "No se observa catarata OD"})


@pytest.mark.parametrize("campo", ["anexos", "fondo"])
def test_c18_trauma_reciente_en_campo_clinico_conserva_urgencia(campo):
    entrada = {campo: "Cristalino subluxado OD tras traumatismo de hoy"}
    assert ID in alertas_h01(**entrada)
    texto = _ensure_emergency_preserved("Se recomienda control anual.", _req(**entrada))
    assert "el mismo dia" in texto and "control anual" not in texto


def test_c18_trauma_negado_o_antiguo_no_es_urgente():
    assert ID not in alertas_h01(anexos="Cristalino subluxado OD, sin traumatismo")
    assert ID not in alertas_h01(anexos="Cristalino subluxado OD tras traumatismo hace 10 anos")


def test_c18_leucocoria_h01_conserva_plazo():
    texto = _ensure_emergency_preserved("Se registra leucocoria OD; requiere evaluacion oftalmologica.",
                                      _req(anexos="Leucocoria OD", edad=2))
    assert "el mismo dia" in texto


@pytest.mark.parametrize("historia", ["Sin cirugia de catarata hace tres dias", "Madre operada de catarata hace tres dias",
                                       "Descartar cirugia de catarata hace tres dias"])
def test_c18_cirugia_negada_de_tercero_o_hipotetica_no_se_inventa(historia):
    assert ID not in activas(motivo=historia + ". Dolor ocular intenso y perdida visual desde hoy")


def test_c18_cirugia_ocular_no_se_convierte_en_catarata():
    salida = activas(motivo="Cirugia ocular de estrabismo hace tres dias. Dolor ocular intenso desde hoy")[ID]
    assert "cirugia ocular" in salida and "cirugia de catarata" not in salida


def test_c18_trauma_del_otro_ojo_no_escala_posicion_od():
    assert ID not in alertas_h01(anexos="Cristalino subluxado OD", motivo="Traumatismo OI de hoy, sin dolor ni perdida visual")


def test_c18_catarata_de_historia_quirurgica_y_actual_en_otra_ocurrencia():
    salida = activas(anexos="Pseudofaquia OD tras cirugia de catarata, catarata OI")[ID]
    assert "OI" in salida and "OD" not in salida
    assert salida.count("opacidad del cristalino") == 1


def test_c18_cirugia_od_y_dolor_oi_no_forman_alarma_posoperatoria():
    assert ID not in activas(motivo="Cirugia de catarata OD hace tres dias. Dolor ocular intenso OI desde hoy")
