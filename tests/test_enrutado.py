import asyncio
import json

import httpx
import pytest

import app.main as main
from app.cache import inference_cache
from app.gpu_scheduler import GPUScheduler
from app.providers import ollama
from app.prompt_builder import build_system_prompt
from app.seguimiento.prompts import SYSTEM_PROMPT_REDACCION, SYSTEM_PROMPT_VERIFICACION
from app.seguimiento.servicio import seguimiento_cache
from tests.seguimiento_helpers import fixture

HEADERS = {"Authorization": "Bearer secret"}
CLINICA = "/inferencia/impresion-clinica"
SEGUIMIENTO = "/v1/inferencia/seguimiento-whatsapp"


@pytest.fixture
def registro(monkeypatch):
    monkeypatch.setattr(main.settings, "api_key", "secret")
    monkeypatch.setattr(main, "gpu_scheduler", GPUScheduler())
    monkeypatch.setattr(main.settings, "paciente_llm_habilitado", False)
    llamadas = []
    def handler(req):
        cuerpo = json.loads(req.content)
        llamadas.append(cuerpo)
        formato = cuerpo.get("format", {}).get("properties", {})
        texto = (json.dumps(fixture("g1-modelo-redaccion")) if "apertura" in formato else
                 json.dumps(fixture("modelo-verificacion-false")) if "afirma_algo_de_salud" in formato else
                 "Se registra refraccion final para correccion de lejos.")
        return httpx.Response(200, json={"message": {"content": texto}, "done_reason": "stop"})
    proveedor = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    main.app.dependency_overrides[main.get_http_client] = lambda: proveedor
    inference_cache.clear()
    seguimiento_cache.clear()
    yield llamadas
    main.app.dependency_overrides.pop(main.get_http_client, None)
    asyncio.run(proveedor.aclose())
    inference_cache.clear()
    seguimiento_cache.clear()


def payload(dual=False):
    return {"receta_id": "routing", "refraccion": {"od": {"esfera": -3 if dual else -2, "cilindro": 0}, "oi": {"esfera": -3 if dual else -2, "cilindro": 0}},
            "salida_version": "clinica-paciente-v1" if dual else "clinica-v1"}


def test_tabla_coincide_con_llamadas_y_alias(registro):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://api", headers=HEADERS) as c:
            tabla = (await c.get("/v1/tareas")).json()
            a = await c.post(CLINICA, json=payload())
            assert a.status_code == 200 and len(registro) == 1
            b = await c.post(CLINICA, json=payload(True))
            assert b.status_code == 200 and len(registro) == 2
            assert b.json()["explicacion_paciente_estado"] == "plantilla"
            alias = await c.post("/v1/inferencia/receta-clinica", json=payload())
            assert alias.status_code == 200 and len(registro) == 2
            assert {k: v for k, v in alias.json().items() if k != "cached"} == a.json()
            inference_cache.clear()
            fresco = await c.post("/v1/inferencia/receta-clinica", json=payload())
            assert fresco.json() == a.json() and len(registro) == 3
            r = await c.post(SEGUIMIENTO, json=fixture("g1-request"))
            assert r.json()["estado"] == "generada" and len(registro) == 5
            assert all("format" not in x for x in registro[:3])
            assert all(x["messages"][0]["content"] == build_system_prompt() for x in registro[:3])
            assert registro[3]["messages"][0]["content"] == SYSTEM_PROMPT_REDACCION
            assert registro[4]["messages"][0]["content"] == SYSTEM_PROMPT_VERIFICACION
            assert len({x["messages"][0]["content"] for x in registro[2:]}) == 3
            assert set(registro[3]["format"]["properties"]) == {"apertura", "hechos", "invitacion"}
            assert set(registro[4]["format"]["properties"]) == {"afirma_algo_de_salud"}
            assert len(tabla["explicacion-paciente"]["llamadas"]) == 2
            assert tabla["explicacion-paciente"]["usa_llm"] is True
            assert tabla["explicacion-paciente"]["prioridad"] == "interactiva"
            assert tabla["explicacion-paciente"]["padre"] == "receta-clinica"
            for tarea, cuerpos in [("receta-clinica", registro[:1]), ("seguimiento-whatsapp", registro[3:])]:
                for etapa, cuerpo in zip(tabla[tarea]["llamadas"], cuerpos):
                    assert etapa["temperature"] == cuerpo["options"]["temperature"]
                    assert etapa["num_predict"] == cuerpo["options"]["num_predict"]
                    assert (etapa["formato"] == "json-schema") == ("format" in cuerpo)
            assert [c["options"]["temperature"] for c in registro[3:]] == [.4, 0.0]
            return tabla
    tabla = asyncio.run(run())
    assert tabla["receta-clinica"]["prioridad"] == "interactiva"
    assert tabla["seguimiento-whatsapp"]["prioridad"] == "fondo"


