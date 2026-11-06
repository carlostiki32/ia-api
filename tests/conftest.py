"""La suite es offline: ASGI y MockTransport funcionan sin conexiones reales."""
import httpx
import pytest


@pytest.fixture(autouse=True)
def block_real_http_transport(monkeypatch):
    async def blocked_async(self, request):
        raise httpx.ConnectError("Transporte HTTP real bloqueado en pruebas", request=request)

    def blocked_sync(self, request):
        raise httpx.ConnectError("Transporte HTTP real bloqueado en pruebas", request=request)

    monkeypatch.setattr(httpx.AsyncHTTPTransport, "handle_async_request", blocked_async)
    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", blocked_sync)
