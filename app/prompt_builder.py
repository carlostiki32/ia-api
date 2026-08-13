import logging
import re

from app.config import settings
from app.schemas import ImpresionClinicaRequest
from app.correlaciones import evaluar_correlaciones

logger = logging.getLogger(__name__)

# Tokens de control de Qwen3.5 que nunca deben aparecer en user content.
# /think y /no_think no se soportan en Qwen3.5 (rule 2 del model card).
# Los delimitadores del chat template pueden romper el prompt si se inyectan
# accidentalmente en texto libre clinico (copiado desde un log del modelo, etc.).
_QWEN_CONTROL_RE = re.compile(
    r"(?:/(?:no_)?think"
    r"|<\|im_(?:start|end)\|>"
    r"|<\|(?:system|user|assistant)\|>"
    r"|</?think>"
    r"|</?tool_call>)",
    re.IGNORECASE,
)


def _sanitize(text: str) -> str:
    return _QWEN_CONTROL_RE.sub("", text)


def build_system_prompt(effective_max: int | None = None) -> str:
    """
    Construye el system prompt.

    Es inmutable por defecto (fijado en settings.max_sentences) para permitir
    que Ollama mantenga y reutilice el KV Prefix Cache de los ~1595 tokens
    a lo largo de todas las inferencias consecutivas.
    """
    limit = effective_max if effective_max is not None else settings.max_sentences

    return f"""\
Eres un optometrista clinico experto que redacta la impresion clinica de una receta.

Responde UNICAMENTE con el parrafo clinico final. Sin encabezados, sin explicaciones, sin texto adicional.

REGLA DE ORO — NUNCA DIAGNOSTICAR:
- Jamas emitas un diagnostico ni afirmes que el paciente tiene una enfermedad o entidad clinica (por ejemplo: degeneracion macular, glaucoma, queratocono, catarata, retinopatia, ambliopia, sindrome visual informatico, espasmo acomodativo). Describe solo lo observado y, cuando una correlacion lo indique, reproduce el descarte o la conducta que ELLA recomienda.
- No nombres ninguna patologia, hallazgo, estructura ni medida que NO aparezca de forma explicita en el user prompt (ni en los datos del caso ni en el bloque de correlaciones). Reporta cada hallazgo tal como viene escrito; nunca lo escales a un nombre de enfermedad (por ejemplo, si el dato dice "membrana epirretiniana" no lo llames "degeneracion macular").
- No propongas por tu cuenta ningun descarte, estudio, conducta ni nombre de enfermedad que no provenga textualmente de una correlacion del bloque 'Correlaciones clinicas aplicables'. Si no hay correlacion que lo respalde, NO escribas "amerita descarte de ...", "compatible con ...", "sugiere ...", etc.

SOLO LO QUE APARECE EN EL USER PROMPT:
- Describe unicamente los campos presentes en el user prompt. Si no hay refraccion, no hables de refraccion; si no hay fondo de ojo, no describas el fondo; si no viene la agudeza visual sin correccion, no la menciones. PROHIBIDO rellenar ausencias con normalidad supuesta: no escribas "el fondo de ojo es normal", "la superficie ocular es estable", "los hallazgos binoculares son normales" ni similares cuando esos campos NO fueron proporcionados.
- Nunca inventes valores (agudeza, esfera, cilindro, eje, adicion, BUT, PPC, queratometria) ni uses marcadores de relleno como [valor], 20/xx, 20/?? o equivalentes. Si falta un dato, omite la frase por completo.
- No interpretes por tu cuenta los valores numericos (BUT, PPC, queratometria, etc.): su unica interpretacion clinica valida es la que aporten las correlaciones. Si ninguna correlacion los interpreta, reportalos como dato objetivo neutro (o no los menciones), pero NO los califiques de normales ni patologicos NI sugieras descartar nada a partir de ellos (por ejemplo, un BUT de 12 segundos SIN correlacion de ojo seco no debe describirse como sequedad ni "amerita descarte de ojo seco": es solo un valor).

FORMATO:
- Maximo {limit} oraciones en un solo parrafo corrido. Prefiere la brevedad; no agregues oraciones de relleno.
- Sin bullets, listas, encabezados ni numeracion.
- Usa siempre "El paciente" en tercera persona; nunca asumas genero.
- Redacta en tiempo presente con lenguaje clinico optometrico en español correcto y con acentos. Termina con punto final.
- No incluyas recomendaciones de seguimiento, referencias a especialistas ni estudios complementarios a menos que aparezcan explicitamente como correlacion en el bloque 'Correlaciones clinicas aplicables'.
- Todo conocimiento externo al user prompt debe ignorarse.

ORDEN DE REDACCION (omite todo paso cuyo dato no exista en el user prompt):
1. Motivo de consulta y, solo si se proporciona, agudeza visual sin correccion de cada ojo.
2. Solo si hay refraccion final, presentala con la agudeza visual con correccion de cada ojo. Respeta el signo: esfera negativa = miopia, esfera positiva = hipermetropia; nunca la reformules al signo contrario.
3. Solo los hallazgos realmente presentes en los datos (segmento anterior/posterior, anexos, pupilas, motilidad, campos, Amsler, superficie ocular, binocularidad, cover test).
4. Al final, integra cada hecho del bloque 'Correlaciones clinicas aplicables' como observacion objetiva.

URGENCIA (uso restringido):
- Emplea "urgente", "inmediata", "prioritaria", "grave" o equivalentes UNICAMENTE cuando el texto de una correlacion ya contenga el prefijo "Hallazgo urgente:". En ese caso, coloca ese hallazgo en la segunda o tercera oracion del parrafo, sin diluirlo ni minimizarlo.
- Para cualquier otro hallazgo o correlacion esta PROHIBIDO calificarlo de urgente/inmediato/prioritario/grave.

INTEGRACION DE CORRELACIONES:
- Reescribe cada correlacion con tus propias palabras y ortografia correcta (con acentos); NUNCA pegues su texto literal ni copies el prefijo "Hallazgo urgente:" como parte de la frase.
- Integra cada correlacion dentro del flujo del parrafo, no como oracion aislada. Si el dato ya fue mencionado, añadela como calificador de esa oracion; no la reformules como instruccion.

SIN META-REFERENCIAS NI META-COMENTARIOS:
- NUNCA menciones la palabra "correlacion(es)" ni el bloque "correlaciones clinicas aplicables", ni escribas frases como "segun las correlaciones", "las correlaciones indican", "la correlacion clinica indica" o "se integra la observacion de que": redacta el hecho clinico directamente, como si fuera parte natural de la exploracion.
- NO comentes que falta un dato ni enumeres lo ausente: prohibido escribir "no se dispone de datos de ...", "no se documentan hallazgos en el segmento ...", "no fue proporcionado", "no existen correlaciones aplicables" y similares. Simplemente OMITE lo ausente y redacta solo con lo presente.

GLOSARIO (para interpretar los datos; no lo copies al parrafo):
- PPC = punto proximo de convergencia, medido en centimetros (no es un prisma ni una paralisis).
- BUT = tiempo de ruptura lagrimal, en segundos.
- c/d o E/P = relacion copa/disco (excavacion de la papila).
- AV s/c = agudeza visual sin correccion; AV c/c = agudeza visual con correccion.
"""


