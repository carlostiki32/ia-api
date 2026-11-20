"""Unidades puras de W1a; proveedor simulado y sin puntos de integración."""
import asyncio
from dataclasses import replace
import json

import pytest

from app.paciente.contexto import construir_contexto, contexto_desde_receta, json_canonico, LENTES
from app.paciente.sintomas import extraer_sintomas
from app.paciente.validador import validar, REGLAS
from app.paciente.ensamblado import ensamblar, respaldo, generada
from app.paciente.servicio import generar, Plazos, RespuestaEtapa
from app.paciente.prompts import formato_redaccion
from app.patient_profile import build_patient_profile
from app.schemas import ImpresionClinicaRequest
from app.tareas.presupuesto import PresupuestoExcedido


def ejecutar_async(fn):
    from functools import wraps
    @wraps(fn)
    def ejecutar(*args, **kwargs):
        return asyncio.run(fn(*args, **kwargs))
    return ejecutar


def receta(esfera=-.25, cilindro=0, add=None, **extra):
    return ImpresionClinicaRequest.model_validate({"receta_id": "w1a", "refraccion": {
        "od": {"esfera": esfera, "cilindro": cilindro, "add": add},
        "oi": {"esfera": esfera, "cilindro": cilindro, "add": add}}, **extra})


def contexto(**extra):
    return contexto_desde_receta(receta(**extra), "Se registra miopía en ambos ojos.", [])


def candidato(texto="La miopía puede hacer que los letreros se vean poco definidos.", fuentes=None):
    return {"frases": [{"texto": texto, "fuentes": fuentes or ["rx.od", "rx.oi"]}]}


@pytest.mark.parametrize("texto,ids", [
    ("Refiere visión borrosa de lejos, cansancio visual y ardor ocular.", ["vision_borrosa_lejos", "fatiga_visual", "ardor"]),
    ("Niega visión borrosa, cansancio visual y ardor ocular.", []),
    ("Sin dolor de cabeza, lagrimeo y comezón.", []),
    ("Niega ardor pero refiere lagrimeo.", ["lagrimeo"]),
    ("Mi madre tiene visión borrosa de cerca y ardor.", []),
    ("Si presenta visión borrosa de cerca, consultar.", []),
    ("Posible visión borrosa de lejos.", []),
    ("Quizás tiene ardor ocular.", []),
    ("Visión borrosa.", ["vision_borrosa"]),
    ("Visión borrosa de cerca.", ["vision_borrosa_cerca"]),
    ("Destellos, moscas volantes, sombras, visión doble y dolor intenso.", ["diplopia"]),
    ("Mi madre tiene ardor; el paciente refiere comezón.", ["comezon"]),
])
def test_sintomas(texto, ids):
    ocurrencias = extraer_sintomas(texto)
    assert [x.sintoma for x in ocurrencias] == ids
    assert all(texto[x.inicio:x.fin] == x.literal for x in ocurrencias)
    assert all(x.sujeto == "paciente" and not x.negado and not x.hipotetico for x in ocurrencias)


@pytest.mark.parametrize("esfera,cilindro,add,nombres,estado", [
    (-.25, 0, None, ["miopía"], "aplicable"), (-8, 0, None, ["miopía"], "aplicable"),
    (0, -1, None, ["astigmatismo"], "aplicable"), (2, 0, None, ["hipermetropía"], "aplicable"),
    (0, 0, 1, [], "aplicable"), (0, 0, None, [], "sin_componentes_refractivos"),
    (None, 0, None, None, "datos_incompletos"),
])
def test_matriz_perfil(esfera, cilindro, add, nombres, estado):
    req = receta(esfera, cilindro, add)
    ctx = contexto_desde_receta(req, "Hallazgo descrito.", [])
    assert ctx.perfil.estado == estado
    assert ctx.contenido("rx.od", {}).get("componentes") == nombres
    assert "presbicia" not in ctx.canonico()


