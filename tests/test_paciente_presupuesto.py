"""Presupuesto estricto y fronteras exactas, con el tokenizador oficial offline."""
import asyncio
from pathlib import Path
import pytest

from app.paciente.contexto import construir_contexto
from app.paciente.servicio import MAX_TOKENS_ENTRADA, generar
from app.paciente.prompts import opciones
from app.tareas import presupuesto
from tests.test_paciente import contexto

TOKENIZADOR = Path(r"C:\Users\carlo\AppData\Local\Temp\claude\ff364ab545173299\55dde339-7bed-4855-989c-de526444904c\scratchpad\descargas-qwen\tokenizer.json")


@pytest.fixture
def tokenizador_oficial(monkeypatch):
    if not TOKENIZADOR.exists(): pytest.skip("Tokenizador oficial Qwen no disponible en este equipo")
    from tokenizers import Tokenizer
    tok = Tokenizer.from_file(str(TOKENIZADOR))
    monkeypatch.setattr(presupuesto.contador, "disponible", lambda: True)
    monkeypatch.setattr(presupuesto.contador, "tokenizador", tok)
    async def sin_actualizacion(client): pass
    monkeypatch.setattr(presupuesto.contador, "actualizar", sin_actualizacion)
    return tok


@pytest.mark.parametrize("etapa", ["redaccion", "verificacion"])
def test_fronteras_7782_7783(tokenizador_oficial, etapa):
    tok = tokenizador_oficial
    predict = opciones(etapa)["num_predict"]
    base = len(tok.encode(presupuesto.renderizar("", "")).ids)
    user = " x" * (7782 - predict - base)
    assert len(tok.encode(presupuesto.renderizar("", user)).ids) + predict == 7782
    assert presupuesto.verificar("", user, predict, politica="estricto") + predict == 7782
    with pytest.raises(presupuesto.PresupuestoExcedido):
        presupuesto.verificar("", user + " x", predict, politica="estricto")
    assert MAX_TOKENS_ENTRADA[etapa] + predict <= 7782


@pytest.mark.parametrize("etapa", ["redaccion", "verificacion"])
def test_techo_de_entrada_por_etapa(tokenizador_oficial, etapa):
    base = len(tokenizador_oficial.encode(presupuesto.renderizar("", "")).ids)
    user = " x" * (MAX_TOKENS_ENTRADA[etapa] - base)
    assert presupuesto.verificar("", user, opciones(etapa)["num_predict"], MAX_TOKENS_ENTRADA[etapa], politica="estricto") == MAX_TOKENS_ENTRADA[etapa]
    with pytest.raises(presupuesto.PresupuestoExcedido):
        presupuesto.verificar("", user + " x", opciones(etapa)["num_predict"], MAX_TOKENS_ENTRADA[etapa], politica="estricto")


def test_sin_contador_siempre_estricto(monkeypatch):
    monkeypatch.setattr(presupuesto.contador, "disponible", lambda: False)
    llamadas = []
    async def proveedor(llamada):
        llamadas.append(llamada)
        raise AssertionError("No debe llamar a un proveedor sin presupuesto")
    # Contexto que no cabe en la cota demostrable por bytes: respaldo CPU.
    r = asyncio.run(generar(construir_contexto(impresion_clinica_final="Hallazgo. " * 1000), proveedor, llegada=0, reloj=lambda: 0))
    assert r.motivo == "presupuesto" and not llamadas



def test_cadena_con_conteo_oficial_y_proveedor_simulado(tokenizador_oficial):
    from tests.test_paciente import candidato
    etapas = []
    async def proveedor(l):
        etapas.append(l.etapa)
        return candidato() if l.etapa == "redaccion" else {"valido": True}
    resultado = asyncio.run(generar(contexto(), proveedor, llegada=0, reloj=lambda: 0))
    assert resultado.estado == "generada" and etapas == ["redaccion", "verificacion"]
