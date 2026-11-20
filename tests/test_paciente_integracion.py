"""W1b: contrato HTTP completo con transporte simulado y tokenizador oficial offline."""
import asyncio
from contextlib import asynccontextmanager
import json
from pathlib import Path

import httpx
import pytest
from pydantic import ValidationError

import app.main as main
import app.inference as inference
from app.cache import inference_cache
from app.config import settings, Settings
from app.gpu_scheduler import GPUScheduler
from app.paciente import integracion, servicio, prompts
from app.paciente.contexto import construir_contexto
from app.providers import ollama
from app.tareas import presupuesto
from app.tareas.nucleo import metricas
from tests.test_paciente import candidato
from tests.test_paciente_presupuesto import tokenizador_oficial

HEADERS = {"Authorization": "Bearer secret"}
RUTA = "/v1/inferencia/receta-clinica"
CLINICO = "Se registra refraccion final para correccion de lejos."


def payload(**extra):
    return {"receta_id": "w1b", "salida_version": "clinica-paciente-v1",
        "refraccion": {"od": {"esfera": -2, "cilindro": 0}, "oi": {"esfera": -2, "cilindro": 0}}, **extra}


@pytest.fixture(autouse=True)
def limpio(monkeypatch):
    monkeypatch.setattr(settings, "api_key", "secret")
    monkeypatch.setattr(settings, "paciente_llm_habilitado", True)
    monkeypatch.setattr(settings, "paciente_omitir_si_espera", True)
    monkeypatch.setattr(main, "gpu_scheduler", GPUScheduler())
    inference_cache.clear(); integracion.paciente_cache.clear(); metricas.datos.clear()
    yield
    inference_cache.clear(); integracion.paciente_cache.clear(); metricas.datos.clear()


@asynccontextmanager
async def api(responder=None):
    llamadas = []
    async def handler(req):
        cuerpo = json.loads(req.content)
        llamadas.append(cuerpo)
        system = cuerpo["messages"][0]["content"]
        etapa = "redaccion" if system == prompts.SYSTEM_REDACCION else "verificacion" if system == prompts.SYSTEM_VERIFICACION else "clinica"
        valor = await responder(etapa, cuerpo) if responder else None
        if valor is None:
            valor = CLINICO if etapa == "clinica" else candidato() if etapa == "redaccion" else {"valido": True}
        if isinstance(valor, httpx.Response):
            return valor
        return httpx.Response(200, json={"message": {"content": valor if isinstance(valor, str) else json.dumps(valor)},
            "done_reason": "stop", "prompt_eval_count": 100, "eval_count": 10})
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as proveedor:
        main.app.dependency_overrides[main.get_http_client] = lambda: proveedor
        try:
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://api", headers=HEADERS) as cliente:
                yield cliente, llamadas
        finally:
            main.app.dependency_overrides.pop(main.get_http_client, None)


def test_clinico_identico_bytes_y_tres_llamadas(tokenizador_oficial):
    async def run():
        async with api() as (c, llamadas):
            dual = (await c.post(RUTA, json=payload())).json()
            assert len(llamadas) == 3
            # Quitar solo la caché clínica para comparar ambas llamadas físicas.
            inference_cache.clear()
            legacy = (await c.post(RUTA, json=payload(salida_version="clinica-v1"))).json()
            assert dual["impresion_clinica"].encode() == legacy["impresion_clinica"].encode()
            assert llamadas[0] == llamadas[3]
            assert dual["explicacion_paciente_estado"] == "generada"
            assert dual["generacion"]["motivo_explicacion"] is None
            assert dual["generacion"]["paciente_version"] == servicio.VERSION
            assert all(l["think"] is False for l in llamadas)
            assert [l["options"]["num_predict"] for l in llamadas[:3]] == [settings.ollama_num_predict, 384, 32]
    asyncio.run(run())


