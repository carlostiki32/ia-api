import asyncio
import json
import re
import time

import httpx
import pytest

import app.main as main
from app.gpu_scheduler import GPUScheduler
from app.providers import ollama
from app.seguimiento.servicio import seguimiento_cache, clave_cache, SeguimientoCache, respaldo
from tests.seguimiento_helpers import fixture, request, sin_variables

URL = "/v1/inferencia/seguimiento-whatsapp"
HEADERS = {"Authorization": "Bearer secret"}


@pytest.fixture(autouse=True)
def preparar(monkeypatch):
    monkeypatch.setattr(main.settings, "api_key", "secret")
    monkeypatch.setattr(main, "gpu_scheduler", GPUScheduler())
    seguimiento_cache.clear()
    main.app.dependency_overrides[main.get_http_client] = lambda: object()
    yield
    main.app.dependency_overrides.pop(main.get_http_client, None)
    seguimiento_cache.clear()


def proveedor(monkeypatch, uso=None, redaccion=None, verificacion=None, error=None, demora=0):
    llamadas = []
    async def call(system, user, client, **kwargs):
        llamadas.append((system, user, kwargs))
        if demora:
            await asyncio.sleep(demora)
        if error:
            raise error
        formato = kwargs.get("format", {})
        props = formato.get("properties", {}) if isinstance(formato, dict) else {}
        if "uso_lentes" in props:
            resultado = fixture("g1-modelo-uso") if uso is None else uso
        elif "apertura" in props:
            resultado = fixture("g1-modelo-redaccion") if redaccion is None else redaccion
        elif "afirma_algo_de_salud" in props:
            resultado = fixture("modelo-verificacion-false") if verificacion is None else verificacion
        else:
            resultado = fixture("g1-modelo-uso")
        return resultado if isinstance(resultado, str) else json.dumps(resultado), {}
    monkeypatch.setattr(ollama, "call", call)
    return llamadas


async def post(payload=None, headers=HEADERS):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as client:
        return await client.post(URL, json=fixture("g1-request") if payload is None else payload, headers=headers)


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer otro"}])
def test_auth(headers):
    assert asyncio.run(post(headers=headers)).status_code == 401


def test_sin_api_key(monkeypatch):
    monkeypatch.setattr(main.settings, "api_key", "")
    assert asyncio.run(post()).status_code == 500


@pytest.mark.parametrize("cambio", [
    {"extra": 1},
    {"contrato_version": "v1"},
    {"tramo_edad": "menor"},
    {"paciente_ref": "ABC"},
    {"variante": 1001},
    {"recetas_previas": -1},
    {"meses_desde_ultima_receta": 601},
    {"costo": "gratis"},
    {"rx_lejos": {"od": {"esfera": 1, "cilindro": 0, "add": None, "eje": 90},
                  "oi": {"esfera": 0, "cilindro": 0, "add": None}}},
    {"estado_seguimiento": "vencido", "fecha_revision": "2026-12-15"},
    {"estado_seguimiento": "vencido", "meses_periodo": 12},
    {"contexto_uso": {"campo_no_permitido": "valor"}},
])
def test_validacion_request(cambio):
    assert asyncio.run(post({**fixture("g1-request"), **cambio})).status_code == 422


def test_g1_generada_y_cache_y_semilla(monkeypatch):
    llamadas = proveedor(monkeypatch)
    async def run():
        primero = (await post()).json()
        segundo = (await post({**fixture("g1-request"), "paciente_ref": "0123456789abcdef"})).json()
        tercero = (await post({**fixture("g1-request"), "variante": 1})).json()
        return primero, segundo, tercero
    a, b, c = asyncio.run(run())
    assert sin_variables(a) == sin_variables(fixture("g1-respuesta-generada"))
    assert re.fullmatch("[a-f0-9]{64}", a["generacion"]["base_hash_api"])
    assert not a["generacion"]["cached"] and b["generacion"]["cached"]
    assert a["generacion"]["base_hash_api"] != c["generacion"]["base_hash_api"]
    assert len(llamadas) == 6
    assert llamadas[1][2]["options"]["seed"] == main.settings.ollama_seed
    assert llamadas[4][2]["options"]["seed"] == main.settings.ollama_seed + 1
    assert all(c[2]["max_retries"] == 1 for c in llamadas)


