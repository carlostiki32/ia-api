from pathlib import Path
import re

from app.seguimiento.catalogo import HECHOS, APERTURAS, INVITACIONES, BAJA
from tests.seguimiento_helpers import FIXTURES


def test_catalogo_literal():
    md = (Path(__file__).parents[1] / "CATALOGO_WHATSAPP_Y_TRATO_AL_PACIENTE.md").read_text(encoding="utf-8")
    filas = re.findall(r"^\| `([a-z_]+)` \| ([^|]+) \|", md, re.M)
    assert len(HECHOS) == len(filas) == 20
    assert [(h.id, h.texto) for h in HECHOS] == [(id, texto.strip()) for id, texto in filas]
    assert [h.grupo for h in HECHOS] == ["A"] * 12 + ["B"] * 8
    for prefijo, catalogo in (("A", APERTURAS), ("I", INVITACIONES)):
        muestras = re.findall(r"^- \*\*(" + prefijo + r"\d+)\.\*\* (.+)$", md, re.M)
        assert len(muestras) == len(catalogo) == 10
        assert catalogo == {id: texto.split(" *(")[0] for id, texto in muestras}
    assert f"«{BAJA}»" in md


def test_fixtures_compartidos_sin_cambios():
    # Fijar contenido con hashes del origen, sin dependencia de la carpeta temporal.
    import hashlib
    hashes = __import__("json").loads((FIXTURES / "sha256.json").read_text(encoding="utf-8"))
    for nombre, esperado in hashes.items():
        assert hashlib.sha256((FIXTURES / nombre).read_bytes()).hexdigest() == esperado
