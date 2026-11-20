"""Hija de receta: corre en el turno de su padre, sin endpoint independiente."""
from types import SimpleNamespace
from app.schemas import ImpresionClinicaRequest
from app.providers.ollama import build_options
from app.paciente.prompts import opciones, PROMPT_VERSION, VERIFICADOR_VERSION
from app.paciente.servicio import VERSION, MAX_TOKENS_ENTRADA
from app.tareas.nucleo import FichaTarea, LlamadaLLM

tarea = SimpleNamespace(ficha=FichaTarea(nombre="explicacion-paciente", version=VERSION,
    descripcion="Explicación de graduación y hallazgos en lenguaje cotidiano",
    rutas=("/inferencia/impresion-clinica", "/v1/inferencia/receta-clinica"),
    prioridad="interactiva", padre="receta-clinica", montaje="manual",
    modelo_request=ImpresionClinicaRequest, modo_fallo="respaldo",
    llamadas=tuple(LlamadaLLM(e, v, "json-schema",
        lambda req, e=e: {**build_options(), **opciones(e)},
        lambda e=e: opciones(e)["num_predict"], MAX_TOKENS_ENTRADA[e])
        for e, v in (("redaccion", PROMPT_VERSION), ("verificacion", VERIFICADOR_VERSION))),
    respaldo="Acciones obligatorias y plantilla CPU; conserva el clínico final."))
