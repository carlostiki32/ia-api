from app.schemas import (
    AkrOjo,
    AkrSnapshot,
    ContextoPaciente,
    DatosClinica,
    GraduacionOjo,
    ImpresionClinicaRequest,
    Refraccion,
)


def test_graduacion_ojo_defaults():
    ojo = GraduacionOjo()
    assert ojo.esfera is None
    assert ojo.cilindro is None
    assert ojo.eje is None
    assert ojo.add is None
    assert ojo.av_sc is None
    assert ojo.av_cc is None


def test_graduacion_ojo_with_values():
    ojo = GraduacionOjo(esfera=-1.50, cilindro=-0.75, eje=180, av_sc="20/200", av_cc="20/20")
    assert ojo.esfera == -1.50
    assert ojo.cilindro == -0.75
    assert ojo.eje == 180
    assert ojo.av_sc == "20/200"
    assert ojo.av_cc == "20/20"


def test_akr_ojo_defaults():
    ojo = AkrOjo()
    assert ojo.esfera is None
    assert ojo.k1_d is None


def test_akr_ojo_accepts_keratometry_values():
    ojo = AkrOjo(
        esfera=-1.25,
        cilindro=-0.75,
        eje=180,
        k1_d=41.25,
        k1_mm=8.18,
        k1_eje=180,
        k2_d=43.75,
        k2_mm=7.71,
        k2_eje=90,
        k_promedio_d=42.50,
        k_promedio_mm=7.94,
        k_cilindro=-2.50,
        k_cilindro_eje=180,
    )

    assert ojo.k1_d == 41.25
    assert ojo.k2_eje == 90
    assert ojo.k_cilindro == -2.50


def test_akr_ojo_descarta_keratometria_fuera_de_rango():
    # Coercion tolerante: el endpoint recibe estado de formulario sin validar;
    # un valor fisicamente imposible se descarta sin tumbar el request.
    assert AkrOjo(k1_d=81).k1_d is None
    assert AkrOjo(k1_d=24).k1_d is None
    assert AkrOjo(k1_mm=13).k1_mm is None
    assert AkrOjo(k_promedio_d=81).k_promedio_d is None
    assert AkrOjo(k_cilindro=-31).k_cilindro is None
    assert AkrOjo(k_cilindro=31).k_cilindro is None
    assert AkrOjo(k_cilindro=-25.0).k_cilindro == -25.0
    # El eje es ciclico: se normaliza modulo 180 en vez de descartarse.
    assert AkrOjo(k_cilindro_eje=181).k_cilindro_eje == 1


def test_akr_snapshot_pd_range():
    # Rango en SaaS: 0..100 mm.
    assert AkrSnapshot(pd=63.5).pd == 63.5
    assert AkrSnapshot(pd=0.0).pd == 0.0
    assert AkrSnapshot(pd=100.0).pd == 100.0
    assert AkrSnapshot(pd=-1.0).pd is None
    assert AkrSnapshot(pd=101.0).pd is None


def test_datos_clinica_uso_pantallas_valid():
    for val in ["lt2", "btw2_6", "gt6"]:
        c = DatosClinica(uso_pantallas=val)
        assert c.uso_pantallas == val


def test_datos_clinica_uso_pantallas_invalid_se_descarta():
    assert DatosClinica(uso_pantallas="invalid").uso_pantallas is None


def test_datos_clinica_ojo_seco_range():
    # Catalogo del SaaS: dropdown 1..15 segundos.
    c = DatosClinica(ojo_seco_but_seg=1)
    assert c.ojo_seco_but_seg == 1
    c = DatosClinica(ojo_seco_but_seg=15)
    assert c.ojo_seco_but_seg == 15


def test_datos_clinica_ojo_seco_out_of_range_se_descarta():
    assert DatosClinica(ojo_seco_but_seg=0).ojo_seco_but_seg is None
    assert DatosClinica(ojo_seco_but_seg=16).ojo_seco_but_seg is None


