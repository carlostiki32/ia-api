from collections.abc import Mapping

from pydantic import BaseModel

from app.schemas import ImpresionClinicaRequest


def _has_any_value(value: object) -> bool:
    """Return True when a nested payload contains at least one non-null leaf."""
    if isinstance(value, BaseModel):
        return _has_any_value(value.model_dump())

    if isinstance(value, Mapping):
        return any(_has_any_value(item) for item in value.values())

    if isinstance(value, (list, tuple, set)):
        return any(_has_any_value(item) for item in value)

    return value is not None


def has_clinical_data(req: ImpresionClinicaRequest) -> bool:
    """Check that at least some refraction or clinical data is present."""
    return _has_any_value(req.refraccion) or _has_any_value(req.clinica)
