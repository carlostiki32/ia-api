import hashlib
import json
import logging
import time
import threading
from collections import OrderedDict

from app.config import settings
from app.schemas import ImpresionClinicaRequest

logger = logging.getLogger(__name__)


class InferenceCache:
    """In-memory cache for inference results, keyed by payload hash (excluding receta_id)."""

    def __init__(self, max_size: int, ttl_seconds: int):
        self._store: OrderedDict[str, tuple[str, float]] = OrderedDict()
        self._lock = threading.Lock()
        self._max_size = max_size
        self._ttl = ttl_seconds

    @staticmethod
    def build_key(payload: ImpresionClinicaRequest) -> str:
        data = payload.model_dump(mode="json")
        data.pop("receta_id", None)
        data["__model"] = settings.ollama_model
        # El system prompt efectivo varía según si hay recomendación de seguimiento
        # (effective_max = max_sentences - 1). Se incluye en la key para evitar
        # devolver del cache una respuesta generada con un límite de oraciones distinto.
        data["__has_recommendation"] = bool(
            payload.clinica.recomendacion_seguimiento
        )
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, payload: ImpresionClinicaRequest, key: str | None = None) -> str | None:
        if key is None:
            key = self.build_key(payload)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, ts = entry
            if time.time() - ts > self._ttl:
                del self._store[key]
                logger.info("Cache expired for key %s", key[:12])
                return None
            self._store.move_to_end(key)
            logger.info("Cache hit for key %s", key[:12])
            return value

    def put(self, payload: ImpresionClinicaRequest, result: str, key: str | None = None) -> None:
        if key is None:
            key = self.build_key(payload)
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
            elif len(self._store) >= self._max_size:
                oldest_key, _ = self._store.popitem(last=False)
                logger.info("Cache evicted oldest entry %s", oldest_key[:12])
            self._store[key] = (result, time.time())
            logger.info("Cache stored key %s (size: %d)", key[:12], len(self._store))

    @property
    def size(self) -> int:
        return len(self._store)


inference_cache = InferenceCache(
    max_size=settings.cache_max_size,
    ttl_seconds=settings.cache_ttl_seconds,
)