USO_PANTALLAS_MAP = {
    "lt2":    "menos de 2 horas diarias",
    "btw2_6": "entre 2 y 6 horas diarias",
    "gt6":    "mas de 6 horas diarias",
}

# Claves canonicas de tipo_lente del SaaS -> etiqueta clinica legible. Evita que
# el modelo copie la clave cruda ("bifocal_blended") al parrafo. Claves fuera
# del catalogo se pasan tal cual (texto libre legacy).
TIPO_LENTE_MAP = {
    "monofocal":       "monofocal",
    "bifocal_blended": "bifocal blended (sin linea visible)",
    "progresivo":      "progresivo",
    "flat_top":        "bifocal flat-top (segmento visible)",
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
    ("ojo_seco_but_seg",              lambda v: f"Tiempo de ruptura lagrimal (BUT): {v} segundos"),
    ("cover_test",                    lambda v: f"Cover test: {_sanitize(v)}"),
    ("ppc_cm",                        lambda v: f"Punto proximo de convergencia (PPC): {v} cm"),
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

_AKR_META_FIELDS = (
    ("pd",        lambda v: f"PD {v:.2f} mm"),
    ("vd",        lambda v: f"VD {v:.2f} mm"),
    ("ker_index", lambda v: f"Indice queratometrico {v:.4f}"),
)


def _format_ojo(label: str, ojo) -> str:
    tiene_cilindro = getattr(ojo, "cilindro", None) is not None
    parts = []
    for attr, formatter in _OJO_FIELDS:
        value = getattr(ojo, attr, None)
        if value is None:
            continue
        # Un eje sin cilindro no tiene sentido clinico (p. ej. cuando la coercion
        # descarto esfera/cilindro fuera de catalogo y solo sobrevivio el eje): se
        # omite para no emitir "Eje X grados" suelto al prompt.
        if attr == "eje" and not tiene_cilindro:
            continue
        parts.append(formatter(value))
    if not parts:
        return ""
    return f"{label}: {', '.join(parts)}"


def _format_k_pair(name: str, diopters: float | None, mm: float | None, axis: int | None) -> str:
    parts = []
    if diopters is not None:
        parts.append(f"{diopters:.2f}D")
    if mm is not None:
        parts.append(f"{mm:.2f}mm")
    value = "/".join(parts)
    if axis is not None:
        value = f"{value} @ {axis} grados" if value else f"@ {axis} grados"
    if not value:
        return ""
    return f"{name} {value}"


def _format_keratometry_eye(label: str, ojo) -> str:
    parts = [
        _format_k_pair("K1", ojo.k1_d, ojo.k1_mm, ojo.k1_eje),
        _format_k_pair("K2", ojo.k2_d, ojo.k2_mm, ojo.k2_eje),
        _format_k_pair("K promedio", ojo.k_promedio_d, ojo.k_promedio_mm, None),
    ]
    if ojo.k_cilindro is not None:
        cyl = f"Cil corneal {ojo.k_cilindro:+.2f}D"
        if ojo.k_cilindro_eje is not None:
            cyl += f" x {ojo.k_cilindro_eje} grados"
        parts.append(cyl)
    parts = [part for part in parts if part]
    if not parts:
        return ""
    return f"Queratometria {label}: {', '.join(parts)}"


def _format_akr_metadata(req: ImpresionClinicaRequest) -> str:
    parts = [
        formatter(getattr(req.akr, attr))
        for attr, formatter in _AKR_META_FIELDS
        if getattr(req.akr, attr, None) is not None
    ]
    if not parts:
        return ""
    return "AKR metadata: " + ", ".join(parts)


def _format_akr_comparison(req: ImpresionClinicaRequest) -> str:
    akr = req.akr
    all_null = all(
        value is None
        for value in [
            akr.ticket_id,
            akr.pd,
            akr.vd,
            akr.ker_index,
            *[
                getattr(ojo, attr)
                for ojo in [akr.od, akr.oi]
                for attr in (
                    "esfera",
                    "cilindro",
                    "eje",
                    "k1_d",
                    "k1_mm",
                    "k1_eje",
                    "k2_d",
                    "k2_mm",
                    "k2_eje",
                    "k_promedio_d",
                    "k_promedio_mm",
                    "k_cilindro",
                    "k_cilindro_eje",
                )
            ],
        ]
    )
    if all_null:
        return ""

    lines = []
    metadata = _format_akr_metadata(req)
    if metadata:
        lines.append(metadata)

    for side, label in [("od", "OD"), ("oi", "OI")]:
        akr_eye = getattr(req.akr, side)
        ref_eye = getattr(req.refraccion, side)
        akr_text = _format_ojo(f"AKR {label}", akr_eye)
        ref_text = _format_ojo(f"Rx final {label}", ref_eye)
        ker_text = _format_keratometry_eye(label, akr_eye)
        if akr_text:
            lines.append(akr_text)
        if ref_text:
            lines.append(ref_text)
        if ker_text:
            lines.append(ker_text)

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
            "Correlacion AKR/queratometria vs refraccion final "
            "(la diferencia indica el ajuste del examen subjetivo; la queratometria "
            "describe curvatura y astigmatismo corneal):\n"
            f"{akr_comparison}"
        )

    clinica = req.clinica

    for attr, formatter in _CLINICA_FIELDS:
        value = getattr(clinica, attr)
        if value is not None:
            sections.append(formatter(value))

    if req.tipo_lente is not None:
        tipo_lente = TIPO_LENTE_MAP.get(req.tipo_lente.lower(), req.tipo_lente)
        sections.append(f"Diseno de lente prescrito: {tipo_lente}")

    correlaciones_activas = evaluar_correlaciones(req)
    if correlaciones_activas:
        items = "\n".join(f"- {_sanitize(c)}" for c in correlaciones_activas)
        sections.append(
            f"Correlaciones clinicas aplicables (hechos pre-evaluados del caso):\n{items}"
        )

    return "\n\n".join(sections) + "\n\nGenera el parrafo."


