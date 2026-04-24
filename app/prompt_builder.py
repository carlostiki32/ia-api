import re

from app.config import settings
from app.schemas import ImpresionClinicaRequest
from app.correlaciones import evaluar_correlaciones

_THINK_DIRECTIVE_RE = re.compile(r"/(?:no_)?think", re.IGNORECASE)


def _sanitize(text: str) -> str:
    return _THINK_DIRECTIVE_RE.sub("", text)


def build_system_prompt(effective_max: int | None = None) -> str:
    """
    Construye el system prompt.

    effective_max: límite real de oraciones para esta inferencia.
    Cuando hay recomendación de seguimiento, se pasa max_sentences - 1
    para que el modelo deje espacio sin necesidad de truncamiento.
    """
    limit = effective_max if effective_max is not None else settings.max_sentences

    return f"""\
Eres un optometrista clinico experto redactando impresiones clinicas.

Responde UNICAMENTE con el parrafo clinico final. Sin encabezados, sin explicaciones, sin texto adicional.

FORMATO:
- Maximo {limit} oraciones en un solo parrafo corrido.
- Sin bullets, listas, encabezados ni numeracion.
- Usa siempre "El paciente" en tercera persona; nunca asumas genero.
- Redacta en tiempo presente con lenguaje clinico optometrico en español.
- Termina con punto final.
- Si un campo es nulo, no lo menciones.
- av_sc es agudeza visual sin correccion y av_cc es agudeza visual con correccion; ambas corresponden a vision lejana.

ORDEN DE REDACCION:
Primero describe el motivo de consulta y la agudeza visual sin correccion de cada ojo. Luego presenta la refraccion final con la agudeza visual con correccion de cada ojo. Despues describe los hallazgos del segmento anterior y posterior. A continuacion los hallazgos binoculares y de superficie ocular. Finalmente, si el user prompt incluye un bloque 'Correlaciones clinicas aplicables', incorpora cada hecho al final del parrafo como observacion objetiva sin reformularlos como instrucciones.

PRIORIZACION:
- Dedica mas oraciones a hallazgos anormales que a describir normalidad.
- Si existen hallazgos patologicos en fondo de ojo, segmento anterior u opacidades, prioriza su descripcion sobre hallazgos refractivos o binoculares normales.
- Los hallazgos normales pueden resumirse brevemente (ejemplo: "el segmento anterior y la salud ocular intrinseca se encuentran preservados").
- Si una correlacion incluye el prefijo "Hallazgo urgente:", esa informacion debe aparecer en las primeras 2 oraciones del parrafo, inmediatamente despues del motivo de consulta y la agudeza visual sin correccion. No diluyas la urgencia en oraciones posteriores ni uses lenguaje que minimice el hallazgo.

REGLAS DE ESCRITURA:
- Describe hallazgos usando UNICAMENTE terminos objetivos y medibles: valores numericos, observaciones anatomicas, comportamiento binocular.
- Describe hallazgos normales como normales, sin referencia a patologias ni descartes.
- Menciona UNICAMENTE hallazgos presentes en el examen. Datos ausentes se omiten sin explicacion.
- Cada hallazgo aparece UNA SOLA VEZ en el parrafo; elige la seccion donde tenga mayor relevancia clinica.
- Usa EXCLUSIVAMENTE el tipo de lente proporcionado; describe el prescrito, no sugieras alternativas.
- La recomendacion de seguimiento se agrega automaticamente; no la incluyas en el parrafo.
- Las correlaciones que no aplican al caso se omiten sin explicar por que.
- No inferas relaciones causales entre hallazgos mas alla de las correlaciones incluidas en el user prompt.
"""


USO_PANTALLAS_MAP = {
    "lt2":    "menos de 2 horas diarias",
    "btw2_6": "entre 2 y 6 horas diarias",
    "gt6":    "mas de 6 horas diarias",
}

