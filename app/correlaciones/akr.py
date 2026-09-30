"""Comparacion de autorrefractometro y refraccion final: dos reglas activas.

Las diferencias entre registros no identifican por si solas una causa clinica.
"""
from __future__ import annotations

from datetime import datetime

from app.correlaciones.queratometria import _contexto_mediciones
from app.correlaciones.texto import _join_hallazgos
from app.schemas import GraduacionOjo, ImpresionClinicaRequest

# Umbral operativo de revision; no valida inestabilidad ni una causa clinica.
# La concordancia AR-subjetivo depende del equipo y del componente comparado.
_UMBRAL_VARIABILIDAD_D = 1.50


def _akr_comparable(req: ImpresionClinicaRequest, ahora: datetime | None = None) -> bool:
    """Compatibilidad: permite describir registros AKR presentes.

    El contrato ignora taken_at para inferencia y no aporta fecha del examen Rx.
    La presencia de ambos registros nunca acredita comparabilidad temporal.
    Se conserva el argumento ahora para consumidores previos, sin filtro de reloj.
    """
    return req.akr is not None


def _diferencias_ar_rx(req: ImpresionClinicaRequest) -> list[tuple[str, str, float, float]]:
    if req.refraccion is None or req.akr is None:
        return []
    diferencias = []
    for label, side in [("OD", "od"), ("OI", "oi")]:
        ar = getattr(req.akr, side)
        rx = getattr(req.refraccion, side)
        for componente in ("esfera", "cilindro"):
            valor_ar, valor_rx = getattr(ar, componente), getattr(rx, componente)
            if valor_ar is not None and valor_rx is not None and abs(valor_ar - valor_rx) >= _UMBRAL_VARIABILIDAD_D:
                diferencias.append((label, componente, valor_ar, valor_rx))
    return diferencias


def _cond_ar_rx_variabilidad_inespecifica(req: ImpresionClinicaRequest) -> bool:
    """Diferencia entre componentes registrados para revisar su comparabilidad."""
    return bool(_diferencias_ar_rx(req))


def _texto_ar_rx_variabilidad_inespecifica(req: ImpresionClinicaRequest) -> str:
    valores = _join_hallazgos([
        f"{ojo}: {componente} AR {ar:+.2f}D y Rx prescrita {rx:+.2f}D (diferencia absoluta {abs(ar-rx):.2f}D)"
        for ojo, componente, ar, rx in _diferencias_ar_rx(req)
    ])
    return (
        f"Diferencia entre registros: {valores}. Conviene revisar las mediciones y el criterio "
        "de prescripcion antes de interpretar la diferencia; los registros no acreditan "
        "simultaneidad, ejes equivalentes ni el mismo plano optico. La diferencia aislada "
        "no establece su causa ni inestabilidad refractiva."
    ) + _contexto_mediciones(req)


def _eye_has_refraction(eye: GraduacionOjo | None) -> bool:
    """Verifica si el ojo tiene datos reales de refraccion subjetiva prescrita."""
    if eye is None:
        return False
    return eye.esfera is not None or eye.cilindro is not None


def _cilindros_ar_rx_seleccionados(req: ImpresionClinicaRequest) -> list[tuple[str, float, float]]:
    """Seleccion operativa de cilindros explicitos; K no confirma ni excluye Rx."""
    if req.refraccion is None or req.akr is None:
        return []
    datos = []
    for label, side in [("OD", "od"), ("OI", "oi")]:
        cil_ar = getattr(req.akr, side).cilindro
        cil_rx = getattr(req.refraccion, side).cilindro
        if cil_ar is not None and cil_rx is not None and abs(cil_ar) >= 0.75 and abs(cil_rx) < 0.50:
            datos.append((label, cil_ar, cil_rx))
    return datos


def _cond_ar_detecta_astigmatismo_no_prescrito(req: ImpresionClinicaRequest) -> bool:
    """Compara cilindros registrados sin convertir ausencia en decision de receta."""
    return bool(_cilindros_ar_rx_seleccionados(req))


def _texto_ar_detecta_astigmatismo_no_prescrito(req: ImpresionClinicaRequest) -> str:
    partes = [f"{label}: cilindro AR {cil_ar:+.2f}D y cilindro prescrito {cil_rx:+.2f}D"
              for label, cil_ar, cil_rx in _cilindros_ar_rx_seleccionados(req)]
    return (
        f"En los registros consta {_join_hallazgos(partes)}. Conviene revisar las mediciones "
        "y el criterio de prescripcion antes de interpretar la diferencia; el cilindro corneal "
        "no representa por si solo todo el componente ocular. No se acredita comparabilidad "
        "temporal ni de planos opticos, y esta seleccion no evalua diferencias de eje."
    ) + _contexto_mediciones(req)
