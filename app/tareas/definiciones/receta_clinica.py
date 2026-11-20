"""Ficha descriptiva: el handler certificado permanece en main.py."""
from types import SimpleNamespace
from app.config import settings
from app.providers.ollama import build_options
from app.schemas import ImpresionClinicaRequest
from app.tareas.nucleo import FichaTarea, LlamadaLLM

tarea = SimpleNamespace(ficha=FichaTarea(
    nombre='receta-clinica', version='1', descripcion='Impresión clínica',
    rutas=('/inferencia/impresion-clinica', '/v1/inferencia/receta-clinica'), prioridad='interactiva',
    modelo_request=ImpresionClinicaRequest, montaje='manual',
    sin_conteo_exacto=settings.presupuesto_receta_sin_exacto,
    llamadas=(LlamadaLLM('clinica','clinica-v1','texto', lambda req: build_options(), lambda: settings.ollama_num_predict, 6200),),
    respaldo='Avisos urgentes deterministas si existen; en otro caso error HTTP.'))
