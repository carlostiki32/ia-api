"""Cadena opcional dentro del turno existente; proveedor y plazos inyectados.

`llamar` recibe una LlamadaPaciente y devuelve RespuestaEtapa (o raw JSON).
Debe cancelar su transporte al cancelarse la tarea. No hay reintentos, caché,
registro ni adquisición de GPU en este núcleo. El clínico final es solo dato.
"""
import asyncio
from dataclasses import dataclass
import time
from typing import Awaitable, Callable

from app.paciente.ensamblado import ResultadoPaciente, generada, respaldo
from app.paciente.prompts import (SYSTEM_REDACCION, SYSTEM_VERIFICACION, FORMATO_VERIFICACION,
    formato_redaccion, user_redaccion, user_verificacion, opciones)
from app.paciente.validador import parsear, estructura, validar
from app.tareas.presupuesto import PresupuestoExcedido, verificar

VERSION = "paciente-v1"
# Techos por llamada, no promesa de que cualquier contexto de entrada cabe.
MAX_TOKENS_ENTRADA = {"redaccion": 7000, "verificacion": 7400}


@dataclass(frozen=True)
class Plazos:
    redaccion: float = 15.0
    verificacion: float = 5.0
    paciente: float = 20.0
    global_peticion: float = 85.0
    reserva: float = 0.1
    minimo_redaccion: float = 1.0
    minimo_verificacion: float = 0.5
    ceder_interactiva: bool = True

    def __post_init__(self):
        if min(self.redaccion, self.verificacion, self.paciente, self.global_peticion,
               self.minimo_redaccion, self.minimo_verificacion) <= 0 or self.reserva < 0:
            raise ValueError("plazos")


@dataclass(frozen=True)
class LlamadaPaciente:
    etapa: str
    system: str
    user: str
    formato: dict
    opciones: dict
    timeout: float
    max_tokens_entrada: int
    tarea: str = "explicacion-paciente"
    politica: str = "estricto"
    think: bool = False
    max_retries: int = 1


@dataclass(frozen=True)
class RespuestaEtapa:
    contenido: object
    done_reason: str | None = None


def _respuesta(valor):
    if isinstance(valor, RespuestaEtapa): return valor
    if isinstance(valor, tuple) and len(valor) == 2:
        return RespuestaEtapa(valor[0], "length" if valor[1].get("done") is False else valor[1].get("done_reason"))
    return RespuestaEtapa(valor)


def construir_respaldo(contexto, motivo=None, regla=None):
    try:
        return respaldo(contexto, motivo, regla)
    except Exception:
        return ResultadoPaciente(None, "rechazada", None, "error", regla,
                                 getattr(contexto, "acciones_sin_mapear", 0))


async def generar(contexto, llamar: Callable[[LlamadaPaciente], Awaitable], *, llegada: float,
                  reloj=time.monotonic, hay_interactiva_esperando=lambda: False,
                  plazos=Plazos(), comprobar_presupuesto=verificar):
    """Nunca propaga un fallo de la rama paciente al clínico ya publicado.

    `llegada` y `reloj` comparten base monotónica; la llegada precede a la cola.
    La cancelación externa también devuelve respaldo, sin iniciar otra etapa.
    """
    def fallback(motivo, regla=None):
        return construir_respaldo(contexto, motivo, regla)

    try:
        inicio = reloj()
        limite = min(llegada + plazos.global_peticion, inicio + plazos.paciente)
        for etapa in ("redaccion", "verificacion"):
            ahora = reloj()
            restante = limite - ahora - plazos.reserva
            minimo = plazos.minimo_verificacion + (plazos.minimo_redaccion if etapa == "redaccion" else 0)
            techo = plazos.redaccion if etapa == "redaccion" else plazos.verificacion
            if restante < minimo or techo < (plazos.minimo_redaccion if etapa == "redaccion" else plazos.minimo_verificacion):
                return fallback("timeout")
            if plazos.ceder_interactiva and hay_interactiva_esperando():
                return fallback("ocupado")
            if etapa == "redaccion":
                system, user, formato = SYSTEM_REDACCION, user_redaccion(contexto), formato_redaccion(contexto)
                # Reservar además la ventana mínima útil para verificar.
                timeout = min(techo, restante - plazos.minimo_verificacion)
            else:
                system, user, formato = SYSTEM_VERIFICACION, user_verificacion(contexto, obj), FORMATO_VERIFICACION
                timeout = min(techo, restante)
            opts = opciones(etapa)
            comprobar_presupuesto(system, user, opts["num_predict"], MAX_TOKENS_ENTRADA[etapa], politica="estricto")
            restante = limite - reloj() - plazos.reserva
            if restante < minimo:
                return fallback("timeout")
            timeout = min(timeout, restante - (plazos.minimo_verificacion if etapa == "redaccion" else 0))
            llamada = LlamadaPaciente(etapa, system, user, formato, opts, timeout, MAX_TOKENS_ENTRADA[etapa])
            resp = _respuesta(await asyncio.wait_for(llamar(llamada), timeout))
            if reloj() >= limite - plazos.reserva:
                return fallback("timeout")
            if etapa == "redaccion":
                try:
                    obj = parsear(resp.contenido)
                except (ValueError, TypeError, RecursionError):
                    return fallback("validacion", "json")
                if resp.done_reason != "length" and estructura(obj, contexto, admitir_abstencion=True) and obj["frases"] == []:
                    return fallback("abstencion")
                regla = validar(obj, contexto, done_reason=resp.done_reason)
                if regla:
                    return fallback("validacion", regla)
            else:
                try:
                    veredicto = parsear(resp.contenido)
                    if resp.done_reason == "length" or not isinstance(veredicto, dict) or set(veredicto) != {"valido"} or veredicto["valido"] is not True:
                        return fallback("verificacion")
                except (ValueError, TypeError, RecursionError):
                    return fallback("verificacion")
        try:
            return generada(contexto, obj)
        except ValueError:
            return fallback("validacion", "longitud")
    except PresupuestoExcedido:
        return fallback("presupuesto")
    except (TimeoutError, asyncio.CancelledError):
        return fallback("timeout")
    except Exception:
        return fallback("error")
