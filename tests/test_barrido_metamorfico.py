"""Barrido metamorfico (auditoria independiente 2026-09-29): propiedades que deben cumplirse sin importar
el ojo, la coordinacion gramatical o el sujeto, mas los contraejemplos concretos que las revelaron.

Propiedades generales sobre los 1356 casos historicos:
  * espejo OD<->OI: mismas reglas, mismos hechos (con OD/OI intercambiados) y misma alerta H01.
"""
import copy
import json
import re
from pathlib import Path

import pytest

from tests.test_auditoria_correlaciones import activas, alertas_h01

_CASOS = json.loads((Path(__file__).parents[1] / "auditoria/2026-09-21/casos.json").read_text(encoding="utf-8"))
_TEXTOS = ("anexos", "fondo", "pupilas", "motilidad", "campos", "amsler", "motivo", "seguimiento")
_TOK = re.compile(r"\b(OD|OI|od|oi|Od|Oi|ojo derecho|ojo izquierdo|Ojo derecho|Ojo izquierdo|derecho|izquierdo)\b")
_MAPA = {"OD": "OI", "OI": "OD", "od": "oi", "oi": "od", "Od": "Oi", "Oi": "Od",
         "ojo derecho": "ojo izquierdo", "ojo izquierdo": "ojo derecho", "Ojo derecho": "Ojo izquierdo",
         "Ojo izquierdo": "Ojo derecho", "derecho": "izquierdo", "izquierdo": "derecho"}


def _swap(texto: str) -> str:
    return _TOK.sub(lambda m: _MAPA[m.group(1)], texto)


def _palabras(texto: str) -> list[str]:
    return sorted(re.sub(r"[.,;:()]", " ", texto).split())


def _espejo(entrada: dict) -> dict:
    e = copy.deepcopy(entrada)
    for a, b in (("rx_od", "rx_oi"), ("akr_od", "akr_oi")):
        va, vb = entrada.get(a), entrada.get(b)
        e.pop(a, None)
        e.pop(b, None)
        if va is not None:
            e[b] = va
        if vb is not None:
            e[a] = vb
    for campo in _TEXTOS:
        if isinstance(e.get(campo), str):
            e[campo] = _swap(e[campo])
    cover = e.get("cover")
    if isinstance(cover, str) and "|" in cover:
        partes = [p.strip() for p in cover.split("|")]
        if len(partes) == 2:
            e["cover"] = f"OD: {re.sub(r'^OI:\s*', '', partes[1])} | OI: {re.sub(r'^OD:\s*', '', partes[0])}"
    return e


_CON_ESPEJO = [c for c in _CASOS if _espejo(c["entrada"]) != c["entrada"]]


def test_hay_casos_con_espejo():
    assert len(_CON_ESPEJO) > 900


@pytest.mark.parametrize("bloque", range(0, 10))
def test_espejo_od_oi_conserva_reglas_hechos_y_h01(bloque):
    casos = _CON_ESPEJO[bloque::10]
    for caso in casos:
        original, espejo = caso["entrada"], _espejo(caso["entrada"])
        a1, a2 = activas(**original), activas(**espejo)
        assert set(a1) == set(a2), f"{caso['id']}: reglas distintas {set(a1) ^ set(a2)}"
        for regla in a1:
            assert _palabras(_swap(a1[regla])) == _palabras(a2[regla]), f"{caso['id']} [{regla}]"
        assert alertas_h01(**original) == alertas_h01(**espejo), caso["id"]


# --------------------------------------------- negacion que abarca una lista unida por y/e/o/ni
@pytest.mark.parametrize("motivo", [
    "Sin cefalea y diplopia desde hoy.",
    "Sin evidencia de cefalea intensa y diplopia desde hoy.",
    "No refiere cefalea, vomito ni diplopia desde hoy.",
    "Refiere cefalea, no diplopia.",
])
def test_negacion_se_propaga_a_los_elementos_coordinados(motivo):
    assert "diplopia_aguda" not in activas(motivo=motivo)


@pytest.mark.parametrize("motivo", [
    "Sin cefalea pero con diplopia desde hoy.",
    "Sin cefalea, diplopia desde hoy.",
    "Sin cefalea. Diplopia desde hoy.",
    "Cefalea y diplopia desde hoy.",
    "Sin vomito y con diplopia desde hoy.",
])
def test_negacion_no_cruza_contrastes_comas_ni_oraciones(motivo):
    assert activas(motivo=motivo)["diplopia_aguda"].startswith("Hallazgo urgente:")


_PA = {"motivo": "PA medida hoy 210/125 mmHg; cefalea intensa y vision borrosa de inicio hoy.", "edad": 55}


def test_hipertensivo_negacion_de_lista_no_crea_urgencia_por_hemorragias():
    assert "fondo_hipertensivo" not in activas(
        fondo="Sin evidencia de estrechamiento arteriolar y hemorragias en llama AO.", **_PA)
    assert "fondo_hipertensivo" not in activas(fondo="Sin hemorragias y edema de papila.", **_PA)


@pytest.mark.parametrize("fondo", [
    "Estrechamiento arteriolar y hemorragias en llama AO.",
    "Sin estrechamiento arteriolar pero hemorragias en llama AO.",
    "Sin estrechamiento arteriolar y con hemorragias en llama AO.",
    "Sin hemorragias, edema de papila AO.",
])
def test_hipertensivo_hemorragia_afirmada_con_pa_critica_sigue_urgente(fondo):
    assert activas(fondo=fondo, **_PA)["fondo_hipertensivo"].startswith("Hallazgo urgente:")


# ---------------------------------------------------- ojo normal en otro tramo no localiza el hallazgo
def test_ojo_normal_no_localiza_la_diplopia():
    assert "en OI" in activas(motivo="Dolor ocular OI y diplopia desde hoy, OD normal.")["diplopia_aguda"]
    texto = activas(motivo="Diplopia desde hoy, OD normal.")["diplopia_aguda"]
    assert " en OD" not in texto and " en OI" not in texto
    assert " en OD" in activas(motivo="Diplopia desde hoy en OD.")["diplopia_aguda"]


# ------------------------------------------------ «antecedente familiar» en singular y en plural
@pytest.mark.parametrize("anexos", [
    "Antecedente familiar de orificios meibomianos obstruidos con secrecion espesa y mala expresibilidad.",
    "Antecedentes familiares de orificios meibomianos obstruidos con secrecion espesa.",
    "Antecedente heredofamiliar de DGM.",
])
def test_antecedente_familiar_no_es_dgm_del_paciente(anexos):
    salida = activas(but=4, anexos=anexos)
    assert "ojo_seco_evaporativo_dgm" not in salida and "but_critico" in salida


def test_dgm_del_paciente_sigue_activa():
    assert "ojo_seco_evaporativo_dgm" in activas(but=4, anexos="Orificios meibomianos obstruidos con secrecion espesa.")


# ----------------------------------------------------- un punto tras OD/OI cierra la oracion
def test_punto_tras_od_no_se_confunde_con_dioptrias():
    from app.inference import _split_sentences
    assert _split_sentences("Miopia leve en OD. Presion intraocular alta. Fin.") == [
        "Miopia leve en OD.", "Presion intraocular alta.", "Fin."]
    assert _split_sentences("Cilindro -2.00 D. Se sugiere control.") == ["Cilindro -2.00 D. Se sugiere control."]
    assert _split_sentences("Valores O.D. y O.I. registrados. Otra oracion.") == [
        "Valores O.D. y O.I. registrados.", "Otra oracion."]
