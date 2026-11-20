"""Catálogo de WhatsApp de seguimiento v2. Textos literales del catálogo consolidado."""
from dataclasses import dataclass

CATALOGO_VERSION = "v2-borrador-2026-11-20"
PROMPT_VERSION = "seguimiento-whatsapp-prompt-v3"
VERIFICACION_VERSION = "seguimiento-verificacion-v1"
CONTRATO_VERSION = "seguimiento-whatsapp-v2"
BAJA = "Si prefiere no recibir estos mensajes, solo díganoslo."


@dataclass(frozen=True)
class Hecho:
    id: str
    grupo: str
    tema: str
    texto: str
    activo: bool = True


HECHOS = (
    Hecho('progresivo_zonas', 'A', 'progresivo', 'En sus lentes progresivos revisamos que la zona de lejos, la intermedia y la de cerca sigan acomodándose a sus actividades.', True),
    Hecho('bifocal_zonas', 'A', 'bifocal', 'En sus lentes bifocales revisamos que la parte de lejos y la de cerca sigan acomodándose a lo que usted hace.', True),
    Hecho('hipermetropia_cerca', 'A', 'hipermetropia', 'En la revisión verificamos que su graduación para la hipermetropía le resulte cómoda, tanto de lejos como de cerca.', True),
    Hecho('astigmatismo_comodidad', 'A', 'astigmatismo', 'Con astigmatismo, que el armazón esté bien alineado influye en cómo funcionan sus lentes; en la revisión lo verificamos.', False),
    Hecho('progresivo_ajuste', 'A', 'progresivo', 'En los lentes progresivos, la altura y el ajuste del armazón influyen mucho en la comodidad, y en la revisión los verificamos con calma.', False),
    Hecho('ajuste_armazon', 'A', 'armazon', 'Además de la graduación, revisamos el ajuste de su armazón, que también influye en lo cómodos que se sienten sus lentes.', False),
)

POR_ID = {h.id: h for h in HECHOS}

FRASES_USO = {
    "ver_de_lejos": [
        ("FU_ver_de_lejos_1", "Pensamos en sus lentes para ver de lejos y en cómo le han acompañado en este tiempo."),
        ("FU_ver_de_lejos_2", "Nos acordamos de sus lentes para ver de lejos, para la calle y para todo lo que mira a distancia."),
    ],
    "ver_de_cerca": [
        ("FU_ver_de_cerca_1", "Pensamos en sus lentes para ver de cerca, para leer o usar el celular."),
        ("FU_ver_de_cerca_2", "Nos acordamos de sus lentes para leer y para las cosas que hace de cerca."),
    ],
    "computadora": [
        ("FU_computadora_1", "Pensamos en sus lentes y en cómo le han acompañado frente a la computadora y otras pantallas."),
        ("FU_computadora_2", "Nos acordamos de sus lentes y del tiempo que pasa frente a la computadora y otras pantallas en su día."),
    ],
    "lejos_y_cerca": [
        ("FU_lejos_y_cerca_1", "Pensamos en sus lentes para ver tanto de lejos como de cerca."),
        ("FU_lejos_y_cerca_2", "Nos acordamos de sus lentes para pasar de ver de lejos a ver de cerca durante el día."),
    ],
    "estudiar": [
        ("FU_estudiar_1", "Pensamos en sus lentes y en cómo le han acompañado en sus estudios."),
        ("FU_estudiar_2", "Nos acordamos de sus lentes para sus clases y sus horas de estudio."),
    ],
    "trabajar": [
        ("FU_trabajar_1", "Pensamos en sus lentes para sus actividades de trabajo."),
        ("FU_trabajar_2", "Nos acordamos de sus lentes para su jornada de trabajo."),
    ],
    "manejar": [
        ("FU_manejar_1", "Pensamos en sus lentes y en cómo le han acompañado cuando maneja."),
        ("FU_manejar_2", "Nos acordamos de sus lentes y de sus trayectos cuando maneja."),
    ],
    "desconocido": [
        ("FU_desconocido_1", "Pensamos en sus lentes y en cómo le han funcionado en su día a día."),
        ("FU_desconocido_2", "Nos acordamos de sus lentes y de lo que hace con ellos día con día."),
    ],
}