def test_flujo_tres_etapas_y_orden(monkeypatch):
    llamadas = proveedor(monkeypatch)
    r = asyncio.run(post()).json()
    assert r["estado"] == "generada"
    assert len(llamadas) == 3
    # 1. uso
    assert "uso_lentes" in llamadas[0][2]["format"]["properties"]
    assert llamadas[0][2]["options"]["temperature"] == 0.0
    # 2. redaccion
    assert "apertura" in llamadas[1][2]["format"]["properties"]
    assert llamadas[1][2]["options"]["temperature"] == 0.4
    # 3. verificacion
    assert "afirma_algo_de_salud" in llamadas[2][2]["format"]["properties"]
    assert llamadas[2][2]["options"]["temperature"] == 0.0


def test_uso_invalido_recurre_a_reglas(monkeypatch):
    proveedor(monkeypatch, uso={"uso_lentes": "invalido", "fuente": "ninguna"})
    r = asyncio.run(post()).json()
    assert r["estado"] == "generada"
    assert r["uso_lentes"] == "estudiar"
    assert r["origen_uso"] == "reglas"


def test_verificacion_rechazada_recurre_a_respaldo(monkeypatch):
    proveedor(monkeypatch, verificacion={"afirma_algo_de_salud": True})
    r = asyncio.run(post()).json()
    assert r["estado"] == "plantilla"
    assert r["motivo"] == "verificacion"


@pytest.mark.parametrize("opciones,motivo", [
    ({"verificacion": {"afirma_algo_de_salud": True}}, "verificacion"),
    ({"verificacion": "invalido"}, "verificacion"),
    ({"verificacion": {"afirma_algo_de_salud": 0}}, "verificacion"),
    ({"redaccion": "no json"}, "json_invalido"),
    ({"redaccion": {"apertura": "Hola :paciente de :clinica. " + "palabras largas "*40, "hechos": [], "cierre": "CI_INC_1"}}, "validacion:palabras"),
    ({"error": httpx.ConnectError("secreto que no debe aparecer")}, "ollama_error"),
    ({"demora": 1}, "ia_timeout"),
])
def test_respaldos(monkeypatch, opciones, motivo, caplog):
    proveedor(monkeypatch, **opciones)
    monkeypatch.setattr(main.settings, "seguimiento_timeout", .02)
    r = asyncio.run(post())
    assert r.status_code == 200
    assert r.json()["estado"] == "plantilla" and r.json()["motivo"] == motivo
    assert not seguimiento_cache._store
    assert "secreto que no debe aparecer" not in caplog.text


@pytest.mark.parametrize("esperando", [False, True])
def test_interactiva_rechaza_sin_esperar(monkeypatch, esperando):
    llamadas = proveedor(monkeypatch)
    async def run():
        async with main.gpu_scheduler.turno("fondo" if esperando else "interactiva"):
            tarea = None
            if esperando:
                async def receta():
                    async with main.gpu_scheduler.turno("interactiva"):
                        pass
                tarea = asyncio.create_task(receta())
                await asyncio.sleep(0)
            inicio = time.monotonic()
            r = await post()
            assert time.monotonic() - inicio < .2
            if tarea:
                tarea.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await tarea
            return r
    assert asyncio.run(run()).json()["motivo"] == "ia_ocupada"
    assert llamadas == []


def test_cache_versiones_opciones_y_semilla_negativa(monkeypatch):
    from app.seguimiento import servicio
    req = request()
    clave = clave_cache(req)
    for nombre, valor in [("seguimiento_temperature", .5), ("verificacion_num_predict", 40), ("ollama_model", "otro")]:
        with monkeypatch.context() as m:
            m.setattr(main.settings, nombre, valor)
            assert clave_cache(req) != clave
    monkeypatch.setattr(main.settings, "ollama_seed", -1)
    assert servicio.opciones_generacion(request(variante=20))["seed"] == -1
    monkeypatch.setattr(servicio, "VERIFICACION_VERSION", "otra")
    assert clave_cache(req) != clave


