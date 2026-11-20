"""Texto literal del catálogo v1; no se redactan hechos con el modelo."""
from dataclasses import dataclass

CATALOGO_VERSION = "v1-revisado-2026-11-06"
PROMPT_VERSION = "seguimiento-whatsapp-prompt-v1"
VERIFICACION_VERSION = "seguimiento-verificacion-v1"
CONTRATO_VERSION = "seguimiento-whatsapp-v1"


@dataclass(frozen=True)
class Hecho:
    id: str
    grupo: str
    tema: str
    texto: str


HECHOS = (
    Hecho('miopia_ajuste', 'A', 'miopia', 'Con el tiempo la miopía puede cambiar, y revisarla periódicamente permite ajustar sus lentes cuando haga falta.'),
    Hecho('miopia_lejos', 'A', 'miopia', 'En la revisión comprobamos si sus lentes le siguen dando una visión de lejos cómoda para sus actividades diarias.'),
    Hecho('hipermetropia_ajuste', 'A', 'hipermetropia', 'La graduación para la hipermetropía puede necesitar ajustes con el tiempo, y la revisión periódica nos permite saber si hace falta alguno.'),
    Hecho('hipermetropia_cerca', 'A', 'hipermetropia', 'En la revisión verificamos que su graduación para la hipermetropía le resulte cómoda, tanto de lejos como de cerca.'),
    Hecho('astigmatismo_detalle', 'A', 'astigmatismo', 'En el astigmatismo, la precisión de la graduación influye en la comodidad visual, por eso conviene revisarla periódicamente.'),
    Hecho('astigmatismo_comodidad', 'A', 'astigmatismo', 'Con astigmatismo, que el armazón esté bien alineado influye en cómo funcionan sus lentes; en la revisión lo verificamos.'),
    Hecho('cerca_adecuado', 'A', 'cerca', 'Revisar su graduación ayuda a comprobar si su apoyo para ver de cerca sigue siendo el adecuado para lo que usted hace.'),
    Hecho('cerca_distancias', 'A', 'cerca', 'Si lee o usa el celular con frecuencia, en la consulta podemos revisar su apoyo de cerca según las distancias que más utiliza.'),
    Hecho('progresivo_zonas', 'A', 'progresivo', 'En sus lentes progresivos revisamos que la zona de lejos, la intermedia y la de cerca sigan acomodándose a sus actividades.'),
    Hecho('progresivo_ajuste', 'A', 'progresivo', 'En los lentes progresivos, la altura y el ajuste del armazón influyen mucho en la comodidad, y en la revisión los verificamos con calma.'),
    Hecho('bifocal_zonas', 'A', 'bifocal', 'En sus lentes bifocales revisamos que la parte de lejos y la de cerca sigan acomodándose a lo que usted hace.'),
    Hecho('ajuste_armazon', 'A', 'armazon', 'Además de la graduación, revisamos el ajuste de su armazón, que también influye en lo cómodos que se sienten sus lentes.'),
    Hecho('pantallas_muchas', 'B', 'pantallas', 'Si pasa muchas horas frente a pantallas, en la revisión podemos ver qué tan cómodos le resultan sus lentes para esas actividades.'),
    Hecho('pantallas_ratos', 'B', 'pantallas', 'Si usa pantallas durante parte del día, en la revisión podemos platicar sobre distancias y pausas que le resulten cómodas.'),
    Hecho('vencida_retomar', 'B', 'vencida', 'Si ha pasado un tiempo desde su última revisión, retomarla es sencillo y la hacemos a su ritmo, sin prisas.'),
    Hecho('incluida_sin_costo', 'B', 'costo', 'Su revisión de seguimiento está incluida en su atención, sin ningún costo adicional para usted.'),
    Hecho('con_costo_claro', 'B', 'costo', 'La revisión tiene un costo, y con gusto le informamos el monto antes de agendar para que decida con calma.'),
    Hecho('comodidad_general', 'B', 'comodidad', 'Si algo de sus lentes le incomoda o nota que ya no le acomodan igual, la revisión es un buen momento para comentarlo.'),
    Hecho('general_periodica', 'B', 'periodica', 'La revisión periódica nos permite comprobar si sus lentes siguen siendo adecuados para sus actividades de todos los días.'),
    Hecho('traer_lentes', 'B', 'traer', 'Si usa lentes, le sugerimos traerlos a la consulta, así podemos revisarlos junto con su graduación.'),
)
POR_ID = {h.id: h for h in HECHOS}
APERTURAS = {'A1': 'Hola, :paciente, le saludamos de :clinica. Se acerca la fecha de su revisión visual de control y quisimos avisarle con tiempo.', 'A2': 'Buen día, :paciente. En :clinica nos acordamos de usted y queremos ayudarle a tener al día su revisión visual.', 'A3': 'Hola, :paciente. Le escribimos de :clinica con un recordatorio amable: ya es momento de su revisión visual periódica.', 'A4': 'Hola, :paciente, le saludamos de :clinica. Sabemos que el tiempo se va rápido entre tantas ocupaciones; cuando usted quiera, retomamos su revisión visual.', 'A5': 'Hola, :paciente. Le saludamos de :clinica; sabemos que sus días pueden estar muy llenos, así que queremos ponerle fácil su revisión visual.', 'A6': 'Muy buen día, :paciente. Le saluda con aprecio el equipo de :clinica; nos da gusto seguir acompañándole en sus revisiones.', 'A7': 'Hola, :paciente, ¿cómo está? Le escribimos de :clinica para recordarle que ya le toca su revisión visual de control.', 'A8': 'Hola, :paciente. En :clinica sabemos que su agenda suele estar llena; por eso le escribimos con anticipación sobre su revisión visual.', 'A9': 'Hola, :paciente, le saludamos de :clinica. Queremos recordarle su revisión visual periódica y darle toda la información para que decida con calma.', 'A10': 'Hola, :paciente. Le saluda el equipo de :clinica; esperamos que se encuentre muy bien y queremos recordarle su revisión visual.'}
INVITACIONES = {'I1': 'Nosotros le buscamos un horario que le acomode. ¿Le gustaría que le apartemos una cita?', 'I2': 'La revisión está incluida en su atención. ¿Qué día de la semana le queda mejor para venir?', 'I3': 'La revisión tiene un costo; si lo desea, con gusto le compartimos el detalle antes de agendar. ¿Le gustaría que veamos juntos un horario?', 'I4': 'Usted decide si es buen momento; si prefiere más adelante, también está bien. ¿Quiere que le propongamos algunos horarios?', 'I5': 'Con responder este mensaje basta para agendar. ¿Prefiere venir por la mañana o por la tarde?', 'I6': 'Si desea venir acompañado, con gusto les recibimos. ¿Le parece si le buscamos un horario tranquilo?', 'I7': 'Si usa lentes, puede traerlos. ¿Le acomoda que le apartemos un espacio en los próximos días?', 'I8': 'Si tiene alguna duda antes de venir, aquí estamos para resolverla. ¿Le gustaría agendar su revisión?', 'I9': 'Tomamos en cuenta sus horarios para que la visita le resulte práctica. ¿Qué día le resulta más cómodo?', 'I10': 'Cuando a usted le acomode, le esperamos con gusto. ¿Desea que le apartemos una cita?'}
BAJA = "Si prefiere no recibir estos recordatorios, solo díganoslo."
PUEDE_CAMBIAR = {"miopia_ajuste", "hipermetropia_ajuste", "astigmatismo_detalle"}
COMODIDAD_ARMAZON = {"astigmatismo_comodidad", "progresivo_ajuste", "ajuste_armazon", "comodidad_general"}
PRIORIDAD_A = ("progresivo", "bifocal", "cerca", "miopia", "hipermetropia", "astigmatismo", "armazon")
PRIORIDAD_B = ("pantallas_muchas", "vencida_retomar", "pantallas_ratos", "incluida_sin_costo", "con_costo_claro", "comodidad_general", "general_periodica", "traer_lentes")
