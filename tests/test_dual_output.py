"""Salida dual y caché, con Ollama/HTTP simulados; nunca requiere GPU."""
import asyncio
import json

import httpx
import pytest

import app.inference as inference
import app.main as main
from app.cache import InferenceCache, inference_cache
from app.config import settings
from app.dual_contract import DualInferenceResult
from app.patient_profile import build_patient_profile, build_patient_template
from app.providers import ollama
from app.schemas import ImpresionClinicaRequest


def request(**kwargs):
    eye = {"esfera": -1, "cilindro": -.75}
    return ImpresionClinicaRequest(receta_id="dual", salida_version="clinica-paciente-v1",
        refraccion=kwargs.pop("refraccion", {"od": eye, "oi": eye}), **kwargs)


def fake_provider(monkeypatch, outputs):
    calls = []
    async def call(system, user, client, **kwargs):
        calls.append((system, user, kwargs))
        return outputs[min(len(calls)-1, len(outputs)-1)]
    monkeypatch.setattr(inference.ollama_provider, "call", call)
    return calls


def test_dual_uses_identical_clinical_call_and_cpu_template(monkeypatch):
    req = request()
    monkeypatch.setattr(settings, "ollama_dual_num_predict", 7)
    calls = fake_provider(monkeypatch, [("Se registra refraccion final.", {"done_reason": "stop"})])
    result = asyncio.run(inference.run_inference(req, object()))
    assert len(calls) == 1
    assert result.explicacion_paciente == build_patient_template(build_patient_profile(req))
    assert result.explicacion_paciente_estado == result.origen_explicacion == "plantilla"
    assert result.impresion_clinica == "Se registra refracción final."
    asyncio.run(inference.run_inference(req.model_copy(update={"salida_version": "clinica-v1"}), object()))
    assert calls[0] == calls[1]
    assert "PERFIL EDUCATIVO" not in calls[0][0] + calls[0][1]
    assert "explicacion_paciente" not in calls[0][0] + calls[0][1]
    assert calls[0][2] == {}


def test_dual_length_retry_uses_clinical_budget_without_schema(monkeypatch):
    calls = fake_provider(monkeypatch, [
        ("Se registra", {"done_reason": "length"}),
        ("Se registra refraccion final.", {"done_reason": "stop"}),
    ])
    monkeypatch.setattr(settings, "ollama_dual_num_predict", 7)
    result = asyncio.run(inference.run_inference(request(), object()))
    assert len(calls) == 2
    assert calls[1][2] == {"num_predict": int(settings.ollama_num_predict * 1.5)}
    assert result.explicacion_paciente_estado == "plantilla"


@pytest.mark.parametrize("rx,state", [
    ({"od": {"esfera": 0, "cilindro": 0}, "oi": {"esfera": 0, "cilindro": 0}}, "sin_componentes_refractivos"),
    ({"od": {"esfera": -1}, "oi": {"esfera": 0, "cilindro": 0}}, "datos_incompletos"),
])
def test_nonapplicable_patient_state_null(monkeypatch, rx, state):
    fake_provider(monkeypatch, [("Se registra refraccion final.", {})])
    result = asyncio.run(inference.run_inference(request(refraccion=rx), object()))
    assert result.explicacion_paciente is None
    assert result.explicacion_paciente_estado == state and result.origen_explicacion == "ninguno"



@pytest.mark.parametrize("clinical", ["", "No se dispone de datos clinicos."])
def test_clinical_invalid_does_not_create_success_pair(monkeypatch, clinical):
    fake_provider(monkeypatch, [(clinical, {})])
    with pytest.raises(inference.GeneracionIncompletaError):
        asyncio.run(inference.run_inference(request(), object()))


def test_patient_template_failure_keeps_clinical_and_marks_rejected(monkeypatch):
    calls = fake_provider(monkeypatch, [("Se registra refraccion final.", {})])
    monkeypatch.setattr(inference, "build_patient_template", lambda profile: None)
    result = asyncio.run(inference.run_inference(request(), object()))
    assert result.impresion_clinica and result.explicacion_paciente is None
    assert result.explicacion_paciente_estado == "rechazada" and result.origen_explicacion == "ninguno"
    assert len(calls) == 1


def test_clinical_guard_does_not_accept_patient_profile_as_clinical_source(monkeypatch):
    fake_provider(monkeypatch, [("El paciente tiene glaucoma. Se registra refraccion final.", {})])
    result = asyncio.run(inference.run_inference(request(), object()))
    assert "glaucoma" not in result.impresion_clinica.lower()
    assert "Se registra refracción final." in result.impresion_clinica