def test_datos_clinica_ppc_range():
    # Catalogo del SaaS: dropdown 1..15 cm.
    c = DatosClinica(ppc_cm=1)
    assert c.ppc_cm == 1
    c = DatosClinica(ppc_cm=15)
    assert c.ppc_cm == 15


def test_datos_clinica_ppc_out_of_range_se_descarta():
    assert DatosClinica(ppc_cm=0).ppc_cm is None
    assert DatosClinica(ppc_cm=16).ppc_cm is None


def test_graduacion_ojo_eje_rango_valido():
    assert GraduacionOjo(eje=0).eje == 0
    assert GraduacionOjo(eje=180).eje == 180


def test_graduacion_ojo_eje_fuera_de_rango_se_normaliza_mod_180():
    # El input de eje en el SaaS es un number libre sin validacion de rango;
    # el eje es ciclico, asi que 181 == 1 y -1 == 179.
    assert GraduacionOjo(eje=181).eje == 1
    assert GraduacionOjo(eje=-1).eje == 179
    assert GraduacionOjo(eje=270).eje == 90


def test_graduacion_ojo_esfera_fuera_de_catalogo_se_descarta():
    # Rango clinico: hasta +/-30.00 D para permitir alta miopia (-25.00 D) y afaquia extrema.
    assert GraduacionOjo(esfera=35.0).esfera is None
    assert GraduacionOjo(esfera=-30.25).esfera is None
    assert GraduacionOjo(esfera=-25.0).esfera == -25.0
    assert GraduacionOjo(esfera=30.0).esfera == 30.0


def test_graduacion_ojo_cilindro_fuera_de_catalogo_se_descarta():
    # Catalogo del SaaS: dropdown 0.00..-8.00 en pasos de 0.25.
    assert GraduacionOjo(cilindro=-9.0).cilindro is None
    assert GraduacionOjo(cilindro=-8.0).cilindro == -8.0


def test_graduacion_ojo_rx_no_se_transpone():
    # La Rx final NO se transpone: el dropdown del SaaS garantiza cilindro
    # negativo, asi que en produccion nunca hay plus-cyl. Transponerla romperia
    # el piso de esfera de hipermetropia_alta (CORRELACIONES_CLINICAS.md 5.2).
    ojo = GraduacionOjo(esfera=1.0, cilindro=2.0, eje=90)
    assert ojo.esfera == 1.0
    assert ojo.cilindro == 2.0
    assert ojo.eje == 90


def test_akr_ojo_cilindro_positivo_se_transpone():
    # El AKR (lectura de dispositivo) SI se transpone: su convencion la fija el
    # autorrefractometro y puede ser plus-cyl. Alinearlo con la Rx (negativa)
    # mantiene valida la comparacion esfera-a-esfera AR vs Rx.
    ojo = AkrOjo(esfera=-1.0, cilindro=1.5, eje=10)
    assert ojo.esfera == 0.5
    assert ojo.cilindro == -1.5
    assert ojo.eje == 100


def test_graduacion_ojo_add_cero_o_negativa_se_descarta():
    # add <= 0 significa "sin adicion"; add > 30 es fuera de rango del SaaS (between:0,30).
    assert GraduacionOjo(add=0.0).add is None
    assert GraduacionOjo(add=-1.0).add is None
    assert GraduacionOjo(add=30.25).add is None
    assert GraduacionOjo(add=2.0).add == 2.0
    assert GraduacionOjo(add=30.0).add == 30.0


def test_graduacion_ojo_av_snellen_se_canoniza():
    ojo = GraduacionOjo(av_sc=" 20 / 040 ", av_cc="20/20")
    assert ojo.av_sc == "20/40"
    assert ojo.av_cc == "20/20"


def test_graduacion_ojo_av_no_snellen_se_conserva():
    ojo = GraduacionOjo(av_cc="cuenta dedos a 1 m")
    assert ojo.av_cc == "cuenta dedos a 1 m"


