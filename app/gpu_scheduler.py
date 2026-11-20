"""Un turno de GPU por proceso; MAX_CONCURRENT debe ser 1 en producción."""
import asyncio
from collections import deque
from contextlib import asynccontextmanager
from typing import Literal

from app.config import settings

Prioridad = Literal["interactiva", "fondo"]


class GPUOcupada(TimeoutError):
    """Admisión rechazada, cola llena o espera agotada."""


class GPUScheduler:
    def __init__(self):
        self._lock = asyncio.Lock()
        self._ocupantes: dict[object, Prioridad] = {}
        self._colas = {"interactiva": deque(), "fondo": deque()}

    @property
    def estadisticas(self) -> dict:
        prioridades = list(self._ocupantes.values())
        return {
            "ocupada": bool(prioridades),
            "ocupante": ("interactiva" if "interactiva" in prioridades else prioridades[0]) if prioridades else None,
            "en_espera_interactiva": len(self._colas["interactiva"]),
            "en_espera_fondo": len(self._colas["fondo"]),
        }

    @property
    def en_cola(self) -> int:
        return sum(map(len, self._colas.values()))

    def _despachar(self):
        while len(self._ocupantes) < settings.max_concurrent:
            cola = self._colas["interactiva"] or self._colas["fondo"]
            if not cola:
                break
            token, prioridad, futuro = cola.popleft()
            self._ocupantes[token] = prioridad
            futuro.set_result(None)

    @asynccontextmanager
    async def turno(self, prioridad: Prioridad):
        if prioridad not in self._colas:
            raise ValueError("Prioridad desconocida")
        token = object()
        futuro = asyncio.get_running_loop().create_future()
        entrada = (token, prioridad, futuro)
        async with self._lock:
            if prioridad == "fondo" and (
                "interactiva" in self._ocupantes.values() or self._colas["interactiva"]
            ):
                raise GPUOcupada
            if len(self._ocupantes) < settings.max_concurrent and not self.en_cola:
                self._ocupantes[token] = prioridad
                futuro.set_result(None)
            else:
                if self.en_cola >= settings.max_queue_size:
                    raise GPUOcupada
                self._colas[prioridad].append(entrada)
        try:
            espera = settings.queue_wait_timeout if prioridad == "interactiva" else settings.fondo_queue_wait_timeout
            try:
                if espera <= 0 and prioridad == "interactiva":
                    await asyncio.shield(futuro)
                else:
                    await asyncio.wait_for(asyncio.shield(futuro), espera)
            except TimeoutError as exc:
                raise GPUOcupada from exc
            yield
        finally:
            # También cubre la cancelación después del despacho y antes del yield.
            async with self._lock:
                if entrada in self._colas[prioridad]:
                    self._colas[prioridad].remove(entrada)
                self._ocupantes.pop(token, None)
                self._despachar()


gpu_scheduler = GPUScheduler()
