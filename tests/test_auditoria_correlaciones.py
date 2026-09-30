"""Pruebas de aceptacion de la auditoria clinica de correlaciones.

Cubre las ordenes de trabajo transversales (T1, T13, T9, T11, T10).
Basado en AUDITORIA_CORRELACIONES.md seccion 0.1 y seccion 1.
"""
import copy
from datetime import datetime, timedelta
import re
import pytest

from app.correlaciones.registry import evaluar_correlaciones_con_nombres
from app.inference import _ensure_follow_up_last, _get_active_emergency_alerts
from app.schemas import ImpresionClinicaRequest

_BASE = {
    "receta_id": "auditoria",
    "refraccion": {"od": {"esfera": 0.0}, "oi": {"esfera": 0.0}},
}
_ALIAS = {
    "fondo": ("clinica", "fondo_de_ojo"),
    "anexos": ("clinica", "anexos_oculares"),
    "pupilas": ("clinica", "reflejos_pupilares"),
    "motilidad": ("clinica", "motilidad_ocular"),
    "campos": ("clinica", "confrontacion_campos_visuales"),
    "amsler": ("clinica", "grid_de_amsler"),
    "cover": ("clinica", "cover_test"),
    "ppc": ("clinica", "ppc_cm"),
    "but": ("clinica", "ojo_seco_but_seg"),
    "pantallas": ("clinica", "uso_pantallas"),
    "seguimiento": ("clinica", "recomendacion_seguimiento"),
    "motivo": ("paciente", "motivo_consulta"),
    "ocupacion": ("paciente", "ocupacion"),
    "edad": ("paciente", "edad"),
    "lente": ("tipo_lente",),
}

_N = "Reflejo fotomotor, consensual, acomodativo"
_ANUAL = "Se recomienda revision optometrica anual de control. Proxima cita en: 12 meses "


def _req(**campos) -> ImpresionClinicaRequest:
    data = copy.deepcopy(_BASE)
    for clave, valor in campos.items():
        if clave in ("rx_od", "rx_oi"):
            data["refraccion"][clave[-2:]].update(valor)
        elif clave in ("akr_od", "akr_oi"):
            data.setdefault("akr", {}).setdefault(clave[-2:], {}).update(valor)
        elif clave == "akr":
            data.setdefault("akr", {}).update(valor)
        else:
            ruta = _ALIAS[clave]
            if len(ruta) == 1:
                data[ruta[0]] = valor
            else:
                data.setdefault(ruta[0], {})[ruta[1]] = valor
    return ImpresionClinicaRequest.model_validate(data)


def activas(**campos) -> dict[str, str]:
    return dict(evaluar_correlaciones_con_nombres(_req(**campos)))


def alertas_h01(**campos) -> set[str]:
    return {a.id for a in _get_active_emergency_alerts(_req(**campos))}


# ============================================================================
# T1: Negacion prefija con comas y enumeraciones
# ============================================================================


def test_t1_01_sin_evidencia_desgarro_periferico():
    act = activas(fondo="Sin evidencia de desgarro periferico")
    assert "fondo_periferico_riesgo" not in act


def test_t1_02_ausencia_desgarros_perifericos():
    act = activas(fondo="Ausencia de desgarros perifericos")
    assert "fondo_periferico_riesgo" not in act


def test_t1_03_sin_lesiones_sugestivas_desgarro():
    act = activas(fondo="Sin lesiones sugestivas de desgarro retiniano")
    assert "fondo_periferico_riesgo" not in act


def test_t1_04_sin_datos_desprendimiento_retina():
    act = activas(fondo="Retina aplicada, sin datos de desprendimiento de retina periferica")
    assert "fondo_periferico_riesgo" not in act


def test_t1_05_sin_signos_edema_papila_bilateral():
    act = activas(fondo="Sin signos de edema de papila bilateral")
    assert "papila_patologica" not in act


def test_t1_06_sin_presencia_drusas_maculares():
    act = activas(fondo="Sin presencia de drusas maculares")
    assert "fondo_macular_dmae" not in act


def test_t1_07_sin_signos_blefaritis_anterior():
    act = activas(anexos="Sin signos de blefaritis anterior")
    assert "anexos_patologicos" not in act


def test_t1_08_ausencia_pterigion_nasal():
    act = activas(anexos="Ausencia de pterigion nasal")
    assert "anexos_patologicos" not in act


def test_t1_09_cristalino_transparente_sin_catarata():
    act = activas(anexos="Cristalino transparente, sin datos de catarata subcapsular posterior")
    assert "opacidad_cristaliniana" not in act


def test_t1_10_pupilas_normal_sin_anisocoria_marcada():
    act = activas(pupilas=f"{_N}: sin evidencia de anisocoria marcada")
    assert "pupilas_alteradas" not in act


def test_t1_11_campos_sin_evidencia_defecto_temporal():
    act = activas(campos="Sin evidencia de defecto temporal")
    assert "campos_visuales_alterados" not in act


def test_t1_12_motilidad_versiones_sin_limitacion_superior():
    act = activas(motilidad="Versiones: sin evidencia de limitacion superior Ducciones: completas")
    assert "motilidad_alterada" not in act


def test_t1_13_sin_hemorragias_desgarro_temporal_superior():
    act = activas(fondo="Sin hemorragias, desgarro en herradura temporal superior OD")
    assert "fondo_periferico_riesgo" in act
    assert "Hallazgo urgente:" in act["fondo_periferico_riesgo"]


def test_t1_14_sin_hemorragias_ni_exudados_drusas_blandas():
    act = activas(fondo="Sin hemorragias ni exudados, drusas blandas maculares")
    assert "fondo_macular_dmae" in act


def test_t1_15_sin_hemorragias_drusas_blandas():
    act = activas(fondo="Sin hemorragias, drusas blandas maculares")
    assert "fondo_macular_dmae" in act


def test_t1_16_no_se_observan_desgarros_agujeros_ni_lattice():
    act = activas(fondo="No se observan desgarros, agujeros ni lattice")
    assert "fondo_periferico_riesgo" not in act


def test_t1_17_sin_hemorragias_exudados_microaneurismas_ni_neovasos():
    act = activas(fondo="Sin hemorragias, exudados, microaneurismas ni neovasos")
    assert "fondo_vascular_diabetico" not in act


# ============================================================================
# T13: Formas compuestas negadas y "evidente"
# ============================================================================


def test_t13_01_no_se_aprecian_desgarros():
    act = activas(fondo="No se aprecian desgarros")
    assert "fondo_periferico_riesgo" not in act


def test_t13_02_no_se_aprecia_desgarro_periferico():
    act = activas(fondo="No se aprecia desgarro periferico")
    assert "fondo_periferico_riesgo" not in act


def test_t13_03_no_se_evidencian_drusas():
    act = activas(fondo="No se evidencian drusas")
    assert "fondo_macular_dmae" not in act


def test_t13_04_no_se_visualiza_edema_papila():
    act = activas(fondo="No se visualiza edema de papila")
    assert "papila_patologica" not in act


def test_t13_05_no_muestra_muesca():
    act = activas(fondo="No muestra muesca")
    assert "fondo_glaucomatoso" not in act


def test_t13_06_no_se_identifican_microaneurismas():
    act = activas(fondo="No se identifican microaneurismas")
    assert "fondo_vascular_diabetico" not in act


def test_t13_07_no_se_evidencia_dpar():
    act = activas(pupilas="No se evidencia DPAR")
    assert "pupilas_alteradas" not in act


def test_t13_08_no_se_aprecia_catarata():
    act = activas(anexos="No se aprecia catarata")
    assert "opacidad_cristaliniana" not in act


def test_t13_09_no_se_constata_oclusion_venosa():
    act = activas(fondo="No se constata oclusion venosa")
    assert "fondo_oclusion_vascular_urgente" not in act


def test_t13_10_sin_muesca_evidente():
    act = activas(fondo="Sin muesca evidente")
    assert "fondo_glaucomatoso" not in act


def test_t13_11_sin_defecto_evidente():
    act = activas(campos="Sin defecto evidente")
    assert "campos_visuales_alterados" not in act


def test_t13_12_sin_hemorragias_se_aprecia_desgarro():
    act = activas(fondo="Sin hemorragias se aprecia desgarro en herradura temporal OD")
    assert "fondo_periferico_riesgo" in act
    assert "Hallazgo urgente:" in act["fondo_periferico_riesgo"]


def test_t13_13_preset_ui_campos_sin_defectos_evidentes():
    act = activas(campos="Sin defectos perifericos evidentes.")
    assert "campos_visuales_alterados" not in act


# ============================================================================
# T9: Ventana posterior a 3 palabras, asintomatico y plurales
# ============================================================================


def test_t9_01_desgarro_con_macula_normal():
    act = activas(fondo="Desgarro en herradura temporal superior con macula normal")
    assert "fondo_periferico_riesgo" in act
    assert "Hallazgo urgente:" in act["fondo_periferico_riesgo"]


def test_t9_02_desgarro_asintomatico_od():
    act = activas(fondo="Desgarro en herradura asintomatico OD")
    assert "fondo_periferico_riesgo" in act


def test_t9_03_agujero_operculado_con_operculo_libre():
    act = activas(fondo="Agujero operculado con operculo libre")
    assert "fondo_periferico_riesgo" in act


def test_t9_04_lattice_con_papila_normal():
    act = activas(fondo="Lattice con papila normal")
    assert "fondo_periferico_riesgo" in act


def test_t9_05_papiledema_con_macula_normal():
    act = activas(fondo="Papiledema con macula normal")
    assert "papila_patologica" in act
    assert "Hallazgo urgente:" in act["papila_patologica"]


def test_t9_06_palidez_papilar_con_macula_normal():
    act = activas(fondo="Palidez papilar con macula normal")
    assert "papila_patologica" in act


def test_t9_07_hemorragias_en_mancha_plural():
    act = activas(fondo="Hemorragias en mancha en polo posterior")
    assert "fondo_vascular_diabetico" in act


def test_t9_08_hemorragias_retinianas_puntiformes_plural():
    act = activas(fondo="Hemorragias retinianas puntiformes")
    assert "fondo_vascular_diabetico" in act


def test_t9_09_desgarro_descartado():
    act = activas(fondo="Desgarro descartado")
    assert "fondo_periferico_riesgo" not in act


def test_t9_10_lattice_ausente():
    act = activas(fondo="Lattice ausente")
    assert "fondo_periferico_riesgo" not in act


def test_t9_11_anisocoria_fisiologica():
    act = activas(pupilas=f"{_N}: anisocoria fisiologica")
    assert "pupilas_alteradas" not in act


def test_t9_12_dpar_od_negativo():
    act = activas(pupilas="DPAR OD negativo")
    assert "pupilas_alteradas" not in act


def test_t9_13_excavacion_fisiologica_amplia():
    act = activas(fondo="Excavacion fisiologica amplia")
    assert "fondo_glaucomatoso" not in act


# ============================================================================
# T11: Formato "etiqueta: valor"
# ============================================================================


def test_t11_01_edema_papila_negativo():
    act = activas(fondo="Edema de papila: negativo")
    assert "papila_patologica" not in act


def test_t11_02_desgarros_no():
    act = activas(fondo="Desgarros: no")
    assert "fondo_periferico_riesgo" not in act


def test_t11_03_dpar_negativo():
    act = activas(pupilas="DPAR: negativo")
    assert "pupilas_alteradas" not in act


