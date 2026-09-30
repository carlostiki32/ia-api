"""Regresiones contextuales de las ordenes #4–9 ya implementadas."""
import pytest

from app.correlaciones.fondo_de_ojo import _eval_papila_patologica_info, _cd_por_ojo
from app.correlaciones.fondo_de_ojo import _eval_fondo_glaucomatoso_info
from app.correlaciones.fondo_de_ojo import _eval_fondo_macular_dmae_info
from app.correlaciones.fondo_de_ojo import _eval_fondo_macular_otros_info
from tests.test_auditoria_correlaciones import _req, activas, alertas_h01


@pytest.mark.parametrize("fondo,nivel", [
    ("Papila OD con bordes borrosos. Hemorragias en llama en retina temporal OI", "B"),
    ("Papila OD con bordes borrosos y hemorragias peripapilares en llama", "A"),
    ("Palidez temporal cutanea sin cambios papilares", None),
    ("Hipermetrope con fondo normal", None),
    ("Sin midriasis, retina aplicada", None),
    ("Pseudopapiledema OD, edema de papila OI", "A"),
    ("Palidez papilar OD. Excavacion 0.8 OI", "PALIDEZ"),
    ("Palidez papilar OD. Excavacion 0.8 OD", "PALIDEZ_EXCAVACION"),
    ("Papila OD: bordes borrosos", "B"),
])
def test_papila_anatomia_y_combinaciones_locales(fondo, nivel):
    req = _req(fondo=fondo, lente="monofocal")
    assert _eval_papila_patologica_info(req)["nivel"] == nivel
    assert ("papila_patologica" in alertas_h01(fondo=fondo, lente="monofocal")) == (nivel == "A")


def test_papila_antecedente_conserva_hallazgo_original():
    texto = activas(
        fondo="Antecedente de edema de papila OD resuelto", lente="monofocal",
    )["papila_patologica"]
    assert "antecedente referido de edema de papila" in texto
    assert "neuritis" not in texto


@pytest.mark.parametrize("fondo,esperado", [
    ("C/D 0.4 OI, 0.8 OD", {"OI": 0.4, "OD": 0.8}),
    ("C/D OI 0.4 OD 0.8", {"OI": 0.4, "OD": 0.8}),
    ("OI C/D 0.4 OD C/D 0.8", {"OI": 0.4, "OD": 0.8}),
    ("C/D 0.8, 0.4", {"": 0.8}),
    ("C/D 0.8 OD y 0.4 OD", {"OD": 0.8}),
    ("C/D 0,85 OD; 0,4 OI", {"OD": 0.85}),
    ("C/D 0.7 AO", {"OD": 0.7, "OI": 0.7}),
    ("C/D 7/10 OD, 4/10 OI", {"OD": 0.7, "OI": 0.4}),
    ("C/D 10.8 OD", {}),
])
def test_cd_valores_no_inventan_lateralidad(fondo, esperado):
    assert _cd_por_ojo(fondo) == esperado


@pytest.mark.parametrize("fondo,activa", [
    ("C/D 0.4 OI, 0.8 OD", True),
    ("C/D 0.8, 0.4", False),
    ("C/D 0.8 OD y 0.4 OD", False),
    ("OI C/D 0.4 OD C/D 0.8", True),
    ("Papila OD: muesca inferior", True),
    ("Muesca OD; muesca OI", False),
    ("Papila OD con adelgazamiento focal del anillo", True),
    ("Muesca palpebral OD", False),
    ("OD: ISNT violada", True),
])
def test_dpar_requiere_asimetria_real_concordante(fondo, activa):
    kw = dict(fondo=fondo, pupilas="Marcus Gunn: OD", edad=62, lente="monofocal")
    assert ("glaucoma_asimetrico" in activas(**kw)) == activa
    assert "glaucoma_asimetrico" not in alertas_h01(**kw)


@pytest.mark.parametrize("fondo,activa,detalle", [
    ("Muesca palpebral OD", False, ""),
    ("Sin muesca OD y muesca inferior OI", True, "muesca inferior en OI"),
    ("ISNT violada: negativo", False, ""),
    ("Antecedente de hemorragia de disco OD resuelta", False, ""),
    ("C/D 0.6 OD; microdisco OI", False, ""),
    ("C/D 0.7 OD; macrodisco OI", True, "0.7 en OD"),
    ("Hemorragia de disco OI", True, "disco optico en OI"),
    ("C/D 0.85 OD", True, "0.85 en OD"),
    ("Sin muescas en OD. Muescas inferotemporales OI", True, "en OI"),
    ("No se cumple regla ISNT en OD", True, "regla ISNT"),
])
def test_papila_focal_local_y_dimension_por_ojo(fondo, activa, detalle):
    info = _eval_fondo_glaucomatoso_info(_req(fondo=fondo, lente="monofocal"))
    assert info["activa"] == activa
    if detalle:
        assert detalle in info["texto"]