# Guardarraíl anti-placeholder: cuando falta un dato, el modelo a veces deja un
# marcador de relleno sin sustituir ("[valor]", "20/??", "20/xx") o una agudeza
# generica ("20/x"). Esas oraciones son defectuosas: se descartan en clean_impresion.
# El prompt ya lo prohibe; esto es red de seguridad barata y determinista.
_PLACEHOLDER_RE = re.compile(
    r"\[[^\]]*\]"           # cualquier cosa entre corchetes: [valor], [dato]
    r"|20\s*/\s*\?+"        # 20/?? , 20 / ?
    r"|20\s*/\s*[xX]{1,3}\b"  # 20/xx , 20/XX
    r"|\?\?",               # signos de interrogacion de relleno
)


# Guardarraíl anti-meta-referencia: qwen3.5:9b a veces filtra el nombre del bloque
# interno ("segun las correlaciones clinicas aplicables", "las correlaciones ...
# indican que") o mete meta-comentarios sobre datos ausentes. El prompt ya lo
# prohibe, pero el modelo pequeño no lo respeta de forma fiable, asi que se limpia
# de forma determinista. Estas frases son de ATRIBUCION, no clinicas: se pueden
# quitar sin perder el hallazgo. Importante: NO tocan "correlacion con cifras
# tensionales" ni "correlacion sistemica" (esos SI son texto clinico), porque el
# patron exige la forma "correlacion(es) clinica(s) [aplicable(s)]" o el conector.
_META_PHRASE_RE = re.compile(
    r"(?:,?\s*(?:seg[uú]n|de acuerdo con|conforme a|tal como indican|como indican)\s+(?:el\s+bloque\s+de\s+|las\s+|los\s+)?correlaciones?\s+cl[ií]nicas?(?:\s+aplicables?)?)"
    r"|(?:(?:las\s+)?correlaciones\s+cl[ií]nicas\s+aplicables\s+indican\s+que\s+)"
    r"|(?:la\s+correlaci[oó]n\s+cl[ií]nica(?:\s+aplicable)?\s+indica\s+que\s+)"
    r"|(?:se\s+integra\s+la\s+observaci[oó]n\s+de\s+que\s+)"
    r"|(?:seg[uú]n\s+(?:la\s+)?correlaci[oó]n\s+cl[ií]nica(?:\s+aplicable)?,?\s*)",
    re.IGNORECASE,
)

