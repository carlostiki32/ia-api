"""Acciones versionadas por correlación y variante; nunca modifica el clínico."""
from dataclasses import dataclass
import logging
import re

from app.paciente.sintomas import normalizar

VERSION = "acciones-v1"
logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Accion:
    correlacion: str
    variante: str
    origen: str
    destino: str
    procedimiento: str = "consulta"
    prioridad: str = "ordinaria"
    plazo: str = ""
    condicion: str = ""
    alternativas: str = ""
    relacion: str = "independiente"
    detalle: str = ""
    mapeada: bool = True

    @property
    def texto(self):
        if self.procedimiento == "gestionar la derivación":
            base = "Le recomendamos que su cita con " + self.destino + " quede programada"
        elif self.procedimiento == "contacto para triaje":
            base = "Le recomendamos contactar con " + self.destino + " para que determine la prioridad de la atención"
        elif self.procedimiento == "consulta":
            base = "Le recomendamos acudir a " + self.destino
        else:
            base = "Le recomendamos " + self.procedimiento
            if self.destino:
                base += " con " + self.destino
        if self.plazo:
            base += " " + self.plazo
        elif self.prioridad == "urgente":
            base += " de forma urgente"
        elif self.prioridad in ("preferente", "programada"):
            base += " de forma " + self.prioridad
        if self.detalle:
            base += " " + self.detalle
        if self.condicion:
            base = "Si " + self.condicion + ", " + base[0].lower() + base[1:]
        if self.alternativas:
            base += "; " + self.alternativas
        return base.rstrip(".") + "."


@dataclass(frozen=True)
class Variante:
    accion: Accion
    patron: str
    grupo: str = "principal"


CATALOGO = []


def _v(cor, id, origen, destino="una valoración especializada", *, patron=None, grupo="principal", **campos):
    CATALOGO.append(Variante(Accion(cor, id, origen, destino, **campos), patron or re.escape(normalizar(origen)), grupo))


# Cada grupo elige la primera variante compatible; los grupos distintos conservan
# procedimientos independientes. Los plazos se toman de la indicación, no del hallazgo.
OFT = "un oftalmólogo"
RET = "un especialista en retina"
MED = "una valoración médica"
ESP = "una valoración especializada"
HOY = "hoy mismo"
URG = "un servicio de urgencias"
EVC = "un servicio de urgencias con atención de evento vascular cerebral"

_v("fondo_periferico_riesgo", "DR", "valoracion retinologica urgente el mismo dia", RET, prioridad="urgente", plazo=HOY)
_v("fondo_periferico_riesgo", "ROTURA", "valoracion retinologica urgente con exploracion de la retina periferica bajo midriasis e indentacion escleral", RET, prioridad="urgente", procedimiento="una revisión de la retina con las pupilas dilatadas")
_v("fondo_periferico_riesgo", "VITREO", "valoracion retinologica urgente para descartar rotura retiniana", RET, prioridad="urgente", detalle="para descartar una rotura de la retina")
_v("fondo_periferico_riesgo", "PREDISPONENTE_SINTOMAS", "valoracion retinologica urgente con exploracion de la retina periferica bajo midriasis", RET, prioridad="urgente", procedimiento="una revisión de la retina con las pupilas dilatadas")
_v("fondo_periferico_riesgo", "PREDISPONENTE", "exploracion programada de la periferia bajo midriasis", "", procedimiento="una revisión programada de la retina con las pupilas dilatadas", alternativas="si nota destellos, nuevas manchas flotantes o una sombra en la visión, acuda a revisión sin esperar la cita programada")
_v("fondo_periferico_riesgo", "ANTECEDENTE", "mantener el seguimiento retinologico programado", RET, procedimiento="mantener el seguimiento programado", detalle="y recibir orientación sobre los síntomas de alarma")

