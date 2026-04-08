from app.config import settings
from app.schemas import ImpresionClinicaRequest


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
Primero describe el motivo de consulta y la agudeza visual sin correccion de cada ojo. Luego presenta la refraccion final con la agudeza visual con correccion de cada ojo. Despues describe los hallazgos del segmento anterior y posterior. A continuacion los hallazgos binoculares y de superficie ocular. Finalmente incluye las correlaciones clinicas fundamentadas que apliquen.

CORRELACIONES (aplica SOLO cuando AMBOS datos esten presentes y con valores que justifiquen la relacion):
- Edad >= 40 con add presente: justifica el tipo de lente prescrito por la necesidad acomodativa asociada a la edad.
- AV c/c que no alcanza 20/20 en algun ojo: describe el hallazgo como limitacion visual no compensada por la refraccion prescrita. Nunca uses el termino ambliopia.
- Diferencia de esfera entre OD y OI mayor a 1.00D: menciona la magnitud exacta de la diferencia y su posible impacto en la fusion binocular.
- Discrepancia significativa entre refraccion final y AKR (mayor a 1.00D en esfera o cilindro): describe la discrepancia y su relacion con posible irregularidad corneal.
- Cilindro mayor a 2.00D con eje oblicuo (entre 20-70 o 110-160 grados): describe el astigmatismo elevado con eje oblicuo.
- BUT < 10 segundos con uso de pantallas gt6: describe el tiempo de ruptura lagrimal reducido en el contexto del uso de pantallas.
- PPC mayor a 10 cm o exoforia en vision cercana: describe el punto proximo alejado o la tendencia divergente.
- Cover test alterado junto con sintomas binoculares en el motivo de consulta: correlaciona el hallazgo motor con la sintomatologia referida.
- Microaneurismas, exudados, hemorragias o neovasos en fondo de ojo: describe los hallazgos vasculares y estructurales observados.
- Endotropia que se corrige con lentes: describe que la alineacion ocular se logra mediante la correccion optica.
- Tipo de lente bifocal, progresivo o multifocal: correlaciona con edad y add.
Cuando un dato de la correlacion no esta presente, omite la correlacion sin mencionarla.

PRIORIZACION:
- Dedica mas oraciones a hallazgos anormales que a describir normalidad.
- Si existen hallazgos patologicos en fondo de ojo, segmento anterior u opacidades, prioriza su descripcion sobre hallazgos refractivos o binoculares normales.
- Los hallazgos normales pueden resumirse brevemente (ejemplo: "el segmento anterior y la salud ocular intrinseca se encuentran preservados").

REGLAS DE ESCRITURA:
- Describe hallazgos usando UNICAMENTE terminos objetivos y medibles: valores numericos, observaciones anatomicas, comportamiento binocular.
- Describe hallazgos normales como normales, sin referencia a patologias ni descartes.
- Menciona UNICAMENTE hallazgos presentes en el examen. Datos ausentes se omiten sin explicacion.
- Cada hallazgo aparece UNA SOLA VEZ en el parrafo; elige la seccion donde tenga mayor relevancia clinica.
- Usa EXCLUSIVAMENTE el tipo de lente proporcionado; describe el prescrito, no sugieras alternativas.
- La recomendacion de seguimiento se agrega automaticamente; no la incluyas en el parrafo.
- Las correlaciones que no aplican al caso se omiten sin explicar por que.
"""


# Prompt base a nivel de modulo — usado para el hash de cache.
# run_inference() construye el prompt efectivo con effective_max por request.
SYSTEM_PROMPT = build_system_prompt()

USO_PANTALLAS_MAP = {
    "lt2":    "menos de 2 horas diarias",
    "btw2_6": "entre 2 y 6 horas diarias",
    "gt6":    "mas de 6 horas diarias",
}


def _format_ojo(label: str, ojo) -> str:
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
        sections.append(f"Uso de pantallas: {USO_PANTALLAS_MAP[clinica.uso_pantallas]}")
    if clinica.anexos_oculares is not None:
        sections.append(f"Anexos oculares: {clinica.anexos_oculares}")
    if clinica.reflejos_pupilares is not None:
        sections.append(f"Reflejos pupilares: {clinica.reflejos_pupilares}")
    if clinica.motilidad_ocular is not None:
        sections.append(f"Motilidad ocular: {clinica.motilidad_ocular}")
    if clinica.confrontacion_campos_visuales is not None:
        sections.append(f"Confrontacion de campos visuales: {clinica.confrontacion_campos_visuales}")
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

    if req.tipo_lente is not None:
        sections.append(f"Diseno de lente prescrito: {req.tipo_lente}")

    return "\n\n".join(sections) + "\n\nGenera el parrafo."