def test_t11_04_microaneurismas_no_se_observan():
    act = activas(fondo="Microaneurismas: no se observan")
    assert "fondo_vascular_diabetico" not in act


def test_t11_05_lattice_ausente():
    act = activas(fondo="Lattice: ausente")
    assert "fondo_periferico_riesgo" not in act


def test_t11_06_desgarro_si_en_herradura():
    act = activas(fondo="Desgarro: si, en herradura temporal OD")
    assert "fondo_periferico_riesgo" in act
    assert "Hallazgo urgente:" in act["fondo_periferico_riesgo"]


def test_t11_07_edema_papila_presente():
    act = activas(fondo="Edema de papila: presente en OD")
    assert "papila_patologica" in act
    assert "Hallazgo urgente:" in act["papila_patologica"]


# ============================================================================
# T10: "Descartar X" como sospecha activa vs resolucion
# ============================================================================


def test_t10_01_descartar_ovcr_sospecha_activa():
    act = activas(fondo="Hemorragias en llama en 4 cuadrantes OD, descartar OVCR")
    assert "fondo_oclusion_vascular_urgente" in act
    assert "Hallazgo urgente:" in act["fondo_oclusion_vascular_urgente"]


def test_t10_02_descarte_con_resolucion_sin_hallazgos():
    act = activas(fondo="Fondo de ojo para descarte de retinopatia diabetica: sin hallazgos")
    assert "fondo_vascular_diabetico" not in act


def test_t10_03_se_descarta_desprendimiento_retina():
    act = activas(fondo="Se descarta desprendimiento de retina")
    assert "fondo_periferico_riesgo" not in act


def test_t10_04_desprendimiento_retina_descartado():
    act = activas(fondo="Desprendimiento de retina descartado")
    assert "fondo_periferico_riesgo" not in act


def test_t10_05_a_descartar_edema_papila_sospecha():
    act = activas(fondo="A descartar edema de papila en OD")
    assert "papila_patologica" in act


def test_t10_06_descarte_dmae_negativo():
    act = activas(fondo="Descarte de DMAE: negativo")
    assert "fondo_macular_dmae" not in act


# ============================================================================
# T2: Chip "Marcus Gunn" como DPAR en reflejos pupilares
# ============================================================================


def test_t2_01_chip_marcus_gunn_conserva_dpar_sin_inventar_inicio():
    act = activas(pupilas="Marcus Gunn")
    assert "pupilas_alteradas" in act
    assert "defecto pupilar aferente relativo" in act["pupilas_alteradas"]
    assert "Hallazgo urgente:" not in act["pupilas_alteradas"]
    assert "decidir la prioridad" in act["pupilas_alteradas"]
    assert "desambiguar" not in act["pupilas_alteradas"]


def test_t2_02_chip_marcus_gunn_con_lateralidad_activa_dpar():
    act = activas(pupilas="Marcus Gunn: OI")
    assert "pupilas_alteradas" in act
    assert "defecto pupilar aferente relativo" in act["pupilas_alteradas"]
    assert "desambiguar" not in act["pupilas_alteradas"]


def test_t2_03_chip_marcus_gunn_con_fondo_activa_glaucoma_asimetrico():
    act = activas(pupilas="Marcus Gunn: OD", fondo="Excavacion 0.8 OD, 0.4 OI")
    assert "glaucoma_asimetrico" in act


def test_t2_04_fenomeno_marcus_gunn_mandibulopalpebral_no_es_dpar():
    act = activas(pupilas=f"{_N}: fenomeno de Marcus Gunn mandibulopalpebral")
    if "pupilas_alteradas" in act:
        assert "defecto pupilar aferente" not in act["pupilas_alteradas"]


# ============================================================================
# T4: Convencion de signo y eje queratometrico (minus-cylinder)
# ============================================================================


def test_t4_01_cornea_congruente_k_cil_negativo_no_dispara():
    act = activas(
        rx_od={"esfera": -1.00, "cilindro": -2.00, "eje": 180},
        akr_od={"k1_d": 42.00, "k1_eje": 180, "k2_d": 44.00, "k2_eje": 90, "k_promedio_d": 43.00, "k_cilindro": -2.00, "k_cilindro_eje": 180},
    )
    assert "astigmatismo_corneal_vs_refractivo" not in act


def test_t4_02_cornea_congruente_k_cil_positivo_transpone_eje_no_dispara():
    act = activas(
        rx_od={"esfera": -1.00, "cilindro": -2.00, "eje": 180},
        akr_od={"k1_d": 42.00, "k1_eje": 180, "k2_d": 44.00, "k2_eje": 90, "k_promedio_d": 43.00, "k_cilindro": 2.00, "k_cilindro_eje": 90},
    )
    assert "astigmatismo_corneal_vs_refractivo" not in act


def test_t4_03_cornea_congruente_etiquetas_k1_k2_invertidas_no_dispara():
    act = activas(
        rx_od={"esfera": -1.00, "cilindro": -2.00, "eje": 180},
        akr_od={"k1_d": 44.00, "k1_eje": 90, "k2_d": 42.00, "k2_eje": 180, "k_promedio_d": 43.00},
    )
    assert "astigmatismo_corneal_vs_refractivo" not in act


def test_t4_04_cornea_contra_la_regla_real_dispara_discrepancia():
    act = activas(
        rx_od={"esfera": -1.00, "cilindro": -2.00, "eje": 180},
        akr_od={"k1_d": 42.00, "k1_eje": 90, "k2_d": 44.00, "k2_eje": 180, "k_promedio_d": 43.00},
    )
    assert "astigmatismo_corneal_vs_refractivo" in act


# ============================================================================
# T3: taken_at es metadata; el contrato no acredita fecha de la Rx
# ============================================================================


def test_t3_01_akr_reciente_hace_2h_dispara_variabilidad():
    hace_2h = (datetime.now() - timedelta(hours=2)).strftime("%Y-%m-%d %H:%M:%S")
    act = activas(
        edad=30,
        rx_od={"esfera": -0.50},
        akr={"taken_at": hace_2h},
        akr_od={"esfera": -2.00},
    )
    assert "ar_rx_variabilidad_inespecifica" in act


def test_t3_02_akr_antiguo_hace_90d_conserva_diferencia_de_registros():
    hace_90d = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d %H:%M:%S")
    act = activas(
        edad=30,
        rx_od={"esfera": -0.50},
        akr={"taken_at": hace_90d},
        akr_od={"esfera": -2.00},
    )
    assert "ar_rx_variabilidad_inespecifica" in act
    assert "no acreditan simultaneidad" in act["ar_rx_variabilidad_inespecifica"]


def test_t3_03_akr_sin_taken_at_describe_sin_asumir_del_dia():
    act = activas(
        edad=30,
        rx_od={"esfera": -0.50},
        akr_od={"esfera": -2.00},
    )
    assert "ar_rx_variabilidad_inespecifica" in act
    assert "no acreditan simultaneidad" in act["ar_rx_variabilidad_inespecifica"]


def test_t3_04_akr_taken_at_invalido_coerciona_a_none_y_dispara():
    req = _req(
        edad=30,
        rx_od={"esfera": -0.50},
        akr={"taken_at": "no-es-fecha"},
        akr_od={"esfera": -2.00},
    )
    act = dict(evaluar_correlaciones_con_nombres(req))
    assert "ar_rx_variabilidad_inespecifica" in act


# ============================================================================
# T8: Salvaguarda de Urgencia H01 (urgencia por prefijo unico)
# ============================================================================


def test_t8_01_motivo_moscas_volantes_no_h01_y_preserva_seguimiento():
    """T8-01: 'Moscas volantes' sin inicio agudo es nivel C (no urgente).
    No activa alerta H01 y preserva la recomendacion de control anual."""
    alertas = alertas_h01(motivo="Moscas volantes")
    assert "sintomas_alarma_traccion_vitreoretina" not in alertas

    req = _req(motivo="Moscas volantes", seguimiento=_ANUAL)
    texto_llm = "Paciente refiere moscas volantes habituales. Fondo de ojo normal."
    resultado = _ensure_follow_up_last(texto_llm, _ANUAL, payload=req)
    assert "revision optometrica anual" in resultado.lower()


def test_t8_02_fondo_lattice_aislado_no_genera_h01():
    """T8-02: Degeneracion lattice en OI sin rotura no es urgente y no genera alerta H01."""
    alertas = alertas_h01(fondo="Degeneracion lattice en periferia temporal OI")
    assert "fondo_periferico_riesgo" not in alertas


def test_t8_03_fondo_desgarro_herradura_genera_h01():
    """T8-03: Desgarro en herradura en OD es urgente y genera alerta H01."""
    alertas = alertas_h01(fondo="Desgarro en herradura temporal superior OD")
    assert "fondo_periferico_riesgo" in alertas


# ============================================================================
# C02: sintomas_alarma_traccion_vitreoretina (Niveles A, B y C)
# ============================================================================


def test_c02_01_fotopsias_recientes_dos_dias_urgente_48h():
    act = activas(motivo="Fotopsias en OI desde hace 2 dias")
    assert "sintomas_alarma_traccion_vitreoretina" in act
    assert "Hallazgo urgente:" in act["sintomas_alarma_traccion_vitreoretina"]
    assert "48 horas" in act["sintomas_alarma_traccion_vitreoretina"]


def test_c02_02_cortina_alarma_mismo_dia():
    act = activas(motivo="Veo una cortina negra que sube desde ayer en OI")
    assert "sintomas_alarma_traccion_vitreoretina" in act
    assert "Hallazgo urgente:" in act["sintomas_alarma_traccion_vitreoretina"]
    assert "mismo dia" in act["sintomas_alarma_traccion_vitreoretina"]


def test_c02_03_perdida_subita_vision_con_destellos_alarma_mismo_dia():
    act = activas(motivo="Perdida subita de vision periferica en OI con destellos")
    assert "sintomas_alarma_traccion_vitreoretina" in act
    assert "Hallazgo urgente:" in act["sintomas_alarma_traccion_vitreoretina"]
    assert "mismo dia" in act["sintomas_alarma_traccion_vitreoretina"]


def test_c02_04_moscas_volantes_sin_tiempo_evolucion_nivel_c_no_urgente():
    act = activas(motivo="Moscas volantes")
    assert "sintomas_alarma_traccion_vitreoretina" in act
    assert "Hallazgo urgente" not in act["sintomas_alarma_traccion_vitreoretina"]
    assert "sin tiempo de evolucion documentado" in act["sintomas_alarma_traccion_vitreoretina"]
    assert "agudas" not in act["sintomas_alarma_traccion_vitreoretina"]


def test_c02_05_moscas_volantes_desde_hace_anos_sin_cambios_no_dispara():
    act = activas(motivo="Moscas volantes desde hace anos, sin cambios")
    assert "sintomas_alarma_traccion_vitreoretina" not in act


def test_c02_06_moscas_volantes_hace_tres_dias_vision_sin_cambios_urgente():
    act = activas(motivo="Moscas volantes desde hace 3 dias, vision sin cambios")
    assert "sintomas_alarma_traccion_vitreoretina" in act
    assert "Hallazgo urgente:" in act["sintomas_alarma_traccion_vitreoretina"]


def test_c02_07_moscas_volantes_de_siempre_nueva_graduacion_no_dispara():
    act = activas(motivo="Moscas volantes de siempre; desea nueva graduacion")
    assert "sintomas_alarma_traccion_vitreoretina" not in act


