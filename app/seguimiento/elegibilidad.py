from app.patient_profile import build_patient_profile_from_refraccion
from app.seguimiento.catalogo import HECHOS
from app.seguimiento.schemas import SeguimientoWhatsappRequest


def hechos_elegibles(req: SeguimientoWhatsappRequest, uso_lentes: str) -> list[str]:
    """Determina los hechos elegibles (0..6) según el perfil y la etiqueta de uso."""
    ids = set()
    if req.rx_lejos is not None:
        perfil = build_patient_profile_from_refraccion(req.rx_lejos.refraccion())
        if perfil.estado != "datos_incompletos":
            nombres = set(perfil.nombres)
            antimetropia = {"miopía", "hipermetropía"} <= nombres
            mixto = any(
                (eye.esfera is not None and eye.cilindro is not None and eye.esfera * (eye.esfera + eye.cilindro) < 0)
                for eye in (req.rx_lejos.od, req.rx_lejos.oi)
            )
            if not antimetropia:
                if "hipermetropía" in nombres and not mixto:
                    if uso_lentes not in ("lejos_y_cerca", "ver_de_cerca") and req.estado_seguimiento != "vencido":
                        ids.add("hipermetropia_cerca")
                if "astigmatismo" in nombres:
                    if req.usa_armazon is True:
                        ids.add("astigmatismo_comodidad")
            if any(o.apoyo_cerca for o in perfil.ojos):
                if req.tipo_lente == "progresivo":
                    if uso_lentes != "lejos_y_cerca":
                        ids.add("progresivo_zonas")
                        if req.usa_armazon is True:
                            ids.add("progresivo_ajuste")
                if req.tipo_lente == "bifocal":
                    if uso_lentes != "lejos_y_cerca":
                        ids.add("bifocal_zonas")
            if req.tipo_lente in ("monofocal", "bifocal") and req.usa_armazon is True:
                ids.add("ajuste_armazon")
    return [h.id for h in HECHOS if h.id in ids]
