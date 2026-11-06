"""Perfil cerrado de Rx final y catálogo educativo; sin LLM ni GPU."""
from itertools import product
import re

import pytest
from pydantic import ValidationError

from app.patient_profile import (
    build_patient_profile, build_patient_template,
    patient_opening, validate_patient_text, word_count,
)
from app.schemas import ImpresionClinicaRequest


def request(od=None, oi=None, **kwargs):
    return ImpresionClinicaRequest(receta_id="perfil", refraccion={"od": od or {}, "oi": oi or {}}, **kwargs)


@pytest.mark.parametrize("s,c,names", [
    (-2, 0, ("miopía",)), (2, 0, ("hipermetropía",)), (0, 0, ()),
    (-1, -.75, ("miopía", "astigmatismo")),
    (2, -.5, ("hipermetropía", "astigmatismo")),
    (1, -2, ("astigmatismo",)), (0, -1, ("astigmatismo",)), (1, -1, ("astigmatismo",)),
    (2, -1.5, ("hipermetropía", "astigmatismo")),
    (.5, 1.5, ("hipermetropía", "astigmatismo")),
    (-.01, 0, ("miopía",)), (.01, 0, ("hipermetropía",)),
])
def test_principal_powers_classify_every_nonzero_correction(s, c, names):
    eye = {"esfera": s, "cilindro": c}
    profile = build_patient_profile(request(eye, eye))
    assert profile.ojos[0].nombres == profile.ojos[1].nombres == names
    assert profile.estado == ("aplicable" if names else "sin_componentes_refractivos")


def test_positive_cylinder_transposition_preserves_profile_without_axis():
    a = build_patient_profile(request({"esfera": 2, "cilindro": -1.5}, {"esfera": 2, "cilindro": -1.5}))
    b = build_patient_profile(request({"esfera": .5, "cilindro": 1.5}, {"esfera": .5, "cilindro": 1.5}))
    assert a == b


@pytest.mark.parametrize("od,oi", [
    ({"esfera": 0}, {"esfera": 0, "cilindro": 0}),
    ({"cilindro": -1}, {"esfera": 0, "cilindro": 0}),
    ({"esfera": 0, "cilindro": 0}, {}),
    ({"esfera": None, "cilindro": 1}, {"esfera": 0, "cilindro": 0}),
])
def test_missing_fields_are_not_zero_or_replaced_by_akr(od, oi):
    req = request(od, oi, akr={"od": {"esfera": -2, "cilindro": -1}, "oi": {"esfera": -2, "cilindro": -1}})
    profile = build_patient_profile(req)
    assert profile.estado == "datos_incompletos"
    assert build_patient_template(profile) is None


def test_zero_eye_is_described_without_claiming_health():
    profile = build_patient_profile(request({"esfera": -3, "cilindro": 0}, {"esfera": 0, "cilindro": 0}))
    text = build_patient_template(profile)
    assert "ojo derecho" in text
    assert "En el ojo izquierdo, su receta de lejos marca 0.00: ese lado no lleva corrección para ver de lejos." in text
    assert "sano" not in text and "normal" not in text


def test_age_and_add_never_infer_presbyopia():
    profile = build_patient_profile(request(
        {"esfera": 0, "cilindro": 0, "add": 1.5}, {"esfera": 0, "cilindro": 0, "add": 1.5},
        paciente={"edad": 75},
    ))
    text = build_patient_template(profile)
    assert "apoyo extra para enfocar de cerca" in text and "presbicia" not in text
    assert profile.nombres == ()


def test_profile_uses_only_final_rx_not_age_clinical_akr_or_lens_design():
    eye = {"esfera": -2, "cilindro": 0}
    plain = build_patient_profile(request(eye, eye))
    extra = build_patient_profile(request(eye, eye, paciente={"edad": 80, "motivo_consulta": "Glaucoma"},
        akr={"od": {"esfera": 3, "cilindro": -1}},
        clinica={"fondo_de_ojo": "Catarata y patología", "recomendacion_seguimiento": "Cirugia"}, tipo_lente="progresivo"))
    assert plain == extra
    assert build_patient_template(plain) == build_patient_template(extra)