def test_c02_08_destellos_alrededor_luces_al_manejar_exclusion_no_dispara():
    act = activas(motivo="Veo destellos alrededor de las luces al manejar de noche")
    assert "sintomas_alarma_traccion_vitreoretina" not in act


def test_c02_09_halos_y_destellos_luces_autos_exclusion_no_dispara():
    act = activas(motivo="Halos y destellos con las luces de los autos")
    assert "sintomas_alarma_traccion_vitreoretina" not in act


def test_c02_10_migrana_con_aura_luces_zigzag_exclusion_no_dispara():
    act = activas(motivo="Migrana con aura: ve luces en zigzag y centelleos antes del dolor de cabeza")
    assert "sintomas_alarma_traccion_vitreoretina" not in act


def test_c02_11_aura_migranosa_con_moscas_volantes_nuevas_urgente():
    act = activas(motivo="Aura migranosa con destellos y ahora moscas volantes nuevas desde ayer")
    assert "sintomas_alarma_traccion_vitreoretina" in act
    assert "Hallazgo urgente:" in act["sintomas_alarma_traccion_vitreoretina"]


def test_c02_12_niega_fotopsias_y_miodesopsias_no_dispara():
    act = activas(motivo="Niega fotopsias y miodesopsias")
    assert "sintomas_alarma_traccion_vitreoretina" not in act


def test_c02_13_no_refiere_destellos_temporales_no_dispara():
    act = activas(motivo="No refiere destellos temporales")
    assert "sintomas_alarma_traccion_vitreoretina" not in act


def test_c02_14_fondo_dvp_anillo_weiss_sin_motivo_no_dispara():
    act = activas(fondo="DVP completo con anillo de Weiss, retina aplicada")
    assert "sintomas_alarma_traccion_vitreoretina" not in act


def test_c02_15_revision_anual_flashes_ocasionales_no_urgente_y_no_h01():
    act = activas(motivo="Revision anual, refiere flashes de luz ocasionales", seguimiento=_ANUAL)
    assert "sintomas_alarma_traccion_vitreoretina" in act
    assert "Hallazgo urgente" not in act["sintomas_alarma_traccion_vitreoretina"]
    alertas = alertas_h01(motivo="Revision anual, refiere flashes de luz ocasionales", seguimiento=_ANUAL)
    assert "sintomas_alarma_traccion_vitreoretina" not in alertas


def test_c02_16_fotopsias_subitas_con_desgarro_fondo_suprime_sintomas():
    act = activas(motivo="Fotopsias subitas", fondo="Desgarro en herradura OD")
    assert "sintomas_alarma_traccion_vitreoretina" not in act
    assert "fondo_periferico_riesgo" in act
    assert "Hallazgo urgente:" in act["fondo_periferico_riesgo"]


# ============================================================================
# C01: Correlacion #1 fondo_periferico_riesgo (6 niveles jerarquicos)
# ============================================================================


def test_c01_01_desgarro_en_herradura_urgente_sin_profilactico():
    act = activas(fondo="Desgarro en herradura temporal superior OD")
    assert "fondo_periferico_riesgo" in act
    text = act["fondo_periferico_riesgo"]
    assert "Hallazgo urgente:" in text
    assert "desgarro" in text.lower()
    assert "profilactico" not in text.lower()


def test_c01_02_desprendimiento_retina_mismo_dia():
    act = activas(fondo="Desprendimiento de retina inferior OD con macula aplicada")
    assert "fondo_periferico_riesgo" in act
    text = act["fondo_periferico_riesgo"]
    assert "Hallazgo urgente:" in text
    assert "mismo dia" in text.lower()


def test_c01_03_drr_inferior_urgente():
    act = activas(fondo="DRR inferior OD")
    assert "fondo_periferico_riesgo" in act
    assert "Hallazgo urgente:" in act["fondo_periferico_riesgo"]


def test_c01_04_dialisis_inferotemporal_urgente():
    act = activas(fondo="Dialisis inferotemporal OD")
    assert "fondo_periferico_riesgo" in act
    assert "Hallazgo urgente:" in act["fondo_periferico_riesgo"]


def test_c01_05_rotura_en_herradura_urgente():
    act = activas(fondo="Rotura en herradura OD")
    assert "fondo_periferico_riesgo" in act
    assert "Hallazgo urgente:" in act["fondo_periferico_riesgo"]


def test_c01_06_hemorragia_vitrea_urgente():
    act = activas(fondo="Hemorragia vitrea OD, sin visualizacion de retina periferica")
    assert "fondo_periferico_riesgo" in act
    text = act["fondo_periferico_riesgo"]
    assert "Hallazgo urgente:" in text
    assert "vitreo" in text.lower()


def test_c01_07_lattice_sin_sintomas_no_urgente_educacion():
    act = activas(fondo="Degeneracion lattice en periferia temporal OI")
    assert "fondo_periferico_riesgo" in act
    text = act["fondo_periferico_riesgo"]
    assert "Hallazgo urgente:" not in text
    assert "educacion" in text.lower()


def test_c01_08_lattice_con_fotopsias_recientes_urgente_suprime_sintomas():
    act = activas(
        fondo="Degeneracion lattice en periferia temporal OI",
        motivo="Fotopsias en OI desde hace 3 dias",
    )
    assert "fondo_periferico_riesgo" in act
    assert "Hallazgo urgente:" in act["fondo_periferico_riesgo"]
    assert "sintomas_alarma_traccion_vitreoretina" not in act


def test_c01_09_agujero_operculado_asintomatico_no_urgente():
    act = activas(fondo="Agujero operculado OD")
    assert "fondo_periferico_riesgo" in act
    assert "Hallazgo urgente:" not in act["fondo_periferico_riesgo"]


def test_c01_10_retinosquisis_periferica_no_urgente():
    act = activas(fondo="Retinosquisis periferica inferotemporal")
    assert "fondo_periferico_riesgo" in act
    assert "Hallazgo urgente:" not in act["fondo_periferico_riesgo"]


def test_c01_11_blanco_con_presion_benigno_no_dispara():
    act = activas(fondo="Blanco con presion en periferia inferior")
    assert "fondo_periferico_riesgo" not in act


def test_c01_12_desprendimiento_neurosensorial_seroso_cscr_no_dispara():
    act = activas(fondo="Desprendimiento neurosensorial seroso macular compatible con CSC")
    assert "fondo_periferico_riesgo" not in act


def test_c01_13_antecedente_dr_operado_no_urgente():
    act = activas(fondo="Antecedente de desprendimiento de retina operado OD, retina aplicada")
    assert "fondo_periferico_riesgo" in act
    text = act["fondo_periferico_riesgo"]
    assert "Hallazgo urgente:" not in text
    assert "antecedente" in text.lower()


def test_c01_14_desgarro_tratado_con_laser_antecedente_no_urgente():
    act = activas(fondo="Desgarro tratado con laser, cicatriz pigmentada estable")
    assert "fondo_periferico_riesgo" in act
    assert "Hallazgo urgente:" not in act["fondo_periferico_riesgo"]


def test_c01_15_desgarro_epitelio_pigmentario_macular_no_dispara():
    act = activas(fondo="Desgarro del epitelio pigmentario macular")
    assert "fondo_periferico_riesgo" not in act


def test_c01_16_lattice_y_ruptura_membrana_bruch_no_urgente():
    act = activas(fondo="Lattice y ruptura de membrana de Bruch")
    assert "fondo_periferico_riesgo" in act
    assert "Hallazgo urgente:" not in act["fondo_periferico_riesgo"]


def test_c01_17_antecedente_laser_od_y_desgarro_nuevo_oi_urgente():
    act = activas(fondo="Antecedente de desgarro tratado con laser en OD. Desgarro en herradura nuevo en OI")
    assert "fondo_periferico_riesgo" in act
    assert "Hallazgo urgente:" in act["fondo_periferico_riesgo"]


def test_c01_18_paciente_en_hemodialisis_no_dispara():
    act = activas(fondo="Paciente en hemodialisis, retina aplicada sin lesiones")
    assert "fondo_periferico_riesgo" not in act


def test_c01_19_lattice_seguimiento_anual_no_h01():
    act = activas(fondo="Degeneracion lattice en periferia temporal OI", seguimiento=_ANUAL)
    assert "fondo_periferico_riesgo" in act
    assert "Hallazgo urgente:" not in act["fondo_periferico_riesgo"]
    alertas = alertas_h01(fondo="Degeneracion lattice en periferia temporal OI", seguimiento=_ANUAL)
    assert "fondo_periferico_riesgo" not in alertas


def test_c01_20_lattice_con_moscas_sin_tiempo_ambas_no_urgentes():
    act = activas(
        fondo="Degeneracion lattice en periferia temporal OI",
        motivo="Moscas volantes",
    )
    assert "fondo_periferico_riesgo" in act
    assert "Hallazgo urgente:" not in act["fondo_periferico_riesgo"]
    assert "sintomas_alarma_traccion_vitreoretina" in act
    assert "Hallazgo urgente:" not in act["sintomas_alarma_traccion_vitreoretina"]


# ============================================================================
# C03: Correlacion #3 fondo_oclusion_vascular_urgente y fondo_embolo_retiniano
# ============================================================================


def test_c03_01_mancha_rojo_cereza_edad_72_arterial_con_acg():
    act = activas(fondo="Mancha rojo cereza en OD con arteriolas adelgazadas", edad=72)
    assert "fondo_oclusion_vascular_urgente" in act
    text = act["fondo_oclusion_vascular_urgente"]
    assert "Hallazgo urgente:" in text
    assert "evento vascular cerebral" in text.lower()
    assert "arteritis de celulas gigantes" in text.lower()


def test_c03_02_mancha_rojo_cereza_edad_40_arterial_sin_acg():
    act = activas(fondo="Mancha rojo cereza en OD con arteriolas adelgazadas", edad=40)
    assert "fondo_oclusion_vascular_urgente" in act
    text = act["fondo_oclusion_vascular_urgente"]
    assert "Hallazgo urgente:" in text
    assert "arteritis" not in text.lower()


def test_c03_03_ovcr_edad_65_venosa_prioritaria():
    act = activas(fondo="OVCR en OI con hemorragias en llama en 4 cuadrantes", edad=65)
    assert "fondo_oclusion_vascular_urgente" in act
    text = act["fondo_oclusion_vascular_urgente"]
    assert "Hallazgo urgente:" in text
    assert "presion intraocular" in text.lower()
    assert "emergencia" not in text.lower()
    assert "tromboembolico" not in text.lower()
    assert "rutina" not in text.lower()


def test_c03_04_ovcr_edad_42_venosa_con_hipercoagulabilidad():
    act = activas(fondo="OVCR en OI con hemorragias en llama en 4 cuadrantes", edad=42)
    assert "fondo_oclusion_vascular_urgente" in act
    text = act["fondo_oclusion_vascular_urgente"]
    assert "hipercoagulabilidad" in text.lower()


def test_c03_05_oclusion_vena_central_retina():
    act = activas(fondo="Oclusion de la vena central de la retina OD")
    assert "fondo_oclusion_vascular_urgente" in act
    assert "Hallazgo urgente:" in act["fondo_oclusion_vascular_urgente"]


