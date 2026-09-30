"""Aceptacion #15 `campos_visuales_alterados`: mencion por mencion, fiabilidad, cronologia y ruta de sintomas.

Las expectativas de C15-01..36 salen de la tabla de la orden (AUDITORIA_CORRELACIONES.md, #15).
"""
import json
import re
from pathlib import Path

import pytest

from app.inference import _ensure_emergency_preserved
from tests.test_auditoria_correlaciones import _req, activas, alertas_h01

_ID = "campos_visuales_alterados"
_CASOS = {c["id"]: c for c in json.loads(
    (Path(__file__).parents[1] / "auditoria/2026-09-21/casos.json").read_text(encoding="utf-8"))
    if c["id"].startswith("C15-")}
_PROHIBIDO = ("glaucoma", "ictus", "tumor", "compatible con", "revela alteracion")
_SIN_SALIDA = ("01", "09", "10", "12", "14", "15", "16", "17", "18", "19", "20", "23", "24", "32", "36")
_BASAL = "Este hallazgo requiere evaluacion especializada y caracterizacion mediante perimetria formal segun corresponda."
_IMEDIATA = "valoracion medica inmediata en urgencias"
_MISMO_DIA = "valoracion medica el mismo dia"
# id -> (debe contener, no debe contener, plazo: ""|"inmediata"|"mismo dia")
ACTIVAS = {
    "02": (("Se documenta escotoma temporal OD durante la confrontacion", _BASAL), ("Hallazgo urgente",), ""),
    "03": (("Se documenta hemianopsia homonima derecha durante la confrontacion", _BASAL), ("Hallazgo urgente", " OD"), ""),
    "04": (("hemianopsia homonima derecha de inicio reciente", "perdida de la mitad derecha del campo visual"), (), "inmediata"),
    "05": (("cuadrantanopsia superior derecha de inicio reciente", "dificultad del habla referida",
            "dificultad del lenguaje referida"), (), "inmediata"),
    "06": (("defecto altitudinal inferior OD de inicio reciente",), (), "inmediata"),
    "07": (("Se documenta escotoma OD durante la confrontacion",), ("Hallazgo urgente",), ""),
    "08": (("escotoma nasal OI",), ("OD", "Hallazgo urgente"), ""),
    "11": (("resultado no concluyente (defecto del campo temporal)",), ("Se documenta", "Hallazgo urgente"), ""),
    "13": (("falta de respuesta al estimulo visual temporal OD",), ("Hallazgo urgente",), ""),
    "21": (("reduccion del campo superior OD", "atribuido en el registro a ptosis palpebral"),
           ("Hallazgo urgente",), ""),
    "22": (("el paciente refiere perdida de la mitad del campo visual de inicio reciente",
            "Que la confrontacion no muestre defectos no descarta"), ("La confrontacion documenta",), "inmediata"),
    # La mancha central fija del motivo es vision central: la recoge #16, no esta ruta de campo.
    "25": (("escotoma central OD de inicio reciente",), ("mancha", "el paciente refiere"), "mismo dia"),
    "26": (("perdida del campo temporal OD",), ("Hallazgo urgente",), ""),
    "27": (("falta de respuesta al estimulo visual en cuadrante inferior nasal OI",), ("Hallazgo urgente",), ""),
    "28": (("disminucion del campo visual OD",), ("Hallazgo urgente",), ""),
    "29": (("defecto del campo temporal",), ("Hallazgo urgente",), ""),
    "30": (("defecto del campo nasal OI de inicio reciente",), (), "mismo dia"),
    "31": (("resultado no concluyente (reduccion del campo superior)",), ("Se documenta", "Hallazgo urgente"), ""),
    "33": (("hemianopsia homonima derecha de inicio reciente",), ("cefalea", "debilidad"), "inmediata"),
    "34": (("el paciente refiere perdida del campo visual de inicio reciente",), ("hemianopsia",), "mismo dia"),
    "35": (("perdida de la mitad derecha del campo visual de inicio reciente, en episodio transitorio",
            "Que la confrontacion no muestre defectos no descarta"), (), "mismo dia"),
}


