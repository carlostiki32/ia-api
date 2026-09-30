"""Aceptacion #14 `motilidad_alterada`: signos por seccion/ocurrencia, certeza, cronologia y prioridad.

Las expectativas de C14-01..29 salen de la tabla de la orden (AUDITORIA_CORRELACIONES.md, #14),
no del comportamiento del codigo. Las regresiones posteriores cubren fallos hallados al certificar.
"""
import json
from pathlib import Path

import pytest

from app.inference import _ensure_emergency_preserved
from tests.test_auditoria_correlaciones import _req, activas, alertas_h01

_CASOS = {c["id"]: c for c in json.loads(
    (Path(__file__).parents[1] / "auditoria/2026-09-21/casos.json").read_text(encoding="utf-8"))
    if c["id"].startswith("C14-")}

_PROHIBIDO = ("vias motoras", "neurooftalmologica", "confirma", "compatible con", "paresia por")
_SIN_SALIDA = ("01", "04", "05", "08", "10", "17", "18", "20", "21", "22", "23")
_URGENTE = "Hallazgo urgente:"
# id -> (fragmentos que debe contener, fragmentos que no debe contener, "urgente"/"" , H01)
ACTIVAS = {
    "02": (("limitacion de abduccion OD",), ("urgente",), False, False),
    "03": (("limitacion de abduccion OD de inicio reciente", "diplopia referida", "el mismo dia"), (), True, True),
    "06": (("nistagmo vertical espontaneo en posicion primaria",), ("urgente",), False, False),
    "07": (("nistagmo vertical adquirido",), ("optocinetic",), False, False),
    "09": (("nistagmo horizontal en mirada extrema", "caracterizarse"), ("urgente", "patologico"), False, False),
    "11": (("nistagmo vertical espontaneo de inicio reciente", "vertigo referido", "inestabilidad referida",
            "el mismo dia"), (), True, True),
    "12": (("limitacion mecanica de elevacion OD", "diplopia referida", "traumatismo referido", "el mismo dia"),
           (), True, True),
    "13": (("dolor con el movimiento ocular OD", "disminucion visual referida", "el mismo dia"),
           ("limitacion", "paresia"), True, True),
    "14": (("movimientos sacadicos lentos en ambos ojos", "de inicio reciente"), ("urgente",), False, False),
    "15": (("seguimiento discontinuo y entrecortado",), ("urgente",), False, False),
    "16": (("hipometria sacadica OD",), ("urgente",), False, False),
    "19": (("limitacion de abduccion OI",), ("OD", "urgente"), False, False),
    "24": (("restriccion de elevacion OD", "traumatismo referido", "nausea referida", "el mismo dia"), (), True, True),
    "25": (("oftalmoplejia de inicio reciente", "diplopia referida", "el mismo dia"), (), True, True),
    "26": (("nistagmo espontaneo OD",), ("urgente", "optocinetic"), False, False),
    "27": (("respuesta optocinetica asimetrica",), ("urgente",), False, False),
    "28": (("nistagmo de inicio reciente", "urgente"), ("fisiologico",), True, True),
    "29": (("hipometria sacadica", "seguimiento sacadico"), ("urgente",), False, False),
}


@pytest.mark.parametrize("numero", sorted(set(_SIN_SALIDA) | set(ACTIVAS)))
def test_c14_caso_auditoria(numero):
    caso = _CASOS[f"C14-{numero}"]
    resultado = activas(**caso["entrada"])
    if numero in _SIN_SALIDA:
        assert "motilidad_alterada" not in resultado
        assert "motilidad_alterada" not in alertas_h01(**caso["entrada"])
        return
    pide, no_pide, urgente, h01 = ACTIVAS[numero]
    texto = resultado["motilidad_alterada"]
    for fragmento in pide:
        assert fragmento in texto, (fragmento, texto)
    for fragmento in no_pide + _PROHIBIDO:
        assert fragmento not in texto, (fragmento, texto)
    assert texto.startswith(_URGENTE) == urgente
    assert ("Hallazgo urgente" in texto) == urgente
    assert ("motilidad_alterada" in alertas_h01(**caso["entrada"])) == h01


