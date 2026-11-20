import pytest

from app.seguimiento.catalogo import APERTURAS, INVITACIONES
from app.seguimiento.servicio import respaldo
from app.seguimiento.validador import validar, validar_estilo, LEXICO, PALABRAS
from tests.seguimiento_helpers import request


@pytest.mark.parametrize("apertura", APERTURAS.values())
@pytest.mark.parametrize("invitacion", INVITACIONES.values())
def test_todas_las_muestras_pasan_estilo(apertura, invitacion):
    assert validar_estilo(apertura, invitacion) is None


@pytest.mark.parametrize("termino", LEXICO)
def test_lexico_inicio_de_palabra(termino):
    assert validar_estilo(APERTURAS["A1"], f"¿{termino}?") == "lexico"
    assert validar_estilo(APERTURAS["A1"], f"¿prefijo{termino}?") is None or " " in termino


@pytest.mark.parametrize("palabra", ["vista", "visión", "ojo", "ojos", "graduación", "graduaciones"])
def test_palabras_completas(palabra):
    assert validar_estilo(APERTURAS["A1"], f"¿Su {palabra}?") == "lexico"
    assert validar_estilo(APERTURAS["A1"], f"¿X{palabra}x?") is None


@pytest.mark.parametrize("cambio,regla", [
    ({"apertura": ""}, "palabras"),
    ({"apertura_extra": "\n"}, "palabras"),
    ({"apertura_extra": " :paciente"}, "placeholders"),
    ({"invitacion_extra": " :clinica"}, "placeholders"),
    ({"apertura_extra": " :fecha"}, "placeholders"),
    ({"apertura_extra": " http"}, "placeholders"),
    ({"apertura_extra": " {hola}"}, "placeholders"),
    ({"apertura_extra": " <hola>"}, "placeholders"),
    ({"apertura_extra": " *hola*"}, "placeholders"),
    ({"apertura_extra": " www"}, "placeholders"),
    ({"apertura_extra": " 12"}, "cifras"),
    ({"invitacion": "Puede venir cuando le resulte cómodo."}, "pregunta"),
    ({"invitacion": "Le apartamos un horario?"}, "pregunta"),
    ({"apertura_extra": " Te esperamos."}, "tuteo"),
    ({"apertura_extra": " Su vista."}, "lexico"),
    ({"apertura_extra": " No tiene miopía."}, "lexico"),
    ({"apertura_extra": " No es verdad que la graduación cambia."}, "lexico"),
    ({"apertura_extra": " Es gratis."}, "lexico"),
    ({"apertura_extra": " ¡Solo esta semana!"}, "lexico"),
    ({"invitacion": INVITACIONES["I1"]}, "costo"),
    ({"invitacion": "La revisión tiene un costo. ¿Le apartamos un horario?"}, "costo"),
    ({"apertura_extra": " Está incluida."}, "costo"),
    ({"invitacion": "Está incluida, sí, incluida. ¿Le apartamos una cita?"}, "costo"),
    ({"ids": ["miopia_lejos", "miopia_lejos"]}, "combinacion"),
    ({"mensaje_extra": " texto ajeno"}, "hechos"),
])
def test_primera_regla(cambio, regla):
    req = request()
    r = respaldo(req)
    a = cambio.get("apertura", r.partes.apertura) + cambio.get("apertura_extra", "")
    i = cambio.get("invitacion", r.partes.invitacion) + cambio.get("invitacion_extra", "")
    ids = cambio.get("ids", r.partes.hechos)
    mensaje = r.mensaje + cambio["mensaje_extra"] if "mensaje_extra" in cambio else None
    assert validar(req, a, ids, i, r.hechos_elegibles, mensaje=mensaje) == regla


@pytest.mark.parametrize("costo,ids,i,esperado", [
    ("con_costo", ["miopia_lejos", "pantallas_muchas"], "I1", "costo"),
    ("con_costo", ["miopia_lejos", "pantallas_muchas"], "I3", None),
    ("incluida", ["miopia_lejos", "pantallas_muchas"], "I2", None),
    ("incluida", ["miopia_lejos", "incluida_sin_costo"], "I2", "costo"),
    ("incluida", ["miopia_lejos", "incluida_sin_costo"], "I1", None),
    ("con_costo", ["miopia_lejos", "con_costo_claro"], "I3", "costo"),
    ("con_costo", ["miopia_lejos", "con_costo_claro"], "I1", None),
])
def test_costo_una_vez(costo, ids, i, esperado):
    from app.seguimiento.elegibilidad import hechos_elegibles
    req = request(costo=costo)
    assert validar(req, APERTURAS["A1"], ids, INVITACIONES[i], hechos_elegibles(req)) == esperado


