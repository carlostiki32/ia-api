"""Lateralidad por tramos (extractor compartido `_ocurrencias_oculares`, #13-#19).

Regresion hallada en la revision independiente del 2026-09-29: en «Limitacion de la
abduccion OD, OI normal» el tramo normal del otro ojo hacia que el hallazgo se
describiera «en ambos ojos» (o sin ojo, en pupilas). El hallazgo pertenece solo al ojo
de su tramo cuando el otro ojo aparece unicamente en tramos con marca de normalidad o
negacion; sin esa marca (elipsis, «sin cambios», «no normal») se conservan ambos ojos.
"""
import pytest

from tests.test_auditoria_correlaciones import activas

# (regla, campos, fragmento que debe aparecer)
SOLO_SU_OJO = [
    ("pupilas_alteradas", {"pupilas": "DPAR OD, pupila OI normal"}, "aferente relativo OD"),
    ("pupilas_alteradas", {"pupilas": "Pupila OI normal, DPAR OD"}, "aferente relativo OD"),
    ("pupilas_alteradas", {"pupilas": "Miosis OD, reflejos OI normales"}, "miosis OD"),
    ("pupilas_alteradas", {"pupilas": "Miosis OI, pupila OD sin alteraciones"}, "miosis OI"),
    ("motilidad_alterada", {"motilidad": "Limitacion de la abduccion OD, OI normal"}, "limitacion de abduccion OD"),
    ("motilidad_alterada", {"motilidad": "Ducciones OI normales, limitacion de la aduccion OD"},
     "limitacion de aduccion OD"),
    ("motilidad_alterada", {"motilidad": "Limitacion de la abduccion OI, OD sin limitacion"},
     "limitacion de abduccion OI"),
    ("campos_visuales_alterados", {"campos": "Defecto campimetrico OD, OI sin alteraciones"}, "defecto del campo OD"),
    ("campos_visuales_alterados", {"campos": "OI normal, defecto campimetrico temporal OD"},
     "defecto del campo temporal OD"),
    ("amsler_alterado", {"amsler": "Metamorfopsia OD, OI sin alteracion"}, "metamorfopsia OD"),
    ("amsler_alterado", {"amsler": "Amsler OI normal, metamorfopsia OD"}, "metamorfopsia OD"),
    ("anexos_riesgo_glaucoma_secundario", {"anexos": "Pseudoexfoliacion OD, OI sin signos"}, "pseudoexfoliacion OD"),
    ("anexos_riesgo_glaucoma_secundario", {"anexos": "Krukenberg OD, segmento anterior OI normal"},
     "huso de Krukenberg OD"),
    ("anexos_patologicos", {"anexos": "Pterigion nasal OD, conjuntiva OI normal"}, "pterigion nasal OD"),
    ("anexos_patologicos", {"anexos": "Conjuntiva OD normal, chalazion OI"}, "chalazion OI"),
    ("anexos_patologicos", {"anexos": "Blefaritis OD, parpado OI normal"}, "blefaritis OD"),
    ("opacidad_cristaliniana", {"anexos": "Catarata OD, cristalino OI transparente"}, "opacidad del cristalino OD"),
    ("opacidad_cristaliniana", {"anexos": "Cristalino OD transparente, catarata OI"}, "opacidad del cristalino OI"),
    ("opacidad_cristaliniana", {"anexos": "Cristalino subluxado OD, cristalino OI transparente"},
     "cristalino subluxado OD"),
    ("opacidad_cristaliniana", {"anexos": "Lente intraocular decentrado OI, cristalino OD claro"},
     "lente intraocular decentrado OI"),
]


@pytest.mark.parametrize("regla,campos,fragmento", SOLO_SU_OJO)
def test_hallazgo_con_ojo_contralateral_normal_conserva_solo_su_ojo(regla, campos, fragmento):
    texto = activas(**campos).get(regla)
    assert texto is not None, f"{regla} no se activa"
    assert fragmento in texto
    assert "ambos ojos" not in texto and "bilateral" not in texto


# Sin marca de normalidad no se puede separar: se conservan ambos ojos, sin perder ninguno.
CONSERVAN_AMBOS = [
    ("opacidad_cristaliniana", {"anexos": "Catarata nuclear OD, cortical OI"}),  # elipsis
    ("opacidad_cristaliniana", {"anexos": "Catarata OD, OI"}),
    ("anexos_patologicos", {"anexos": "Pterigion OD, sin cambios en OI"}),
    ("anexos_patologicos", {"anexos": "Pterigion OD, OI no normal"}),
    ("anexos_patologicos", {"anexos": "Blefaritis OD, OI"}),
    ("campos_visuales_alterados", {"campos": "Defecto campimetrico OD, OI"}),
]


@pytest.mark.parametrize("regla,campos", CONSERVAN_AMBOS)
def test_sin_marca_de_normalidad_se_conservan_ambos_ojos(regla, campos):
    texto = activas(**campos).get(regla)
    assert texto is not None and "ambos ojos" in texto


# Dos hallazgos, uno por ojo, siguen separados.
def test_hallazgos_distintos_por_ojo_siguen_separados():
    assert "chalazion OD y blefaritis OI" in activas(anexos="Chalazion OD, blefaritis OI")["anexos_patologicos"]
    assert "miosis OD y midriasis OI" in activas(pupilas="Miosis OD, midriasis OI")["pupilas_alteradas"]
    texto = activas(motilidad="Limitacion de la abduccion OD, limitacion de la abduccion OI")["motilidad_alterada"]
    assert "limitacion de abduccion OD" in texto and "limitacion de abduccion OI" in texto
