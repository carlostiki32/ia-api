"""VOCAB: equivalencia léxica, negación vigente y consumidores reales offline."""
import unicodedata

import pytest

from app.correlaciones.binocularidad import _episodios_visuales, _sintomas_visuales_actuales
from app.correlaciones.fondo_de_ojo import (
    _embolo_sintomas, _vascular_sintomas_oculares_actuales,
)
from app.correlaciones.motilidad import _sintomas_del_motivo
from app.correlaciones.pupilas_motilidad import _ocurrencias_oculares, _SINTOMAS_EPISODIO
from app.correlaciones.segmento_anterior import _sintomas_segmento
from app.correlaciones.texto import _normalize_text
from app.correlaciones.vocabulario import perdidas_subitas
from app.paciente.sintomas import extraer_sintomas
from tests.test_auditoria_correlaciones import _req, activas

DIPLOPIAS = [
    "viendo doble", "ve doble", "veía doble", "ver doble", "vio doble",
    "ha visto doble", "doble visión", "imagen doble", "imágenes dobles",
    "veo doble", "vi doble", "he visto doble",
]
PERDIDAS = [
    "perdió la visión", "perdió la vista", "pierde la visión", "pierde la vista",
    "perdiendo la visión", "perdiendo la vista", "ha perdido la visión",
    "ha perdido la vista", "dejó de ver", "pérdida de la vista",
    "perdí la visión", "perdí la vista", "pierdo la visión", "pierdo la vista",
    "he perdido la visión", "he perdido la vista", "dejé de ver",
]
SOMBRAS = [
    "sombra en la visión", "sombra en el campo visual", "sombra en {ojo}",
    "ve una sombra", "sombra en el ojo", "sombra sobre la visión",
    "sombra en la vista", "veo una sombra", "sombras en la visión",
]
BRUSQUEDAD = [
    "súbita", "súbitamente", "repentina", "repentinamente", "de repente",
    "de golpe", "brusca", "bruscamente", "de un momento a otro",
]
TIEMPOS = ["desde ayer", "hoy", "anoche", "hace 2 horas", "hace tres días", "esta mañana"]
FORMAS = [("diplopia", f) for f in DIPLOPIAS] + [
    ("perdida_visual", f) for f in PERDIDAS
] + [("sombra_cortina", f) for f in SOMBRAS]


def variante(texto, estilo):
    if estilo == "sin_acentos":
        return "".join(c for c in unicodedata.normalize("NFD", texto)
                       if not unicodedata.combining(c))
    return texto.upper() if estilo == "mayusculas" else texto


@pytest.mark.parametrize("concepto,forma", FORMAS)
@pytest.mark.parametrize("estilo,ojo", [("original", "OD"), ("sin_acentos", "OI"), ("mayusculas", "AO")])
@pytest.mark.parametrize("contexto", ["afirmada", "negada", "lista", "lista_negada", "tiempo"])
def test_vocab_forma_en_correlaciones_y_sintomas(concepto, forma, estilo, ojo, contexto):
    forma = forma.format(ojo=ojo)
    # La diplopia exige cronología para activar su correlación independiente.
    # La pérdida sin brusquedad se prueba como síntoma, sin crear alarma nueva.
    fecha = " desde ayer" if concepto == "diplopia" or contexto == "tiempo" else ""
    afirmada = contexto not in ("negada", "lista_negada")
    frase = forma + f" en {ojo}" + fecha
    if contexto == "negada":
        frase = "Niega " + frase
    elif contexto == "lista_negada":
        # Sin tiempo: el contrato vigente lo considera apertura tras una coma.
        frase = f"Niega {forma} en {ojo}, cefalea ni ardor ocular."
    elif contexto == "lista":
        frase = f"Refiere {frase}, cefalea y ardor ocular."
    frase = variante(frase, estilo)
    req = _req(motivo=frase)
    referidos = extraer_sintomas(frase)
    assert any(s.sintoma == concepto for s in referidos) == afirmada
    for s in referidos:
        assert frase[s.inicio:s.fin] == s.literal
    nombres = activas(motivo=frase)
    if concepto == "sombra_cortina":
        assert ("sintomas_alarma_traccion_vitreoretina" in nombres) == afirmada
        if afirmada:
            assert nombres["sintomas_alarma_traccion_vitreoretina"] == activas(motivo="cortina en la visión")["sintomas_alarma_traccion_vitreoretina"]
    else:
        etiqueta = "diplopia" if concepto == "diplopia" else "perdida visual"
        for hechos, buscada in (
            (_episodios_visuales(req), etiqueta),
            (_sintomas_del_motivo(req), "diplopia referida" if concepto == "diplopia" else "disminucion visual referida"),
            (_sintomas_segmento(req), "sintoma|diplopia" if concepto == "diplopia" else "sintoma|perdida o disminucion visual"),
            (_ocurrencias_oculares(frase, _SINTOMAS_EPISODIO, "motivo_consulta"), etiqueta + " referida"),
        ):
            assert any(h.afirmado and h.hallazgo == buscada for h in hechos) == afirmada, (frase, buscada, hechos)
        assert bool(_sintomas_visuales_actuales(req, binocular=False)) == afirmada
        if concepto == "diplopia":
            assert ("diplopia_aguda" in nombres) == afirmada
            if afirmada:
                assert nombres["diplopia_aguda"] == activas(motivo=f"diplopia en {ojo} desde ayer")["diplopia_aguda"]
        else:
            assert ("sintomas_alarma_traccion_vitreoretina" in nombres) == (afirmada and contexto == "tiempo")


