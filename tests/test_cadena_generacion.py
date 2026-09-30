"""Cadena final API -> generacion -> H01 -> respuesta, con proveedor simulado (auditoria de produccion 2026-09-29).

No ensaya Qwen real: comprueba que el motor determinista y las salvaguardas no dejan pasar como exito
un texto cortado, vacio, contradictorio con una urgencia o con cifras/terapias que el payload no contiene.
"""
import asyncio
import logging

import pytest
from fastapi.testclient import TestClient

import app.inference as inference
import app.main as main
from app.cache import inference_cache
from app.correlaciones.texto import _normalize_text as _norm
from tests.test_auditoria_correlaciones import _req

DIPLOPIA_HOY = {"motivo": "Diplopia desde hoy."}
ROTULO = "Bearer secret-token"


def _fake_call(respuestas):
    """Proveedor simulado: devuelve (texto, meta) en orden y registra los num_predict pedidos."""
    llamadas = []

    async def call(system_prompt, user_prompt, client, *, num_predict=None):
        llamadas.append(num_predict)
        return respuestas[min(len(llamadas) - 1, len(respuestas) - 1)]

    call.llamadas = llamadas
    return call


def _correr(payload, respuestas, monkeypatch):
    fake = _fake_call(respuestas)
    monkeypatch.setattr(inference.ollama_provider, "call", fake)
    return asyncio.run(inference.run_inference(payload, object())), fake


# ------------------------------------------------------- seguimiento vs urgencia activa (P1)
@pytest.mark.parametrize("seguimiento", [
    "No requiere acudir a urgencias.",
    "No es necesario acudir a urgencias.",
    "Sin necesidad de urgencias.",
    "No necesita valoracion urgente.",
])
def test_seguimiento_no_anula_una_urgencia_activa(seguimiento, monkeypatch):
    req = _req(seguimiento=seguimiento, **DIPLOPIA_HOY)
    texto, _ = _correr(req, [("Se registra diplopia reciente.", {"done_reason": "stop"})], monkeypatch)
    assert "urgente" in texto and "el mismo dia" in texto
    for negacion in ("No requiere acudir", "No es necesario acudir", "Sin necesidad de urgencias",
                     "No necesita valoracion urgente"):
        assert negacion not in texto


def test_seguimiento_compatible_se_conserva_al_final(monkeypatch):
    req = _req(seguimiento="Control con optometria en tres dias.", **DIPLOPIA_HOY)
    texto, _ = _correr(req, [("Se registra diplopia reciente.", {})], monkeypatch)
    assert texto.endswith("Control con optometria en tres dias.")
    assert "el mismo dia" in texto


def test_seguimiento_sin_urgencia_no_se_toca(monkeypatch):
    req = _req(seguimiento="No requiere acudir a urgencias.", rx_od={"esfera": -1.25})
    texto, _ = _correr(req, [("Miopia leve registrada.", {})], monkeypatch)
    assert texto.endswith("No requiere acudir a urgencias.")


# ------------------------------------------------------------ texto cortado por longitud (P1)
def test_truncamiento_se_reintenta_con_mas_tokens_y_se_acepta_si_termina(monkeypatch):
    req = _req(rx_od={"esfera": -1.25})
    texto, fake = _correr(req, [("Miopia leve en OD y ademas", {"done_reason": "length"}),
                                ("Miopia leve en OD.", {"done_reason": "stop"})], monkeypatch)
    assert _norm(texto) == "miopia leve en od."
    assert fake.llamadas[0] is None and fake.llamadas[1] > inference.settings.ollama_num_predict


def test_truncamiento_persistente_se_rechaza(monkeypatch):
    req = _req(rx_od={"esfera": -1.25})
    with pytest.raises(inference.GeneracionIncompletaError):
        _correr(req, [("Miopia leve en OD y ademas", {"done_reason": "length"})], monkeypatch)


# ------------------------------------------------------------ impresion vacia (P2) y cache
@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setattr(main.settings, "api_key", "secret-token")
    inference_cache.clear()
    with TestClient(main.app) as c:
        yield c
    inference_cache.clear()


def _post(cliente, cuerpo):
    return cliente.post("/inferencia/impresion-clinica", headers={"Authorization": ROTULO}, json=cuerpo)


def test_impresion_vacia_no_es_exito_ni_se_cachea(cliente, monkeypatch):
    fake = _fake_call([("No se dispone de datos clinicos.", {"done_reason": "stop"})])
    monkeypatch.setattr(inference.ollama_provider, "call", fake)
    cuerpo = {"receta_id": "vacia", "refraccion": {"od": {"esfera": -1.0}}}
    primera = _post(cliente, cuerpo)
    segunda = _post(cliente, cuerpo)
    assert primera.status_code == segunda.status_code == 502
    assert len(fake.llamadas) == 2          # la segunda peticion no salio de cache


def test_truncamiento_persistente_sin_urgencia_es_502(cliente, monkeypatch):
    monkeypatch.setattr(inference.ollama_provider, "call",
                        _fake_call([("Miopia leve en OD y ademas", {"done_reason": "length"})]))
    assert _post(cliente, {"receta_id": "corta", "refraccion": {"od": {"esfera": -1.0}}}).status_code == 502