def test_c14_las_29_reproducciones_estan_cubiertas():
    assert len(_CASOS) == 29
    assert set(_SIN_SALIDA) | set(ACTIVAS) == {f"{i:02d}" for i in range(1, 30)}


# ---------------------------------------------------------------- pares positivo/negativo por signo
@pytest.mark.parametrize("motilidad", [
    "Versiones: Suaves y completas Ducciones: Libres Sacadicos: Adecuados Seguimiento: Continuo",
    "Sin limitaciones. Sin nistagmo.", "Ducciones: sin restricciones ni limitacion", "Nistagmo (-)", "Nistagmo: no",
    "Sin paralisis ni paresia", "Versiones: No evaluadas Ducciones: No evaluadas",
    "Sacadicos: Precisos Seguimiento: Suave", "Seguimiento: Sin alteraciones",
    "Seguimiento: Nistagmo optocinetico presente y simetrico", "Optocinetico conservado",
    "No hay restriccion ni dolor al movimiento", "Sin dolor al movimiento, sin limitacion",
    "Nistagmo fisiologico de mirada extrema", "Torticolis congenito muscular", "Torticolis",
])
def test_c14_normal_negado_o_no_ocular_no_dispara(motilidad):
    assert "motilidad_alterada" not in activas(motilidad=motilidad)


@pytest.mark.parametrize("motilidad,esperado", [
    ("Limitacion de la supraduccion OI", "limitacion de supraduccion OI"),
    ("Restriccion de elevacion OD", "restriccion de elevacion OD"),
    ("Paresia del VI par OD", "paresia del VI par OD"),
    ("Oftalmoparesia OI", "oftalmoparesia OI"),
    ("Incomitancia", "incomitancia"),
    ("Ducciones: incompletas OD", "limitacion de ducciones OD"),
    ("Version: limitada en supraversion bilateralmente", "limitacion de supraversion en ambos ojos"),
    ("Movimientos oculares limitados en todas las direcciones AO", "limitacion en todas las direcciones de la mirada"),
    ("Nistagmo latente", "nistagmo latente"),
    ("Sacadicos: Lentos", "movimientos sacadicos lentos"),
    ("Movimientos sacadicos: hipometricos OI", "hipometria sacadica OI"),
    ("Sacadicos: Hipermetricos", "hipermetria sacadica"),
    ("Seguimiento: Entrecortado", "seguimiento entrecortado"),
    ("Seguimiento: Sacadico", "seguimiento sacadico"),
    ("Seguimiento: OKN ausente", "respuesta optocinetica ausente"),
    ("Sobreaccion del oblicuo inferior OI", "sobreaccion muscular OI"),
    ("Sincinesia mandibulopalpebral", "sincinesia mandibulopalpebral"),
    ("Posicion compensadora de la cabeza", "posicion compensadora de la cabeza"),
    ("Torticolis ocular derecho", "torticolis"),
])
def test_c14_cada_signo_conserva_su_nombre_y_ojo(motilidad, esperado):
    texto = activas(motilidad=motilidad)["motilidad_alterada"]
    assert esperado in texto and not any(p in texto for p in _PROHIBIDO)


def test_c14_torticolis_no_convierte_el_lado_de_inclinacion_en_ojo():
    assert " OD" not in activas(motilidad="Torticolis ocular derecho")["motilidad_alterada"]


def test_c14_limitacion_no_se_convierte_en_paresia_ni_dolor_en_deficit():
    assert "paresia" not in activas(motilidad="Limitacion de abduccion OD")["motilidad_alterada"]
    texto = activas(motilidad="Versiones: Completas Ducciones: Completas. Dolor con movimiento OD")["motilidad_alterada"]
    assert texto.startswith("El paciente refiere dolor con el movimiento ocular OD")
    assert "limitacion" not in texto and "Hallazgo urgente" not in texto


