"""Aceptacion #19 derivada de las 50 observaciones de la orden."""
import json
from pathlib import Path

import pytest

from app.inference import _ensure_emergency_preserved
from app.prompt_builder import build_user_prompt
from tests.test_auditoria_correlaciones import _req, activas, alertas_h01

ID = "anexos_patologicos"
CASOS = {c["id"]: c for c in json.loads(
    (Path(__file__).parents[1] / "auditoria/2026-09-21/casos.json").read_text(encoding="utf-8"))
    if c["id"].startswith("C19-")}
INACTIVAS = {11, 12, 20, 30, 34, 35, 36, 38, 40, 46, 48, 50}
URGENTES = {14, 15, 22, 29, 33, 41, 42, 43, 44}
ESPERADAS = {
    1: "blefaritis anterior OD", 2: "meibomitis en ambos ojos", 3: "disfuncion glandular lagrimal",
    4: "disfuncion de glandulas de meibomio en ambos ojos", 5: "chalazion palpebral superior OD",
    6: "chalazion inferior OI", 7: "orzuelo externo OD", 8: "orzuelo palpebral OD", 9: "pterigion nasal OD",
    10: "carnosidad palpebral superior OD", 13: "hiperemia del borde palpebral", 14: "inyeccion ciliar OD",
    15: "queratitis OD", 16: "queratopatia punteada superficial en ambos ojos", 17: "erosion cutanea palpebral OD",
    18: "defecto epitelial conjuntival nasal", 19: "abrasion corneal OD", 21: "nubecula corneal OI",
    22: "edema corneal OD", 23: "queratopatia bullosa OD", 24: "distiquiasis OI", 25: "triquiasis con roce corneal OD",
    26: "ectropion inferior OI", 27: "entropion inferior OD", 28: "ptosis palpebral OD",
    29: "proptosis OD de inicio reciente", 31: "lagoftalmos con exposicion corneal OD",
    32: "madarosis sobre lesion palpebral ulcerada recurrente OD", 33: "dacriocistitis OD",
    37: "plantea, sin establecer, pterigion", 39: "hiperemia conjuntival OI", 41: "ulcera corneal OD",
    42: "infiltrado corneal central OD", 43: "cuerpo extrano corneal OD", 44: "hipopion OD",
    45: "inyeccion ciliar OD", 47: "blefaritis OD", 49: "hiperemia conjuntival leve",
}


@pytest.mark.parametrize("numero", range(1, 51))
def test_c19_historico(numero):
    entrada = CASOS[f"C19-{numero:02d}"]["entrada"]
    salida = activas(**entrada)
    if numero in INACTIVAS:
        assert ID not in salida
        return
    texto = salida[ID]
    assert ESPERADAS[numero] in texto
    assert (ID in alertas_h01(**entrada)) == (numero in URGENTES)
    if numero in URGENTES:
        assert texto.startswith("Hallazgo urgente:") and "el mismo dia" in texto
    elif numero != 37:
        assert "amerita evaluacion oftalmologica" in texto
    if numero in {3, 10, 13, 17, 18, 29}:
        prohibido = {3: "meibomio", 10: "pterigion", 13: "hiperemia conjuntival",
                     17: "corneal", 18: "corneal", 29: "ptosis palpebral"}[numero]
        assert prohibido not in texto
    if numero == 42:
        assert "defecto epitelial" in texto
    if numero == 14:
        assert "dolor profundo" in texto and "dolor ocular intenso" not in texto
    for prohibido in ("cierre angular", "infeccion confirmada", "tumor", "antibiotico", "corticoide"):
        assert prohibido not in texto


def test_c19_cobertura_completa():
    assert len(CASOS) == 50
    assert INACTIVAS | set(ESPERADAS) == set(range(1, 51))


@pytest.mark.parametrize("texto", ["Hiperemia", "Erosion", "Defecto epitelial", "Carnosidad", "Disfuncion glandular"])
def test_c19_no_completa_anatomia_de_termino_generico(texto):
    salida = activas(anexos=texto)[ID]
    assert texto.lower() in salida
    assert all(p not in salida for p in ("conjuntival", "corneal", "meibomio", "pterigion"))