def test_acciones_primero_en_exito_y_clinico_inmutable(tokenizador_oficial):
    async def run():
        req = payload(clinica={"fondo_de_ojo": "Lattice temporal en OI."})
        async with api() as (c, llamadas):
            r = await c.post(RUTA, json=req)
            assert r.status_code == 200
            obj = r.json()
            assert obj["explicacion_paciente_estado"] == "generada"
            caso = json.loads(llamadas[1]["messages"][1]["content"].split("\n", 1)[1])
            acciones = " ".join(caso["acciones_obligatorias"])
            assert acciones and obj["explicacion_paciente"].startswith(acciones + "\n\n")
            assert obj["explicacion_paciente"].endswith(candidato()["frases"][0]["texto"])
            assert obj["impresion_clinica"] == caso["hechos"][0]["contenido"]
    asyncio.run(run())


@pytest.mark.parametrize("motivo", ["validacion", "verificacion", "abstencion", "timeout", "presupuesto", "ocupado", "error"])
def test_cada_respaldo_por_http(monkeypatch, tokenizador_oficial, motivo):
    async def responder(etapa, cuerpo):
        if motivo == "validacion" and etapa == "redaccion": return {"frases": [{"texto": "Todo normal.", "fuentes": ["clinico"]}]}
        if motivo == "abstencion" and etapa == "redaccion": return {"frases": []}
        if motivo == "verificacion" and etapa == "verificacion": return {"valido": False}
        if motivo == "timeout" and etapa == "redaccion": raise httpx.ReadTimeout("simulado")
        if motivo == "error" and etapa == "redaccion": return httpx.Response(503)
    if motivo == "presupuesto":
        monkeypatch.setattr(presupuesto, "contar", lambda system, user, politica=None:
            8000 if system == prompts.SYSTEM_REDACCION else 100)
    if motivo == "ocupado":
        class Plan(GPUScheduler):
            @property
            def estadisticas(self): return {**super().estadisticas, "en_espera_interactiva": 1}
        monkeypatch.setattr(main, "gpu_scheduler", Plan())
    async def run():
        async with api(responder) as (c, llamadas):
            r = await c.post(RUTA, json=payload())
            assert r.status_code == 200
            obj = r.json()
            assert obj["impresion_clinica"] and obj["explicacion_paciente_estado"] == "plantilla"
            assert obj["generacion"]["motivo_explicacion"] == motivo
            assert obj["cached"] is False
            assert len(llamadas) == (3 if motivo == "verificacion" else 1 if motivo in ("ocupado", "presupuesto") else 2)
            assert not integracion.paciente_cache._store
    asyncio.run(run())


def test_timeout_exterior_tras_control_conserva_clinico(monkeypatch, tokenizador_oficial):
    async def colgar(*args, **kwargs): await asyncio.Event().wait()
    monkeypatch.setattr(integracion, "completar", colgar)
    monkeypatch.setattr(settings, "plazo_global_receta_s", .08)
    async def run():
        async with api() as (c, llamadas):
            r = await c.post(RUTA, json=payload())
            assert r.status_code == 200 and r.json()["impresion_clinica"]
            assert r.json()["generacion"]["motivo_explicacion"] == "timeout"
            assert len(llamadas) == 1
            assert not main.gpu_scheduler.estadisticas["ocupada"]
    asyncio.run(run())


def test_timeout_etapa_cancela_transporte_y_libera_turno(monkeypatch, tokenizador_oficial):
    cancelado = []
    async def responder(etapa, cuerpo):
        if etapa == "redaccion":
            try: await asyncio.Event().wait()
            finally: cancelado.append(True)
    monkeypatch.setattr(settings, "paciente_timeout_redaccion_s", .02)
    monkeypatch.setattr(settings, "paciente_minimo_redaccion_s", .001)
    async def run():
        async with api(responder) as (c, _):
            obj = (await c.post(RUTA, json=payload())).json()
            assert obj["generacion"]["motivo_explicacion"] == "timeout"
            assert cancelado == [True] and not main.gpu_scheduler.estadisticas["ocupada"]
    asyncio.run(run())


def test_cache_separada_reintenta_solo_paciente_y_flags(tokenizador_oficial):
    intentos = 0
    async def responder(etapa, cuerpo):
        nonlocal intentos
        if etapa == "redaccion":
            intentos += 1
            if intentos == 1: return {"frases": []}
    async def run():
        async with api(responder) as (c, llamadas):
            a = (await c.post(RUTA, json=payload())).json()
            assert len(llamadas) == 2 and not a["cached"]
            b = (await c.post(RUTA, json=payload())).json()
            assert len(llamadas) == 4 and not b["cached"]
            assert b["generacion"]["cache"] == {"clinico": True, "paciente": False}
            d = (await c.post(RUTA, json=payload())).json()
            assert len(llamadas) == 4 and d["cached"]
            assert d["generacion"]["cache"] == {"clinico": True, "paciente": True}
            assert a["impresion_clinica"] == b["impresion_clinica"] == d["impresion_clinica"]
    asyncio.run(run())


