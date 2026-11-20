"""Montaje de tareas sin modificar main para cada función nueva."""
import asyncio
import time
from fastapi import Depends, HTTPException
from app.tareas.nucleo import ContextoEjecucion, CacheTareas, clave_general, metricas
from app.tareas.presupuesto import PresupuestoExcedido
from app.gpu_scheduler import GPUOcupada
from app.tareas.registro import REGISTRO, cargar_definiciones

def montar_rutas(app, registro=None, *, autenticar=None, cliente=None, planificador=None):
    if registro is None:
        cargar_definiciones(); registro = REGISTRO
    if autenticar is None or cliente is None or planificador is None:
        from app import main
        autenticar = autenticar or main.verify_api_key
        cliente = cliente or main.get_http_client
        planificador = planificador or (lambda: main.gpu_scheduler)
    async def tareas(): return registro.tabla()
    async def metricas_http():
        return {n: metricas.tarea(n) for n in registro.tareas}
    app.add_api_route('/v1/tareas', tareas, dependencies=[Depends(autenticar)])
    app.add_api_route('/v1/metricas', metricas_http, dependencies=[Depends(autenticar)])

    def endpoint(tarea):
        f = tarea.ficha
        cache = CacheTareas(f.cache.max_size, f.cache.ttl_seconds) if f.cache else None
        async def ejecutar(req, client=Depends(cliente)):
            inicio = time.monotonic(); estado, motivo = '500', None
            try:
                clave = (tarea.clave_cache(req) if hasattr(tarea, 'clave_cache') else clave_general(tarea, req)) if cache else None
                resultado = cache.get(clave) if cache else None
                if resultado is None:
                    ctx = ContextoEjecucion(tarea, client, planificador(), req)
                    timeout = f.timeout_s() if callable(f.timeout_s) else f.timeout_s
                    try:
                        resultado = await asyncio.wait_for(tarea.ejecutar(req, ctx), timeout)
                    except (PresupuestoExcedido, GPUOcupada, TimeoutError) as exc:
                        motivo = 'presupuesto' if isinstance(exc, PresupuestoExcedido) else 'ia_ocupada' if isinstance(exc, GPUOcupada) else 'ia_timeout'
                        if f.modo_fallo == 'respaldo': resultado = tarea.respaldo(req, motivo)
                        else: raise HTTPException(413 if motivo == 'presupuesto' else 503 if motivo == 'ia_ocupada' else 504, detail='No se pudo ejecutar la tarea.')
                    if cache: cache.put(clave, resultado)
                estado = getattr(resultado, 'estado', '200'); motivo = getattr(resultado, 'motivo', motivo)
                return resultado
            except HTTPException as exc:
                estado = str(exc.status_code); raise
            finally:
                metricas.solicitud(f.nombre, estado, motivo, time.monotonic()-inicio)
        ejecutar.__annotations__['req'] = f.modelo_request
        return ejecutar
    for tarea in registro.tareas.values():
        if tarea.ficha.montaje == 'registro':
            for ruta in tarea.ficha.rutas:
                app.add_api_route(ruta, endpoint(tarea), methods=['POST'], response_model=tarea.ficha.modelo_respuesta,
                                 dependencies=[Depends(autenticar)])
