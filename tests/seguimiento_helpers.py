import json
from pathlib import Path

from app.seguimiento.schemas import SeguimientoWhatsappRequest

FIXTURES = Path(__file__).parent / "fixtures" / "seguimiento_whatsapp"


def fixture(nombre):
    return json.loads((FIXTURES / (nombre + ".json")).read_text(encoding="utf-8"))


def request(n=1, **cambios):
    return SeguimientoWhatsappRequest.model_validate({**fixture(f"g{n}-request"), **cambios})


def sin_variables(respuesta, *, plantilla=False):
    obj = json.loads(json.dumps(respuesta))
    obj["generacion"].pop("base_hash_api")
    obj["generacion"].pop("cached")
    if plantilla:
        obj.pop("motivo")
    return obj