_v("papila_patologica", "A", "valoracion oftalmologica o neurooftalmologica dentro de las 24 horas", "un oftalmólogo o un neurooftalmólogo", prioridad="urgente", plazo="en las próximas 24 horas", condicion="", detalle="para verificar lo que se encontró y estudiar su causa")
_v("papila_patologica", "PALIDEZ_EXCAVACION", "valoracion oftalmologica preferente con tonometria", OFT, prioridad="preferente", detalle="con medición de la presión del ojo, estudio del campo visual e imagen del nervio óptico")
_v("papila_patologica", "PALIDEZ", "valoracion oftalmologica preferente con campimetria", OFT, prioridad="preferente", detalle="con estudio del campo visual e imagen del nervio óptico; el especialista decidirá si necesita imágenes del sistema nervioso")
_v("papila_patologica", "B", "valoracion oftalmologica preferente con imagen del nervio optico", OFT, prioridad="preferente", detalle="con imagen del nervio óptico y estudio del campo visual", alternativas="adelante la revisión si nota oscurecimientos de la visión, zumbido al ritmo del pulso o visión doble")
_v("papila_patologica", "ANTECEDENTE", "verificar su seguimiento oftalmologico o neurologico", "un oftalmólogo o neurología", procedimiento="verificar el seguimiento", alternativas="adelante la revisión si nota menor visión o dolor al mover los ojos")
_v("glaucoma_asimetrico", "estudio", "valoracion oftalmologica preferente", OFT, prioridad="preferente", detalle="con medición de la presión del ojo, estudio del campo visual e imagen del nervio óptico")
_v("fondo_glaucomatoso", "ISNT", "con valoracion oftalmologica si alguno resulta alterado", OFT, condicion="alguno de los estudios resulta alterado", detalle="tras completar la medición de la presión del ojo, el campo visual y la imagen del nervio óptico")
_v("fondo_glaucomatoso", "estudio", "valoracion oftalmologica para estudio de glaucoma", OFT, detalle="con medición de la presión del ojo, revisión del ángulo interno del ojo, grosor de la córnea, campo visual e imagen del nervio óptico")

_v("fondo_macular_dmae", "A", "para OCT macular y valoracion de tratamiento", RET, procedimiento="gestionar la derivación", prioridad="urgente", plazo="en un plazo máximo de un día hábil", detalle="para una imagen por capas de la zona central de la retina y valorar el tratamiento")
_v("fondo_macular_dmae", "A2", "de 1 dia habil para OCT macular", RET, procedimiento="gestionar la derivación", prioridad="urgente", plazo="en un plazo máximo de un día hábil", detalle="para una imagen por capas de la zona central de la retina")
_v("fondo_macular_dmae", "TRATADA", "mantener el seguimiento retinologico establecido", RET, procedimiento="mantener el seguimiento establecido", alternativas="acuda a revisión ante cambios visuales sin esperar la cita programada")
_v("fondo_macular_dmae", "C", "valoracion retinologica programada con OCT e imagen multimodal", RET, prioridad="programada", detalle="con imágenes por capas y otros tipos de imagen para revisar con detalle lo que se encontró")
_v("fondo_macular_dmae", "B", "valoracion oftalmologica programada con retinografia u OCT macular", OFT, prioridad="programada", detalle="con fotografía o imagen por capas de la retina para definir los pasos a seguir; solicite orientación para vigilar la visión con la rejilla de Amsler", alternativas="acuda sin esperar la cita si nota distorsión o una mancha central nueva")
for id, prioridad in (("P", "preferente"), ("R", "programada")):
    _v("fondo_macular_otros", id, "valoracion retinologica " + prioridad, RET, prioridad=prioridad, detalle="con una imagen por capas de la zona central de la retina", alternativas="acuda a revisión si aparece distorsión o menor visión central" if id == "R" else "")

_v("fondo_hipertensivo", "URGENTE", "valoracion medica especializada el mismo dia", MED, prioridad="urgente", plazo=HOY)
_v("fondo_hipertensivo", "R", "valoracion oftalmologica y revision medica de la presion arterial", OFT, detalle="y a una revisión médica de la presión arterial")
_v("fondo_vascular_diabetico", "RUBEOSIS", "valoracion oftalmologica urgente el mismo dia", OFT, prioridad="urgente", plazo=HOY)
_v("fondo_vascular_diabetico", "NEOVASCULAR", "contacto con oftalmologia para triage", OFT, procedimiento="contacto para triaje", prioridad="urgente")
_v("fondo_vascular_diabetico", "HEMORRAGIA", "valoracion oftalmologica el mismo dia", OFT, prioridad="urgente", plazo=HOY)
_v("fondo_vascular_diabetico", "MICROVASCULAR_P", "valoracion retinologica preferente", RET, prioridad="preferente")
_v("fondo_vascular_diabetico", "MICROVASCULAR", "valoracion retinologica y evaluacion medica sistemica", RET)
_v("fondo_vascular_diabetico", "sistemica", "evaluacion medica sistemica", MED, grupo="sistemica", detalle="incluidos el azúcar en sangre y la presión arterial")
_v("fondo_vascular_diabetico", "tratante", "valoracion con su medico tratante respecto al control glucemico", "su médico tratante", grupo="tratante", detalle="para revisar el control del azúcar en sangre")

