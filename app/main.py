import asyncio
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

# Limit concurrent inferences to protect the home GPU from OOM.
_inference_semaphore = asyncio.Semaphore(settings.max_concurrent)
_bearer_scheme = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.http_client = httpx.AsyncClient(timeout=settings.ollama_timeout + 5)
    logger.info("HTTP client started for model %s", settings.ollama_model)
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
    """Return the shared httpx client stored in the app lifespan."""
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
    """Validate the Bearer token against the configured API key."""
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

    if credentials.credentials != settings.api_key:
        raise HTTPException(status_code=401, detail="Token invalido.")


async def _acquire_inference_slot(receta_id: str) -> None:
    """Queue inference requests so the GPU processes them one at a time."""
    logger.info("Inference request queued for receta %s", receta_id)

    if settings.queue_wait_timeout <= 0:
        await _inference_semaphore.acquire()
    else:
        await asyncio.wait_for(
            _inference_semaphore.acquire(),
            timeout=settings.queue_wait_timeout,
        )

    logger.info("Inference slot acquired for receta %s", receta_id)


@app.post("/inferencia/impresion-clinica")
async def crear_impresion_clinica(
    req: ImpresionClinicaRequest,
    _authorized: Annotated[None, Depends(verify_api_key)],
    client: Annotated[httpx.AsyncClient, Depends(get_http_client)],
):
    if not has_clinical_data(req):
        raise HTTPException(
            status_code=422,
            detail="El payload no contiene datos clinicos. "
            "Al menos un campo de refraccion o clinica debe tener valor.",
        )

    cached = inference_cache.get(req)
    if cached is not None:
        logger.info("Returning cached result for receta %s", req.receta_id)
        return {"status": "ok", "impresion_clinica": cached, "cached": True}

    try:
        await _acquire_inference_slot(req.receta_id)
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
        logger.info(
            "Inference for receta %s completed in %.1fs", req.receta_id, elapsed
        )
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
        logger.exception("Ollama HTTP error for receta %s", req.receta_id)
        raise HTTPException(
            status_code=502,
            detail=f"Error de Ollama: {exc.response.status_code}",
        )
    except Exception as exc:
        logger.exception("Inference failed for receta %s", req.receta_id)
        raise HTTPException(status_code=500, detail=f"Error interno: {exc}")
    finally:
        _inference_semaphore.release()
        logger.info("Inference slot released for receta %s", req.receta_id)


@app.get("/health")
async def health(client: Annotated[httpx.AsyncClient, Depends(get_http_client)]):
    ollama_status = "ok"
    try:
        resp = await client.get(
            f"{settings.ollama_url}/api/tags",
            timeout=settings.health_check_timeout,
        )
        resp.raise_for_status()
    except Exception:
        ollama_status = "error"

    return {
        "status": "ok",
        "model": settings.ollama_model,
        "ollama": ollama_status,
    }
