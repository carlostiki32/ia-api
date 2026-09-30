"""Aceptacion #17 `anexos_riesgo_glaucoma_secundario`: signo exacto, campo por campo, certeza y ruta de sintomas.

Las expectativas de C17-01..30 salen de la tabla de la orden (AUDITORIA_CORRELACIONES.md, #17).
"""
import json
from pathlib import Path

import pytest

from app.inference import _ensure_emergency_preserved
from tests.test_auditoria_correlaciones import _req, activas, alertas_h01

_ID = "anexos_riesgo_glaucoma_secundario"
_CASOS = {c["id"]: c for c in json.loads(
    (Path(__file__).parents[1] / "auditoria/2026-09-21/casos.json").read_text(encoding="utf-8"))
    if c["id"].startswith("C17-")}
_PROHIBIDO = ("biomicroscopia del segmento anterior se documentan", "compatibles con", "predisposicion",
              "glaucoma secundario de angulo abierto", "hipertension ocular")
_SIN_SALIDA = ("07", "08", "09", "10", "12", "16", "19", "20", "21", "23", "25", "26", "29")
_EVAL = "que amerita evaluacion oftalmologica del segmento anterior y del riesgo glaucomatoso, incluyendo presion intraocular y gonioscopia segun corresponda."
# id -> (debe contener, no debe contener, urgente?)
ACTIVAS = {
    "01": (("Se registra huso de Krukenberg OD en anexos oculares", _EVAL), ("Hallazgo urgente",), False),
    "02": (("Se registra dispersion pigmentaria en ambos ojos (diagnostico referido en anexos oculares)",), (), False),
    "03": (("Se registra material pseudoexfoliativo OD en anexos oculares",), (), False),
    "04": (("Se registra linea de Sampaolesi en anexos oculares",), (), False),
    "05": (("Se registra pseudoexfoliacion OD (diagnostico referido en anexos oculares)",), (), False),
    "06": (("Se registra pseudoexfoliacion OI (diagnostico referido en anexos oculares)",), (), False),
    "11": (("El registro plantea, sin establecer, huso de Krukenberg en anexos oculares", "Verificar el hallazgo"),
           ("Se registra", "Hallazgo urgente"), False),
    "13": (("Se registra material pseudoexfoliativo OI en anexos oculares",), ("OD", "Hallazgo urgente"), False),
    "14": (("Se registra huso de Krukenberg OD en fondo de ojo",), ("anexos oculares",), False),
    "15": (("Se registra huso de Krukenberg OD en fondo de ojo",), ("anexos oculares", "biomicroscopia"), False),
    "17": (("pigmento en endotelio corneal con defectos de transiluminacion iridiana en anexos oculares",),
           ("sindrome", "dispersion pigmentaria"), False),
    "18": (("Se registran depositos blanquecinos en capsula anterior y margen pupilar en anexos oculares",),
           ("pseudoexfoliacion",), False),
    "22": (("Hallazgo urgente: se registra huso de Krukenberg en anexos oculares, con dolor ocular intenso, halos y nausea",
            "valoracion oftalmologica el mismo dia", "sin esperar el control periodico"),
           ("crisis", "cierre angular", "diagnostico"), True),
    "24": (("Se registra huso de Krukenberg OD en anexos oculares",), ("PXF", "pseudoexfoliacion"), False),
    "27": (("Se registra huso de Krukenberg OD en fondo de ojo",), (), False),
    "28": (("Se registra huso de Krukenberg OD en fondo de ojo",), (), False),
    # «riesgo glaucomatoso» es la evaluacion pedida; no se afirma glaucoma ni hipertension ocular.
    "30": (("Se registra huso de Krukenberg OD en anexos oculares", _EVAL), ("hipertension", "glaucoma "), False),
}


@pytest.mark.parametrize("numero", sorted(set(_SIN_SALIDA) | set(ACTIVAS)))
def test_c17_caso_auditoria(numero):
    caso = _CASOS[f"C17-{numero}"]
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
    assert (_ID in alertas_h01(**caso["entrada"])) == urgente


def test_c17_las_30_reproducciones_estan_cubiertas():
    assert len(_CASOS) == 30
    assert set(_SIN_SALIDA) | set(ACTIVAS) == {f"{i:02d}" for i in range(1, 31)}


# ---------------------------------------------------------------- limites entre campos
@pytest.mark.parametrize("anexos,fondo", [
    ("Sin pseudoexfoliacion", "Huso de Krukenberg OD"),
    ("Sin pseudoexfoliacion.", "Huso de Krukenberg OD."),
    ("Sin pseudoexfoliacion", "OD: Huso de Krukenberg"),
    ("No se observa dispersion pigmentaria", "Krukenberg OI"),
])
def test_c17_la_negacion_de_anexos_no_alcanza_al_fondo_ni_al_reves(anexos, fondo):
    assert _ID in activas(anexos=anexos, fondo=fondo)
    assert _ID in activas(anexos=fondo, fondo=anexos)


