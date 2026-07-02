import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator


_WS_RE = re.compile(r"\s+")
_COVER_DASH_RE = re.compile(r"\s+-\s+")
# Agudeza visual Snellen en pie: el frontend la envia como "20/xx". Se canoniza
# (colapsa espacios internos) para que _snellen_denominator la interprete y para
# no arrastrar espacios al prompt. Notaciones no-Snellen (p. ej. "CF", "MM",
# "cuenta dedos") se conservan tal cual: no se rechazan porque el catalogo real
# del frontend puede incluirlas y la capa de correlaciones las ignora sin error.
_SNELLEN_RE = re.compile(r"^\s*20\s*/\s*(\d{1,3})\s*$")

# Eje refractivo y de queratometria: 0..180 grados (constante del frontend).
_EJE_MIN, _EJE_MAX = 0, 180


def _normalize_whitespace(value) -> str | None:
    if value is None:
        return None
    value = _WS_RE.sub(" ", str(value)).strip()
    return value or None


def _normalize_av(value) -> str | None:
    value = _normalize_whitespace(value)
    if value is None:
        return None
    match = _SNELLEN_RE.match(value)
    if match:
        return f"20/{int(match.group(1))}"
    return value


class GraduacionOjo(BaseModel):
    esfera: float | None = None
    cilindro: float | None = None
    eje: int | None = Field(None, ge=_EJE_MIN, le=_EJE_MAX)
    add: float | None = None
    av_sc: str | None = None
    av_cc: str | None = None

    @field_validator("av_sc", "av_cc", mode="before")
    @classmethod
    def normalize_av(cls, value):
        return _normalize_av(value)


class AkrOjo(BaseModel):
    esfera: float | None = None
    cilindro: float | None = None
    eje: int | None = Field(None, ge=_EJE_MIN, le=_EJE_MAX)
    k1_d: float | None = Field(None, ge=25, le=80)
    k1_mm: float | None = Field(None, ge=4, le=12)
    k1_eje: int | None = Field(None, ge=0, le=180)
    k2_d: float | None = Field(None, ge=25, le=80)
    k2_mm: float | None = Field(None, ge=4, le=12)
    k2_eje: int | None = Field(None, ge=0, le=180)
    k_promedio_d: float | None = Field(None, ge=25, le=80)
    k_promedio_mm: float | None = Field(None, ge=4, le=12)
    k_cilindro: float | None = Field(None, ge=-20, le=20)
    k_cilindro_eje: int | None = Field(None, ge=0, le=180)


class Refraccion(BaseModel):
    od: GraduacionOjo = Field(default_factory=GraduacionOjo)
    oi: GraduacionOjo = Field(default_factory=GraduacionOjo)


class AkrSnapshot(BaseModel):
    ticket_id: int | None = None
    taken_at: str | None = None
    pd: float | None = None
    vd: float | None = Field(None, ge=0, le=30)
    ker_index: float | None = Field(None, ge=1.3, le=1.4)
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
    edad: int | None = Field(None, ge=0, le=120)
    ocupacion: str | None = None
    motivo_consulta: str | None = None


class ImpresionClinicaRequest(BaseModel):
    receta_id: str
    paciente: ContextoPaciente = Field(default_factory=ContextoPaciente)
    refraccion: Refraccion = Field(default_factory=Refraccion)
    akr: AkrSnapshot = Field(default_factory=AkrSnapshot)
    clinica: DatosClinica = Field(default_factory=DatosClinica)
    # tipo_lente NO se cierra a Literal: el catalogo de disenos (monofocal,
    # bifocal, progresivo, multifocal, ocupacional, etc.) lo define el frontend
    # y puede crecer sin coordinacion con la API. Se normaliza espacio en blanco;
    # la deteccion multifocal se hace por substring en la capa de correlaciones.
    tipo_lente: str | None = None

    @field_validator("tipo_lente", mode="before")
    @classmethod
    def normalize_tipo_lente(cls, value):
        return _normalize_whitespace(value)