_v("fondo_oclusion_vascular_urgente", "ARTERIAL", "derivacion inmediata el mismo dia a un servicio de urgencias", EVC, prioridad="urgente", plazo="de inmediato", detalle="para evaluación de los vasos del sistema nervioso y de los ojos")
_v("fondo_oclusion_vascular_urgente", "SIN_TIPIFICAR", "sin tipificar, hallazgo que amerita valoracion oftalmologica el mismo dia", OFT, prioridad="urgente", plazo=HOY, alternativas="si la pérdida visual es repentina y comenzó hace horas, acuda de inmediato a urgencias con atención de evento vascular cerebral")
_v("fondo_oclusion_vascular_urgente", "VENOSA", "valoracion oftalmologica prioritaria en los proximos dias", OFT, prioridad="prioritaria", plazo="en los próximos días", detalle="sin esperar la siguiente cita, con medición de la presión del ojo y revisión de la retina, además de revisión médica de presión arterial, azúcar y grasas en sangre")
_v("fondo_oclusion_vascular_urgente", "SECUELA", "verificar seguimiento oftalmologico vigente", OFT, procedimiento="verificar el seguimiento vigente", detalle="para vigilar la retina, además del control médico de factores de riesgo vascular")
_v("fondo_embolo_retiniano", "NEURO", "derivacion inmediata a urgencias para evaluacion neurologica", URG, prioridad="urgente", plazo="de inmediato", detalle="para una evaluación neurológica")
_v("fondo_embolo_retiniano", "VISUAL", "derivacion inmediata el mismo dia a urgencias con atencion", EVC, prioridad="urgente", plazo="de inmediato", detalle="para evaluación de los vasos del sistema nervioso y de los ojos")
_v("fondo_embolo_retiniano", "INTEGRAR", "Integrar la evaluacion medica del posible origen embolico", MED, relacion="misma valoración por oclusión vascular", detalle="junto con la valoración oftalmológica ya indicada, sin demorar esa atención")
_v("fondo_embolo_retiniano", "ASINTOMATICO", "evaluacion medica ambulatoria", MED, detalle="ambulatoria de los factores cardiovasculares y posible origen de una obstrucción; el médico decidirá si estudia las arterias del cuello")
_v("fondo_embolo_retiniano", "INDETERMINADO", "Amerita valoracion oftalmologica y medica", OFT, detalle="y a revisión médica de factores cardiovasculares; es necesario precisar los síntomas y cuándo comenzaron para decidir la prioridad")

_v("sintomas_alarma_traccion_vitreoretina", "A", "referencia a oftalmologia el mismo dia", OFT, prioridad="urgente", plazo=HOY, procedimiento="una revisión de la retina con las pupilas dilatadas", detalle="para descartar rotura o desprendimiento de retina")
_v("sintomas_alarma_traccion_vitreoretina", "B", "en un plazo maximo de 48 horas", "", prioridad="urgente", plazo="en un plazo máximo de 48 horas", procedimiento="una revisión de la retina con las pupilas dilatadas", alternativas="o con un oftalmólogo si no puede hacerse en la óptica")
_v("sintomas_alarma_traccion_vitreoretina", "C", "si son de inicio reciente o han aumentado", "", procedimiento="una revisión de la retina con las pupilas dilatadas", condicion="los síntomas son recientes o han aumentado", detalle="para descartar una rotura de la retina")

