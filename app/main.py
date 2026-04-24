import asyncio
import hashlib
import hmac
import logging
import time
from contextlib import asynccontextmanager
from typing import Annotated, Any

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.cache import inference_cache
from app.clinical_data import has_clinical_data
from app.config import settings
from app.inference import CONTEXT_OVERFLOW_PREFIX, run_inference
from app.schemas import ImpresionClinicaRequest

logger = logging.getLogger(__name__)

_inference_semaphore = asyncio.Semaphore(settings.max_concurrent)
_bearer_scheme = HTTPBearer(auto_error=False)
_queue_waiting = 0


def _safe_id(receta_id: str) -> str:
    return hashlib.sha256(receta_id.encode()).hexdigest()[:10]


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
        raise HTTPException(
            status_code=500,
            detail="API_KEY no configurada en el servidor.",
        )
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Header Authorization requerido: Bearer <token>",
        )
    if not hmac.compare_digest(credentials.credentials, settings.api_key):
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

    if not has_clinical_data(req):
        raise HTTPException(
            status_code=422,
            detail="El payload no contiene datos clinicos. "
            "Al menos un campo de refraccion o clinica debe tener valor.",
        )

    cache_key = inference_cache.build_key(req)
    cached = inference_cache.get(req, key=cache_key)
    if cached is not None:
        logger.info("Cache hit [%s]", sid)
        return {"status": "ok", "impresion_clinica": cached, "cached": True}

    try:
        await _acquire_inference_slot(sid)
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=503,
            detail="Servidor ocupado. Hay demasiadas peticiones en espera. "
            "Intente de nuevo en unos segundos.",
        )

    start_time = time.perf_counter()
    try:
        result = await asyncio.wait_for(
            run_inference(req, client),
            timeout=settings.ollama_timeout,
        )
        elapsed = time.perf_counter() - start_time
        logger.info("Inference completed [%s] in %.1fs", sid, elapsed)
        inference_cache.put(req, result, key=cache_key)
        return {"status": "ok", "impresion_clinica": result}

    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Ollama no respondio a tiempo. Intente de nuevo.",
        )
    except ValueError as exc:
        detail = str(exc)
        if detail.startswith(CONTEXT_OVERFLOW_PREFIX):
            # Prompt demasiado grande para num_ctx: 413 Payload Too Large.
            # Se strippea el prefijo interno antes de exponer al cliente.
            raise HTTPException(
                status_code=413,
                detail=detail[len(CONTEXT_OVERFLOW_PREFIX):].strip(),
            )
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
        "model": settings.ollama_model,
        "model_available": model_available,
        "model_loaded": model_loaded,
        "ollama": ollama_status,
    }