@pytest.mark.parametrize("numero", sorted(set(_SIN_SALIDA) | set(ACTIVAS)))
def test_c15_caso_auditoria(numero):
    caso = _CASOS[f"C15-{numero}"]
    resultado = activas(**caso["entrada"])
    if numero in _SIN_SALIDA:
        assert _ID not in resultado
        assert _ID not in alertas_h01(**caso["entrada"])
        return
    pide, no_pide, plazo = ACTIVAS[numero]
    texto = resultado[_ID]
    for fragmento in pide:
        assert fragmento in texto, (fragmento, texto)
    for fragmento in no_pide + _PROHIBIDO:
        assert fragmento not in texto, (fragmento, texto)
    assert not re.search(r"\bconfirma\b", texto)               # «verificar o descartar» si es legitimo
    assert texto.startswith("Hallazgo urgente:") == bool(plazo)
    assert ("Hallazgo urgente" in texto) == bool(plazo)
    if plazo:
        assert (_IMEDIATA if plazo == "inmediata" else _MISMO_DIA) in texto
        assert "sin esperar la perimetria programada" in texto
    assert (_ID in alertas_h01(**caso["entrada"])) == bool(plazo)


def test_c15_las_36_reproducciones_estan_cubiertas():
    assert len(_CASOS) == 36
    assert set(_SIN_SALIDA) | set(ACTIVAS) == {f"{i:02d}" for i in range(1, 37)}


# ---------------------------------------------------------------- lexico: cobertura y acotamiento
@pytest.mark.parametrize("campos,esperado", [
    ("Defecto de campo temporal OD", "defecto del campo temporal OD"),
    ("Constriccion concentrica AO", "reduccion del campo concentrica en ambos ojos"),
    ("Escotoma arqueado superior OI", "escotoma arqueado superior OI"),
    ("Hemianopsia bitemporal", "hemianopsia bitemporal"),
    ("Cuadrantanopsia inferior izquierda", "cuadrantanopsia inferior izquierda"),
    ("Campos alterados OD", "alteracion del campo visual OD"),
    ("Restriccion generalizada", "reduccion del campo generalizada"),
    ("Campo reducido superiormente por armazon", "atribuido en el registro a armazon"),
    ("No responde al estimulo nasal inferior OI, buena colaboracion", "falta de respuesta al estimulo visual nasal inferior OI"),
])
def test_c15_vocabulario_ampliado_conserva_el_hallazgo_exacto(campos, esperado):
    texto = activas(campos=campos)[_ID]
    assert esperado in texto and not any(p in texto for p in _PROHIBIDO)


@pytest.mark.parametrize("campos", [
    "Campos visuales completos", "Campos normales, hemianopsia descartada", "Sin defecto de campo",
    "Defecto de fijacion", "Defecto epitelial corneal", "Defecto pupilar aferente OD",
    "Defecto refractivo corregido, campos conservados", "Restriccion de la movilidad cervical",
    "No responde a las preguntas", "No responde al estimulo visual, no comprende las instrucciones",
    "Escotoma fisiologico correspondiente a la mancha ciega", "Mancha ciega fisiologica",
    "Confrontacion no valorable por restriccion de movilidad cervical",
    "Sin alteracion campimetrica, no responde a preguntas por hipoacusia",
])
def test_c15_no_confunde_defectos_no_campimetricos_ni_pruebas_no_interpretables(campos):
    assert _ID not in activas(campos=campos)


def test_c15_un_ojo_o_zona_normal_no_cancela_el_positivo_del_otro():
    assert "escotoma nasal OI" in activas(campos="OD: Sin escotoma. OI: Escotoma nasal.")[_ID]
    assert "escotoma OD" in activas(campos="Escotoma OD, resto del campo normal.")[_ID]
    assert "defecto del campo temporal" in activas(campos="OD sin defecto OI con defecto temporal.")[_ID]


def test_c15_el_lado_de_un_hemicampo_no_se_lee_como_ojo():
    texto = activas(campos="Hemianopsia homonima derecha de inicio hoy")[_ID]
    assert "hemianopsia homonima derecha" in texto and " OD" not in texto


