"""Matriz de respaldo con cobertura t=3 (185 perfiles) por defecto.
Para ejecutar la suite exhaustiva completa, definir IAAPI_EXHAUSTIVO=1.
"""
from itertools import product
import json
import os
from pathlib import Path
import re
import pytest

from app.patient_profile import word_count
from app.seguimiento.catalogo import FRASES_FECHA
from app.seguimiento.fechas import formatear_fecha
from app.seguimiento.prompts import build_user_prompt_redaccion
from app.seguimiento.servicio import respaldo
from app.seguimiento.validador import validar
from tests.seguimiento_helpers import request, fixture, sin_variables
from tests.test_seguimiento_elegibilidad import rx


@pytest.mark.parametrize("n", [1, 2, 3])
def test_respaldo_dorado(n):
    actual = respaldo(request(n)).model_dump()
    assert re.fullmatch("[a-f0-9]{64}", actual["generacion"]["base_hash_api"])
    assert sin_variables(actual, plantilla=True) == sin_variables(fixture(f"g{n}-respuesta-plantilla"), plantilla=True)


RX = [None, {"od": dict(esfera=None, cilindro=0, add=None), "oi": rx()["oi"]}, rx(-2), rx(2), rx(1, -2),
      {"od": rx(-2)["od"], "oi": rx(2)["oi"]}, rx(-2, -1, 2), rx(-3, 1)]

PERFILES_EXHAUSTIVOS = []
for p in product(
    ("18_39", "40_59", "60_mas"),
    ("proximo", "vencido"),
    ("incluida", "con_costo"),
    (False, True),
    (None, "monofocal", "bifocal", "progresivo", "otro"),
    (None, "lt2", "btw2_6", "gt6"),
    range(len(RX)),
    (0, 3),
    (None, True),
    (None, "estudiante", "chofer"),
    (None, 12, 30),
    (None, "Lentes para lectura"),
):
    tramo, estado, costo, notificado, lente, pantallas, rxidx, previas, armazon, ocupacion, fecha_meses, obs = p
    if estado == "vencido":
        fecha_meses = None
    PERFILES_EXHAUSTIVOS.append((tramo, estado, costo, notificado, lente, pantallas, rxidx, previas, armazon, ocupacion, fecha_meses, obs))

PERFILES_EXHAUSTIVOS = list(dict.fromkeys(PERFILES_EXHAUSTIVOS))

_FIXTURE_T3 = Path(__file__).parent / "fixtures" / "seguimiento_whatsapp" / "perfiles_t3.json"
PERFILES_T3 = [tuple(p) for p in json.loads(_FIXTURE_T3.read_text(encoding="utf-8"))["perfiles"]]

PERFILES = PERFILES_EXHAUSTIVOS if os.environ.get("IAAPI_EXHAUSTIVO") == "1" else PERFILES_T3


def test_perfiles_t3_son_subconjunto_del_exhaustivo():
    assert len(PERFILES_T3) == 186
    assert len(set(PERFILES_T3)) == 186
    set_ex = set(PERFILES_EXHAUSTIVOS)
    assert all(p in set_ex for p in PERFILES_T3)


@pytest.mark.parametrize("perfil", PERFILES)
def test_matriz_respaldo(perfil):
    tramo, estado, costo, notificado, lente, pantallas, rxidx, previas, armazon, ocupacion, fecha_meses, obs = perfil
    req = request(tramo_edad=tramo, estado_seguimiento=estado, costo=costo, ya_notificado_en_ciclo=notificado,
                  tipo_lente=lente, uso_pantallas=pantallas, rx_lejos=RX[rxidx], recetas_previas=previas,
                  usa_armazon=armazon, ocupacion=ocupacion, fecha_meses=fecha_meses, observaciones_receta=obs)
    r = respaldo(req)
    cuerpo = r.mensaje.rsplit("\n\n", 1)[0]
    assert 60 <= word_count(cuerpo) <= 140
    assert validar(req, r.partes, r.hechos_elegibles, r.uso_lentes, mensaje=r.mensaje) is None


@pytest.mark.parametrize("cambios,esperado_grupo", [
    pytest.param({"ya_notificado_en_ciclo": True, "estado_seguimiento": "vencido", "recetas_previas": 3}, "AP_SEG", id="notificado_prevalece_sobre_vencido"),
    pytest.param({"ya_notificado_en_ciclo": True, "estado_seguimiento": "proximo", "recetas_previas": 0}, "AP_SEG", id="notificado_prevalece_sobre_proximo"),
    pytest.param({"ya_notificado_en_ciclo": False, "estado_seguimiento": "vencido", "recetas_previas": 2}, "AP_VENC", id="vencido_con_recetas"),
    pytest.param({"ya_notificado_en_ciclo": False, "estado_seguimiento": "vencido", "recetas_previas": 0}, "AP_VENC", id="vencido_sin_recetas"),
    pytest.param({"ya_notificado_en_ciclo": False, "estado_seguimiento": "proximo", "recetas_previas": 1}, "AP_PROX_CONT", id="proximo_con_receta_previa"),
    pytest.param({"ya_notificado_en_ciclo": False, "estado_seguimiento": "proximo", "recetas_previas": 3}, "AP_PROX_CONT", id="proximo_con_varias_recetas"),
    pytest.param({"ya_notificado_en_ciclo": False, "estado_seguimiento": "proximo", "recetas_previas": 0}, "AP_PROX_PRIM", id="proximo_sin_recetas_previas"),
])
def test_apertura_del_respaldo_por_prioridad(cambios, esperado_grupo):
    r = respaldo(request(1, **cambios))
    assert r.partes.apertura_id.startswith(esperado_grupo + "_")


