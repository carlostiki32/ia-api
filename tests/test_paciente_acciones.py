"""Cobertura de ramas ejecutables y deriva del catálogo de acciones."""
import json
from pathlib import Path
import pytest
from app.paciente.acciones import extraer_acciones, CATALOGO, BINOCULARES
from tests.paciente_inventario import inventario, expandir_consumidores

INVENTARIO = json.loads(Path("tests/fixtures/paciente_inventario_acciones.json").read_text(encoding="utf-8"))


def test_no_hay_nuevas_ramas_sin_catalogar():
    actuales = expandir_consumidores(inventario(), BINOCULARES)
    assert actuales == [{k: v for k, v in x.items() if k != "variantes"} for x in INVENTARIO], "Cambió una variante ejecutable: revisar acción y actualizar inventario explícitamente"


@pytest.mark.parametrize("variante", INVENTARIO, ids=lambda x: x["correlacion"] + "/" + x["funcion"])
def test_toda_variante_ejecutable_tiene_mapeo(variante):
    acciones = extraer_acciones([{"nombre": variante["correlacion"], "texto": variante["texto"]}])
    assert acciones and all(a.mapeada for a in acciones), variante
    assert [a.variante for a in acciones] == variante["variantes"], "Cambió el procedimiento o prioridad de una rama"
    assert all(a.destino or a.procedimiento != "consulta" for a in acciones)
    assert all(a.texto.endswith(".") for a in acciones)


def test_tabla_sin_ids_duplicados():
    ids = [(v.accion.correlacion, v.accion.variante) for v in CATALOGO]
    assert len(set(ids)) == len(ids)


def test_procedimientos_plazos_y_alternativa():
    a = extraer_acciones([{"nombre": "sintomas_alarma_traccion_vitreoretina", "texto":
        "Hallazgo urgente: exploracion de retina periferica bajo midriasis con oftalmoscopia indirecta, idealmente con indentacion escleral, en un plazo maximo de 48 horas, o referencia a oftalmologia si no puede realizarse en consulta."}])[0]
    assert a.plazo == "en un plazo máximo de 48 horas"
    assert "dilatadas" in a.procedimiento and "revisión" in a.procedimiento
    assert "si no puede" in a.alternativas
    a = extraer_acciones([{"nombre": "fondo_macular_dmae", "texto":
        "Hallazgo urgente: derivacion prioritaria a retina gestionada en un plazo maximo de 1 dia habil para OCT macular y valoracion de tratamiento."}])[0]
    assert a.procedimiento == "gestionar la derivación"
    assert a.plazo == "en un plazo máximo de un día hábil"
    assert "tratamiento" in a.texto


def test_condicion_y_dos_acciones():
    acciones = extraer_acciones([{"nombre": "fondo_oclusion_vascular_urgente", "texto":
        "Hallazgo urgente: sin tipificar, hallazgo que amerita valoracion oftalmologica el mismo dia y, si la perdida visual es subita y de horas de evolucion, derivacion inmediata a urgencias con atencion de evento vascular cerebral."}])
    assert "hoy mismo" in acciones[0].texto
    assert "si la pérdida visual" in acciones[0].texto
    acciones = extraer_acciones([{"nombre": "fondo_vascular_diabetico", "texto":
        "valoracion retinologica preferente y evaluacion medica sistemica, incluida la glucemia y presion arterial."}])
    assert len(acciones) == 2


@pytest.mark.parametrize("texto,palabras", [
    ("Hallazgo urgente: requiere valoracion urgente", ["de inmediato", "optometrista"]),
    ("valoracion oftalmologica en 72 horas", ["oftalmólogo", "72 horas"]),
    ("valoracion retinologica urgente para exploracion bajo midriasis", ["retina", "dilatadas"]),
    ("valoracion especializada", ["optometrista"]),
])
def test_desconocidas(texto, palabras, caplog):
    a = extraer_acciones([{"nombre": "futura", "texto": texto}])[0]
    assert not a.mapeada and all(p in a.texto for p in palabras)
    assert "lo antes posible" not in a.texto
    assert texto not in caplog.text


def test_no_interpreta_normalidad_como_derivacion():
    assert not extraer_acciones([{"nombre": "sin_accion", "texto": "Se documenta un hallazgo."}])



def test_32_sitios_urgentes_en_18_constructores():
    import ast
    sitios = []
    for p in Path("app/correlaciones").glob("*.py"):
        tree = ast.parse(p.read_text(encoding="utf-8"))
        padres = {hijo: padre for padre in ast.walk(tree) for hijo in ast.iter_child_nodes(padre)}
        for n in ast.walk(tree):
            if isinstance(n, ast.Constant) and isinstance(n.value, str) and "Hallazgo urgente:" in n.value:
                padre = n
                while padre in padres and not isinstance(padre, ast.FunctionDef): padre = padres[padre]
                sitios.append((p.name, padre.name))
    assert len(sitios) == 32, "Revisar catálogo al agregar o retirar una rama urgente"
    assert len(set(sitios)) == 18
    assert {fn for _, fn in sitios} <= {x["funcion"] for x in INVENTARIO}



def test_cada_entrada_del_catalogo_tiene_una_rama_origen():
    ejercidas = {(x["correlacion"], v) for x in INVENTARIO for v in x["variantes"]}
    assert {(v.accion.correlacion, v.accion.variante) for v in CATALOGO} <= ejercidas
