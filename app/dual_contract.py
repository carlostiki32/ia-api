"""Contrato interno inmutable de salida dual; la API agrega trazabilidad."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, StrictStr

PIPELINE_VERSION = "clinica-paciente-v1"
PATIENT_PROFILE_VERSION = "refraccion-final-lejos-v1"
DUAL_PROMPT_VERSION = "educacion-catalogo-v2"

PatientState = Literal[
    "generada", "plantilla", "sin_componentes_refractivos", "datos_incompletos", "rechazada"
]
PatientOrigin = Literal["llm", "plantilla", "ninguno"]

# Solo dos strings en el contenido generado. Nunca pedir al LLM hashes/orígenes.
DUAL_OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "impresion_clinica": {"type": "string", "minLength": 1},
        "explicacion_paciente": {"type": ["string", "null"]},
    },
    "required": ["impresion_clinica", "explicacion_paciente"],
    "additionalProperties": False,
}


class RecoverableDualOutput(BaseModel):
    """Tipar el clínico sin perderlo por un tipo educativo defectuoso.

    El schema que se envía a Ollama es estrecho. Aquí el candidato educativo
    se valida por separado: un objeto/lista/número activa plantilla, sin
    convertir un clínico válido en un fallo completo.
    """
    model_config = ConfigDict(extra="forbid")
    impresion_clinica: StrictStr
    explicacion_paciente: Any = None


class DualInferenceResult(BaseModel):
    model_config = ConfigDict(frozen=True)
    impresion_clinica: str
    explicacion_paciente: str | None
    explicacion_paciente_estado: PatientState
    origen_explicacion: PatientOrigin