def test_c17_dos_campos_dos_signos_se_conservan_con_su_procedencia():
    texto = activas(anexos="Linea de Sampaolesi OD.", fondo="Huso de Krukenberg OI.")[_ID]
    assert "linea de Sampaolesi OD en anexos oculares" in texto and "huso de Krukenberg OI en fondo de ojo" in texto
    assert texto.startswith("Se registran ")


# ---------------------------------------------------------------- contexto anatomico
@pytest.mark.parametrize("texto", [
    "Dispersion pigmentaria retiniana periferica", "Dispersion pigmentaria macular", "Dispersion pigmentaria en papila",
    "Apex corneal normal", "Cornea sin alteraciones", "Pigmento", "Depositos blanquecinos",
    "Pigmento en endotelio", "Depositos blanquecinos en capsula anterior",
])
def test_c17_no_infiere_sindrome_de_pigmento_o_depositos_sin_anatomia_completa(texto):
    assert _ID not in activas(fondo=texto)
    assert _ID not in activas(anexos=texto)


def test_c17_la_combinacion_descriptiva_exige_toda_su_anatomia_y_no_nombra_el_sindrome():
    texto = activas(anexos="Pigmento en endotelio corneal OD con defectos de transiluminacion iridiana")[_ID]
    assert "pigmento en endotelio corneal con defectos de transiluminacion iridiana OD" in texto or \
        "pigmento en endotelio corneal con defectos de transiluminacion iridiana" in texto
    assert "Krukenberg" not in texto and "dispersion pigmentaria" not in texto


# ---------------------------------------------------------------- certeza y antecedentes
@pytest.mark.parametrize("anexos", [
    "Descartar pseudoexfoliacion en proxima revision.", "Pseudoexfoliacion conocida, estable bajo control oftalmologico.",
    "Huso de Krukenberg resuelto tras episodio inflamatorio previo, sin pigmento actual.",
    "Antecedente familiar de pseudoexfoliacion, examen propio normal.", "Sindrome de dispersion pigmentaria conocido, en seguimiento",
    "PEX negativo.", "Lineas de Sampaolesi ausentes.",
])
def test_c17_plan_resuelto_conocido_o_familiar_no_es_un_hallazgo_nuevo(anexos):
    assert _ID not in activas(anexos=anexos)


def test_c17_un_cambio_nuevo_devuelve_el_diagnostico_conocido_a_hallazgo_actual():
    assert _ID in activas(anexos="Pseudoexfoliacion conocida, con material nuevo en borde pupilar OD")


@pytest.mark.parametrize("anexos", ["Posible huso de Krukenberg, no concluyente.", "Sospecha de pseudoexfoliacion OD",
                                    "Krukenberg?"])
def test_c17_signo_incierto_no_se_declara_confirmado(anexos):
    texto = activas(anexos=anexos)[_ID]
    assert texto.startswith("El registro plantea, sin establecer,") and "Se registra" not in texto
    assert not alertas_h01(anexos=anexos)


# ---------------------------------------------------------------- ruta de sintomas agudos
@pytest.mark.parametrize("motivo,urgente", [
    ("Dolor ocular intenso, halos y nausea desde hoy.", True),
    ("Dolor ocular y halos desde ayer", True),
    ("Dolor ocular intenso con vision borrosa desde hoy", True),
    ("Halos aislados desde hoy", False),
    ("Dolor ocular cronico desde hace 5 anos con halos", False),
    ("Sin dolor, sin halos", False),
    ("Dolor ocular intenso y halos y nausea, niega", False),
    ("Revision de rutina", False),
])
def test_c17_signo_con_sintomas_agudos_no_se_reduce_a_control_periodico(motivo, urgente):
    kw = dict(anexos="Huso de Krukenberg OD", motivo=motivo)
    texto = activas(**kw)[_ID]
    assert texto.startswith("Hallazgo urgente:") == urgente
    assert (_ID in alertas_h01(**kw)) == urgente
    assert "control periodico" not in texto or urgente


def test_c17_los_sintomas_agudos_sin_signo_no_activan_esta_regla():
    assert _ID not in activas(anexos="Cornea transparente", motivo="Dolor ocular intenso, halos y nausea desde hoy")


# ---------------------------------------------------------------- H01
def test_c17_h01_exige_el_plazo_y_no_acepta_control_periodico():
    req = _req(anexos="Huso de Krukenberg", motivo="Dolor ocular intenso, halos y nausea desde hoy")
    salida = _ensure_emergency_preserved("Se observa huso de Krukenberg; se recomienda control anual.", req)
    assert "control anual" not in salida.lower() and "el mismo dia" in salida


def test_c17_h01_conserva_el_texto_que_ya_cumple():
    req = _req(anexos="Huso de Krukenberg OD", motivo="Dolor ocular intenso y halos desde hoy")
    texto = "Huso de Krukenberg OD con dolor ocular intenso y halos; requiere valoracion oftalmologica el mismo dia."
    assert _ensure_emergency_preserved(texto, req) == texto


def test_c17_h01_no_se_activa_por_el_signo_solo():
    assert not alertas_h01(anexos="Huso de Krukenberg OD")