def test_c03_06_oclusion_vascular_retiniana_sin_tipificar():
    act = activas(fondo="Oclusion vascular retiniana OI")
    assert "fondo_oclusion_vascular_urgente" in act
    text = act["fondo_oclusion_vascular_urgente"]
    assert "Hallazgo urgente:" in text
    assert "mismo dia" in text.lower()


def test_c03_07_descartar_ovcr_activa_sospecha():
    act = activas(fondo="Hemorragias en llama en 4 cuadrantes OD, descartar OVCR")
    assert "fondo_oclusion_vascular_urgente" in act
    assert "Hallazgo urgente:" in act["fondo_oclusion_vascular_urgente"]


def test_c03_08_antecedente_ovcr_secuela_no_urgente_no_h01():
    act = activas(
        fondo="Antecedente de OVCR en OI tratada con antiangiogenicos, secuela estable",
        seguimiento=_ANUAL,
    )
    assert "fondo_oclusion_vascular_urgente" in act
    text = act["fondo_oclusion_vascular_urgente"]
    assert "Hallazgo urgente:" not in text
    assert "seguimiento" in text.lower()
    alertas = alertas_h01(
        fondo="Antecedente de OVCR en OI tratada con antiangiogenicos, secuela estable",
        seguimiento=_ANUAL,
    )
    assert "fondo_oclusion_vascular_urgente" not in alertas


def test_c03_09_oclusion_rama_venosa_antigua_con_colaterales_no_urgente():
    act = activas(fondo="Oclusion de rama venosa temporal superior antigua con vasos colaterales")
    assert "fondo_oclusion_vascular_urgente" in act
    assert "Hallazgo urgente:" not in act["fondo_oclusion_vascular_urgente"]


def test_c03_10_trombosis_venosa_profunda_sistemica_no_dispara():
    act = activas(fondo="Paciente anticoagulado por trombosis venosa profunda previa; fondo de ojo normal")
    assert "fondo_oclusion_vascular_urgente" not in act


def test_c03_11_microinfarto_retiniano_peripapilar_no_dispara():
    act = activas(fondo="Microinfarto retiniano peripapilar")
    assert "fondo_oclusion_vascular_urgente" not in act


def test_c03_12_sin_evidencia_oclusion_venosa_no_dispara():
    act = activas(fondo="Sin evidencia de oclusion venosa temporal")
    assert "fondo_oclusion_vascular_urgente" not in act


def test_c03_13_trombosis_sistemica_no_apaga_adulto_mayor_screening():
    act = activas(
        edad=67,
        rx_od={"esfera": 1.0, "av_cc": "20/60"},
        rx_oi={"esfera": 1.0, "av_cc": "20/60"},
        fondo="Paciente anticoagulado por trombosis venosa profunda previa; fondo de ojo normal",
    )
    assert "adulto_mayor_screening" in act


def test_c03_14_embolo_colesterol_hollenhorst_ambulatorio_no_urgente():
    act = activas(fondo="Embolo de colesterol (placa de Hollenhorst) en arteriola temporal inferior OD")
    assert "fondo_embolo_retiniano" in act
    assert "Hallazgo urgente:" not in act["fondo_embolo_retiniano"]


def test_c03_15_placa_hollenhorst_con_amaurosis_fugaz_urgente():
    act = activas(
        fondo="Placa de Hollenhorst en arteriola temporal inferior OD",
        motivo="Amaurosis fugaz en OD hace 2 dias",
    )
    assert "fondo_embolo_retiniano" in act
    assert "Hallazgo urgente:" in act["fondo_embolo_retiniano"]


def test_c03_16_ovr_od_urgente():
    act = activas(fondo="OVR OD")
    assert "fondo_oclusion_vascular_urgente" in act
    assert "Hallazgo urgente:" in act["fondo_oclusion_vascular_urgente"]


# ============================================================================
# C04: papila_patologica (#4)
# ============================================================================


def test_c04_01_papiledema_bilateral_edad_30_urgente_24h_sin_arteritis():
    act = activas(fondo="Papiledema bilateral", edad=30)
    assert "papila_patologica" in act
    assert "Hallazgo urgente:" in act["papila_patologica"]
    assert "24 horas" in act["papila_patologica"]
    assert "arteritis" not in act["papila_patologica"]


def test_c04_02_edema_papila_od_edad_68_urgente_con_arteritis():
    act = activas(fondo="Edema de papila OD", edad=68)
    assert "papila_patologica" in act
    assert "Hallazgo urgente:" in act["papila_patologica"]
    assert "arteritis de celulas gigantes" in act["papila_patologica"]


def test_c04_03_papilas_edematosas_bilaterales_urgente():
    act = activas(fondo="Papilas edematosas bilaterales")
    assert "papila_patologica" in act
    assert "Hallazgo urgente:" in act["papila_patologica"]


def test_c04_04_bordes_borrosos_con_hemorragias_en_llama_urgente():
    act = activas(fondo="Papila OD con bordes borrosos y hemorragias peripapilares en llama")
    assert "papila_patologica" in act
    assert "Hallazgo urgente:" in act["papila_patologica"]


def test_c04_05_bordes_borrosos_od_aislados_no_urgente_preferente():
    act = activas(fondo="Papilas con bordes borrosos en OD")
    assert "papila_patologica" in act
    assert "Hallazgo urgente:" not in act["papila_patologica"]
    assert "preferente" in act["papila_patologica"]


def test_c04_06_bordes_borrosos_con_oscurecimientos_visuales_hic_urgente():
    act = activas(
        fondo="Papilas con bordes borrosos en OD",
        motivo="Cefalea y oscurecimientos visuales transitorios al agacharse",
    )
    assert "papila_patologica" in act
    assert "Hallazgo urgente:" in act["papila_patologica"]


def test_c04_07_bordes_borrosos_con_cefalea_frecuente_no_urgente():
    act = activas(fondo="Papilas con bordes borrosos en OD", motivo="Cefalea frecuente")
    assert "papila_patologica" in act
    assert "Hallazgo urgente:" not in act["papila_patologica"]


def test_c04_08_disco_inclinado_bordes_difuminados_por_miopia_no_urgente():
    act = activas(fondo="Disco inclinado con bordes difuminados nasales por miopia")
    assert "papila_patologica" in act
    assert "Hallazgo urgente:" not in act["papila_patologica"]


def test_c04_09_fibras_mielina_peripapilares_no_urgente():
    act = activas(fondo="Bordes borrosos por fibras de mielina peripapilares")
    assert "papila_patologica" in act
    assert "Hallazgo urgente:" not in act["papila_patologica"]


def test_c04_10_pseudopapiledema_por_drusas_nervio_optico_no_urgente():
    act = activas(fondo="Pseudopapiledema por drusas del nervio optico")
    assert "papila_patologica" in act
    assert "Hallazgo urgente:" not in act["papila_patologica"]


def test_c04_11_drusas_blandas_bordes_mal_definidos_en_macula_no_papila():
    act = activas(fondo="Drusas blandas de bordes mal definidos en macula OD")
    assert "papila_patologica" not in act


def test_c04_12_nevus_coroideo_bordes_difuminados_temporal_a_papila_no_papila():
    act = activas(fondo="Nevus coroideo de bordes difuminados temporal a papila OD")
    assert "papila_patologica" not in act


def test_c04_13_palidez_papilar_temporal_od_campimetria():
    act = activas(fondo="Palidez papilar temporal OD")
    assert "papila_patologica" in act
    assert "Hallazgo urgente:" not in act["papila_patologica"]
    assert "campimetria" in act["papila_patologica"]


def test_c04_14_excavacion_08_con_palidez_papilar_od_suprime_glaucomatoso():
    act = activas(fondo="Excavacion 0.8 con palidez papilar OD")
    assert "papila_patologica" in act
    assert "no glaucomatosa" in act["papila_patologica"]
    assert "fondo_glaucomatoso" not in act
    assert "no asociada a excavacion glaucomatosa" not in act["papila_patologica"]


def test_c04_15_antecedente_neuritis_optica_od_no_urgente():
    act = activas(fondo="Antecedente de neuritis optica OD")
    assert "papila_patologica" in act
    assert "Hallazgo urgente:" not in act["papila_patologica"]
    assert "antecedente" in act["papila_patologica"]


def test_c04_16_sin_signos_edema_papila_no_dispara():
    act = activas(fondo="Sin signos de edema de papila bilateral")
    assert "papila_patologica" not in act


def test_c04_17_papiledema_con_macula_normal_urgente():
    act = activas(fondo="Papiledema con macula normal")
    assert "papila_patologica" in act
    assert "Hallazgo urgente:" in act["papila_patologica"]


def test_c04_18_neuropatia_optica_glaucomatosa_no_activa_papila_patologica():
    act = activas(fondo="Neuropatia optica glaucomatosa OD")
    assert "papila_patologica" not in act


def test_c04_19_bordes_borrosos_od_no_genera_h01_y_preserva_control_anual():
    alertas = alertas_h01(fondo="Papilas con bordes borrosos en OD")
    assert "papila_patologica" not in alertas

    req = _req(fondo="Papilas con bordes borrosos en OD", seguimiento=_ANUAL)
    texto_llm = "Se documentan bordes papilares poco definidos en OD. " + _ANUAL
    resultado = _ensure_follow_up_last(texto_llm, _ANUAL, payload=req)
    assert "revision optometrica anual" in resultado.lower()


def test_c04_20_disco_inclinado_miopico_no_apaga_deficit_visual_inexplicado():
    act = activas(
        edad=30,
        rx_od={"esfera": -1.00, "av_cc": "20/50", "av_sc": "20/200"},
        rx_oi={"esfera": -1.00, "av_cc": "20/20"},
        fondo="Disco inclinado con bordes difuminados nasales por miopia OD",
    )
    assert "deficit_visual_inexplicado_refractivo" in act


# ============================================================================
# C05: glaucoma_asimetrico (#5)
# ============================================================================

_BASE5 = dict(
    pupilas="DPAR OD",
    fondo="C/D 0.8 OD, 0.4 OI",
    edad=62,
    rx_od={"av_cc": "20/25"},
)


def test_c05_01_base5_glaucoma_asimetrico_preferente_suprime_pupilas_y_glaucomatoso():
    act = activas(**_BASE5)
    assert "glaucoma_asimetrico" in act
    assert "Hallazgo urgente:" not in act["glaucoma_asimetrico"]
    assert "preferente" in act["glaucoma_asimetrico"]
    assert "tonometria" in act["glaucoma_asimetrico"]
    assert "pupilas_alteradas" not in act
    assert "fondo_glaucomatoso" not in act


def test_c05_02_marcus_gunn_lateralizado_od_activa():
    act = activas(pupilas="Marcus Gunn: OD", fondo="Excavacion 0.8 OD, 0.4 OI", edad=60)
    assert "glaucoma_asimetrico" in act


def test_c05_03_marcus_gunn_sin_lateralidad_no_activa_asimetrico_va_a_pupilas():
    act = activas(pupilas="Marcus Gunn", fondo="C/D 0.8 OD, 0.4 OI", edad=60)
    assert "glaucoma_asimetrico" not in act
    assert "pupilas_alteradas" in act
    assert "defecto pupilar aferente relativo" in act["pupilas_alteradas"]


def test_c05_04_dpar_oi_con_excavacion_mayor_contralateral_no_activa_urgente_pupilas():
    act = activas(pupilas="DPAR OI", fondo="Excavacion 0.8 OD, 0.3 OI", edad=60)
    assert "glaucoma_asimetrico" not in act
    assert "pupilas_alteradas" in act
    assert "Hallazgo urgente:" not in act["pupilas_alteradas"]
    assert "defecto pupilar aferente relativo OI" in act["pupilas_alteradas"]


