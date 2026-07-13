import asyncio
import hashlib
import hmac
import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Annotated, Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.cache import inference_cache
from app.clinical_data import has_clinical_data
from app.config import settings
from app.correlaciones import nombres_correlaciones_activas
from app.inference import CONTEXT_OVERFLOW_PREFIX, run_inference
from app.observability import request_id_var
from app.schemas import ImpresionClinicaRequest

# Timeout total de la inferencia para asyncio.wait_for.
_INFERENCE_TIMEOUT = settings.ollama_timeout

logger = logging.getLogger(__name__)

_inference_semaphore = asyncio.Semaphore(settings.max_concurrent)
_bearer_scheme = HTTPBearer(auto_error=False)
_queue_waiting = 0


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
    contenido — el texto libre completo solo se loggea en nivel DEBUG con el
    prompt renderizado)."""

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
                    "num_ctx": settings.ollama_num_ctx,
                },
            },
            timeout=settings.ollama_timeout,
        )
        logger.info("Warmup completado — modelo en VRAM")
    except Exception as exc:
        logger.warning("Warmup fallido (no critico): %s", exc)

    try:
        yield
    finally:
        await app.state.http_client.aclose()
        logger.info("HTTP client closed")


app = FastAPI(
    title="ia-api - Inferencia Clinica Optometrica",
    version="2.1.0",
    lifespan=lifespan,
)


@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """Asigna un request-id a cada request (propaga X-Request-ID del cliente o
    genera uno), lo inyecta en todos los logs via contextvar, mide la duracion
    total y la loggea junto al status. El id vuelve al cliente en el header
    X-Request-ID para correlacionar con los logs del SaaS."""
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:8]
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
    if not hmac.compare_digest(credentials.credentials, settings.api_key):
        logger.warning(
            "Auth rechazada (401): token invalido (longitud recibida: %d)",
            len(credentials.credentials),
        )
        raise HTTPException(status_code=401, detail="Token invalido.")


async def _acquire_inference_slot(safe_id: str) -> None:
    global _queue_waiting
    if _queue_waiting >= settings.max_queue_size:
        raise asyncio.TimeoutError
    _queue_waiting += 1
    logger.info("Inference request queued [%s] (queue: %d)", safe_id, _queue_waiting)
    try:
        if settings.queue_wait_timeout <= 0:
            await _inference_semaphore.acquire()
        else:
            await asyncio.wait_for(
                _inference_semaphore.acquire(),
                timeout=settings.queue_wait_timeout,
            )
    finally:
        _queue_waiting -= 1
    logger.info("Inference slot acquired [%s]", safe_id)


@app.post("/inferencia/impresion-clinica")
async def crear_impresion_clinica(
    req: ImpresionClinicaRequest,
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
    logger.info(
        "Correlaciones activadas [%s] (%d): %s",
        sid, len(correlaciones), correlaciones or "ninguna",
    )

    cache_key = inference_cache.build_key(req)
    cached = inference_cache.get(req, key=cache_key)
    if cached is not None:
        logger.info("Cache hit [%s]", sid)
        return {
            "status": "ok",
            "impresion_clinica": cached,
            "cached": True,
            "correlaciones_activadas": correlaciones,
        }

    try:
        await _acquire_inference_slot(sid)
    except asyncio.TimeoutError:
        logger.warning(
            "Cola saturada [%s] -> 503 (en espera: %d, maximo: %d)",
            sid, _queue_waiting, settings.max_queue_size,
        )
        raise HTTPException(
            status_code=503,
            detail="Servidor ocupado. Hay demasiadas peticiones en espera. "
            "Intente de nuevo en unos segundos.",
        )

    start_time = time.perf_counter()
    try:
        result = await asyncio.wait_for(
            run_inference(req, client),
            timeout=_INFERENCE_TIMEOUT,
        )
        elapsed = time.perf_counter() - start_time
        logger.info(
            "Inferencia completada [%s] en %.1fs (%d chars, %d correlaciones)",
            sid, elapsed, len(result), len(correlaciones),
        )
        inference_cache.put(req, result, key=cache_key)
        return {
            "status": "ok",
            "impresion_clinica": result,
            "correlaciones_activadas": correlaciones,
        }

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
    except Exception:
        # Los detalles del error ya están en el log — no exponerlos al cliente
        logger.exception("Inference failed [%s]", sid)
        raise HTTPException(status_code=500, detail="Error interno del servidor.")
    finally:
        _inference_semaphore.release()
        logger.info("Inference slot released [%s]", sid)


@app.get("/health")
async def health(client: Annotated[httpx.AsyncClient, Depends(get_http_client)]):
    ollama_status = "error"
    model_available = False
    model_loaded = False
    try:
        tags_resp = await client.get(
            f"{settings.ollama_url}/api/tags",
            timeout=settings.health_check_timeout,
        )
        tags_resp.raise_for_status()
        available = [m["name"] for m in tags_resp.json().get("models", [])]
        model_available = settings.ollama_model in available
        ollama_status = "ok"
    except Exception:
        pass

    if ollama_status == "ok":
        try:
            ps_resp = await client.get(
                f"{settings.ollama_url}/api/ps",
                timeout=settings.health_check_timeout,
            )
            ps_resp.raise_for_status()
            loaded: list[dict[str, Any]] = ps_resp.json().get("models", [])
            model_loaded = any(
                m.get("name") == settings.ollama_model for m in loaded
            )
        except Exception:
            pass

    return {
        "status": "ok" if ollama_status == "ok" else "degraded",
        "ollama": ollama_status,
        "model": settings.ollama_model,
        "model_available": model_available,
        "model_loaded": model_loaded,
        # Con max_concurrent=1 la profundidad de cola es la senal operacional mas
        # importante: indica cuantas peticiones esperan turno de GPU (0..max_queue_size).
        "concurrencia": {
            "max_concurrent": settings.max_concurrent,
            "en_cola": _queue_waiting,
            "max_en_cola": settings.max_queue_size,
        },
    }