# ---------------------------------------------------------------- mezcla de secciones y de ojos
def test_c14_un_signo_no_borra_a_otro_de_otra_seccion():
    texto = activas(motilidad="Versiones: Sin limitacion Ducciones: Limitacion de abduccion OI "
                              "Sacadicos: Precisos Seguimiento: Continuo")["motilidad_alterada"]
    assert "limitacion de abduccion OI" in texto
    texto = activas(motilidad="Versiones: Nistagmo vertical espontaneo Ducciones: Completas "
                              "Sacadicos: Precisos Seguimiento: Optocinetico conservado")["motilidad_alterada"]
    assert "nistagmo vertical espontaneo" in texto


def test_c14_normalidad_de_un_ojo_no_cancela_el_signo_del_otro():
    texto = activas(motilidad="OD: normal. OI: limitacion de abduccion")["motilidad_alterada"]
    assert "limitacion de abduccion OI" in texto and "OD" not in texto
    texto = activas(motilidad="OD: limitacion de abduccion; OI: normal")["motilidad_alterada"]
    assert "limitacion de abduccion OD" in texto and "OI" not in texto


def test_c14_dos_signos_se_conservan_juntos_con_concordancia():
    texto = activas(motilidad="Limitacion de la supraduccion OI, restriccion en la infraduccion")["motilidad_alterada"]
    assert "limitacion de supraduccion OI y restriccion de infraduccion" in texto and "ameritan" in texto
    texto = activas(motilidad="Sacadicos: Lentos Seguimiento: Entrecortado")["motilidad_alterada"]
    assert "movimientos sacadicos lentos y seguimiento entrecortado" in texto


def test_c14_okn_conservado_en_otra_clausula_no_cancela_el_nistagmo():
    assert "nistagmo espontaneo OD" in activas(motilidad="Nistagmo espontaneo OD. OKN conservado.")["motilidad_alterada"]
    assert "nistagmo vertical adquirido" in activas(
        motilidad="Nistagmo vertical adquirido, sin nistagmo optocinetico.")["motilidad_alterada"]


def test_c14_no_fisiologico_no_es_normalidad():
    assert "nistagmo" in activas(motilidad="Nistagmo no fisiologico de nueva aparicion")["motilidad_alterada"]


# ---------------------------------------------------------------- antecedentes
@pytest.mark.parametrize("motilidad", [
    "Sindrome de Duane conocido desde la infancia, estable y en seguimiento",
    "Duane conocido OI", "Nistagmo congenito estable, conocido en seguimiento",
    "Limitacion OD antigua estable por cirugia de estrabismo, sin diplopia nueva",
    "Antecedente de paresia del VI par resuelta",
])
def test_c14_diagnostico_conocido_no_es_hallazgo_nuevo(motilidad):
    assert "motilidad_alterada" not in activas(motilidad=motilidad)


def test_c14_antecedente_estable_no_oculta_cambio_nuevo_independiente():
    texto = activas(motilidad="Duane conocido estable OI. Limitacion de abduccion OD nueva",
                    motivo="Diplopia desde ayer")["motilidad_alterada"]
    assert "limitacion de abduccion OD de inicio reciente" in texto and "Duane" not in texto
    assert "motilidad_alterada" not in activas(motilidad="Duane conocido estable OI", motivo="Diplopia desde ayer")


def test_c14_antiguo_sin_estable_se_describe_sin_urgencia():
    texto = activas(motilidad="Nistagmo pendular congenito")["motilidad_alterada"]
    assert "de evolucion antigua descrita" in texto and "Hallazgo urgente" not in texto


# ---------------------------------------------------------------- certeza
@pytest.mark.parametrize("motilidad,frase", [
    ("Posible limitacion de abduccion OD", "hallazgo no concluyente de limitacion de abduccion OD"),
    ("Descartar paresia del VI par", "sospecha por descartar de paresia del VI par"),
    ("Limitacion de la abduccion en OD?", "sospecha por descartar de limitacion de abduccion OD"),
])
def test_c14_hallazgo_incierto_no_se_declara_confirmado(motilidad, frase):
    texto = activas(motilidad=motilidad)["motilidad_alterada"]
    assert frase in texto and "verificar o descartar" in texto and "Hallazgo urgente" not in texto


