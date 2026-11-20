"""Orquestación sin datos personales en prompts ni contenido en logs."""
import asyncio
import hashlib
import json
import logging
import time  # noqa: F401  (las pruebas de caché parchean servicio.time)

from app.config import settings
from app.gpu_scheduler import GPUOcupada
from app.patient_profile import word_count
from app.providers import ollama
from app.seguimiento.catalogo import (
    APERTURAS_V2, CIERRES, CIERRES_POR_ID, BAJA, CATALOGO_VERSION, PROMPT_VERSION,
    VERIFICACION_VERSION, CONTRATO_VERSION, FRASES_FECHA, FRASES_USO,
)
from app.seguimiento.combinacion import ordenar_hechos, seleccionar_respaldo
from app.seguimiento.elegibilidad import hechos_elegibles
from app.seguimiento.fechas import formatear_fecha, periodo_en_palabras
from app.seguimiento.prompts import (
    SYSTEM_PROMPT_REDACCION, SYSTEM_PROMPT_VERIFICACION, FORMATO_VERIFICACION,
    build_user_prompt_redaccion, build_user_prompt_verificacion, formato_redaccion,
)
from app.seguimiento.schemas import Generacion, Partes, SeguimientoWhatsappResponse
from app.seguimiento.uso import (
    FORMATO_USO, SYSTEM_PROMPT_USO, USO_VERSION, build_user_prompt_uso, parsear_uso, reglas_uso,
)
from app.seguimiento.validador import ensamblar, validar
from app.tareas.nucleo import CacheTareas as SeguimientoCache
from app.tareas.presupuesto import PresupuestoExcedido

logger = logging.getLogger(__name__)
seguimiento_cache = SeguimientoCache()


def opciones_generacion(req, *, verificacion: bool = False, uso: bool = False) -> dict:
    temp = 0.0 if (verificacion or uso) else settings.seguimiento_temperature
    predict = 32 if uso else (settings.verificacion_num_predict if verificacion else settings.seguimiento_num_predict)
    seed = settings.ollama_seed if (verificacion or uso or settings.ollama_seed < 0) else (settings.ollama_seed + req.variante if req is not None else "ollama_seed + variante")
    return {
        **ollama.build_options(),
        "temperature": temp,
        "num_predict": predict,
        "seed": seed,
    }