# Constructores con un selector común de prioridad. La tabla sigue el texto
# renderizado y no vuelve a evaluar las condiciones clínicas.
BINOCULARES = ("insuficiencia_convergencia", "ppc_exoforia", "cover_exoforia_sintomatica", "cover_endoforia_sintomatica", "desviacion_vertical", "endotropia_lente", "exotropia_lente", "ambliopia_sospecha", "ambliopia_isoametropica_bilateral", "deficit_visual_inexplicado_refractivo", "adulto_mayor_screening", "cvs_sospecha")
for cor in (*BINOCULARES, "diplopia_aguda", "campos_visuales_alterados", "motilidad_alterada", "horner_o_tercer_par_sospecha", "pupilas_alteradas", "anexos_patologicos", "opacidad_cristaliniana", "anexos_riesgo_glaucoma_secundario", "amsler_alterado"):
    if cor in (*BINOCULARES, "diplopia_aguda", "campos_visuales_alterados"):
        _v(cor, "inmediata", "inmediata en urgencias", URG, prioridad="urgente", plazo="de inmediato")
    if cor == "opacidad_cristaliniana":
        _v(cor, "pediatrica_hoy", "valoracion oftalmologica pediatrica urgente el mismo dia", "un oftalmólogo pediátrico", prioridad="urgente", plazo=HOY)
    if cor != "amsler_alterado":
        _v(cor, "hoy", "el mismo dia", MED if cor in ("campos_visuales_alterados", "motilidad_alterada", "horner_o_tercer_par_sospecha") else OFT, prioridad="urgente", plazo=HOY)
    if cor in ("motilidad_alterada", "pupilas_alteradas", "amsler_alterado"):
        _v(cor, "urgente", "valoracion especializada urgente" if cor == "motilidad_alterada" else "valoracion oftalmologica urgente", ESP if cor == "motilidad_alterada" else OFT, prioridad="urgente")
for cor in ("pupilas_alteradas",):
    _v(cor, "aferente", "de retina y via visual aferente", OFT, grupo="examen", procedimiento="una evaluación de la retina y del trayecto que lleva la información visual al cerebro")
    _v(cor, "anatomia", "de la respuesta y anatomia pupilar", OFT, grupo="examen", procedimiento="una evaluación de la respuesta y estructura de las pupilas")
for cor in ("diplopia_aguda",):
    _v(cor, "examen", "con evaluacion de la motilidad y alineacion ocular", "", grupo="examen", procedimiento="una evaluación del movimiento y alineación de los ojos", detalle="sin esperar el control periódico")
_v("amsler_alterado", "OCT", "con OCT macular segun los hallazgos", "", grupo="examen", procedimiento="una imagen por capas de la zona central de la retina según los hallazgos")
for cor, origen, destino, detalle in (
    ("anexos_patologicos", "evaluacion oftalmologica para caracterizar", OFT, "para revisar con detalle lo que se encontró"),
    ("opacidad_cristaliniana", "valoracion oftalmologica pediatrica para", "un oftalmólogo pediátrico", "para revisar con detalle lo que se encontró y vigilar el desarrollo visual"),
    ("opacidad_cristaliniana", "valoracion oftalmologica para", OFT, "para revisar con detalle lo que se encontró"),
    ("anexos_riesgo_glaucoma_secundario", "evaluacion oftalmologica del segmento anterior", OFT, "con revisión de la parte anterior del ojo, presión del ojo y ángulo interno según corresponda"),
    ("amsler_alterado", "evaluacion oftalmologica de la vision central", OFT, "para revisar la visión central y los estudios necesarios según los hallazgos"),
    ("campos_visuales_alterados", "evaluacion especializada y caracterizacion", ESP, "con estudio formal del campo visual según corresponda"),
    ("motilidad_alterada", "valoracion especializada para aclarar", ESP, "para aclarar su causa"),
    ("motilidad_alterada", "para decidir si requiere valoracion especializada", ESP, "solo si la revisión inicial lo indica"),
    ("horner_o_tercer_par_sospecha", "valoracion especializada para caracterizar", ESP, "para revisar la respuesta pupilar y el movimiento de los ojos"),
    ("miopia_magna", "valoracion de retina central y periferica", ESP, "de la retina central y periférica y seguimiento según los hallazgos y controles registrados"),
    ("queratometria_asimetrica_interocular", "valorar evaluacion corneal especializada", ESP, "de la córnea si la diferencia persiste sin explicación o hay otros signos en su revisión"),
    ("queratocono_ectasia_sospecha", "valorar evaluacion corneal especializada", ESP, "de la córnea y los estudios de su forma si los valores persisten sin explicación o hay otros signos en su revisión"),
):
    _v(cor, "no_urgente_pediatrica" if "pediátrico" in destino else "no_urgente_condicional" if "decidir" in origen else "no_urgente", origen, destino, detalle=detalle)
