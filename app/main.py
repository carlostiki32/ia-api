import asyncio
import hashlib
import hmac
import logging
import time
from contextlib import asynccontextmanager
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.cache import inference_cache
from app.clinical_data import has_clinical_data
from app.config import settings
from app.inference import run_inference
from app.schemas import ImpresionClinicaRequest

logger = logging.getLogger(__name__)

_inference_semaphore = asyncio.Semaphore(settings.max_concurrent)
_bearer_scheme = HTTPBearer(auto_error=False)


def _safe_id(receta_id: str) -> str:
    return hashlib.sha256(receta_id.encode()).hexdigest()[:10]


@asynccontextmanager
async def lifespan(app: FastAPI):
    per_request_timeout = settings.ollama_timeout / 2
    app.state.http_client = httpx.AsyncClient(timeout=per_request_timeout + 5)
    logger.info("HTTP client started for model %s", settings.ollama_model)

    try:
        await app.state.http_client.post(
            f"{settings.ollama_url}/api/chat",
            json={
                "model": settings.ollama_model,
                "messages": [{"role": "user", "content": "ok"}],
                "stream": False,
                "think": False,
                "options": {"num_predict": 1, "num_ctx": 512},
            },
            timeout=60.0,
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
    version="2.0.0",
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
    logger.info("Inference request queued [%s]", safe_id)
    if settings.queue_wait_timeout <= 0:
        await _inference_semaphore.acquire()
    else:
        await asyncio.wait_for(
            _inference_semaphore.acquire(),
            timeout=settings.queue_wait_timeout,
        )
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

    cached = inference_cache.get(req)
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

    start_time = time.time()
    try:
        result = await asyncio.wait_for(
            run_inference(req, client),
            timeout=settings.ollama_timeout,
        )
        elapsed = time.time() - start_time
        logger.info("Inference completed [%s] in %.1fs", sid, elapsed)
        inference_cache.put(req, result)
        return {"status": "ok", "impresion_clinica": result}
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Ollama no respondio a tiempo. Intente de nuevo.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except httpx.HTTPStatusError as exc:
        logger.exception("Ollama HTTP error [%s]", sid)
        raise HTTPException(
            status_code=502,
            detail=f"Error de Ollama: {exc.response.status_code}",
        )
    except Exception as exc:
        logger.exception("Inference failed [%s]", sid)
        raise HTTPException(status_code=500, detail=f"Error interno: {exc}")
    finally:
        _inference_semaphore.release()
        logger.info("Inference slot released [%s]", sid)


@app.get("/health")
async def health(client: Annotated[httpx.AsyncClient, Depends(get_http_client)]):
    ollama_status = "error"
    model_available = False
    try:
        resp = await client.get(
            f"{settings.ollama_url}/api/tags",
            timeout=settings.health_check_timeout,
        )
        resp.raise_for_status()
        available = [m["name"] for m in resp.json().get("models", [])]
        model_available = settings.ollama_model in available
        ollama_status = "ok"
    except Exception:
        pass

    return {
        "status": "ok" if ollama_status == "ok" else "degraded",
        "model": settings.ollama_model,
        "model_available": model_available,
        "ollama": ollama_status,
    }