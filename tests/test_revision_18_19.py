"""Regresiones de la revision independiente de #18 y #19 (2026-09-29), cada una con su control positivo.

Todas las entradas son texto libre valido del contrato. Se comprueba la salida real del motor, sin
depender de goldens.
"""
import pytest

from tests.test_auditoria_correlaciones import activas, alertas_h01

CRISTALINO = "opacidad_cristaliniana"
ANEXOS = "anexos_patologicos"


# ------------------------------------------------------------------------------- #18
def test_detalle_de_otra_estructura_no_se_atribuye_al_cristalino():
    texto = activas(anexos="Catarata OD, capsula posterior transparente")[CRISTALINO]
    assert "cristalino posterior" not in texto and "opacidad del cristalino OD" in texto


def test_detalle_propio_del_hallazgo_se_conserva_y_el_negado_no():
    assert "opacidad del cristalino nuclear leve OD" in activas(anexos="Catarata nuclear OD leve")[CRISTALINO]
    assert "densa" not in activas(anexos="Catarata nuclear OD, densa no")[CRISTALINO]


@pytest.mark.parametrize("anexos", [
    "Opacidad capsular posterior OD",
    "LIO centrado OD con opacidad capsular posterior leve",
    "Opacificacion de la capsula posterior OD",
])
def test_opacidad_capsular_se_reconoce_y_no_es_catarata_del_cristalino(anexos):
    texto = activas(anexos=anexos)[CRISTALINO]
    assert "capsula posterior" in texto or "capsular posterior" in texto
    assert "opacidad del cristalino" not in texto


@pytest.mark.parametrize("motivo", [
    "Cirugia de catarata ayer. Dolor ocular intenso desde hoy.",
    "Operado de catarata hoy. Dolor ocular intenso.",
    "Cirugia de catarata reciente. Dolor ocular intenso desde hoy.",
    "Cirugia de catarata hace 3 dias. Dolor ocular intenso y perdida visual desde hoy.",
])
def test_cirugia_reciente_con_dolor_intenso_es_urgente_el_mismo_dia(motivo):
    texto = activas(motivo=motivo)[CRISTALINO]
    assert texto.startswith("Hallazgo urgente:") and "cirugia de catarata reciente" in texto and "el mismo dia" in texto
    assert CRISTALINO in alertas_h01(motivo=motivo)
    assert "endoftalmitis" not in texto.lower()


@pytest.mark.parametrize("motivo", [
    "Cirugia de catarata hace 3 meses. Dolor ocular intenso desde hoy.",
    "Cirugia de catarata ayer. Sin dolor. Vision buena.",
    "Cirugia de catarata ayer, dolor leve.",
    "Cirugia de catarata OD hace 2 semanas. Dolor ocular intenso OI.",
])
def test_sin_ventana_posoperatoria_o_sin_sintoma_de_alarma_no_hay_urgencia(motivo):
    assert CRISTALINO not in activas(motivo=motivo)


def test_fecha_de_los_sintomas_no_fecha_la_cirugia():
    texto = activas(motivo="Cirugia de catarata OD hace 10 dias, dolor intenso OD desde hoy",
                    anexos="Pseudofaquia OD")[CRISTALINO]
    assert "cirugia de catarata reciente OD," in texto and "de inicio reciente" not in texto


@pytest.mark.parametrize("campo,texto", [
    ("fondo", "Fondo no visible por catarata OI"),
    ("fondo", "Sin vision de fondo por catarata OD"),
    ("fondo", "No se logra observar fondo OD por catarata densa"),
    ("anexos", "No se puede visualizar fondo OD por catarata densa"),
])
def test_la_negacion_de_la_observacion_no_niega_la_catarata_que_la_impide(campo, texto):
    assert CRISTALINO in activas(**{campo: texto})


@pytest.mark.parametrize("campo,texto", [
    ("anexos", "No se observa catarata OD"),
    ("fondo", "No se logra observar fondo por mala colaboracion; sin catarata"),
    ("anexos", "No se observa opacidad del cristalino por biomicroscopia"),
])
def test_la_negacion_de_la_catarata_sigue_valiendo(campo, texto):
    assert CRISTALINO not in activas(**{campo: texto})


def test_lio_se_escribe_en_mayuscula_y_leucocoria_dudosa_no_se_orienta_al_cristalino():
    assert "LIO subluxado OD" in activas(anexos="LIO subluxado OD")[CRISTALINO]
    dudosa = activas(anexos="Posible leucocoria OD", edad=3)[CRISTALINO]
    assert "reflejo rojo" in dudosa and "evaluacion del cristalino" not in dudosa


def test_catarata_congenita_conserva_la_palabra_del_registro():
    texto = activas(anexos="Catarata congenita OD", edad=1)[CRISTALINO]
    assert "descrita como congenita" in texto and "evolucion antigua" not in texto
    assert "pediatrica" in texto


# ------------------------------------------------------------------------------- #19
def test_anatomia_de_otra_estructura_no_se_presta_a_la_dacriocistitis():
    texto = activas(anexos="Dacriocistitis OI con fiebre y edema palpebral")[ANEXOS]
    assert "dacriocistitis palpebral" not in texto and "dacriocistitis OI" in texto


@pytest.mark.parametrize("anexos", [
    "Dacriocistitis OI con fiebre y edema palpebral",
    "Dacriocistitis OI, febril",
])
def test_fiebre_registrada_en_anexos_alcanza_la_ruta_de_dacriocistitis(anexos):
    texto = activas(anexos=anexos)[ANEXOS]
    assert texto.startswith("Hallazgo urgente:") and "fiebre" in texto and "el mismo dia" in texto
    assert "fiebre OI" not in texto                 # sintoma sistemico: no se lateraliza
    assert ANEXOS in alertas_h01(anexos=anexos)


def test_dacriocistitis_sin_fiebre_no_es_urgente():
    assert not activas(anexos="Dacriocistitis cronica OD sin fiebre")[ANEXOS].startswith("Hallazgo urgente")


def test_ulcera_cicatrizada_no_es_una_lesion_activa():
    assert ANEXOS not in activas(anexos="Ulcera corneal OD antigua, cicatrizada")
    assert ANEXOS not in alertas_h01(anexos="Ulcera corneal OD antigua, cicatrizada")
    assert ANEXOS in alertas_h01(anexos="Ulcera corneal OD")


def test_un_solo_signo_no_se_llama_combinacion():
    assert "este hallazgo amerita" in activas(anexos="Ulcera corneal OD")[ANEXOS]
    combinado = activas(anexos="Ulcera corneal OD", motivo="Dolor ocular OD y fotofobia desde hoy")[ANEXOS]
    assert "esta combinacion amerita" in combinado


@pytest.mark.parametrize("anexos,esperado", [
    ("Erosion cutanea palpebral OD", "erosion cutanea palpebral OD"),
    ("Defecto epitelial conjuntival OI", "defecto epitelial conjuntival OI"),
    ("Pterigion nasal OD con crecimiento reciente", "pterigion nasal OD"),
    ("Triquiasis OD con roce corneal", "triquiasis con roce corneal OD"),
    ("Madarosis sobre lesion palpebral ulcerada recurrente OD", "madarosis sobre lesion palpebral ulcerada recurrente OD"),
])
def test_los_calificadores_adyacentes_se_conservan(anexos, esperado):
    assert esperado in activas(anexos=anexos)[ANEXOS]