# (atributo, formateador) — orden preservado del prompt original.
_CLINICA_FIELDS = [
    ("uso_pantallas",                 lambda v: f"Uso de pantallas: {USO_PANTALLAS_MAP[v]}"),
    ("anexos_oculares",               lambda v: f"Anexos oculares: {_sanitize(v)}"),
    ("reflejos_pupilares",            lambda v: f"Reflejos pupilares: {_sanitize(v)}"),
    ("motilidad_ocular",              lambda v: f"Motilidad ocular: {_sanitize(v)}"),
    ("confrontacion_campos_visuales", lambda v: f"Confrontacion de campos visuales: {_sanitize(v)}"),
    ("fondo_de_ojo",                  lambda v: f"Fondo de ojo: {_sanitize(v)}"),
    ("grid_de_amsler",                lambda v: f"Grid de Amsler: {_sanitize(v)}"),
    ("ojo_seco_but_seg",              lambda v: f"Ojo seco (BUT): {v} segundos"),
    ("cover_test",                    lambda v: f"Cover test: {_sanitize(v)}"),
    ("ppc_cm",                        lambda v: f"PPC: {v} cm"),
]


# (atributo, formateador). Los campos solo presentes en GraduacionOjo (add, av_*)
# se saltan en AkrOjo via hasattr.
_OJO_FIELDS = (
    ("esfera",   lambda v: f"Esf {v:+.2f}"),
    ("cilindro", lambda v: f"Cil {v:+.2f}"),
    ("eje",      lambda v: f"Eje {v} grados"),
    ("add",      lambda v: f"Add {v:+.2f}"),
    ("av_sc",    lambda v: f"AV s/c {v}"),
    ("av_cc",    lambda v: f"AV c/c {v}"),
)


def _format_ojo(label: str, ojo) -> str:
    parts = [
        formatter(getattr(ojo, attr))
        for attr, formatter in _OJO_FIELDS
        if getattr(ojo, attr, None) is not None
    ]
    if not parts:
        return ""
    return f"{label}: {', '.join(parts)}"


def _format_akr_comparison(req: ImpresionClinicaRequest) -> str:
    akr = req.akr
    all_null = all(
        value is None
        for ojo in [akr.od, akr.oi]
        for value in [ojo.esfera, ojo.cilindro, ojo.eje]
    )
    if all_null:
        return ""

    lines = []
    for side, label in [("od", "OD"), ("oi", "OI")]:
        akr_eye = getattr(req.akr, side)
        ref_eye = getattr(req.refraccion, side)
        akr_text = _format_ojo(f"AKR {label}", akr_eye)
        ref_text = _format_ojo(f"Rx final {label}", ref_eye)
        if akr_text and ref_text:
            lines.append(akr_text)
            lines.append(ref_text)

    return "\n".join(lines)


def build_user_prompt(req: ImpresionClinicaRequest) -> str:
    sections = []

    paciente = req.paciente
    paciente_parts = []
    if paciente.edad is not None:
        paciente_parts.append(f"Edad: {paciente.edad} anos")
    if paciente.ocupacion is not None:
        paciente_parts.append(f"Ocupacion: {_sanitize(paciente.ocupacion)}")
    if paciente.motivo_consulta is not None:
        paciente_parts.append(f"Motivo de consulta: {_sanitize(paciente.motivo_consulta)}")
    if paciente_parts:
        sections.append("Contexto del paciente:\n  " + "\n  ".join(paciente_parts))

    od_text = _format_ojo("OD", req.refraccion.od)
    oi_text = _format_ojo("OI", req.refraccion.oi)
    if od_text or oi_text:
        ref_lines = ["Refraccion final:"]
        if od_text:
            ref_lines.append(f"  {od_text}")
        if oi_text:
            ref_lines.append(f"  {oi_text}")
        sections.append("\n".join(ref_lines))

    akr_comparison = _format_akr_comparison(req)
    if akr_comparison:
        sections.append(
            "Correlacion AKR vs refraccion final "
            "(la diferencia indica el ajuste del examen subjetivo):\n"
            f"{akr_comparison}"
        )

    clinica = req.clinica

    for attr, formatter in _CLINICA_FIELDS:
        value = getattr(clinica, attr)
        if value is not None:
            sections.append(formatter(value))

    if req.tipo_lente is not None:
        sections.append(f"Diseno de lente prescrito: {req.tipo_lente}")

    correlaciones_activas = evaluar_correlaciones(req)
    if correlaciones_activas:
        items = "\n".join(f"- {_sanitize(c)}" for c in correlaciones_activas)
        sections.append(
            f"Correlaciones clinicas aplicables (hechos pre-evaluados del caso):\n{items}"
        )

    return "\n\n".join(sections) + "\n\nGenera el parrafo."