"""Ensamblado CPU; las reglas de Qwen no se aplican al respaldo heredado."""
from dataclasses import dataclass

from app.patient_profile import build_patient_template

VERSION = "respaldo-paciente-v1"
LIMITE = 2000
SEPARADOR = "\n\n"


@dataclass(frozen=True)
class ResultadoPaciente:
    texto: str | None
    estado: str
    origen: str | None
    motivo: str | None = None
    regla: str | None = None
    acciones_sin_mapear: int = 0


def ensamblar(acciones, prosa=None):
    bloque = " ".join(acciones)
    texto = SEPARADOR.join(x for x in (bloque, prosa) if x)
    if len(texto) > LIMITE:
        raise ValueError("longitud")
    return texto or None


def respaldo(contexto, motivo, regla=None):
    acciones = contexto.contenido("acciones", [])
    plantilla = build_patient_template(contexto.perfil) if contexto.perfil is not None else None
    try:
        texto = ensamblar(acciones, plantilla)
    except ValueError:
        # Se descarta la prosa completa, nunca se corta una acción por caracteres.
        texto = ensamblar(acciones)
    estado = "plantilla" if texto else contexto.perfil.estado if contexto.perfil else "datos_incompletos"
    if estado == "aplicable":
        estado, motivo = "rechazada", "error"
    return ResultadoPaciente(texto, estado, "plantilla" if texto else None, motivo, regla,
                             contexto.acciones_sin_mapear)


def generada(contexto, candidato):
    prosa = " ".join(f["texto"].strip() for f in candidato["frases"])
    return ResultadoPaciente(ensamblar(contexto.contenido("acciones", []), prosa), "generada", "llm",
                             acciones_sin_mapear=contexto.acciones_sin_mapear)
