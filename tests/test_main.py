from app.clinical_data import has_clinical_data
from app.schemas import ImpresionClinicaRequest


def test_has_clinical_data_accepts_zero_refraction_values():
    req = ImpresionClinicaRequest(
        receta_id="test-zero",
        refraccion={
            "od": {
                "esfera": 0.0,
            }
        },
    )

    assert has_clinical_data(req) is True


def test_has_clinical_data_rejects_context_without_clinical_fields():
    req = ImpresionClinicaRequest(
        receta_id="test-context-only",
        paciente={
            "edad": 36,
            "ocupacion": "Programador",
            "motivo_consulta": "Revision",
        },
    )

    assert has_clinical_data(req) is False