def test_fechas_respaldo():
    # próximo en primer aviso con 12 meses -> FF_P con "un año"
    req_p = request(1, estado_seguimiento="proximo", ya_notificado_en_ciclo=False, fecha_revision="2026-12-15", meses_periodo=12)
    r_p = respaldo(req_p)
    assert r_p.partes.frase_fecha is not None
    assert "un año" in r_p.partes.frase_fecha
    assert "15 de diciembre" in r_p.partes.frase_fecha

    # segundo aviso -> FF_N
    req_seg = request(1, estado_seguimiento="proximo", ya_notificado_en_ciclo=True, fecha_revision="2026-12-15", meses_periodo=12)
    r_seg = respaldo(req_seg)
    ff_n_textos = [t for _, t in FRASES_FECHA["N"]]
    assert r_seg.partes.frase_fecha in ff_n_textos

    # vencido -> FF_N
    req_v = request(1, estado_seguimiento="vencido", ya_notificado_en_ciclo=False)
    r_v = respaldo(req_v)
    assert r_v.partes.frase_fecha in ff_n_textos

    # periodo de 30 meses -> FF_PS
    req_ps = request(1, estado_seguimiento="proximo", ya_notificado_en_ciclo=False, fecha_revision="2026-12-15", meses_periodo=30)
    r_ps = respaldo(req_ps)
    ff_ps_textos = [t.format(fecha=formatear_fecha(req_ps.fecha_revision)) for _, t in FRASES_FECHA["PS"]]
    assert r_ps.partes.frase_fecha in ff_ps_textos
    assert "meses" not in r_ps.partes.frase_fecha and "año" not in r_ps.partes.frase_fecha

    # R7: meses_periodo = null con próximo en primer aviso con fecha -> FF_PS
    req_null = request(1, estado_seguimiento="proximo", ya_notificado_en_ciclo=False, fecha_revision="2026-12-15", meses_periodo=None)
    r_null = respaldo(req_null)
    assert r_null.partes.frase_fecha in ff_ps_textos


def test_variedad_respaldo():
    aperturas = {}
    cierres = {}
    grupos_ap = {}
    grupos_ci = {}
    for perfil in PERFILES_T3:
        tramo, estado, costo, notificado, lente, pantallas, rxidx, previas, armazon, ocupacion, fecha_meses, obs = perfil
        req = request(tramo_edad=tramo, estado_seguimiento=estado, costo=costo, ya_notificado_en_ciclo=notificado,
                      tipo_lente=lente, uso_pantallas=pantallas, rx_lejos=RX[rxidx], recetas_previas=previas,
                      usa_armazon=armazon, ocupacion=ocupacion, fecha_meses=fecha_meses, observaciones_receta=obs)
        r = respaldo(req)
        ap_id = r.partes.apertura_id
        ci_id = r.partes.cierre_id
        aperturas[ap_id] = aperturas.get(ap_id, 0) + 1
        cierres[ci_id] = cierres.get(ci_id, 0) + 1

        g_ap = ap_id.rsplit("_", 1)[0]
        grupos_ap.setdefault(g_ap, {})[ap_id] = grupos_ap.setdefault(g_ap, {}).get(ap_id, 0) + 1

        g_ci = ci_id.rsplit("_", 1)[0]
        grupos_ci.setdefault(g_ci, {})[ci_id] = grupos_ci.setdefault(g_ci, {}).get(ci_id, 0) + 1

    assert len(aperturas) >= 18 * 0.70
    assert len(cierres) >= 12 * 0.70

    for g, counts in grupos_ap.items():
        tot = sum(counts.values())
        max_c = max(counts.values())
        assert max_c / tot <= 0.35, f"Grupo {g} supera 35%: {max_c}/{tot} ({max_c/tot:.1%})"

    for g, counts in grupos_ci.items():
        tot = sum(counts.values())
        max_c = max(counts.values())
        assert max_c / tot <= 0.35, f"Grupo {g} supera 35%: {max_c}/{tot} ({max_c/tot:.1%})"


def test_pista_prompt_continuidad():
    assert "Ya nos ha visitado antes" in build_user_prompt_redaccion(request(1, recetas_previas=1), [], "desconocido", ["CI_INC_1"])
    assert "Primera revisión de seguimiento" in build_user_prompt_redaccion(request(1, recetas_previas=0), [], "desconocido", ["CI_INC_1"])