def clave_cache(req) -> str:
    datos = req.model_dump(mode="json", exclude={"paciente_ref", "contexto_uso"})
    if req.contexto_uso is not None:
        ctx_json = json.dumps(req.contexto_uso.model_dump(mode="json"), sort_keys=True, ensure_ascii=False)
        datos["contexto_uso_sha256"] = hashlib.sha256(ctx_json.encode()).hexdigest()
    else:
        datos["contexto_uso_sha256"] = None
    datos.update(
        modelo=settings.ollama_model,
        versiones=[CATALOGO_VERSION, PROMPT_VERSION, VERIFICACION_VERSION, USO_VERSION, CONTRATO_VERSION],
        uso=opciones_generacion(req, uso=True),
        redaccion=opciones_generacion(req),
        verificacion=opciones_generacion(req, verificacion=True),
    )
    return hashlib.sha256(json.dumps(datos, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def calcular_indice_rotacion(req, uso_lentes: str) -> int:
    clave_rotacion = f"{req.estado_seguimiento}:{uso_lentes}:{req.tipo_lente}:{req.costo}:{req.variante}:{req.recetas_previas}"
    return hashlib.sha256(clave_rotacion.encode("utf-8")).digest()[9]


def obtener_grupo_apertura(req) -> str:
    if req.ya_notificado_en_ciclo:
        return "AP_SEG"
    if req.estado_seguimiento == "vencido":
        return "AP_VENC"
    if req.recetas_previas >= 1:
        return "AP_PROX_CONT"
    return "AP_PROX_PRIM"


def obtener_grupo_fecha(req) -> str:
    if req.estado_seguimiento == "proximo" and not req.ya_notificado_en_ciclo and req.fecha_revision is not None:
        if req.meses_periodo is not None and 3 <= req.meses_periodo <= 24:
            return "P"
        return "PS"
    return "N"


def obtener_frase_fecha(req, idx: int) -> str:
    grupo = obtener_grupo_fecha(req)
    opciones = FRASES_FECHA[grupo]
    _, plantilla = opciones[idx % len(opciones)]
    if grupo == "P":
        return plantilla.format(
            fecha=formatear_fecha(req.fecha_revision),
            periodo=periodo_en_palabras(req.meses_periodo),
        )
    if grupo == "PS":
        return plantilla.format(fecha=formatear_fecha(req.fecha_revision))
    return plantilla


def obtener_frase_uso(uso_lentes: str, idx: int) -> str:
    opciones = FRASES_USO[uso_lentes]
    return opciones[idx % len(opciones)][1]


def obtener_cierres_permitidos(req) -> list[tuple[str, str]]:
    return CIERRES["INC"] if req.costo == "incluida" else CIERRES["COS"]


def respaldo(req, elegibles=None, clave=None, motivo="ollama_error", uso_lentes=None, origen_uso=None):
    if uso_lentes is None:
        uso_lentes = reglas_uso(req)
        origen_uso = "reglas"
    elif origen_uso is None:
        origen_uso = "reglas"

    elegibles = hechos_elegibles(req, uso_lentes) if elegibles is None else elegibles
    idx = calcular_indice_rotacion(req, uso_lentes)

    grupo_ap = obtener_grupo_apertura(req)
    opciones_ap = APERTURAS_V2[grupo_ap]
    ap_id, ap_texto = opciones_ap[idx % len(opciones_ap)]

    frase_uso = obtener_frase_uso(uso_lentes, idx)
    frase_fecha = obtener_frase_fecha(req, idx)
    hechos_ids = seleccionar_respaldo(elegibles, req.recetas_previas)

    cierres = obtener_cierres_permitidos(req)
    cierre_id, cierre_texto = cierres[idx % len(cierres)]

    cuerpo = ensamblar(ap_texto, frase_uso, frase_fecha, hechos_ids, cierre_texto).rsplit("\n\n", 1)[0]
    if word_count(cuerpo) < 60:
        cierre_id, cierre_texto = cierres[(idx + 1) % len(cierres)]

    partes = Partes(
        apertura=ap_texto,
        apertura_id=ap_id,
        frase_uso=frase_uso,
        frase_fecha=frase_fecha,
        hechos=hechos_ids,
        cierre=cierre_texto,
        cierre_id=cierre_id,
        baja=BAJA,
    )
    clave_final = clave or clave_cache(req)
    return SeguimientoWhatsappResponse(
        estado="plantilla",
        mensaje=ensamblar(ap_texto, frase_uso, frase_fecha, hechos_ids, cierre_texto),
        partes=partes,
        motivo=motivo,
        hechos_elegibles=elegibles,
        generacion=Generacion(
            origen="catalogo",
            modelo=None,
            catalogo_version=CATALOGO_VERSION,
            prompt_version=PROMPT_VERSION,
            base_hash_api=clave_final,
            cached=False,
        ),
        uso_lentes=uso_lentes,
        origen_uso=origen_uso,
    )


class FalloGeneracion(Exception):
    pass


def parsear_redaccion(raw: str, cierres_ids: list[str]) -> dict:
    try:
        obj = json.loads(raw)
        if (
            not isinstance(obj, dict)
            or set(obj) != {"apertura", "hechos", "cierre"}
            or not isinstance(obj["apertura"], str)
            or not isinstance(obj["cierre"], str)
            or obj["cierre"] not in cierres_ids
            or not isinstance(obj["hechos"], list)
            or len(obj["hechos"]) > 1
            or any(not isinstance(id, str) for id in obj["hechos"])
        ):
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
        logger.info(
            "Seguimiento paciente_ref=%s estado=generada motivo=cache uso_lentes=%s origen_uso=%s hechos=%s prioridad=fondo",
            req.paciente_ref, cache.uso_lentes, cache.origen_uso, cache.partes.hechos,
        )
        return cache

    # 1. Etapa uso
    uso_lentes = None
    origen_uso = "reglas"
    try:
        if ctx is not None:
            raw_uso, _ = await ctx.llamar(
                'uso', SYSTEM_PROMPT_USO, build_user_prompt_uso(req), format=FORMATO_USO,
            )
        else:
            async with planificador.turno("fondo"):
                raw_uso, _ = await ollama.call(
                    SYSTEM_PROMPT_USO, build_user_prompt_uso(req), client,
                    options=opciones_generacion(req, uso=True),
                    format=FORMATO_USO, max_retries=1,
                )
        parsed = parsear_uso(raw_uso, req)
        if parsed is not None:
            uso_lentes = parsed
            origen_uso = "llm"
        else:
            uso_lentes = reglas_uso(req)
            origen_uso = "reglas"
    except (GPUOcupada, PresupuestoExcedido):
        raise
    except Exception:
        uso_lentes = reglas_uso(req)
        origen_uso = "reglas"

    elegibles = hechos_elegibles(req, uso_lentes)
    cierres_permitidos = obtener_cierres_permitidos(req)
    cierres_ids = [id for id, _ in cierres_permitidos]
    idx = calcular_indice_rotacion(req, uso_lentes)
    frase_uso = obtener_frase_uso(uso_lentes, idx)
    frase_fecha = obtener_frase_fecha(req, idx)

    async def llamar_etapa(etapa_nombre, system, user, formato, *, verificacion=False):
        if ctx is not None:
            raw, _ = await ctx.llamar(etapa_nombre, system, user, format=formato)
            return raw
        async with planificador.turno("fondo"):
            raw, _ = await ollama.call(
                system, user, client,
                options=opciones_generacion(req, verificacion=verificacion),
                format=formato, max_retries=1,
            )
            return raw

    async def cadena():
        try:
            raw_red = await llamar_etapa(
                'redaccion',
                SYSTEM_PROMPT_REDACCION,
                build_user_prompt_redaccion(req, elegibles, uso_lentes, cierres_ids),
                formato_redaccion(elegibles, cierres_ids),
            )
        except (GPUOcupada, PresupuestoExcedido):
            raise
        except Exception as exc:
            raise FalloGeneracion("ollama_error") from exc

        obj = parsear_redaccion(raw_red, cierres_ids)
        apertura = obj["apertura"]
        hechos_ids = ordenar_hechos(obj["hechos"])
        cierre_id = obj["cierre"]
        cierre_texto = CIERRES_POR_ID[cierre_id]

        partes = Partes(
            apertura=apertura,
            apertura_id=None,
            frase_uso=frase_uso,
            frase_fecha=frase_fecha,
            hechos=hechos_ids,
            cierre=cierre_texto,
            cierre_id=cierre_id,
            baja=BAJA,
        )
        mensaje = ensamblar(apertura, frase_uso, frase_fecha, hechos_ids, cierre_texto)
        regla = validar(req, partes, elegibles, uso_lentes, mensaje=mensaje)
        if regla:
            raise FalloGeneracion("validacion:" + regla)

        try:
            raw_ver = await llamar_etapa(
                'verificacion',
                SYSTEM_PROMPT_VERIFICACION,
                build_user_prompt_verificacion(apertura),
                FORMATO_VERIFICACION,
                verificacion=True,
            )
            ver = json.loads(raw_ver)
            if not isinstance(ver, dict) or ver != {"afirma_algo_de_salud": False} or type(ver.get("afirma_algo_de_salud")) is not bool:
                raise ValueError
        except (GPUOcupada, PresupuestoExcedido):
            raise
        except Exception as exc:
            raise FalloGeneracion("verificacion") from exc

        return SeguimientoWhatsappResponse(
            estado="generada",
            mensaje=mensaje,
            partes=partes,
            motivo=None,
            hechos_elegibles=elegibles,
            generacion=Generacion(
                origen="llm",
                modelo=settings.ollama_model,
                catalogo_version=CATALOGO_VERSION,
                prompt_version=PROMPT_VERSION,
                base_hash_api=clave,
                cached=False,
            ),
            uso_lentes=uso_lentes,
            origen_uso=origen_uso,
        )

    try:
        resultado = await asyncio.wait_for(cadena(), settings.seguimiento_timeout)
    except PresupuestoExcedido:
        resultado = respaldo(req, elegibles, clave, "presupuesto", uso_lentes=uso_lentes, origen_uso=origen_uso)
    except GPUOcupada:
        resultado = respaldo(req, elegibles, clave, "ia_ocupada", uso_lentes=uso_lentes, origen_uso=origen_uso)
    except TimeoutError:
        resultado = respaldo(req, elegibles, clave, "ia_timeout", uso_lentes=uso_lentes, origen_uso=origen_uso)
    except FalloGeneracion as exc:
        resultado = respaldo(req, elegibles, clave, str(exc), uso_lentes=uso_lentes, origen_uso=origen_uso)

    seguimiento_cache.put(clave, resultado)
    logger.info(
        "Seguimiento paciente_ref=%s estado=%s motivo=%s uso_lentes=%s origen_uso=%s hechos=%s prioridad=fondo",
        req.paciente_ref, resultado.estado, resultado.motivo, resultado.uso_lentes, resultado.origen_uso, resultado.partes.hechos,
    )
    return resultado
