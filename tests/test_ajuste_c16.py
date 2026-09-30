"""Aceptacion #16 `amsler_alterado` y reapertura de la integracion A2 de #8.

Las expectativas de C16-01..33 salen de la tabla de la orden (AUDITORIA_CORRELACIONES.md, #16).
"""
import json
import re
from pathlib import Path

import pytest

from app.inference import _ensure_emergency_preserved
from tests.test_auditoria_correlaciones import _req, activas, alertas_h01

_ID = "amsler_alterado"
_DMAE = "fondo_macular_dmae"
_CASOS = {c["id"]: c for c in json.loads(
    (Path(__file__).parents[1] / "auditoria/2026-09-21/casos.json").read_text(encoding="utf-8"))
    if c["id"].startswith("C16-")}
_PROHIBIDO = ("revela alteracion", "sugestiva de", "compatible con", "dmae", "maculopatia", "degeneracion")
_SIN_SALIDA = ("01", "04", "07", "08", "09", "10", "25", "26", "27", "28", "29", "30")
_BASAL = "Este hallazgo amerita evaluacion oftalmologica de la vision central y estudios complementarios segun los hallazgos."
_VERIFICAR = "Verificar inicio y sintomas asociados para decidir la prioridad de atencion."
_URGENTE = "este cambio reciente de la vision central amerita valoracion oftalmologica urgente"
# id -> (debe contener, no debe contener, urgente?)
ACTIVAS = {
    "02": (("En la rejilla de Amsler se refieren lineas onduladas OD.", _BASAL, _VERIFICAR), ("Hallazgo urgente",), False),
    "03": (("metamorfopsia OD de inicio reciente", "lineas torcidas de inicio reciente", _URGENTE), (), True),
    "05": (("escotoma central OI.", _BASAL), (" OD", "Hallazgo urgente"), False),
    "06": (("resultado no concluyente (distorsion)", "Repetir la prueba"), ("se refiere", "Hallazgo urgente", _BASAL), False),
    "11": (("mancha central OD de inicio reciente", _URGENTE), (), True),
    "12": (("zona borrosa central OD.", _BASAL), ("Hallazgo urgente",), False),
    "13": (("cuadrados de distinto tamano OI.", _BASAL), ("Hallazgo urgente",), False),
    "14": (("micropsia OD.", _BASAL), ("Hallazgo urgente",), False),
    "15": (("macropsia OI.", _BASAL), ("Hallazgo urgente",), False),
    "16": (("escotoma central OD.", _BASAL, _VERIFICAR), ("Hallazgo urgente", "reciente"), False),
    "17": (("lineas onduladas OI de inicio reciente", _URGENTE), ("drusas", " OD"), True),
    "18": (("metamorfopsia OD.", _BASAL, _VERIFICAR), ("Hallazgo urgente", "reciente"), False),
    "21": (("metamorfopsia OD de inicio reciente", _URGENTE), (), True),
    "23": (("lineas onduladas OD.", _BASAL, _VERIFICAR), ("Hallazgo urgente", "1 dia habil"), False),
    "24": (("el paciente refiere mancha central OD de inicio reciente", "Que la rejilla de Amsler no muestre alteraciones no descarta"),
           ("En la rejilla de Amsler se refiere",), True),
    "31": (("el paciente refiere escotoma central transitorio de inicio reciente",
            "Que la rejilla de Amsler no muestre alteraciones no descarta"), ("En la rejilla de Amsler se refiere",), True),
    "32": (("zona faltante OD.", _BASAL), ("Hallazgo urgente",), False),
    "33": (("metamorfopsia OI.", _BASAL), (" OD", "ambos ojos", "Hallazgo urgente"), False),
}
# Casos donde A2 de #8 recoge TODA la evidencia y #16 no la repite.
ABSORBIDOS = {
    "19": ("od: metamorfopsia estable", "oi: distorsion nueva desde hoy"),
    "20": ("oi: lineas onduladas de inicio hoy",),
    "22": ("oi: micropsia", "od: veo lineas torcidas desde ayer"),
}


@pytest.mark.parametrize("numero", sorted(set(_SIN_SALIDA) | set(ACTIVAS)))
def test_c16_caso_auditoria(numero):
    caso = _CASOS[f"C16-{numero}"]
    resultado = activas(**caso["entrada"])
    if numero in _SIN_SALIDA:
        assert _ID not in resultado
        assert _ID not in alertas_h01(**caso["entrada"])
        return
    pide, no_pide, urgente = ACTIVAS[numero]
    texto = resultado[_ID]
    for fragmento in pide:
        assert fragmento in texto, (fragmento, texto)
    for fragmento in no_pide:
        assert fragmento not in texto, (fragmento, texto)
    for fragmento in _PROHIBIDO:
        assert fragmento not in texto.lower(), (fragmento, texto)
    assert texto.startswith("Hallazgo urgente:") == urgente
    assert ("Hallazgo urgente" in texto) == urgente
    assert (_ID in alertas_h01(**caso["entrada"])) == urgente


