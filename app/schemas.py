import re

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Literal


class GraduacionOjo(BaseModel):
    esfera: Optional[float] = None
    cilindro: Optional[float] = None
    eje: Optional[int] = None
    add: Optional[float] = None
    av_sc: Optional[str] = None
    av_cc: Optional[str] = None


class AkrOjo(BaseModel):
    esfera: Optional[float] = None
    cilindro: Optional[float] = None
    eje: Optional[int] = None


class Refraccion(BaseModel):
    od: GraduacionOjo = Field(default_factory=GraduacionOjo)
    oi: GraduacionOjo = Field(default_factory=GraduacionOjo)


class AkrSnapshot(BaseModel):
    od: AkrOjo = Field(default_factory=AkrOjo)
    oi: AkrOjo = Field(default_factory=AkrOjo)


class DatosClinica(BaseModel):
    uso_pantallas: Optional[Literal["lt2", "btw2_6", "gt6"]] = None
    anexos_oculares: Optional[str] = None
    reflejos_pupilares: Optional[str] = None
    motilidad_ocular: Optional[str] = None
    confrontacion_campos_visuales: Optional[str] = None
    fondo_de_ojo: Optional[str] = None
    grid_de_amsler: Optional[str] = None
    ojo_seco_but_seg: Optional[int] = Field(None, ge=1, le=15)
    cover_test: Optional[str] = None
    ppc_cm: Optional[int] = Field(None, ge=1, le=15)
    recomendacion_seguimiento: Optional[str] = None

    @field_validator("motilidad_ocular", mode="before")
    @classmethod
    def normalize_motilidad_ocular(cls, value):
        if value is None:
            return None

        value = str(value).replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
        value = re.sub(r"\s+", " ", value).strip()

        return value or None

    @field_validator("cover_test", mode="before")
    @classmethod
    def normalize_cover_test(cls, value):
        if value is None:
            return None

        value = re.sub(r"\s+-\s+", " y ", str(value))
        value = re.sub(r"\s+", " ", value).strip()

        return value or None


class ContextoPaciente(BaseModel):
    edad: Optional[int] = None
    ocupacion: Optional[str] = None
    motivo_consulta: Optional[str] = None


class ImpresionClinicaRequest(BaseModel):
    receta_id: str
    paciente: ContextoPaciente = Field(default_factory=ContextoPaciente)
    refraccion: Refraccion = Field(default_factory=Refraccion)
    akr: AkrSnapshot = Field(default_factory=AkrSnapshot)
    clinica: DatosClinica = Field(default_factory=DatosClinica)
    tipo_lente: Optional[str] = None
