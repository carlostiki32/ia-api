from typing import Literal
from contextvars import ContextVar
import logging

from pydantic import BaseModel, ConfigDict, Field

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


class SeguimientoWhatsappRequest(Estricto):
    contrato_version: Literal["seguimiento-whatsapp-v1"]
    paciente_ref: str = Field(pattern=r"^[a-f0-9]{16}$")
    tramo_edad: Literal["18_39", "40_59", "60_mas"]
    estado_seguimiento: Literal["proximo", "vencido"]
    meses_desde_ultima_receta: int | None = Field(ge=0, le=600)
    recetas_previas: int = Field(ge=0, le=1000)
    costo: Literal["incluida", "con_costo"]
    ya_notificado_en_ciclo: bool
    variante: int = Field(ge=0, le=1000)
    rx_lejos: RxLejos | None
    tipo_lente: Literal["monofocal", "bifocal", "progresivo", "otro"] | None
    uso_pantallas: Literal["lt2", "btw2_6", "gt6"] | None
    usa_armazon: bool | None


class Partes(Estricto):
    apertura: str
    hechos: list[str]
    invitacion: str
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
    contrato_version: Literal["seguimiento-whatsapp-v1"] = "seguimiento-whatsapp-v1"
    estado: Literal["generada", "plantilla"]
    mensaje: str = Field(max_length=2000)
    partes: Partes
    motivo: str | None
    hechos_elegibles: list[str]
    generacion: Generacion
