"""Contrato interno inmutable de salida dual; la API agrega trazabilidad."""
from typing import Literal

from pydantic import BaseModel, ConfigDict

PIPELINE_VERSION = "clinica-paciente-v1"
PATIENT_PROFILE_VERSION = "refraccion-final-lejos-v2"
DUAL_PROMPT_VERSION = "educacion-plantilla-usted-v3"

PatientState = Literal[
    "generada", "plantilla", "sin_componentes_refractivos", "datos_incompletos", "rechazada"
]
PatientOrigin = Literal["llm", "plantilla", "ninguno"]

class DualInferenceResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    impresion_clinica: str
    explicacion_paciente: str | None
    explicacion_paciente_estado: PatientState
    origen_explicacion: PatientOrigin
