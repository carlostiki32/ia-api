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
    assert "datos clinicos" in response.json()["detail"]


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
    }


