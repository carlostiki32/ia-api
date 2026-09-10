"""Esquema del payload de /inferencia/impresion-clinica.

Refleja el catalogo REAL del formulario de receta del SaaS (repo `opt`):
`app/Support/OpticaOptions.php`, `app/Support/Recetas/RecetaFormOptions.php`,
`app/Support/Recetas/RecetaValidationRules.php` y las vistas
`resources/views/livewire/recetas/form/*.blade.php`. El payload lo arma
`App\\Services\\IaApiService::buildPayload()`.

Politica de validacion: COERCION TOLERANTE, no rechazo. El SaaS llama a este
endpoint con el estado crudo del formulario SIN pasar por la validacion de
Laravel (FormEditor::generateImpresionClinica no valida antes de toPayload),
asi que un valor fuera de catalogo en un campo secundario no debe tumbar la
generacion completa con 422: se descarta (None) o se normaliza, y se loggea.
"""
import logging
import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

_WS_RE = re.compile(r"\s+")
_COVER_DASH_RE = re.compile(r"\s+-\s+")
# Agudeza visual Snellen en pie: el frontend la envia como "20/xx". Se canoniza
# (colapsa espacios internos) y para no arrastrar espacios al prompt. La capa de
# correlaciones (_av_denominator) interpreta ademas notacion metrica (6/12) y
# decimal (0.5). Notaciones no interpretables (p. ej. "CF", "MM", "cuenta dedos")
# se conservan tal cual: no se rechazan porque pueden venir de registros legacy
# y la capa de correlaciones las ignora sin error.
_SNELLEN_RE = re.compile(r"^\s*20\s*/\s*(\d{1,3})\s*$")

# ---------------------------------------------------------------------------
# Catalogo del formulario de receta del SaaS (valores estandarizados).
# ---------------------------------------------------------------------------
# Esfera: dropdown habitual +20.00 a -20.00, pero admite alta miopia y afaquia extrema hasta 30.00 D.
_ESFERA_MAX_ABS_D = 30.0
# Cilindro: dropdown 0.00 a -8.00 en pasos de 0.25 (OpticaOptions::cilindro).
# Convencion de cilindro NEGATIVO: el catalogo nunca emite cilindro positivo;
# un positivo solo puede venir de datos legacy en convencion plus-cyl y se
# normaliza por transposicion (ver _transponer_a_cilindro_negativo).
_CILINDRO_MAX_ABS_D = 8.0
# Eje refractivo y queratometrico: 0..180 grados. El input del SaaS es un
# number libre SIN validacion de rango, asi que valores fuera de 0..180 se
# normalizan modulo 180 (el eje es ciclico) en vez de rechazarse.
_EJE_MIN, _EJE_MAX = 0, 180
# PPC y BUT: dropdowns 1..15 (clinica.blade.php).
_BUT_PPC_MIN, _BUT_PPC_MAX = 1, 15
# Uso de pantallas: select con exactamente estas claves.
_USO_PANTALLAS = ("lt2", "btw2_6", "gt6")

def _normalize_whitespace(value) -> str | None:
    if value is None:
        return None
    value = _WS_RE.sub(" ", str(value)).strip()
    return value or None


_MAX_TEXTO_CLINICO_LEN = 500


def _normalize_texto_clinico(value, campo: str, max_len: int = _MAX_TEXTO_CLINICO_LEN) -> str | None:
    value = _normalize_whitespace(value)
    if value is None:
        return None
    if len(value) > max_len:
        logger.warning(
            "%s excede %d caracteres, truncando (recibido: %d)",
            campo, max_len, len(value),
        )
        return value[:max_len].strip()
    return value


def _normalize_av(value) -> str | None:
    value = _normalize_whitespace(value)
    if value is None:
        return None
    match = _SNELLEN_RE.match(value)
    if match:
        return f"20/{int(match.group(1))}"
    return value


def _rango_o_none(value, minimo, maximo, campo: str):
    """Coercion tolerante: un valor fuera del rango fisico/de catalogo se
    descarta (None) en lugar de rechazar el request completo."""
    if value is None or minimo <= value <= maximo:
        return value
    logger.warning(
        "Valor fuera de catalogo descartado: %s=%s (rango %s..%s)",
        campo, value, minimo, maximo,
    )
    return None


def _normaliza_eje(value: int | None) -> int | None:
    """El eje es ciclico: 190 == 10, -20 == 160. El SaaS no valida rango."""
    if value is None or _EJE_MIN <= value <= _EJE_MAX:
        return value
    return value % 180