def test_c05_05_sin_excavacion_patologica_no_activa():
    act = activas(
        pupilas="DPAR OD",
        fondo="Papila de bordes nitidos, excavacion 0.3 AO, sin excavacion patologica",
        edad=60,
    )
    assert "glaucoma_asimetrico" not in act


def test_c05_06_excavacion_central_generica_no_activa():
    act = activas(pupilas="DPAR OD", fondo="Papila con excavacion central", edad=60)
    assert "glaucoma_asimetrico" not in act


def test_c05_07_hemorragia_en_astilla_aislada_no_activa():
    act = activas(pupilas="DPAR OD", fondo="Hemorragia en astilla peripapilar OD", edad=60)
    assert "glaucoma_asimetrico" not in act


def test_c05_08_palidez_del_anillo_bloquea_y_deriva_a_papila_patologica():
    act = activas(pupilas="DPAR OD", fondo="c/d 0.7 OD, 0.3 OI con palidez del anillo OD", edad=60)
    assert "glaucoma_asimetrico" not in act
    assert "papila_patologica" in act


def test_c05_09_edad_menor_50_bloquea():
    act = activas(pupilas="DPAR OD", fondo="C/D 0.8 OD, 0.4 OI", edad=38)
    assert "glaucoma_asimetrico" not in act


def test_c05_10_av_cc_peor_20_40_bloquea():
    params = copy.deepcopy(_BASE5)
    params["rx_od"] = {"av_cc": "20/200"}
    act = activas(**params)
    assert "glaucoma_asimetrico" not in act


def test_c05_11_excavacion_simetrica_ep_07_ao_no_activa():
    act = activas(pupilas="DPAR OD", fondo="E/P 0.7 AO", edad=60)
    assert "glaucoma_asimetrico" not in act


def test_c05_12_hemianopsia_en_campos_bloquea():
    params = copy.deepcopy(_BASE5)
    params["campos"] = "Hemianopsia temporal OI"
    act = activas(**params)
    assert "glaucoma_asimetrico" not in act


def test_c05_13_dpar_negativo_no_activa_asimetrico_activa_fondo_glaucomatoso():
    act = activas(pupilas=_N + ": DPAR negativo", fondo="C/D 0.8 OD, 0.4 OI", edad=60)
    assert "glaucoma_asimetrico" not in act
    assert "fondo_glaucomatoso" in act


def test_c05_14_muesca_inferior_concordante_activa():
    act = activas(
        pupilas="DPAR OD",
        fondo="Papila OD con muesca inferior, C/D 0.6 OD 0.5 OI",
        edad=58,
    )
    assert "glaucoma_asimetrico" in act
    assert "muesca" in act["glaucoma_asimetrico"]


def test_c05_15_base5_no_genera_alerta_h01():
    alertas = alertas_h01(**_BASE5)
    assert "glaucoma_asimetrico" not in alertas


# ============================================================================
# C06: fondo_glaucomatoso (#6)
# ============================================================================


def test_c06_01_cd_07_ao_no_urgente_gonioscopia():
    act = activas(fondo="C/D 0.7 AO")
    assert "fondo_glaucomatoso" in act
    assert "Hallazgo urgente:" not in act["fondo_glaucomatoso"]
    assert "gonioscopia" in act["fondo_glaucomatoso"]


def test_c06_02_cd_06_ao_fisiologico_no_activa():
    act = activas(fondo="C/D 0.6 AO")
    assert "fondo_glaucomatoso" not in act


def test_c06_03_cd_06_ao_con_discos_pequenos_activa():
    act = activas(fondo="C/D 0.6 AO, discos pequenos")
    assert "fondo_glaucomatoso" in act


def test_c06_04_excavacion_07_ao_en_macrodisco_no_activa():
    act = activas(fondo="Excavacion 0.7 AO en macrodisco")
    assert "fondo_glaucomatoso" not in act


def test_c06_05_excavacion_08_con_macula_normal_activa():
    act = activas(fondo="Excavacion 0.8 con macula normal")
    assert "fondo_glaucomatoso" in act


def test_c06_06_ep_03_od_07_oi_asimetria_activa():
    act = activas(fondo="E/P 0.3 OD y 0.7 OI")
    assert "fondo_glaucomatoso" in act
    assert "asimetria" in act["fondo_glaucomatoso"]


def test_c06_07_cd_od_02_oi_05_asimetria_activa():
    act = activas(fondo="C/D OD 0.2, OI 0.5")
    assert "fondo_glaucomatoso" in act


def test_c06_08_cd_03_04_asimetria_subumbral_no_activa():
    act = activas(fondo="C/D 0.3/0.4")
    assert "fondo_glaucomatoso" not in act


def test_c06_09_papila_con_excavacion_central_no_activa():
    act = activas(fondo="Papila con excavacion central")
    assert "fondo_glaucomatoso" not in act


def test_c06_10_papila_normal_excavacion_04_sin_muesca_ni_hemorragias_no_activa():
    act = activas(fondo="Papila normal, excavacion 0.4, sin muesca ni hemorragias")
    assert "fondo_glaucomatoso" not in act


def test_c06_11_hemorragia_de_disco_borde_inferior_activa():
    act = activas(fondo="Hemorragia de disco en borde inferior OD, c/d 0.4 AO")
    assert "fondo_glaucomatoso" in act
    assert "hemorragia" in act["fondo_glaucomatoso"]


def test_c06_12_hemorragias_astilla_peripapilares_oi_activa():
    act = activas(fondo="Hemorragias en astilla peripapilares OI")
    assert "fondo_glaucomatoso" in act


def test_c06_13_hemorragias_astilla_arcada_temporal_retiniana_no_papilar():
    act = activas(fondo="Hemorragias en astilla en arcada temporal, cruces AV")
    assert "fondo_glaucomatoso" not in act


def test_c06_14_cd_07_con_miopia_alta_advierte_factor_riesgo():
    act = activas(fondo="C/D 0.7 OD", rx_od={"esfera": -6.00, "cilindro": 0.00})
    assert "fondo_glaucomatoso" in act
    assert "miopia" in act["fondo_glaucomatoso"]


def test_c06_15_cd_07_no_apaga_deficit_visual_inexplicado_refractivo():
    act = activas(fondo="C/D 0.7 AO", rx_od={"av_cc": "20/50"})
    assert "fondo_glaucomatoso" in act
    assert "deficit_visual_inexplicado_refractivo" in act


def test_c06_16_excavacion_05_ao_sin_asimetria_no_activa():
    act = activas(fondo="Excavacion 0.5 AO sin asimetria")
    assert "fondo_glaucomatoso" not in act


def test_c06_17_excavacion_03_sin_adelgazamiento_no_activa():
    act = activas(fondo="Papilas con excavacion 0.3 AO, sin adelgazamiento del anillo")
    assert "fondo_glaucomatoso" not in act


def test_c06_18_cd_vertical_07_od_activa():
    act = activas(fondo="c/d vertical 0.7 OD")
    assert "fondo_glaucomatoso" in act


def test_c06_19_cd_07_ao_descartar_glaucoma_sospecha_activa():
    act = activas(fondo="C/D 0.7 AO, descartar glaucoma")
    assert "fondo_glaucomatoso" in act


def test_c06_20_anillo_neurorretiniano_adelgazado_inferior_activa():
    act = activas(fondo="Anillo neurorretiniano adelgazado inferior OD")
    assert "fondo_glaucomatoso" in act


# ============================================================================
# C07: Fusión isnt_violada_papila (#7) en fondo_glaucomatoso (#6)
# ============================================================================


def test_c07_01_no_se_cumple_regla_isnt_activa_fondo_glaucomatoso():
    act = activas(fondo="No se cumple regla ISNT en OD")
    assert "fondo_glaucomatoso" in act
    assert "regla ISNT" in act["fondo_glaucomatoso"]
    assert "isnt_violada_papila" not in act


def test_c07_02_regla_isnt_no_se_cumple_nivel_b_completar_estudio():
    act = activas(fondo="Regla ISNT: no se cumple en OD")
    assert "fondo_glaucomatoso" in act
    assert "completar estudio de glaucoma" in act["fondo_glaucomatoso"]


def test_c07_03_papila_no_respeta_regla_isnt_con_cd_fisiologico():
    act = activas(fondo="C/D 0.3 AO, papila OD no respeta la regla ISNT")
    assert "fondo_glaucomatoso" in act


def test_c07_04_regla_isnt_respetada_no_activa():
    act = activas(fondo="C/D 0.3 AO, regla ISNT respetada")
    assert "fondo_glaucomatoso" not in act
    assert "isnt_violada_papila" not in act


def test_c07_05_anillo_temporal_mas_grueso_que_nasal_fisiologico_no_activa():
    act = activas(fondo="Anillo temporal mas grueso que el nasal")
    assert "fondo_glaucomatoso" not in act
    assert "isnt_violada_papila" not in act


def test_c07_06_anillo_temporal_mas_grueso_que_inferior_activa():
    act = activas(fondo="Anillo temporal mas grueso que el inferior OD")
    assert "fondo_glaucomatoso" in act
    assert "regla ISNT" in act["fondo_glaucomatoso"]


def test_c07_07_muesca_inferotemporal_od_activa():
    act = activas(fondo="Muesca inferotemporal OD")
    assert "fondo_glaucomatoso" in act
    assert "muesca" in act["fondo_glaucomatoso"]
    assert "valoracion oftalmologica" in act["fondo_glaucomatoso"]


def test_c07_08_escotadura_inferior_con_hemorragia_astilla_ambos_detalles():
    act = activas(fondo="Escotadura inferior con hemorragia en astilla")
    assert "fondo_glaucomatoso" in act
    assert "escotadura" in act["fondo_glaucomatoso"]
    assert "hemorragia" in act["fondo_glaucomatoso"]


def test_c07_09_muesca_inferior_con_macula_normal_activa():
    act = activas(fondo="Muesca inferior con macula normal")
    assert "fondo_glaucomatoso" in act


def test_c07_10_sin_muescas_evidentes_no_activa():
    act = activas(fondo="Sin muescas evidentes")
    assert "fondo_glaucomatoso" not in act
    assert "isnt_violada_papila" not in act


def test_c07_11_no_se_evidencia_muesca_ni_hemorragia_no_activa():
    act = activas(fondo="No se evidencia muesca ni hemorragia")
    assert "fondo_glaucomatoso" not in act
    assert "isnt_violada_papila" not in act


def test_c07_12_ausencia_de_muesca_inferior_no_activa():
    act = activas(fondo="Ausencia de muesca inferior")
    assert "fondo_glaucomatoso" not in act
    assert "isnt_violada_papila" not in act


def test_c07_13_sin_violacion_de_la_regla_isnt_no_activa():
    act = activas(fondo="Sin violacion de la regla ISNT")
    assert "fondo_glaucomatoso" not in act
    assert "isnt_violada_papila" not in act


def test_c07_14_muesca_inferior_no_urgente_sin_diagnostico_inicial():
    act = activas(fondo="Muesca inferior OD")
    assert "fondo_glaucomatoso" in act
    assert "Hallazgo urgente:" not in act["fondo_glaucomatoso"]
    assert "inicial" not in act["fondo_glaucomatoso"]
    assert "sugestivo" not in act["fondo_glaucomatoso"]
    assert "priorizad" not in act["fondo_glaucomatoso"]


