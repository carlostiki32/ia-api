from pathlib import Path
import re

from app.seguimiento.catalogo import (
    HECHOS, APERTURAS_POR_ID, CIERRES_POR_ID, FRASES_USO_POR_ID, FRASES_FECHA_POR_ID, BAJA,
)
from tests.seguimiento_helpers import FIXTURES


def test_catalogo_literal():
    md = (Path(__file__).parents[1] / "CATALOGO_WHATSAPP_Y_TRATO_AL_PACIENTE.md").read_text(encoding="utf-8")

    # 1. Hechos conservados (6)
    filas_hechos = re.findall(r"^\| `(progresivo_zonas|bifocal_zonas|hipermetropia_cerca|astigmatismo_comodidad|progresivo_ajuste|ajuste_armazon)` \| ([^|]+) \|", md, re.M)
    assert len(HECHOS) == len(filas_hechos) == 6
    assert [(h.id, h.texto) for h in HECHOS] == [(id, texto.strip()) for id, texto in filas_hechos]

    # 2. Frases de uso (16)
    filas_uso = re.findall(r"^\| `(FU_[a-z_]+_\d+)` \| ([^|]+) \|", md, re.M)
    assert len(FRASES_USO_POR_ID) == len(filas_uso) == 16
    for id, texto in filas_uso:
        assert FRASES_USO_POR_ID[id] == texto.strip()

    # 3. Frases de fecha (11)
    filas_fecha = re.findall(r"^\| `(FF_[A-Z]+_\d+)` \| ([^|]+) \|", md, re.M)
    assert len(FRASES_FECHA_POR_ID) == len(filas_fecha) == 11
    for id, texto in filas_fecha:
        assert FRASES_FECHA_POR_ID[id] == texto.strip()

    # 4. Aperturas (18)
    filas_ap = re.findall(r"^\| `(AP_[A-Z_]+_\d+)` \| ([^|]+) \|", md, re.M)
    assert len(APERTURAS_POR_ID) == len(filas_ap) == 18
    for id, texto in filas_ap:
        assert APERTURAS_POR_ID[id] == texto.strip()

    # 5. Cierres (12)
    filas_ci = re.findall(r"^\| `(CI_[A-Z]+_\d+)` \| ([^|]+) \|", md, re.M)
    assert len(CIERRES_POR_ID) == len(filas_ci) == 12
    for id, texto in filas_ci:
        assert CIERRES_POR_ID[id] == texto.strip()

    # 6. Línea de baja
    assert f"«{BAJA}»" in md


def test_fixtures_compartidos_sin_cambios():
    import hashlib
    hashes = __import__("json").loads((FIXTURES / "sha256.json").read_text(encoding="utf-8"))
    for nombre, esperado in hashes.items():
        assert hashlib.sha256((FIXTURES / nombre).read_bytes()).hexdigest() == esperado