def test_hechos_y_json():
    req = receta(paciente={"motivo_consulta": "Niega ardor, refiere lagrimeo."},
                 tipo_lente="heredado", clinica={"uso_pantallas": "gt6"})
    ctx = contexto_desde_receta(req, "FINAL depurado", [{"nombre": "prueba", "texto": "Hecho"}])
    assert "lente" not in ctx.ids
    assert ctx.contenido("clinico") == "FINAL depurado"
    assert ctx.contenido("motivo")["sintomas_referidos"] == ["lagrimeo"]
    assert not any(x in ctx.ids for x in ("edad", "ocupacion", "akr"))
    assert json.loads(ctx.canonico()) == ctx.como_dict()
    assert formato_redaccion(ctx)["properties"]["frases"]["items"]["properties"]["fuentes"]["items"]["enum"] == list(ctx.ids)
    assert "lejos" not in LENTES["monofocal"] and "cerca" not in LENTES["monofocal"]


@pytest.mark.parametrize("regla,texto", [
    ("tuteo", "TÚ puedes ver mejor."), ("cifras", "Su receta incluye dos dioptrías."),
    ("meta", "La IMPRESIÓN CLÍNICA describe su receta."), ("normalidad", "Su ojo está SANO."),
    ("promesa", "Sus lentes curarán la miopía."), ("magnitud", "Su miopía es LEVE."),
    ("accion_propia", "Acuda con un oftalmólogo."), ("enfermedad", "Puede tener glaucoma."),
    ("sintoma_no_referido", "Usted refiere ardor ocular."),
    ("componente", "La hipermetropía puede dificultar el enfoque."),
    ("modalidad", "La miopía dificulta ver letreros."),
    ("consejo", "Hacer pausas puede ayudarle a descansar."),
    ("lente", "Sus lentes progresivos tienen zonas de enfoque."),
])
def test_rechazo_reglas_normalizadas(regla, texto):
    assert validar(candidato(texto), contexto()) == regla


@pytest.mark.parametrize("mal", [None, {}, {"frases": []}, {"frases": [], "extra": 1},
    {"frases": [{"texto": " ", "fuentes": ["clinico"]}]},
    candidato(fuentes=["inventada"]), candidato(fuentes=["clinico", "clinico"]),
    '{"frases":[],"frases":[]}', '{"frases":', candidato("a" * 321)])
def test_json(mal):
    assert validar(mal, contexto()) == "json"


def test_longitud():
    obj = {"frases": [{"texto": " " .join(["palabra"] * 40), "fuentes": ["clinico"]} for _ in range(4)]}
    assert validar(obj, contexto()) == "longitud"


def test_aceptacion_y_caso_completo():
    ctx = contexto()
    assert validar(candidato(), ctx) is None
    assert validar(candidato("Su receta incluye corrección para miopía."), ctx) is None
    assert validar(candidato("Su ojo derecho incluye corrección para miopía.", ["clinico"]), ctx) is None
    assert validar(candidato("La miopía dificulta ver letreros.", ["clinico"]), ctx) == "modalidad"
    assert validar(candidato(), ctx, done_reason="length") == "json"


def test_descartes_consejos_y_sintomas():
    ctx = construir_contexto(impresion_clinica_final="Estudiar para descartar glaucoma. Se recomiendan pausas.",
        motivo="Ardor ocular.", acciones_obligatorias=[], rx=None)
    assert validar(candidato("Se realiza el estudio para descartar glaucoma.", ["clinico"]), ctx) is None
    assert validar(candidato("Puede hacer pausas.", ["clinico"]), ctx) is None
    assert validar(candidato("Usted refiere ardor ocular.", ["motivo"]), ctx) is None
    assert validar(candidato("Se realiza el estudio para descartar catarata.", ["clinico"]), ctx) == "enfermedad"


def test_lateralidad_anisometropia():
    req = receta()
    req.refraccion.oi.esfera = 2
    ctx = contexto_desde_receta(req, "Refracción registrada.", [])
    assert validar(candidato("Miopía en el ojo derecho e hipermetropía en el ojo izquierdo."), ctx) is None
    assert validar(candidato("Miopía en el ojo izquierdo."), ctx) == "componente"