@pytest.mark.parametrize("espera", ["ocupado", "timeout"])
def test_clinico_en_cache_y_espera_paciente_falla(monkeypatch, tokenizador_oficial, espera):
    async def run():
        async with api() as (c, llamadas):
            await c.post(RUTA, json=payload(salida_version="clinica-v1"))
            if espera == "ocupado": monkeypatch.setattr(settings, "max_queue_size", 0)
            else: monkeypatch.setattr(settings, "plazo_global_receta_s", .03)
            async with main.gpu_scheduler.turno("interactiva"):
                r = await c.post(RUTA, json=payload())
            assert r.status_code == 200 and len(llamadas) == 1
            assert r.json()["generacion"]["motivo_explicacion"] == espera
            assert r.json()["generacion"]["cache"] == {"clinico": True, "paciente": False}
    asyncio.run(run())


def test_plazo_desde_llegada_antes_cola(monkeypatch, tokenizador_oficial):
    monkeypatch.setattr(settings, "plazo_global_receta_s", .04)
    async def run():
        async with api() as (c, llamadas):
            async with main.gpu_scheduler.turno("interactiva"):
                r = await c.post(RUTA, json=payload())
            assert r.status_code == 504 and not llamadas
            assert main.gpu_scheduler.en_cola == 0
    asyncio.run(run())


def test_cede_ante_otra_interactiva_real(tokenizador_oficial):
    async def run():
        inicio, liberar = asyncio.Event(), asyncio.Event()
        async def responder(etapa, cuerpo):
            if etapa == "clinica":
                inicio.set(); await liberar.wait()
        async with api(responder) as (c, llamadas):
            primero = asyncio.create_task(c.post(RUTA, json=payload()))
            await inicio.wait()
            segundo = asyncio.create_task(c.post(RUTA, json=payload(receta_id="otro", paciente={"edad": 30})))
            while not main.gpu_scheduler.estadisticas["en_espera_interactiva"]: await asyncio.sleep(0)
            liberar.set()
            a, b = await asyncio.gather(primero, segundo)
            assert a.json()["generacion"]["motivo_explicacion"] == "ocupado"
            assert b.status_code == 200
    asyncio.run(run())


def test_interruptor_no_llama_paciente_incluso_cache_validada(monkeypatch, tokenizador_oficial):
    async def run():
        async with api() as (c, llamadas):
            await c.post(RUTA, json=payload())
            monkeypatch.setattr(settings, "paciente_llm_habilitado", False)
            obj = (await c.post(RUTA, json=payload())).json()
            assert len(llamadas) == 3 and obj["explicacion_paciente_estado"] == "plantilla"
            assert obj["generacion"]["motivo_explicacion"] is None and not obj["cached"]
    asyncio.run(run())


def test_registro_y_metricas_etapas_intentos_sin_contenido(tokenizador_oficial):
    clinicas = 0
    async def responder(etapa, cuerpo):
        nonlocal clinicas
        if etapa == "clinica":
            clinicas += 1
            if clinicas == 1: return httpx.Response(503)
    async def run():
        async with api(responder) as (c, llamadas):
            await c.post(RUTA, json=payload())
            tabla = (await c.get("/v1/tareas")).json()["explicacion-paciente"]
            assert tabla["padre"] == "receta-clinica" and tabla["montaje"] == "manual"
            assert tabla["prioridad"] == "interactiva" and tabla["usa_llm"] is True
            assert [(x["etapa"], x["max_tokens_entrada"], x["num_predict"]) for x in tabla["llamadas"]] == [("redaccion", 7000, 384), ("verificacion", 7400, 32)]
            m = (await c.get("/v1/metricas")).json()
            assert m["receta-clinica"]["etapas"]["clinica"]["llamadas"] == 2
            assert m["explicacion-paciente"]["etapas"]["redaccion"]["llamadas"] == 1
            assert m["explicacion-paciente"]["etapas"]["verificacion"]["llamadas"] == 1
            plano = json.dumps(m)
            assert all(x not in plano for x in ("miopía", "letreros", "messages", "frases", "impresion_clinica", "w1b"))
    asyncio.run(run())