# Oración que es puro meta-comentario sobre ausencia de DATOS/registro → se elimina
# entera (no aporta contenido clínico). Se busca por `search` (no solo al inicio)
# para atrapar formas con prefijo ("En el resto de la exploración no se disponen…").
# Los patrones apuntan solo a "faltan datos/registro", NO a negativos clínicos
# legítimos del payload ("fondo sin lesiones", "no presenta pterigión", "no muestra
# defectos periféricos"), que se conservan.
_ABSENCE_SENTENCE_RE = re.compile(
    r"no se dispone[n]? de (?:dato|informaci|otro)"
    r"|no se (?:documentan?|reportan?|registran?|observan?|identifican?|incluyen?) (?:dato|otros hallazgo|hallazgos adicional|informaci|otro dato)"
    r"|no se (?:documentan?|reportan?|registran?|observan?) hallazgos?(?:\s+adicionales?)?\s+en\s+(?:el\s+|los\s+)?(?:segmento|resto)"
    r"|en el resto de la exploraci[oó]n[^.]*\bno se (?:dispon|document|observ|report|registr)"
    r"|la refracci[oó]n final no (?:fue|se ha|ha sido|se pudo) (?:document|determin|proporcion|especific|registr|obten)"
    r"|no (?:existen|hay|se identifican) correlaciones"
    r"|no fue posible (?:documentar|obtener|determinar)"
    r"|no se cuenta con (?:dato|informaci)",
    re.IGNORECASE,
)


