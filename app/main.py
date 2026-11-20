import asyncio
import hashlib
import hmac
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.gpu_scheduler import gpu_scheduler
from app.cache import inference_cache
from app.clinical_data import has_clinical_data
from app.config import settings
from app.correlaciones import nombres_correlaciones_activas
from app.inference import (
    CONTEXT_OVERFLOW_PREFIX,
    GeneracionIncompletaError,
    respaldo_determinista,
    run_inference,
)
from app.observability import request_id_var
from app.schemas import ImpresionClinicaRequest
from app.dual_contract import PIPELINE_VERSION, DualInferenceResult

# Timeout total de la inferencia para asyncio.wait_for.
_INFERENCE_TIMEOUT = settings.ollama_timeout

logger = logging.getLogger(__name__)

_bearer_scheme = HTTPBearer(auto_error=False)


def _safe_id(receta_id: str) -> str:
    return hashlib.sha256(receta_id.encode()).hexdigest()[:10]


def _origen_request(request: Request) -> str:
    """IP real del cliente. Detras de Cloudflare Tunnel el socket es local, asi
    que se prefieren los headers que Cloudflare agrega con la IP de origen."""
    return (
        request.headers.get("cf-connecting-ip")
        or request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        or (request.client.host if request.client else "?")
    )


def _payload_resumen(req: ImpresionClinicaRequest) -> str:
    """Resumen compacto del payload para el log: QUE campos vienen (no su
    contenido)."""

    def _campos(model) -> list[str]:
        return [k for k, v in model.model_dump().items() if v is not None]

    rx = "+".join(
        lbl for lbl, ojo in (("OD", req.refraccion.od), ("OI", req.refraccion.oi))
        if _campos(ojo)
    )
    akr = "+".join(
        lbl for lbl, ojo in (("OD", req.akr.od), ("OI", req.akr.oi))
        if _campos(ojo)
    )
    clinica = _campos(req.clinica)
    partes = [
        f"edad={req.paciente.edad if req.paciente.edad is not None else '?'}",
        f"rx={rx or 'no'}",
        f"akr={akr or 'no'}",
        f"clinica=[{', '.join(clinica)}]" if clinica else "clinica=no",
    ]
    if req.tipo_lente:
        partes.append(f"lente={req.tipo_lente}")
    return " ".join(partes)


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.ollama_num_ctx < 8192:
        logger.warning("OLLAMA_NUM_CTX=%d < 8192: recetas con AKR y datos clínicos pueden devolver 413",
                       settings.ollama_num_ctx)
    # httpx read timeout: ollama_timeout + margen suficiente para que asyncio.wait_for
    # sea siempre el mecanismo de timeout activo, nunca httpx. connect/write/pool
    # se limitan por separado para que un socket colgado no consuma el presupuesto completo.
    _read_timeout = max(settings.ollama_timeout * 1.2, settings.ollama_timeout + 10)
    _httpx_timeout = httpx.Timeout(connect=5.0, read=_read_timeout, write=5.0, pool=5.0)
    app.state.http_client = httpx.AsyncClient(timeout=_httpx_timeout)
    logger.info("HTTP client started (read_timeout=%.0fs) for model %s",
                _read_timeout, settings.ollama_model)

    try:
        # num_ctx debe coincidir con produccion para que Ollama asigne el
        # KV cache definitivo aqui y no en el primer request real.
        await app.state.http_client.post(
            f"{settings.ollama_url}/api/chat",
            json={
                "model":   settings.ollama_model,
                "messages": [{"role": "user", "content": "ok"}],
                "stream":  False,
                "think":   False,
                "options": {
                    "num_predict": 1,
                    "num_ctx": min(settings.ollama_num_ctx, settings.limite_contexto_tokens, 8192),
                },
            },
            timeout=settings.ollama_timeout,
        )
        logger.info("Warmup completado — modelo en VRAM")
    except Exception as exc:
        logger.warning("Warmup fallido (no critico): %s", exc)

    from app.tareas.presupuesto import contador
    verificacion = asyncio.create_task(contador.mantener(app.state.http_client))
    try:
        yield
    finally:
        verificacion.cancel()
        await asyncio.gather(verificacion, return_exceptions=True)
        await contador.cerrar()
        await app.state.http_client.aclose()
        logger.info("HTTP client closed")


