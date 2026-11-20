"""Oráculo independiente: no reescribir ni reclasificar sus archivos."""
import json
from pathlib import Path
import pytest

from app.paciente.contexto import construir_contexto
from app.paciente.validador import validar

CORPUS = Path(__file__).parent / "fixtures" / "paciente" / "corpus"


def casos_corpus():
    casos = []
    for archivo in sorted(CORPUS.glob("*.json")):
        for caso in json.loads(archivo.read_text(encoding="utf-8")):
            casos.append(pytest.param(caso, id=archivo.stem + "/" + caso["id"]))
    return casos or [pytest.param(None, marks=pytest.mark.skip(reason="El corpus independiente del paciente aún no contiene archivos JSON"))]


@pytest.mark.parametrize("caso", casos_corpus())
def test_corpus_independiente(caso):
    contexto = construir_contexto(**caso["caso"])
    regla = validar(caso["candidato"], contexto)
    assert regla == caso["regla"], caso["nota"]
    assert (regla is None) == (caso["esperado"] == "aceptar")