def test_cache_lru_ttl_copias_y_solo_generadas(monkeypatch):
    from app.seguimiento import servicio
    cache = SeguimientoCache(max_size=1, ttl_seconds=2)
    r = respaldo(request())
    r.partes.hechos = ["progresivo_zonas"]
    cache.put("a", r)
    assert cache.get("a") is None
    r.estado = "generada"
    cache.put("a", r)
    copia = cache.get("a")
    copia.partes.hechos.clear()
    assert cache.get("a").partes.hechos == ["progresivo_zonas"]
    cache.put("b", r)
    assert cache.get("a") is None
    ahora = servicio.time.monotonic()
    monkeypatch.setattr(servicio.time, "monotonic", lambda: ahora + 3)
    assert cache.get("b") is None


def test_logs_sin_contenido_incluso_normalizacion(monkeypatch, caplog):
    import logging
    proveedor(monkeypatch)
    datos = fixture("g1-request")
    datos["rx_lejos"]["od"]["esfera"] = 12345.6789
    with caplog.at_level(logging.DEBUG):
        asyncio.run(post(datos))
    for contenido in ("12345.6789", "Se acerca", ":paciente", ":clinica", "afirma_algo_de_salud", "rx_lejos", "Estudiante"):
        assert contenido not in caplog.text
    assert datos["paciente_ref"] in caplog.text


def test_user_prompt_minimizado_y_verificacion_sin_hechos():
    from app.seguimiento.elegibilidad import hechos_elegibles
    from app.seguimiento.prompts import build_user_prompt_redaccion, build_user_prompt_verificacion
    req = request(meses_desde_ultima_receta=599, recetas_previas=937)
    texto = build_user_prompt_redaccion(req, hechos_elegibles(req, "desconocido"), "desconocido", ["CI_INC_1"])
    assert "599" not in texto and "937" not in texto
    assert req.paciente_ref not in texto
    assert "esfera" not in texto and "meses" not in texto
    esperado = [f"{id}:" for id in hechos_elegibles(req, "desconocido")]
    assert [linea.split(":", 1)[0] + ":" for linea in texto.splitlines() if any(linea.startswith(x) for x in esperado)] == esperado
    verificacion = json.loads(build_user_prompt_verificacion("apertura"))
    assert verificacion == {"apertura": "apertura"}


@pytest.mark.parametrize("fallo", ["error", "timeout"])
def test_fallo_en_verificacion(monkeypatch, fallo):
    llamadas = 0
    async def call(*args, **kwargs):
        nonlocal llamadas
        llamadas += 1
        if llamadas == 1:
            return json.dumps(fixture("g1-modelo-uso")), {}
        if llamadas == 2:
            return json.dumps(fixture("g1-modelo-redaccion")), {}
        if fallo == "timeout":
            await asyncio.sleep(1)
        raise httpx.ReadTimeout("contenido privado")
    monkeypatch.setattr(ollama, "call", call)
    monkeypatch.setattr(main.settings, "seguimiento_timeout", .02)
    r = asyncio.run(post()).json()
    assert llamadas == 3
    assert r["motivo"] == ("ia_timeout" if fallo == "timeout" else "verificacion")


def test_health_publica_estadisticas_gpu():
    async def run():
        async with main.gpu_scheduler.turno("fondo"):
            async def receta():
                async with main.gpu_scheduler.turno("interactiva"):
                    pass
            tarea = asyncio.create_task(receta())
            await asyncio.sleep(0)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://test") as c:
                r = (await c.get("/health")).json()
            assert r["gpu"] == dict(ocupada=True, ocupante="fondo", en_espera_interactiva=1, en_espera_fondo=0)
            assert r["concurrencia"]["en_cola"] == 1
        await tarea
    asyncio.run(run())
