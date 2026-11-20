"""La suite es offline: ASGI y MockTransport funcionan sin conexiones reales."""
import os

# El .env local no debe cambiar resultados. num_ctx se fija ANTES de importar app
# (pydantic-settings prioriza el entorno sobre .env, y ollama._OLLAMA_OPTIONS se calcula al importar).
# Con OLLAMA_NUM_CTX=4096 el seguimiento caia a plantilla por presupuesto y colgaba
# test_enrutado::test_receta_entre_redaccion_y_verificacion. Debe igualar el valor por defecto de app/config.py.
os.environ["OLLAMA_NUM_CTX"] = "8192"

import httpx  # noqa: E402
import pytest  # noqa: E402


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


@pytest.fixture(autouse=True, scope="session")
def num_ctx_igual_al_del_codigo():
    from app.config import settings
    esperado = type(settings).model_fields["ollama_num_ctx"].default
    assert settings.ollama_num_ctx == esperado, "Actualiza OLLAMA_NUM_CTX en tests/conftest.py al default de app/config.py"
