import asyncio
import httpx
from app import main
from app.config import Settings
from app.seguimiento import servicio
from tests.seguimiento_helpers import request

def test_interruptor_default():
    assert Settings(_env_file=None).seguimiento_llm_habilitado is True

def test_apagado_antes_de_cache_y_proveedor(monkeypatch):
    req = request()
    esperado = servicio.respaldo(req, motivo="ia_deshabilitada").model_dump(mode="json")
    assert esperado["estado"] == "plantilla" and esperado["motivo"] == "ia_deshabilitada"
    # Una respuesta válida existente tampoco puede eludir el interruptor.
    generada = servicio.respaldo(req)
    generada.estado = "generada"
    generada.motivo = None
    generada.generacion.origen = "llm"
    servicio.seguimiento_cache.put(servicio.clave_cache(req), generada)
    def prohibido(*a, **k):
        raise AssertionError("Se consultó caché o proveedor con el interruptor apagado")
    monkeypatch.setattr(servicio.seguimiento_cache, "get", prohibido)
    monkeypatch.setattr(servicio.ollama, "call", prohibido)
    monkeypatch.setattr(main.settings, "seguimiento_llm_habilitado", False)
    monkeypatch.setattr(main.settings, "api_key", "secret")
    main.app.dependency_overrides[main.get_http_client] = lambda: object()
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),
            base_url="http://test", headers={"Authorization": "Bearer secret"}) as c:
            r = await c.post("/v1/inferencia/seguimiento-whatsapp", json=req.model_dump(mode="json"))
            assert r.status_code == 200
            assert r.json() == esperado
    try:
        asyncio.run(run())
    finally:
        servicio.seguimiento_cache.clear()
        main.app.dependency_overrides.pop(main.get_http_client, None)
