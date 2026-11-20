from app.config import settings
from app.seguimiento import servicio
from app.seguimiento.catalogo import PROMPT_VERSION, VERIFICACION_VERSION
from app.seguimiento.schemas import SeguimientoWhatsappRequest, SeguimientoWhatsappResponse
from app.seguimiento.uso import USO_VERSION
from app.tareas.nucleo import FichaTarea, LlamadaLLM


class SeguimientoWhatsapp:
    ficha = FichaTarea(nombre='seguimiento-whatsapp', version='1', descripcion='Recordatorio de seguimiento',
        rutas=('/v1/inferencia/seguimiento-whatsapp',), prioridad='fondo',
        modelo_request=SeguimientoWhatsappRequest, modelo_respuesta=SeguimientoWhatsappResponse,
        modo_fallo='respaldo', timeout_s=lambda: settings.seguimiento_timeout,
        llamadas=(LlamadaLLM('uso', USO_VERSION, 'json-schema',
                    lambda req: servicio.opciones_generacion(req, uso=True), lambda: 32, 6000),
                  LlamadaLLM('redaccion', PROMPT_VERSION, 'json-schema', servicio.opciones_generacion,
                    lambda: settings.seguimiento_num_predict, 7400),
                  LlamadaLLM('verificacion', VERIFICACION_VERSION, 'json-schema',
                    lambda req: servicio.opciones_generacion(req, verificacion=True), lambda: settings.verificacion_num_predict, 3000)),
        respaldo='Plantilla determinista del catálogo ante cualquier fallo.')

    async def ejecutar(self, req, ctx):
        return await servicio.generar(req, ctx.client, ctx.planificador, ctx)

    def respaldo(self, req, motivo): return servicio.respaldo(req, motivo=motivo)


tarea = SeguimientoWhatsapp()