def rutas_documentacion(habilitadas: bool) -> dict[str, str | None]:
    """/docs, /redoc y /openapi.json solo existen si DOCS_HABILITADOS=true (apagadas en produccion)."""
    return {
        "docs_url": "/docs" if habilitadas else None,
        "redoc_url": "/redoc" if habilitadas else None,
        "openapi_url": "/openapi.json" if habilitadas else None,
    }


app = FastAPI(
    title="ia-api - Inferencia Clinica Optometrica",
    version="2.1.0",
    lifespan=lifespan,
    **rutas_documentacion(settings.docs_habilitados),
)


class LimiteCuerpoMiddleware:
    """Middleware ASGI que valida el tamaño del cuerpo antes de parsear.

    Si Content-Length excede max_cuerpo_bytes responde 413 sin leer el cuerpo.
    Si no hay Content-Length o viene fragmentado, envuelve receive a nivel ASGI
    y corta por conteo acumulado.
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = dict(scope.get("headers", []))
        content_length_raw = headers.get(b"content-length")
        max_bytes = settings.max_cuerpo_bytes

        if content_length_raw is not None:
            try:
                content_length = int(content_length_raw.decode("latin-1"))
                if content_length > max_bytes:
                    response = JSONResponse(
                        status_code=413,
                        content={"detail": f"El cuerpo de la petición excede el límite de {max_bytes} bytes."},
                    )
                    await response(scope, receive, send)
                    return
            except ValueError:
                pass

        bytes_recibidos = 0

        async def custom_receive() -> dict[str, Any]:
            nonlocal bytes_recibidos
            message = await receive()
            if message["type"] == "http.request":
                cuerpo = message.get("body", b"")
                bytes_recibidos += len(cuerpo)
                if bytes_recibidos > max_bytes:
                    raise HTTPException(
                        status_code=413,
                        detail=f"El cuerpo de la petición excede el límite de {max_bytes} bytes.",
                    )
            return message

        try:
            await self.app(scope, custom_receive, send)
        except HTTPException as exc:
            if exc.status_code == 413:
                response = JSONResponse(
                    status_code=413,
                    content={"detail": exc.detail},
                )
                await response(scope, receive, send)
            else:
                raise


app.add_middleware(LimiteCuerpoMiddleware)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Asigna un request-id a cada request (propaga X-Request-ID del cliente o
    genera uno), lo inyecta en todos los logs via contextvar, mide la duracion
    total y la loggea junto al status. El id vuelve al cliente en el header
    X-Request-ID para correlacionar con los logs del SaaS."""
    request.state.llegada = time.monotonic()
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:8]
    from app.tareas.presupuesto import politica_actual, tarea_actual
    politica_token = politica_actual.set(settings.presupuesto_receta_sin_exacto if request.url.path in
        ('/inferencia/impresion-clinica', '/v1/inferencia/receta-clinica') else 'estricto')
    tarea_token = tarea_actual.set('receta-clinica' if request.url.path in
        ('/inferencia/impresion-clinica', '/v1/inferencia/receta-clinica') else None)
    token = request_id_var.set(rid)
    # /health se consulta constantemente (monitoreo): solo a nivel DEBUG.
    log = logger.debug if request.url.path == "/health" else logger.info
    log("→ %s %s (origen %s)", request.method, request.url.path, _origen_request(request))
    start = time.perf_counter()
    try:
        response = await call_next(request)
        log(
            "← %s %s %d en %.2fs",
            request.method, request.url.path,
            response.status_code, time.perf_counter() - start,
        )
        if tarea_actual.get():
            from app.tareas.nucleo import metricas
            metricas.solicitud(tarea_actual.get(), response.status_code, 'presupuesto' if response.status_code == 413 else None, time.perf_counter()-start)
        response.headers["X-Request-ID"] = rid
        return response
    except Exception:
        # Error NO manejado por el endpoint (los HTTPException ya salieron como
        # respuesta): traceback completo a logs/errors.log antes de propagar.
        logger.exception(
            "✗ %s %s fallo sin manejar tras %.2fs",
            request.method, request.url.path, time.perf_counter() - start,
        )
        raise
    finally:
        request_id_var.reset(token)
        politica_actual.reset(politica_token)
        tarea_actual.reset(tarea_token)


