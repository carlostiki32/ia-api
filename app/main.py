import asyncio
import logging
import time

import httpx
from fastapi import FastAPI, HTTPException, Header

from app.clinical_data import has_clinical_data
from app.config import settings
from app.inference import run_inference
from app.schemas import ImpresionClinicaRequest

logger = logging.getLogger(__name__)

# Semaphore limits concurrent inferences to protect the GPU
_inference_semaphore = asyncio.Semaphore(settings.max_concurrent)

app = FastAPI(
    title="ia-api — Inferencia Clínica Optométrica",
    version="2.0.0",
)


def _verify_api_key(authorization: str | None):
    """Validate the Bearer token against the configured API key."""
    if not settings.api_key:
        raise HTTPException(
            status_code=500,
            detail="API_KEY no configurada en el servidor.",
        )
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Header Authorization requerido: Bearer <token>",
        )
    token = authorization[len("Bearer "):]
    if token != settings.api_key:
        raise HTTPException(status_code=401, detail="Token inválido.")
@app.post("/inferencia/impresion-clinica")
async def crear_impresion_clinica(
    req: ImpresionClinicaRequest,
    authorization: str | None = Header(None),
):
    _verify_api_key(authorization)

    if not has_clinical_data(req):
        raise HTTPException(
            status_code=422,
            detail="El payload no contiene datos clínicos. "
            "Al menos un campo de refracción o clínica debe tener valor.",
        )

    # Acquire semaphore with timeout — serializes GPU access
    try:
        await asyncio.wait_for(
            _inference_semaphore.acquire(),
            timeout=settings.queue_wait_timeout,
        )
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=503,
            detail="Servidor ocupado. Hay demasiadas peticiones en espera. "
            "Intente de nuevo en unos segundos.",
        )

    start_time = time.time()
    try:
        result = await asyncio.wait_for(
            run_inference(req),
            timeout=settings.ollama_timeout,
        )
        elapsed = time.time() - start_time
        logger.info(
            "Inference for receta %s completed in %.1fs", req.receta_id, elapsed
        )
        return {
            "status": "ok",
            "impresion_clinica": result,
        }
    except asyncio.TimeoutError:
        raise HTTPException(
            status_code=504,
            detail="Ollama no respondió a tiempo. Intente de nuevo.",
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


@app.get("/health")
async def health():
    ollama_status = "ok"
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(f"{settings.ollama_url}/api/tags")
            resp.raise_for_status()
    except Exception:
        ollama_status = "error"

    return {
        "status": "ok",
        "model": settings.ollama_model,
        "ollama": ollama_status,
    }
