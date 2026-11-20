"""Pruebas de endurecimiento y seguridad de ia-api (Encargo C)."""
import asyncio
import logging
import time

from fastapi.testclient import TestClient
import httpx
import pytest

import app.main as main


def test_docs_y_openapi_deshabilitados_por_omision():
    """Por omisión docs_url, redoc_url y openapi_url son None y devuelven 404."""
    with TestClient(main.app) as client:
        r_docs = client.get("/docs")
        r_openapi = client.get("/openapi.json")
        r_redoc = client.get("/redoc")
        assert r_docs.status_code == 404
        assert r_openapi.status_code == 404
        assert r_redoc.status_code == 404


def test_docs_y_openapi_existen_si_se_habilita():
    """Con DOCS_HABILITADOS=true la app expone /docs, /redoc y /openapi.json; apagado, ninguna."""
    assert main.rutas_documentacion(True) == {
        "docs_url": "/docs", "redoc_url": "/redoc", "openapi_url": "/openapi.json",
    }
    assert main.rutas_documentacion(False) == {"docs_url": None, "redoc_url": None, "openapi_url": None}
    assert main.settings.docs_habilitados is False


def test_post_cuerpo_mayor_al_limite_da_413_sin_llegar_al_proveedor(monkeypatch):
    """Un cuerpo mayor a max_cuerpo_bytes responde 413 JSON sin llegar al proveedor (con y sin Content-Length)."""
    monkeypatch.setattr(main.settings, "api_key", "secret-test-key")
    monkeypatch.setattr(main.settings, "max_cuerpo_bytes", 65536)  # 64 KB para prueba

    envios = []

    def mock_transporte(request):
        envios.append(request)
        raise AssertionError("El proveedor no debe recibir peticiones que excedan el límite de cuerpo")

    # Caso A: Con Content-Length declarado que excede el límite
    cuerpo_grande = b"x" * 70000

    async def run_content_length():
        async with httpx.AsyncClient(transport=httpx.MockTransport(mock_transporte)) as proveedor:
            monkeypatch.setitem(main.app.dependency_overrides, main.get_http_client, lambda: proveedor)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
                return await client.post(
                    "/inferencia/impresion-clinica",
                    content=cuerpo_grande,
                    headers={
                        "Authorization": "Bearer secret-test-key",
                        "Content-Type": "application/json",
                    },
                )

    r_cl = asyncio.run(run_content_length())
    assert r_cl.status_code == 413
    assert "detail" in r_cl.json()
    assert not envios

    # Caso B: Sin Content-Length (streaming / chunked) que supera el límite por conteo
    async def generador_stream():
        yield b'{"receta_id": "1", "relleno": "'
        yield b"a" * 40000
        yield b"b" * 40000
        yield b'"}'

    async def run_stream():
        async with httpx.AsyncClient(transport=httpx.MockTransport(mock_transporte)) as proveedor:
            monkeypatch.setitem(main.app.dependency_overrides, main.get_http_client, lambda: proveedor)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
                return await client.post(
                    "/inferencia/impresion-clinica",
                    content=generador_stream(),
                    headers={
                        "Authorization": "Bearer secret-test-key",
                        "Content-Type": "application/json",
                    },
                )

    r_stream = asyncio.run(run_stream())
    assert r_stream.status_code == 413
    assert "detail" in r_stream.json()
    assert not envios


def test_post_cuerpo_normal_pasa(monkeypatch):
    """Un payload clínico normal atraviesa el límite de cuerpo y se procesa (200)."""
    monkeypatch.setattr(main.settings, "api_key", "secret-test-key")
    llamadas = []

    async def fake_run_inference(req, client):
        llamadas.append(req.receta_id)
        return "Texto generado."

    monkeypatch.setattr(main, "run_inference", fake_run_inference)
    with TestClient(main.app) as client:
        r = client.post(
            "/inferencia/impresion-clinica",
            headers={"Authorization": "Bearer secret-test-key"},
            json={"receta_id": "test-cuerpo-normal", "clinica": {"fondo_de_ojo": "Lattice temporal en OI."}},
        )
    assert r.status_code == 200, r.text
    assert llamadas == ["test-cuerpo-normal"]


def test_health_cache_una_sola_ronda_de_sondas(monkeypatch):
    """Dos llamadas a /health seguidas dentro del TTL ejecutan una sola ronda de sondas a Ollama."""
    monkeypatch.setattr(main.settings, "api_key", "secret-test-key")
    monkeypatch.setattr(main.settings, "health_cache_segundos", 2.0)
    # Limpiar caché previa
    main._health_probe_cache["expira"] = 0.0
    main._health_probe_cache["tags"] = None
    main._health_probe_cache["ps"] = None

    sondas = []

    async def handler(request):
        path = request.url.path.rsplit("/", 1)[-1]
        sondas.append(path)
        return httpx.Response(200, json={"models": [{"name": main.settings.ollama_model}]})

    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as ollama:
            monkeypatch.setitem(main.app.dependency_overrides, main.get_http_client, lambda: ollama)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as api:
                r1 = await api.get("/health")
                r2 = await api.get("/health")
                return r1, r2

    r1, r2 = asyncio.run(run())
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["status"] == "ok"
    assert r2.json()["status"] == "ok"
    # Solo una ronda de tags y ps en total (2 consultas exactas a Ollama):
    assert len(sondas) == 2
    assert sorted(sondas) == ["ps", "tags"]


def test_log_info_no_contiene_nombres_de_correlaciones(monkeypatch, caplog):
    """A nivel INFO solo se registra cuántas correlaciones se activaron, nunca sus nombres clínicos."""
    monkeypatch.setattr(main.settings, "api_key", "secret-test-key")

    async def fake_run_inference(req, client):
        return "Texto generado."

    monkeypatch.setattr(main, "run_inference", fake_run_inference)
    with caplog.at_level(logging.INFO, logger="app.main"):
        with TestClient(main.app) as client:
            r = client.post(
                "/inferencia/impresion-clinica",
                headers={"Authorization": "Bearer secret-test-key"},
                json={"receta_id": "test-log-corr", "clinica": {"fondo_de_ojo": "Lattice temporal en OI."}},
            )
    assert r.status_code == 200, r.text
    assert "fondo_periferico_riesgo" in r.json()["correlaciones_activadas"]
    info = [rec.getMessage() for rec in caplog.records if rec.levelno == logging.INFO]
    assert any(m.startswith("Correlaciones activadas") for m in info), info
    assert not any("fondo_periferico_riesgo" in m for m in info), info