def get_http_client(request: Request) -> httpx.AsyncClient:
    client = getattr(request.app.state, "http_client", None)
    if client is None:
        raise RuntimeError("HTTP client not initialized")
    return client


def verify_api_key(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Depends(_bearer_scheme),
    ],
) -> None:
    if not settings.api_key:
        logger.error("Auth imposible: API_KEY no esta configurada en el servidor")
        raise HTTPException(
            status_code=500,
            detail="API_KEY no configurada en el servidor.",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        logger.warning("Auth rechazada (401): falta header 'Authorization: Bearer'")
        raise HTTPException(
            status_code=401,
            detail="Header Authorization requerido: Bearer <token>",
        )
    # compare_digest sobre str lanza TypeError con caracteres no ASCII (Bearer «ñ» -> 500): se compara en bytes.
    if not hmac.compare_digest(credentials.credentials.encode("utf-8"), settings.api_key.encode("utf-8")):
        logger.warning(
            "Auth rechazada (401): token invalido (longitud recibida: %d)",
            len(credentials.credentials),
        )
        raise HTTPException(status_code=401, detail="Token invalido.")


@asynccontextmanager
async def _inference_slot(safe_id: str):
    async with gpu_scheduler.turno("interactiva"):
        logger.info("Turno GPU adquirido [%s] prioridad=interactiva", safe_id)
        try:
            yield
        finally:
            logger.info("Turno GPU liberado [%s] prioridad=interactiva", safe_id)


def _inference_response(req, result, correlaciones, cache_key, *, cached, cache_hits=None):
    if req.salida_version == "clinica-v1":
        response = {"status": "ok", "impresion_clinica": result, "correlaciones_activadas": correlaciones}
        if cached:
            response["cached"] = True
        return response
    if not isinstance(result, DualInferenceResult):
        raise TypeError("Resultado incompatible con el contrato dual")
    return {
        "status": "ok", "impresion_clinica": result.impresion_clinica,
        "explicacion_paciente": result.explicacion_paciente,
        "explicacion_paciente_estado": result.explicacion_paciente_estado,
        "correlaciones_activadas": correlaciones, "salida_version": req.salida_version,
        "cached": cached,
        "generacion": {
            "origen_clinico": "llm", "origen_explicacion": result.origen_explicacion,
            "modelo": settings.ollama_model, "pipeline_version": PIPELINE_VERSION,
            "base_hash_api": cache_key,
            "paciente_version": result.paciente_version,
            "motivo_explicacion": result.motivo_explicacion,
            "acciones_sin_mapear": result.acciones_sin_mapear,
            "cache": cache_hits or {"clinico": cached, "paciente": cached},
        },
    }


async def _crear_dual(req, client, correlaciones, sid, llegada):
    from app.gpu_scheduler import GPUOcupada
    from app.paciente.integracion import PuntoControlPaciente, completar
    from app.tareas.nucleo import metricas
    from app.tareas.presupuesto import PresupuestoExcedido

    # La clave clínica histórica se comparte entre las dos presentaciones.
    clinica_req = req.model_copy(update={"salida_version": "clinica-v1"})
    clave_clinica = inference_cache.build_key(clinica_req)
    punto = PuntoControlPaciente(publicar_clinico=lambda texto:
        inference_cache.put(clinica_req, texto, key=clave_clinica))

    def recuperar_clinico():
        valor = inference_cache.get(clinica_req, key=clave_clinica)
        if valor is not None:
            punto.cache_clinico = True
            punto.publicar(req, valor)
        return valor

    def esperando():
        return gpu_scheduler.estadisticas["en_espera_interactiva"] > 0

    async def trabajo():
        if recuperar_clinico() is not None:
            valor = punto.recuperado()
            if valor is not None:
                return valor
            if not settings.paciente_llm_habilitado:
                return punto.respaldo(None)
        # Tanto el clínico nuevo como el paciente pendiente usan un único turno.
        async with _inference_slot(sid):
            if punto.clinico is None:
                recuperar_clinico()  # Deduplicar tras la espera.
            if punto.clinico is not None:
                return await completar(punto, client, llegada=llegada,
                                       hay_interactiva_esperando=esperando)
            return await run_inference(req, client, punto_control=punto, llegada=llegada,
                                       hay_interactiva_esperando=esperando)

    try:
        restante = min(settings.plazo_global_receta_s, _INFERENCE_TIMEOUT) - (time.monotonic() - llegada)
        if restante <= 0:
            # Aún puede existir clínico cacheado, aunque el plazo ya haya vencido.
            recuperar_clinico()
            raise TimeoutError
        result = await asyncio.wait_for(trabajo(), timeout=restante)
    except (GPUOcupada, TimeoutError) as exc:
        if punto.clinico is None:
            raise HTTPException(status_code=503 if isinstance(exc, GPUOcupada) else 504,
                detail="Servidor ocupado. Hay demasiadas peticiones en espera. Intente de nuevo en unos segundos."
                       if isinstance(exc, GPUOcupada) else "Ollama no respondio a tiempo. Intente de nuevo.")
        result = punto.respaldo("ocupado" if isinstance(exc, GPUOcupada) else "timeout")
    except Exception as exc:
        if punto.clinico is not None:
            result = punto.respaldo("error")
        elif isinstance(exc, PresupuestoExcedido) or (isinstance(exc, ValueError) and str(exc).startswith(CONTEXT_OVERFLOW_PREFIX)):
            raise HTTPException(status_code=413, detail=str(exc).removeprefix(CONTEXT_OVERFLOW_PREFIX).strip())
        elif isinstance(exc, GeneracionIncompletaError):
            respaldo = respaldo_determinista(req)
            if respaldo is None:
                raise HTTPException(status_code=502, detail="El modelo no produjo una impresion clinica completa. Intente de nuevo.")
            return dict(status="ok", impresion_clinica=respaldo, origen="determinista",
                correlaciones_activadas=correlaciones, salida_version=req.salida_version,
                cached=False, explicacion_paciente=None, explicacion_paciente_estado="rechazada")
        elif isinstance(exc, httpx.HTTPStatusError):
            raise HTTPException(status_code=502, detail=f"Error de Ollama: {exc.response.status_code}")
        else:
            logger.exception("Inference failed [%s]", sid)
            raise HTTPException(status_code=500, detail="Error interno del servidor.")
    metricas.solicitud("explicacion-paciente", result.explicacion_paciente_estado,
                       result.motivo_explicacion, time.monotonic() - llegada)
    return _inference_response(req, result, correlaciones, inference_cache.build_key(req),
        cached=punto.cache_clinico and punto.cache_paciente,
        cache_hits={"clinico": punto.cache_clinico, "paciente": punto.cache_paciente})


@app.post("/v1/inferencia/receta-clinica")
@app.post("/inferencia/impresion-clinica")
async def crear_impresion_clinica(
    req: ImpresionClinicaRequest,
    request: Request,
    _authorized: Annotated[None, Depends(verify_api_key)],
    client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
):
    sid = _safe_id(req.receta_id)
    logger.info("Payload recibido [%s]: %s", sid, _payload_resumen(req))

    if not has_clinical_data(req):
        logger.warning("Payload sin datos clinicos [%s] -> 422", sid)
        raise HTTPException(
            status_code=422,
            detail="El payload no contiene datos clínicos. "
            "Al menos un campo de refracción o clínica debe tener valor.",
        )

    # Trazabilidad: los nombres de las correlaciones deterministas que aplican al
    # caso se devuelven junto al texto. Es barato y deterministico, asi que se
    # calcula tambien en cache hit para que la respuesta sea homogenea.
    correlaciones = nombres_correlaciones_activas(req)
    logger.info("Correlaciones activadas [%s]: %d", sid, len(correlaciones))
    logger.debug("Nombres de correlaciones activadas [%s]: %s", sid, correlaciones or "ninguna")

    if req.salida_version == "clinica-paciente-v1":
        return await _crear_dual(req, client, correlaciones, sid, request.state.llegada)

    cache_key = inference_cache.build_key(req)
    cached = inference_cache.get(req, key=cache_key)
    if cached is not None:
        logger.info("Cache hit [%s]", sid)
        return _inference_response(req, cached, correlaciones, cache_key, cached=True)

    try:
        async with _inference_slot(sid):
            # Otro envío igual pudo generar mientras esta solicitud esperaba GPU.
            cached = inference_cache.get(req, key=cache_key)
            if cached is not None:
                return _inference_response(req, cached, correlaciones, cache_key, cached=True)
            start_time = time.perf_counter()
            try:
                result = await asyncio.wait_for(
                    run_inference(req, client),
                    timeout=_INFERENCE_TIMEOUT,
                )
                elapsed = time.perf_counter() - start_time
                logger.info(
                    "Inferencia completada [%s] en %.1fs (%d chars, %d correlaciones)",
                    sid, elapsed, len(result.impresion_clinica if isinstance(result, DualInferenceResult) else result), len(correlaciones),
                )
                response = _inference_response(req, result, correlaciones, cache_key, cached=False)
                if not isinstance(result, DualInferenceResult) or result.explicacion_paciente_estado != "rechazada":
                    inference_cache.put(req, result, key=cache_key)
                return response

            except asyncio.TimeoutError:
                logger.error(
                    "Timeout de inferencia [%s] -> 504 tras %.0fs (OLLAMA_TIMEOUT=%.0fs). "
                    "¿Modelo descargado de VRAM o GPU saturada?",
                    sid, time.perf_counter() - start_time, settings.ollama_timeout,
                )
                raise HTTPException(
                    status_code=504,
                    detail="Ollama no respondio a tiempo. Intente de nuevo.",
                )
            except GeneracionIncompletaError as exc:
                # Cortada por longitud o vacia tras la depuracion: nunca es un exito silencioso ni se cachea.
                respaldo = respaldo_determinista(req)
                if respaldo is not None:
                    logger.warning(
                        "Generacion incompleta [%s]: se entrega el respaldo determinista de la urgencia activa", sid)
                    response = {
                        "status": "ok", "impresion_clinica": respaldo,
                        "origen": "determinista", "correlaciones_activadas": correlaciones,
                    }
                    if req.salida_version == "clinica-paciente-v1":
                        response.update({
                            "salida_version": req.salida_version, "cached": False,
                            "explicacion_paciente": None, "explicacion_paciente_estado": "rechazada",
                        })
                    return response
                logger.error("Generacion incompleta [%s] -> 502: %s", sid, exc)
                raise HTTPException(
                    status_code=502,
                    detail="El modelo no produjo una impresion clinica completa. Intente de nuevo.",
                )
            except ValueError as exc:
                detail = str(exc)
                if detail.startswith(CONTEXT_OVERFLOW_PREFIX):
                    # Prompt demasiado grande para num_ctx: 413 Payload Too Large.
                    # Se strippea el prefijo interno antes de exponer al cliente.
                    logger.warning("Prompt excede contexto [%s] -> 413: %s", sid, detail)
                    raise HTTPException(
                        status_code=413,
                        detail=detail[len(CONTEXT_OVERFLOW_PREFIX):].strip(),
                    )
                logger.exception("ValueError en inferencia [%s] -> 500", sid)
                raise HTTPException(status_code=500, detail=detail)
            except httpx.HTTPStatusError as exc:
                logger.exception("Ollama HTTP error [%s]", sid)
                raise HTTPException(
                    status_code=502,
                    detail=f"Error de Ollama: {exc.response.status_code}",
                )
            except HTTPException:
                raise
            except Exception:
                # Los detalles del error ya están en el log — no exponerlos al cliente
                logger.exception("Inference failed [%s]", sid)
                raise HTTPException(status_code=500, detail="Error interno del servidor.")
    except asyncio.TimeoutError:
        logger.warning(
            "Cola saturada [%s] -> 503 (en espera: %d, maximo: %d)",
            sid, gpu_scheduler.en_cola, settings.max_queue_size,
        )
        raise HTTPException(
            status_code=503,
            detail="Servidor ocupado. Hay demasiadas peticiones en espera. "
            "Intente de nuevo en unos segundos.",
        )


_health_probe_cache: dict[str, Any] = {
    "expira": 0.0,
    "tags": None,
    "ps": None,
}


@app.get("/health")
async def health(
    client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
    response: Response,
):
    ollama_status = "error"
    model_available = False
    model_loaded = False
    # Presupuesto total inferior a los 2 s del cliente Laravel, incluso con E/S lenta.
    timeout = min(settings.health_check_timeout, 1.4)

    async def probe(path):
        try:
            result = await asyncio.wait_for(
                client.get(f"{settings.ollama_url}/api/{path}", timeout=timeout),
                timeout=timeout,
            )
            result.raise_for_status()
            return result.json()
        except Exception:
            return None

    ahora = time.monotonic()
    ttl = settings.health_cache_segundos
    if ttl > 0 and ahora < _health_probe_cache.get("expira", 0.0):
        tags = _health_probe_cache.get("tags")
        ps = _health_probe_cache.get("ps")
    else:
        tags, ps = await asyncio.gather(probe("tags"), probe("ps"))
        if ttl > 0:
            _health_probe_cache["expira"] = ahora + ttl
            _health_probe_cache["tags"] = tags
            _health_probe_cache["ps"] = ps
        else:
            _health_probe_cache["expira"] = 0.0
            _health_probe_cache["tags"] = None
            _health_probe_cache["ps"] = None
    try:
        available = [m["name"] for m in tags.get("models", [])]
        model_available = settings.ollama_model in available
        ollama_status = "ok"
    except Exception:
        pass

    if ollama_status == "ok":
        try:
            loaded: list[dict[str, Any]] = ps.get("models", [])
            model_loaded = any(
                m.get("name") == settings.ollama_model for m in loaded
            )
        except Exception:
            pass

    # Sin API_KEY el POST clinico responde 500: el servicio no esta listo aunque Ollama lo este.
    api_key_configurada = bool(settings.api_key)
    is_ready = (ollama_status == "ok" and model_available and api_key_configurada)
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ok" if is_ready else "degraded",
        "api_key_configurada": api_key_configurada,
        "ollama": ollama_status,
        "model": settings.ollama_model,
        "model_available": model_available,
        "model_loaded": model_loaded,
        # Con max_concurrent=1 la profundidad de cola es la senal operacional mas
        # importante: indica cuantas peticiones esperan turno de GPU (0..max_queue_size).
        "tareas_degradadas": REGISTRO.degradadas(),
        "modo_conteo": {n: f["modo_conteo"] for n, f in REGISTRO.tabla().items()},
        "pre_tokenizador": {n: f["pre_tokenizador"] for n, f in REGISTRO.tabla().items()},
        "gpu": gpu_scheduler.estadisticas,
        "concurrencia": {
            "max_concurrent": settings.max_concurrent,
            "en_cola": gpu_scheduler.en_cola,
            "max_en_cola": settings.max_queue_size,
        },
    }


from app.tareas.http import montar_rutas
from app.tareas.registro import REGISTRO

montar_rutas(app)