@pytest.mark.parametrize("numero", sorted(ABSORBIDOS))
def test_c16_a2_recoge_la_evidencia_completa_con_ojos_y_tiempos(numero):
    caso = _CASOS[f"C16-{numero}"]
    resultado = activas(**caso["entrada"])
    assert _ID not in resultado                            # sin duplicar
    texto = resultado[_DMAE].lower()
    assert texto.startswith("hallazgo urgente:")
    for evidencia in ABSORBIDOS[numero]:
        assert evidencia in texto, (evidencia, texto)
    assert _DMAE in alertas_h01(**caso["entrada"])


def test_c16_las_33_reproducciones_estan_cubiertas():
    assert len(_CASOS) == 33
    cubiertos = set(_SIN_SALIDA) | set(ACTIVAS) | set(ABSORBIDOS)
    assert cubiertos == {f"{i:02d}" for i in range(1, 34)}


# ---------------------------------------------------------------- A2 / #8
def test_c16_a2_reconoce_inicio_hoy_y_ayer_y_no_convierte_un_sintoma_en_otro():
    texto = activas(amsler="Escotoma central OD de inicio hoy.", fondo="Drusas blandas maculares OD.", edad=72)[_DMAE]
    minusculas = texto.lower()
    assert texto.startswith("Hallazgo urgente:")
    assert "escotoma central" in minusculas and "de inicio hoy" in minusculas
    assert "metamorfopsia" not in minusculas and "distorsion" not in minusculas


def test_c16_a2_no_toma_como_agudo_lo_que_no_declara_inicio_ni_asume_estabilidad():
    resultado = activas(amsler="Metamorfopsia OD, inicio no registrado.", fondo="Drusas blandas maculares OD.", edad=70)
    assert not resultado[_DMAE].startswith("Hallazgo urgente:") and _ID in resultado
    assert "estable" not in resultado[_ID] and "agud" not in resultado[_ID]


def test_c16_sintoma_contralateral_no_se_atribuye_a_las_drusas_del_otro_ojo():
    resultado = activas(amsler="OI: Lineas onduladas de inicio ayer.",
                        fondo="OD: Drusas blandas maculares. OI: Macula sin alteraciones visibles.", edad=72)
    assert not resultado[_DMAE].startswith("Hallazgo urgente:")
    assert resultado[_ID].startswith("Hallazgo urgente:") and "OI" in resultado[_ID]


def test_c16_sintomas_no_confiables_no_activan_a2_ni_se_declaran_alteracion():
    resultado = activas(amsler="Posible distorsion OD de inicio hoy, prueba no confiable.",
                        fondo="Drusas blandas maculares OD.", edad=72)
    assert not resultado[_DMAE].startswith("Hallazgo urgente:")
    assert "resultado no concluyente" in resultado[_ID] and "Hallazgo urgente" not in resultado[_ID]


def test_c16_el_preset_normal_no_veta_un_sintoma_reciente_del_motivo():
    kw = dict(amsler="Sin descendencia de patologia aparente.", motivo="Desde ayer veo torcidas las lineas OD")
    texto = activas(**kw)[_ID]
    assert texto.startswith("Hallazgo urgente: el paciente refiere lineas torcidas OD de inicio reciente")
    assert _ID in alertas_h01(**kw)


def test_c16_sin_rejilla_registrada_no_se_afirma_su_normalidad():
    texto = activas(motivo="Desde ayer veo torcidas las lineas")[_ID]
    assert "rejilla de Amsler sin alteraciones" not in texto


# ---------------------------------------------------------------- vocabulario y negativos
@pytest.mark.parametrize("amsler,esperado", [
    ("Amsler alterado OD", "alteracion referida en la rejilla OD"),
    ("Rejilla alterada OI", "alteracion referida en la rejilla OI"),
    ("Metamorfopsias OD", "metamorfopsia OD"),
    ("Ve las lineas quebradas en OI", "lineas quebradas OI"),
    ("Lineas rectas torcidas OD", "lineas torcidas OD"),
    ("Area faltante OI", "zona faltante OI"),
    ("Mancha fija central OD", "mancha central OD"),
    ("Cuadros de distinto tamano OD", "cuadrados de distinto tamano OD"),
    ("Escotoma OI", "escotoma OI"),
])
def test_c16_vocabulario_conserva_la_percepcion_exacta(amsler, esperado):
    texto = activas(amsler=amsler)[_ID]
    assert esperado in texto and not any(p in texto.lower() for p in _PROHIBIDO)