def test_ensamblado_limite_unicode():
    assert ensamblar(["Acción."], "Prosa.") == "Acción.\n\nProsa."
    assert len(ensamblar(["😀" * 1997], "a")) == 2000
    with pytest.raises(ValueError): ensamblar(["😀" * 1998], "a")
    ctx = contexto()
    r = respaldo(ctx, "timeout")
    assert (r.estado, r.origen) == ("plantilla", "plantilla")
    assert len(r.texto) <= 2000
    for s in ("datos_incompletos", "sin_componentes_refractivos"):
        perfil = replace(ctx.perfil, estado=s)
        nuevo = replace(ctx, perfil=perfil)
        assert respaldo(nuevo, "error").texto is None
        assert generada(nuevo, candidato("Se describe un hallazgo.", ["clinico"])).estado == "generada"
    con_accion = construir_contexto(impresion_clinica_final="Hallazgo.", acciones_obligatorias=["Acuda hoy."], perfil=replace(ctx.perfil, estado="datos_incompletos"))
    assert respaldo(con_accion, "error").texto == "Acuda hoy."


@ejecutar_async
async def test_servicio_exito():
    llamadas = []
    async def proveedor(llamada):
        llamadas.append(llamada)
        return candidato() if llamada.etapa == "redaccion" else {"valido": True}
    r = await generar(contexto(), proveedor, llegada=0, reloj=lambda: 0,
                      comprobar_presupuesto=lambda *a, **k: None)
    assert (r.estado, r.origen, r.motivo) == ("generada", "llm", None)
    assert [l.etapa for l in llamadas] == ["redaccion", "verificacion"]
    assert all(l.politica == "estricto" and not l.think and l.max_retries == 1 for l in llamadas)


@ejecutar_async
@pytest.mark.parametrize("motivo", ["validacion", "verificacion", "abstencion", "timeout", "presupuesto", "ocupado", "error"])
async def test_motivos(motivo):
    llamadas = []
    async def proveedor(l):
        llamadas.append(l.etapa)
        if motivo == "error": raise RuntimeError("simulado")
        if motivo == "timeout": raise TimeoutError
        if l.etapa == "verificacion": return {"valido": False}
        return {"frases": []} if motivo == "abstencion" else candidato("Tu receta.") if motivo == "validacion" else candidato()
    def presupuesto(*args, **kwargs):
        assert kwargs["politica"] == "estricto"
        if motivo == "presupuesto": raise PresupuestoExcedido()
    r = await generar(contexto(), proveedor, llegada=0, reloj=lambda: 0,
        hay_interactiva_esperando=lambda: motivo == "ocupado", comprobar_presupuesto=presupuesto)
    assert r.motivo == motivo
    assert r.estado == "plantilla"
    if motivo in ("ocupado", "presupuesto"): assert not llamadas


@ejecutar_async
@pytest.mark.parametrize("etapa", ["redaccion", "verificacion"])
async def test_timeout_cancelacion_efectiva(etapa):
    canceladas = []
    async def proveedor(l):
        if l.etapa != etapa: return candidato()
        try: await asyncio.Event().wait()
        finally: canceladas.append(l.etapa)
    p = Plazos(redaccion=.02, verificacion=.02, minimo_redaccion=.001, minimo_verificacion=.001)
    r = await generar(contexto(), proveedor, llegada=0, reloj=lambda: 0, plazos=p, comprobar_presupuesto=lambda *a, **k: None)
    assert r.motivo == "timeout" and canceladas == [etapa]


@ejecutar_async
async def test_ventana_y_carga_antes_verificar():
    async def proveedor(l): return candidato()
    r = await generar(contexto(), proveedor, llegada=0, reloj=lambda: 84.8, comprobar_presupuesto=lambda *a, **k: None)
    assert r.motivo == "timeout"
    carga = iter((False, True))
    r = await generar(contexto(), proveedor, llegada=0, reloj=lambda: 0, hay_interactiva_esperando=lambda: next(carga), comprobar_presupuesto=lambda *a, **k: None)
    assert r.motivo == "ocupado"


@ejecutar_async
@pytest.mark.parametrize("valor", [{"valido": 1}, {"valido": "true"}, {"valido": True, "extra": False}, "{", RespuestaEtapa('{"valido":true}', "length")])
async def test_verificador_estricto(valor):
    async def proveedor(l): return candidato() if l.etapa == "redaccion" else valor
    r = await generar(contexto(), proveedor, llegada=0, reloj=lambda: 0, comprobar_presupuesto=lambda *a, **k: None)
    assert r.motivo == "verificacion"


