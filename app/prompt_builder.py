from app.config import settings
from app.schemas import ImpresionClinicaRequest


def build_system_prompt() -> str:
    """Build the system prompt from runtime configuration."""
    return f"""Eres un asistente de documentacion clinica optometrica.
Tu UNICA funcion es redactar la impresion clinica basandote
EXCLUSIVAMENTE en los datos proporcionados.

REGLAS ABSOLUTAS:
- Maximo {settings.max_sentences} oraciones.
- NO agregues informacion que no este en los datos.
- NO uses bullets, listas ni numeracion.
- NO establezcas relaciones causales entre campos que no esten explicitas en los datos.
- NO hagas recomendaciones de tipo de lente ni de correccion optica.
- Usa siempre "El paciente" en tercera persona; nunca asumas genero.
- Si recomendacion_seguimiento tiene valor, DEBES incluirlo como ultima oracion.
- Si un campo es nulo, no lo menciones.
- Redacta en tiempo presente y con lenguaje clinico en espanol.
- Termina con punto final. Nada mas despues del punto.
- av_sc es agudeza visual sin correccion. av_cc es agudeza visual con correccion. Ambas corresponden a vision lejana. NO las interpretes como distancia vs cerca."""


USO_PANTALLAS_MAP = {
    "lt2": "menos de 2 horas diarias",
    "btw2_6": "entre 2 y 6 horas diarias",
    "gt6": "mas de 6 horas diarias",
}


def _format_ojo(label: str, ojo) -> str:
    """Format refraction data for one eye."""
    parts = []
    if ojo.esfera is not None:
        parts.append(f"Esf {ojo.esfera:+.2f}")
    if ojo.cilindro is not None:
        parts.append(f"Cil {ojo.cilindro:+.2f}")
    if ojo.eje is not None:
        parts.append(f"Eje {ojo.eje} grados")
    if hasattr(ojo, "add") and ojo.add is not None:
        parts.append(f"Add {ojo.add:+.2f}")
    if hasattr(ojo, "av_sc") and ojo.av_sc is not None:
        parts.append(f"AV s/c {ojo.av_sc}")
    if hasattr(ojo, "av_cc") and ojo.av_cc is not None:
        parts.append(f"AV c/c {ojo.av_cc}")
    if not parts:
        return ""
    return f"{label}: {', '.join(parts)}"


def _format_akr_comparison(req: ImpresionClinicaRequest) -> str:
    """Build AKR vs refraction comparison text."""
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
    """Build the dynamic user prompt from the request payload."""
    sections = []

    paciente = req.paciente
    paciente_parts = []
    if paciente.edad is not None:
        paciente_parts.append(f"Edad: {paciente.edad} anos")
    if paciente.ocupacion is not None:
        paciente_parts.append(f"Ocupacion: {paciente.ocupacion}")
    if paciente.motivo_consulta is not None:
        paciente_parts.append(f"Motivo de consulta: {paciente.motivo_consulta}")
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
    if clinica.uso_pantallas is not None:
        sections.append(
            f"Uso de pantallas: {USO_PANTALLAS_MAP[clinica.uso_pantallas]}"
        )
    if clinica.anexos_oculares is not None:
        sections.append(f"Anexos oculares: {clinica.anexos_oculares}")
    if clinica.reflejos_pupilares is not None:
        sections.append(f"Reflejos pupilares: {clinica.reflejos_pupilares}")
    if clinica.motilidad_ocular is not None:
        sections.append(f"Motilidad ocular: {clinica.motilidad_ocular}")
    if clinica.confrontacion_campos_visuales is not None:
        sections.append(
            "Confrontacion de campos visuales: "
            f"{clinica.confrontacion_campos_visuales}"
        )
    if clinica.fondo_de_ojo is not None:
        sections.append(f"Fondo de ojo: {clinica.fondo_de_ojo}")
    if clinica.grid_de_amsler is not None:
        sections.append(f"Grid de Amsler: {clinica.grid_de_amsler}")
    if clinica.ojo_seco_but_seg is not None:
        sections.append(f"Ojo seco (BUT): {clinica.ojo_seco_but_seg} segundos")
    if clinica.cover_test is not None:
        sections.append(f"Cover test: {clinica.cover_test}")
    if clinica.ppc_cm is not None:
        sections.append(f"PPC: {clinica.ppc_cm} cm")
    if clinica.recomendacion_seguimiento is not None:
        sections.append(
            f"Recomendacion de seguimiento: {clinica.recomendacion_seguimiento}"
        )

    if req.tipo_lente is not None:
        sections.append(f"Diseno de lente prescrito: {req.tipo_lente}")

    sections.append(
        "Redacta la impresion clinica en exactamente este orden:\n"
        "1. Motivo de consulta y agudeza visual sin correccion (av_sc) de cada ojo.\n"
        "2. Refraccion final de cada ojo con agudeza visual con correccion (av_cc).\n"
        "3. Hallazgos del segmento anterior y posterior.\n"
        "4. Hallazgos binoculares y de superficie ocular.\n"
        "5. Recomendacion de seguimiento si existe.\n"
        "Redacta cada punto como una oracion continua, sin numeracion ni bullets."
    )

    return "\n\n".join(sections)