FRASES_FECHA = {
    "P": [
        ("FF_P_1", "El {fecha} cumple {periodo} de su última revisión con nosotros, y nos gustaría ver con usted cómo va su graduación."),
        ("FF_P_2", "El {fecha} cumple {periodo} de su última revisión, y por eso quisimos saber de usted."),
        ("FF_P_3", "Para el {fecha} cumple {periodo} de su última revisión; será un buen momento para comprobar con calma si su graduación sigue siendo la adecuada para usted."),
        ("FF_P_4", "El {fecha} cumple {periodo} desde su última revisión con nosotros, y nos gustaría ver con usted, con calma, cómo va su graduación."),
    ],
    "PS": [
        ("FF_PS_1", "Se acerca el {fecha}, la fecha que le sugerimos para su siguiente revisión, y por eso quisimos saber de usted."),
        ("FF_PS_2", "Para el {fecha} le sugerimos su siguiente revisión; será un buen momento para platicar con calma sobre su graduación."),
        ("FF_PS_3", "Alrededor del {fecha} le sugerimos su siguiente revisión, y nos gustaría ver juntos cómo va su graduación."),
    ],
    "N": [
        ("FF_N_1", "Quisimos saber de usted y de cómo le ha ido en este tiempo."),
        ("FF_N_2", "Para nosotros es un gusto seguir en contacto con usted, a su ritmo y sin prisas."),
        ("FF_N_3", "Nos interesa saber de usted y de lo que hoy necesita de sus lentes."),
        ("FF_N_4", "Queremos acompañarle con calma, cuando y como usted lo prefiera."),
    ],
}

APERTURAS_V2 = {
    "AP_PROX_CONT": [
        ("AP_PROX_CONT_1", "Buen día, :paciente. Le escribimos de :clinica porque nos da gusto seguir acompañándole y queremos saber de usted."),
        ("AP_PROX_CONT_2", "Hola, :paciente, le saludamos de :clinica. Nos da gusto seguir acompañándole y por eso quisimos escribirle hoy."),
        ("AP_PROX_CONT_3", "Muy buen día, :paciente. Le saluda con aprecio el equipo de :clinica; nos da gusto seguir acompañándole y saber cómo está."),
        ("AP_PROX_CONT_4", "Hola, :paciente. Le escribimos de :clinica para saludarle; nos da gusto seguir acompañándole como hasta ahora."),
        ("AP_PROX_CONT_5", "Buen día, :paciente. Para el equipo de :clinica es un gusto seguir acompañándole, y hoy queremos saber de usted."),
    ],
    "AP_PROX_PRIM": [
        ("AP_PROX_PRIM_1", "Hola, :paciente, le saludamos de :clinica. Gracias por la confianza que nos ha dado; queremos acompañarle y saber de usted."),
        ("AP_PROX_PRIM_2", "Buen día, :paciente. Le escribimos de :clinica porque queremos acompañarle y saber cómo le ha ido."),
        ("AP_PROX_PRIM_3", "Muy buen día, :paciente. Le saluda el equipo de :clinica; nos gustaría seguir en contacto con usted y saber cómo se encuentra."),
        ("AP_PROX_PRIM_4", "Hola, :paciente. En :clinica le tenemos presente y queremos acompañarle; por eso le escribimos con gusto."),
    ],
    "AP_VENC": [
        ("AP_VENC_1", "Hola, :paciente, le saludamos de :clinica. Nos acordamos de usted con gusto y queremos saber cómo se encuentra."),
        ("AP_VENC_2", "Buen día, :paciente. Le escribimos de :clinica porque nos da gusto saber de usted y seguir acompañándole."),
        ("AP_VENC_3", "Muy buen día, :paciente. El equipo de :clinica le envía un saludo cordial; queremos saber de usted y acompañarle."),
        ("AP_VENC_4", "Hola, :paciente. En :clinica le tenemos presente y nos gustaría volver a saber de usted."),
        ("AP_VENC_5", "Hola, :paciente, le saludamos de :clinica. Esperamos que se encuentre muy bien; queremos acompañarle cuando usted lo decida."),
    ],
    "AP_SEG": [
        ("AP_SEG_1", "Hola, :paciente, le saludamos de nuevo de :clinica. Solo queremos saber de usted, sin ninguna prisa."),
        ("AP_SEG_2", "Buen día, :paciente. Le escribimos otra vez de :clinica, con calma, porque nos interesa saber cómo se encuentra."),
        ("AP_SEG_3", "Hola, :paciente. En :clinica seguimos con gusto a sus órdenes y quisimos saludarle una vez más."),
        ("AP_SEG_4", "Muy buen día, :paciente. Le saluda nuevamente el equipo de :clinica; queremos acompañarle cuando a usted le acomode."),
    ],
}

