"""Primitivas compartidas por todas las correlaciones: el tipo Correlacion y la
memoizacion por evaluacion.

El contextvar `_eval_cache` es un unico objeto importado por todos los dominios;
`registry.evaluar_correlaciones` lo activa una vez por request para que las
condiciones compartidas (p. ej. `_cond_glaucoma_asimetrico`, consultada tanto por
`fondo_glaucomatoso` como por `pupilas_alteradas`) se computen una sola vez.
"""
from __future__ import annotations

import contextvars
import functools
from dataclasses import dataclass
from typing import Callable

from app.schemas import ImpresionClinicaRequest

_eval_cache: contextvars.ContextVar[dict | None] = contextvars.ContextVar(
    "_eval_cache", default=None
)


def _memoize_cond(fn):
    """Cachea el resultado de una condicion durante una evaluacion de evaluar_correlaciones.

    Fuera de ese scope (cache is None), la funcion se ejecuta sin memoizar para
    preservar el comportamiento en llamadas directas desde tests.
    """
    name = fn.__name__

    @functools.wraps(fn)
    def wrapper(req):
        cache = _eval_cache.get()
        if cache is None:
            return fn(req)
        if name not in cache:
            cache[name] = fn(req)
        return cache[name]

    return wrapper


@dataclass(frozen=True)
class Correlacion:
    nombre: str
    condicion: Callable[[ImpresionClinicaRequest], bool]
    texto: str | Callable[[ImpresionClinicaRequest], str]

    def render(self, req: ImpresionClinicaRequest) -> str:
        texto = self.texto
        return texto if isinstance(texto, str) else texto(req)