@pytest.mark.parametrize("forma", PERDIDAS + ["pérdida de visión", "pérdida visual"])
@pytest.mark.parametrize("marcador", BRUSQUEDAD)
@pytest.mark.parametrize("posicion", ["antes", "despues"])
def test_vocab_perdida_subita_todos_los_marcadores(forma, marcador, posicion):
    frase = f"{marcador} {forma} en OD" if posicion == "antes" else f"{forma} en OD {marcador}"
    frase = variante(frase, "sin_acentos") if posicion == "antes" else frase.upper()
    nombre = "sintomas_alarma_traccion_vitreoretina"
    assert activas(motivo=frase)[nombre] == activas(motivo="pérdida súbita de visión")[nombre]
    assert list(perdidas_subitas(_normalize_text(frase)))
    assert any(s.evolucion == "cambio reciente" for s in _episodios_visuales(_req(motivo=frase)))
    assert _vascular_sintomas_oculares_actuales(_normalize_text(frase))
    assert _embolo_sintomas(_req(motivo=frase))["visuales"]
    assert nombre not in activas(motivo="Niega " + frase)
    assert not list(perdidas_subitas(_normalize_text("Niega " + frase)))


@pytest.mark.parametrize("forma", PERDIDAS)
@pytest.mark.parametrize("tiempo", TIEMPOS)
def test_vocab_perdida_reciente_accede_a_ruta_subita(forma, tiempo):
    frase = f"{forma} en OI {tiempo}"
    assert extraer_sintomas(frase)[0].sintoma == "perdida_visual"
    assert list(perdidas_subitas(_normalize_text(frase)))
    assert "sintomas_alarma_traccion_vitreoretina" in activas(motivo=frase)


@pytest.mark.parametrize("frase", [
    "Niega ver doble", "No ha perdido la visión", "Sin sombras ni destellos",
    "Niega viendo doble, destellos ni cortinas",
    "Niega súbitamente perdió la visión, destellos ni cortinas",
])
def test_vocab_negaciones_requeridas(frase):
    assert not activas(motivo=frase)
    assert not extraer_sintomas(frase)


@pytest.mark.parametrize("frase", [
    "perdió la visión. De golpe le duele la cabeza",
    "de repente cefalea; perdió la vista", "de golpe cefalea\nperdió la vista",
    "súbitamente cefalea | perdió la visión", "súbitamente cefalea pero perdió la vista",
])
def test_vocab_brusquedad_no_se_presta_de_otra_clausula(frase):
    assert not list(perdidas_subitas(_normalize_text(frase)))
    assert "sintomas_alarma_traccion_vitreoretina" not in activas(motivo=frase)


@pytest.mark.parametrize("forma", DIPLOPIAS)
def test_vocab_diplopia_papilar_y_motora(forma):
    assert activas(fondo="Papilas con bordes borrosos en OD", motivo=forma + " desde ayer")["papila_patologica"].startswith("Hallazgo urgente:")
    resultado = activas(motilidad="Limitación de ducciones OD", motivo=forma + " en OD desde ayer")
    assert resultado["motilidad_alterada"].startswith("Hallazgo urgente:")


@pytest.mark.parametrize("motivo,debe", [
    ("Sin antecedentes familiares de glaucoma, refiere sombra en la visión de OD.", True),
    ("Mi madre refiere sombra en la visión de OD.", True),
    ("Antecedente familiar de sombra en el campo visual.", False),
])
def test_vocab_reporte_del_paciente_tras_antecedente_familiar(motivo, debe):
    assert bool(activas(motivo=motivo)) == debe
    assert bool(extraer_sintomas(motivo)) == debe


@pytest.mark.parametrize("forma", DIPLOPIAS)
def test_vocab_vinculo_ocular_torticolis(forma):
    assert "motilidad_alterada" in activas(motilidad="Tortícolis con " + forma)
    assert "motilidad_alterada" not in activas(motilidad="Tortícolis sin " + forma)


def test_vocab_alias_mas_largo_no_retira_deteccion_previa():
    resultado = activas(motivo="Perdida visual subita: negativo.", pantallas="gt6",
                       cover="OD: Exo y Foria | OI: Exo y Foria", ppc=12)
    assert {"ppc_exoforia", "cover_exoforia_sintomatica", "cvs_sospecha"} <= resultado.keys()
