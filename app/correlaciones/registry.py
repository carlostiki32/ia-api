"""Registro y evaluacion de las 36 correlaciones.

El ORDEN de esta lista es un invariante clinico, no incidental: determina el orden
en que los hechos llegan al prompt y, por tanto, la secuencia narrativa del
parrafo. Cualquier reordenamiento debe justificarse clinicamente (los hallazgos
urgentes van primero) y esta cubierto por tests. No ensamblar por concatenacion
automatica de modulos: mantener la lista explicita.
"""
from __future__ import annotations

import logging

from app.correlaciones.base import Correlacion, _eval_cache
from app.correlaciones.akr import (
    _cond_ar_detecta_astigmatismo_no_prescrito,
    _cond_ar_rx_cambio_cristalino,
    _cond_ar_rx_espasmo_acomodativo,
    _cond_ar_rx_variabilidad_inespecifica,
    _texto_ar_detecta_astigmatismo_no_prescrito,
    _texto_ar_rx_cambio_cristalino,
    _texto_ar_rx_espasmo_acomodativo,
    _texto_ar_rx_variabilidad_inespecifica,
)
from app.correlaciones.anexos_cristalino import (
    _cond_anexos_patologicos,
    _cond_opacidad_cristaliniana,
    _texto_anexos_patologicos,
    _texto_opacidad_cristaliniana,
)
from app.correlaciones.binocularidad import (
    _cond_cover_endoforia_sintomatica,
    _cond_cover_exoforia_sintomatica,
    _cond_desviacion_vertical,
    _cond_endotropia_lente,
    _cond_exotropia_lente,
    _cond_insuficiencia_convergencia,
    _cond_ppc_exoforia,
    _texto_cover_endoforia_sintomatica,
    _texto_cover_exoforia_sintomatica,
    _texto_desviacion_vertical,
    _texto_endotropia_lente,
    _texto_exotropia_lente,
    _texto_insuficiencia_convergencia,
    _texto_ppc_exoforia,
)
from app.correlaciones.campos_amsler import (
    _cond_amsler_alterado,
    _cond_campos_visuales_alterados,
    _texto_amsler_alterado,
    _texto_campos_visuales_alterados,
)
from app.correlaciones.contexto import (
    _cond_adulto_mayor_screening,
    _cond_cvs_sospecha,
    _cond_presbicia_multifocal,
    _texto_adulto_mayor_screening,
    _texto_cvs_sospecha,
    _texto_presbicia_multifocal,
)
from app.correlaciones.fondo_de_ojo import (
    _cond_fondo_glaucomatoso,
    _cond_fondo_hipertensivo,
    _cond_fondo_macular_dmae,
    _cond_fondo_macular_otros,
    _cond_fondo_periferico_riesgo,
    _cond_fondo_vascular_diabetico,
    _cond_glaucoma_asimetrico,
    _cond_papila_patologica,
    _texto_fondo_glaucomatoso,
    _texto_fondo_hipertensivo,
    _texto_fondo_macular_dmae,
    _texto_fondo_macular_otros,
    _texto_fondo_periferico_riesgo,
    _texto_fondo_vascular_diabetico,
    _texto_glaucoma_asimetrico,
    _texto_papila_patologica,
)
from app.correlaciones.pupilas_motilidad import (
    _cond_motilidad_alterada,
    _cond_pupilas_alteradas,
    _texto_motilidad_alterada,
    _texto_pupilas_alteradas,
)
from app.correlaciones.refractivas import (
    _cond_anisometropia,
    _cond_astig_oblicuo,
    _cond_av_cc_limitada,
    _cond_hipermetropia_alta,
    _cond_miopia_magna,
    _texto_anisometropia,
    _texto_astig_oblicuo,
    _texto_av_cc_limitada,
    _texto_hipermetropia_alta,
    _texto_miopia_magna,
)
from app.correlaciones.superficie_ocular import (
    _cond_but_critico,
    _cond_but_limitrofe,
    _cond_but_pantallas,
    _texto_but_critico,
    _texto_but_limitrofe,
    _texto_but_pantallas,
)
from app.schemas import ImpresionClinicaRequest

logger = logging.getLogger(__name__)