def _transponer_a_cilindro_negativo(ojo) -> None:
    """Normaliza una lectura en convencion plus-cyl a convencion negativa:
    esf' = esf + cil, cil' = -cil, eje' = (eje + 90) % 180.

    Solo se aplica al AKR (lectura del autorrefractometro, cuya convencion la
    fija el dispositivo y puede ser plus-cyl). Asi la comparacion esfera-a-esfera
    AR vs Rx (ar_rx_espasmo/cambio/variabilidad) queda en la misma convencion que
    la Rx final (que el dropdown del SaaS ya garantiza negativa). NO se aplica a
    la Rx final para no alterar el piso de esfera de hipermetropia_alta."""
    if ojo.cilindro is None or ojo.cilindro <= 0:
        return
    if ojo.esfera is not None:
        ojo.esfera = ojo.esfera + ojo.cilindro
    ojo.cilindro = -ojo.cilindro
    if ojo.eje is not None:
        ojo.eje = (ojo.eje + 90) % 180


class GraduacionOjo(BaseModel):
    esfera: float | None = None
    cilindro: float | None = None
    eje: int | None = None
    add: float | None = None
    av_sc: str | None = None
    av_cc: str | None = None

    @field_validator("eje")
    @classmethod
    def normalize_eje(cls, value):
        return _normaliza_eje(value)

    @field_validator("av_sc", "av_cc", mode="before")
    @classmethod
    def normalize_av(cls, value):
        return _normalize_av(value)

    @model_validator(mode="after")
    def normaliza_catalogo_saas(self):
        # 1) Descartar valores imposibles para el catalogo (dato corrupto/legacy).
        self.esfera = _rango_o_none(self.esfera, -_ESFERA_MAX_ABS_D, _ESFERA_MAX_ABS_D, "esfera")
        if self.cilindro is not None and abs(self.cilindro) > _CILINDRO_MAX_ABS_D:
            logger.warning("Cilindro fuera de catalogo descartado: %s", self.cilindro)
            self.cilindro = None
        # 2) La Rx final NO se transpone: el dropdown del SaaS garantiza cilindro
        # negativo, asi que en produccion nunca hay plus-cyl que transponer, y
        # hacerlo alteraria el piso de esfera de hipermetropia_alta (el ejemplo
        # +1.00/+8.00 de CORRELACIONES_CLINICAS.md 5.2 debe NO disparar). La
        # transposicion solo aplica al AKR (lectura de dispositivo, ver AkrOjo).
        # 3) El dropdown no emite add; el input es libre. El SaaS valida between:0,30
        # y prohibe negativos. add <= 0 significa "sin adicion" (o typo) y add > 30 es corrupto.
        if self.add is not None and (self.add <= 0 or self.add > 30.0):
            logger.warning("Add fuera de catalogo descartada: %s", self.add)
            self.add = None
        return self


class AkrOjo(BaseModel):
    esfera: float | None = None
    cilindro: float | None = None
    eje: int | None = None
    k1_d: float | None = None
    k1_mm: float | None = None
    k1_eje: int | None = None
    k2_d: float | None = None
    k2_mm: float | None = None
    k2_eje: int | None = None
    k_promedio_d: float | None = None
    k_promedio_mm: float | None = None
    k_cilindro: float | None = None
    k_cilindro_eje: int | None = None

    @field_validator("eje", "k1_eje", "k2_eje", "k_cilindro_eje")
    @classmethod
    def normalize_ejes(cls, value):
        return _normaliza_eje(value)

    @model_validator(mode="after")
    def normaliza_catalogo_saas(self):
        # Rangos fisicos alineados con RecetaValidationRules (mm 4..12,
        # K promedio 25..80, k_cilindro -30..30); fuera de rango = lectura corrupta -> se descarta.
        self.k1_d = _rango_o_none(self.k1_d, 25, 80, "akr.k1_d")
        self.k2_d = _rango_o_none(self.k2_d, 25, 80, "akr.k2_d")
        self.k_promedio_d = _rango_o_none(self.k_promedio_d, 25, 80, "akr.k_promedio_d")
        self.k1_mm = _rango_o_none(self.k1_mm, 4, 12, "akr.k1_mm")
        self.k2_mm = _rango_o_none(self.k2_mm, 4, 12, "akr.k2_mm")
        self.k_promedio_mm = _rango_o_none(self.k_promedio_mm, 4, 12, "akr.k_promedio_mm")
        self.k_cilindro = _rango_o_none(self.k_cilindro, -30, 30, "akr.k_cilindro")
        # Misma convencion negativa que la Rx final para que las comparaciones
        # AR vs Rx (esfera con esfera) no queden sesgadas por la convencion.
        _transponer_a_cilindro_negativo(self)
        return self


class Refraccion(BaseModel):
    od: GraduacionOjo = Field(default_factory=GraduacionOjo)
    oi: GraduacionOjo = Field(default_factory=GraduacionOjo)


