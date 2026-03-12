from app.schemas import ImpresionClinicaRequest


def has_clinical_data(req: ImpresionClinicaRequest) -> bool:
    """Check that at least some clinical data is present."""
    ref_has_data = False
    for ojo in [req.refraccion.od, req.refraccion.oi]:
        if any(
            v is not None
            for v in [ojo.esfera, ojo.cilindro, ojo.eje, ojo.add, ojo.av_sc, ojo.av_cc]
        ):
            ref_has_data = True
            break

    clinica_has_data = any(
        v is not None
        for v in [
            req.clinica.uso_pantallas,
            req.clinica.anexos_oculares,
            req.clinica.reflejos_pupilares,
            req.clinica.motilidad_ocular,
            req.clinica.confrontacion_campos_visuales,
            req.clinica.fondo_de_ojo,
            req.clinica.grid_de_amsler,
            req.clinica.ojo_seco_but_seg,
            req.clinica.cover_test,
            req.clinica.ppc_cm,
            req.clinica.recomendacion_seguimiento,
        ]
    )

    return ref_has_data or clinica_has_data