# Sondas originales de auditoría y X2, congeladas sin dependencia del scratchpad.
@pytest.mark.parametrize(
    "etiqueta,costo,ids,apertura,invitacion,regla",
[   (   'costo: incluido en con_costo',
        'con_costo',
        ['progresivo_zonas', 'vencida_retomar'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo. Su chequeo está incluido en su atención.',
        'La revisión tiene un costo. ¿Qué día de la semana le resulta más cómodo para venir?',
        'costo'),
    (   'tuteo: estas sin acento',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo; si estas disponible nos avisa.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'tuteo'),
    (   'tuteo: avisanos sin acento',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. Si le conviene, avisanos pronto. ¿Qué día de la semana le resulta más cómodo para '
        'venir?',
        'tuteo'),
    (   'tuteo: escribenos sin acento',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. Si prefiere, escribenos hoy. ¿Qué día de la semana le resulta más cómodo para venir?',
        'tuteo'),
    (   'tuteo: cuentanos sin acento',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. Por favor cuentanos su horario. ¿Qué día de la semana le resulta más cómodo para '
        'venir?',
        'tuteo'),
    (   'tuteo: dinos imperativo',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. Por favor dinos cuando puede. ¿Qué día de la semana le resulta más cómodo para venir?',
        'tuteo'),
    (   'tuteo: prefieres',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Prefieres venir entre semana o en sábado?',
        'tuteo'),
    (   'tuteo: deseas',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Deseas apartar una cita esta semana?',
        'tuteo'),
    (   'tuteo: reserva imperativo',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. Reserva una cita con nosotros. ¿Qué día de la semana le resulta más cómodo para venir?',
        'tuteo'),
    (   'tuteo: aparta imperativo',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. Aparta una cita con nosotros. ¿Qué día de la semana le resulta más cómodo para venir?',
        'tuteo'),
    (   'medico: estrabismo',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo, para evaluar su estrabismo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'lexico'),
    (   'medico: ambliopia',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo, para controlar su ambliopia.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'lexico'),
    (   'medico: queratocono',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo, para revisar su queratocono.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'lexico'),
    (   'medico: danar verbo',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo, para que no se dane su agudeza visual.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'lexico'),
    (   'medico: fatiga ocular',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo, si siente fatiga ocular.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'lexico'),
    (   'medico: deterioro',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo, para evitar un deterioro visual.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'lexico'),
    (   'markdown: cursiva con guion bajo',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su _revisión visual_ de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'placeholders'),
    (   'markdown: tachado con tilde',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su ~revisión visual~ de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'placeholders'),
    (   'markdown: monospace con backticks',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su ```revisión visual``` de control y '
        'quisimos escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'placeholders'),
    (   'promesa: aseguramos',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. Le aseguramos el mejor servicio profesional. ¿Qué día de la semana le resulta más '
        'cómodo para venir?',
        'lexico'),
    (   'promesa: resolver',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. Con gusto le resolvemos cualquier molestia al ver. ¿Qué día de la semana le resulta '
        'más cómodo para venir?',
        'lexico'),
    (   'costo: tarifa en incluida',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo; aplica una pequeña tarifa de consulta.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'costo'),
    (   'costo: arancel en incluida',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo; requiere un arancel administrativo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'costo'),
    (   'negacion del hecho',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo; aunque probablemente sus lentes estén bien.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'lexico'),
    (   'vista disfrazada mayusc',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Su VISTA puede cambiar y ya se acerca su revisión visual '
        'de control y quisimos escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'lexico'),
    (   'ver borroso sin palabra clave',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Si nota que ve menos claro, ya se acerca su revisión '
        'visual de control y quisimos escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'lexico'),
    (   'tuteo visitanos',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. Visítanos pronto. ¿Qué día de la semana le resulta más cómodo para venir?',
        'tuteo'),
    (   'tuteo recuerda',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Recuerda que ya se acerca tu revisión visual de control.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'tuteo'),
    (   'tuteo llamanos',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. Llámanos cuando quieras. ¿Qué día de la semana le resulta más cómodo para venir?',
        'tuteo'),
    (   'cifra en palabras',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Hace doce meses fue su revision y ya se acerca su '
        'revisión visual de control y quisimos escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'lexico'),
    (   'urgencia sin lexico',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. No espere más. ¿Qué día de la semana le resulta más cómodo para venir?',
        'lexico'),
    (   'miedo sin lexico',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo, porque esperar puede complicar las cosas.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'lexico'),
    (   'culpa',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Hace mucho que no viene y ya se acerca su revisión '
        'visual de control y quisimos escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'lexico'),
    (   'promesa',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. Saldrá viendo mucho mejor. ¿Qué día de la semana le resulta más cómodo para venir?',
        'lexico'),
    (   'html',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo. <b>',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'placeholders'),
    (   'markdown negrita',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su *revisión visual* de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'placeholders'),
    (   'salto de linea',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica.\n'
        'Ya se acerca su revisión visual de control y quisimos escribirle con tiempo para que la organice a '
        'su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'palabras'),
    (   'marcador extra',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. Su cita :fecha. ¿Qué día de la semana le resulta más cómodo para venir?',
        'placeholders'),
    (   'diagnostico con acento',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Su diagnóstico indica que ya se acerca su revisión '
        'visual de control y quisimos escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'lexico'),
    (   'condicion sin acento',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Por su miopia ya se acerca su revisión visual de control '
        'y quisimos escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'lexico'),
    (   'nitidez',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Para que vuelva a ver con nitidez, ya se acerca su '
        'revisión visual de control y quisimos escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. ¿Qué día de la semana le resulta más cómodo para venir?',
        'lexico'),
    (   'descuento en palabras',
        'incluida',
        ['miopia_lejos', 'pantallas_muchas'],
        'Hola, :paciente, le saludamos de :clinica. Ya se acerca su revisión visual de control y quisimos '
        'escribirle con tiempo para que la organice a su ritmo.',
        'La revisión está incluida en su atención, y con gusto le buscamos un horario que se acomode a sus '
        'actividades. Este mes la revisión le sale a mitad de precio. ¿Qué día de la semana le resulta más '
        'cómodo para venir?',
        'lexico')],
)
def test_sondas_auditoria_y_x2(etiqueta, costo, ids, apertura, invitacion, regla):
    from app.seguimiento.elegibilidad import hechos_elegibles
    req = request(costo=costo)
    assert validar(req, apertura, ids, invitacion, hechos_elegibles(req)) == regla


@pytest.mark.parametrize("texto", [
    "revisión visual", "Si usa lentes, puede traerlos", "le queda mejor", "próximos días", "una cita",
    "muy bien", "El equipo le recuerda su cita", "El equipo les recuerda su cita", "estas actividades",
    "Seguimos dando atención", "Le ayudamos a resolverla",
])
def test_positivos_endurecimiento(texto):
    assert validar_estilo(APERTURAS["A1"], f"¿{texto}?") is None


@pytest.mark.parametrize("texto", ["sus lentes están bien", "sus lentes ya no le sirven", "Si usa lentes, sus lentes están bien"])
def test_lentes_solo_condicional(texto):
    assert validar_estilo(APERTURAS["A1"], f"¿{texto}?") == "lexico"


@pytest.mark.parametrize("palabra", PALABRAS)
def test_nuevas_palabras_completas(palabra):
    assert validar_estilo(APERTURAS["A1"], f"¿{palabra}?") == "lexico"
    assert validar_estilo(APERTURAS["A1"], f"¿prefijo{palabra}sufijo?") is None


@pytest.mark.parametrize("texto", ["Recuerda su cita", "avísanos", "avisanos", "Visítanos", "Llámanos", "estás interesado", "estas lista"])
def test_tuteo_normalizado(texto):
    assert validar_estilo(APERTURAS["A1"], f"¿{texto}?") == "tuteo"


@pytest.mark.parametrize("costo,texto,regla", [
    ("con_costo", "Su revisión es gratuita.", "costo"),
    ("con_costo", "Su chequeo está incluido.", "costo"),
    ("con_costo", "Sus controles están incluidos.", "costo"),
    ("incluida", "Aplica una cuota.", "costo"),
    ("incluida", "Consulte el importe.", "costo"),
    ("incluida", "Puede pagar aquí.", "lexico"),
])
def test_variantes_costo(costo, texto, regla):
    req = request(costo=costo)
    r = respaldo(req)
    assert validar(req, r.partes.apertura + " " + texto, r.partes.hechos,
                   r.partes.invitacion, r.hechos_elegibles) == regla


# No se veta resolv: I8 exige resolverla. Esta promesa semántica requiere
# la verificación y aprobación humana; la sonda literal X2 con ver sí cae.
def test_resolver_sin_vision_permanece_para_verificacion():
    assert validar_estilo(APERTURAS["A1"], "¿Le resolvemos cualquier molestia?") is None