def test_context_overflow_happens_before_provider(monkeypatch):
    calls = fake_provider(monkeypatch, [("Se registra refraccion final.", {})])
    monkeypatch.setattr(settings, "ollama_num_ctx", 10)
    with pytest.raises(ValueError, match=inference.CONTEXT_OVERFLOW_PREFIX):
        asyncio.run(inference.run_inference(request(), object()))
    assert not calls


def test_http_provider_receives_same_body_in_both_modes_without_format(monkeypatch):
    bodies = []
    async def handler(req):
        bodies.append(json.loads(req.content))
        return httpx.Response(200, json={"message": {"content": "Se registra refraccion final.", "thinking": "secreto"}, "done_reason": "stop"})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            req = request()
            await inference.run_inference(req, client)
            await inference.run_inference(req.model_copy(update={"salida_version": "clinica-v1"}), client)
    asyncio.run(run())
    assert len(bodies) == 2 and bodies[0] == bodies[1]
    assert "format" not in bodies[0]
    assert bodies[0]["options"]["num_predict"] == settings.ollama_num_predict
    assert bodies[0]["think"] is False



def test_cache_separates_versions_config_and_equivalent_transpositions(monkeypatch):
    req = request()
    legacy = req.model_copy(update={"salida_version": "clinica-v1"})
    assert InferenceCache.build_key(req) != InferenceCache.build_key(legacy)
    original = InferenceCache.build_key(req)
    assert original == InferenceCache.build_key(req.model_copy(update={"receta_id": "otra"}))
    monkeypatch.setattr(settings, "ollama_dual_num_predict", 1536)
    assert original == InferenceCache.build_key(req)
    monkeypatch.setattr(settings, "ollama_num_predict", 1536)
    assert original != InferenceCache.build_key(req)
    minus = request(refraccion={"od": {"esfera": 2, "cilindro": -1.5, "eje": 90}})
    plus = request(refraccion={"od": {"esfera": .5, "cilindro": 1.5, "eje": 180}})
    assert InferenceCache.build_key(minus) == InferenceCache.build_key(plus)


def test_educational_policy_change_invalidates_only_dual_cache(monkeypatch):
    import app.cache as cache_module
    req = request()
    legacy = req.model_copy(update={"salida_version": "clinica-v1"})
    dual_key = InferenceCache.build_key(req)
    legacy_key = InferenceCache.build_key(legacy)
    monkeypatch.setattr(cache_module, "DUAL_PROMPT_VERSION", "educacion-simple-v1")
    assert InferenceCache.build_key(req) != dual_key
    assert InferenceCache.build_key(legacy) == legacy_key


async def api_pair(payload, monkeypatch, *, simultaneous=False):
    monkeypatch.setattr(main.settings, "api_key", "secret")
    monkeypatch.setattr(main, "_inference_semaphore", asyncio.Semaphore(1))
    inference_cache.clear()
    main.app.dependency_overrides[main.get_http_client] = lambda: object()
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://api") as client:
            post = lambda: client.post("/inferencia/impresion-clinica", json=payload, headers={"Authorization": "Bearer secret"})
            responses = await asyncio.gather(post(), post()) if simultaneous else [await post(), await post()]
            return responses
    finally:
        main.app.dependency_overrides.pop(main.get_http_client, None)
        inference_cache.clear()


def test_http_metadata_and_original_pair_are_cached(monkeypatch):
    calls = fake_provider(monkeypatch, [("Se registra refraccion final.", {})])
    responses = asyncio.run(api_pair(request().model_dump(mode="json"), monkeypatch))
    first, second = [r.json() for r in responses]
    assert all(r.status_code == 200 for r in responses)
    assert first["cached"] is False and second["cached"] is True and len(calls) == 1
    assert first["generacion"] == second["generacion"]
    assert first["generacion"]["origen_clinico"] == "llm"
    assert first["explicacion_paciente_estado"] == "plantilla"
    assert first["generacion"]["origen_explicacion"] == "plantilla"
    assert first["explicacion_paciente"] == build_patient_template(build_patient_profile(request()))
    assert first["generacion"]["pipeline_version"] == "clinica-paciente-v1"
    assert len(first["generacion"]["base_hash_api"]) == 64


def test_identical_requests_waiting_for_gpu_deduplicate_under_slot(monkeypatch):
    calls = []
    async def call(*args, **kwargs):
        calls.append(1)
        await asyncio.sleep(.03)
        return "Se registra refraccion final.", {}
    monkeypatch.setattr(inference.ollama_provider, "call", call)
    responses = asyncio.run(api_pair(request().model_dump(mode="json"), monkeypatch, simultaneous=True))
    assert all(r.status_code == 200 for r in responses)
    assert len(calls) == 1
    assert sorted(r.json()["cached"] for r in responses) == [False, True]


