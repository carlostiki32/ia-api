"""Preservacion de hechos y urgencia en la frontera motor/prompt/LLM simulado."""
import pytest

from app.correlaciones.registry import evaluar_recordatorios_tecnicos
from app.inference import _ensure_emergency_preserved, _get_active_emergency_alerts
from app.prompt_builder import build_user_prompt
from tests.test_auditoria_correlaciones import _req, activas


@pytest.mark.parametrize("id,entrada,plazo", [
    ("opacidad_cristaliniana", {"anexos": "Leucocoria OD", "edad": 2}, "el mismo dia"),
    ("anexos_patologicos", {"anexos": "Hipopion OI"}, "el mismo dia"),
    ("insuficiencia_convergencia", {"ppc": 8, "cover": "OD: Exo y Foria | OI: Orto", "motivo": "Diplopia OD al leer de inicio subito hoy"}, "el mismo dia"),
    ("ppc_exoforia", {"ppc": 8, "motivo": "Diplopia OD de inicio subito hoy"}, "el mismo dia"),
    ("cover_exoforia_sintomatica", {"cover": "OD: Exo y Foria | OI: Orto", "motivo": "Diplopia OD de inicio subito hoy"}, "el mismo dia"),
    ("cover_endoforia_sintomatica", {"cover": "OD: Endo y Foria | OI: Orto", "motivo": "Diplopia OD de inicio subito hoy"}, "el mismo dia"),
    ("desviacion_vertical", {"cover": "OD: Orto | OI: Hiper y Tropia", "motivo": "Diplopia OI de inicio subito hoy"}, "el mismo dia"),
    ("endotropia_lente", {"cover": "OD: Endo y Tropia | OI: Orto", "motivo": "Diplopia OD de inicio subito hoy"}, "el mismo dia"),
    ("exotropia_lente", {"cover": "OD: Orto | OI: Exo y Tropia", "motivo": "Diplopia OI de inicio subito hoy"}, "el mismo dia"),
    ("cvs_sospecha", {"pantallas": "gt6", "motivo": "Dolor ocular intenso y ojo rojo con fotofobia desde hoy"}, "inmediata en urgencias"),
    ("ambliopia_sospecha", {"rx_od": {"esfera": -3, "cilindro": 0, "av_cc": "20/60"},
                              "rx_oi": {"esfera": 0, "cilindro": 0}, "motivo": "Perdida visual subita OD desde hoy"}, "inmediata en urgencias"),
    ("ambliopia_isoametropica_bilateral", {"edad": 8, "rx_od": {"esfera": 5, "cilindro": 0, "av_cc": "20/40"},
                                          "rx_oi": {"esfera": 5, "cilindro": 0, "av_cc": "20/40"},
                                          "motivo": "Perdida visual subita bilateral desde hoy"}, "inmediata en urgencias"),
    ("deficit_visual_inexplicado_refractivo", {"edad": 25, "rx_od": {"av_cc": "20/60"},
                                               "motivo": "Perdida visual subita OD desde hoy"}, "inmediata en urgencias"),
    ("adulto_mayor_screening", {"edad": 72, "rx_oi": {"av_cc": "20/60"},
                                 "motivo": "Perdida visual subita OI desde hoy"}, "inmediata en urgencias"),
])
def test_h01_preserva_plazo_de_rutas_corregidas(id, entrada, plazo):
    req = _req(**entrada)
    hechos = activas(**entrada)[id]
    assert hechos.startswith("Hallazgo urgente:") and plazo in hechos
    alertas = {a.id: a for a in _get_active_emergency_alerts(req)}
    assert id in alertas and alertas[id].texto_determinista == hechos
    reparado = _ensure_emergency_preserved("Se registra el hallazgo y se recomienda control anual.", req)
    assert plazo in reparado and "control anual" not in reparado
    assert hechos in reparado


def test_recordatorio_de_vertice_separa_salida_tecnica_y_hechos_medicos():
    req = _req(rx_od={"esfera": 0, "cilindro": -5})
    assert evaluar_recordatorios_tecnicos(req)[0][0] == "distancia_vertice_alta_ametropia"
    prompt = build_user_prompt(req)
    assert "Recordatorio tecnico" not in prompt and "compensacion si cambia el plano" not in prompt


def test_pseudofaquia_normal_no_oculta_av_de_otro_ojo_ni_explica_la_propia():
    entrada = dict(anexos="Pseudofaquia OD con capsula transparente", rx_od={"av_cc": "20/60"}, rx_oi={"av_cc": "20/80"})
    salida = activas(**entrada)
    assert "opacidad_cristaliniana" not in salida
    assert "AV con correccion 20/60 en OD" in salida["deficit_visual_inexplicado_refractivo"]
    assert "AV con correccion 20/80 en OI" in salida["deficit_visual_inexplicado_refractivo"]
    assert "causa organica" not in salida["deficit_visual_inexplicado_refractivo"]