# ---------------------------------------------------------------- prioridad
@pytest.mark.parametrize("motivo,urgente", [
    ("Diplopia desde hace 2 dias", True),
    ("Vision doble desde ayer", True),
    ("Diplopia desde hace 5 anos", False),
    ("Diplopia", False),
    ("Revision de rutina", False),
    ("Cefalea intensa desde hoy", True),
    ("Dolor ocular OD", True),
    ("Dolor ocular OI intenso", False),           # otro ojo: no se asocia
    ("Disminucion visual OD desde ayer", True),
    ("Golpe en el ojo hace 3 dias", True),
    ("Golpe en el ojo hace 5 anos", False),
])
def test_c14_deficit_motor_con_sintoma_de_alarma(motivo, urgente):
    kw = dict(motilidad="Limitacion de abduccion OD", motivo=motivo)
    texto = activas(**kw)["motilidad_alterada"]
    assert texto.startswith("Hallazgo urgente:") == urgente
    assert ("el mismo dia" in texto) == urgente
    assert ("motilidad_alterada" in alertas_h01(**kw)) == urgente


def test_c14_deficit_nuevo_sin_sintomas_es_urgente_pero_no_el_mismo_dia():
    texto = activas(motilidad="Limitacion de abduccion OD de inicio hoy")["motilidad_alterada"]
    assert texto.startswith("Hallazgo urgente:") and "el mismo dia" not in texto and "urgente para aclarar" in texto


def test_c14_una_limitacion_aislada_o_de_fecha_desconocida_no_es_urgencia():
    kw = dict(motilidad="Limitacion de abduccion OD", motivo="Revision de rutina")
    assert "Hallazgo urgente" not in activas(**kw)["motilidad_alterada"]
    assert not alertas_h01(**kw)
    assert "Verificar inicio" in activas(**kw)["motilidad_alterada"]


@pytest.mark.parametrize("motivo,urgente", [
    ("Mareo desde ayer", True),
    ("Vertigo continuo e inestabilidad para caminar desde hoy", True),
    ("Mareo cronico", False),
    ("Debilidad en brazo izquierdo", True),
    ("Revision de rutina", False),
])
def test_c14_nistagmo_con_sintomas_vestibulares_o_neurologicos(motivo, urgente):
    kw = dict(motilidad="Nistagmo espontaneo", motivo=motivo)
    assert activas(**kw)["motilidad_alterada"].startswith("Hallazgo urgente:") == urgente


def test_c14_nistagmo_en_mirada_extrema_solo_escala_con_sintomas_agudos():
    assert "Hallazgo urgente" not in activas(motilidad="Nistagmo en mirada extrema")["motilidad_alterada"]
    assert "Hallazgo urgente" not in activas(
        motilidad="Nistagmo horizontal en mirada extrema de inicio hoy")["motilidad_alterada"]
    assert activas(motilidad="Nistagmo en mirada extrema", motivo="Vertigo desde hoy"
                   )["motilidad_alterada"].startswith("Hallazgo urgente:")


def test_c14_dolor_con_movimiento_solo_escala_con_deterioro_visual_reciente():
    assert "Hallazgo urgente" not in activas(motilidad="Dolor con movimiento OD")["motilidad_alterada"]
    assert "Hallazgo urgente" not in activas(
        motilidad="Dolor con movimiento OD", motivo="Disminucion visual hace 5 anos")["motilidad_alterada"]
    assert activas(motilidad="Dolor con movimiento OD", motivo="Disminucion visual OD desde ayer"
                   )["motilidad_alterada"].startswith("Hallazgo urgente:")
    # el deterioro del OTRO ojo no se atribuye al ojo doloroso
    assert "Hallazgo urgente" not in activas(
        motilidad="Dolor con movimiento OD", motivo="Disminucion visual OI desde ayer")["motilidad_alterada"]


def test_c14_sacadicos_y_seguimiento_no_generan_urgencia_por_si_solos():
    texto = activas(motilidad="Movimientos sacadicos lentos bilateralmente de inicio reciente")["motilidad_alterada"]
    assert "Hallazgo urgente" not in texto and "en ambos ojos" in texto


