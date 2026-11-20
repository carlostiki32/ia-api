import datetime
from typing import Literal
from contextvars import ContextVar
import logging

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas import GraduacionOjo, Refraccion

_normalizando_seguimiento = ContextVar("normalizando_seguimiento", default=False)


class _SinContenidoRx(logging.Filter):
    def filter(self, record):
        # La normalización clínica registra valores descartados. En seguimiento
        # se aplica idéntica normalización, pero nunca se registran cifras de Rx.
        return not _normalizando_seguimiento.get()


logging.getLogger("app.schemas").addFilter(_SinContenidoRx())


class Estricto(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RxOjoLejos(Estricto):
    esfera: float | None
    cilindro: float | None
    add: float | None


class RxLejos(Estricto):
    od: RxOjoLejos
    oi: RxOjoLejos

    def refraccion(self) -> Refraccion:
        token = _normalizando_seguimiento.set(True)
        try:
            return Refraccion(**{lado: GraduacionOjo(**getattr(self, lado).model_dump()) for lado in ("od", "oi")})
        finally:
            _normalizando_seguimiento.reset(token)


class ContextoUso(Estricto):
    ocupacion: str | None = Field(default=None, max_length=120)
    motivo_consulta: str | None = Field(default=None, max_length=1500)
    impresion_clinica: str | None = Field(default=None, max_length=3000)
    explicacion_paciente: str | None = Field(default=None, max_length=3000)
    observaciones_receta: str | None = Field(default=None, max_length=1500)
    recomendacion_seguimiento: str | None = Field(default=None, max_length=1500)

    @field_validator(
        "ocupacion",
        "motivo_consulta",
        "impresion_clinica",
        "explicacion_paciente",
        "observaciones_receta",
        "recomendacion_seguimiento",
        mode="before",
    )
    @classmethod
    def _limpiar_cadenas_vacias(cls, v):
        if isinstance(v, str) and not v.strip():
            return None
        return v


class SeguimientoWhatsappRequest(Estricto):
    contrato_version: Literal["seguimiento-whatsapp-v2"]
    paciente_ref: str = Field(pattern=r"^[a-f0-9]{16}$")
    tramo_edad: Literal["18_39", "40_59", "60_mas"]
    estado_seguimiento: Literal["proximo", "vencido"]
    meses_desde_ultima_receta: int | None = Field(default=None, ge=0, le=600)
    recetas_previas: int = Field(ge=0, le=1000)
    costo: Literal["incluida", "con_costo"]
    ya_notificado_en_ciclo: bool
    variante: int = Field(ge=0, le=1000)
    rx_lejos: RxLejos | None = None
    tipo_lente: Literal["monofocal", "bifocal", "progresivo", "otro"] | None = None
    uso_pantallas: Literal["lt2", "btw2_6", "gt6"] | None = None
    usa_armazon: bool | None = None
    fecha_revision: datetime.date | None = None
    meses_periodo: int | None = Field(default=None, ge=1, le=600)
    contexto_uso: ContextoUso

    @model_validator(mode="after")
    def _validar_vencido_sin_fecha(self):
        if self.estado_seguimiento == "vencido":
            if self.fecha_revision is not None or self.meses_periodo is not None:
                raise ValueError("Con estado 'vencido', fecha_revision y meses_periodo deben ser None")
        return self


class Partes(Estricto):
    apertura: str
    apertura_id: str | None = None
    frase_uso: str
    frase_fecha: str
    hechos: list[str] = Field(max_length=1)
    cierre: str
    cierre_id: str
    baja: str


class Generacion(Estricto):
    origen: Literal["llm", "catalogo"]
    modelo: str | None
    catalogo_version: str
    prompt_version: str
    base_hash_api: str = Field(pattern=r"^[a-f0-9]{64}$")
    cached: bool


class SeguimientoWhatsappResponse(Estricto):
    status: Literal["ok"] = "ok"
    contrato_version: Literal["seguimiento-whatsapp-v2"] = "seguimiento-whatsapp-v2"
    estado: Literal["generada", "plantilla"]
    mensaje: str = Field(max_length=2000)
    partes: Partes
    motivo: str | None = None
    hechos_elegibles: list[str]
    generacion: Generacion
    uso_lentes: str
    origen_uso: Literal["llm", "reglas"]