@pytest.mark.parametrize("amsler", [
    "Prueba alterada por no usar correccion de cerca; no interpretable.",
    "No logra fijar el punto central; prueba no valorable.",
    "Alteracion de comprension de instrucciones; no valorable.",
    "Lineas torcidas por defecto de impresion de la rejilla; repetir prueba.",
    "No evaluado. Descartar metamorfopsia en proxima revision.",
    "Sin metamorfopsia ni escotoma.", "Distorsion descartada tras repetir.", "Lineas rectas sin distorsion.",
    "Metamorfopsia antigua estable por membrana epirretiniana conocida, en seguimiento.",
    "Amsler normal", "Amsler sin alteraciones", "Amsler negativo",
])
def test_c16_no_afirma_alteracion_sin_percepcion_interpretable_actual(amsler):
    assert _ID not in activas(amsler=amsler)


@pytest.mark.parametrize("motivo", [
    "Veo lineas torcidas desde hace 3 anos", "Metamorfopsia por MER conocida, en seguimiento",
    "Sin distorsion ni mancha central", "Niega mancha central", "Vision borrosa de lejos desde ayer",
])
def test_c16_motivo_sin_percepcion_central_reciente_no_dispara(motivo):
    assert _ID not in activas(amsler="Sin descendencia de patologia aparente.", motivo=motivo)


def test_c16_percepcion_de_un_ojo_no_se_transfiere_al_otro():
    texto = activas(amsler="OD normal. OI con escotoma central.")[_ID]
    assert "escotoma central OI" in texto and " OD" not in texto
    texto = activas(amsler="OD: Sin metamorfopsia. OI: Lineas onduladas.")[_ID]
    assert "lineas onduladas OI" in texto and " OD" not in texto


def test_c16_ambos_ojos_solo_cuando_el_registro_lo_dice():
    assert "en ambos ojos" in activas(amsler="Metamorfopsia en ambos ojos")[_ID]
    assert "en ambos ojos" in activas(amsler="Micropsia AO")[_ID]


# ---------------------------------------------------------------- cronologia y episodios
@pytest.mark.parametrize("amsler,urgente", [
    ("Metamorfopsia OD de inicio hoy", True),
    ("Metamorfopsia OD desde hace 3 dias", True),
    ("Metamorfopsia OD nueva", True),
    ("Metamorfopsia OD empeora", True),
    ("Metamorfopsia OD desde hace 3 meses", False),
    ("Metamorfopsia OD", False),
])
def test_c16_prioridad_segun_inicio_documentado(amsler, urgente):
    texto = activas(amsler=amsler)[_ID]
    assert texto.startswith("Hallazgo urgente:") == urgente
    assert (_ID in alertas_h01(amsler=amsler)) == urgente


def test_c16_inicio_desconocido_no_inventa_agudeza_ni_estabilidad():
    texto = activas(amsler="Metamorfopsia OD")[_ID]
    assert _VERIFICAR in texto and "estable" not in texto and "reciente" not in texto


def test_c16_diagnostico_conocido_con_cambio_nuevo_conserva_su_prioridad():
    texto = activas(amsler="Metamorfopsia OD conocida por MER, empeora desde ayer")[_ID]
    assert "metamorfopsia OD con empeoramiento documentado" in texto and texto.startswith("Hallazgo urgente:")


def test_c16_episodio_transitorio_reciente_conserva_tiempo_y_no_se_lee_como_resultado_actual():
    texto = activas(amsler="Escotoma central transitorio ayer, hoy rejilla normal.")[_ID]
    assert "escotoma central transitorio de inicio reciente" in texto
    assert "En la rejilla de Amsler se refiere" not in texto


# ---------------------------------------------------------------- H01
def test_c16_h01_purga_amsler_normal_y_control_anual_ante_cambio_reciente():
    req = _req(amsler="Metamorfopsia OD de inicio hoy")
    salida = _ensure_emergency_preserved("Amsler normal. Se recomienda control anual.", req)
    assert "Amsler normal" not in salida and "control anual" not in salida.lower()
    assert "metamorfopsia OD" in salida and "urgente" in salida


def test_c16_h01_conserva_el_texto_que_ya_cumple():
    req = _req(amsler="Metamorfopsia OD de inicio hoy")
    texto = "Metamorfopsia OD de inicio reciente en la rejilla de Amsler; requiere valoracion oftalmologica urgente."
    assert _ensure_emergency_preserved(texto, req) == texto


def test_c16_h01_no_se_activa_por_hallazgos_sin_inicio_reciente():
    assert not alertas_h01(amsler="Metamorfopsia OD")
    assert not alertas_h01(amsler="Posible distorsion OD de inicio hoy, prueba no confiable")
