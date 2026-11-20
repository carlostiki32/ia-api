"""La suite es offline: ASGI y MockTransport funcionan sin conexiones reales."""
import httpx
import pytest


_original_handle_sync = httpx.HTTPTransport.handle_request
_original_handle_async = httpx.AsyncHTTPTransport.handle_async_request


@pytest.fixture(autouse=True)
def block_real_http_transport(monkeypatch):
    async def blocked_async(self, request):
        if request.url.host in ("127.0.0.1", "localhost") and request.url.port != 11434:
            return await _original_handle_async(self, request)
        raise httpx.ConnectError("Transporte HTTP real bloqueado en pruebas", request=request)

    def blocked_sync(self, request):
        if request.url.host in ("127.0.0.1", "localhost") and request.url.port != 11434:
            return _original_handle_sync(self, request)
        raise httpx.ConnectError("Transporte HTTP real bloqueado en pruebas", request=request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked_async)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked_sync)


@pytest.fixture(autouse=True)
def conteo_offline(monkeypatch):
    from app.tareas.presupuesto import contador, politica_actual
    # Contratos históricos: respaldo conservador explícito, sin Ollama.
    # Las pruebas del modo estricto/exacto sustituyen esta configuración.
    from app.config import settings
    monkeypatch.setattr(settings, 'presupuesto_receta_sin_exacto', 'conservador')
    monkeypatch.setattr(contador, 'tokenizador', None)
    monkeypatch.setattr(contador, 'identidad', None)
    token = politica_actual.set('conservador')
    yield
    politica_actual.reset(token)