def test_c07_15_regla_isnt_violada_no_apaga_adulto_mayor_screening():
    act = activas(edad=68, rx_od={"av_cc": "20/50"}, fondo="Regla ISNT violada en OD")
    assert "adulto_mayor_screening" in act


# ============================================================================
# C08: fondo_macular_dmae (#8)
# ============================================================================


def test_c08_01_drusas_blandas_edad_72_programada_estadificacion():
    act = activas(edad=72, fondo="Drusas blandas maculares AO")
    assert "fondo_macular_dmae" in act
    assert "Hallazgo urgente:" not in act["fondo_macular_dmae"]
    assert "estadificacion" in act["fondo_macular_dmae"]


def test_c08_02_drusas_duras_pequenas_beckman_no_activa_dmae_apaga_screening():
    act = activas(
        edad=70,
        fondo="Drusas duras pequenas aisladas en polo posterior OD",
        rx_od={"av_cc": "20/50"},
    )
    assert "fondo_macular_dmae" not in act
    assert "adulto_mayor_screening" in act


def test_c08_03_drusas_papila_no_activa_dmae_no_apaga_deficit_visual():
    act = activas(
        edad=30,
        fondo="Drusas de papila OD",
        rx_od={"av_cc": "20/50"},
    )
    assert "fondo_macular_dmae" not in act
    assert "deficit_visual_inexplicado_refractivo" in act


def test_c08_04_membrana_neovascular_coroidea_urgente_1_dia_habil():
    act = activas(edad=68, fondo="Membrana neovascular coroidea en OD")
    assert "fondo_macular_dmae" in act
    assert "Hallazgo urgente:" in act["fondo_macular_dmae"]
    assert "1 dia habil" in act["fondo_macular_dmae"]
    assert "fondo_vascular_diabetico" not in act


def test_c08_05_hemorragia_subretiniana_macular_urgente():
    act = activas(edad=74, fondo="Hemorragia subretiniana macular OD")
    assert "fondo_macular_dmae" in act
    assert "Hallazgo urgente:" in act["fondo_macular_dmae"]


def test_c08_06_drusas_blandas_con_liquido_subretiniano_urgente():
    act = activas(edad=66, fondo="Drusas blandas OI con liquido subretiniano macular")
    assert "fondo_macular_dmae" in act
    assert "Hallazgo urgente:" in act["fondo_macular_dmae"]


def test_c08_07_liquido_subretiniano_joven_sin_drusas_va_a_fondo_macular_otros():
    act = activas(edad=35, fondo="Liquido subretiniano macular OD")
    assert "fondo_macular_dmae" not in act
    assert "fondo_macular_otros" in act


def test_c08_08_drusas_con_amsler_sin_inicio_no_inventa_agudeza():
    act = activas(edad=71, fondo="Drusas blandas maculares OD", amsler="Metamorfopsia OD")
    assert "fondo_macular_dmae" in act
    # C16-18 reabre esta aceptacion: ausencia de cronicidad no prueba cambio nuevo.
    assert "Hallazgo urgente:" not in act["fondo_macular_dmae"]
    assert "amsler_alterado" in act


def test_c08_09_drusas_con_metamorfopsia_motivo_urgente():
    act = activas(
        edad=70,
        fondo="Drusas medianas maculares AO",
        motivo="Veo torcidas las lineas rectas con OI desde hace una semana",
    )
    assert "fondo_macular_dmae" in act
    assert "Hallazgo urgente:" in act["fondo_macular_dmae"]


def test_c08_10_drusas_en_menor_50_nivel_c_atipico():
    act = activas(edad=44, fondo="Drusas blandas confluentes maculares AO")
    assert "fondo_macular_dmae" in act
    assert "Hallazgo urgente:" not in act["fondo_macular_dmae"]
    assert "menor de 50" in act["fondo_macular_dmae"]


def test_c08_11_degeneracion_macular_miopica_no_es_dmae_activa_miopia_magna():
    act = activas(
        edad=65,
        rx_od={"esfera": -9.00},
        fondo="Degeneracion macular miopica con atrofia peripapilar OD",
    )
    assert "fondo_macular_dmae" not in act
    assert "miopia_magna" in act


def test_c08_12_pigmento_periferico_sal_y_pimienta_no_es_dmae():
    act = activas(edad=60, fondo="Cambios pigmentarios perifericos en sal y pimienta")
    assert "fondo_macular_dmae" not in act


def test_c08_13_epiteliopatia_y_mev_eliminados_no_disparan():
    act = activas(edad=58, fondo="Epiteliopatia en polo posterior. MEV OD")
    assert "fondo_macular_dmae" not in act


def test_c08_14_atrofia_geografica_tardia_seca_no_urgente():
    act = activas(edad=78, fondo="Atrofia geografica OI")
    assert "fondo_macular_dmae" in act
    assert "Hallazgo urgente:" not in act["fondo_macular_dmae"]


def test_c08_15_dmae_tratada_inactiva_mantenimiento():
    act = activas(
        edad=76,
        fondo="DMAE humeda OD en tratamiento con antiangiogenicos, cicatriz disciforme",
    )
    assert "fondo_macular_dmae" in act
    assert "Hallazgo urgente:" not in act["fondo_macular_dmae"]
    assert "seguimiento retinologico establecido" in act["fondo_macular_dmae"]


def test_c08_16_sin_presencia_drusas_no_dispara():
    act = activas(fondo="Sin presencia de drusas maculares")
    assert "fondo_macular_dmae" not in act


def test_c08_17_membrana_neovascular_genera_alerta_h01_y_suprime_control_anual():
    alertas = alertas_h01(edad=70, fondo="Membrana neovascular coroidea en OD")
    assert "fondo_macular_dmae" in alertas

    req = _req(edad=70, fondo="Membrana neovascular coroidea en OD", seguimiento=_ANUAL)
    texto_llm = "Membrana neovascular macular en OD."
    resultado = _ensure_follow_up_last(texto_llm, _ANUAL, payload=req)
    assert "revision optometrica anual" not in resultado.lower()


# ============================================================================
# C09: fondo_macular_otros (#9)
# ============================================================================


def test_c09_01_agujero_macular_espesor_completo_preferente():
    act = activas(edad=66, fondo="Agujero macular de espesor completo OD")
    assert "fondo_macular_otros" in act
    assert "Hallazgo urgente:" not in act["fondo_macular_otros"]
    assert "preferente" in act["fondo_macular_otros"]


def test_c09_02_pseudoagujero_macular_programada_no_preferente():
    act = activas(fondo="Pseudoagujero macular OI")
    assert "fondo_macular_otros" in act
    assert "programada" in act["fondo_macular_otros"]
    assert "preferente" not in act["fondo_macular_otros"]


def test_c09_03_maculopatia_en_celofan_programada():
    act = activas(fondo="Maculopatia en celofan OD")
    assert "fondo_macular_otros" in act
    assert "programada" in act["fondo_macular_otros"]


def test_c09_04_maculopatia_miopica_programada_no_urgente():
    act = activas(
        edad=58,
        rx_od={"esfera": -12.00},
        fondo="Maculopatia miopica con atrofia coriorretiniana difusa OD",
    )
    assert "fondo_macular_otros" in act
    assert "Hallazgo urgente:" not in act["fondo_macular_otros"]
    assert "programada" in act["fondo_macular_otros"]


def test_c09_05_csc_joven_preferente():
    act = activas(edad=38, rx_od={"esfera": -1.00}, fondo="CSC OD")
    assert "fondo_macular_otros" in act
    assert "Hallazgo urgente:" not in act["fondo_macular_otros"]
    assert "preferente" in act["fondo_macular_otros"]


def test_c09_06_csc_edad_50_o_mas_deriva_a_dmae_urgente():
    act = activas(edad=58, fondo="CSC OD")
    assert "fondo_macular_otros" not in act
    assert "fondo_macular_dmae" in act
    assert "Hallazgo urgente:" in act["fondo_macular_dmae"]


def test_c09_07_liquido_subretiniano_miopia_alta_deriva_a_dmae_urgente():
    act = activas(
        edad=35,
        rx_od={"esfera": -9.00, "cilindro": 0.00},
        fondo="Liquido subretiniano macular OD",
    )
    assert "fondo_macular_otros" not in act
    assert "fondo_macular_dmae" in act
    assert "Hallazgo urgente:" in act["fondo_macular_dmae"]


def test_c09_08_desprendimiento_neurosensorial_macular_no_es_periferico():
    act = activas(edad=42, fondo="Desprendimiento neurosensorial seroso macular OD")
    assert "fondo_macular_otros" in act
    assert "preferente" in act["fondo_macular_otros"]
    assert "fondo_periferico_riesgo" not in act


def test_c09_09_macula_con_edema_preferente():
    act = activas(fondo="Macula con edema OD")
    assert "fondo_macular_otros" in act
    assert "preferente" in act["fondo_macular_otros"]


def test_c09_10_edema_macular_diabetico_activa_ambas_reglas():
    act = activas(fondo="Edema macular diabetico clinicamente significativo OD")
    assert "fondo_macular_otros" in act
    assert "fondo_vascular_diabetico" in act


def test_c09_11_edema_macular_por_ovcr_suprime_otros_activa_oclusion_urgente():
    act = activas(fondo="Edema macular por OVCR OD")
    assert "fondo_macular_otros" not in act
    assert "fondo_oclusion_vascular_urgente" in act
    assert "Hallazgo urgente:" in act["fondo_oclusion_vascular_urgente"]


def test_c09_12_sin_evidencia_edema_macular_no_activa():
    act = activas(fondo="Sin evidencia de edema macular bilateral")
    assert "fondo_macular_otros" not in act


def test_c09_13_engrosamiento_macular_descartar_edema_preferente():
    act = activas(fondo="Engrosamiento macular OD, descartar edema macular")
    assert "fondo_macular_otros" in act
    assert "preferente" in act["fondo_macular_otros"]


def test_c09_14_fondo_tigroide_cono_miopico_no_es_maculopatia():
    act = activas(
        rx_od={"esfera": -7.00},
        rx_oi={"esfera": -7.00},
        fondo="Fondo tigroide, cono miopico temporal AO",
    )
    assert "fondo_macular_otros" not in act


def test_c09_15_desgarro_epr_macular_no_activa_periferico():
    act = activas(edad=74, fondo="Desgarro del epitelio pigmentario OD")
    assert "fondo_macular_otros" in act
    assert "fondo_periferico_riesgo" not in act


def test_c09_16_membrana_epirretiniana_programada_no_urgente():
    act = activas(fondo="Membrana epirretiniana OD")
    assert "fondo_macular_otros" in act
    assert "Hallazgo urgente:" not in act["fondo_macular_otros"]
    assert "programada" in act["fondo_macular_otros"]


def test_c09_17_sin_evidencia_edema_macular_no_apaga_deficit_visual_inexplicado():
    act = activas(
        edad=30,
        rx_od={"esfera": -1.00, "av_cc": "20/50", "av_sc": "20/200"},
        fondo="Sin evidencia de edema macular bilateral",
    )
    assert "deficit_visual_inexplicado_refractivo" in act


# ============================================================================
# Correlación #10: fondo_hipertensivo (C10-01 .. C10-28)
# ============================================================================


