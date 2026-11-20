"""Orquestación sin datos personales en prompts ni contenido en logs."""
import asyncio
from collections import OrderedDict
import hashlib
import json
import logging
import threading
import time

from app.config import settings
from app.gpu_scheduler import GPUOcupada
from app.providers import ollama
from app.seguimiento.catalogo import (
    APERTURAS, INVITACIONES, BAJA, CATALOGO_VERSION, PROMPT_VERSION, VERIFICACION_VERSION, CONTRATO_VERSION,
)
from app.seguimiento.combinacion import ordenar_hechos, seleccionar_respaldo
from app.seguimiento.elegibilidad import hechos_elegibles
from app.seguimiento.prompts import (
    SYSTEM_PROMPT_REDACCION, SYSTEM_PROMPT_VERIFICACION, FORMATO_VERIFICACION,
    build_user_prompt_redaccion, build_user_prompt_verificacion, formato_redaccion,
)
from app.seguimiento.schemas import SeguimientoWhatsappResponse
from app.seguimiento.validador import ensamblar, validar

logger = logging.getLogger(__name__)


def opciones_generacion(req, *, verificacion=False) -> dict:
    return {**ollama.build_options(),
            "temperature": 0.0 if verificacion else settings.seguimiento_temperature,
            "num_predict": settings.verificacion_num_predict if verificacion else settings.seguimiento_num_predict,
            "seed": settings.ollama_seed if verificacion or settings.ollama_seed < 0 else settings.ollama_seed + req.variante if req is not None else "ollama_seed + variante"}


def clave_cache(req) -> str:
    datos = req.model_dump(mode="json", exclude={"paciente_ref"})
    datos.update(modelo=settings.ollama_model,
                 versiones=[CATALOGO_VERSION, PROMPT_VERSION, VERIFICACION_VERSION, CONTRATO_VERSION],
                 redaccion=opciones_generacion(req), verificacion=opciones_generacion(req, verificacion=True))
    return hashlib.sha256(json.dumps(datos, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


from app.tareas.nucleo import CacheTareas as SeguimientoCache
from app.tareas.presupuesto import PresupuestoExcedido


seguimiento_cache = SeguimientoCache()


def respuesta(req, elegibles, clave, apertura, ids, invitacion, motivo=None):
    return SeguimientoWhatsappResponse(
        estado="plantilla" if motivo else "generada", mensaje=ensamblar(apertura, ids, invitacion),
        partes={"apertura": apertura, "hechos": ids, "invitacion": invitacion, "baja": BAJA},
        motivo=motivo, hechos_elegibles=elegibles,
        generacion={"origen": "catalogo" if motivo else "llm", "modelo": None if motivo else settings.ollama_model,
                    "catalogo_version": CATALOGO_VERSION, "prompt_version": PROMPT_VERSION,
                    "base_hash_api": clave, "cached": False},
    )


def respaldo(req, elegibles=None, clave=None, motivo="ollama_error"):
    elegibles = hechos_elegibles(req) if elegibles is None else elegibles
    ids = seleccionar_respaldo(elegibles, req.recetas_previas)
    a = ("A4" if req.estado_seguimiento == "vencido" else "A3" if req.ya_notificado_en_ciclo
         else "A6" if req.tramo_edad == "60_mas" and req.recetas_previas >= 2
         else "A9" if req.costo == "con_costo" else "A1")
    i = ("I3" if req.costo == "con_costo" and "con_costo_claro" not in ids
         else "I2" if req.costo == "incluida" and "incluida_sin_costo" not in ids else "I1")
    return respuesta(req, elegibles, clave or clave_cache(req), APERTURAS[a], ids, INVITACIONES[i], motivo)


class FalloGeneracion(Exception):
    pass


def parsear_redaccion(raw):
    try:
        obj = json.loads(raw)
        if (not isinstance(obj, dict) or set(obj) != {"apertura", "hechos", "invitacion"} or
            not isinstance(obj["apertura"], str) or not isinstance(obj["invitacion"], str) or
            not isinstance(obj["hechos"], list) or any(not isinstance(id, str) for id in obj["hechos"])):
            raise ValueError
        return obj
    except (ValueError, TypeError) as exc:
        raise FalloGeneracion("json_invalido") from exc


async def generar(req, client, planificador, ctx=None):
    if not settings.seguimiento_llm_habilitado:
        return respaldo(req, motivo="ia_deshabilitada")
    clave = clave_cache(req)
    cache = seguimiento_cache.get(clave)
    if cache is not None:
        logger.info("Seguimiento paciente_ref=%s estado=generada motivo=cache hechos=%s prioridad=fondo",
                    req.paciente_ref, cache.partes.hechos)
        return cache
    elegibles = hechos_elegibles(req)

    async def llamar(system, user, formato, *, verificacion=False):
        if ctx is not None:
            raw, _ = await ctx.llamar('verificacion' if verificacion else 'redaccion', system, user, format=formato)
            return raw
        async with planificador.turno("fondo"):
            raw, _ = await ollama.call(system, user, client, options=opciones_generacion(req, verificacion=verificacion),
                                       format=formato, max_retries=1)
            return raw

    async def cadena():
        try:
            raw = await llamar(SYSTEM_PROMPT_REDACCION, build_user_prompt_redaccion(req, elegibles), formato_redaccion(elegibles))
        except (GPUOcupada, PresupuestoExcedido):
            raise
        except Exception as exc:
            raise FalloGeneracion("ollama_error") from exc
        obj = parsear_redaccion(raw)
        ids = ordenar_hechos(obj["hechos"])
        apertura, invitacion = obj["apertura"], obj["invitacion"]
        regla = validar(req, apertura, ids, invitacion, elegibles)
        if regla:
            raise FalloGeneracion("validacion:" + regla)
        try:
            raw = await llamar(SYSTEM_PROMPT_VERIFICACION, build_user_prompt_verificacion(apertura, invitacion),
                               FORMATO_VERIFICACION, verificacion=True)
            verificacion = json.loads(raw)
            if not isinstance(verificacion, dict) or verificacion != {"afirma_algo_de_salud": False} or type(verificacion.get("afirma_algo_de_salud")) is not bool:
                raise ValueError
        except (GPUOcupada, PresupuestoExcedido):
            raise
        except Exception as exc:
            raise FalloGeneracion("verificacion") from exc
        return respuesta(req, elegibles, clave, apertura, ids, invitacion)

    try:
        resultado = await asyncio.wait_for(cadena(), settings.seguimiento_timeout)
    except PresupuestoExcedido:
        resultado = respaldo(req, elegibles, clave, "presupuesto")
    except GPUOcupada:
        resultado = respaldo(req, elegibles, clave, "ia_ocupada")
    except TimeoutError:
        resultado = respaldo(req, elegibles, clave, "ia_timeout")
    except FalloGeneracion as exc:
        resultado = respaldo(req, elegibles, clave, str(exc))
    seguimiento_cache.put(clave, resultado)
    logger.info("Seguimiento paciente_ref=%s estado=%s motivo=%s hechos=%s prioridad=fondo",
                req.paciente_ref, resultado.estado, resultado.motivo, resultado.partes.hechos)
    return resultado