# ---------------------------------------------------------------- certeza y fiabilidad
@pytest.mark.parametrize("campos,frase", [
    ("Posible defecto temporal, prueba poco confiable", "resultado no concluyente (defecto del campo temporal)"),
    ("Posible hemianopsia, paciente poco colaborador", "resultado no concluyente (hemianopsia)"),
    ("Restriccion superior no reproducible al repetir", "resultado no concluyente (reduccion del campo superior)"),
    ("Descartar hemianopsia", "plantea, sin establecer, hemianopsia"),
    ("Hemianopsia? repetir", "plantea, sin establecer, hemianopsia"),
])
def test_c15_resultado_dudoso_no_se_declara_alteracion(campos, frase):
    texto = activas(campos=campos)[_ID]
    assert frase in texto and "Se documenta" not in texto and "Hallazgo urgente" not in texto
    assert "verificar o descartar" in texto and not alertas_h01(campos=campos)


# ---------------------------------------------------------------- cronologia
def test_c15_defecto_antiguo_estable_no_es_hallazgo_nuevo_pero_el_cambio_nuevo_si():
    assert _ID not in activas(campos="Defecto altitudinal superior OI conocido de hace anos, estable")
    assert _ID not in activas(campos="Escotoma central OI de larga evolucion, conocido")
    texto = activas(campos="Escotoma central OI conocido, empeora")[_ID]
    assert "escotoma central OI con empeoramiento documentado" in texto and "el mismo dia" in texto


@pytest.mark.parametrize("campos,urgente", [
    ("Escotoma OD de inicio hace 2 dias", True),
    ("Escotoma OD", False),
    ("Escotoma OD de inicio hace 3 meses", False),
    ("Hemianopsia bitemporal", False),
    ("Hemianopsia bitemporal de inicio hoy", True),
])
def test_c15_prioridad_segun_inicio_documentado(campos, urgente):
    texto = activas(campos=campos)[_ID]
    assert texto.startswith("Hallazgo urgente:") == urgente
    assert (_ID in alertas_h01(campos=campos)) == urgente
    if not urgente:
        assert "Verificar inicio" in texto or "hace 3 meses" in campos


def test_c15_cronologia_desconocida_no_certifica_estabilidad_ni_urgencia():
    texto = activas(campos="Hemianopsia homonima derecha.")[_ID]
    assert "Verificar inicio y sintomas asociados" in texto and "estable" not in texto


# ---------------------------------------------------------------- ruta independiente por sintomas del motivo
@pytest.mark.parametrize("motivo,plazo", [
    ("Perdida de vision del lado derecho desde ayer", "inmediata"),
    ("Pierde la mitad de la vision del ojo izquierdo desde hace 3 horas", "inmediata"),
    ("Perdida repentina de la mitad derecha de la vision desde hace una hora", "inmediata"),
    ("Hace 3 dias no vi la mitad izquierda un rato, ya paso", "mismo dia"),
    ("Perdi vision en el campo superior OD desde hace 2 dias", "mismo dia"),
])
def test_c15_sintoma_agudo_de_campo_con_examen_normal(motivo, plazo):
    kw = dict(campos="Sin defectos perifericos evidentes.", motivo=motivo)
    texto = activas(**kw)[_ID]
    assert texto.startswith("Hallazgo urgente: el paciente refiere")
    assert (_IMEDIATA if plazo == "inmediata" else _MISMO_DIA) in texto
    assert "La confrontacion documenta" not in texto              # no se inventa un defecto observado
    assert "Que la confrontacion no muestre defectos no descarta el sintoma referido." in texto
    assert _ID in alertas_h01(**kw)


@pytest.mark.parametrize("motivo", [
    "Perdida de campo hace 10 anos", "Niega perdida del campo visual", "Sin perdida de campo, sin destellos",
    "Antecedente de hemianopsia por ictus hace 3 anos", "Refiere que no ve bien de lejos",
    "No veo de un ojo desde ayer", "Moscas volantes y manchas negras que se mueven desde ayer",
    "Perdi mi trabajo en el campo desde ayer", "Pierde el hilo en el campo de la fisica desde hoy",
])
def test_c15_motivo_sin_perdida_de_campo_reciente_no_dispara(motivo):
    kw = dict(campos="Sin defectos perifericos evidentes.", motivo=motivo)
    assert _ID not in activas(**kw) and _ID not in alertas_h01(**kw)


