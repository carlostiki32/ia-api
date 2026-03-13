from app.schemas import ImpresionClinicaRequest

SYSTEM_PROMPT = """Eres un asistente de documentación clínica optométrica.
Tu ÚNICA función es redactar la impresión clínica basándote
EXCLUSIVAMENTE en los datos proporcionados.

REGLAS ABSOLUTAS:
- Máximo 5 oraciones.
- NO agregues información que no esté en los datos.
- NO uses bullets, listas, ni numeración.
- NO establezcas relaciones causales entre campos que no estén explícitas en los datos.
- NO hagas recomendaciones de tipo de lente ni de corrección óptica.
- NO incluyas recomendaciones de seguimiento a menos que recomendacion_seguimiento tenga valor; en ese caso, redáctala tal cual, sin expandirla.
- Redacta en tercera persona, tiempo presente, lenguaje clínico en español.
- Si un campo es nulo, no lo menciones.
- Termina con punto final. Nada más después del punto.
- av_sc es agudeza visual SIN corrección. av_cc es agudeza visual CON corrección. Ambas corresponden a visión lejana. NO las interpretes como distancia vs cerca."""

USO_PANTALLAS_MAP = {
    "lt2": "menos de 2 horas diarias",
    "btw2_6": "entre 2 y 6 horas diarias",
    "gt6": "más de 6 horas diarias",
}


def _format_ojo(label: str, ojo) -> str:
    """Format refraction data for one eye."""
    parts = []
    if ojo.esfera is not None:
        parts.append(f"Esf {ojo.esfera:+.2f}")
    if ojo.cilindro is not None:
        parts.append(f"Cil {ojo.cilindro:+.2f}")
    if ojo.eje is not None:
        parts.append(f"Eje {ojo.eje}°")
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
    lines = []
    for side, label in [("od", "OD"), ("oi", "OI")]:
        akr_ojo = getattr(req.akr, side)
        ref_ojo = getattr(req.refraccion, side)
        akr_str = _format_ojo(f"AKR {label}", akr_ojo)
        ref_str = _format_ojo(f"Rx final {label}", ref_ojo)
        if akr_str and ref_str:
            lines.append(akr_str)
            lines.append(ref_str)
    return "\n".join(lines)


def build_user_prompt(req: ImpresionClinicaRequest) -> str:
    """Build the dynamic user prompt from the request payload."""
    sections = []

    # Contexto del paciente (clínicamente relevante)
    paciente = req.paciente
    paciente_parts = []
    if paciente.edad is not None:
        paciente_parts.append(f"Edad: {paciente.edad} años")
    if paciente.ocupacion is not None:
        paciente_parts.append(f"Ocupación: {paciente.ocupacion}")
    if paciente.motivo_consulta is not None:
        paciente_parts.append(f"Motivo de consulta: {paciente.motivo_consulta}")
    if paciente_parts:
        sections.append("Contexto del paciente:\n  " + "\n  ".join(paciente_parts))

    # Refraction
    od_str = _format_ojo("OD", req.refraccion.od)
    oi_str = _format_ojo("OI", req.refraccion.oi)
    if od_str or oi_str:
        ref_lines = ["Refracción final:"]
        if od_str:
            ref_lines.append(f"  {od_str}")
        if oi_str:
            ref_lines.append(f"  {oi_str}")
        sections.append("\n".join(ref_lines))

    # AKR comparison
    akr_comp = _format_akr_comparison(req)
    if akr_comp:
        sections.append(
            f"Correlación AKR vs refracción final (la diferencia indica "
            f"el ajuste del examen subjetivo):\n{akr_comp}"
        )

    # Clinical data
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
            f"Confrontación de campos visuales: "
            f"{clinica.confrontacion_campos_visuales}"
        )
    if clinica.fondo_de_ojo is not None:
        sections.append(f"Fondo de ojo: {clinica.fondo_de_ojo}")
    if clinica.grid_de_amsler is not None:
        sections.append(f"Grid de Amsler: {clinica.grid_de_amsler}")
    if clinica.ojo_seco_but_seg is not None:
        sections.append(
            f"Ojo seco (BUT): {clinica.ojo_seco_but_seg} segundos"
        )
    if clinica.cover_test is not None:
        sections.append(f"Cover test: {clinica.cover_test}")
    if clinica.ppc_cm is not None:
        sections.append(f"PPC: {clinica.ppc_cm} cm")
    if clinica.recomendacion_seguimiento is not None:
        sections.append(
            f"Recomendación de seguimiento: {clinica.recomendacion_seguimiento}"
        )

    # Lens type
    if req.tipo_lente is not None:
        sections.append(f"Diseño de lente prescrito: {req.tipo_lente}")

    sections.append("Redacta ÚNICAMENTE la impresión clínica:")

    return "\n\n".join(sections)
