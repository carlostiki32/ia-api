import asyncio
import httpx

from fastapi.testclient import TestClient

import app.main as main
from app.clinical_data import has_clinical_data
from app.schemas import ImpresionClinicaRequest


def _valid_payload() -> dict:
    return {
        "receta_id": "test-001",
        "refraccion": {
            "od": {
                "esfera": -1.25,
            }
        },
    }


def test_has_clinical_data_accepts_zero_refraction_values():
    req = ImpresionClinicaRequest(
        receta_id="test-zero",
        refraccion={
            "od": {
                "esfera": 0.0,
            }
        },
    )

    assert has_clinical_data(req) is True


def test_has_clinical_data_accepts_akr_keratometry_values():
    req = ImpresionClinicaRequest(
        receta_id="test-ker",
        akr={
            "od": {
                "k1_d": 41.25,
                "k2_d": 43.75,
                "k_cilindro": -2.50,
            }
        },
    )

    assert has_clinical_data(req) is True


def test_has_clinical_data_rejects_context_without_clinical_fields():
    req = ImpresionClinicaRequest(
        receta_id="test-context-only",
        paciente={
            "edad": 36,
            "ocupacion": "Programador",
            "motivo_consulta": "Revision",
        },
    )

    assert has_clinical_data(req) is False


def test_endpoint_requires_bearer_token(monkeypatch):
    monkeypatch.setattr(main.settings, "api_key", "secret-token")

    with TestClient(main.app) as client:
        response = client.post("/inferencia/impresion-clinica", json=_valid_payload())

    assert response.status_code == 401
    assert response.json()["detail"] == "Header Authorization requerido: Bearer <token>"


def test_endpoint_rejects_payload_without_clinical_data(monkeypatch):
    monkeypatch.setattr(main.settings, "api_key", "secret-token")

    with TestClient(main.app) as client:
        response = client.post(
            "/inferencia/impresion-clinica",
            headers={"Authorization": "Bearer secret-token"},
            json={"receta_id": "test-001"},
        )

    assert response.status_code == 422
    assert "datos clínicos" in response.json()["detail"]


def test_endpoint_returns_inference_result(monkeypatch):
    monkeypatch.setattr(main.settings, "api_key", "secret-token")

    async def fake_run_inference(req, client):
        assert req.receta_id == "test-001"
        assert client is main.app.state.http_client
        return "Texto generado."

    monkeypatch.setattr(main, "run_inference", fake_run_inference)

    with TestClient(main.app) as client:
        response = client.post(
            "/inferencia/impresion-clinica",
            headers={"Authorization": "Bearer secret-token"},
            json=_valid_payload(),
        )

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "impresion_clinica": "Texto generado.",
        "correlaciones_activadas": [],
    }


def test_endpoint_reporta_correlaciones_activadas(monkeypatch):
    monkeypatch.setattr(main.settings, "api_key", "secret-token")

    async def fake_run_inference(req, client):
        return "Texto generado."

    monkeypatch.setattr(main, "run_inference", fake_run_inference)

    with TestClient(main.app) as client:
        response = client.post(
            "/inferencia/impresion-clinica",
            headers={"Authorization": "Bearer secret-token"},
            json={
                "receta_id": "test-corr",
                "clinica": {"fondo_de_ojo": "Lattice temporal en OI."},
            },
        )

    assert response.status_code == 200
    body = response.json()
    assert "fondo_periferico_riesgo" in body["correlaciones_activadas"]


def test_health_when_ollama_offline_returns_503():
    with TestClient(main.app) as client:
        response = client.get("/health")

    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "degraded"
    assert body["ollama"] == "error"
    assert body["model_available"] is False
    concurrencia = body["concurrencia"]
    assert concurrencia["max_concurrent"] == main.settings.max_concurrent
    assert concurrencia["en_cola"] == 0
    assert concurrencia["max_en_cola"] == main.settings.max_queue_size


def test_health_when_ollama_ready_returns_200():
    class FakeResponse:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            pass

        def json(self):
            return self._data

    class FakeClient:
        async def get(self, url, timeout=None):
            if "/api/tags" in url:
                return FakeResponse({"models": [{"name": main.settings.ollama_model}]})
            if "/api/ps" in url:
                return FakeResponse({"models": [{"name": main.settings.ollama_model}]})
            raise RuntimeError(f"Unexpected url {url}")

    main.app.dependency_overrides[main.get_http_client] = lambda: FakeClient()
    try:
        with TestClient(main.app) as client:
            response = client.get("/health")

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "ok"
        assert body["ollama"] == "ok"
        assert body["model_available"] is True
        assert body["model_loaded"] is True
    finally:
        main.app.dependency_overrides.pop(main.get_http_client, None)


def test_endpoint_queue_saturated_returns_503(monkeypatch):
    monkeypatch.setattr(main.settings, "api_key", "secret-token")
    monkeypatch.setattr(main, "_queue_waiting", main.settings.max_queue_size)
    main.inference_cache.clear()

    payload = {
        "receta_id": "test-queue-503",
        "refraccion": {"od": {"esfera": -8.75}},
    }

    with TestClient(main.app) as client:
        response = client.post(
            "/inferencia/impresion-clinica",
            headers={"Authorization": "Bearer secret-token"},
            json=payload,
        )

    assert response.status_code == 503
    assert "demasiadas peticiones en espera" in response.json()["detail"].lower()


def test_inference_slot_releases_semaphore_on_exception():
    initial_val = main._inference_semaphore._value

    async def _fail_inside():
        async with main._inference_slot("test-fail"):
            raise RuntimeError("Boom!")

    try:
        asyncio.run(_fail_inside())
    except RuntimeError:
        pass

    assert main._inference_semaphore._value == initial_val
    assert main._queue_waiting == 0


def test_inference_slot_releases_semaphore_on_cancellation():
    initial_val = main._inference_semaphore._value

    async def _cancel_task():
        started = asyncio.Event()

        async def _worker():
            async with main._inference_slot("test-cancel"):
                started.set()
                await asyncio.sleep(10)

        task = asyncio.create_task(_worker())
        await started.wait()
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    asyncio.run(_cancel_task())

    assert main._inference_semaphore._value == initial_val
    assert main._queue_waiting == 0