CORRELACIONES: list[Correlacion] = [
    Correlacion("fondo_periferico_riesgo", _cond_fondo_periferico_riesgo, _texto_fondo_periferico_riesgo),
    Correlacion("papila_patologica", _cond_papila_patologica, _texto_papila_patologica),
    Correlacion("glaucoma_asimetrico", _cond_glaucoma_asimetrico, _texto_glaucoma_asimetrico),
    Correlacion("pupilas_alteradas", _cond_pupilas_alteradas, _texto_pupilas_alteradas),
    Correlacion("fondo_glaucomatoso", _cond_fondo_glaucomatoso, _texto_fondo_glaucomatoso),
    Correlacion("fondo_macular_dmae", _cond_fondo_macular_dmae, _texto_fondo_macular_dmae),
    Correlacion("fondo_macular_otros", _cond_fondo_macular_otros, _texto_fondo_macular_otros),
    Correlacion("fondo_hipertensivo", _cond_fondo_hipertensivo, _texto_fondo_hipertensivo),
    Correlacion("fondo_vascular_diabetico", _cond_fondo_vascular_diabetico, _texto_fondo_vascular_diabetico),
    Correlacion("motilidad_alterada", _cond_motilidad_alterada, _texto_motilidad_alterada),
    Correlacion("campos_visuales_alterados", _cond_campos_visuales_alterados, _texto_campos_visuales_alterados),
    Correlacion("opacidad_cristaliniana", _cond_opacidad_cristaliniana, _texto_opacidad_cristaliniana),
    Correlacion("but_critico", _cond_but_critico, _texto_but_critico),
    Correlacion("miopia_magna", _cond_miopia_magna, _texto_miopia_magna),
    Correlacion("hipermetropia_alta", _cond_hipermetropia_alta, _texto_hipermetropia_alta),
    Correlacion("anisometropia", _cond_anisometropia, _texto_anisometropia),
    Correlacion("av_cc_limitada", _cond_av_cc_limitada, _texto_av_cc_limitada),
    Correlacion("ar_rx_espasmo_acomodativo", _cond_ar_rx_espasmo_acomodativo, _texto_ar_rx_espasmo_acomodativo),
    Correlacion("ar_rx_cambio_cristalino", _cond_ar_rx_cambio_cristalino, _texto_ar_rx_cambio_cristalino),
    Correlacion("ar_rx_variabilidad_inespecifica", _cond_ar_rx_variabilidad_inespecifica, _texto_ar_rx_variabilidad_inespecifica),
    Correlacion("ar_detecta_astigmatismo_no_prescrito", _cond_ar_detecta_astigmatismo_no_prescrito, _texto_ar_detecta_astigmatismo_no_prescrito),
    Correlacion("astig_oblicuo", _cond_astig_oblicuo, _texto_astig_oblicuo),
    Correlacion("amsler_alterado", _cond_amsler_alterado, _texto_amsler_alterado),
    Correlacion("anexos_patologicos", _cond_anexos_patologicos, _texto_anexos_patologicos),
    Correlacion("insuficiencia_convergencia", _cond_insuficiencia_convergencia, _texto_insuficiencia_convergencia),
    Correlacion("ppc_exoforia", _cond_ppc_exoforia, _texto_ppc_exoforia),
    Correlacion("cover_exoforia_sintomatica", _cond_cover_exoforia_sintomatica, _texto_cover_exoforia_sintomatica),
    Correlacion("cover_endoforia_sintomatica", _cond_cover_endoforia_sintomatica, _texto_cover_endoforia_sintomatica),
    Correlacion("desviacion_vertical", _cond_desviacion_vertical, _texto_desviacion_vertical),
    Correlacion("cvs_sospecha", _cond_cvs_sospecha, _texto_cvs_sospecha),
    Correlacion("endotropia_lente", _cond_endotropia_lente, _texto_endotropia_lente),
    Correlacion("exotropia_lente", _cond_exotropia_lente, _texto_exotropia_lente),
    Correlacion("but_pantallas", _cond_but_pantallas, _texto_but_pantallas),
    Correlacion("but_limitrofe", _cond_but_limitrofe, _texto_but_limitrofe),
    Correlacion("presbicia_multifocal", _cond_presbicia_multifocal, _texto_presbicia_multifocal),
    Correlacion("adulto_mayor_screening", _cond_adulto_mayor_screening, _texto_adulto_mayor_screening),
]


def _evaluar(req: ImpresionClinicaRequest) -> list[tuple[str, str]]:
    """Evalua las 36 correlaciones dentro de un unico scope de memoizacion y
    devuelve pares (nombre, texto) en el orden de registro de CORRELACIONES."""
    token = _eval_cache.set({})
    try:
        return [
            (correlacion.nombre, correlacion.render(req))
            for correlacion in CORRELACIONES
            if correlacion.condicion(req)
        ]
    finally:
        _eval_cache.reset(token)


def evaluar_correlaciones(req: ImpresionClinicaRequest) -> list[str]:
    """Textos clinicos de las correlaciones activas, en orden de registro."""
    activas = _evaluar(req)
    if activas:
        logger.debug(
            "Correlaciones activadas [%s]: %s",
            req.receta_id,
            [nombre for nombre, _ in activas],
        )
    return [texto for _, texto in activas]


def nombres_correlaciones_activas(req: ImpresionClinicaRequest) -> list[str]:
    """Solo los nombres de las correlaciones activas, para trazabilidad en la
    respuesta HTTP. Determinista y barato: comparte la logica de supresion con
    evaluar_correlaciones (mismo orden, mismos supresores)."""
    token = _eval_cache.set({})
    try:
        return [c.nombre for c in CORRELACIONES if c.condicion(req)]
    finally:
        _eval_cache.reset(token)
