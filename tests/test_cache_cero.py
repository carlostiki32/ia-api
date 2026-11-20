"""Regresiones: tamaño cero desactiva la caché; negativos no arrancan."""
import pytest
from pydantic import ValidationError
from app.cache import InferenceCache
from app.config import Settings
from app.schemas import ImpresionClinicaRequest

def test_cache_cero_no_falla_tras_inferencia():
    cache = InferenceCache(max_size=0, ttl_seconds=60)
    req = ImpresionClinicaRequest(receta_id="cero")
    cache.put(req, "Inferencia exitosa")
    assert cache.get(req) is None
    assert len(cache._store) == 0

def test_cache_negativa_rechazada_al_arrancar():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, cache_max_size=-1)

def test_constructor_cache_negativa():
    with pytest.raises(ValueError):
        InferenceCache(max_size=-1, ttl_seconds=60)