def test_receta_entre_redaccion_y_verificacion(monkeypatch, registro):
    async def run():
        redaccion = asyncio.Event()
        liberar = asyncio.Event()
        original = ollama.call
        async def call(system, user, client, **kwargs):
            resultado = await original(system, user, client, **kwargs)
            if system == SYSTEM_PROMPT_REDACCION:
                redaccion.set()
                await liberar.wait()
            elif system == build_system_prompt():
                # Mantener la receta hasta que se compruebe el rechazo de verificación.
                await liberar_receta.wait()
            return resultado
        liberar_receta = asyncio.Event()
        monkeypatch.setattr(ollama, "call", call)
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://api", headers=HEADERS) as c:
            seguimiento = asyncio.create_task(c.post(SEGUIMIENTO, json=fixture("g1-request")))
            await redaccion.wait()
            receta = asyncio.create_task(c.post(CLINICA, json=payload()))
            while main.gpu_scheduler.estadisticas["en_espera_interactiva"] == 0:
                await asyncio.sleep(0)
            liberar.set()
            r = await seguimiento
            assert r.json()["motivo"] == "ia_ocupada"
            liberar_receta.set()
            assert (await receta).status_code == 200
            assert len(registro) == 2
            assert "apertura" in registro[0]["format"]["properties"]
            assert "format" not in registro[1]
    asyncio.run(run())


def test_tareas_autenticada_y_settings_vivos(monkeypatch):
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://api") as c:
            assert (await c.get("/v1/tareas")).status_code == 401
            monkeypatch.setattr(main.settings, "seguimiento_temperature", .7)
            monkeypatch.setattr(main.settings, "seguimiento_num_predict", 222)
            tabla = (await c.get("/v1/tareas", headers=HEADERS)).json()
            assert tabla["seguimiento-whatsapp"]["llamadas"][0]["temperature"] == .7
            assert tabla["seguimiento-whatsapp"]["llamadas"][0]["num_predict"] == 222
    monkeypatch.setattr(main.settings, "api_key", "secret")
    asyncio.run(run())


def test_proveedor_clinico_conserva_cuerpo_y_reintentos(monkeypatch):
    cuerpos = []
    def handler(req):
        cuerpos.append(json.loads(req.content))
        if len(cuerpos) == 1:
            return httpx.Response(503)
        return httpx.Response(200, json={"message": {"content": "Texto clínico."}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            texto, _ = await ollama.call("system", "user", c)
            assert texto == "Texto clínico."
    monkeypatch.setattr(main.settings, "ollama_max_retries", 2)
    asyncio.run(run())
    esperado = {"model": main.settings.ollama_model,
                "messages": [{"role": "system", "content": "system"}, {"role": "user", "content": "user"}],
                "stream": False, "think": False, "options": ollama._OLLAMA_OPTIONS}
    assert cuerpos == [esperado, esperado]


def test_proveedor_mezcla_opciones_y_sin_reintentos(monkeypatch):
    cuerpos = []
    def handler(req):
        cuerpos.append(json.loads(req.content))
        return httpx.Response(503)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            with pytest.raises(httpx.HTTPStatusError):
                await ollama.call("s", "u", c, options={"seed": 101, "temperature": .4},
                                  num_predict=320, format={"type": "object"}, max_retries=1)
    asyncio.run(run())
    assert len(cuerpos) == 1
    assert cuerpos[0]["options"] == {**ollama._OLLAMA_OPTIONS, "seed": 101, "temperature": .4, "num_predict": 320}
    assert cuerpos[0]["format"] == {"type": "object"}
