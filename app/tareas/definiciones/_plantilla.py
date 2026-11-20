"""Copiar y registrar en app/tareas/registro.py, función cargar_definiciones; este módulo NO se registra."""
from pydantic import BaseModel
from app.providers.ollama import build_options
from app.tareas.nucleo import FichaTarea, LlamadaLLM

class RequestEjemplo(BaseModel):
    texto: str

class TareaEjemplo:
    ficha = FichaTarea(
        nombre='ejemplo', version='1', descripcion='Completar descripcion',
        rutas=('/v1/inferencia/ejemplo',), prioridad='fondo',
        modelo_request=RequestEjemplo, modo_fallo='http', timeout_s=30,
        llamadas=(LlamadaLLM('generar', 'ejemplo-v1', 'texto',
            lambda req: {**build_options(), 'num_predict':128}, lambda:128, 2000),))

    async def ejecutar(self, req, ctx):
        # System estable; validar siempre la respuesta antes de devolverla.
        texto, _ = await ctx.llamar('generar', 'Resume el texto recibido.', req.texto)
        return {'texto': texto}

# Crear tarea = TareaEjemplo() en el modulo copiado y registrar explicitamente.
# Probar maximos, presupuesto, prioridad, metricas y respaldo antes de habilitar.