# Todas las combinaciones de tipos/ojos/ADD tienen plantilla legible válida.
@pytest.mark.parametrize("left,right,near_left,near_right", list(product(
    [(0, 0), (-2, 0), (2, 0), (-1, -1), (2, -.5), (1, -2)],
    [(0, 0), (-2, 0), (2, 0), (-1, -1), (2, -.5), (1, -2)], [False, True], [False, True],
)))
def test_template_catalog_all_combinations(left, right, near_left, near_right):
    od = {"esfera": left[0], "cilindro": left[1], "add": 1.5 if near_left else None}
    oi = {"esfera": right[0], "cilindro": right[1], "add": 1.5 if near_right else None}
    profile = build_patient_profile(request(od, oi))
    text = build_patient_template(profile)
    if profile.estado == "sin_componentes_refractivos":
        assert text is None
    else:
        assert text is not None, (left, right, near_left, near_right)
        assert 60 <= word_count(text) <= 110
        assert validate_patient_text(text, profile) == text
        assert not re.search(
            r"\b(tú|tu|tus|te|ti|contigo|puedes|quieres|veas|tienes|usas|veas|"
            r"pregunta|deja|vuelve|mira|consulta|"
            r"(?:ayudar|explicar|explicár|llevar|cuidar|adaptar|operar)te(?:la|lo|las|los)?)\b",
            text, re.IGNORECASE,
        )
        assert not re.search(r"\b(sano|sana|normal|no necesita|no requiere|presbicia|perfecto|perfecta)\b", text, re.IGNORECASE)
        if profile.nombres:
            assert text.count("Su graduación incluye") == 1


@pytest.mark.parametrize("defect", [
    " Tienes glaucoma y debes usar gotas.", " Tu visión será perfecta.",
    " Necesitas cirugía urgente.", " La presbicia viene con la edad.",
    " El ojo izquierdo tiene miopía.", " Tienes 2 dioptrías.",
    " El paciente tiene miopía leve.", " Tus ojos están sanos.",
    " <script>hola</script>", " Tu visión es normal.",
])
def test_editorial_guard_rejects_unsupported_claims(defect):
    eye = {"esfera": -2, "cilindro": 0}
    profile = build_patient_profile(request(eye, eye))
    text = build_patient_template(profile)
    assert validate_patient_text(text + defect, profile) is None


def test_guard_rejects_wrong_eye_or_extra_correction_and_types():
    profile = build_patient_profile(request({"esfera": -2, "cilindro": 0}, {"esfera": 0, "cilindro": 0}))
    text = build_patient_template(profile)
    assert validate_patient_text(text.replace("ojo derecho", "ojo izquierdo"), profile) is None
    assert validate_patient_text(text + " La hipermetropía puede dificultar ver.", profile) is None
    assert validate_patient_text({"texto": text}, profile) is None
    assert validate_patient_text(None, profile) is None


@pytest.mark.parametrize("defect", [
    "inverted_definition", "permanent_loss", "abandon_lenses", "clinical_finding", "unknown_advice",
])
def test_sentence_catalog_rejects_semantic_inversion_and_unapproved_tail(defect):
    eye = {"esfera": -2, "cilindro": 0}
    profile = build_patient_profile(request(eye, eye))
    original = build_patient_template(profile)
    if defect == "inverted_definition":
        candidate = original.replace("está lejos, como un letrero", "está cerca, como un libro")
    else:
        tail = {
            "permanent_loss": " La miopía puede llevarte a perder la visión para siempre.",
            "abandon_lenses": " Deja de usar tus lentes y no vuelvas a la óptica.",
            "clinical_finding": " Tu nervio óptico está dañado.",
            "unknown_advice": " Ignora tu receta y compra lentes de otra persona.",
        }[defect]
        candidate = original + tail
    # No rechazamos solo porque el ejemplo deje de cumplir la longitud editorial.
    assert 60 <= word_count(candidate) <= 110
    assert validate_patient_text(candidate, profile) is None


def test_sentence_catalog_keeps_previously_approved_variants():
    eye = {"esfera": -2, "cilindro": -.75}
    profile = build_patient_profile(request(eye, eye))
    candidate = (
        "Su graduación incluye corrección para miopía y astigmatismo en los dos ojos. "
        "La miopía hace que los objetos lejanos puedan verse borrosos. "
        "El astigmatismo puede hacer que algunas letras o bordes se vean poco definidos. "
        "Con sus lentes, la imagen puede verse más clara y cómoda en sus actividades diarias. "
        "Cada ojo recibe la graduación que necesita. Los lentes le ayudan a enfocar mientras los usa. "
        "Si tiene dudas sobre cómo usarlos, su optometrista se lo puede explicar durante la entrega."
    )
    assert 60 <= word_count(candidate) <= 110
    assert validate_patient_text(candidate, profile) == candidate


