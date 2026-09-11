"""Dominio: campos visuales por confrontacion y test de Amsler (2 correlaciones).

campos_visuales_alterados y amsler_alterado. Ambas usan la ventana de negacion
por oracion sobre las keywords positivas (misma mecanica que fondo/pupilas): un
hallazgo positivo dispara salvo que su propia oracion lo niegue ("sin escotoma",
"campo normal sin defectos"). No se aplica un bloqueo global del campo por la
palabra "normal": una normalidad parcial ("escotoma en OD, resto del campo
normal") no debe suprimir un hallazgo positivo documentado en otra clausula.
"""
from __future__ import annotations

from app.correlaciones.texto import _contains_keyword
from app.schemas import ImpresionClinicaRequest

_KEYWORDS_CAMPOS_POSITIVOS = (
    "escotoma", "defecto", "hemianopsia", "hemianopia",
    "cuadrantopsia", "cuadrantanopsia", "cuadrantanopia",
    "escalon nasal", "constriccion", "restriccion",
    "campo reducido", "reduccion del campo", "estrechamiento del campo",
    "vision tubular", "campo tubular", "alteracion", "no responde",
)
_KEYWORDS_AMSLER_POSITIVOS = (
    "distorsion", "metamorfopsia", "micropsia", "macropsia",
    "escotoma central", "escotoma", "alterado", "alteracion",
    "ondulacion", "lineas torcidas", "lineas onduladas", "lineas distorsionadas",
    "lineas quebradas", "area faltante", "zona faltante",
)


def _cond_campos_visuales_alterados(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: escotoma o hemianopsia en confrontacion ameritan perimetria formal."""
    clinica = req.clinica
    if clinica is None:
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
    return _contains_keyword(
        clinica.grid_de_amsler,
        _KEYWORDS_AMSLER_POSITIVOS,
        allow_negation_window=True,
    )


_texto_amsler_alterado = (
    "El test de Amsler revela alteracion sugestiva de alteracion macular funcional "
    "que amerita OCT macular."
)
