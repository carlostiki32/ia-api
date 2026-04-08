import hashlib
import json
import logging
import time
import threading

from app.config import settings
from app.prompt_builder import SYSTEM_PROMPT
from app.schemas import ImpresionClinicaRequest

logger = logging.getLogger(__name__)


class InferenceCache:
    """In-memory cache for inference results, keyed by payload hash (excluding receta_id)."""

    def __init__(self, max_size: int, ttl_seconds: int):
        self._store: dict[str, tuple[str, float]] = {}
        self._lock = threading.Lock()
        self._max_size = max_size
        self._ttl = ttl_seconds

    @staticmethod
    def _build_key(payload: ImpresionClinicaRequest) -> str:
        data = payload.model_dump(mode="json")
        data.pop("receta_id", None)
        data["__model"] = settings.ollama_model
        data["__prompt_hash"] = hashlib.sha256(
            SYSTEM_PROMPT.encode()
        ).hexdigest()[:16]
        raw = json.dumps(data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode()).hexdigest()

    def get(self, payload: ImpresionClinicaRequest) -> str | None:
        key = self._build_key(payload)
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, ts = entry
            if time.time() - ts > self._ttl:
                del self._store[key]
                logger.info("Cache expired for key %s", key[:12])
                return None
            logger.info("Cache hit for key %s", key[:12])
            return value

    def put(self, payload: ImpresionClinicaRequest, result: str) -> None:
        key = self._build_key(payload)
        with self._lock:
            if len(self._store) >= self._max_size and key not in self._store:
                oldest_key = min(self._store, key=lambda k: self._store[k][1])
                del self._store[oldest_key]
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
