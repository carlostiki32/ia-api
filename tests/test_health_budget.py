"""Contrato de /health y presupuesto de pared; Ollama siempre simulado."""
import asyncio
import time

import httpx
import pytest

import app.main as main


def expected_health(*, ollama="ok", available=True, loaded=True, key=True):
    ready = ollama == "ok" and available and key
    return {
        "status": "ok" if ready else "degraded",
        "api_key_configurada": key,
        "ollama": ollama,
        "model": main.settings.ollama_model,
        "model_available": available,
        "model_loaded": loaded,
        "tareas_degradadas": main.REGISTRO.degradadas(),
        "modo_conteo": {n: f["modo_conteo"] for n, f in main.REGISTRO.tabla().items()},
        "pre_tokenizador": {n: f["pre_tokenizador"] for n, f in main.REGISTRO.tabla().items()},
        "gpu": main.gpu_scheduler.estadisticas,
        "concurrencia": {
            "max_concurrent": main.settings.max_concurrent,
            "en_cola": main.gpu_scheduler.en_cola,
            "max_en_cola": main.settings.max_queue_size,
        },
    }


def request_health(monkeypatch, handler):
    # Desactivar caché para medir con precisión el presupuesto de pared por sonda
    # y evitar reutilización de respuestas entre casos parametrizados secuenciales.
    monkeypatch.setattr(main.settings, "health_cache_segundos", 0.0)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as ollama:
            monkeypatch.setitem(main.app.dependency_overrides, main.get_http_client, lambda: ollama)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as api:
                started = time.perf_counter()
                response = await api.get("/health")
                return response, time.perf_counter() - started

    return asyncio.run(run())


@pytest.mark.parametrize("slow", [{"tags"}, {"ps"}, {"tags", "ps"}])
def test_health_slow_probe_respects_total_budget_and_preserves_fields(monkeypatch, slow):
    monkeypatch.setattr(main.settings, "api_key", "test-key")
    monkeypatch.setattr(main.settings, "health_check_timeout", 5.0)
    started, finished = set(), set()

    async def handler(request):
        path = request.url.path.rsplit("/", 1)[-1]
        started.add(path)
        try:
            if path in slow:
                await asyncio.sleep(5)
            return httpx.Response(200, json={"models": [{"name": main.settings.ollama_model}]})
        finally:
            finished.add(path)

    response, elapsed = request_health(monkeypatch, handler)
    print(f"slow={sorted(slow)} elapsed={elapsed:.3f}s")
    assert 1.3 <= elapsed < 1.6  # 1.4 s de presupuesto y margen del planificador de Windows.
    tags_ok = "tags" not in slow
    assert response.status_code == (200 if tags_ok else 503)
    assert response.json() == expected_health(
        ollama="ok" if tags_ok else "error", available=tags_ok,
        loaded=tags_ok and "ps" not in slow,
    )
    assert started == finished == {"tags", "ps"}


@pytest.mark.parametrize("case", ["ready", "unloaded", "missing", "tags_error", "ps_error", "empty_tags", "malformed_tags", "no_key"])
def test_health_fast_probes_preserve_complete_legacy_response(monkeypatch, case):
    monkeypatch.setattr(main.settings, "api_key", "" if case == "no_key" else "test-key")
    started = set()

    async def handler(request):
        path = request.url.path.rsplit("/", 1)[-1]
        started.add(path)
        await asyncio.sleep(0.02)
        assert started == {"tags", "ps"}  # Ambas consultas arrancan antes de terminar la primera.
        if case == f"{path}_error":
            return httpx.Response(503)
        if path == "tags" and case == "empty_tags":
            return httpx.Response(200, json={})
        if path == "tags" and case == "malformed_tags":
            return httpx.Response(200, json={"models": [{}]})
        absent = (path == "tags" and case == "missing") or (path == "ps" and case == "unloaded")
        return httpx.Response(200, json={"models": [] if absent else [{"name": main.settings.ollama_model}]})

    response, elapsed = request_health(monkeypatch, handler)
    tags_ok = case not in {"tags_error", "malformed_tags"}
    available = tags_ok and case not in {"missing", "empty_tags"}
    ready = tags_ok and available and case != "no_key"
    assert response.status_code == (200 if ready else 503)
    assert response.json() == expected_health(
        ollama="ok" if tags_ok else "error", available=available,
        loaded=tags_ok and case not in {"unloaded", "ps_error"}, key=case != "no_key",
    )
    assert elapsed < 1.5