def test_c10_01_cruces_y_tortuosidad_no_activa():
    act = activas(fondo="Cruces arteriovenosos y tortuosidad vascular.")
    assert "fondo_hipertensivo" not in act


def test_c10_02_cruces_normales_no_activa():
    act = activas(fondo="Cruces arteriovenosos normales.")
    assert "fondo_hipertensivo" not in act


def test_c10_03_cruces_conservados_sin_compresion_no_activa():
    act = activas(fondo="Cruces arteriovenosos conservados, sin compresion.")
    assert "fondo_hipertensivo" not in act


def test_c10_04_gunn_y_estrechamiento_focal_aviso_ambos_signos():
    act = activas(fondo="Signo de Gunn positivo con estrechamiento arteriolar focal.")
    assert "fondo_hipertensivo" in act
    texto = act["fondo_hipertensivo"]
    assert "signo de Gunn" in texto
    assert "estrechamiento arteriolar focal" in texto
    assert "Hallazgo urgente:" not in texto


def test_c10_05_sin_signos_retinopatia_hipertensiva_no_activa():
    act = activas(fondo="Sin signos de retinopatia hipertensiva.")
    assert "fondo_hipertensivo" not in act


def test_c10_06_algodonoso_aislado_no_activa():
    act = activas(fondo="Exudado algodonoso aislado OD.")
    assert "fondo_hipertensivo" not in act


def test_c10_07_hemorragia_por_ovcr_mantiene_c03_no_duplica_c10():
    act = activas(fondo="Hemorragia en llama OD por OVCR.")
    assert "fondo_oclusion_vascular_urgente" in act
    assert "fondo_hipertensivo" not in act


def test_c10_08_antecedente_resuelto_fondo_sin_lesiones_no_activa():
    act = activas(fondo="Antecedente de retinopatia hipertensiva, resuelta; fondo actual sin lesiones.")
    assert "fondo_hipertensivo" not in act


def test_c10_09_hemorragias_y_edema_papila_sin_pa_mantiene_alarma_c04_no_inventa_pa():
    act = activas(
        fondo="Retinopatia hipertensiva con hemorragias en llama bilaterales y edema de papila.",
        motivo="Vision borrosa de inicio subito y cefalea intensa.",
    )
    assert "papila_patologica" in act
    if "fondo_hipertensivo" in act:
        assert "Hallazgo urgente:" not in act["fondo_hipertensivo"]


def test_c10_10_hilo_cobre_arteriolar_singular_activa():
    act = activas(fondo="Hilo de cobre arteriolar bilateral.")
    assert "fondo_hipertensivo" in act
    assert "hilo de cobre arteriolar bilateral" in act["fondo_hipertensivo"]


def test_c10_11_cruces_av_presentes_sin_alteraciones_no_activa():
    act = activas(fondo="Cruces AV presentes, sin alteraciones vasculares.")
    assert "fondo_hipertensivo" not in act


def test_c10_12_od_cruces_normales_oi_estrechamiento_solo_oi():
    act = activas(fondo="OD: cruces AV sin alteraciones. OI: estrechamiento arteriolar.")
    assert "fondo_hipertensivo" in act
    texto = act["fondo_hipertensivo"]
    assert "OI" in texto
    assert "OD" not in texto


def test_c10_13_fondo_null_no_activa():
    act = activas(fondo=None)
    assert "fondo_hipertensivo" not in act


def test_c10_14_hemorragias_y_sintomas_agudos_sin_pa_no_urgente():
    act = activas(
        fondo="Hemorragia en llama bilateral con exudados algodonosos.",
        motivo="Cefalea intensa nueva y vision borrosa desde esta manana.",
    )
    if "fondo_hipertensivo" in act:
        assert "Hallazgo urgente:" not in act["fondo_hipertensivo"]


def test_c10_15_retinopatia_hipertensiva_descartada_no_activa():
    act = activas(fondo="Retinopatia hipertensiva descartada.")
    assert "fondo_hipertensivo" not in act


def test_c10_16_adulto_pa_210_125_con_hemorragias_urgente_mismo_dia_h01():
    act = activas(
        edad=55,
        fondo="Estrechamiento arteriolar y hemorragias en llama AO.",
        motivo="PA medida hoy 210/125 mmHg; cefalea intensa y vision borrosa de inicio hoy.",
    )
    assert "fondo_hipertensivo" in act
    texto = act["fondo_hipertensivo"]
    assert "Hallazgo urgente:" in texto
    assert "210/125 mmHg" in texto
    assert "mismo dia" in texto
    assert "fondo_hipertensivo" in alertas_h01(
        edad=55,
        fondo="Estrechamiento arteriolar y hemorragias en llama AO.",
        motivo="PA medida hoy 210/125 mmHg; cefalea intensa y vision borrosa de inicio hoy.",
    )


def test_c10_17_cruces_av_con_pinzamiento_activa():
    act = activas(fondo="Cruces AV con pinzamiento venoso en OD.")
    assert "fondo_hipertensivo" in act
    assert "pinzamiento" in act["fondo_hipertensivo"]


def test_c10_18_cruces_av_sin_pinzamiento_no_activa():
    act = activas(fondo="Cruces AV sin pinzamiento en OD; macula sin lesiones.")
    assert "fondo_hipertensivo" not in act


def test_c10_19_relacion_av_disminuida_activa():
    act = activas(fondo="Relacion A/V disminuida bilateral.")
    assert "fondo_hipertensivo" in act
    assert "relacion arteria/vena disminuida bilateral" in act["fondo_hipertensivo"]


def test_c10_20_salus_positivo_en_cruce_activa():
    act = activas(fondo="Salus positivo en cruce arteriovenoso OD.")
    assert "fondo_hipertensivo" in act
    assert "signo de Salus" in act["fondo_hipertensivo"]


def test_c10_21_adulto_190_100_con_hemorragia_urgente_mismo_dia_h01():
    act = activas(
        edad=60,
        motivo="PA 190/100 mmHg",
        fondo="Hemorragias en llama en polo posterior.",
    )
    assert "fondo_hipertensivo" in act
    assert "Hallazgo urgente:" in act["fondo_hipertensivo"]
    assert "190/100 mmHg" in act["fondo_hipertensivo"]
    assert "fondo_hipertensivo" in alertas_h01(
        edad=60,
        motivo="PA 190/100 mmHg",
        fondo="Hemorragias en llama en polo posterior.",
    )


def test_c10_22_adulto_170_125_con_hemorragia_urgente_mismo_dia_h01():
    act = activas(
        edad=50,
        motivo="PA 170/125 mmHg",
        fondo="Hemorragias retinianas OD.",
    )
    assert "fondo_hipertensivo" in act
    assert "Hallazgo urgente:" in act["fondo_hipertensivo"]
    assert "170/125 mmHg" in act["fondo_hipertensivo"]
    assert "fondo_hipertensivo" in alertas_h01(
        edad=50,
        motivo="PA 170/125 mmHg",
        fondo="Hemorragias retinianas OD.",
    )


def test_c10_23_pa_historica_hace_cinco_anos_no_urgente():
    act = activas(
        edad=55,
        motivo="Antecedente de PA 190/120 hace 5 anos",
        fondo="Hemorragias retinianas.",
    )
    if "fondo_hipertensivo" in act:
        assert "Hallazgo urgente:" not in act["fondo_hipertensivo"]


def test_c10_24_pa_familiar_no_urgente():
    act = activas(
        edad=40,
        motivo="Padre con PA 200/130",
        fondo="Hemorragias retinianas.",
    )
    if "fondo_hipertensivo" in act:
        assert "Hallazgo urgente:" not in act["fondo_hipertensivo"]


def test_c10_25_pa_negada_no_urgente():
    act = activas(
        edad=50,
        motivo="Niega PA 180/120",
        fondo="Hemorragias retinianas.",
    )
    if "fondo_hipertensivo" in act:
        assert "Hallazgo urgente:" not in act["fondo_hipertensivo"]


def test_c10_26_menor_de_edad_no_aplica_umbral_adulto_ng136():
    act = activas(
        edad=14,
        motivo="PA 180/120 mmHg",
        fondo="Hemorragias retinianas.",
    )
    if "fondo_hipertensivo" in act:
        assert "Hallazgo urgente:" not in act["fondo_hipertensivo"]


def test_c10_27_cifras_tensionales_contradictorias_no_urgente():
    act = activas(
        edad=45,
        motivo="PA hoy 210/125 pero en segundo registro 120/80",
        fondo="Hemorragias retinianas.",
    )
    if "fondo_hipertensivo" in act:
        assert "Hallazgo urgente:" not in act["fondo_hipertensivo"]


def test_c10_28_signo_unilateral_con_contralateral_negado_y_descarte_vs_sospecha():
    act = activas(
        fondo="OD signo de Gunn presente; OI sin alteraciones vasculares ni cruces patologicos.",
    )
    assert "fondo_hipertensivo" in act
    texto = act["fondo_hipertensivo"]
    assert "signo de Gunn en OD" in texto
    assert "OI" not in texto


# ============================================================================
# Correlación #11: fondo_vascular_diabetico (C11-01 .. C11-31)
# ============================================================================


def test_c11_01_microaneurismas_y_exudados_duros_sin_asumir_dm():
    act = activas(fondo="Microaneurismas y exudados duros.")
    assert "fondo_vascular_diabetico" in act
    texto = act["fondo_vascular_diabetico"]
    assert "Hallazgo urgente:" not in texto
    assert "microaneurismas y exudados duros" in texto
    assert "control glucemico con su medico" not in texto
    assert "glucemia y la presion arterial" in texto


def test_c11_02_ambos_negados_no_activa():
    act = activas(fondo="Sin microaneurismas ni exudados duros.")
    assert "fondo_vascular_diabetico" not in act


def test_c11_03_no_padece_dm_no_asume_tratamiento():
    act = activas(fondo="Microaneurismas retinianos OD. No padece diabetes.")
    assert "fondo_vascular_diabetico" in act
    texto = act["fondo_vascular_diabetico"]
    assert "Hallazgo urgente:" not in texto
    assert "microaneurismas retinianos en OD" in texto
    assert "control glucemico con su medico" not in texto
    assert "glucemia y la presion arterial" in texto


def test_c11_04_exudado_conjuntival_no_lesion_retiniana():
    act = activas(fondo="Exudado conjuntival; retina normal.")
    assert "fondo_vascular_diabetico" not in act


def test_c11_05_hemorragia_retiniana_unilateral():
    act = activas(fondo="Hemorragia retiniana OD.")
    assert "fondo_vascular_diabetico" in act
    texto = act["fondo_vascular_diabetico"]
    assert "Hallazgo urgente:" not in texto
    assert "hemorragia retiniana en OD" in texto


def test_c11_06_microhemorragias_intrarretinianas_puntiformes():
    act = activas(fondo="Microhemorragias intrarretinianas puntiformes OD.")
    assert "fondo_vascular_diabetico" in act
    texto = act["fondo_vascular_diabetico"]
    assert "microhemorragias intrarretinianas puntiformes en OD" in texto
    assert "Hallazgo urgente:" not in texto


def test_c11_07_neovasos_corneales_no_activa_fondo():
    act = activas(fondo="Neovasos corneales por uso de lentes de contacto; retina normal.")
    assert "fondo_vascular_diabetico" not in act


