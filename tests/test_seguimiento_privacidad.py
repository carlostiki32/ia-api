import asyncio
import json

from app.gpu_scheduler import GPUScheduler
from app.providers import ollama
from app.seguimiento.prompts import build_user_prompt_redaccion
from app.seguimiento.servicio import clave_cache, generar, seguimiento_cache
from tests.seguimiento_helpers import fixture, request

SENTINEL = "SENTINEL_PRIVACIDAD_SECRET_DATOS_PACIENTE_987654"


def test_user_prompt_redaccion_sin_contexto_uso():
    req = request(
        contexto_uso={
            "ocupacion": f"Ingeniero {SENTINEL}",
            "motivo_consulta": f"Molestia {SENTINEL}",
            "impresion_clinica": f"Astenopia {SENTINEL}",
            "explicacion_paciente": f"Detalle {SENTINEL}",
        }
    )
    prompt = build_user_prompt_redaccion(req, [], uso_lentes="trabajar", cierres_ids=["CI_INC_1"])
    assert SENTINEL not in prompt


def test_clave_cache_sin_contexto_uso_en_claro():
    req = request(
        contexto_uso={
            "ocupacion": f"Ingeniero {SENTINEL}",
            "motivo_consulta": f"Molestia {SENTINEL}",
            "impresion_clinica": f"Astenopia {SENTINEL}",
            "explicacion_paciente": f"Detalle {SENTINEL}",
        }
    )
    clave = clave_cache(req)
    assert SENTINEL not in clave


def test_flujo_completo_privacidad_centinela(monkeypatch):
    seguimiento_cache.clear()
    llamadas = []

    async def mock_call(system, user, client, **kwargs):
        llamadas.append((system, user))
        props = kwargs.get("format", {}).get("properties", {})
        if "uso_lentes" in props:
            return json.dumps({"uso_lentes": "trabajar", "fuente": "ocupacion"}), {}
        if "apertura" in props:
            return json.dumps(fixture("g1-modelo-redaccion")), {}
        return json.dumps({"afirma_algo_de_salud": False}), {}

    monkeypatch.setattr(ollama, "call", mock_call)
    planificador = GPUScheduler()

    req = request(
        contexto_uso={
            "ocupacion": f"Ingeniero {SENTINEL}",
            "motivo_consulta": f"Molestia {SENTINEL}",
            "impresion_clinica": f"Astenopia {SENTINEL}",
            "explicacion_paciente": f"Detalle {SENTINEL}",
            "observaciones_receta": f"Nota {SENTINEL}",
            "recomendacion_seguimiento": f"Recom {SENTINEL}",
        }
    )

    resp = asyncio.run(generar(req, object(), planificador))
    assert len(llamadas) == 3

    # El centinela aparece solo en la llamada de la etapa uso
    sys_uso, usr_uso = llamadas[0]
    assert SENTINEL in usr_uso
    assert SENTINEL not in sys_uso

    # No aparece en las de redacción ni verificación
    for sys, usr in llamadas[1:]:
        assert SENTINEL not in sys
        assert SENTINEL not in usr

    # No aparece en el JSON de la respuesta final
    assert SENTINEL not in resp.model_dump_json()

    # Repetir con IA deshabilitada: no se hace ninguna llamada y el centinela no aparece
    llamadas.clear()
    seguimiento_cache.clear()
    monkeypatch.setattr("app.config.settings.seguimiento_llm_habilitado", False)

    resp_deshab = asyncio.run(generar(req, object(), planificador))
    assert len(llamadas) == 0
    assert SENTINEL not in resp_deshab.model_dump_json()


def test_logs_sin_contexto_uso(monkeypatch, caplog):
    seguimiento_cache.clear()
    req = request(
        contexto_uso={
            "ocupacion": f"Ingeniero {SENTINEL}",
            "motivo_consulta": f"Molestia {SENTINEL}",
            "impresion_clinica": f"Astenopia {SENTINEL}",
            "explicacion_paciente": f"Detalle {SENTINEL}",
        }
    )

    async def mock_call(system, user, client, **kwargs):
        props = kwargs.get("format", {}).get("properties", {})
        if "uso_lentes" in props:
            return json.dumps({"uso_lentes": "trabajar", "fuente": "ocupacion"}), {}
        if "apertura" in props:
            return json.dumps(fixture("g1-modelo-redaccion")), {}
        return json.dumps({"afirma_algo_de_salud": False}), {}

    monkeypatch.setattr(ollama, "call", mock_call)
    planificador = GPUScheduler()

    async def run():
        return await generar(req, object(), planificador)

    with caplog.at_level("DEBUG"):
        asyncio.run(run())

    assert SENTINEL not in caplog.text