def test_rejected_patient_failure_is_not_cached(monkeypatch):
    calls = fake_provider(monkeypatch, [("Se registra refraccion final.", {})])
    monkeypatch.setattr(inference, "build_patient_template", lambda profile: None)
    responses = asyncio.run(api_pair(request().model_dump(mode="json"), monkeypatch))
    assert len(calls) == 2 and all(r.json()["cached"] is False for r in responses)
    assert all(r.json()["explicacion_paciente_estado"] == "rechazada" for r in responses)


def test_urgent_fallback_has_no_false_llm_metadata_and_is_not_cached(monkeypatch):
    calls = fake_provider(monkeypatch, [("{", {"done_reason": "length"})])
    req = request(paciente={"motivo_consulta": "Diplopia desde hoy."})
    responses = asyncio.run(api_pair(req.model_dump(mode="json"), monkeypatch))
    assert len(calls) == 4
    for response in responses:
        assert response.status_code == 200
        body = response.json()
        assert body["origen"] == "determinista" and "generacion" not in body
        assert body["explicacion_paciente"] is None and body["explicacion_paciente_estado"] == "rechazada"
        assert body["cached"] is False and body["salida_version"] == "clinica-paciente-v1"


def test_structural_failure_502_without_urgency_and_no_cache(monkeypatch):
    calls = fake_provider(monkeypatch, [("", {})])
    responses = asyncio.run(api_pair(request().model_dump(mode="json"), monkeypatch))
    assert len(calls) == 2 and all(r.status_code == 502 for r in responses)


@pytest.mark.parametrize("content", [None, {}, ""])
def test_invalid_http_provider_content_retries_bounded_and_dual_is_502(monkeypatch, content):
    calls = []
    async def handler(req):
        calls.append(1)
        return httpx.Response(200, json={"message": {"content": content}, "done_reason": "stop"})
    original_call = ollama.call
    async def call(system, user, unused, **options):
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            return await original_call(system, user, client, **options)
    monkeypatch.setattr(inference.ollama_provider, "call", call)
    responses = asyncio.run(api_pair(request().model_dump(mode="json"), monkeypatch))
    assert all(r.status_code == 502 for r in responses)
    assert len(calls) == 2 * settings.ollama_max_retries


def test_f0_invalidates_previous_dual_key_and_preserves_fixed_legacy_key(monkeypatch):
    import app.cache as cache_module
    # Valores fijados antes de F0, independientes del .env de cada equipo.
    for name, value in {
        "ollama_model": "qwen3.5:9b", "ollama_num_ctx": 8192,
        "ollama_num_predict": 1024, "ollama_dual_num_predict": 1024,
        "ollama_temperature": .2, "ollama_repeat_penalty": 1.,
        "ollama_top_p": .8, "ollama_top_k": 20, "ollama_min_p": 0.,
        "ollama_seed": 42, "max_sentences": 10,
    }.items():
        monkeypatch.setattr(settings, name, value)
    req = request()
    legacy = req.model_copy(update={"salida_version": "clinica-v1"})
    previous_dual_key = "556d2df835232926f70eda89f8fd934e5e4756bb2d22aa32aff039f998842cc6"
    assert InferenceCache.build_key(legacy) == "d9853e8f43c21d862ddf96292f42825f5ac166381c523e3b0de4e0ca29c432d9"
    assert InferenceCache.build_key(req) != previous_dual_key
    monkeypatch.setattr(cache_module, "DUAL_PROMPT_VERSION", "educacion-catalogo-v2")
    monkeypatch.setattr(cache_module, "PATIENT_PROFILE_VERSION", "refraccion-final-lejos-v1")
    assert InferenceCache.build_key(req) == previous_dual_key


@pytest.mark.parametrize("rx,state", [
    ({"od": {"esfera": 0, "cilindro": 0}, "oi": {"esfera": 0, "cilindro": 0}}, "sin_componentes_refractivos"),
    ({"od": {"esfera": -1}, "oi": {"esfera": 0, "cilindro": 0}}, "datos_incompletos"),
])
def test_http_nonapplicable_pairs_are_preserved_and_cached(monkeypatch, rx, state):
    calls = fake_provider(monkeypatch, [("Se registra refraccion final.", {})])
    responses = asyncio.run(api_pair(request(refraccion=rx).model_dump(mode="json"), monkeypatch))
    assert len(calls) == 1
    assert all(r.status_code == 200 for r in responses)
    for response in responses:
        body = response.json()
        assert body["explicacion_paciente"] is None
        assert body["explicacion_paciente_estado"] == state
        assert body["generacion"]["origen_explicacion"] == "ninguno"