@pytest.mark.parametrize("ctx", [4096, 16384])
def test_num_ctx_efectivo_lo_pone_proveedor(monkeypatch, tokenizador_oficial, ctx):
    monkeypatch.setattr(settings, "ollama_num_ctx", ctx)
    assert "num_ctx" not in prompts.opciones("redaccion")
    async def run():
        async with api() as (c, llamadas):
            obj = (await c.post(RUTA, json=payload())).json()
            assert obj["explicacion_paciente_estado"] == "generada"
            assert all(x["options"]["num_ctx"] == min(ctx, settings.limite_contexto_tokens, 8192) for x in llamadas)
    asyncio.run(run())


@pytest.mark.parametrize("politica,esperado", [("estricto", 413), ("conservador", 200)])
def test_clinica_sin_exactitud_politica_del_dueno(monkeypatch, politica, esperado):
    monkeypatch.setattr(presupuesto.contador, "disponible", lambda: False)
    monkeypatch.setattr(settings, "presupuesto_receta_sin_exacto", politica)
    async def run():
        async with api() as (c, llamadas):
            from scripts.probar_enrutado import golden
            r = await c.post(RUTA, json={**golden(), "salida_version": "clinica-v1"})
            assert r.status_code == esperado and len(llamadas) == (1 if esperado == 200 else 0)
    asyncio.run(run())


@pytest.mark.parametrize("etapa", ["redaccion", "verificacion"])
def test_paciente_siempre_estricto_en_proveedor(monkeypatch, etapa):
    monkeypatch.setattr(presupuesto.contador, "disponible", lambda: False)
    etiquetas = []
    original = presupuesto.contar
    def contar(s, u, politica=None):
        etiquetas.append(politica)
        return original(s, u, politica)
    monkeypatch.setattr(presupuesto, "contar", contar)
    async def run():
        # La política heredada conservadora nunca se usa para esta llamada.
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: pytest.fail("Envío fuera del presupuesto"))) as client:
            with pytest.raises(presupuesto.PresupuestoExcedido):
                await ollama.call("s", "á" * 5000, client, options=prompts.opciones(etapa),
                    tarea="explicacion-paciente", etapa=etapa, politica="conservador")
    asyncio.run(run())
    assert etiquetas == ["estricto"]


def test_dual_413_antes_control(tokenizador_oficial, monkeypatch):
    monkeypatch.setattr(presupuesto, "contar", lambda *a, **k: 8000)
    async def run():
        async with api() as (c, llamadas):
            r = await c.post(RUTA, json=payload())
            assert r.status_code == 413 and not llamadas
    asyncio.run(run())


def test_hallazgos_sin_refraccion_admiten_generada(tokenizador_oficial):
    async def responder(etapa, cuerpo):
        if etapa == "redaccion": return candidato("La revisión de la retina puede ayudar a estudiar lo observado.", ["clinico"])
    async def run():
        async with api(responder) as (c, llamadas):
            r = await c.post(RUTA, json=payload(refraccion={}, clinica={"fondo_de_ojo": "Lattice temporal en OI."}))
            assert r.status_code == 200 and r.json()["explicacion_paciente_estado"] == "generada"
            assert len(llamadas) == 3
    asyncio.run(run())


@pytest.mark.parametrize("nombre", ["paciente_timeout_redaccion_s", "paciente_timeout_verificacion_s", "paciente_minimo_redaccion_s", "paciente_minimo_verificacion_s", "plazo_global_receta_s"])
def test_config_rechaza_plazos_no_positivos(nombre):
    with pytest.raises(ValidationError): Settings(_env_file=None, **{nombre: 0})


