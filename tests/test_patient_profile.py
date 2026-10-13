"""Perfil cerrado de Rx final y catálogo educativo; sin LLM ni GPU."""
from itertools import product

import pytest
from pydantic import ValidationError

from app.patient_profile import (
    build_patient_profile, build_patient_context, build_patient_template,
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


def test_zero_eye_is_omitted_without_claiming_health():
    profile = build_patient_profile(request({"esfera": -2, "cilindro": 0}, {"esfera": 0, "cilindro": 0}))
    text = build_patient_template(profile)
    assert "ojo derecho" in text and "izquierdo" not in text
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
    assert "Glaucoma" not in str(build_patient_context(extra))


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
        "Tu graduación incluye corrección para miopía y astigmatismo en los dos ojos. "
        "La miopía hace que los objetos lejanos puedan verse borrosos. "
        "El astigmatismo puede hacer que algunas letras o bordes se vean poco definidos. "
        "Con tus lentes, la imagen puede verse más clara y cómoda en las actividades diarias. "
        "Cada ojo recibe la graduación que necesita. Los lentes ayudan a enfocar mientras los usas. "
        "Si tienes dudas sobre cómo utilizarlos, tu optometrista puede explicártelo durante la entrega."
    )
    assert word_count(candidate) == 78
    assert validate_patient_text(candidate, profile) == candidate
    context = build_patient_context(profile)
    assert "La miopía hace que los objetos lejanos puedan verse borrosos." in context["definiciones_permitidas"]["miopía"]
    assert "hipermetropía" not in context["definiciones_permitidas"]
    assert context["frase_apoyo_cerca"] == context["definicion_apoyo_cerca"] == ""


@pytest.mark.parametrize("change", ["missing_definition", "duplicate_definition", "duplicate_closing", "wrong_near_eye"])
def test_catalog_requires_each_profile_fact_once_and_correct_near_eye(change):
    eye = {"esfera": -2, "cilindro": 0, "add": 1.5}
    profile = build_patient_profile(request(eye, {"esfera": -2, "cilindro": 0}))
    original = build_patient_template(profile)
    context = build_patient_context(profile)
    definition = context["definiciones_permitidas"]["miopía"][0]
    if change == "missing_definition":
        candidate = original.replace(definition + " ", "") + " " + context["cierres_permitidos"][2]
    elif change == "duplicate_definition":
        candidate = original.replace(definition, definition + " " + definition)
    elif change == "duplicate_closing":
        candidate = original + " " + context["cierres_permitidos"][0]
    else:
        candidate = original.replace("enfocar de cerca en el ojo derecho", "enfocar de cerca en el ojo izquierdo")
    assert 60 <= word_count(candidate) <= 110
    assert validate_patient_text(candidate, profile) is None


@pytest.mark.parametrize("value", [None, "otra-version", 1])
def test_output_version_is_typed(value):
    with pytest.raises(ValidationError):
        request(salida_version=value)
    assert request().salida_version == "clinica-v1"
