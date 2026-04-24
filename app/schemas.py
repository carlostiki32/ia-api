import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


_WS_RE = re.compile(r"\s+")
_COVER_DASH_RE = re.compile(r"\s+-\s+")


def _normalize_whitespace(value) -> str | None:
    if value is None:
        return None
    value = _WS_RE.sub(" ", str(value)).strip()
    return value or None


class GraduacionOjo(BaseModel):
    esfera: float | None = None
    cilindro: float | None = None
    eje: int | None = None
    add: float | None = None
    av_sc: str | None = None
    av_cc: str | None = None


class AkrOjo(BaseModel):
    esfera: float | None = None
    cilindro: float | None = None
    eje: int | None = None


class Refraccion(BaseModel):
    od: GraduacionOjo = Field(default_factory=GraduacionOjo)
    oi: GraduacionOjo = Field(default_factory=GraduacionOjo)


class AkrSnapshot(BaseModel):
    od: AkrOjo = Field(default_factory=AkrOjo)
    oi: AkrOjo = Field(default_factory=AkrOjo)


class DatosClinica(BaseModel):
    uso_pantallas: Literal["lt2", "btw2_6", "gt6"] | None = None
    anexos_oculares: str | None = None
    reflejos_pupilares: str | None = None
    motilidad_ocular: str | None = None
    confrontacion_campos_visuales: str | None = None
    fondo_de_ojo: str | None = None
    grid_de_amsler: str | None = None
    ojo_seco_but_seg: int | None = Field(None, ge=1, le=15)
    cover_test: str | None = None
    ppc_cm: int | None = Field(None, ge=1, le=15)
    recomendacion_seguimiento: str | None = None

    @field_validator("motilidad_ocular", mode="before")
    @classmethod
    def normalize_motilidad_ocular(cls, value):
        return _normalize_whitespace(value)

    @field_validator("cover_test", mode="before")
    @classmethod
    def normalize_cover_test(cls, value):
        if value is None:
            return None
        value = _COVER_DASH_RE.sub(" y ", str(value))
        return _normalize_whitespace(value)


class ContextoPaciente(BaseModel):
    edad: int | None = None
    ocupacion: str | None = None
    motivo_consulta: str | None = None


class ImpresionClinicaRequest(BaseModel):
    receta_id: str
    paciente: ContextoPaciente = Field(default_factory=ContextoPaciente)
    refraccion: Refraccion = Field(default_factory=Refraccion)
    akr: AkrSnapshot = Field(default_factory=AkrSnapshot)
    clinica: DatosClinica = Field(default_factory=DatosClinica)
    tipo_lente: str | None = None