@pytest.mark.parametrize("campos,nivel", [
    ({"fondo": "Drusas de papila OD. Hemorragia subretiniana macular OI"}, "A"),
    ({"fondo": "Membrana neovascular OD tratada. Membrana neovascular OI activa"}, "A"),
    ({"fondo": "Hemorragias subretinianas maculares OI"}, "A"),
    ({"fondo": "Drusas de papila OD"}, None),
    ({"fondo": "Drusas blandas y exudados duros maculares OD"}, "A"),
    ({"fondo": "Antecedente de membrana neovascular OD resuelta"}, None),
    ({"fondo": "Membrana neovascular corneal OD"}, None),
    ({"fondo": "CSC OD", "edad": 35, "rx_od": {"esfera": -1}, "rx_oi": {"esfera": -9}}, None),
    ({"fondo": "CSC OD. Sin drusas", "edad": 35}, None),
    ({"fondo": "Desprendimiento neurosensorial macular OD", "edad": 65}, "A"),
    ({"fondo": "Drusas OD", "amsler": "Metamorfopsia nueva OI"}, "B"),
    ({"fondo": "Drusas AO", "amsler": "Metamorfopsia de inicio no registrado"}, "B"),
    ({"fondo": "Drusas AO", "amsler": "Metamorfopsia estable OD; lineas onduladas nuevas OI"}, "A2"),
    ({"fondo": "Drusas AO", "amsler": "Sin metamorfopsia OD; lineas onduladas nuevas OI"}, "A2"),
    ({"fondo": "Drusas AO", "amsler": "Lineas onduladas nuevas OI; sin metamorfopsia OD"}, "A2"),
    ({"fondo": "Drusas OD", "amsler": "Posible distorsion nueva OD, prueba no confiable"}, "B"),
    ({"fondo": "Drusas OD", "amsler": "Distorsion nueva OD, prueba no confiable"}, "B"),
    ({"fondo": "Drusas OD", "amsler": "Comprension alterada, distorsion nueva OD"}, "B"),
    ({"fondo": "Drusas OD", "motivo": "Metamorfopsia OD y dolor de cabeza desde hoy"}, "B"),
    ({"fondo": "Drusas OD", "motivo": "Madre con metamorfopsia nueva OD"}, "B"),
    ({"fondo": "Drusas OD", "amsler": "Escotoma central nuevo OD"}, "A2"),
])
def test_macular_contexto_ocular_y_prioridad(campos, nivel):
    kw = dict(edad=70, lente="monofocal") | campos
    info = _eval_fondo_macular_dmae_info(_req(**kw))
    assert info["nivel"] == nivel
    assert ("fondo_macular_dmae" in alertas_h01(**kw)) == (nivel in ("A", "A2"))


def test_macular_a2_conserva_escotoma_y_micropsia_contralateral():
    kw = dict(edad=70, fondo="Drusas OD", amsler="Escotoma central nuevo OD; micropsia OI", lente="monofocal")
    info = _eval_fondo_macular_dmae_info(_req(**kw))
    assert info["nivel"] == "A2"
    assert "escotoma central nuevo od" in info["texto"]
    assert "micropsia oi" in info["texto"]
    assert "metamorfopsia" not in info["texto"]
    assert "amsler_alterado" not in activas(**kw)


def test_macular_a2_actividad_nueva_no_se_suprime_por_tratamiento_contralateral():
    info = _eval_fondo_macular_dmae_info(_req(
        fondo="DMAE humeda OD en tratamiento; drusas blandas OI", edad=70,
        amsler="Lineas onduladas nuevas OI", lente="monofocal",
    ))
    assert info["nivel"] == "A2"
    assert "lineas onduladas nuevas oi" in info["texto"]


@pytest.mark.parametrize("campos,nivel", [
    ({"fondo": "Membrana epirretiniana OD sin liquido"}, "R"),
    ({"fondo": "Agujero macular lamelar OI"}, "R"),
    ({"fondo": "Agujeros maculares OD"}, "P"),
    ({"fondo": "Quiste macular OD"}, "P"),
    ({"fondo": "Antecedente de edema macular OD resuelto"}, None),
    ({"fondo": "Posible membrana epirretiniana OD"}, None),
    ({"fondo": "Maculopatia miopica con hemorragia OD"}, None),
    ({"fondo": "Maculopatia miopica OD sin hemorragia"}, "R"),
    ({"fondo": "Edema macular OD; OVCR OI"}, "P"),
    ({"fondo": "Edema macular OD; OVCR OD"}, None),
    ({"fondo": "CSC OD. Sin drusas", "edad": 35}, "P"),
    ({"fondo": "CSC OD", "edad": 35, "rx_od": {"esfera": -1}, "rx_oi": {"esfera": -9}}, "P"),
    ({"fondo": "Desprendimiento neurosensorial macular OD", "edad": 65}, None),
    ({"fondo": "Desprendimiento neurosensorial periferico en cuadrante inferior OD"}, None),
])
def test_macular_otros_conserva_hallazgo_real_y_enrutamiento(campos, nivel):
    kw = dict(edad=70, lente="monofocal") | campos
    assert _eval_fondo_macular_otros_info(_req(**kw))["nivel"] == nivel
    if "con hemorragia" in kw["fondo"]:
        assert _eval_fondo_macular_dmae_info(_req(**kw))["nivel"] == "A"
