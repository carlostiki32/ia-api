"""Regresión W1c: explicaciones válidas y usos atribuidos al tipo monofocal."""
import pytest

from app.paciente.contexto import contexto_desde_receta
from app.paciente.validador import validar
from app.schemas import ImpresionClinicaRequest


CASOS = {
    "miopia": {
        "od": {"esfera": -2.00, "cilindro": 0, "av_cc": "20/20"},
        "oi": {"esfera": -1.75, "cilindro": 0, "av_cc": "20/20"},
        "motivo": "Visión borrosa de lejos.",
        "clinico": "El paciente acude por visión borrosa de lejos. Presenta miopía en ambos ojos con agudeza visual corregida de 20/20.",
        "frases": [
            "La miopía puede hacer que los letreros o los rostros lejanos se vean borrosos.",
            "Sus lentes le ayudan a ver con más claridad los letreros lejanos.",
            "Usted refiere visión borrosa de lejos; sus lentes corrigen la miopía de cada ojo para que vea más nítido.",
            "Con sus lentes puede distinguir mejor los objetos lejanos, como los letreros de la calle o el pizarrón.",
            "Al manejar de noche, la miopía puede hacer que las señales se vean menos definidas; sus lentes le ayudarán.",
            "Su graduación corrige la miopía en ambos ojos.",
            "Sus lentes tienen una sola graduación en toda su superficie.",
            "La miopía puede hacer que los letreros o los rostros lejanos se vean poco definidos; sus lentes llevan la corrección de cada ojo.",
        ],
    },
    "astigmatismo": {
        "od": {"esfera": -0.50, "cilindro": -1.25},
        "oi": {"esfera": -0.25, "cilindro": -1.00},
        "motivo": "Cansancio visual al leer.",
        "clinico": "Refracción registrada.",
        "frases": [
            "El astigmatismo puede hacer que las letras o los bordes se vean poco definidos, de cerca o de lejos.",
            "Usted refiere cansancio visual al leer; el astigmatismo puede contribuir a ese esfuerzo.",
            "Sus lentes corrigen el astigmatismo de cada ojo para que las letras se vean más nítidas.",
        ],
    },
    "presbicia": {
        "od": {"esfera": 0.00, "cilindro": 0, "add": 1.50},
        "oi": {"esfera": 0.00, "cilindro": 0, "add": 1.50},
        "lente": "progresivo",
        "motivo": "No alcanza a leer el celular.",
        "clinico": "Refracción registrada.",
        "frases": [
            "Su receta incluye un apoyo para enfocar de cerca, como al leer el celular o un libro.",
            "Usted refiere que no alcanza a leer el celular; el apoyo de cerca de su receta le ayuda a enfocar a esa distancia.",
            "Sus lentes progresivos cambian poco a poco de graduación para ver de lejos, a media distancia y de cerca.",
            "De lejos su receta no lleva corrección; el apoyo es para la visión cercana.",
        ],
    },
    "hipermetropia": {
        "od": {"esfera": 1.50, "cilindro": 0},
        "oi": {"esfera": 1.25, "cilindro": 0},
        "motivo": "Dolor de cabeza al usar la computadora.",
        "clinico": "Refracción registrada.",
        "clinica": {"uso_pantallas": "gt6"},
        "frases": [
            "La hipermetropía puede hacer más difícil enfocar de cerca, por ejemplo al leer o usar la computadora.",
            "Usted refiere dolor de cabeza al usar la computadora; la hipermetropía puede aumentar el esfuerzo para enfocar.",
            "Sus lentes pueden ayudarle a enfocar con menos esfuerzo al leer o trabajar en pantallas.",
        ],
    },
}


def contexto_caso(nombre):
    caso = CASOS[nombre]
    receta = ImpresionClinicaRequest.model_validate({
        "receta_id": "w1c",
        "refraccion": {"od": caso["od"], "oi": caso["oi"]},
        "paciente": {"motivo_consulta": caso["motivo"]},
        "tipo_lente": caso.get("lente", "monofocal"),
        "clinica": caso.get("clinica", {}),
    })
    return contexto_desde_receta(receta, caso["clinico"], [])


def candidato(texto):
    return {"frases": [{"texto": texto, "fuentes": ["rx.od", "rx.oi", "lente"]}]}


@pytest.mark.parametrize("nombre,texto", [
    pytest.param(nombre, texto, id=f"{nombre}-{indice}")
    for nombre, caso in CASOS.items()
    for indice, texto in enumerate(caso["frases"], 1)
])
def test_frases_correctas_en_contexto_real(nombre, texto):
    assert validar(candidato(texto), contexto_caso(nombre)) is None


@pytest.mark.parametrize("texto", [
    "Sus lentes monofocales le ayudan a ver de lejos.",
    "Sus anteojos monofocales le ayudan a ver de cerca.",
    "Su lente monofocal es para lectura.",
])
def test_tipo_monofocal_no_autoriza_distancia(texto):
    assert validar(candidato(texto), contexto_caso("miopia")) == "lente"
