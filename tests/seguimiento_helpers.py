import json
from pathlib import Path

from app.seguimiento.schemas import SeguimientoWhatsappRequest

FIXTURES = Path(__file__).parent / "fixtures" / "seguimiento_whatsapp"


def fixture(nombre):
    return json.loads((FIXTURES / (nombre + ".json")).read_text(encoding="utf-8"))


def request(n=1, **cambios):
    base = fixture(f"g{n}-request")
    ctx = dict(base.get("contexto_uso") or {})
    if "ocupacion" in cambios:
        ctx["ocupacion"] = cambios.pop("ocupacion")
    if "observaciones_receta" in cambios:
        ctx["observaciones_receta"] = cambios.pop("observaciones_receta")
    if "recomendacion_seguimiento" in cambios:
        ctx["recomendacion_seguimiento"] = cambios.pop("recomendacion_seguimiento")
    if "motivo_consulta" in cambios:
        ctx["motivo_consulta"] = cambios.pop("motivo_consulta")
    if "impresion_clinica" in cambios:
        ctx["impresion_clinica"] = cambios.pop("impresion_clinica")
    if "explicacion_paciente" in cambios:
        ctx["explicacion_paciente"] = cambios.pop("explicacion_paciente")
    if "contexto_uso" in cambios:
        ctx = cambios.pop("contexto_uso")
    cambios["contexto_uso"] = ctx
    if "fecha_meses" in cambios:
        fm = cambios.pop("fecha_meses")
        if fm is not None:
            cambios.setdefault("fecha_revision", "2026-12-15")
            cambios.setdefault("meses_periodo", fm)
        else:
            cambios.setdefault("fecha_revision", None)
            cambios.setdefault("meses_periodo", None)
    estado = cambios.get("estado_seguimiento", base.get("estado_seguimiento"))
    if estado == "vencido":
        cambios["fecha_revision"] = None
        cambios["meses_periodo"] = None
    return SeguimientoWhatsappRequest.model_validate({**base, **cambios})


def sin_variables(respuesta, *, plantilla=False):
    obj = json.loads(json.dumps(respuesta))
    obj["generacion"].pop("base_hash_api")
    obj["generacion"].pop("cached")
    if plantilla:
        obj.pop("motivo")
    return obj
