"""Prueba del exportador offline sobre una salida temporal."""
from pathlib import Path
import subprocess
import sys

from app.paciente.acciones import CATALOGO
from app.paciente.prompts import GLOSARIO, SYSTEM_REDACCION, SYSTEM_VERIFICACION


def test_catalogo_paciente_cli(tmp_path):
    script = Path(__file__).resolve().parents[1] / "scripts/catalogo_paciente.py"
    salida = tmp_path / "revisión.md"
    resultado = subprocess.run(
        [sys.executable, str(script), "--salida", str(salida)],
        cwd=tmp_path, capture_output=True, check=True,
    )
    assert b"Acciones:" in resultado.stdout
    datos = salida.read_bytes()
    texto = datos.decode("utf-8")
    assert b"\r\r\n" not in datos
    assert b"\n" not in datos.replace(b"\r\n", b"")
    assert b"\r" not in datos.replace(b"\r\n", b"")
    texto = texto.replace("\r\n", "\n")
    for variante in CATALOGO:
        assert variante.accion.texto in texto
        assert f"#### Variante `{variante.accion.variante}`" in texto
        assert f"- Prioridad: `{variante.accion.prioridad}`." in texto
    assert SYSTEM_REDACCION in texto
    assert SYSTEM_VERIFICACION in texto
    assert all(f"{k}: {v}." in texto for k, v in GLOSARIO.items())
    assert "PROMPT_VERSION" in texto
    assert "sin conteo" in texto