def test_contexto_paciente_edad_fuera_de_rango_se_descarta():
    # Rango en SaaS: 0..125 (nacidos desde 1900).
    assert ContextoPaciente(edad=126).edad is None
    assert ContextoPaciente(edad=125).edad == 125
    assert ContextoPaciente(edad=0).edad == 0
    assert ContextoPaciente(edad=-1).edad is None


def test_contexto_paciente_ocupacion_y_motivo_truncados():
    # Limites en SaaS: ocupacion max 120, motivo max 1000.
    p = ContextoPaciente(ocupacion="A" * 150, motivo_consulta="B" * 1200)
    assert len(p.ocupacion) == 120
    assert p.ocupacion == "A" * 120
    assert len(p.motivo_consulta) == 1000
    assert p.motivo_consulta == "B" * 1000


def test_tipo_lente_normaliza_espacios():
    req = ImpresionClinicaRequest(receta_id="t", tipo_lente="  lente   progresivo  ")
    assert req.tipo_lente == "lente progresivo"


def test_contexto_paciente_defaults():
    p = ContextoPaciente()
    assert p.edad is None
    assert p.ocupacion is None
    assert p.motivo_consulta is None


def test_contexto_paciente_with_values():
    p = ContextoPaciente(edad=42, ocupacion="diseñador gráfico", motivo_consulta="cefalea frontal")
    assert p.edad == 42
    assert p.ocupacion == "diseñador gráfico"
    assert p.motivo_consulta == "cefalea frontal"


def test_full_request():
    req = ImpresionClinicaRequest(
        receta_id="test-001",
        paciente=ContextoPaciente(edad=42, ocupacion="diseñador gráfico", motivo_consulta="cefalea frontal"),
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-1.50, cilindro=-0.75, eje=180, av_sc="20/200", av_cc="20/20"),
            oi=GraduacionOjo(esfera=-1.25),
        ),
        akr=AkrSnapshot(
            od=AkrOjo(esfera=-1.75, cilindro=-0.50, eje=175),
        ),
        clinica=DatosClinica(
            uso_pantallas="gt6",
            fondo_de_ojo="papila de bordes nítidos",
            ojo_seco_but_seg=6,
            ppc_cm=8,
        ),
        tipo_lente="progresivo",
    )
    assert req.receta_id == "test-001"
    assert req.paciente.edad == 42
    assert req.refraccion.od.esfera == -1.50
    assert req.clinica.uso_pantallas == "gt6"
    assert req.tipo_lente == "progresivo"


def test_minimal_request():
    req = ImpresionClinicaRequest(receta_id="min-001")
    assert req.paciente.edad is None
    assert req.paciente.ocupacion is None
    assert req.paciente.motivo_consulta is None
    assert req.refraccion.od.esfera is None
    assert req.clinica.uso_pantallas is None
    assert req.tipo_lente is None


def test_datos_clinica_campos_texto_truncados():
    long_text = "Observación clínica detallada. " * 30  # ~930 chars
    clinica = DatosClinica(
        anexos_oculares=long_text,
        reflejos_pupilares="  PIRRL   normal  ",
        motilidad_ocular="Versiones:\n " + ("Normales " * 70),
        confrontacion_campos_visuales=long_text,
        fondo_de_ojo=long_text,
        grid_de_amsler=long_text,
        cover_test="  Orto   -   Foria  ",
        recomendacion_seguimiento=long_text,
    )

    assert len(clinica.anexos_oculares) == 500
    assert clinica.reflejos_pupilares == "PIRRL normal"
    assert len(clinica.motilidad_ocular) == 500
    assert len(clinica.confrontacion_campos_visuales) == 500
    assert len(clinica.fondo_de_ojo) == 500
    assert len(clinica.grid_de_amsler) == 500
    assert " y " in clinica.cover_test  # _COVER_DASH_RE reemplaza " - " por " y "
    assert len(clinica.recomendacion_seguimiento) == 500