for cor in ("ambliopia_sospecha", "ambliopia_isoametropica_bilateral", "deficit_visual_inexplicado_refractivo", "adulto_mayor_screening"):
    if cor == "ambliopia_isoametropica_bilateral":
        _v(cor, "pediatrica", "evaluacion oftalmologica pediatrica", "un oftalmólogo pediátrico", detalle="tras verificar las mediciones y la corrección utilizada")
    _v(cor, "evaluacion", "evaluacion oftalmologica", OFT, detalle="tras verificar las mediciones y la corrección utilizada")
_v("fondo_embolo_retiniano", "verificar", "Verificar el hallazgo mediante valoracion oftalmologica", OFT, grupo="verificacion", procedimiento="verificar lo que se encontró")
_v("av_cc_limitada", "evaluacion", "requiere evaluacion oftalmologica", OFT, condicion="la visión sigue reducida sin explicación después de verificar la medición y la corrección")
_v("anisometropia", "pediatrica_condicional", "valorar evaluacion especializada segun agudeza visual y alineacion", ESP, detalle="según la agudeza visual y la alineación de los ojos, tras revisar el desarrollo visual")
CATALOGO = tuple(CATALOGO)


def _desconocida(nombre, texto):
    """Conserva destinos, procedimientos y plazos reconocidos, sin inferir horas."""
    norm = normalizar(texto)
    urgente = "urgente" in norm or "inmediata" in norm
    destino = (EVC if "evento vascular cerebral" in norm else URG if "urgencias" in norm else
               "un oftalmólogo pediátrico" if "oftalmologica pediatrica" in norm else
               "un neurooftalmólogo" if "neurooftalm" in norm else RET if "retinolog" in norm else
               OFT if "oftalmolog" in norm else "neurología" if "neurolog" in norm else
               MED if "medica" in norm else "la valoración urgente que le indicó su optometrista" if urgente else "la valoración que le indicó su optometrista")
    plazos = ((r"(?:mismo dia|hoy)", HOY), (r"24 horas", "en las próximas 24 horas"),
              (r"48 horas", "en un plazo máximo de 48 horas"), (r"72 horas", "en un plazo máximo de 72 horas"),
              (r"1 dia habil|un dia habil", "en un plazo máximo de un día hábil"),
              (r"proximos dias", "en los próximos días"), (r"inmediat", "de inmediato"))
    plazo = next((v for k, v in plazos if re.search(k, norm)), "de inmediato" if urgente else "")
    proc = "gestionar la derivación" if "gestionad" in norm else "contacto para triaje" if "triage" in norm else "consulta"
    detalle = "con revisión de la retina con las pupilas dilatadas" if "midriasis" in norm else ""
    logger.warning("Acción del paciente sin mapear")
    return Accion(nombre, "sin_mapear", texto, destino, proc, "urgente" if urgente else "ordinaria", plazo, detalle=detalle, mapeada=False)


def extraer_acciones(correlaciones):
    resultado = []
    for cor in correlaciones:
        nombre, texto = cor["nombre"], cor["texto"]
        norm, grupos = normalizar(texto), set()
        locales = []
        for v in CATALOGO:
            if v.accion.correlacion == nombre and v.grupo not in grupos and re.search(v.patron, norm):
                locales.append(v.accion); grupos.add(v.grupo)
        if not locales and re.search(r"urgente|derivacion|referencia a|valoracion (?:oftalmolog|retinolog|medica|especializada)|evaluacion (?:oftalmolog|medica|corneal especializada|especializada)|(?:mantener|verificar) (?:su |el )?seguimiento (?:retinologico|oftalmologico)", norm):
            locales.append(_desconocida(nombre, texto))
        for a in locales:
            # Solo equivalentes exactos se agrupan, preservando orden y relación.
            firma = (a.destino, a.procedimiento, a.prioridad, a.plazo, a.condicion, a.alternativas, a.relacion, a.detalle)
            if not any(firma == (b.destino, b.procedimiento, b.prioridad, b.plazo, b.condicion, b.alternativas, b.relacion, b.detalle) for b in resultado):
                resultado.append(a)
    return tuple(resultado)