def test_c19_proptosis_no_es_ptosis():
    salida = activas(anexos="Proptosis OD reciente")
    assert "proptosis OD" in salida[ID] and "ptosis palpebral" not in salida[ID]
    assert "horner_o_tercer_par_sospecha" not in salida


def test_c19_negacion_independiente_por_ojo():
    texto = activas(anexos="OD: sin queratitis. OI: ulcera corneal") [ID]
    assert "ulcera corneal OI" in texto and "OD" not in texto
    assert ID in alertas_h01(anexos="OD: sin queratitis. OI: ulcera corneal")


@pytest.mark.parametrize("motivo", ["Sin dolor ni halos ni nausea desde hoy", "Dolor ocular cronico y halos hace 5 anos",
                                     "Halos aislados desde hoy", "Revision de rutina"])
def test_c19_sintomas_aislados_negados_o_antiguos_no_generan_alarma(motivo):
    assert ID not in alertas_h01(motivo=motivo)


def test_c19_dolor_y_halos_recientes_generan_triaje_sin_asumir_causa():
    entrada = dict(motivo="Dolor ocular intenso, halos y nausea desde hoy")
    assert ID in alertas_h01(**entrada)
    salida = _ensure_emergency_preserved("Se recomienda revision anual.", _req(**entrada))
    assert "el mismo dia" in salida and "revision anual" not in salida


def test_c19_dolor_del_otro_ojo_tiene_triaje_propio_sin_escalar_lesion_od():
    entrada = dict(anexos="Queratitis OD", motivo="Dolor y fotofobia OI desde hoy")
    texto = activas(**entrada)[ID]
    urgente, lesion = texto.split("En anexos oculares", 1)
    assert ID in alertas_h01(**entrada) and "OI" in urgente and "OD" not in urgente
    assert "queratitis OD" in lesion and "urgente" not in lesion


def test_c19_defecto_negado_no_completa_combinacion_infiltrado():
    assert ID not in alertas_h01(anexos="Infiltrado corneal OD, sin defecto epitelial")


def test_c19_certeza_no_es_confirmacion():
    salida = activas(anexos="Posible ulcera corneal OD") [ID]
    assert "plantea, sin establecer" in salida and not salida.startswith("Hallazgo urgente")


def test_c19_fusion_por_ojo_conserva_ptosis_independiente_actual():
    entrada = dict(anexos="Ptosis OD. Ptosis OI", pupilas="Reflejo fotomotor, consensual, acomodativo: Midriasis OD nueva")
    salida = activas(**entrada)
    assert "horner_o_tercer_par_sospecha" in salida
    assert "ptosis OI" in salida[ID] and "ptosis OD" not in salida[ID]


def test_c19_antecedente_contralateral_se_conserva_en_prompt_como_contexto():
    entrada = CASOS["C19-46"]["entrada"]
    texto = build_user_prompt(_req(**entrada)).lower()
    assert "ptosis congenita estable oi" in texto


def test_c19_sintomas_en_anexos_tambien_permiten_triaje_con_ojo():
    salida = activas(anexos="Dolor ocular y halos OD desde hoy")[ID]
    assert salida.startswith("Hallazgo urgente") and "OD" in salida


def test_c19_sintomas_agudos_de_ojos_distintos_no_se_combinan():
    assert ID not in alertas_h01(motivo="Dolor ocular OD desde hoy. Halos OI desde hoy")


def test_c19_defecto_conjuntival_no_se_convierte_en_soporte_corneal():
    assert ID not in alertas_h01(anexos="Infiltrado corneal OD y defecto epitelial conjuntival OD")


def test_c19_sintomas_agudos_se_evalúan_aunque_la_lesion_sea_incierta():
    entrada = dict(anexos="Posible queratitis OD", motivo="Dolor ocular y fotofobia OD desde hoy")
    salida = activas(**entrada)[ID]
    assert ID in alertas_h01(**entrada) and salida.startswith("Hallazgo urgente:")
    assert "plantea, sin establecer" in salida