class AkrSnapshot(BaseModel):
    ticket_id: int | None = None
    pd: float | None = None
    vd: float | None = None
    ker_index: float | None = None
    od: AkrOjo = Field(default_factory=AkrOjo)
    oi: AkrOjo = Field(default_factory=AkrOjo)

    @model_validator(mode="after")
    def normaliza_catalogo_saas(self):
        self.pd = _rango_o_none(self.pd, 0, 100, "akr.pd")
        self.vd = _rango_o_none(self.vd, 0, 30, "akr.vd")
        self.ker_index = _rango_o_none(self.ker_index, 1.3, 1.4, "akr.ker_index")
        return self


class DatosClinica(BaseModel):
    uso_pantallas: Literal["lt2", "btw2_6", "gt6"] | None = None
    anexos_oculares: str | None = None
    reflejos_pupilares: str | None = None
    motilidad_ocular: str | None = None
    confrontacion_campos_visuales: str | None = None
    fondo_de_ojo: str | None = None
    grid_de_amsler: str | None = None
    ojo_seco_but_seg: int | None = None
    cover_test: str | None = None
    ppc_cm: int | None = None
    recomendacion_seguimiento: str | None = None

    @field_validator("uso_pantallas", mode="before")
    @classmethod
    def normalize_uso_pantallas(cls, value):
        # Select cerrado en el SaaS; cualquier otra cosa es corrupcion -> None.
        if value is None or value in _USO_PANTALLAS:
            return value
        logger.warning("uso_pantallas fuera de catalogo descartado: %r", value)
        return None

    @field_validator("ojo_seco_but_seg", "ppc_cm")
    @classmethod
    def normalize_dropdown_1_15(cls, value, info):
        return _rango_o_none(value, _BUT_PPC_MIN, _BUT_PPC_MAX, info.field_name)

    @field_validator(
        "anexos_oculares",
        "reflejos_pupilares",
        "confrontacion_campos_visuales",
        "fondo_de_ojo",
        "grid_de_amsler",
        "recomendacion_seguimiento",
        mode="before",
    )
    @classmethod
    def normalize_texto_clinico(cls, value, info):
        return _normalize_texto_clinico(value, info.field_name)

    @field_validator("motilidad_ocular", mode="before")
    @classmethod
    def normalize_motilidad_ocular(cls, value):
        # El SaaS compone "Versiones: X\nDucciones: Y\n..." y lo aplana a una
        # linea antes de enviar; se colapsa whitespace por si llega multilinea.
        return _normalize_texto_clinico(value, "motilidad_ocular")

    @field_validator("cover_test", mode="before")
    @classmethod
    def normalize_cover_test(cls, value):
        if value is None:
            return None
        value = _COVER_DASH_RE.sub(" y ", str(value))
        return _normalize_texto_clinico(value, "cover_test")


class ContextoPaciente(BaseModel):
    edad: int | None = None
    ocupacion: str | None = None
    motivo_consulta: str | None = None

    @field_validator("edad")
    @classmethod
    def normalize_edad(cls, value):
        return _rango_o_none(value, 0, 125, "paciente.edad")

    @field_validator("ocupacion", mode="before")
    @classmethod
    def normalize_ocupacion(cls, value):
        value = _normalize_whitespace(value)
        if value is None:
            return None
        # Limite exacto en SaaS (RecetaValidationRules): max 120 caracteres
        if len(value) > 120:
            logger.warning("ocupacion excede 120 caracteres, truncando: len=%d", len(value))
            return value[:120].strip()
        return value

    @field_validator("motivo_consulta", mode="before")
    @classmethod
    def normalize_motivo_consulta(cls, value):
        value = _normalize_whitespace(value)
        if value is None:
            return None
        # Limite exacto en SaaS (RecetaValidationRules): max 1000 caracteres
        if len(value) > 1000:
            logger.warning("motivo_consulta excede 1000 caracteres, truncando: len=%d", len(value))
            return value[:1000].strip()
        return value


class ImpresionClinicaRequest(BaseModel):
    receta_id: str
    paciente: ContextoPaciente = Field(default_factory=ContextoPaciente)
    refraccion: Refraccion = Field(default_factory=Refraccion)
    akr: AkrSnapshot = Field(default_factory=AkrSnapshot)
    clinica: DatosClinica = Field(default_factory=DatosClinica)
    # tipo_lente NO se cierra a Literal: el catalogo canonico actual del SaaS
    # es monofocal, bifocal_blended, progresivo y flat_top, pero
    # el frontend puede ampliarlo sin coordinacion con la API. Se normaliza
    # espacio en blanco; la deteccion multifocal (incluido flat_top, que es un
    # bifocal de segmento) se hace por tokens en la capa de correlaciones.
    tipo_lente: str | None = None

    @field_validator("tipo_lente", mode="before")
    @classmethod
    def normalize_tipo_lente(cls, value):
        return _normalize_whitespace(value)