# Reacentuación de terminología clínica. Los textos fuente de las correlaciones
# se almacenan SIN acentos (para el matching por normalización) y el modelo los
# copia tal cual; además el propio modelo a veces omite acentos. Este mapa restaura
# la ortografía correcta SOLO en términos clínicos inequívocos (sin homógrafo común
# en prosa clínica). Se excluyen a propósito palabras ambiguas (esta/está,
# practica/práctica, critico/crítico, numero/número, publico/público, continua/
# continúa, solo/sólo, mas/más, termino/término). Operа sobre el texto FINAL, así
# que no afecta el matching de keywords (que trabaja sobre la ENTRADA normalizada).
# Regla GENERICA segura: toda palabra terminada en "-cion"/"-sion" es un sustantivo
# que en singular SIEMPRE lleva acento (-ción/-sión); el plural termina en "-es" y no
# matchea. Cubre refraccion, adicion, evaluacion, correlacion, medicion, desviacion,
# degeneracion, vision, hipertension, etc. sin necesidad de listarlas.
_CION_RE = re.compile(r"\b([a-zñáéíóúü]+?)(cion|sion)\b", re.IGNORECASE)
_CION_ACC = {"cion": "ción", "sion": "sión"}

# Lista blanca para lo que la regla generica NO cubre y que tiene homografo (por eso
# NO se generaliza -ico/-ica ni -ia): terminos clinicos griegos (-ía) y adjetivos
# medicos (-ico/-ica) que en este dominio siempre van acentuados, mas nombres propios.
_ACENTOS = {
    "anos": "años",                                # critico: "anos" sin ñ es otra palabra
    # -ía (singular y plural conservan acento)
    "miopia": "miopía", "miopias": "miopías",
    "hipermetropia": "hipermetropía", "hipermetropias": "hipermetropías",
    "anisometropia": "anisometropía", "antimetropia": "antimetropía",
    "patologia": "patología", "patologias": "patologías",
    "topografia": "topografía", "tomografia": "tomografía",
    "queratometria": "queratometría", "sintomatologia": "sintomatología",
    "asimetria": "asimetría", "cicloplejia": "cicloplejía", "epiteliopatia": "epiteliopatía",
    # -ico / -ica (y plurales; todas acentuadas en este dominio)
    "astigmatico": "astigmático", "astigmatica": "astigmática", "astigmaticos": "astigmáticos", "astigmaticas": "astigmáticas",
    "sistemico": "sistémico", "sistemica": "sistémica", "sistemicos": "sistémicos", "sistemicas": "sistémicas",
    "biomicroscopico": "biomicroscópico", "biomicroscopica": "biomicroscópica",
    "oftalmologico": "oftalmológico", "oftalmologica": "oftalmológica", "oftalmologicos": "oftalmológicos", "oftalmologicas": "oftalmológicas",
    "neurooftalmologico": "neurooftalmológico", "neurooftalmologica": "neurooftalmológica",
    "retinologico": "retinológico", "retinologica": "retinológica", "retinologicos": "retinológicos", "retinologicas": "retinológicas",
    "fisiologico": "fisiológico", "fisiologica": "fisiológica", "fisiologicos": "fisiológicos", "fisiologicas": "fisiológicas",
    "glucemico": "glucémico", "glucemica": "glucémica",
    "esferico": "esférico", "esferica": "esférica",
    "queratometrico": "queratométrico", "queratometrica": "queratométrica",
    "miopico": "miópico", "miopica": "miópica", "miopicos": "miópicos", "miopicas": "miópicas",
    "hipermetropico": "hipermetrópico", "hipermetropica": "hipermetrópica",
    "hipermetropicos": "hipermetrópicos", "hipermetropicas": "hipermetrópicas",
    "profilactico": "profiláctico", "profilactica": "profiláctica",
    "profilacticos": "profilácticos", "profilacticas": "profilácticas",
    "diabetico": "diabético", "diabetica": "diabética", "diabeticos": "diabéticos", "diabeticas": "diabéticas",
    "periferico": "periférico", "periferica": "periférica", "perifericos": "periféricos", "perifericas": "periféricas",
    "clinico": "clínico", "clinica": "clínica", "clinicos": "clínicos", "clinicas": "clínicas",
    "organico": "orgánico", "organica": "orgánica",
    "asimetrico": "asimétrico", "asimetrica": "asimétrica",
    "cronico": "crónico", "cronica": "crónica",
    "diagnostico": "diagnóstico",
    # nombres propios del dominio (sin homografo relevante)
    "optico": "óptico", "optica": "óptica", "opticos": "ópticos", "opticas": "ópticas",
    "macula": "mácula", "camara": "cámara", "angulo": "ángulo", "indice": "índice",
    "pelicula": "película", "pterigion": "pterigión", "autorrefractometro": "autorrefractómetro",
    "region": "región",
}
_ACENTOS_RE = re.compile(
    r"\b(" + "|".join(sorted(map(re.escape, _ACENTOS), key=len, reverse=True)) + r")\b",
    re.IGNORECASE,
)


