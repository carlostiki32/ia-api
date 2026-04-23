import app.correlaciones as corr
from app.schemas import (
    AkrOjo,
    AkrSnapshot,
    ContextoPaciente,
    DatosClinica,
    GraduacionOjo,
    ImpresionClinicaRequest,
    Refraccion,
)


def _make_request(**kwargs) -> ImpresionClinicaRequest:
    defaults = {"receta_id": "test"}
    defaults.update(kwargs)
    return ImpresionClinicaRequest(**defaults)


def _active_names(req: ImpresionClinicaRequest) -> list[str]:
    return [c.nombre for c in corr.CORRELACIONES if c.condicion(req)]


def test_av_cc_limitada_ignora_vision_supranormal():
    req = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(av_cc="20/15"),
            oi=GraduacionOjo(av_cc="20/20"),
        )
    )

    assert corr.evaluar_correlaciones(req) == []


def test_av_cc_limitada_categoria_moderada():
    req = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(av_cc="20/40"),
        )
    )

    result = corr.evaluar_correlaciones(req)

    assert len(result) == 1
    assert "OD (20/40)" in result[0]
    assert "reduccion moderada" in result[0]


def test_anisometropia_usa_equivalente_esferico_y_evita_falso_positivo():
    req = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-3.00, cilindro=0.00),
            oi=GraduacionOjo(esfera=-1.00, cilindro=-4.00),
        )
    )

    assert "anisometropia" not in _active_names(req)


def test_ar_rx_espasmo_acomodativo_activa_variante_especifica():
    req = _make_request(
        paciente=ContextoPaciente(edad=25),
        clinica=DatosClinica(uso_pantallas="gt6"),
        refraccion=Refraccion(od=GraduacionOjo(esfera=-1.00)),
        akr=AkrSnapshot(od=AkrOjo(esfera=-1.75)),
    )

    names = _active_names(req)
    texts = corr.evaluar_correlaciones(req)

    assert "ar_rx_espasmo_acomodativo" in names
    assert "ar_rx_variabilidad_inespecifica" not in names
    assert any("espasmo acomodativo" in text for text in texts)


def test_ar_rx_cambio_cristalino_activa_variante_especifica():
    req = _make_request(
        paciente=ContextoPaciente(edad=67),
        refraccion=Refraccion(od=GraduacionOjo(esfera=+1.00)),
        akr=AkrSnapshot(od=AkrOjo(esfera=-0.50)),
    )

    names = _active_names(req)

    assert "ar_rx_cambio_cristalino" in names
    assert "ar_rx_variabilidad_inespecifica" not in names


def test_ar_rx_variabilidad_inespecifica_activa_como_fallback():
    req = _make_request(
        paciente=ContextoPaciente(edad=45),
        refraccion=Refraccion(od=GraduacionOjo(esfera=+0.50)),
        akr=AkrSnapshot(od=AkrOjo(esfera=+2.00)),
    )

    names = _active_names(req)

    assert "ar_rx_variabilidad_inespecifica" in names
    assert "ar_rx_espasmo_acomodativo" not in names
    assert "ar_rx_cambio_cristalino" not in names


def test_ar_detecta_astigmatismo_no_prescrito():
    req = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(cilindro=-0.25)),
        akr=AkrSnapshot(od=AkrOjo(cilindro=-1.00)),
    )

    names = _active_names(req)

    assert "ar_detecta_astigmatismo_no_prescrito" in names


def test_insuficiencia_convergencia_suprime_ppc_y_cover_exoforia():
    req = _make_request(
        paciente=ContextoPaciente(motivo_consulta="cefalea frontal y fatiga con lectura"),
        clinica=DatosClinica(
            ppc_cm=12,
            cover_test="OD: Exo y Foria | OI: Orto",
        ),
    )

    names = _active_names(req)
    texts = corr.evaluar_correlaciones(req)

    assert "insuficiencia_convergencia" in names
    assert "ppc_exoforia" not in names
    assert "cover_exoforia_sintomatica" not in names
    assert any("insuficiencia de convergencia" in text for text in texts)


def test_papila_patologica_urgente_por_bordes_borrosos():
    req = _make_request(
        clinica=DatosClinica(fondo_de_ojo="Papila con bordes borrosos en ambos ojos."),
    )

    names = _active_names(req)
    texts = corr.evaluar_correlaciones(req)

    assert "papila_patologica" in names
    assert any("urgente" in text for text in texts)
    assert any("hipertension intracraneal" in text for text in texts)


def test_fondo_vascular_diabetico_no_activa_por_hemorragia_subconjuntival():
    req = _make_request(
        clinica=DatosClinica(fondo_de_ojo="Hemorragia subconjuntival por esfuerzo."),
    )

    assert "fondo_vascular_diabetico" not in _active_names(req)


def test_negacion_por_oracion_evita_falso_positivo_en_dmae():
    req = _make_request(
        clinica=DatosClinica(
            fondo_de_ojo=(
                "En la exploracion detallada del segmento posterior no se documenta la "
                "presencia de drusas ni alteraciones pigmentarias."
            )
        ),
    )

    assert "fondo_macular_dmae" not in _active_names(req)


def test_hipermetropia_alta_adapta_texto_en_paciente_joven():
    req = _make_request(
        paciente=ContextoPaciente(edad=18),
        refraccion=Refraccion(od=GraduacionOjo(esfera=+5.50)),
    )

    result = corr.evaluar_correlaciones(req)

    assert len(result) == 1
    assert "demanda acomodativa significativa" in result[0]


def test_exotropia_lente_activa():
    req = _make_request(
        clinica=DatosClinica(cover_test="OD: Exo y Tropia | OI: Orto"),
        tipo_lente="monofocal",
    )

    names = _active_names(req)

    assert "exotropia_lente" in names


def test_desviacion_vertical_activa():
    req = _make_request(
        clinica=DatosClinica(cover_test="OD: Hiper y Foria | OI: Orto"),
    )

    names = _active_names(req)
    texts = corr.evaluar_correlaciones(req)

    assert "desviacion_vertical" in names
    assert any("hiperforia" in text for text in texts)


def test_adulto_mayor_screening_se_suprime_si_ya_hay_patologia_especifica():
    req = _make_request(
        paciente=ContextoPaciente(edad=72),
        refraccion=Refraccion(od=GraduacionOjo(av_cc="20/40")),
        clinica=DatosClinica(fondo_de_ojo="Drusas en polo posterior."),
    )

    names = _active_names(req)

    assert "fondo_macular_dmae" in names
    assert "adulto_mayor_screening" not in names


def test_fondo_periferico_riesgo_incluye_hallazgo_especifico():
    req = _make_request(
        clinica=DatosClinica(fondo_de_ojo="Se observa lattice periferico temporal."),
    )

    result = corr.evaluar_correlaciones(req)

    assert len(result) == 1
    assert "degeneracion lattice" in result[0]


def test_but_critico_esta_antes_que_correlaciones_contextuales():
    names = [correlacion.nombre for correlacion in corr.CORRELACIONES]

    assert names.index("but_critico") < names.index("presbicia_multifocal")
    assert names.index("but_critico") < names.index("but_pantallas")