def test_clave_paciente_canonica_versionada_y_opciones(monkeypatch):
    a = construir_contexto(impresion_clinica_final="Texto.")
    original = integracion.clave_paciente(a)
    assert original == integracion.clave_paciente(a)
    monkeypatch.setattr(prompts, "GLOSARIO_VERSION", "otra")
    assert original != integracion.clave_paciente(a)
    otra = integracion.clave_paciente(a)
    monkeypatch.setattr(settings, "ollama_num_ctx", 4096)
    assert otra != integracion.clave_paciente(a)


@pytest.mark.parametrize("etapa", ["redaccion", "verificacion"])
def test_proveedor_fronteras_exactas_7782_7783(tokenizador_oficial, etapa):
    predict = prompts.opciones(etapa)["num_predict"]
    base = len(tokenizador_oficial.encode(presupuesto.renderizar("", "")).ids)
    user = " x" * (7782 - predict - base)
    enviadas = []
    def handler(req):
        enviadas.append(req)
        return httpx.Response(200, json={"message": {"content": "ok"}})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c:
            await ollama.call("", user, c, options=prompts.opciones(etapa), tarea="explicacion-paciente", etapa=etapa)
            with pytest.raises(presupuesto.PresupuestoExcedido):
                await ollama.call("", user + " x", c, options=prompts.opciones(etapa), tarea="explicacion-paciente", etapa=etapa)
    asyncio.run(run())
    assert len(enviadas) == 1


def test_script_enrutado_simulado():
    import subprocess
    import sys
    resultado = subprocess.run([sys.executable, "scripts/probar_enrutado.py", "--modo", "simulado"],
        capture_output=True, encoding="utf-8", timeout=60,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    assert resultado.returncode == 0, resultado.stdout + resultado.stderr
    assert "(clinica-paciente-v1) | 3 |" in resultado.stdout
    assert "(dual-respaldo) | 2 |" in resultado.stdout


@pytest.mark.parametrize("version", ["clinica-v1", "clinica-paciente-v1"])
@pytest.mark.parametrize("politica,esperado", [("estricto", 413), ("conservador", 200)])
def test_politicas_clinicas_en_ambas_presentaciones(monkeypatch, version, politica, esperado):
    from scripts.probar_enrutado import golden
    monkeypatch.setattr(presupuesto.contador, "disponible", lambda: False)
    monkeypatch.setattr(settings, "presupuesto_receta_sin_exacto", politica)
    async def run():
        async with api() as (c, llamadas):
            r = await c.post(RUTA, json={**golden(), "salida_version": version})
            assert r.status_code == esperado
            assert len(llamadas) == (0 if esperado == 413 else 1)
            if esperado == 200 and version == "clinica-paciente-v1":
                assert r.json()["generacion"]["motivo_explicacion"] == "presupuesto"
    asyncio.run(run())


def test_acciones_solas_excesivas_rechazada_error_por_http(monkeypatch, tokenizador_oficial):
    monkeypatch.setattr(integracion.contexto, "contexto_desde_receta", lambda req, texto, cor:
        construir_contexto(impresion_clinica_final=texto, acciones_obligatorias=["x" * 2001]))
    monkeypatch.setattr(settings, "paciente_llm_habilitado", False)
    async def run():
        async with api() as (c, llamadas):
            r = await c.post(RUTA, json=payload())
            assert r.status_code == 200 and len(llamadas) == 1
            assert r.json()["explicacion_paciente"] is None
            assert r.json()["explicacion_paciente_estado"] == "rechazada"
            assert r.json()["generacion"]["motivo_explicacion"] == "error"
    asyncio.run(run())


def test_metadata_cuenta_todas_las_acciones_sin_mapear(monkeypatch, tokenizador_oficial):
    from types import SimpleNamespace
    monkeypatch.setattr("app.paciente.acciones.extraer_acciones", lambda cor: [
        SimpleNamespace(texto="Primera acción.", mapeada=False),
        SimpleNamespace(texto="Segunda acción.", mapeada=False)])
    monkeypatch.setattr(settings, "paciente_llm_habilitado", False)
    async def run():
        async with api() as (c, _):
            r = await c.post(RUTA, json=payload())
            assert r.status_code == 200
            assert r.json()["generacion"]["acciones_sin_mapear"] == 2
            assert r.json()["explicacion_paciente"].startswith("Primera acción. Segunda acción.")
    asyncio.run(run())