@pytest.mark.parametrize("change", ["missing_definition", "duplicate_definition", "duplicate_closing", "wrong_near_eye"])
def test_catalog_requires_each_profile_fact_once_and_correct_near_eye(change):
    eye = {"esfera": -2, "cilindro": 0, "add": 1.5}
    profile = build_patient_profile(request(eye, {"esfera": -2, "cilindro": 0}))
    original = build_patient_template(profile)
    definition = "La miopía puede hacer que vea borroso lo que está lejos, como un letrero."
    if change == "missing_definition":
        candidate = original.replace(definition + " ", "") + " Puede preguntarnos qué significa cada parte de su receta y se lo explicamos con palabras sencillas."
    elif change == "duplicate_definition":
        candidate = original.replace(definition, definition + " " + definition)
    elif change == "duplicate_closing":
        candidate = original + " Sus lentes llevan la graduación de cada ojo para ayudarle a ver más claro."
    else:
        candidate = original.replace("enfocar de cerca en el ojo derecho", "enfocar de cerca en el ojo izquierdo")
    assert 60 <= word_count(candidate) <= 110
    assert validate_patient_text(candidate, profile) is None


@pytest.mark.parametrize("value", [None, "otra-version", 1])
def test_output_version_is_typed(value):
    with pytest.raises(ValidationError):
        request(salida_version=value)
    assert request().salida_version == "clinica-v1"


def test_zero_sphere_with_cylinder_is_not_plano():
    eye = {"esfera": 0, "cilindro": -1}
    profile = build_patient_profile(request(eye, eye))
    assert all(not eye.plano for eye in profile.ojos)
    assert "marca 0.00" not in build_patient_template(profile)


def test_plano_left_with_unilateral_near_support():
    profile = build_patient_profile(request(
        {"esfera": -2, "cilindro": 0}, {"esfera": 0, "cilindro": 0, "add": 1.5},
    ))
    text = build_patient_template(profile)
    assert "En el ojo izquierdo, su receta de lejos marca 0.00" in text
    assert "Su receta también incluye un apoyo extra para enfocar de cerca en el ojo izquierdo." in text
    assert text.index("marca 0.00") < text.index("La miopía") < text.index("Su receta también")


@pytest.mark.parametrize("side", ["od", "oi"])
def test_add_only_describes_both_plano_eyes_and_correct_near_side(side):
    eyes = {"od": {"esfera": 0, "cilindro": 0}, "oi": {"esfera": 0, "cilindro": 0}}
    eyes[side]["add"] = 1.5
    profile = build_patient_profile(request(**eyes))
    text = build_patient_template(profile)
    assert "En los dos ojos, su receta de lejos marca 0.00: no lleva corrección para ver de lejos." in text
    assert f"en el ojo {'derecho' if side == 'od' else 'izquierdo'}." in text


def test_different_eyes_have_one_opening_sentence():
    profile = build_patient_profile(request({"esfera": 0, "cilindro": -1}, {"esfera": -2, "cilindro": 0}))
    opening = "Su graduación incluye corrección para astigmatismo en el ojo derecho y para miopía en el ojo izquierdo."
    text = build_patient_template(profile)
    assert patient_opening(profile) == opening
    assert text.startswith(opening)
    assert len(re.findall(r"(?:^|\.\s+)Su graduación incluye", text)) == 1


@pytest.mark.parametrize("change", ["omit", "duplicate", "move_after_definition", "alter_zero", "add_cylinder_plano"])
def test_guard_requires_exact_plano_fact_in_order(change):
    profile = build_patient_profile(request({"esfera": -2, "cilindro": 0}, {"esfera": 0, "cilindro": 0}))
    original = build_patient_template(profile)
    plano = "En el ojo izquierdo, su receta de lejos marca 0.00: ese lado no lleva corrección para ver de lejos."
    definition = "La miopía puede hacer que vea borroso lo que está lejos, como un letrero."
    if change == "omit":
        candidate = original.replace(plano + " ", "")
    elif change == "duplicate":
        candidate = original.replace(plano, plano + " " + plano)
    elif change == "move_after_definition":
        candidate = original.replace(plano + " " + definition, definition + " " + plano)
    elif change == "alter_zero":
        candidate = original.replace("0.00", "0.01")
    else:
        candidate = original.replace("ojo izquierdo, su receta de lejos", "ojo derecho, su receta de lejos")
    assert validate_patient_text(candidate, profile) is None
