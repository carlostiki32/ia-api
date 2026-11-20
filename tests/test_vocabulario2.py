"""VOCAB2: cronología propia, complementos visuales e informantes; sin red."""
import pytest

from app.correlaciones.texto import _normalize_text
from app.correlaciones.vocabulario import perdidas_subitas
from app.correlaciones.fondo_de_ojo import _embolo_sintomas, _vascular_sintomas_oculares_actuales, _has_confirmed_dm
from app.correlaciones.binocularidad import _episodios_visuales, _sintomas_visuales_actuales
from app.correlaciones.motilidad import _sintomas_del_motivo
from app.correlaciones.segmento_anterior import _sintomas_segmento
from app.correlaciones.pupilas_motilidad import _ocurrencias_oculares, _SINTOMAS_EPISODIO
from app.paciente.sintomas import extraer_sintomas
from tests.test_auditoria_correlaciones import _req, activas

ALARMA = "sintomas_alarma_traccion_vitreoretina"
TIEMPOS = [
    "hoy", "ayer", "anoche", "esta mañana", "esta tarde", "esta noche",
    "hace 1 hora", "hace dos horas", "hace 15 minutos", "hace tres minutos",
    "desde hace unas horas",
] + [f"hace {n} días" for n in range(1, 8)] + [
    f"hace {n} días" for n in ("un", "dos", "tres", "cuatro", "cinco", "seis", "siete")
] + [f"desde el {dia}" for dia in ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")]


def comprobar_perdida(frase, afirmada):
    norm = _normalize_text(frase)
    assert bool(list(perdidas_subitas(norm))) == afirmada
    assert (ALARMA in activas(motivo=frase)) == afirmada
    assert any("perdida" in s[0] for s in _vascular_sintomas_oculares_actuales(norm)) == afirmada
    assert bool(_embolo_sintomas(_req(motivo=frase))["visuales"]) == afirmada


@pytest.mark.parametrize("tiempo", TIEMPOS)
@pytest.mark.parametrize("posicion", ["antes", "despues"])
@pytest.mark.parametrize("negada", [False, True])
def test_inicio_reciente_propio(tiempo, posicion, negada):
    frase = f"{tiempo} perdió la visión en OD" if posicion == "antes" else f"perdió la visión en OD {tiempo}"
    comprobar_perdida(("Niega " if negada else "") + frase, not negada)


@pytest.mark.parametrize("frase", [
    "Pérdida de visión sin fecha", "Pérdida de visión hace 8 días", "Pérdida de visión hace diez días",
    "Pérdida de visión hace 10 años", "Pérdida de visión hace 2 semanas", "Pérdida de visión hace tres semanas",
    "Hoy revisión por pérdida de visión", "Revisión hoy por pérdida de visión", "Pérdida de visión para control esta mañana",
    "Pérdida de visión. Hoy cefalea", "Hoy cefalea; pérdida de visión", "Hoy cefalea: pérdida de visión",
    "Hoy cefalea | pérdida de visión", "Hoy cefalea\npérdida de visión", "Hoy cefalea pero pérdida de visión",
    "Pérdida de visión y cefalea desde ayer", "Pérdida de visión, hoy cefalea", "Hoy cefalea, pérdida de visión",
    "Pérdida de visión mientras hoy tiene cefalea", "Pérdida de visión y desde ayer tiene dolor ocular",
])
@pytest.mark.parametrize("negada", [False, True])
def test_exclusiones_temporales(frase, negada):
    comprobar_perdida(("Niega " if negada else "") + frase, False)


@pytest.mark.parametrize("complemento", ["con el OD", "de lejos", "por el ojo izquierdo", "nada", "bien", ""])
@pytest.mark.parametrize("verbo", ["dejó", "dejé"])
@pytest.mark.parametrize("negada", [False, True])
def test_dejar_de_ver_visual(complemento, verbo, negada):
    frase = ("Niega " if negada else "") + f"Hoy {verbo} de ver {complemento}".strip()
    comprobar_perdida(frase, not negada)
    assert bool(extraer_sintomas(frase)) == (not negada)


@pytest.mark.parametrize("complemento", ["la televisión", "la tele", "películas", "series", "el celular", "a su familia", "borroso"])
@pytest.mark.parametrize("marcador", ["Hoy", "De repente"])
@pytest.mark.parametrize("negada", [False, True])
def test_dejar_de_ver_objeto_o_mejoria(complemento, marcador, negada):
    frase = ("Niega " if negada else "") + f"{marcador} dejó de ver {complemento}"
    comprobar_perdida(frase, False)
    assert not extraer_sintomas(frase)
    req = _req(motivo=frase)
    for hechos in (_episodios_visuales(req), _sintomas_del_motivo(req), _sintomas_segmento(req)):
        assert not any(h.afirmado for h in hechos)


@pytest.mark.parametrize("complemento,correlacion", [
    ("doble", "diplopia_aguda"), ("destellos", ALARMA), ("manchas", None),
])
@pytest.mark.parametrize("marcador", ["Hoy", "De repente"])
@pytest.mark.parametrize("negada", [False, True])
def test_dejar_de_ver_un_sintoma_no_es_perdida_pero_conserva_el_sintoma(complemento, correlacion, marcador, negada):
    """«Dejó de ver doble/destellos» no es pérdida visual, pero el síntoma sigue contando.

    Ante ambigüedad gana la detección: «dejó de ver doble con el parche» significa que la
    diplopía existe y el parche la oculta; los destellos que cesaron siguen siendo un
    antecedente reciente que amerita revisar la retina.
    """
    frase = ("Niega " if negada else "") + f"{marcador} dejó de ver {complemento}"
    assert not list(perdidas_subitas(_normalize_text(frase)))
    if correlacion:
        assert (correlacion in activas(motivo=frase)) == (not negada)


FAMILIARES = ["Su esposa", "La madre", "Su padre", "Su hija", "Su hijo", "Familiar", "Acompañante", "Tutor", "Su hermana", "Su abuelo", "Su pareja", "Cuidadora"]
REPORTES = ["refiere", "comenta", "menciona", "dice", "reporta", "informa", "indica", "señala", "nota", "ha notado", "observa", "cuenta", "relata", "manifiesta", "expresa", "describe"]


@pytest.mark.parametrize("informante", FAMILIARES)
@pytest.mark.parametrize("verbo", REPORTES)
@pytest.mark.parametrize("negada", [False, True])
def test_informante_con_reporte_en_consumidores(informante, verbo, negada):
    frase = f"{informante} {verbo} que " + ("no " if negada else "") + "tiene visión doble desde ayer"
    req = _req(motivo=frase)
    assert ("diplopia_aguda" in activas(motivo=frase)) == (not negada)
    assert bool(extraer_sintomas(frase)) == (not negada)
    for hechos, etiqueta in (
        (_episodios_visuales(req), "diplopia"), (_sintomas_del_motivo(req), "diplopia referida"),
        (_sintomas_segmento(req), "sintoma|diplopia"),
        (_ocurrencias_oculares(frase, _SINTOMAS_EPISODIO, "motivo_consulta"), "diplopia referida"),
    ):
        assert any(h.afirmado and h.hallazgo == etiqueta for h in hechos) == (not negada)
    assert bool(_sintomas_visuales_actuales(req, binocular=False)) == (not negada)


@pytest.mark.parametrize("contenido", [
    "desde ayer tiene visión doble", "el niño tiene visión doble desde ayer",
    "pérdida súbita de visión en OD esta mañana", "desde ayer ve destellos",
    "hoy perdió la visión en OD", "hoy dejó de ver con el OD",
])
@pytest.mark.parametrize("negada", [False, True])
def test_ejemplos_informante(contenido, negada):
    frase = "Su esposa refiere que " + ("no " if negada else "") + contenido
    assert bool(activas(motivo=frase)) == (not negada)


@pytest.mark.parametrize("contenido", [
    "su madre tuvo pérdida súbita de visión", "su madre tiene pérdida súbita de visión",
    "su madre padece pérdida súbita de visión", "su madre presentó pérdida súbita de visión",
    "su madre sufrió pérdida súbita de visión", "su madre perdió la visión de repente por glaucoma",
    "antecedente familiar de pérdida súbita de visión", "su padre fue operado de glaucoma",
    "su madre tiene visión doble desde ayer", "su madre tiene destellos desde ayer",
    "su esposa refiere que su madre tiene visión doble desde ayer",
])
@pytest.mark.parametrize("negada", [False, True])
def test_antecedente_del_familiar(contenido, negada):
    frase = ("Niega que " if negada else "") + contenido
    assert not activas(motivo=frase)
    assert not extraer_sintomas(frase)


@pytest.mark.parametrize("motivo", [
    "Su madre informa que tiene diabetes mellitus tipo 2",
    "Su madre padece diabetes mellitus tipo 2",
    "Diabetes mellitus en padre y abuela materna",
    "Madre diabética, padre hipertenso",
    "Antecedente de diabetes en la familia (madre)",
])
def test_diabetes_con_familiar_en_la_clausula_no_se_atribuye_al_paciente(motivo):
    """Decisión de Claude (auditoría VOCAB2): el informante solo reasigna síntomas de alarma.

    Un diagnóstico sistémico en una cláusula con un familiar no se atribuye al paciente:
    escribir «paciente diabético» en su expediente por la diabetes de la madre es un error
    de hecho. Se conserva el comportamiento certificado.
    """
    assert not _has_confirmed_dm(_req(motivo=motivo))
    assert _has_confirmed_dm(_req(motivo="Diabetes mellitus tipo 2 desde hace 8 años"))