def _preserva_caso(original: str, acentuada: str) -> str:
    if original[:1].isupper():
        return acentuada[:1].upper() + acentuada[1:]
    return acentuada


def _reacentuar(text: str) -> str:
    # El español NUNCA usa acento grave: cualquier à/è/ì/ò/ù es un artefacto del
    # modelo (p. ej. "retinològica") -> se convierte al acento agudo correcto.
    text = text.translate(str.maketrans("àèìòùÀÈÌÒÙ", "áéíóúÁÉÍÓÚ"))
    text = _CION_RE.sub(
        lambda m: _preserva_caso(m.group(0), m.group(1) + _CION_ACC[m.group(2).lower()]),
        text,
    )
    return _ACENTOS_RE.sub(
        lambda m: _preserva_caso(m.group(0), _ACENTOS[m.group(0).lower()]),
        text,
    )


def _clean_sentence(s: str) -> str | None:
    """Aplica los guardarraíles a una oración. Devuelve la oración depurada o
    None si debe descartarse. Cada descarte/limpieza se loggea para poder
    auditar por qué el párrafo final difiere del output crudo del modelo."""
    meta_al_inicio = bool(_META_PHRASE_RE.match(s))
    tenia_meta = bool(_META_PHRASE_RE.search(s))
    stripped = _META_PHRASE_RE.sub(" ", s)
    stripped = re.sub(r"\s+", " ", stripped)
    stripped = re.sub(r"\s+([,.;:])", r"\1", stripped).strip(" ,;:").strip()
    if tenia_meta:
        logger.info("Guardarrail: meta-referencia a correlaciones eliminada de la oración")
    if not stripped:
        return None
    if _ABSENCE_SENTENCE_RE.search(stripped):
        logger.info("Guardarrail: descartada oración de meta-ausencia: %.80s", stripped)
        return None
    if _PLACEHOLDER_RE.search(stripped):
        logger.warning("Guardarrail: descartada oración con placeholder: %.80s", stripped)
        return None
    # Si el meta-prefijo iba al inicio, el resto quedó en minúscula: recapitalizar.
    if meta_al_inicio:
        stripped = stripped[0].upper() + stripped[1:]
    # Solo se conservan oraciones que empiezan con mayúscula: descarta fragmentos
    # colgados en minúscula (comportamiento original).
    if not re.match(r'^[A-ZÁÉÍÓÚÜÑ¿¡"]', stripped):
        logger.info("Guardarrail: descartado fragmento sin mayúscula inicial: %.80s", stripped)
        return None
    return stripped


def clean_impresion(text: str) -> str:
    """
    Depura el párrafo: elimina fragmentos colgados, oraciones con placeholders sin
    rellenar, meta-referencias al bloque de correlaciones y meta-comentarios sobre
    datos ausentes.
    """
    text = text.strip()

    # Partir por oraciones terminadas en punto
    sentences = re.split(r'(?<=[.!?])\s+', text)

    valid = []
    for s in sentences:
        s = s.strip()
        if not s:
            continue
        cleaned = _clean_sentence(s)
        if cleaned:
            valid.append(cleaned)

    result = " ".join(valid)
    # Regla de oro (nunca diagnosticar): el modelo a veces adjetiva un hallazgo como
    # "diagnosticado/a" (p. ej. "ametropia miopica diagnosticada"). Se elimina el
    # participio; el sustantivo "diagnostico"/"diagnóstico" de la correlacion
    # (insuficiencia de convergencia: "confirmar el diagnostico") NO matchea y se
    # conserva. Ninguna correlacion usa la forma "diagnosticad*".
    result, n_diag = re.subn(r"\s*\bdiagnosticad[oa]s?\b", "", result, flags=re.IGNORECASE)
    if n_diag:
        logger.info("Guardarrail: eliminado participio 'diagnosticad*' (%d ocurrencias)", n_diag)
    result = re.sub(r"\s+([.,;:])", r"\1", result).strip()
    result = _reacentuar(result)
    if result and not result.endswith("."):
        result += "."
    return result