def test_truncamiento_con_urgencia_entrega_respaldo_determinista_identificado(cliente, monkeypatch):
    fake = _fake_call([("Se registra diplopia y ademas", {"done_reason": "length"})])
    monkeypatch.setattr(inference.ollama_provider, "call", fake)
    cuerpo = {"receta_id": "urgente", "refraccion": {"od": {"esfera": 0}},
              "paciente": {"motivo_consulta": "Diplopia desde hoy."},
              "clinica": {"recomendacion_seguimiento": "No requiere acudir a urgencias."}}
    r = _post(cliente, cuerpo)
    assert r.status_code == 200
    body = r.json()
    assert body["origen"] == "determinista"
    assert "el mismo dia" in body["impresion_clinica"] and "No requiere acudir" not in body["impresion_clinica"]
    assert "diplopia_aguda" in body["correlaciones_activadas"]
    # El respaldo no se guarda: la siguiente peticion vuelve a intentar con el modelo.
    _post(cliente, cuerpo)
    assert len(fake.llamadas) == 4


# ------------------------------------------------------------------ fidelidad minima (limite)
def test_cifra_de_riesgo_inventada_se_omite(monkeypatch):
    req = _req(rx_od={"esfera": -1.0})
    texto, _ = _correr(req, [("Miopia leve en OD. Presion intraocular de 40 mmHg con glaucoma avanzado y "
                              "cirugia inmediata. Se sugiere control optometrico.", {})], monkeypatch)
    assert "40 mmHg" not in texto and "cirugia" not in texto.lower()
    assert _norm(texto).startswith("miopia leve en od.")


def test_cifra_presente_en_el_payload_se_conserva(monkeypatch):
    req = _req(anexos="Espesor corneal central de 480 um.", rx_od={"esfera": -1.0})
    texto, _ = _correr(req, [("Se registra un espesor corneal de 480 um.", {})], monkeypatch)
    assert "480 um" in texto


def test_terapia_mencionada_en_el_payload_no_se_omite(monkeypatch):
    req = _req(motivo="Cirugia de catarata hace 3 semanas.", rx_od={"esfera": -1.0})
    texto, _ = _correr(req, [("Antecedente de cirugia de catarata reciente.", {})], monkeypatch)
    assert "cirugia de catarata" in texto.lower()


# ----------------------------------------------------------------------------- API (P2)
def test_bearer_no_ascii_es_401_no_500(cliente):
    r = cliente.post("/inferencia/impresion-clinica", headers={"Authorization": "Bearer señal-ñandú".encode("utf-8")},
                     json={"receta_id": "x", "refraccion": {"od": {"esfera": -1.0}}})
    assert r.status_code == 401


def test_health_degradado_sin_api_key(monkeypatch):
    monkeypatch.setattr(main.settings, "api_key", "")

    class Resp:
        def __init__(self, d): self._d = d
        def raise_for_status(self): pass
        def json(self): return self._d

    class Cliente:
        async def get(self, url, timeout=None):
            return Resp({"models": [{"name": main.settings.ollama_model}]})

    main.app.dependency_overrides[main.get_http_client] = lambda: Cliente()
    try:
        with TestClient(main.app) as c:
            r = c.get("/health")
    finally:
        main.app.dependency_overrides.pop(main.get_http_client, None)
    assert r.status_code == 503 and r.json()["status"] == "degraded"
    assert r.json()["api_key_configurada"] is False


def test_logs_de_advertencia_no_contienen_texto_clinico(monkeypatch, caplog):
    sensible = "Control estricto de la paciente Maria Lopez en tres dias."
    req = _req(seguimiento="No requiere acudir a urgencias. " + sensible, **DIPLOPIA_HOY)
    with caplog.at_level(logging.INFO):
        _correr(req, [("Sin diplopia. La exploracion es normal y no requiere valoracion urgente.", {})], monkeypatch)
    registrado = " ".join(r.getMessage() for r in caplog.records if r.levelno >= logging.INFO)
    assert "Maria Lopez" not in registrado and "No requiere acudir" not in registrado
    assert "no requiere valoracion urgente" not in registrado.lower()


def test_diagnostico_inventado_se_omite_y_el_mencionado_en_el_payload_se_conserva(monkeypatch):
    inventado = _req(rx_od={"esfera": -1.0})
    texto, _ = _correr(inventado, [("El paciente tiene glaucoma avanzado en ambos ojos. Miopia leve en OD.", {})], monkeypatch)
    assert "glaucoma" not in texto.lower() and _norm(texto).startswith("miopia leve en od")
    presente = _req(fondo="Sospecha de glaucoma por excavacion 0.7 en OD.", rx_od={"esfera": -1.0})
    texto, _ = _correr(presente, [("Se registra sospecha de glaucoma en OD.", {})], monkeypatch)
    assert "glaucoma" in texto.lower()


def test_respuesta_del_proveedor_defectuosa_g03_no_sobrevive_intacta(monkeypatch):
    req = _req(rx_od={"esfera": -1.0})
    fake = _fake_call([("El paciente tiene glaucoma avanzado en ambos ojos. La presion intraocular es de 40 mmHg y "
                        "requiere cirugia inmediata.", {})])
    monkeypatch.setattr(inference.ollama_provider, "call", fake)
    with pytest.raises(inference.GeneracionIncompletaError):
        asyncio.run(inference.run_inference(req, object()))