@ejecutar_async
async def test_nunca_escapa_error_dependencias():
    def falla(): raise RuntimeError
    async def proveedor(l): raise asyncio.CancelledError
    for kwargs in ({"reloj": falla}, {"hay_interactiva_esperando": falla}, {}):
        r = await generar(contexto(), proveedor, llegada=0, comprobar_presupuesto=lambda *a, **k: None, **kwargs)
        assert r.motivo in ("error", "timeout")


@pytest.mark.parametrize("texto,regla", [
    ("Usted nota ardor ocular.", "sintoma_no_referido"),
    ("Usted experimenta dolor de cabeza.", "sintoma_no_referido"),
    ("Los ojos son saludables.", "normalidad"),
    ("Sus lentes curan el astigmatismo.", "promesa"),
    ("Puede tener catarata.", "enfermedad"),
    ("Su ojo izquierdo tiene hipermetropía.", "componente"),
    ("La miopía puede dificultar la visión y la miopía produce desenfoque.", "modalidad"),
    ("Texto\u200b oculto.", "meta"),
    ("Se realizó una CORRELACIÓN para redactarlo.", "meta"),
])
def test_rechazos_adicionales(texto, regla):
    assert validar(candidato(texto), contexto()) == regla


def test_consejo_negado_no_autoriza():
    ctx = construir_contexto(impresion_clinica_final="No se recomiendan gotas.")
    assert validar(candidato("Puede aplicar gotas.", ["clinico"]), ctx) == "consejo"


def test_distancia_ambigua_no_atribuida():
    assert extraer_sintomas("Visión borrosa de cerca o lejos.") == ()


@ejecutar_async
async def test_prosa_excede_ensamblado_y_respaldo_cabe():
    ctx = construir_contexto(impresion_clinica_final="Hallazgo registrado.", acciones_obligatorias=["A" * 1800], perfil=contexto().perfil)
    async def proveedor(l):
        return candidato("Se describe un hallazgo que puede estudiarse. " * 6, ["clinico"]) if l.etapa == "redaccion" else {"valido": True}
    r = await generar(ctx, proveedor, llegada=0, reloj=lambda: 0, comprobar_presupuesto=lambda *a, **k: None)
    assert (r.estado, r.motivo, r.regla, len(r.texto)) == ("plantilla", "validacion", "longitud", 1800)


@ejecutar_async
async def test_proveedor_incompleto():
    async def proveedor(l): return candidato(), {"done": False}
    r = await generar(contexto(), proveedor, llegada=0, reloj=lambda: 0, comprobar_presupuesto=lambda *a, **k: None)
    assert r.motivo == "validacion" and r.regla == "json"


@ejecutar_async
async def test_acciones_imposibles_no_escapan():
    ctx = construir_contexto(impresion_clinica_final="Hallazgo.", acciones_obligatorias=["A" * 2001])
    async def proveedor(l): raise RuntimeError
    r = await generar(ctx, proveedor, llegada=0, reloj=lambda: 0, comprobar_presupuesto=lambda *a, **k: None)
    assert r.texto is None and r.motivo == "error"


@ejecutar_async
async def test_no_llama_si_presupuesto_consume_ventana():
    hora = [0.0]
    llamadas = []
    def presupuesto(*a, **k): hora[0] = 84.9
    async def proveedor(l): llamadas.append(l.etapa)
    r = await generar(contexto(), proveedor, llegada=0, reloj=lambda: hora[0], comprobar_presupuesto=presupuesto)
    assert r.motivo == "timeout" and not llamadas


@pytest.mark.parametrize("texto", ["Texto \ud800 inválido.", "Vea ftp://optica.ejemplo.com", "Escriba a mailto:optica@ejemplo.com"])
def test_controles_y_enlaces(texto):
    assert validar(candidato(texto), contexto()) == "meta"


@pytest.mark.parametrize("texto", ["Tiene síndrome de Horner.", "Puede tener ectasia.", "Presenta oclusión venosa retiniana."])
def test_enfermedades_de_correlaciones(texto):
    assert validar(candidato(texto), contexto()) == "enfermedad"
