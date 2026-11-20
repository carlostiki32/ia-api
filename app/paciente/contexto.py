"""Contexto mínimo, determinista y compartido con el adaptador del corpus."""
from dataclasses import asdict, dataclass
import json

from app.patient_profile import PatientProfile, build_patient_profile
from app.paciente.sintomas import extraer_sintomas

VERSION = "contexto-v1"
LENTES = {
    "monofocal": "Lente con una sola graduación óptica; no determina por sí solo una distancia de uso.",
    "bifocal_blended": "Lente bifocal con zona para cerca y unión disimulada, sin línea divisoria visible.",
    "flat_top": "Lente bifocal con un segmento visible para cerca, de borde superior recto.",
    "progresivo": "Lente con cambio gradual de graduación entre las zonas de lejos, intermedia y cerca, sin línea divisoria.",
}
PANTALLAS = {"lt2": "Menos de dos horas diarias", "btw2_6": "Entre dos y seis horas diarias", "gt6": "Más de seis horas diarias"}


def json_canonico(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


@dataclass(frozen=True)
class ContextoPaciente:
    hechos: tuple[dict, ...]
    perfil: PatientProfile | None = None
    acciones_sin_mapear: int = 0

    @property
    def ids(self):
        return tuple(h["id"] for h in self.hechos)

    def contenido(self, id, defecto=None):
        return next((h["contenido"] for h in self.hechos if h["id"] == id), defecto)

    def como_dict(self):
        return {"hechos": list(self.hechos), "acciones_obligatorias": self.contenido("acciones", [])}

    def canonico(self):
        return json_canonico(self.como_dict())


def construir_contexto(*, impresion_clinica_final, rx=None, motivo=None, sintomas_referidos=None,
                       pantallas=None, lente=None, correlaciones=(), acciones_obligatorias=(),
                       perfil=None, acciones_sin_mapear=0):
    hechos = [{"id": "clinico", "fuente": "impresion_clinica_final", "contenido": impresion_clinica_final}]
    if rx is not None and all(lado in rx for lado in ("od", "oi")):
        for lado, ojo in (("od", "derecho"), ("oi", "izquierdo")):
            hechos.append({"id": "rx." + lado, "fuente": "refraccion." + lado,
                           "contenido": {**rx[lado], "ojo": ojo}})
    if motivo:
        sintomas = extraer_sintomas(motivo)
        hechos.append({"id": "motivo", "fuente": "paciente.motivo_consulta", "contenido": {
            "texto": motivo, "sintomas_referidos": list(sintomas_referidos) if sintomas_referidos is not None
            else list(dict.fromkeys(s.sintoma for s in sintomas)),
            "ocurrencias": [asdict(s) for s in sintomas]}})
    if pantallas in PANTALLAS:
        hechos.append({"id": "pantallas", "fuente": "clinica.uso_pantallas", "contenido": {"id": pantallas, "descripcion": PANTALLAS[pantallas]}})
    if lente in LENTES:
        hechos.append({"id": "lente", "fuente": "tipo_lente", "contenido": {"id": lente, "descripcion": LENTES[lente]}})
    for cor in correlaciones:
        hechos.append({"id": "cor." + cor["nombre"], "fuente": "correlaciones." + cor["nombre"], "contenido": cor["texto"]})
    if acciones_obligatorias:
        hechos.append({"id": "acciones", "fuente": "acciones_obligatorias", "contenido": list(acciones_obligatorias)})
    return ContextoPaciente(tuple(hechos), perfil, acciones_sin_mapear)


def contexto_desde_receta(req, impresion_clinica_final, correlaciones):
    from app.paciente.acciones import extraer_acciones
    correlaciones = tuple(correlaciones)
    perfil = build_patient_profile(req)
    rx = {lado: {"componentes": list(o.nombres), "apoyo_cerca": o.apoyo_cerca, "plano": o.plano}
          for lado, o in zip(("od", "oi"), perfil.ojos)} if len(perfil.ojos) == 2 else None
    acciones = extraer_acciones(correlaciones)
    return construir_contexto(impresion_clinica_final=impresion_clinica_final, rx=rx,
        motivo=req.paciente.motivo_consulta if req.paciente else None,
        pantallas=req.clinica.uso_pantallas if req.clinica else None, lente=req.tipo_lente,
        correlaciones=correlaciones, acciones_obligatorias=[a.texto for a in acciones], perfil=perfil,
        acciones_sin_mapear=sum(not a.mapeada for a in acciones))
