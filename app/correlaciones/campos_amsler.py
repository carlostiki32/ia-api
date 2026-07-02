"""Dominio: campos visuales por confrontacion y test de Amsler (2 correlaciones).

campos_visuales_alterados y amsler_alterado. Ambas aplican un doble filtro de
negacion: marcas negativas globales (normal, integro, sin alteracion...) que
bloquean toda la correlacion, mas la ventana de negacion por oracion sobre las
keywords positivas.
"""
from __future__ import annotations

from app.correlaciones.texto import _contains_keyword, _normalize_text
from app.schemas import ImpresionClinicaRequest

_KEYWORDS_CAMPOS_POSITIVOS = (
    "escotoma", "defecto", "hemianopsia", "cuadrantopsia",
    "constriccion", "restriccion", "campo reducido", "alteracion", "no responde",
)
_KEYWORDS_CAMPOS_NEGATIVOS = ("sin defect", "sin alteracion", "normal", "integro")
_KEYWORDS_AMSLER_POSITIVOS = (
    "distorsion", "metamorfopsia", "escotoma central", "escotoma",
    "alterado", "alteracion", "ondulacion", "lineas torcidas",
)
_KEYWORDS_AMSLER_NEGATIVOS = ("sin distorsion", "sin alteracion", "normal", "negativo")


def _cond_campos_visuales_alterados(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: escotoma o hemianopsia en confrontacion ameritan perimetria formal."""
    clinica = req.clinica
    if clinica is None:
        return False
    texto = _normalize_text(clinica.confrontacion_campos_visuales)
    if not texto:
        return False
    if any(neg in texto for neg in _KEYWORDS_CAMPOS_NEGATIVOS):
        return False
    return _contains_keyword(
        clinica.confrontacion_campos_visuales,
        _KEYWORDS_CAMPOS_POSITIVOS,
        allow_negation_window=True,
    )


_texto_campos_visuales_alterados = (
    "La confrontacion de campos visuales revela alteracion que amerita perimetria "
    "automatizada para caracterizacion del defecto."
)


def _cond_amsler_alterado(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: metamorfopsia o lineas torcidas en Amsler ameritan OCT macular."""
    clinica = req.clinica
    if clinica is None:
        return False
    texto = _normalize_text(clinica.grid_de_amsler)
    if not texto:
        return False
    if any(neg in texto for neg in _KEYWORDS_AMSLER_NEGATIVOS):
        return False
    return _contains_keyword(
        clinica.grid_de_amsler,
        _KEYWORDS_AMSLER_POSITIVOS,
        allow_negation_window=True,
    )


_texto_amsler_alterado = (
    "El test de Amsler revela alteracion compatible con patologia macular funcional "
    "que amerita OCT macular."
)