def test_c11_08_neovascularizacion_coroidea_enruta_dmae_h01():
    act = activas(fondo="Neovascularizacion coroidea macular OD.")
    assert "fondo_vascular_diabetico" not in act
    assert "fondo_macular_dmae" in act
    assert "fondo_macular_dmae" in alertas_h01(fondo="Neovascularizacion coroidea macular OD.")


def test_c11_09_nvd_activa_urgente_h01():
    act = activas(fondo="NVD OD, neovascularizacion papilar activa.")
    assert "fondo_vascular_diabetico" in act
    texto = act["fondo_vascular_diabetico"]
    assert "Hallazgo urgente:" in texto
    assert "neovascularizacion papilar en OD" in texto
    assert "fondo_vascular_diabetico" in alertas_h01(fondo="NVD OD, neovascularizacion papilar activa.")


def test_c11_10_rubeosis_iris_con_sintomas_agudos_urgente_mismo_dia_h01():
    act = activas(
        fondo="Rubeosis iridis OD.",
        anexos="Neovasos en iris OD.",
        motivo="Dolor ocular intenso y vision borrosa desde hoy.",
    )
    assert "fondo_vascular_diabetico" in act
    texto = act["fondo_vascular_diabetico"]
    assert "Hallazgo urgente:" in texto
    assert "rubeosis de iris con sintomas agudos" in texto
    assert "mismo dia" in texto
    assert "fondo_vascular_diabetico" in alertas_h01(
        fondo="Rubeosis iridis OD.",
        anexos="Neovasos en iris OD.",
        motivo="Dolor ocular intenso y vision borrosa desde hoy.",
    )


def test_c11_11_edema_macular_diabetico_coexiste_con_maculopatia():
    act = activas(fondo="Edema macular diabetico OD.")
    assert "fondo_vascular_diabetico" in act
    assert "fondo_macular_otros" in act
    texto = act["fondo_vascular_diabetico"]
    assert "Hallazgo urgente:" not in texto
    assert "edema macular diabetico en OD" in texto


def test_c11_12_edema_macular_diabetico_sin_algodonosos_negacion_clausula():
    act = activas(fondo="Edema macular diabetico OD, sin exudados algodonosos.")
    assert "fondo_vascular_diabetico" in act
    texto = act["fondo_vascular_diabetico"]
    assert "edema macular diabetico en OD" in texto
    assert "algodonoso" not in texto


def test_c11_13_edema_macular_diabetico_con_algodonosos_ambas_lesiones():
    act = activas(fondo="Edema macular diabetico y exudados algodonosos OD.")
    assert "fondo_vascular_diabetico" in act
    texto = act["fondo_vascular_diabetico"]
    assert "edema macular diabetico y exudados algodonosos en OD" in texto


def test_c11_14_hemorragia_retiniana_sin_algodonosos_no_veto_global():
    act = activas(fondo="Hemorragia retiniana OD, sin exudados algodonosos.")
    assert "fondo_vascular_diabetico" in act
    texto = act["fondo_vascular_diabetico"]
    assert "hemorragia retiniana en OD" in texto
    assert "algodonoso" not in texto


def test_c11_15_algodonoso_aislado_aviso_neutral_sin_fondo_hipertensivo():
    act = activas(fondo="Exudado algodonoso aislado OD.")
    assert "fondo_vascular_diabetico" in act
    assert "fondo_hipertensivo" not in act
    texto = act["fondo_vascular_diabetico"]
    assert "Hallazgo urgente:" not in texto
    assert "exudados algodonosos en OD" in texto


def test_c11_16_rd_tratada_sin_actividad_no_activa():
    act = activas(fondo="Antecedente de retinopatia diabetica tratada, sin lesiones activas.")
    assert "fondo_vascular_diabetico" not in act


def test_c11_17_descartar_rd_retina_sin_lesiones_no_activa():
    act = activas(fondo="Descartar retinopatia diabetica; retina sin lesiones.")
    assert "fondo_vascular_diabetico" not in act


def test_c11_18_irma_y_arrosariamiento_venoso():
    act = activas(fondo="IRMA en OD y arrosariamiento venoso.")
    assert "fondo_vascular_diabetico" in act
    texto = act["fondo_vascular_diabetico"]
    assert "Hallazgo urgente:" not in texto
    assert "IRMA y arrosariamiento venoso" in texto


def test_c11_19_hemorragia_por_ovcr_no_duplica_en_diabetico():
    act = activas(fondo="Hemorragias retinianas por OVCR OD.")
    assert "fondo_vascular_diabetico" not in act
    assert "fondo_oclusion_vascular_urgente" in act
    assert "Hallazgo urgente:" in act["fondo_oclusion_vascular_urgente"]


def test_c11_20_neovascularizacion_retiniana_y_hemorragia_vitrea_ambas_urgentes():
    act = activas(fondo="Neovascularizacion retiniana activa y hemorragia vitrea OD.")
    assert "fondo_vascular_diabetico" in act
    assert "fondo_periferico_riesgo" in act
    assert "Hallazgo urgente:" in act["fondo_vascular_diabetico"]
    assert "Hallazgo urgente:" in act["fondo_periferico_riesgo"]
    assert alertas_h01(fondo="Neovascularizacion retiniana activa y hemorragia vitrea OD.") == {
        "fondo_periferico_riesgo",
        "fondo_vascular_diabetico",
    }


def test_c11_21_dm_conocida_sin_fondo_no_activa():
    act = activas(
        fondo=None,
        motivo="Paciente con diabetes mellitus conocida, consulta para graduacion.",
    )
    assert "fondo_vascular_diabetico" not in act


def test_c11_22_exudados_maculares_av_20_20():
    act = activas(
        fondo="Exudados duros maculares OD.",
        rx_od={"av_cc": "20/20"},
    )
    assert "fondo_vascular_diabetico" in act
    assert "exudados duros maculares en OD" in act["fondo_vascular_diabetico"]


def test_c11_23_exudados_maculares_av_20_100():
    act = activas(
        fondo="Exudados duros maculares OD.",
        rx_od={"av_cc": "20/100"},
    )
    assert "fondo_vascular_diabetico" in act
    assert "exudados duros maculares en OD" in act["fondo_vascular_diabetico"]


def test_c11_24_microaneurismas_con_dm2_en_motivo_contextualiza_glucemia():
    act = activas(
        fondo="OD: microaneurismas. OI: sin lesiones.",
        motivo="Diabetes mellitus tipo 2 en tratamiento.",
    )
    assert "fondo_vascular_diabetico" in act
    texto = act["fondo_vascular_diabetico"]
    assert "microaneurismas en OD" in texto
    assert "control glucemico" in texto


def test_c11_25_neovasos_coroideos_maculares_enruta_dmae():
    act = activas(fondo="Neovasos coroideos maculares OD.")
    assert "fondo_vascular_diabetico" not in act
    assert "fondo_macular_dmae" in act
    assert "fondo_macular_dmae" in alertas_h01(fondo="Neovasos coroideos maculares OD.")


def test_c11_26_exudados_oi_independiente_de_ovcr_od():
    act = activas(fondo="Exudados duros retinianos OI. OD: hemorragia por OVCR.")
    assert "fondo_vascular_diabetico" in act
    assert "exudados duros retinianos en OI" in act["fondo_vascular_diabetico"]
    assert "fondo_oclusion_vascular_urgente" in act


def test_c11_27_emcs_con_algodonosos_no_veto_global():
    act = activas(fondo="Edema macular clinicamente significativo con exudados algodonosos.")
    assert "fondo_vascular_diabetico" in act
    texto = act["fondo_vascular_diabetico"]
    assert "edema macular clinicamente significativo" in texto
    assert "exudados algodonosos" in texto


def test_c11_28_nve_retinianos_activos_urgente_h01():
    act = activas(fondo="NVE retinianos activos OD.")
    assert "fondo_vascular_diabetico" in act
    texto = act["fondo_vascular_diabetico"]
    assert "Hallazgo urgente:" in texto
    assert "neovascularizacion retiniana en OD" in texto
    assert "fondo_vascular_diabetico" in alertas_h01(fondo="NVE retinianos activos OD.")


def test_c11_29_neovascularizacion_negada_no_activa():
    act = activas(fondo="Sin neovascularizacion papilar; retina sin lesiones.")
    assert "fondo_vascular_diabetico" not in act


def test_c11_30_neovasos_retinianos_antiguos_inactivos_no_activa():
    act = activas(fondo="Neovasos retinianos antiguos tratados, actualmente inactivos.")
    assert "fondo_vascular_diabetico" not in act


def test_c11_31_nevus_convexo_no_dispara_nve():
    act = activas(fondo="Nevus coroideo convexo estable.")
    assert "fondo_vascular_diabetico" not in act


# ============================================================================
# Fase 5: Cierre y Normalización Diagnóstica (T5 & T12)
# ============================================================================

from tests.test_correlaciones_golden import GOLDEN

_T5_PROHIBITED_RE = re.compile(
    r"\b(?:compatible\s+con|confirma\w*|patron\s+sugestivo\s+de|patron\s+compatible|diagnostico\s+de)\b",
    re.IGNORECASE,
)

_T12_URGENCY_WORDS_RE = re.compile(
    r"\b(?:urgent\w*|inmediat\w*|prioritari\w*|\bgrave\b|emergencia\w*)\b",
    re.IGNORECASE,
)


@pytest.mark.parametrize("caso_id,req,esperado", GOLDEN, ids=[c[0] for c in GOLDEN])
def test_t5_ningun_texto_contiene_etiquetas_diagnosticas_prohibidas(caso_id, req, esperado):
    """T5: Ningun texto esperado ni texto emitido debe contener etiquetas diagnosticas prohibidas.
    
    Prohibidas segun regla de oro CDS: 'compatible con', 'confirma', 'patron sugestivo de',
    'patron compatible', 'diagnostico de'.
    """
    match_esp = _T5_PROHIBITED_RE.search(esperado)
    assert match_esp is None, f"[{caso_id}] Texto esperado contiene etiqueta diagnostica prohibida: {match_esp.group(0)!r}"

    act = dict(evaluar_correlaciones_con_nombres(req))
    for nombre, texto in act.items():
        match_act = _T5_PROHIBITED_RE.search(texto)
        assert match_act is None, f"[{caso_id}] Correlacion '{nombre}' emitida contiene etiqueta diagnostica prohibida: {match_act.group(0)!r}"


@pytest.mark.parametrize("caso_id,req,esperado", GOLDEN, ids=[c[0] for c in GOLDEN])
def test_t12_textos_no_urgentes_no_contienen_palabras_de_urgencia(caso_id, req, esperado):
    """T12: Todo texto emitido que NO comience con 'Hallazgo urgente:' no debe contener
    palabras de urgencia (urgent*, inmediat*, prioritari*, grave, emergencia)."""
    if "hallazgo urgente" not in esperado.lower():
        match_esp = _T12_URGENCY_WORDS_RE.search(esperado)
        assert match_esp is None, f"[{caso_id}] Texto esperado no urgente contiene palabra de urgencia: {match_esp.group(0)!r}"

    act = dict(evaluar_correlaciones_con_nombres(req))
    for nombre, texto in act.items():
        if "hallazgo urgente" not in texto.lower():
            match_act = _T12_URGENCY_WORDS_RE.search(texto)
            assert match_act is None, f"[{caso_id}] Correlacion no urgente '{nombre}' contiene palabra de urgencia: {match_act.group(0)!r}"

