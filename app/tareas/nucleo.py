"""Contratos, ejecución, caché y métricas sin contenido."""
from collections import OrderedDict, Counter
from contextlib import asynccontextmanager
from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
import threading
import time
from app.config import settings
from app.tareas.presupuesto import verificar, politica_actual

@dataclass(frozen=True)
class LlamadaLLM:
    etapa: str
    prompt_version: str
    formato: str
    opciones: object
    num_predict: object
    max_tokens_entrada: object

    def entrada(self):
        return self.max_tokens_entrada() if callable(self.max_tokens_entrada) else self.max_tokens_entrada

@dataclass(frozen=True)
class PoliticaCache:
    max_size: int = 500
    ttl_seconds: int = 86400

@dataclass(frozen=True)
class FichaTarea:
    nombre: str
    version: str
    descripcion: str
    rutas: tuple
    prioridad: str
    modelo_request: object
    modelo_respuesta: object = None
    llamadas: tuple = ()
    timeout_s: object = 120
    modo_fallo: str = 'http'
    cache: object = None
    respaldo: str = ''
    montaje: str = 'registro'
    sin_conteo_exacto: str = 'estricto'
    padre: str | None = None

    def __post_init__(self):
        import re
        if not re.fullmatch(r'[a-z][a-z0-9]*(?:-[a-z0-9]+)*', self.nombre):
            raise ValueError('Nombre inválido')
        if self.prioridad not in ('cpu', 'fondo', 'interactiva') or self.montaje not in ('registro', 'manual') or self.modo_fallo not in ('http', 'respaldo') or self.sin_conteo_exacto not in ('estricto', 'conservador'):
            raise ValueError('Ficha inválida')
        if self.sin_conteo_exacto == 'conservador' and self.nombre != 'receta-clinica':
            raise ValueError('Conservador reservado a receta')
        if self.prioridad == 'cpu' and self.llamadas:
            raise ValueError('CPU no puede declarar llamadas')
        if len({l.etapa for l in self.llamadas}) != len(self.llamadas):
            raise ValueError('Etapa duplicada')

class Metricas:
    def __init__(self):
        self.datos = {}

    def tarea(self, nombre):
        return self.datos.setdefault(nombre, dict(solicitudes=0, estados=Counter(), motivos=Counter(), gpu_ocupada=0,
            presupuesto_excedido=0, latencia_suma=0., latencia_max=0., etapas={}))

    def solicitud(self, nombre, estado, motivo, duracion):
        m = self.tarea(nombre); m['solicitudes'] += 1; m['estados'][str(estado)] += 1
        if motivo: m['motivos'][motivo] += 1
        m['gpu_ocupada'] += motivo == 'ia_ocupada'; m['presupuesto_excedido'] += motivo == 'presupuesto'
        m['latencia_suma'] += duracion; m['latencia_max'] = max(m['latencia_max'], duracion)

    def llamada(self, nombre, etapa, cota, datos):
        m = self.tarea(nombre)['etapas'].setdefault(etapa, dict(llamadas=0, entrada_suma=0, entrada_max=0, salida_suma=0, salida_max=0, cota_max=0))
        m['llamadas'] += 1; m['cota_max'] = max(cota, m['cota_max'])
        for clave, campo in [('entrada','prompt_eval_count'), ('salida','eval_count')]:
            n = datos.get(campo, 0); m[clave+'_suma'] += n; m[clave+'_max'] = max(n, m[clave+'_max'])
        # Nanosegundos, como en la respuesta de Ollama; nunca contenido.
        for campo in ('load_duration', 'prompt_eval_duration', 'eval_duration', 'total_duration'):
            n = datos.get(campo) or 0
            m[campo+'_suma'] = m.get(campo+'_suma', 0) + n
            m[campo+'_max'] = max(n, m.get(campo+'_max', 0))

metricas = Metricas()

class ContextoEjecucion:
    def __init__(self, tarea, client, planificador, req=None, metricas=metricas):
        self.ficha = tarea.ficha
        self.client, self.planificador, self.req, self.metricas = client, planificador, req, metricas
        self._exclusivo = False

    @asynccontextmanager
    async def turno_exclusivo(self):
        if self.ficha.prioridad == 'cpu' or self._exclusivo:
            raise ValueError('Turno inválido')
        async with self.planificador.turno(self.ficha.prioridad):
            self._exclusivo = True
            try: yield
            finally: self._exclusivo = False

    async def llamar(self, etapa, system, user, *, format=None, opciones_extra=None):
        from app.providers import ollama
        if self.ficha.prioridad == 'cpu': raise ValueError('CPU no puede llamar al modelo')
        llamada = next((l for l in self.ficha.llamadas if l.etapa == etapa), None)
        if llamada is None: raise ValueError('Etapa no declarada')
        opciones = {**llamada.opciones(self.req), **(opciones_extra or {})}
        cota = verificar(system, user, opciones['num_predict'], llamada.entrada(), self.ficha.sin_conteo_exacto)
        token = politica_actual.set(self.ficha.sin_conteo_exacto)
        try:
            async def enviar():
                return await ollama.call(system, user, self.client, options=opciones, format=format, max_retries=1,
                    tarea=self.ficha.nombre, etapa=etapa, politica=self.ficha.sin_conteo_exacto,
                    max_tokens_entrada=llamada.entrada())
            if self._exclusivo:
                resultado = await enviar()
            else:
                async with self.planificador.turno(self.ficha.prioridad): resultado = await enviar()
            return resultado
        finally: politica_actual.reset(token)

class CacheTareas:
    def __init__(self, max_size=None, ttl_seconds=None):
        self._max_size = settings.cache_max_size if max_size is None else max_size
        self._ttl = settings.cache_ttl_seconds if ttl_seconds is None else ttl_seconds
        self._store = OrderedDict()
        self._lock = threading.Lock()

    def get(self, clave):
        with self._lock:
            entrada = self._store.get(clave)
            if entrada is None:
                return None
            valor, fecha = entrada
            if time.monotonic() - fecha > self._ttl:
                del self._store[clave]
                return None
            self._store.move_to_end(clave)
            copia = deepcopy(valor)
            if hasattr(copia, "generacion"):
                copia.generacion.cached = True
            elif isinstance(copia, dict):
                copia["cached"] = True
            return copia

    def put(self, clave, respuesta):
        if (respuesta.get("estado", "generada") if isinstance(respuesta, dict) else getattr(respuesta, "estado", "generada")) != "generada" or self._max_size <= 0:
            return
        with self._lock:
            self._store[clave] = (deepcopy(respuesta), time.monotonic())
            self._store.move_to_end(clave)
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    def clear(self):
        with self._lock:
            self._store.clear()


def clave_general(tarea, req):
    datos = [tarea.ficha.nombre, tarea.ficha.version, settings.ollama_model,
             [l.opciones(req) for l in tarea.ficha.llamadas], req.model_dump(mode='json')]
    return hashlib.sha256(json.dumps(datos, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
