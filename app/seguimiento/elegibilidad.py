from app.patient_profile import build_patient_profile_from_refraccion
from app.seguimiento.catalogo import HECHOS
from app.seguimiento.schemas import SeguimientoWhatsappRequest


def hechos_elegibles(req: SeguimientoWhatsappRequest) -> list[str]:
    ids = {"traer_lentes"}
    lente = req.tipo_lente is not None
    if req.uso_pantallas == "gt6" and lente:
        ids.add("pantallas_muchas")
    if req.uso_pantallas in ("btw2_6", "gt6"):
        ids.add("pantallas_ratos")
    if req.estado_seguimiento == "vencido":
        ids.add("vencida_retomar")
    ids.add("incluida_sin_costo" if req.costo == "incluida" else "con_costo_claro")
    if lente:
        ids.update(("comodidad_general", "general_periodica"))
    if req.rx_lejos is not None:
        perfil = build_patient_profile_from_refraccion(req.rx_lejos.refraccion())
        if perfil.estado != "datos_incompletos":
            nombres = set(perfil.nombres)
            antimetropia = {"miopía", "hipermetropía"} <= nombres
            if not antimetropia:
                if "miopía" in nombres:
                    ids.add("miopia_ajuste")
                    if lente:
                        ids.add("miopia_lejos")
                if "hipermetropía" in nombres:
                    ids.update(("hipermetropia_ajuste", "hipermetropia_cerca"))
                if "astigmatismo" in nombres:
                    ids.add("astigmatismo_detalle")
                    if req.usa_armazon is True:
                        ids.add("astigmatismo_comodidad")
            if any(o.apoyo_cerca for o in perfil.ojos):
                ids.update(("cerca_adecuado", "cerca_distancias"))
                if req.tipo_lente == "progresivo":
                    ids.add("progresivo_zonas")
                    if req.usa_armazon is True:
                        ids.add("progresivo_ajuste")
                if req.tipo_lente == "bifocal":
                    ids.add("bifocal_zonas")
            if req.tipo_lente in ("monofocal", "bifocal") and req.usa_armazon is True:
                ids.add("ajuste_armazon")
    return [h.id for h in HECHOS if h.id in ids]