def test_c14_sintomas_coordinados_comparten_la_expresion_temporal_final():
    texto = activas(motilidad="Nistagmo vertical espontaneo",
                    motivo="Vertigo continuo e inestabilidad para caminar desde hoy")["motilidad_alterada"]
    assert "vertigo referido" in texto and "inestabilidad referida" in texto
    # una expresion temporal de otra oracion no contagia: el mareo sigue siendo cronico
    assert "Hallazgo urgente" not in activas(
        motilidad="Nistagmo espontaneo", motivo="Mareo cronico. Ojo rojo desde hoy")["motilidad_alterada"]
    # ni una expresion antigua propia se pierde por una reciente vecina de otra oracion
    assert activas(motilidad="Nistagmo espontaneo", motivo="Mareo desde ayer. Ojo rojo cronico"
                   )["motilidad_alterada"].startswith("Hallazgo urgente:")


# ---------------------------------------------------------------- integracion con #12 (sin vetos globales)
def test_c14_no_duplica_la_limitacion_que_ya_describe_12_pero_conserva_el_otro_ojo():
    kw = dict(anexos="Ptosis OD nueva", motivo="Diplopia desde hoy")
    mismo = activas(motilidad="Versiones: Limitacion de abduccion OD", **kw)
    assert "horner_o_tercer_par_sospecha" in mismo and "motilidad_alterada" not in mismo
    otro = activas(motilidad="Versiones: Limitacion de abduccion OI", **kw)
    assert "horner_o_tercer_par_sospecha" in otro and "limitacion de abduccion OI" in otro["motilidad_alterada"]
    # otro tipo de signo en el mismo ojo tampoco se pierde
    ambos = activas(motilidad="Versiones: Limitacion de abduccion OD Sacadicos: Lentos", **kw)
    assert "movimientos sacadicos lentos" in ambos["motilidad_alterada"]


def test_c14_al_deduplicar_12_conserva_que_movimientos_estan_limitados():
    texto = activas(motilidad="Versiones: Limitacion de aduccion, elevacion y depresion OD.",
                    anexos="Ptosis OD de inicio hoy.", motivo="Diplopia y cefalea de inicio subito hoy."
                    )["horner_o_tercer_par_sospecha"]
    assert "limitacion de la motilidad OD" in texto and "(aduccion, elevacion y depresion)" in texto


# ---------------------------------------------------------------- H01
def test_c14_h01_purga_motilidad_normal_y_control_anual_ante_deficit_agudo():
    req = _req(motilidad="Limitacion de abduccion OD de inicio hoy", motivo="Diplopia desde hoy")
    salida = _ensure_emergency_preserved("Motilidad ocular normal. Se recomienda control anual.", req)
    assert "normal" not in salida and "control anual" not in salida.lower()
    assert "limitacion de abduccion OD" in salida and "el mismo dia" in salida


def test_c14_h01_exige_el_plazo_y_no_una_mencion_generica():
    req = _req(motilidad="Limitacion de abduccion OD de inicio hoy", motivo="Diplopia desde hoy")
    salida = _ensure_emergency_preserved("Se observa limitacion de abduccion OD; se sugiere valoracion oftalmologica.", req)
    assert "el mismo dia" in salida


def test_c14_h01_conserva_el_texto_que_ya_cumple():
    req = _req(motilidad="Limitacion de abduccion OD de inicio hoy", motivo="Diplopia desde hoy")
    texto = "Limitacion de abduccion OD de inicio reciente con diplopia; requiere valoracion medica el mismo dia."
    assert _ensure_emergency_preserved(texto, req) == texto


def test_c14_h01_no_purga_una_oracion_correcta_de_otro_ojo():
    req = _req(motilidad="OD: nistagmo espontaneo. OI: limitacion de abduccion", motivo="Vertigo desde hoy")
    texto = "Nistagmo espontaneo OD y limitacion de abduccion OI con vertigo; requiere valoracion el mismo dia."
    assert _ensure_emergency_preserved(texto, req) == texto


def test_c14_h01_no_se_activa_por_hallazgos_sin_urgencia():
    assert not alertas_h01(motilidad="Nistagmo congenito estable, conocido en seguimiento")
    assert not alertas_h01(motilidad="Sacadicos: Hipometricos")
    assert not alertas_h01(motilidad="Dolor con movimiento OD")
