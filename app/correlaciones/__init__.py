"""Capa determinista de correlaciones clinicas optometricas.

API publica estable (consumida por prompt_builder y main):
    - Correlacion
    - CORRELACIONES
    - evaluar_correlaciones(req) -> list[str]
    - nombres_correlaciones_activas(req) -> list[str]

La implementacion esta particionada por dominio clinico (fondo_de_ojo,
refractivas, akr, anexos_cristalino, pupilas_motilidad, campos_amsler,
binocularidad, superficie_ocular, contexto) sobre helpers compartidos
(base, texto, refraccion_utils, queratometria). El registro y el orden de
evaluacion viven en registry.py.
"""
from app.correlaciones.base import Correlacion
from app.correlaciones.registry import (
    CORRELACIONES,
    evaluar_correlaciones,
    nombres_correlaciones_activas,
)

__all__ = [
    "Correlacion",
    "CORRELACIONES",
    "evaluar_correlaciones",
    "nombres_correlaciones_activas",
]
