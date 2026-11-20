import json
import pytest

from app.seguimiento.uso import (
    ETIQUETAS, FUENTES, USO_VERSION, reglas_uso, parsear_uso, build_user_prompt_uso,
)
from tests.seguimiento_helpers import request


def test_constantes():
    assert USO_VERSION == "seguimiento-uso-v1"
    assert "desconocido" in ETIQUETAS
    assert "ocupacion" in FUENTES


@pytest.mark.parametrize("ocupacion,esperado", [
    ("Estudiante", "estudiar"),
    ("estudiante de preparatoria", "estudiar"),
    ("estudiantes", "estudiar"),
    ("Chofer", "manejar"),
    ("conductor de autobús", "manejar"),
    ("taxista de sitio", "manejar"),
    ("operador de transporte escolar", "manejar"),
    ("repartidor en moto", "manejar"),
    ("repartidores", "manejar"),
])
def test_reglas_ocupacion(ocupacion, esperado):
    req = request(ocupacion=ocupacion, tipo_lente=None, rx_lejos=None, uso_pantallas=None)
    assert reglas_uso(req) == esperado


def test_reglas_orden_prevalencia():
    # 1. Ocupación gana sobre observaciones_receta y tipo_lente progresivo
    req1 = request(ocupacion="Estudiante", tipo_lente="progresivo", observaciones_receta="Lentes para manejar")
    assert reglas_uso(req1) == "estudiar"

    # 2. Observaciones receta gana sobre tipo_lente progresivo
    req_obs_cerca = request(ocupacion=None, tipo_lente="progresivo", observaciones_receta="Lentes para lectura")
    assert reglas_uso(req_obs_cerca) == "ver_de_cerca"

    req_obs_pc = request(ocupacion=None, tipo_lente="progresivo", observaciones_receta="Trabajo en computadora")
    assert reglas_uso(req_obs_pc) == "computadora"

    req_obs_man = request(ocupacion=None, tipo_lente="monofocal", observaciones_receta="Maneja de noche")
    assert reglas_uso(req_obs_man) == "manejar"

    # Negación en observaciones_receta (< 3 palabras antes)
    req_neg = request(ocupacion=None, tipo_lente=None, uso_pantallas=None, rx_lejos=None, observaciones_receta="no maneja de noche")
    assert reglas_uso(req_neg) == "desconocido"

    req_neg_prog = request(ocupacion=None, tipo_lente="progresivo", observaciones_receta="no maneja de noche")
    assert reglas_uso(req_neg_prog) == "lejos_y_cerca"

    req_neg_pc = request(ocupacion=None, tipo_lente=None, uso_pantallas=None, rx_lejos=None, observaciones_receta="sin pantallas en su día")
    assert reglas_uso(req_neg_pc) == "desconocido"

    req_neg_leer = request(ocupacion=None, tipo_lente=None, uso_pantallas=None, rx_lejos=None, observaciones_receta="nunca lee de cerca")
    assert reglas_uso(req_neg_leer) == "desconocido"

    # 3. Progresivo/bifocal gana sobre pantallas
    req2 = request(ocupacion=None, tipo_lente="progresivo", uso_pantallas="gt6")
    assert reglas_uso(req2) == "lejos_y_cerca"

    req2_bif = request(ocupacion=None, tipo_lente="bifocal", uso_pantallas="gt6")
    assert reglas_uso(req2_bif) == "lejos_y_cerca"

    # R1: Con ADD > 0 y tipo_lente monofocal o null -> desconocido, nunca lejos_y_cerca
    req2_add = request(ocupacion=None, tipo_lente="monofocal", uso_pantallas="gt6",
                       rx_lejos={"od": {"esfera": -1.0, "cilindro": 0.0, "add": 1.5},
                                 "oi": {"esfera": -1.0, "cilindro": 0.0, "add": 1.5}})
    assert reglas_uso(req2_add) == "desconocido"

    req2_add_null = request(ocupacion=None, tipo_lente=None, uso_pantallas="gt6",
                            rx_lejos={"od": {"esfera": -1.0, "cilindro": 0.0, "add": 1.5},
                                      "oi": {"esfera": -1.0, "cilindro": 0.0, "add": 1.5}})
    assert reglas_uso(req2_add_null) == "desconocido"

    # 4. Pantallas gana sobre miopía
    req3 = request(ocupacion=None, tipo_lente="monofocal", uso_pantallas="gt6",
                   rx_lejos={"od": {"esfera": -2.0, "cilindro": 0.0, "add": None},
                             "oi": {"esfera": -2.0, "cilindro": 0.0, "add": None}})
    assert reglas_uso(req3) == "computadora"

    # 5. Miopía (sin antimetropía)
    req4 = request(ocupacion=None, tipo_lente="monofocal", uso_pantallas="lt2",
                   rx_lejos={"od": {"esfera": -2.0, "cilindro": 0.0, "add": None},
                             "oi": {"esfera": -2.0, "cilindro": 0.0, "add": None}})
    assert reglas_uso(req4) == "ver_de_lejos"

    # 6. Desconocido
    req5 = request(ocupacion=None, tipo_lente=None, uso_pantallas=None, rx_lejos=None)
    assert reglas_uso(req5) == "desconocido"