CIERRES = {
    "INC": [
        ("CI_INC_1", "¿Cómo le va con sus lentes? Si todo va bien, nos da gusto saberlo; y si quiere que revisemos algo, su revisión está incluida en su atención y nosotros le buscamos un horario."),
        ("CI_INC_2", "¿Cómo le han funcionado sus lentes hasta ahora? Si gusta, también le apartamos una revisión, que está incluida en su atención."),
        ("CI_INC_3", "Nos encantaría leerle: ¿cómo se ha sentido con sus lentes en este tiempo? Y si le acomoda, con gusto le buscamos un horario para su revisión, que está incluida en su atención."),
        ("CI_INC_4", "¿Qué tal le han funcionado sus lentes en su día a día? Cuando usted quiera, le apartamos un espacio para su revisión; está incluida en su atención."),
        ("CI_INC_5", "Platíquenos, ¿cómo se ha sentido con sus lentes últimamente? Si quiere, también vemos juntos un horario para su revisión, que está incluida en su atención."),
        ("CI_INC_6", "Nos dará gusto leerle: ¿cómo le va con sus lentes? Si lo desea, le buscamos un horario para su revisión, que está incluida en su atención."),
    ],
    "COS": [
        ("CI_COS_1", "¿Cómo le va con sus lentes? Si todo va bien, nos da gusto saberlo. Y si quiere su revisión, tiene un costo; con gusto le informamos el monto y le buscamos un horario, y usted decide."),
        ("CI_COS_2", "¿Cómo le han funcionado sus lentes hasta ahora? Si gusta, también le apartamos una revisión; tiene un costo y con gusto le compartimos el detalle antes de que decida."),
        ("CI_COS_3", "Nos encantaría leerle: ¿cómo se ha sentido con sus lentes en este tiempo? Si le interesa una revisión, le compartimos su costo sin compromiso y le buscamos un horario solo si usted lo desea."),
        ("CI_COS_4", "¿Qué tal le han funcionado sus lentes en su día a día? Cuando usted quiera, le contamos el costo de la revisión y, si le parece, le apartamos un espacio."),
        ("CI_COS_5", "Platíquenos, ¿cómo se ha sentido con sus lentes últimamente? Si más adelante desea una revisión, con gusto le informamos su costo antes de agendar, sin ningún compromiso."),
        ("CI_COS_6", "Nos dará gusto leerle: ¿cómo le va con sus lentes? Si quiere, también le buscamos un horario para su revisión; tiene un costo y se lo compartimos antes de agendar."),
    ],
}

APERTURAS_POR_ID = {id: texto for grupo in APERTURAS_V2.values() for id, texto in grupo}
CIERRES_POR_ID = {id: texto for grupo in CIERRES.values() for id, texto in grupo}
FRASES_USO_POR_ID = {id: texto for grupo in FRASES_USO.values() for id, texto in grupo}
FRASES_FECHA_POR_ID = {id: texto for grupo in FRASES_FECHA.values() for id, texto in grupo}

PRIORIDAD_HECHOS = ("progresivo", "bifocal", "hipermetropia", "astigmatismo", "armazon")