def test_c15_sintoma_sin_fecha_pide_verificar_inicio_sin_urgencia():
    texto = activas(campos="Sin defectos perifericos evidentes.", motivo="Perdida del campo visual")[_ID]
    assert texto.startswith("El paciente refiere perdida del campo visual.")
    assert "Verificar inicio" in texto and "Hallazgo urgente" not in texto


def test_c15_sin_confrontacion_registrada_no_se_afirma_su_normalidad():
    texto = activas(motivo="Perdida de la mitad del campo visual desde hace una hora")[_ID]
    assert "confrontacion sin defectos" not in texto.lower()


def test_c15_la_ausencia_de_sintomas_neurologicos_no_reduce_la_prioridad():
    kw = dict(campos="Hemianopsia homonima derecha de inicio hace una hora", motivo="Sin cefalea, sin debilidad, sin dificultad del habla.")
    assert "valoracion medica inmediata en urgencias" in activas(**kw)[_ID]


def test_c15_sintomas_neurologicos_focales_se_nombran_y_elevan_la_prioridad():
    texto = activas(campos="Escotoma nasal OD nuevo", motivo="Dificultad para hablar desde hoy")[_ID]
    assert "dificultad del habla referida" in texto and "inmediata en urgencias" in texto
    assert "el mismo dia" in activas(campos="Escotoma nasal OD nuevo")[_ID]


def test_c15_escotoma_central_nuevo_no_es_hemicampo():
    texto = activas(campos="OD: escotoma central nuevo. OI: normal")[_ID]
    assert "el mismo dia" in texto and "inmediata" not in texto


def test_c15_defecto_antiguo_y_defecto_nuevo_de_otro_ojo_se_conservan_independientes():
    texto = activas(campos="Defecto temporal OD antiguo. Defecto nasal OI nuevo desde hoy.")[_ID]
    assert "defecto del campo temporal OD de evolucion antigua descrita" in texto
    assert "defecto del campo nasal OI de inicio reciente" in texto and "el mismo dia" in texto


def test_c15_empeoramiento_reciente_de_defecto_conocido_conserva_su_prioridad():
    texto = activas(campos="Hemianopsia antigua estable desde hace 5 anos.",
                    motivo="Desde hoy empeoro la perdida del campo visual.")[_ID]
    assert "hemianopsia" not in texto and "el mismo dia" in texto


# ---------------------------------------------------------------- H01
def test_c15_h01_purga_campos_normales_y_control_anual_ante_perdida_aguda():
    req = _req(campos="Sin defectos perifericos evidentes.", motivo="Perdida de la mitad del campo visual desde hace una hora")
    salida = _ensure_emergency_preserved("Campos visuales normales. Se recomienda control anual.", req)
    assert "normales" not in salida and "control anual" not in salida.lower()
    assert "urgencias" in salida and "inmediat" in salida


def test_c15_h01_exige_el_plazo_inmediato_y_no_una_mencion_generica():
    req = _req(campos="Hemianopsia homonima derecha de inicio hoy")
    salida = _ensure_emergency_preserved("Se observa hemianopsia homonima derecha; se sugiere perimetria.", req)
    assert "inmediata en urgencias" in salida


def test_c15_h01_conserva_el_texto_que_ya_cumple():
    req = _req(campos="Escotoma nasal OD nuevo")
    texto = "Escotoma nasal OD de inicio reciente; requiere valoracion medica el mismo dia."
    assert _ensure_emergency_preserved(texto, req) == texto


def test_c15_h01_no_se_activa_por_hallazgos_sin_inicio_reciente():
    assert not alertas_h01(campos="Hemianopsia homonima derecha.")
    assert not alertas_h01(campos="Escotoma OD", motivo="Perdida del campo visual")
    assert not alertas_h01(campos="Posible defecto temporal, prueba poco confiable")