@pytest.mark.parametrize("etiqueta,fuente,campo_presente,esperado", [
    ("estudiar", "ocupacion", True, "estudiar"),
    ("trabajar", "motivo_consulta", True, "trabajar"),
    ("manejar", "ocupacion", True, "manejar"),
    ("manejar", "observaciones_receta", True, "manejar"),
    ("trabajar", "recomendacion_seguimiento", True, "trabajar"),
    # Rechazadas con fuentes clínicas
    ("estudiar", "impresion_clinica", True, None),
    ("trabajar", "explicacion_paciente", True, None),
    ("manejar", "receta", True, None),
    ("manejar", "ninguna", True, None),
    # Rechazadas si el campo en contexto_uso es None o vacío
    ("estudiar", "ocupacion", False, None),
    ("trabajar", "motivo_consulta", False, None),
    ("manejar", "observaciones_receta", False, None),
    ("trabajar", "recomendacion_seguimiento", False, None),
    # Desconocido siempre válido con cualquier fuente
    ("desconocido", "ninguna", False, "desconocido"),
    ("desconocido", "ocupacion", False, "desconocido"),
    ("desconocido", "impresion_clinica", False, "desconocido"),
    # Ópticas aceptadas con fuentes válidas
    ("ver_de_lejos", "impresion_clinica", True, "ver_de_lejos"),
    ("computadora", "receta", True, "computadora"),
    ("lejos_y_cerca", "motivo_consulta", True, "lejos_y_cerca"),
])
def test_parsear_uso_valido_e_invalido(etiqueta, fuente, campo_presente, esperado):
    ctx = {
        "ocupacion": "Estudiante" if (fuente == "ocupacion" and campo_presente) else None,
        "motivo_consulta": "Para el trabajo" if (fuente == "motivo_consulta" and campo_presente) else None,
        "impresion_clinica": "Miopía" if (fuente == "impresion_clinica" and campo_presente) else None,
        "explicacion_paciente": "Uso diario" if (fuente == "explicacion_paciente" and campo_presente) else None,
        "observaciones_receta": "Para manejar" if (fuente == "observaciones_receta" and campo_presente) else None,
        "recomendacion_seguimiento": "Para su trabajo" if (fuente == "recomendacion_seguimiento" and campo_presente) else None,
    }
    req = request(contexto_uso=ctx)
    raw = json.dumps({"uso_lentes": etiqueta, "fuente": fuente})
    assert parsear_uso(raw, req) == esperado


def test_parsear_uso_r2_progresivo_bifocal():
    # R2: Con tipo_lente progresivo o bifocal, si etapa uso devuelve ver_de_lejos o ver_de_cerca -> se descarta (None)
    req_prog = request(tipo_lente="progresivo")
    assert parsear_uso(json.dumps({"uso_lentes": "ver_de_lejos", "fuente": "impresion_clinica"}), req_prog) is None
    assert parsear_uso(json.dumps({"uso_lentes": "ver_de_cerca", "fuente": "impresion_clinica"}), req_prog) is None
    # Otras etiquetas sí se aceptan
    assert parsear_uso(json.dumps({"uso_lentes": "computadora", "fuente": "impresion_clinica"}), req_prog) == "computadora"

    req_bif = request(tipo_lente="bifocal")
    assert parsear_uso(json.dumps({"uso_lentes": "ver_de_lejos", "fuente": "impresion_clinica"}), req_bif) is None
    assert parsear_uso(json.dumps({"uso_lentes": "ver_de_cerca", "fuente": "impresion_clinica"}), req_bif) is None

    # Con monofocal sí se aceptan ver_de_lejos y ver_de_cerca
    req_mono = request(tipo_lente="monofocal")
    assert parsear_uso(json.dumps({"uso_lentes": "ver_de_lejos", "fuente": "impresion_clinica"}), req_mono) == "ver_de_lejos"
    assert parsear_uso(json.dumps({"uso_lentes": "ver_de_cerca", "fuente": "impresion_clinica"}), req_mono) == "ver_de_cerca"


def test_parsear_uso_malformado():
    req = request()
    assert parsear_uso("no json", req) is None
    assert parsear_uso("[]", req) is None
    assert parsear_uso(json.dumps({"uso_lentes": "invalido", "fuente": "ocupacion"}), req) is None
    assert parsear_uso(json.dumps({"uso_lentes": "estudiar", "fuente": "fuente_falsa"}), req) is None


def test_build_user_prompt_uso_contiene_campos_esperados():
    req = request(ocupacion="Abogado", tipo_lente="bifocal",
                  rx_lejos={"od": {"esfera": 1.0, "cilindro": 0.0, "add": 2.0},
                            "oi": {"esfera": 1.0, "cilindro": 0.0, "add": 2.0}})
    prompt = build_user_prompt_uso(req)
    obj = json.loads(prompt)
    assert obj["contexto_uso"]["ocupacion"] == "Abogado"
    assert obj["tipo_lente"] == "bifocal"
    assert obj["tiene_add"] is True


@pytest.mark.parametrize("pantallas,esperado", [("gt6", "computadora"), ("btw2_6", "desconocido"), ("lt2", "desconocido"), (None, "desconocido")])
def test_reglas_solo_mas_de_seis_horas_es_computadora(pantallas, esperado):
    # Hueco detectado por mutante U3 (auditoría 2026-11-20): solo > 6 h de pantalla da la etiqueta computadora.
    req = request(tipo_lente="monofocal", rx_lejos=None, uso_pantallas=pantallas, contexto_uso={})
    assert reglas_uso(req) == esperado
