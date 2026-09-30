import app.correlaciones as corr
from app.correlaciones import fondo_de_ojo
from app.correlaciones.registry import evaluar_correlaciones_con_nombres
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


def test_av_cc_limitada_describe_cifra_sin_categoria_de_gravedad():
    req = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(av_cc="20/40"),
        )
    )

    result = corr.evaluar_correlaciones(req)

    text = dict(evaluar_correlaciones_con_nombres(req))["av_cc_limitada"]
    assert "OD: AV con correccion registrada de 20/40" in text
    assert "no acredita mejor AV corregida" in text and "moderada" not in text
    assert "deficit_visual_inexplicado_refractivo" in _active_names(req)


def test_anisometropia_usa_equivalente_esferico_y_evita_falso_positivo():
    req = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-3.00, cilindro=0.00),
            oi=GraduacionOjo(esfera=-1.00, cilindro=-4.00),
        )
    )

    assert "anisometropia" not in _active_names(req)


def test_retiro_espasmo_no_infiere_acomodacion_desde_ar_y_pantallas():
    req = _make_request(
        paciente=ContextoPaciente(edad=25),
        clinica=DatosClinica(uso_pantallas="gt6"),
        refraccion=Refraccion(od=GraduacionOjo(esfera=-1.00)),
        akr=AkrSnapshot(od=AkrOjo(esfera=-1.75)),
    )

    names = _active_names(req)
    texts = corr.evaluar_correlaciones(req)

    assert "ar_rx_espasmo_acomodativo" not in names
    assert "ar_rx_variabilidad_inespecifica" not in names
    assert not any("espasmo acomodativo" in text for text in texts)


def test_retiro_cambio_cristalino_conserva_discrepancia():
    req = _make_request(
        paciente=ContextoPaciente(edad=67),
        refraccion=Refraccion(od=GraduacionOjo(esfera=+1.00)),
        akr=AkrSnapshot(od=AkrOjo(esfera=-0.50)),
    )

    names = _active_names(req)

    assert "ar_rx_cambio_cristalino" not in names
    assert "ar_rx_variabilidad_inespecifica" in names


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


def test_ar_rx_cilindros_explicitos_no_se_silencian_por_k_pequena():
    req = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(cilindro=-0.25)),
        akr=AkrSnapshot(
            od=AkrOjo(
                cilindro=-1.00,
                k_cilindro=-0.25,
                k_cilindro_eje=180,
            )
        ),
    )

    assert "ar_detecta_astigmatismo_no_prescrito" in _active_names(req)


def test_ar_rx_cilindros_explicitos_no_infiere_tolerancia_desde_k():
    req = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(cilindro=-0.25)),
        akr=AkrSnapshot(
            od=AkrOjo(
                cilindro=-1.00,
                k_cilindro=-1.25,
                k_cilindro_eje=180,
            )
        ),
    )

    texts = corr.evaluar_correlaciones(req)

    assert "ar_detecta_astigmatismo_no_prescrito" in _active_names(req)
    assert any("cilindro AR -1.00D y cilindro prescrito -0.25D" in text for text in texts)
    assert not any("tolerancia clinica adecuada" in text for text in texts)


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
    assert any("PPC de 12 cm" in text and "exoforia en OD" in text for text in texts)
    assert not any("sospecha de insuficiencia" in text for text in texts)


def test_papila_patologica_urgente_por_bordes_borrosos():
    req = _make_request(
        clinica=DatosClinica(fondo_de_ojo="Papiledema en ambos ojos."),
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
        refraccion=Refraccion(od=GraduacionOjo(esfera=+5.50, cilindro=0)),
    )

    result = corr.evaluar_correlaciones(req)

    assert any("EE +5.50D" in text for text in result)
    assert not any("demanda acomodativa significativa" in text for text in result)


def test_hipermetropia_alta_no_atribuye_mecanismo_desde_k_plana():
    req = _make_request(
        paciente=ContextoPaciente(edad=45),
        refraccion=Refraccion(od=GraduacionOjo(esfera=+5.50, cilindro=0)),
        akr=AkrSnapshot(od=AkrOjo(k_promedio_d=40.00)),
    )

    result = corr.evaluar_correlaciones(req)

    assert any("EE +5.50D" in text for text in result)
    assert not any("componente corneal" in text or "curvatura corneal plana" in text for text in result)


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


def test_astig_oblicuo_no_activa_solo_por_queratometria():
    """K sola no sustituye cilindro/eje final; la coincidencia angular no confirma causa."""
    req = _make_request(
        akr=AkrSnapshot(
            od=AkrOjo(
                k1_d=42.00,
                k1_eje=45,
                k2_d=45.00,
                k2_eje=135,
                k_cilindro=-3.00,
                k_cilindro_eje=45,
            )
        )
    )

    assert "astig_oblicuo" not in _active_names(req)


def test_astig_oblicuo_queratometria_solo_agrega_orientacion():
    req = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(cilindro=-2.50, eje=45)),
        akr=AkrSnapshot(
            od=AkrOjo(
                k1_d=42.00,
                k1_eje=45,
                k2_d=45.00,
                k2_eje=135,
                k_cilindro=-3.00,
                k_cilindro_eje=45,
            )
        ),
    )

    names = _active_names(req)
    texts = corr.evaluar_correlaciones(req)

    assert "astig_oblicuo" in names
    assert any("orientacion oblicua" in text for text in texts)
    assert not any("confirmado" in text or "concordante con queratometria" in text for text in texts)


def test_cambio_cristalino_no_activa_si_queratometria_sugiere_irregularidad_corneal():
    req = _make_request(
        paciente=ContextoPaciente(edad=67),
        refraccion=Refraccion(od=GraduacionOjo(esfera=+1.00)),
        akr=AkrSnapshot(
            od=AkrOjo(
                esfera=-0.50,
                k2_d=49.00,
                k_cilindro=-2.00,
            )
        ),
    )

    names = _active_names(req)

    assert "ar_rx_cambio_cristalino" not in names
    assert "ar_rx_variabilidad_inespecifica" in names


def test_adulto_mayor_av_se_conserva_junto_a_patologia_especifica():
    req = _make_request(
        paciente=ContextoPaciente(edad=72),
        refraccion=Refraccion(od=GraduacionOjo(av_cc="20/40")),
        clinica=DatosClinica(fondo_de_ojo="Atrofia geografica macular."),
    )

    names = _active_names(req)

    assert "fondo_macular_dmae" in names
    assert "adulto_mayor_screening" in names


def test_fondo_periferico_riesgo_incluye_hallazgo_especifico():
    req = _make_request(
        clinica=DatosClinica(fondo_de_ojo="Se observa lattice periferico temporal."),
    )

    result = corr.evaluar_correlaciones(req)

    assert len(result) == 1
    assert "degeneracion lattice" in result[0]


def test_but_critico_esta_antes_que_correlaciones_contextuales():
    names = [correlacion.nombre for correlacion in corr.CORRELACIONES]

    assert names.index("but_critico") < names.index("cvs_sospecha")
    assert names.index("but_critico") < names.index("but_pantallas")


def test_registro_separa_47_medicas_y_un_recordatorio_tecnico():
    """47 médicas: las 46 anteriores más la vía sintomática exigida por #27 D6; las
    correlaciones, con nombres unicos. Blinda el ensamblado de registry.py tras
    la absorcion de ISNT y el retiro de inferencias funcionales #27 y #28."""
    names = [c.nombre for c in corr.CORRELACIONES]
    assert len(names) == 47
    assert len(set(names)) == 47
    assert [c.nombre for c in corr.RECORDATORIOS_TECNICOS] == ["distancia_vertice_alta_ametropia"]


def test_nombres_correlaciones_activas_coincide_con_evaluar():
    """nombres_correlaciones_activas y evaluar_correlaciones deben activar el mismo
    conjunto de correlaciones (misma logica de supresion, un solo origen)."""
    req = _make_request(
        clinica=DatosClinica(
            fondo_de_ojo="Excavacion c/d 0.8 en OD.",
            reflejos_pupilares="Marcus Gunn: positivo OD",
        ),
    )
    nombres = corr.nombres_correlaciones_activas(req)
    esperados = [c.nombre for c in corr.CORRELACIONES if c.condicion(req)]
    assert nombres == esperados


# --- Regresion: bug de substring "mer" en fondo_macular_otros ---

def test_fondo_macular_otros_no_falso_positivo_por_substring_mer():
    """'primer' contiene 'mer' como substring; con matching de palabra completa ya
    no debe disparar la correlacion de membrana epirretiniana."""
    req = _make_request(
        clinica=DatosClinica(fondo_de_ojo="En primer lugar, la macula se observa sin alteraciones."),
    )
    assert "fondo_macular_otros" not in _active_names(req)


def test_fondo_macular_otros_activa_por_abreviatura_mer_como_palabra():
    req = _make_request(clinica=DatosClinica(fondo_de_ojo="Se documenta MER macular en OD."))
    assert "fondo_macular_otros" in _active_names(req)


# --- Regresion: bloqueo global de "normal" en campos/amsler ---

def test_campos_no_se_bloquea_por_normalidad_parcial():
    """Un escotoma real no debe suprimirse porque el resto del campo sea 'normal'."""
    req = _make_request(
        clinica=DatosClinica(
            confrontacion_campos_visuales="Escotoma en cuadrante superior OD, resto del campo normal.",
        ),
    )
    assert "campos_visuales_alterados" in _active_names(req)


def test_amsler_no_se_bloquea_por_normalidad_parcial():
    req = _make_request(
        clinica=DatosClinica(grid_de_amsler="Metamorfopsia central en OI, resto normal."),
    )
    assert "amsler_alterado" in _active_names(req)


# --- Regresion: av_cc en notacion metrica y decimal ---

def test_av_cc_limitada_acepta_metrico():
    """Compatibilidad del helper fuera del catálogo actual; no valida un nuevo payload."""
    req = _make_request(refraccion=Refraccion(od=GraduacionOjo(av_cc="6/12")))
    result = corr.evaluar_correlaciones(req)
    text = dict(evaluar_correlaciones_con_nombres(req))["av_cc_limitada"]
    assert "AV con correccion registrada de 6/12" in text and "moderada" not in text


def test_av_cc_limitada_acepta_decimal():
    req = _make_request(refraccion=Refraccion(od=GraduacionOjo(av_cc="0.5")))
    assert "av_cc_limitada" in _active_names(req)


def test_av_cc_limitada_no_dispara_en_20_25():
    """20/25 queda fuera de esta selección operativa; no acredita normalidad."""
    req = _make_request(refraccion=Refraccion(od=GraduacionOjo(av_cc="20/25")))
    assert corr.evaluar_correlaciones(req) == []


# --- PPC registrado no hereda diagnóstico ni cortes CITT por edad ---

def test_ppc_exoforia_dispara_en_joven_con_ppc_intermedio():
    req = _make_request(
        paciente=ContextoPaciente(edad=25),
        clinica=DatosClinica(ppc_cm=8),
    )
    assert "ppc_exoforia" in _active_names(req)


def test_ppc_exoforia_describe_dato_en_adulto_sin_etiqueta_alejado():
    req = _make_request(
        paciente=ContextoPaciente(edad=55),
        clinica=DatosClinica(ppc_cm=8),
    )
    assert "ppc_exoforia" in _active_names(req)
    assert not any("alejado" in t for t in corr.evaluar_correlaciones(req))


# --- Correlaciones nuevas disparadas por queratometria ---

def test_queratocono_ectasia_sospecha_dispara_por_curvatura_alta():
    req = _make_request(akr=AkrSnapshot(od=AkrOjo(k2_d=49.00, k_cilindro=-2.00)))
    names = _active_names(req)
    texts = corr.evaluar_correlaciones(req)
    assert "queratocono_ectasia_sospecha" in names
    assert any("K2 registrada 49.00D" in text for text in texts)
    assert not any("queratocono" in text or "ectasia" in text for text in texts)


def test_astigmatismo_corneal_vs_refractivo_dispara_por_discrepancia_de_magnitud():
    req = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(cilindro=-0.75, eje=90)),
        akr=AkrSnapshot(od=AkrOjo(k_cilindro=-3.00, k_cilindro_eje=90)),
    )
    assert "astigmatismo_corneal_vs_refractivo" in _active_names(req)


def test_astigmatismo_corneal_vs_refractivo_dispara_por_discrepancia_de_eje():
    req = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(cilindro=-2.00, eje=90)),
        akr=AkrSnapshot(od=AkrOjo(k1_d=42, k2_d=44, k1_eje=180, k2_eje=90, k_cilindro=-2.00, k_cilindro_eje=180)),
    )
    assert "astigmatismo_corneal_vs_refractivo" in _active_names(req)


def test_astigmatismo_corneal_vs_refractivo_no_dispara_si_concuerdan():
    req = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(cilindro=-2.00, eje=90)),
        akr=AkrSnapshot(od=AkrOjo(k_cilindro=-2.25, k_cilindro_eje=92)),
    )
    assert "astigmatismo_corneal_vs_refractivo" not in _active_names(req)


def test_retiro_presbicia_sin_adicion_no_infiere_deficit():
    req = _make_request(
        paciente=ContextoPaciente(edad=50),
        refraccion=Refraccion(od=GraduacionOjo(esfera=+0.50)),
        tipo_lente="monofocal",
    )
    names = _active_names(req)
    assert "presbicia_sin_adicion" not in names
    assert "presbicia_multifocal" not in names


def test_presbicia_sin_adicion_no_dispara_si_hay_adicion():
    req = _make_request(
        paciente=ContextoPaciente(edad=50),
        refraccion=Refraccion(od=GraduacionOjo(esfera=+0.50, add=2.00)),
    )
    assert "presbicia_sin_adicion" not in _active_names(req)


def test_presbicia_sin_adicion_retirada_en_rx_miopica():
    """La receta sola no acredita función de cerca ni estrategia de uso de gafas."""
    req = _make_request(
        paciente=ContextoPaciente(edad=52),
        refraccion=Refraccion(od=GraduacionOjo(esfera=-2.50), oi=GraduacionOjo(esfera=-2.75)),
        tipo_lente="monofocal",
    )
    assert "presbicia_sin_adicion" not in _active_names(req)


# --- Correlaciones nuevas que reviven datos del payload ---

def test_adicion_incongruente_por_add_alta_para_la_edad():
    req = _make_request(
        paciente=ContextoPaciente(edad=46),
        refraccion=Refraccion(od=GraduacionOjo(add=2.75)),
    )
    assert "adicion_incongruente_edad" not in _active_names(req)


def test_adicion_incongruente_por_add_en_no_presbita():
    req = _make_request(
        paciente=ContextoPaciente(edad=28),
        refraccion=Refraccion(od=GraduacionOjo(add=1.50)),
    )
    assert "adicion_incongruente_edad" not in _active_names(req)


def test_adicion_congruente_no_dispara():
    req = _make_request(
        paciente=ContextoPaciente(edad=60),
        refraccion=Refraccion(od=GraduacionOjo(add=2.25)),
    )
    assert "adicion_incongruente_edad" not in _active_names(req)


def test_hipermetropia_alta_invarianza_transposicion_plus_minus():
    """H08: +1.00 esf / +8.00 cil x 90 y su equivalente transpuesta +9.00 esf / -8.00 cil x 180
    representan la misma lente fisica y deben activar exactamente las mismas correlaciones."""
    req_plus = _make_request(
        paciente=ContextoPaciente(edad=25),
        refraccion=Refraccion(od=GraduacionOjo(esfera=+1.00, cilindro=+8.00, eje=90)),
    )
    req_minus = _make_request(
        paciente=ContextoPaciente(edad=25),
        refraccion=Refraccion(od=GraduacionOjo(esfera=+9.00, cilindro=-8.00, eje=180)),
    )
    assert _active_names(req_plus) == _active_names(req_minus)
    assert "hipermetropia_alta" in _active_names(req_plus)
    assert "distancia_vertice_alta_ametropia" not in _active_names(req_plus)
    assert corr.evaluar_recordatorios_tecnicos(req_plus) == corr.evaluar_recordatorios_tecnicos(req_minus)
    assert corr.evaluar_correlaciones(req_plus) == corr.evaluar_correlaciones(req_minus)


def test_ambliopia_sospecha_por_anisometropia_y_av_limitada():
    req = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-0.50, cilindro=0, av_cc="20/20"),
            oi=GraduacionOjo(esfera=-3.00, cilindro=0, av_cc="20/60", av_sc="20/200"),
        ),
    )
    names = _active_names(req)
    texts = corr.evaluar_correlaciones(req)
    assert "ambliopia_sospecha" in names
    assert any("20/200" in t and "20/60" in t for t in texts)
    assert not any("sospecha de ambliopia" in t for t in texts)


def test_ambliopia_sospecha_se_suprime_si_hay_causa_organica():
    req = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-0.50, av_cc="20/20"),
            oi=GraduacionOjo(esfera=-3.00, av_cc="20/60"),
        ),
        clinica=DatosClinica(fondo_de_ojo="Catarata nuclear densa en OI."),
    )
    assert "ambliopia_sospecha" not in _active_names(req)


def test_midriasis_farmacologica_no_dispara_pupilas():
    req = _make_request(
        clinica=DatosClinica(reflejos_pupilares="Midriasis farmacologica post dilatacion para fondo."),
    )
    assert "pupilas_alteradas" not in _active_names(req)


def test_convergencia_no_usa_ocupacion_como_sustituto_de_sintoma():
    """H05: Sin sintomas en el motivo, la ocupacion aporta demanda de cerca pero no sintomatologia.
    No debe disparar insuficiencia_convergencia; en su lugar activa ppc_exoforia describiendo signos."""
    req = _make_request(
        paciente=ContextoPaciente(edad=30, ocupacion="programador", motivo_consulta="revision anual"),
        clinica=DatosClinica(ppc_cm=12, cover_test="OD: Exo y Foria | OI: Orto"),
    )
    names = _active_names(req)
    assert "insuficiencia_convergencia" not in names
    assert "ppc_exoforia" in names
    texts = corr.evaluar_correlaciones(req)
    assert any("PPC de 12 cm" in t for t in texts)
    assert any("exoforia en OD" in t for t in texts)
    assert not any("sintomatologia de vision proxima" in t for t in texts)


def test_convergencia_con_ocupacion_y_sintomas_reales_si_dispara():
    """H05: Con ocupacion y sintomas astenopicos/binoculares reales si dispara insuficiencia_convergencia."""
    req = _make_request(
        paciente=ContextoPaciente(
            edad=30, ocupacion="programador", motivo_consulta="fatiga visual y cefalea al programar"
        ),
        clinica=DatosClinica(ppc_cm=12, cover_test="OD: Exo y Foria | OI: Orto"),
    )
    names = _active_names(req)
    assert "insuficiencia_convergencia" not in names
    assert "ppc_exoforia" in names
    assert "cover_exoforia_sintomatica" in names


# --- Refuerzo de disparadores en texto libre (sinonimos, coloquialismos, abreviaturas) ---

def test_anexos_dispara_por_coloquialismo_carnosidad():
    req = _make_request(clinica=DatosClinica(anexos_oculares="Se observa carnosidad nasal en OD."))
    result = corr.evaluar_correlaciones(req)
    assert "anexos_patologicos" in _active_names(req)
    assert any("carnosidad nasal OD" in t for t in result)
    assert not any("pterigion" in t for t in result)


def test_anexos_dispara_por_calacio_y_perrilla():
    assert "anexos_patologicos" in _active_names(
        _make_request(clinica=DatosClinica(anexos_oculares="Calacio en parpado superior."))
    )
    assert "anexos_patologicos" in _active_names(
        _make_request(clinica=DatosClinica(anexos_oculares="Perrilla en borde palpebral inferior."))
    )


def test_fondo_glaucomatoso_dispara_por_notacion_e_sobre_p():
    req = _make_request(clinica=DatosClinica(fondo_de_ojo="Papila con E/P 0.7 en OD."))
    assert "fondo_glaucomatoso" in _active_names(req)


def test_pupilas_dispara_por_rapd_variante_inglesa():
    req = _make_request(clinica=DatosClinica(reflejos_pupilares="RAPD positivo en OI."))
    texts = corr.evaluar_correlaciones(req)
    assert "pupilas_alteradas" in _active_names(req)
    assert any("retina y via visual aferente" in t for t in texts)
    assert not any("Hallazgo urgente:" in t for t in texts)


def test_campos_dispara_por_vision_tubular():
    req = _make_request(clinica=DatosClinica(confrontacion_campos_visuales="Vision tubular bilateral."))
    assert "campos_visuales_alterados" in _active_names(req)


def test_amsler_dispara_por_micropsia():
    req = _make_request(clinica=DatosClinica(grid_de_amsler="Refiere micropsia en OI."))
    assert "amsler_alterado" in _active_names(req)


def test_fondo_vascular_diabetico_dispara_por_termino_directo():
    # Etiqueta diagnostica aislada sin lesion concreta no dispara
    req_etiqueta = _make_request(clinica=DatosClinica(fondo_de_ojo="Datos de retinopatia diabetica no proliferativa."))
    assert "fondo_vascular_diabetico" not in _active_names(req_etiqueta)

    # Con lesion concreta documentada dispara
    req_lesion = _make_request(clinica=DatosClinica(fondo_de_ojo="Datos de retinopatia diabetica no proliferativa con microaneurismas."))
    assert "fondo_vascular_diabetico" in _active_names(req_lesion)


def test_opacidad_cristaliniana_dispara_por_iol():
    req = _make_request(clinica=DatosClinica(anexos_oculares="Se observa IOL en saco capsular en OD."))
    assert "opacidad_cristaliniana" not in _active_names(req)


def test_cvs_dispara_por_fatiga_ocular():
    req = _make_request(
        paciente=ContextoPaciente(motivo_consulta="fatiga ocular al final del dia"),
        clinica=DatosClinica(uso_pantallas="gt6"),
    )
    assert "cvs_sospecha" in _active_names(req)


def test_insuficiencia_convergencia_dispara_por_contexto_computadora():
    req = _make_request(
        paciente=ContextoPaciente(edad=30, motivo_consulta="cansancio al usar la computadora"),
        clinica=DatosClinica(ppc_cm=12, cover_test="OD: Exo y Foria | OI: Orto"),
    )
    assert "insuficiencia_convergencia" in _active_names(req)


def test_abreviaturas_cortas_no_generan_falsos_positivos_por_substring():
    """irma/adie/iol/nve como substring de palabras comunes no deben disparar."""
    r_irma = _make_request(clinica=DatosClinica(fondo_de_ojo="El paciente afirma no tener sintomas."))
    r_adie = _make_request(clinica=DatosClinica(reflejos_pupilares="No hay nadie con anisocoria en la familia."))
    r_iol = _make_request(clinica=DatosClinica(anexos_oculares="Coloracion violeta del parpado por trauma."))
    r_nve = _make_request(clinica=DatosClinica(fondo_de_ojo="Nevus coroideo convexo estable."))
    assert "fondo_vascular_diabetico" not in _active_names(r_irma)
    assert "fondo_vascular_diabetico" not in _active_names(r_nve)
    assert "opacidad_cristaliniana" not in _active_names(r_iol)
    # 'nadie' no debe disparar la pupila tonica de adie; anisocoria sigue su regla aparte
    nombres_adie = _active_names(r_adie)
    assert "pupila tonica" not in " ".join(corr.evaluar_correlaciones(r_adie))

# ---------------------------------------------------------------------------
# Cover test canonico del SaaS con tipo SIN clasificar (sin Tropia/Foria).
# La UI permite elegir Endo/Exo/Hiper/Hipo sin elegir sub: sigue siendo una
# desviacion documentada por dropdown y debe disparar de forma determinista.
# ---------------------------------------------------------------------------


def test_cover_exo_sin_clasificar_dispara_ppc_exoforia():
    req = _make_request(clinica=DatosClinica(cover_test="OD: Exo | OI: Orto"))

    names = _active_names(req)
    texts = corr.evaluar_correlaciones(req)

    assert "ppc_exoforia" in names
    assert any("exodesviacion no clasificada" in text for text in texts)


def test_cover_endo_sin_clasificar_sintomatico_dispara_endoforia_sintomatica():
    req = _make_request(
        paciente=ContextoPaciente(motivo_consulta="cefalea y vision doble ocasional"),
        clinica=DatosClinica(cover_test="OD: Endo | OI: Orto"),
    )

    names = _active_names(req)
    texts = corr.evaluar_correlaciones(req)

    assert "cover_endoforia_sintomatica" in names
    assert any("endodesviacion no clasificada" in text for text in texts)


def test_cover_hiper_sin_clasificar_dispara_desviacion_vertical():
    req = _make_request(clinica=DatosClinica(cover_test="OD: Hiper | OI: Orto"))

    names = _active_names(req)
    texts = corr.evaluar_correlaciones(req)

    assert "desviacion_vertical" in names
    assert any("hiperdesviacion no clasificada" in text for text in texts)


def test_cover_orto_ambos_ojos_no_dispara_binoculares():
    req = _make_request(clinica=DatosClinica(cover_test="OD: Orto | OI: Orto"))

    names = _active_names(req)

    assert "ppc_exoforia" not in names
    assert "desviacion_vertical" not in names
    assert "cover_endoforia_sintomatica" not in names


def test_cover_endo_sin_clasificar_no_dispara_endotropia_lente():
    """Un Endo sin clasificar no debe tratarse como tropia manifiesta."""
    req = _make_request(
        clinica=DatosClinica(cover_test="OD: Endo | OI: Orto"),
        tipo_lente="monofocal",
    )

    assert "endotropia_lente" not in _active_names(req)


# ---------------------------------------------------------------------------
# tipo_lente: catalogo canonico del SaaS (monofocal, bifocal_blended,
# progresivo, flat_top). flat_top es un bifocal de segmento -> multifocal.
# ---------------------------------------------------------------------------


def test_retiro_presbicia_no_avala_flat_top():
    req = _make_request(
        paciente=ContextoPaciente(edad=55),
        refraccion=Refraccion(od=GraduacionOjo(esfera=+1.00, add=2.00)),
        tipo_lente="flat_top",
    )

    names = _active_names(req)
    texts = corr.evaluar_correlaciones(req)

    assert "presbicia_multifocal" not in names
    assert not any("justifica" in text for text in texts)


def test_flat_top_suprime_presbicia_sin_adicion():
    req = _make_request(
        paciente=ContextoPaciente(edad=55),
        refraccion=Refraccion(od=GraduacionOjo(esfera=+1.00)),
        tipo_lente="flat_top",
    )

    assert "presbicia_sin_adicion" not in _active_names(req)


def test_bifocal_blended_cuenta_como_multifocal():
    req = _make_request(
        paciente=ContextoPaciente(edad=55),
        refraccion=Refraccion(od=GraduacionOjo(esfera=+1.00)),
        tipo_lente="bifocal_blended",
    )

    assert "presbicia_sin_adicion" not in _active_names(req)


# ---------------------------------------------------------------------------
# Interaccion catalogo -> correlaciones: la coercion del schema evita disparos
# espurios con valores que la UI permite capturar pero que no son hallazgo.
# ---------------------------------------------------------------------------


def test_add_cero_no_dispara_presbicia_multifocal():
    """add=0 tecleada en el input libre no es una adicion prescrita."""
    req = _make_request(
        paciente=ContextoPaciente(edad=50),
        refraccion=Refraccion(od=GraduacionOjo(esfera=+1.00, add=0.0)),
        tipo_lente="monofocal",
    )

    names = _active_names(req)

    assert "presbicia_multifocal" not in names
    # La ausencia de add no demuestra una necesidad visual no atendida.
    assert "presbicia_sin_adicion" not in names


def test_eje_fuera_de_rango_se_normaliza_y_dispara_astig_oblicuo():
    """El SaaS no valida el rango del eje (input libre): 225 == 45 (oblicuo)."""
    req = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(esfera=-1.00, cilindro=-2.50, eje=225)),
    )

    assert "astig_oblicuo" in _active_names(req)


# ---------------------------------------------------------------------------
# Tests para remediación NLP (negación bidireccional) y correcciones clínicas
# ---------------------------------------------------------------------------


def test_negacion_pospuesta_elimina_falsos_positivos():
    """Tanto la negación previa ('sin ...') como la pospuesta ('... ausente/descartado')
    deben anular la detección para evitar alertas erróneas."""
    req1 = _make_request(clinica=DatosClinica(fondo_de_ojo="Lattice temporal ausente en OI."))
    assert "fondo_periferico_riesgo" not in _active_names(req1)

    req2 = _make_request(clinica=DatosClinica(fondo_de_ojo="Desgarro retiniano descartado en OD."))
    assert "fondo_periferico_riesgo" not in _active_names(req2)

    req3 = _make_request(clinica=DatosClinica(test_amsler="Metamorfopsia ausente en AO."))
    assert "amsler_alterado" not in _active_names(req3)

    req4 = _make_request(clinica=DatosClinica(anexos_oculares="Blefaritis descartada."))
    assert "anexos_patologicos" not in _active_names(req4)

    req5 = _make_request(clinica=DatosClinica(reflejos_pupilares="Anisocoria ausente."))
    assert "pupilas_alteradas" not in _active_names(req5)


def test_excavacion_fisiologica_no_dispara_glaucoma():
    """Excavaciones fisiológicas normales (0.2, 0.3) no deben activar sospecha de glaucoma."""
    req_normal = _make_request(clinica=DatosClinica(fondo_de_ojo="Papila con excavacion fisiologica 0.3 en AO."))
    assert "fondo_glaucomatoso" not in _active_names(req_normal)

    req_patologico = _make_request(clinica=DatosClinica(fondo_de_ojo="Excavacion 0.7 en OD con rechazo nasal."))
    assert "fondo_glaucomatoso" in _active_names(req_patologico)


def test_coexistencia_retinopatia_diabetica_con_otras_patologias():
    """fondo_vascular_diabetico NO debe ser suprimida por glaucoma o maculopatía."""
    req = _make_request(
        clinica=DatosClinica(
            fondo_de_ojo="Retinopatia diabetica con microaneurismas. Excavacion c/d 0.8 en OD."
        )
    )
    names = _active_names(req)
    assert "fondo_vascular_diabetico" in names
    assert "fondo_glaucomatoso" in names


def test_corneal_cyl_abs_fallback_k1_k2():
    """Si k_cilindro es None, se calcula el delta |K1 - K2|."""
    req = _make_request(
        akr=AkrSnapshot(
            od=AkrOjo(k1_d=42.00, k2_d=44.00, k_cilindro=None),
            oi=AkrOjo(k1_d=43.00, k2_d=43.00, k_cilindro=None),
        ),
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-1.00, cilindro=-0.75, eje=90),
            oi=GraduacionOjo(esfera=-1.00),
        ),
    )
    names = _active_names(req)
    assert "astigmatismo_corneal_vs_refractivo" in names


# ---------------------------------------------------------------------------
# Tests unitarios para las 8 nuevas correlaciones
# ---------------------------------------------------------------------------


def test_nueva_correlacion_horner_o_tercer_par_sospecha():
    req = _make_request(
        clinica=DatosClinica(
            anexos_oculares="Ptosis palpebral en OD",
            reflejos_pupilares="Anisocoria pupilar OD > OI",
        )
    )
    names = _active_names(req)
    assert "horner_o_tercer_par_sospecha" in names
    assert "pupilas_alteradas" not in names  # Retirada


def test_nueva_correlacion_isnt_violada_papila():
    req = _make_request(
        clinica=DatosClinica(fondo_de_ojo="Regla ISNT violada en papila de OD.")
    )
    names = _active_names(req)
    assert "fondo_glaucomatoso" in names
    assert "isnt_violada_papila" not in names
    texts = corr.evaluar_correlaciones(req)
    assert any("regla ISNT" in t for t in texts)


def test_nueva_correlacion_cornea_plana_extrema():
    req = _make_request(
        akr=AkrSnapshot(od=AkrOjo(k1_d=37.50, k2_d=37.80))
    )
    names = _active_names(req)
    assert "cornea_plana_extrema" in names


def test_retiro_astigmatismo_lenticular_puro_conserva_discrepancia():
    req = _make_request(
        akr=AkrSnapshot(od=AkrOjo(k1_d=43.00, k2_d=43.25)),
        refraccion=Refraccion(od=GraduacionOjo(cilindro=-2.00, eje=180)),
    )
    names = _active_names(req)
    assert "astigmatismo_lenticular_puro" not in names
    assert "astigmatismo_corneal_vs_refractivo" in names  # Discrepancia sin etiologia inferida


def test_nueva_correlacion_ojo_seco_evaporativo_dgm():
    req = _make_request(
        clinica=DatosClinica(
            anexos_oculares="Blefaritis anterior y disfuncion meibomio",
            ojo_seco_but_seg=6,
        )
    )
    names = _active_names(req)
    assert "ojo_seco_evaporativo_dgm" in names


def test_aniseiconia_retirada_conserva_asimetria_descriptiva():
    req = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-1.00, cilindro=0),
            oi=GraduacionOjo(esfera=-4.00, cilindro=0),
        ),
        akr=AkrSnapshot(
            od=AkrOjo(k_promedio_d=42.00),
            oi=AkrOjo(k_promedio_d=44.25),
        ),
    )
    names = _active_names(req)
    assert "aniseiconia_queratometrica_severa" not in names
    assert "anisometropia" in names


def test_retiro_insuficiencia_acomodacion_joven():
    req = _make_request(
        paciente=ContextoPaciente(edad=22, motivo_consulta="Cansancio visual y fatiga al leer"),
        refraccion=Refraccion(od=GraduacionOjo(add=1.00)),
    )
    names = _active_names(req)
    assert "insuficiencia_acomodacion_joven" not in names
    assert "adicion_incongruente_edad" not in names  # Retirada


def test_nueva_correlacion_deficit_visual_inexplicado_refractivo():
    req = _make_request(
        paciente=ContextoPaciente(edad=28),
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-1.50, av_sc="20/100", av_cc="20/50"),
        ),
    )
    names = _active_names(req)
    assert "deficit_visual_inexplicado_refractivo" in names


# ---------------------------------------------------------------------------
# Tests de blindaje para las 34 comprobaciones de la auditoria clinica
# ---------------------------------------------------------------------------

def test_auditoria_bloque_a_falsos_negativos():
    # A-01: Desgarro retiniano tras clausula negativa sin puntuacion
    req = _make_request(clinica=DatosClinica(fondo_de_ojo="sin hemorragias ni exudados se observa desgarro en herradura superior"))
    assert "fondo_periferico_riesgo" in _active_names(req)

    # A-02: Papiledema seguido de 'resto normal'
    req = _make_request(clinica=DatosClinica(fondo_de_ojo="papiledema, resto normal"))
    assert "papila_patologica" in _active_names(req)

    # A-03: DPAR tras 'sin anisocoria' sin puntuacion
    req = _make_request(clinica=DatosClinica(reflejos_pupilares="sin anisocoria dpar positivo od"))
    assert "pupilas_alteradas" in _active_names(req)

    # A-04: Excavacion 0.8 dentro de 'se solicita descarte de glaucoma'
    req = _make_request(clinica=DatosClinica(fondo_de_ojo="se solicita descarte de glaucoma por excavacion 0.8"))
    assert "fondo_glaucomatoso" in _active_names(req)

    # A-05: Blefaritis tras 'ao sin pterigion' separada por coma (T1 has_comma_break)
    req = _make_request(clinica=DatosClinica(anexos_oculares="ao sin pterigion, blefaritis moderada bilateral"))
    assert "anexos_patologicos" in _active_names(req)

    # A-06 & A-07: Escotoma y Metamorfopsia seguidos de 'resto normal'
    req = _make_request(clinica=DatosClinica(confrontacion_campos_visuales="escotoma central, resto normal"))
    assert "campos_visuales_alterados" in _active_names(req)
    req = _make_request(clinica=DatosClinica(grid_de_amsler="metamorfopsia central, resto normal"))
    assert "amsler_alterado" in _active_names(req)

    # A-08 & A-09: Endotropia y Exotropia manifiestas sin tipo_lente
    req = _make_request(clinica=DatosClinica(cover_test="OD: Endo y Tropia | OI: Orto"))
    assert "endotropia_lente" in _active_names(req)
    req = _make_request(clinica=DatosClinica(cover_test="OD: Exo y Tropia | OI: Orto"))
    assert "exotropia_lente" in _active_names(req)

    # A-10 & A-11: AV baja no numerica (cuenta dedos, MM)
    req = _make_request(paciente=ContextoPaciente(edad=72), refraccion=Refraccion(od=GraduacionOjo(esfera=-2.0, av_cc="cuenta dedos")))
    assert "av_cc_limitada" in _active_names(req)
    req = _make_request(paciente=ContextoPaciente(edad=45), refraccion=Refraccion(od=GraduacionOjo(esfera=-2.0, av_cc="MM")))
    assert "av_cc_limitada" in _active_names(req)

    # A-12: Alta miopia -25.00 D
    req = _make_request(refraccion=Refraccion(od=GraduacionOjo(esfera=-25.0), oi=GraduacionOjo(esfera=-25.0)))
    assert "miopia_magna" in _active_names(req)


def test_auditoria_bloque_b_falsos_positivos():
    # B-01: Amsler No alterado
    req = _make_request(clinica=DatosClinica(grid_de_amsler="No alterado"))
    assert "amsler_alterado" not in _active_names(req)

    # B-02: Campos No se detectan defectos
    req = _make_request(clinica=DatosClinica(confrontacion_campos_visuales="No se detectan defectos"))
    assert "campos_visuales_alterados" not in _active_names(req)

    # B-03: Isocoricas, no DPAR
    req = _make_request(clinica=DatosClinica(reflejos_pupilares="Isocoricas, no DPAR"))
    assert "pupilas_alteradas" not in _active_names(req)

    # B-04: Excavacion c/d 0.4
    req = _make_request(clinica=DatosClinica(fondo_de_ojo="papila de bordes netos, excavacion c/d 0.4"))
    assert "fondo_glaucomatoso" not in _active_names(req)

    # B-05: Regla ISNT respetada
    req = _make_request(clinica=DatosClinica(fondo_de_ojo="papila sana, regla ISNT respetada, excavacion 0.2"))
    assert "fondo_glaucomatoso" not in _active_names(req)

    # B-06: Papiledema clinicamente descartado
    req = _make_request(clinica=DatosClinica(fondo_de_ojo="papiledema en este momento clinicamente descartado"))
    assert "papila_patologica" not in _active_names(req)

    # B-07: Pseudopapiledema sin alerta de HIC
    req = _make_request(clinica=DatosClinica(fondo_de_ojo="pseudopapiledema por hipermetropia alta, sin edema real"))
    unido = " ".join(corr.evaluar_correlaciones(req)).lower()
    assert "hipertension intracraneal" not in unido

    # B-08: Atrofia optica + sin borramiento de bordes
    req = _make_request(clinica=DatosClinica(fondo_de_ojo="atrofia optica en OD. Papila de OI sin borramiento de bordes."))
    unido = " ".join(corr.evaluar_correlaciones(req)).lower()
    assert "edema de papila" not in unido
    assert "hipertension intracraneal" not in unido

    # B-09 & B-10: DVP y DEP no se reportan como desprendimiento de retina
    req = _make_request(clinica=DatosClinica(fondo_de_ojo="desprendimiento de vitreo posterior con anillo de Weiss"))
    unido = " ".join(corr.evaluar_correlaciones(req)).lower()
    assert "desprendimiento de retina" not in unido
    req = _make_request(clinica=DatosClinica(fondo_de_ojo="desprendimiento del epitelio pigmentario macular"))
    unido = " ".join(corr.evaluar_correlaciones(req)).lower()
    assert "desprendimiento de retina" not in unido

    # B-11: Lattice asintomatica sin desgarros
    req = _make_request(clinica=DatosClinica(fondo_de_ojo="degeneracion lattice en periferia temporal, sin desgarros"))
    unido = " ".join(corr.evaluar_correlaciones(req)).lower()
    assert "urgente" not in unido
    assert "tratamiento profilactico" not in unido

    # B-12: Drusas de papila
    req = _make_request(clinica=DatosClinica(fondo_de_ojo="drusas de papila bilaterales"))
    assert "fondo_macular_dmae" not in _active_names(req)

    # B-13: Pseudofaquia
    req = _make_request(clinica=DatosClinica(anexos_oculares="pseudofaquia con LIO en camara posterior, bien centrado"))
    unido = " ".join(corr.evaluar_correlaciones(req)).lower()
    assert "estadificacion de la opacidad" not in unido

    # B-14: Nistagmo optocinetico
    req = _make_request(clinica=DatosClinica(motilidad_ocular="nistagmo optocinetico presente y simetrico"))
    assert "motilidad_alterada" not in _active_names(req)

    # B-15: magnitud corneal elevada describe datos, sin demostrar ectasia
    req = _make_request(akr=AkrSnapshot(od=AkrOjo(k1_d=42.0, k2_d=46.1, k1_eje=180)))
    assert "queratocono_ectasia_sospecha" in _active_names(req)
    assert not any("ectasia" in t for t in corr.evaluar_correlaciones(req))

    # B-16: Meibomio permeable
    req = _make_request(clinica=DatosClinica(anexos_oculares="glandulas de meibomio permeables y de buena expresibilidad", ojo_seco_but_seg=8))
    assert "ojo_seco_evaporativo_dgm" not in _active_names(req)

    # B-17: Anisocoria calificada de fisiologica
    req = _make_request(clinica=DatosClinica(reflejos_pupilares="anisocoria de 1mm que resulta fisiologica y benigna en este paciente"))
    assert "pupilas_alteradas" not in _active_names(req)

    # B-18: Niega diplopia y cefalea
    req = _make_request(paciente=ContextoPaciente(edad=30, motivo_consulta="niega diplopia y cefalea"), clinica=DatosClinica(cover_test="OD: Exo y Foria | OI: Exo y Foria"))
    assert "cover_exoforia_sintomatica" not in _active_names(req)

    # B-19: Discrepancia AR-Rx 0.50 D
    req = _make_request(paciente=ContextoPaciente(edad=28), clinica=DatosClinica(uso_pantallas="btw2_6"), refraccion=Refraccion(od=GraduacionOjo(esfera=-1.0), oi=GraduacionOjo(esfera=-1.0)), akr=AkrSnapshot(od=AkrOjo(esfera=-1.5), oi=AkrOjo(esfera=-1.5)))
    assert "ar_rx_espasmo_acomodativo" not in _active_names(req)

    # B-20: Vision borrosa sola con pantallas
    req = _make_request(paciente=ContextoPaciente(edad=35, motivo_consulta="vision borrosa"), clinica=DatosClinica(uso_pantallas="btw2_6"))
    assert "cvs_sospecha" in _active_names(req)
    assert not any("sindrome visual informatico" in t for t in corr.evaluar_correlaciones(req))

    # B-21: Tortuosidad vascular aislada
    req = _make_request(clinica=DatosClinica(fondo_de_ojo="tortuosidad vascular aumentada"))
    assert "fondo_hipertensivo" not in _active_names(req)

    # B-21b: Cruces arteriovenosos ambiguos sin patologia (antiguo golden C10-01)
    req = _make_request(clinica=DatosClinica(fondo_de_ojo="Cruces arteriovenosos y tortuosidad vascular."))
    assert "fondo_hipertensivo" not in _active_names(req)

    # B-22: Exudado algodonoso sin dato de diabetes
    req = _make_request(clinica=DatosClinica(fondo_de_ojo="exudado algodonoso peripapilar"))
    unido = " ".join(corr.evaluar_correlaciones(req)).lower()
    assert "control glucemico" not in unido


def test_negacion_quiebre_conector_con_y_cambio_ojo():
    """D1: El conector 'con' rompe la negacion previa ('sin retinopatia diabetica con desgarro...')
    y el marcador de ojo con puntuacion ('en OD,') no oculta la patologia afirmativa."""
    req = _make_request(
        clinica=DatosClinica(
            fondo_de_ojo="sin retinopatia diabetica con desgarro en retina periferica en OD, OI normal"
        )
    )
    names = _active_names(req)
    assert "fondo_periferico_riesgo" in names
    textos = corr.evaluar_correlaciones(req)
    assert any("desgarro" in t.lower() for t in textos)


def test_glaucoma_asimetrico_detecta_rapd_y_defecto_aferente():
    """D2: Terminos tecnicos 'rapd' y 'defecto pupilar aferente' activan la sospecha de asimetria glaucomatosa."""
    req = _make_request(
        clinica=DatosClinica(
            fondo_de_ojo="excavacion papilar OD 0.8, OI 0.4",
            reflejos_pupilares="Se aprecia RAPD en OD.",
        )
    )
    assert "glaucoma_asimetrico" in _active_names(req)

    req2 = _make_request(
        clinica=DatosClinica(
            fondo_de_ojo="OD C/D 0.7 OI C/D 0.3",
            reflejos_pupilares="defecto pupilar aferente en OD",
        )
    )
    assert "glaucoma_asimetrico" in _active_names(req2)


def test_dmae_excluye_drusas_nervio_optico_y_peripapilares():
    """D3: Las drusas del nervio optico o peripapilares no deben confundirse con drusas maculares de DMAE."""
    req = _make_request(
        clinica=DatosClinica(
            fondo_de_ojo="drusas del nervio optico bilaterales, macula libre de lesiones"
        )
    )
    assert "fondo_macular_dmae" not in _active_names(req)

    req2 = _make_request(
        clinica=DatosClinica(
            fondo_de_ojo="drusas peripapilares congenitas, polo posterior normal"
        )
    )
    assert "fondo_macular_dmae" not in _active_names(req2)


def test_aniseiconia_fallback_k1_k2_sin_k_promedio():
    """D4: Si el autorrefractor no calcula k_promedio_d pero reporta k1_d y k2_d,
    la asimetria queratometrica calcula el promedio aritmetico correctamente."""
    req = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-1.00, cilindro=0.00),
            oi=GraduacionOjo(esfera=-4.00, cilindro=0.00),
        ),
        akr=AkrSnapshot(
            od=AkrOjo(k1_d=41.50, k2_d=42.50),  # Promedio 42.00 D
            oi=AkrOjo(k1_d=43.50, k2_d=44.50),  # Promedio 44.00 D -> Dif 2.00 D (>=1.50 D)
        ),
    )
    assert "aniseiconia_queratometrica_severa" not in _active_names(req)
    assert "anisometropia" in _active_names(req)


def test_deficit_visual_inexplicado_dispara_sin_av_sc():
    """D5: La ausencia del registro de AV sin correccion (av_sc=None) no debe bloquear
    el aviso de deficit visual corregido inexplicable (av_cc reducida)."""
    req = _make_request(
        paciente=ContextoPaciente(edad=32),
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-1.50, cilindro=-0.50, av_cc="20/50", av_sc=None),
            oi=GraduacionOjo(esfera=-1.50, cilindro=-0.50, av_cc="20/20", av_sc="20/40"),
        ),
    )
    assert "deficit_visual_inexplicado_refractivo" in _active_names(req)


def test_retiro_lenticular_no_suprime_discrepancia_del_otro_ojo():
    req = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(cilindro=-1.50, eje=0),
            oi=GraduacionOjo(cilindro=-1.50, eje=0),
        ),
        akr=AkrSnapshot(
            od=AkrOjo(k1_d=42, k2_d=45, k1_eje=0, k2_eje=90),
            oi=AkrOjo(k1_d=42, k2_d=42.50),
        ),
    )
    names = _active_names(req)
    assert "astigmatismo_lenticular_puro" not in names
    assert "astigmatismo_corneal_vs_refractivo" in names
    texts = corr.evaluar_correlaciones(req)
    text = dict(evaluar_correlaciones_con_nombres(req))["astigmatismo_corneal_vs_refractivo"]
    assert "OD" in text and "-1.50D" in text and "3.00D" in text
    assert not any("ectopia lentis" in t or "componente astigmatico lenticular" in t for t in texts)


def test_astigmatismo_lenticular_puro_requiere_cilindro_rx():
    """D6: Un cilindro en el autorrefractor desestimado en la Rx final (Rx esferica)
    no debe diagnosticarse como astigmatismo lenticular prescrito."""
    # Caso 1: Cilindro AR de -2.00 pero Rx final 0.00D -> NO debe disparar astigmatismo lenticular
    req_ar_solo = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-1.00, cilindro=0.00),
            oi=GraduacionOjo(esfera=-1.00, cilindro=0.00),
        ),
        akr=AkrSnapshot(
            od=AkrOjo(k1_d=43.00, k2_d=43.25, cilindro=-2.00),
        ),
    )
    assert "astigmatismo_lenticular_puro" not in _active_names(req_ar_solo)

    # Caso 2: Rx con cilindro y K casi iguales tampoco acredita origen lenticular puro.
    req_rx_real = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-1.00, cilindro=-1.75),
            oi=GraduacionOjo(esfera=-1.00, cilindro=0.00),
        ),
        akr=AkrSnapshot(
            od=AkrOjo(k1_d=43.00, k2_d=43.25, cilindro=-1.75),
        ),
    )
    assert "astigmatismo_lenticular_puro" not in _active_names(req_rx_real)


def test_h1_hallazgos_papilares_sin_av_no_inventan_av_reducida():
    """H1: Sin cifra AV registrada no se activa la revisión de AV del adulto mayor."""
    req_isnt = _make_request(
        paciente=ContextoPaciente(edad=68),
        clinica=DatosClinica(fondo_de_ojo="Regla ISNT violada en OD"),
    )
    names_isnt = _active_names(req_isnt)
    assert "fondo_glaucomatoso" in names_isnt
    assert "adulto_mayor_screening" not in names_isnt

    req_asimetrico = _make_request(
        paciente=ContextoPaciente(edad=65),
        clinica=DatosClinica(
            fondo_de_ojo="Excavacion c/d 0.8 en OD, 0.4 en OI.",
            reflejos_pupilares="DPAR positivo en OD",
        ),
    )
    names_asimetrico = _active_names(req_asimetrico)
    assert "glaucoma_asimetrico" in names_asimetrico
    assert "adulto_mayor_screening" not in names_asimetrico


def test_h2_cornea_plana_meridiano_invertido():
    """H2: Si k1_d es 40.50 y k2_d es 37.50 sin promedio, debe detectar cornea plana por el meridiano menor."""
    req = _make_request(
        akr=AkrSnapshot(od=AkrOjo(k1_d=40.50, k2_d=37.50))
    )
    names = _active_names(req)
    assert "cornea_plana_extrema" in names


def test_h3_ar_rx_cambio_cristalino_excluye_pseudofaquia():
    """H3: Si el paciente es pseudofaquico (LIO), no debe atribuirse el cambio refractivo al cristalino biologico."""
    req = _make_request(
        paciente=ContextoPaciente(edad=70, motivo_consulta="Control postquirurgico pseudofaquia bilateral"),
        clinica=DatosClinica(anexos_oculares="Pseudofaquia con LIO centrado bilateral"),
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-1.50, cilindro=-0.50, eje=90),
            oi=GraduacionOjo(esfera=-1.50, cilindro=-0.50, eje=90),
        ),
        akr=AkrSnapshot(
            od=AkrOjo(esfera=-3.50, cilindro=-0.50, eje=90),
            oi=AkrOjo(esfera=-3.50, cilindro=-0.50, eje=90),
        ),
    )
    names = _active_names(req)
    assert "ar_rx_cambio_cristalino" not in names


def test_h4_fondo_glaucomatoso_excavacion_05_fisiologica():
    """H4: Excavacion de 0.5 aislada sin asimetria ni muescas es variante fisiologica normal."""
    req = _make_request(
        clinica=DatosClinica(fondo_de_ojo="Excavacion papilar fisiologica 0.5 simetrica")
    )
    names = _active_names(req)
    assert "fondo_glaucomatoso" not in names


def test_nueva_correlacion_distancia_vertice_alta_ametropia():
    req = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(esfera=-4.50)),
    )
    names = _active_names(req)
    assert "distancia_vertice_alta_ametropia" not in names
    assert corr.evaluar_recordatorios_tecnicos(req)[0][0] == "distancia_vertice_alta_ametropia"


def test_antimetropia_retirada_conserva_anisometropia():
    req = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-1.50, cilindro=0),
            oi=GraduacionOjo(esfera=+1.50, cilindro=0),
        ),
    )
    names = _active_names(req)
    assert "antimetropia_pura_acomodativa" not in names
    assert "anisometropia" in names


def test_retirada_astigmatismo_contra_regla_joven():
    req = _make_request(
        paciente=ContextoPaciente(edad=25),
        refraccion=Refraccion(od=GraduacionOjo(cilindro=-1.75, eje=90)),
    )
    names = _active_names(req)
    assert "astigmatismo_contra_regla_joven" not in names


def test_nueva_correlacion_queratometria_asimetrica_interocular():
    req = _make_request(
        akr=AkrSnapshot(
            od=AkrOjo(k_promedio_d=42.00),
            oi=AkrOjo(k_promedio_d=43.50),
        ),
    )
    names = _active_names(req)
    assert "queratometria_asimetrica_interocular" in names


def test_nueva_correlacion_fondo_oclusion_vascular_urgente():
    req = _make_request(
        clinica=DatosClinica(fondo_de_ojo="Hallazgo de OVCR con exudados y hemorragias"),
    )
    names = _active_names(req)
    assert "fondo_oclusion_vascular_urgente" in names


def test_nueva_correlacion_sintomas_alarma_traccion_vitreoretina():
    req = _make_request(
        paciente=ContextoPaciente(motivo_consulta="Refiere fotopsias recientes y centelleos"),
    )
    names = _active_names(req)
    assert "sintomas_alarma_traccion_vitreoretina" in names


def test_nueva_correlacion_anexos_riesgo_glaucoma_secundario():
    req = _make_request(
        clinica=DatosClinica(anexos_oculares="Signos de pseudoexfoliacion en borde pupilar"),
    )
    names = _active_names(req)
    assert "anexos_riesgo_glaucoma_secundario" in names


def test_nueva_correlacion_ambliopia_isoametropica_bilateral():
    req = _make_request(
        paciente=ContextoPaciente(edad=7),
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=+5.00, av_cc="20/50"),
            oi=GraduacionOjo(esfera=+5.00, av_cc="20/50"),
        ),
    )
    names = _active_names(req)
    assert "ambliopia_isoametropica_bilateral" in names
    assert "deficit_visual_inexplicado_refractivo" not in names


def test_audit_whole_word_obar_no_falso_positivo_en_comprobar():
    req = _make_request(
        clinica=DatosClinica(fondo_de_ojo="se procede a comprobar periferia retinal normal"),
    )
    names = _active_names(req)
    assert "fondo_oclusion_vascular_urgente" not in names


def test_audit_whole_word_pex_no_falso_positivo_en_retinopexia():
    req = _make_request(
        clinica=DatosClinica(anexos_oculares="paciente con antecedente de retinopexia con laser"),
    )
    names = _active_names(req)
    assert "anexos_riesgo_glaucoma_secundario" not in names


def test_audit_whole_word_lio_no_falso_positivo_en_folio():
    req = _make_request(
        clinica=DatosClinica(anexos_oculares="folio 987654 de atencion"),
    )
    names = _active_names(req)
    assert "anexos_patologicos" not in names
    assert "opacidad_cristaliniana" not in names


def test_audit_sintomas_alarma_traccion_moscas_volantes_y_destellos():
    req = _make_request(
        paciente=ContextoPaciente(motivo_consulta="Refiere moscas volantes y destellos de luz recientes"),
    )
    names = _active_names(req)
    assert "sintomas_alarma_traccion_vitreoretina" in names


def test_audit_fondo_glaucomatoso_excavacion_1_0_y_coma_decimal():
    req1 = _make_request(
        clinica=DatosClinica(fondo_de_ojo="e/p 1.0 con rechazo nasal de vasos"),
    )
    assert "fondo_glaucomatoso" in _active_names(req1)

    req2 = _make_request(
        clinica=DatosClinica(fondo_de_ojo="c/d 0,7 bilateral con adelgazamiento de rima"),
    )
    assert "fondo_glaucomatoso" in _active_names(req2)


def test_audit_drusas_papila_y_maculares_coexistentes():
    # Solo drusas de papila: no debe activar DMAE
    req_solo_papila = _make_request(
        clinica=DatosClinica(fondo_de_ojo="drusas de papila en OD"),
    )
    assert "fondo_macular_dmae" not in _active_names(req_solo_papila)

    # Coexistencia: drusas de papila + drusas maculares explícitas: DEBE activar DMAE
    req_coexistencia = _make_request(
        clinica=DatosClinica(fondo_de_ojo="drusas de papila en OD y drusas maculares en OI"),
    )
    assert "fondo_macular_dmae" in _active_names(req_coexistencia)


def test_audit_fondo_oclusion_vascular_crvo_y_trombosis():
    req_crvo = _make_request(
        clinica=DatosClinica(fondo_de_ojo="cuadro clinico compatible con CRVO en OD"),
    )
    assert "fondo_oclusion_vascular_urgente" in _active_names(req_crvo)

    req_trombosis = _make_request(
        clinica=DatosClinica(fondo_de_ojo="trombosis de rama venosa temporal superior"),
    )
    assert "fondo_oclusion_vascular_urgente" in _active_names(req_trombosis)


# ---------------------------------------------------------------------------
# Tests de Auditoría Clínica Formal (10 Hallazgos Críticos)
# ---------------------------------------------------------------------------

def test_audit_fondo_glaucomatoso_relacion_copa_disco():
    """H1: fondo_glaucomatoso debe reconocer 'relacion copa/disco', 'copa/disco', 'copa disco', 'relacion c/d' >= 0.70 por defecto."""
    req1 = _make_request(
        clinica=DatosClinica(fondo_de_ojo="Relacion copa/disco 0.7 en ambos ojos"),
    )
    assert "fondo_glaucomatoso" in _active_names(req1)

    req2 = _make_request(
        clinica=DatosClinica(fondo_de_ojo="copa/disco: 0.8 con palidez temporal"),
    )
    # Palidez + excavacion aumentada se canaliza a papila_patologica (PALIDEZ_EXCAVACION), suprimiendo fondo_glaucomatoso
    assert "papila_patologica" in _active_names(req2)
    assert "fondo_glaucomatoso" not in _active_names(req2)

    req3 = _make_request(
        clinica=DatosClinica(fondo_de_ojo="copa disco 0.6 bilateral"),
    )
    # C/D 0.6 sin mención de microdisco ni asimetría no alcanza el umbral general de 0.70
    assert "fondo_glaucomatoso" not in _active_names(req3)

    req4 = _make_request(
        clinica=DatosClinica(fondo_de_ojo="relacion c/d 0.75"),
    )
    assert "fondo_glaucomatoso" in _active_names(req4)

    # Excavacion fisiologica pura no debe activar
    req_fisiologico = _make_request(
        clinica=DatosClinica(fondo_de_ojo="Relacion copa/disco 0.3 en ambos ojos"),
    )
    assert "fondo_glaucomatoso" not in _active_names(req_fisiologico)


def test_audit_adulto_mayor_miopia_magna_no_suprime_screening():
    """H2: miopia magna es factor de riesgo y NO causa organica; no debe suprimir adulto_mayor_screening."""
    req = _make_request(
        paciente=ContextoPaciente(edad=72),
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-7.00, av_cc="20/60"),
            oi=GraduacionOjo(esfera=-7.00, av_cc="20/60"),
        ),
    )
    names = _active_names(req)
    assert "miopia_magna" in names
    assert "adulto_mayor_screening" in names


def test_aniseiconia_retirada_en_ambas_direcciones_queratometricas():
    """K y Rx no demuestran mecanismo ni aniseiconia en ninguna direccion."""
    # Consistente: ojo mas miope (OI -4.00 vs OD -1.00) tiene cornea mas curva (OI 44.25 vs OD 42.00)
    req_consistente = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-1.00, cilindro=0),
            oi=GraduacionOjo(esfera=-4.00, cilindro=0),
        ),
        akr=AkrSnapshot(
            od=AkrOjo(k_promedio_d=42.00),
            oi=AkrOjo(k_promedio_d=44.25),
        ),
    )
    assert "aniseiconia_queratometrica_severa" not in _active_names(req_consistente)
    assert "anisometropia" in _active_names(req_consistente)

    # Direccion invertida, sin inferir predominio axial: ojo mas miope (OI -4.00 vs OD -1.00) tiene cornea mas PLANA (OI 42.00 vs OD 44.25)
    req_invertida = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-1.00, cilindro=0),
            oi=GraduacionOjo(esfera=-4.00, cilindro=0),
        ),
        akr=AkrSnapshot(
            od=AkrOjo(k_promedio_d=44.25),
            oi=AkrOjo(k_promedio_d=42.00),
        ),
    )
    assert "aniseiconia_queratometrica_severa" not in _active_names(req_invertida)


def test_audit_sintomas_alarma_traccion_miodesopsias_cronicas():
    """H4: miodesopsias cronicas/estables sin fotopsias ni inicio agudo no deben activar alarma urgente."""
    req_cronico = _make_request(
        paciente=ContextoPaciente(motivo_consulta="Moscas volantes desde hace 10 anos, estables"),
    )
    assert "sintomas_alarma_traccion_vitreoretina" not in _active_names(req_cronico)

    # Con fotopsias si debe activar alarma
    req_fotopsias = _make_request(
        paciente=ContextoPaciente(motivo_consulta="Moscas volantes desde hace 10 anos, estables pero con fotopsias recientes"),
    )
    assert "sintomas_alarma_traccion_vitreoretina" in _active_names(req_fotopsias)

    # Con inicio agudo/subito si debe activar alarma
    req_agudo = _make_request(
        paciente=ContextoPaciente(motivo_consulta="Aparicion subita de moscas volantes hace 2 dias"),
    )
    assert "sintomas_alarma_traccion_vitreoretina" in _active_names(req_agudo)


def test_audit_desambiguacion_marcus_gunn():
    """H5: distinguir Marcus Gunn mandibulopalpebral de Marcus Gunn pupilar (DPAR)."""
    # Mandibulopalpebral no es DPAR ni activa glaucoma_asimetrico
    req_mandibular = _make_request(
        clinica=DatosClinica(
            reflejos_pupilares="Fenomeno de Marcus Gunn mandibulopalpebral con ptosis sinaptica",
            fondo_de_ojo="Excavacion c/d 0.8 en OD.",
        ),
    )
    assert "glaucoma_asimetrico" not in _active_names(req_mandibular)

    # Chip Marcus Gunn es DPAR; la ausencia de fecha no demuestra una urgencia nueva.
    req_chip_ambiguo = _make_request(
        clinica=DatosClinica(
            reflejos_pupilares="Marcus Gunn",
        ),
    )
    texts = corr.evaluar_correlaciones(req_chip_ambiguo)
    assert any("defecto pupilar aferente relativo" in t and "retina y via visual aferente" in t for t in texts)
    assert not any("Hallazgo urgente:" in t for t in texts)

    # Marcus Gunn pupilar confirmado con fondo patologico activa glaucoma asimetrico
    req_pupilar = _make_request(
        clinica=DatosClinica(
            reflejos_pupilares="Marcus Gunn: DPAR en OD",
            fondo_de_ojo="Excavacion c/d 0.8 en OD, 0.4 en OI.",
        ),
    )
    assert "glaucoma_asimetrico" in _active_names(req_pupilar)


def test_audit_astig_oblicuo_vs_contra_regla_joven_ejes_70_110():
    """Ejes 70 y 110 no son oblicuos ni justifican el aviso retirado de ectasia."""
    req_70 = _make_request(
        paciente=ContextoPaciente(edad=25),
        refraccion=Refraccion(od=GraduacionOjo(cilindro=-2.50, eje=70)),
    )
    names_70 = _active_names(req_70)
    assert "astigmatismo_contra_regla_joven" not in names_70
    assert "astig_oblicuo" not in names_70

    req_110 = _make_request(
        paciente=ContextoPaciente(edad=25),
        refraccion=Refraccion(od=GraduacionOjo(cilindro=-2.50, eje=110)),
    )
    names_110 = _active_names(req_110)
    assert "astigmatismo_contra_regla_joven" not in names_110
    assert "astig_oblicuo" not in names_110

    # 45 grados sigue siendo oblicuo puro
    req_45 = _make_request(
        paciente=ContextoPaciente(edad=25),
        refraccion=Refraccion(od=GraduacionOjo(cilindro=-2.50, eje=45)),
    )
    names_45 = _active_names(req_45)
    assert "astig_oblicuo" in names_45
    assert "astigmatismo_contra_regla_joven" not in names_45


def test_audit_cornea_plana_no_dispara_con_cola_baja_fisiologica():
    """H9: cornea_plana_extrema exige K < 38.00 D; 38.50 o 39.50 D no deben disparar."""
    req_fisiologico = _make_request(
        akr=AkrSnapshot(od=AkrOjo(k1_d=38.50, k2_d=39.00)),
    )
    assert "cornea_plana_extrema" not in _active_names(req_fisiologico)

    req_patologico = _make_request(
        akr=AkrSnapshot(od=AkrOjo(k1_d=37.20, k2_d=37.50)),
    )
    assert "cornea_plana_extrema" in _active_names(req_patologico)


def test_audit_lenguaje_no_diagnostico_textos():
    """LA API NO DIAGNOSTICA: verificar sustitucion de 'confirma', 'configura un cuadro' y 'compatible con ojo seco clinico'."""
    # astigmatismo_lenticular_puro
    req_astig = _make_request(
        akr=AkrSnapshot(od=AkrOjo(k1_d=43.00, k2_d=43.25)),
        refraccion=Refraccion(od=GraduacionOjo(cilindro=-2.00, eje=180)),
    )
    text_astig = corr.evaluar_correlaciones(req_astig)[0]
    assert "ni establece la causa de la diferencia" in text_astig
    assert "ectopia" not in text_astig
    assert "cristaliniano" not in text_astig
    assert "confirma" not in text_astig

    # but_critico
    req_but = _make_request(clinica=DatosClinica(ojo_seco_but_seg=3))
    text_but = corr.evaluar_correlaciones(req_but)[0]
    assert "compatible con ojo seco clinico" not in text_but
    assert "corroborar la medicion" in text_but
    assert "disfuncion" not in text_but

    # ojo_seco_evaporativo_dgm
    req_dgm = _make_request(clinica=DatosClinica(
        anexos_oculares="Blefaritis anterior y disfuncion meibomio",
        ojo_seco_but_seg=6,
    ))
    texts_dgm = corr.evaluar_correlaciones(req_dgm)
    assert not any("configura un cuadro compatible" in t for t in texts_dgm)
    assert any("alteracion meibomiana descrita" in t for t in texts_dgm)
    assert not any("evaporativo" in t for t in texts_dgm)

    # ar_rx_variabilidad_inespecifica
    req_var = _make_request(
        paciente=ContextoPaciente(edad=45),
        refraccion=Refraccion(od=GraduacionOjo(esfera=0.50)),
        akr=AkrSnapshot(od=AkrOjo(esfera=2.00)),
    )
    texts_var = corr.evaluar_correlaciones(req_var)
    assert not any("compatible con variabilidad refractiva" in t for t in texts_var)
    assert not any("lo que sugiere variabilidad refractiva" in t for t in texts_var)
    assert any("Rx prescrita" in t for t in texts_var)


def test_audit_barrido_completo_no_diagnostico():
    """Los avisos revisados describen datos, sin recuperar inferencias retiradas."""
    from tests.test_correlaciones_golden import GOLDEN

    prohibidas = ("sospecha de ambliopia", "descompensacion forica", "sospecha de ectasia",
                  "demanda acomodativa significativa", "sindrome visual informatico",
                  "sugestivo de un componente corneal", "para confirmar el diagnostico")
    for _, req, _ in GOLDEN:
        for texto in corr.evaluar_correlaciones(req):
            assert not any(p in texto.lower() for p in prohibidas), texto


def test_h03_lattice_con_destellos_activa_urgencia_y_sintomas():
    """H03: lattice con destellos agudos debe activar fondo_periferico_riesgo (urgente) y suprime sintomas_alarma_traccion_vitreoretina."""
    req = _make_request(
        paciente=ContextoPaciente(motivo_consulta="destellos nuevos desde ayer"),
        clinica=DatosClinica(fondo_de_ojo="degeneracion lattice"),
    )
    names = _active_names(req)
    assert "fondo_periferico_riesgo" in names
    assert "sintomas_alarma_traccion_vitreoretina" not in names

    text_fondo = fondo_de_ojo._texto_fondo_periferico_riesgo(req)
    assert "Hallazgo urgente:" in text_fondo
    assert "degeneracion lattice" in text_fondo
    assert "sintomas visuales de inicio reciente" in text_fondo
    assert "valoracion retinologica urgente" in text_fondo
    assert "midriasis" in text_fondo
    assert "educacion sobre sintomas de alarma" not in text_fondo


def test_h03_lattice_asintomatico_mantiene_preventivo():
    """H03: lattice sin sintomas agudos genera recomendacion preventiva sin lenguaje urgente."""
    req = _make_request(
        clinica=DatosClinica(fondo_de_ojo="degeneracion lattice"),
    )
    names = _active_names(req)
    assert "fondo_periferico_riesgo" in names
    assert "sintomas_alarma_traccion_vitreoretina" not in names

    text_fondo = fondo_de_ojo._texto_fondo_periferico_riesgo(req)
    assert "Hallazgo urgente:" not in text_fondo
    assert "exploracion programada de la periferia bajo midriasis" in text_fondo
    assert "educacion al paciente para acudir a revision sin esperar a la cita programada" in text_fondo


def test_h03_desgarro_comprobado_suprime_descarte_subclinico():
    """H03: ante desgarro/rotura comprobado, prevalece la rotura urgente y se suprime sintomas_alarma_traccion_vitreoretina."""
    req = _make_request(
        paciente=ContextoPaciente(motivo_consulta="destellos y fotopsias agudas"),
        clinica=DatosClinica(fondo_de_ojo="desgarro retiniano en herradura"),
    )
    names = _active_names(req)
    assert "fondo_periferico_riesgo" in names
    assert "sintomas_alarma_traccion_vitreoretina" not in names

    text_fondo = fondo_de_ojo._texto_fondo_periferico_riesgo(req)
    assert "Hallazgo urgente:" in text_fondo
    assert "desgarro retiniano" in text_fondo
    assert "posible tratamiento profilactico" not in text_fondo
    assert "indentacion escleral" in text_fondo


def test_h03_otras_lesiones_perifericas_con_fotopsias():
    """H03: baba de caracol o retinosquisis con fotopsias tambien elevan a urgente y suprimen sintomas."""
    req = _make_request(
        paciente=ContextoPaciente(motivo_consulta="fotopsias y destellos recientes"),
        clinica=DatosClinica(fondo_de_ojo="degeneracion en baba de caracol"),
    )
    names = _active_names(req)
    assert "fondo_periferico_riesgo" in names
    assert "sintomas_alarma_traccion_vitreoretina" not in names

    text_fondo = fondo_de_ojo._texto_fondo_periferico_riesgo(req)
    assert "Hallazgo urgente:" in text_fondo
    assert "degeneracion en baba de caracol" in text_fondo


# ============================================================================
# H04: Negaciones ignoradas en varios dominios (P1)
# ============================================================================


def test_h04_cvs_negado_no_activa_sospecha():
    """H04: 'niega ardor y fatiga visual' con pantallas >6h no activa cvs_sospecha."""
    req_neg = _make_request(
        paciente=ContextoPaciente(motivo_consulta="niega ardor y fatiga visual"),
        clinica=DatosClinica(uso_pantallas="gt6"),
    )
    assert "cvs_sospecha" not in _active_names(req_neg)

    # Control positivo: cuando si afirma sintomas
    req_pos = _make_request(
        paciente=ContextoPaciente(motivo_consulta="ardor ocular y fatiga visual"),
        clinica=DatosClinica(uso_pantallas="gt6"),
    )
    assert "cvs_sospecha" in _active_names(req_pos)


def test_h04_acomodacion_negada_no_activa_insuficiencia():
    """H04: 'sin fatiga ni dificultad para enfocar' con add +1 a los 25 anos no afirma sintomas acomodativos.
    La edad y la adicion no prueban un error refractivo; la regla #51 fue retirada."""
    req_neg = _make_request(
        paciente=ContextoPaciente(edad=25, motivo_consulta="sin fatiga ni dificultad para enfocar"),
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=0.0, add=1.00),
            oi=GraduacionOjo(esfera=0.0, add=1.00),
        ),
    )
    names_neg = _active_names(req_neg)
    assert "insuficiencia_acomodacion_joven" not in names_neg
    assert "adicion_incongruente_edad" not in names_neg

    # La astenopia con adicion tampoco demuestra insuficiencia acomodativa; #51 y #52 retiradas
    req_pos = _make_request(
        paciente=ContextoPaciente(edad=25, motivo_consulta="fatiga y dificultad para enfocar de cerca"),
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=0.0, add=1.00),
            oi=GraduacionOjo(esfera=0.0, add=1.00),
        ),
    )
    names_pos = _active_names(req_pos)
    assert "insuficiencia_acomodacion_joven" not in names_pos
    assert "adicion_incongruente_edad" not in names_pos


def test_h04_cover_test_negado_no_activa_tropias():
    """H04: 'sin endotropia ni exotropia' no activa ninguna tropia."""
    req = _make_request(
        clinica=DatosClinica(cover_test="sin endotropia ni exotropia"),
    )
    names = _active_names(req)
    assert "endotropia_lente" not in names
    assert "exotropia_lente" not in names


def test_h04_cover_test_signos_opuestos():
    """H04: frase con signos opuestos 'sin endotropia pero con exotropia' activa solo exotropia."""
    req_exo = _make_request(
        clinica=DatosClinica(cover_test="sin endotropia pero con exotropia manifiesta"),
    )
    names_exo = _active_names(req_exo)
    assert "exotropia_lente" in names_exo
    assert "endotropia_lente" not in names_exo

    req_endo = _make_request(
        clinica=DatosClinica(cover_test="sin exotropia pero con endotropia alternante"),
    )
    names_endo = _active_names(req_endo)
    assert "endotropia_lente" in names_endo
    assert "exotropia_lente" not in names_endo


def test_h04_negacion_bounded_no_genera_falsos_positivos():
    """H04: 'retiniano ' o 'temprano ' no debe activar negacion de palabras posteriores."""
    from app.correlaciones.texto import _find_neg_bounded, _contains_keyword

    # 'retiniano ' termina con 'no ', pero no debe ser detectado como la negacion 'no '
    pos = _find_neg_bounded("desgarro retiniano temporal", "no ")
    assert pos == -1

    pos_real = _find_neg_bounded("desgarro no temporal", "no ")
    assert pos_real == 9

    # Verificacion de palabra temporal tras retiniano
    assert _contains_keyword("desgarro retiniano temporal", ("temporal",), allow_negation_window=True)


def test_h04_hipotesis_descarte_y_antecedente_familiar():
    """H04: 'se descarta queratocono' y 'antecedente familiar de glaucoma' no se afirman como hallazgo personal."""
    from app.correlaciones.texto import _contains_keyword

    # Hipotesis de descarte
    assert not _contains_keyword(
        "se descarta queratocono en cornea",
        ("queratocono",),
        allow_negation_window=True,
    )
    assert not _contains_keyword(
        "sospecha descartada de queratocono",
        ("queratocono",),
        allow_negation_window=True,
    )

    # Antecedente familiar
    assert not _contains_keyword(
        "antecedente familiar de glaucoma en madre",
        ("glaucoma",),
        allow_negation_window=True,
    )
    assert not _contains_keyword(
        "padre con glaucoma",
        ("glaucoma",),
        allow_negation_window=True,
    )


def test_h04_cover_otras_forias_negadas():
    """H04: negaciones en cover test para insuficiencia de convergencia, PPC y desviacion vertical."""
    # Exoforia negada con PPC alejado
    req_exo_neg = _make_request(
        paciente=ContextoPaciente(motivo_consulta="cansancio ocular al leer"),
        clinica=DatosClinica(ppc=12.0, cover_test="sin exoforia ni endotropia"),
    )
    names = _active_names(req_exo_neg)
    assert "ppc_exoforia" not in names
    assert "insuficiencia_convergencia" not in names
    assert "cover_exoforia_sintomatica" not in names

    # Desviacion vertical negada
    req_vert_neg = _make_request(
        clinica=DatosClinica(cover_test="sin hiperforia ni hipotropia"),
    )
    assert "desviacion_vertical" not in _active_names(req_vert_neg)


# ============================================================================
# H05: Ocupacion se transforma en sintoma de insuficiencia de convergencia (P1)
# ============================================================================


def test_h05_ci_sin_sintomas_describe_signos_sin_afirmar_sintomatologia():
    """H05: Paciente programador asintomatico con PPC 8 cm y exoforia describe signos
    objetivos sin afirmar sintomatologia ni diagnosticar insuficiencia de convergencia."""
    req = _make_request(
        paciente=ContextoPaciente(edad=25, ocupacion="programador", motivo_consulta="revision rutinaria sin molestias"),
        clinica=DatosClinica(ppc_cm=8, cover_test="OD: Exo y Foria | OI: Orto"),
    )
    names = _active_names(req)
    assert "insuficiencia_convergencia" not in names
    assert "ppc_exoforia" in names

    texts = corr.evaluar_correlaciones(req)
    assert len(texts) == 1
    t = texts[0]
    assert "PPC de 8 cm" in t
    assert "exoforia en OD" in t
    assert "Verificar el protocolo" in t and "alejado" not in t
    assert "sintomatologia" not in t
    assert "insuficiencia de convergencia" not in t


def test_h05_ppc_6cm_con_exoforia_y_sintomas_describe_coocurrencia():
    """H05: PPC, exoforia y molestias actuales se describen sin diagnóstico CITT."""
    req = _make_request(
        paciente=ContextoPaciente(edad=25, motivo_consulta="fatiga al leer"),
        clinica=DatosClinica(ppc_cm=6, cover_test="exoforia"),
    )
    names = _active_names(req)
    assert "insuficiencia_convergencia" in names
    assert "ppc_exoforia" not in names

    texts = corr.evaluar_correlaciones(req)
    assert any("PPC de 6 cm" in t for t in texts)


def test_h05_ppc_5cm_no_se_declara_normal_ni_alejado():
    """H05: La cifra sola no acredita protocolo ni clasifica normalidad."""
    req = _make_request(
        paciente=ContextoPaciente(edad=25, motivo_consulta="fatiga al leer"),
        clinica=DatosClinica(ppc_cm=5, cover_test="exoforia"),
    )
    names = _active_names(req)
    assert "insuficiencia_convergencia" in names
    # La coocurrencia se resume en #42 sin repetir el mismo aviso en #44.
    assert "cover_exoforia_sintomatica" not in names
    assert not any("alejado" in t for t in corr.evaluar_correlaciones(req))


def test_h05_adulto_ppc_8_y_12cm_no_infiere_causa_por_edad():
    """H05: Ambas cifras se registran con síntomas sin umbral diagnóstico por edad."""
    req_ppc_8 = _make_request(
        paciente=ContextoPaciente(edad=45, motivo_consulta="fatiga al leer"),
        clinica=DatosClinica(ppc_cm=8, cover_test="exoforia"),
    )
    assert "insuficiencia_convergencia" in _active_names(req_ppc_8)

    req_ppc_12 = _make_request(
        paciente=ContextoPaciente(edad=45, motivo_consulta="fatiga al leer"),
        clinica=DatosClinica(ppc_cm=12, cover_test="exoforia"),
    )
    assert "insuficiencia_convergencia" in _active_names(req_ppc_12)


# ============================================================================
# H06: Datos ausentes se interpretan como decisiones o exploraciones realizadas
# ============================================================================


def test_h06_ar_sin_refraccion_subjetiva_no_dispara():
    """H06: Si el AR detecta astigmatismo (-2.00D) pero la refraccion subjetiva final
    no fue capturada/medida en ese ojo, NO se debe asumir que el clinico decidio
    no prescribir cilindro."""
    req = _make_request(
        akr=AkrSnapshot(od=AkrOjo(cilindro=-2.00)),
        # refraccion default vacia (sin esfera ni cilindro)
    )
    names = _active_names(req)
    assert "ar_detecta_astigmatismo_no_prescrito" not in names


def test_h06_ar_con_rx_esferica_si_dispara():
    """H06: Una Rx esférica documenta cilindro 0; ausencia no expresa omisión deliberada."""
    req = _make_request(
        akr=AkrSnapshot(od=AkrOjo(cilindro=-2.00)),
        refraccion=Refraccion(od=GraduacionOjo(esfera=-1.00, cilindro=0.00)),
    )
    names = _active_names(req)
    assert "ar_detecta_astigmatismo_no_prescrito" in names
    texts = corr.evaluar_correlaciones(req)
    assert any("OD: cilindro AR -2.00D y cilindro prescrito +0.00D" in t for t in texts)


def test_h06_ar_con_rx_solo_cilindro_coincidente_no_dispara():
    """H06: Si la Rx subjetiva solo prescribe cilindro (plano / -2.00), el cilindro SI
    fue prescrito y no debe disparar la alerta de astigmatismo no prescrito."""
    req = _make_request(
        akr=AkrSnapshot(od=AkrOjo(cilindro=-2.00)),
        refraccion=Refraccion(od=GraduacionOjo(cilindro=-2.00, eje=180)),
    )
    names = _active_names(req)
    assert "ar_detecta_astigmatismo_no_prescrito" not in names


def test_h06_ar_con_rx_en_otro_ojo_no_activa_ojo_sin_rx():
    """H06: Si OD tiene AR cilindrico pero sin Rx, y OI tiene Rx pero sin cilindro en AR,
    la regla evalua por ojo y no confunde la presencia de Rx en OI con OD."""
    req = _make_request(
        akr=AkrSnapshot(od=AkrOjo(cilindro=-2.00), oi=AkrOjo(cilindro=-0.25)),
        refraccion=Refraccion(oi=GraduacionOjo(esfera=-1.00)),
    )
    names = _active_names(req)
    assert "ar_detecta_astigmatismo_no_prescrito" not in names


def test_h06_equivalente_esferico_con_ausentes():
    """H06: El EE requiere ambos componentes explícitos; un cero es dato válido."""
    from app.correlaciones.refraccion_utils import _equivalente_esferico

    assert _equivalente_esferico(None, None) is None
    assert _equivalente_esferico(-2.0, None) is None
    assert _equivalente_esferico(None, -1.0) is None
    assert _equivalente_esferico(0.0, -1.0) == -0.5
    assert _equivalente_esferico(-2.0, -1.0) == -2.5


def test_h06_av_categoria_no_afirma_correccion_optima():
    """H06: AV con correccion limitada no debe afirmar que la correccion es 'optima'
    cuando no se ha verificado refraccion cicloplejica o refraccion manifiesta certificada."""
    from app.correlaciones.refraccion_utils import _av_categoria

    cat = _av_categoria("20/200")
    assert "AV con correccion registrada" in cat and "pendiente de verificacion" in cat
    assert "severo" not in cat
    assert "optima" not in cat


def test_h06_textos_redactan_datos_disponibles_sin_afirmar_examen_normal():
    """H06: Las reglas de descarte clinico deben referirse a 'datos disponibles'
    en lugar de afirmar que el examen actual fue exhaustivo o normal."""
    from app.correlaciones.contexto import (
        _texto_deficit_visual_inexplicado_refractivo,
        _texto_adulto_mayor_screening,
    )

    req_deficit = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(esfera=-1.00, av_cc="20/50", av_sc="20/100")),
    )
    txt_deficit = _texto_deficit_visual_inexplicado_refractivo(req_deficit)
    assert "segun la edad y el metodo utilizado" in txt_deficit
    assert "sin equipararla a la mejor AV corregida" in txt_deficit
    assert "en el examen actual" not in txt_deficit

    req_adulto = _make_request(
        paciente=ContextoPaciente(edad=70),
        refraccion=Refraccion(od=GraduacionOjo(av_cc="20/50")),
    )
    txt_adulto = _texto_adulto_mayor_screening(req_adulto)
    assert "segun la edad y el metodo utilizado" in txt_adulto
    assert "sin equipararla a la mejor AV corregida" in txt_adulto
    assert "en el examen actual" not in txt_adulto


# ============================================================================
# H07: Interpretacion incompleta de agudeza visual muy baja
# ============================================================================


def test_h07_sub_snellen_categorias_explicitas():
    """H07: Reconocimiento de categorias clinicas explicitas (NPL, PL, MM, CD)
    con soporte para tildes, mayusculas/minusculas, abreviaturas y distancias."""
    from app.correlaciones.refraccion_utils import (
        CATEGORIA_CUENTA_DEDOS,
        CATEGORIA_MOVIMIENTO_MANOS,
        CATEGORIA_NO_PERCEPCION_LUZ,
        CATEGORIA_PERCEPCION_LUZ,
        _av_sub_snellen_categoria,
    )

    # NPL
    assert _av_sub_snellen_categoria("NPL") == CATEGORIA_NO_PERCEPCION_LUZ
    assert _av_sub_snellen_categoria("npl") == CATEGORIA_NO_PERCEPCION_LUZ
    assert _av_sub_snellen_categoria("N.P.L.") == CATEGORIA_NO_PERCEPCION_LUZ
    assert _av_sub_snellen_categoria("NLP") == CATEGORIA_NO_PERCEPCION_LUZ
    assert _av_sub_snellen_categoria("no percepcion de luz") == CATEGORIA_NO_PERCEPCION_LUZ
    assert _av_sub_snellen_categoria("no percepción de luz") == CATEGORIA_NO_PERCEPCION_LUZ
    assert _av_sub_snellen_categoria("sin percepcion de luz") == CATEGORIA_NO_PERCEPCION_LUZ
    assert _av_sub_snellen_categoria("no luz") == CATEGORIA_NO_PERCEPCION_LUZ
    assert _av_sub_snellen_categoria("amaurosis") == CATEGORIA_NO_PERCEPCION_LUZ

    # PL
    assert _av_sub_snellen_categoria("PL") == CATEGORIA_PERCEPCION_LUZ
    assert _av_sub_snellen_categoria("pl") == CATEGORIA_PERCEPCION_LUZ
    assert _av_sub_snellen_categoria("P.L.") == CATEGORIA_PERCEPCION_LUZ
    assert _av_sub_snellen_categoria("LP") == CATEGORIA_PERCEPCION_LUZ
    assert _av_sub_snellen_categoria("percepcion de luz") == CATEGORIA_PERCEPCION_LUZ
    assert _av_sub_snellen_categoria("percepción de luz") == CATEGORIA_PERCEPCION_LUZ
    assert _av_sub_snellen_categoria("proyeccion de luz") == CATEGORIA_PERCEPCION_LUZ
    assert _av_sub_snellen_categoria("light perception") == CATEGORIA_PERCEPCION_LUZ

    # MM
    assert _av_sub_snellen_categoria("MM") == CATEGORIA_MOVIMIENTO_MANOS
    assert _av_sub_snellen_categoria("mm") == CATEGORIA_MOVIMIENTO_MANOS
    assert _av_sub_snellen_categoria("M.M.") == CATEGORIA_MOVIMIENTO_MANOS
    assert _av_sub_snellen_categoria("HM") == CATEGORIA_MOVIMIENTO_MANOS
    assert _av_sub_snellen_categoria("movimiento de manos") == CATEGORIA_MOVIMIENTO_MANOS
    assert _av_sub_snellen_categoria("movimiento de manos a 50 cm") == CATEGORIA_MOVIMIENTO_MANOS
    assert _av_sub_snellen_categoria("mm a 1 m") == CATEGORIA_MOVIMIENTO_MANOS
    assert _av_sub_snellen_categoria("hand motion at 1 ft") == CATEGORIA_MOVIMIENTO_MANOS

    # CD
    assert _av_sub_snellen_categoria("CD") == CATEGORIA_CUENTA_DEDOS
    assert _av_sub_snellen_categoria("cd") == CATEGORIA_CUENTA_DEDOS
    assert _av_sub_snellen_categoria("C.D.") == CATEGORIA_CUENTA_DEDOS
    assert _av_sub_snellen_categoria("CF") == CATEGORIA_CUENTA_DEDOS
    assert _av_sub_snellen_categoria("cuenta dedos") == CATEGORIA_CUENTA_DEDOS
    assert _av_sub_snellen_categoria("cuenta dedos a 50 cm") == CATEGORIA_CUENTA_DEDOS
    assert _av_sub_snellen_categoria("cuenta dedos a 1 metro") == CATEGORIA_CUENTA_DEDOS
    assert _av_sub_snellen_categoria("CD a 30 cm") == CATEGORIA_CUENTA_DEDOS
    assert _av_sub_snellen_categoria("CD 1m") == CATEGORIA_CUENTA_DEDOS
    assert _av_sub_snellen_categoria("CF at 2 feet") == CATEGORIA_CUENTA_DEDOS

    # Desconocidos / no aplicables
    assert _av_sub_snellen_categoria("desconocido") is None
    assert _av_sub_snellen_categoria("no evaluado") is None
    assert _av_sub_snellen_categoria("no colabora") is None
    assert _av_sub_snellen_categoria("20/20") is None
    assert _av_sub_snellen_categoria("") is None
    assert _av_sub_snellen_categoria(None) is None


def test_h07_npl_prioridad_sobre_pl():
    """H07: 'no percepcion de luz' jamas debe resolverse a 4000 (PL).
    Debe categorizarse como NPL con centinela 8000."""
    from app.correlaciones.refraccion_utils import _av_denominator

    # NPL casos
    assert _av_denominator("no percepcion de luz") == 8000
    assert _av_denominator("no percepción de luz") == 8000
    assert _av_denominator("NPL") == 8000
    assert _av_denominator("sin percepcion de luz") == 8000

    # PL casos
    assert _av_denominator("percepcion de luz") == 4000
    assert _av_denominator("percepción de luz") == 4000
    assert _av_denominator("PL") == 4000


def test_h07_denominadores_positivos_y_notaciones_invalidas():
    """H07: Denominadores iguales o menores a cero (ej. '20/0', '6/0', '0.0')
    son matematicamente invalidos y deben retornar None, no cero."""
    from app.correlaciones.refraccion_utils import _av_denominator, _av_es_limitada

    assert _av_denominator("20/0") is None
    assert _av_denominator("20/00") is None
    assert _av_denominator("6/0") is None
    assert _av_denominator("0.0") is None
    assert _av_denominator("0") is None

    # No debe evaluar como agudeza visual limitada
    assert _av_es_limitada("20/0") is False
    assert _av_es_limitada("desconocido") is False


def test_h07_pl_con_tilde_activa_av_cc_limitada():
    """H07: 'percepción de luz' con acento grafico debe normalizarse Unicode
    y activar adecuadamente la correlacion av_cc_limitada."""
    req = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(av_cc="percepción de luz")),
    )
    names = _active_names(req)
    assert "av_cc_limitada" in names

    texts = corr.evaluar_correlaciones(req)
    assert any("OD: AV con correccion registrada de percepción de luz" in t for t in texts)


def test_h07_cd_con_distancia_activa_av_cc_limitada():
    """H07: 'cuenta dedos a 50 cm' debe ser reconocido como baja vision profunda
    y activar av_cc_limitada con calificacion severa."""
    req = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(av_cc="cuenta dedos a 50 cm")),
    )
    names = _active_names(req)
    assert "av_cc_limitada" in names

    texts = corr.evaluar_correlaciones(req)
    assert any("OD: AV con correccion registrada de cuenta dedos a 50 cm" in t for t in texts)


def test_h07_centinelas_orden_y_constantes():
    """H07: Validacion de las constantes centinela ordinales y su separacion
    conceptual de mediciones opticas directas."""
    from app.correlaciones.refraccion_utils import (
        AV_DENOM_CUENTA_DEDOS,
        AV_DENOM_MOVIMIENTO_MANOS,
        AV_DENOM_NO_PERCEPCION_LUZ,
        AV_DENOM_PERCEPCION_LUZ,
        _AV_DENOM_LIMITE,
    )

    # Monotonia de severidad
    assert _AV_DENOM_LIMITE < AV_DENOM_CUENTA_DEDOS < AV_DENOM_MOVIMIENTO_MANOS < AV_DENOM_PERCEPCION_LUZ < AV_DENOM_NO_PERCEPCION_LUZ
    assert AV_DENOM_CUENTA_DEDOS == 1000
    assert AV_DENOM_MOVIMIENTO_MANOS == 2000
    assert AV_DENOM_PERCEPCION_LUZ == 4000
    assert AV_DENOM_NO_PERCEPCION_LUZ == 8000


# ============================================================================
# H08: Invarianza optica por transposicion y meridianos principales en vertice
# ============================================================================


def test_h08_invarianza_miopia_magna():
    """H08: Miopia magna (-7.00 / +2.00 x 90) vs (-5.00 / -2.00 x 180).
    Ambas tienen EE = -6.00 D y deben activar exactamente las mismas reglas."""
    req_plus = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(esfera=-7.00, cilindro=+2.00, eje=90)),
    )
    req_minus = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(esfera=-5.00, cilindro=-2.00, eje=180)),
    )
    assert _active_names(req_plus) == _active_names(req_minus)
    assert "miopia_magna" in _active_names(req_plus)


def test_h08_invarianza_astigmatismo_oblicuo():
    """H08: Astigmatismo oblicuo en notacion plus (plano / +2.50 x 45) vs minus (+2.50 / -2.50 x 135).
    Ambas orientaciones son oblicuas y deben activar astig_oblicuo identicamente."""
    req_plus = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(esfera=0.00, cilindro=+2.50, eje=45)),
    )
    req_minus = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(esfera=+2.50, cilindro=-2.50, eje=135)),
    )
    assert _active_names(req_plus) == _active_names(req_minus)
    assert "astig_oblicuo" in _active_names(req_plus)


def test_h08_invarianza_astigmatismo_contra_regla_joven():
    """H08: En paciente de 24 anos, (-1.00 / -2.00 x 90) en minus-cyl equivale a (-3.00 / +2.00 x 180) en plus-cyl.
    Ambas representan la misma potencia astigmatica contra la regla."""
    req_plus = _make_request(
        paciente=ContextoPaciente(edad=24),
        refraccion=Refraccion(od=GraduacionOjo(esfera=-3.00, cilindro=+2.00, eje=180)),
    )
    req_minus = _make_request(
        paciente=ContextoPaciente(edad=24),
        refraccion=Refraccion(od=GraduacionOjo(esfera=-1.00, cilindro=-2.00, eje=90)),
    )
    assert _active_names(req_plus) == _active_names(req_minus)
    assert "astigmatismo_contra_regla_joven" not in _active_names(req_plus)


def test_h08_distancia_vertice_en_astigmatismo_puro_elevado():
    """H08: Un paciente con cilindro puro de -5.00 D (0.00 / -5.00) tiene un meridiano
    principal de -5.00 D (|potencia| >= 4.00 D), seleccionado para revisión técnica del plano de uso."""
    req = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(esfera=0.00, cilindro=-5.00, eje=180)),
    )
    names = [n for n, _ in corr.evaluar_recordatorios_tecnicos(req)]
    assert "distancia_vertice_alta_ametropia" in names
    texts = [t for _, t in corr.evaluar_recordatorios_tecnicos(req)]
    assert any("S+C -5.00D" in t for t in texts)


def test_h08_distancia_vertice_meridiano_principal_compuesto():
    """H08: (-1.00 / -4.00 x 90) tiene meridiano 1 de -1.00 D y meridiano 2 de -5.00 D.
    El meridiano de -5.00 D amerita distancia al vertice independientemente de que la esfera sea baja."""
    req = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(esfera=-1.00, cilindro=-4.00, eje=90)),
    )
    names = [n for n, _ in corr.evaluar_recordatorios_tecnicos(req)]
    assert "distancia_vertice_alta_ametropia" in names
    texts = [t for _, t in corr.evaluar_recordatorios_tecnicos(req)]
    assert any("S+C -5.00D" in t for t in texts)


def test_h08_cilindro_positivo_puro_sin_esfera_transpone_adecuadamente():
    """Compatibilidad legacy del schema fuera del contrato de cilindro final negativo.
    Esta coerción no valida calcular EE clínico desde componentes ausentes."""
    ojo = GraduacionOjo(cilindro=+2.00, eje=90)
    assert ojo.esfera is None
    assert ojo.cilindro == -2.00
    assert ojo.eje == 180


# ---------------------------------------------------------------------------
# Tests para H09: Queratometria contradictoria y consistencia de parametros
# ---------------------------------------------------------------------------


def test_h09_queratometria_contradictoria_suspende_lenticular_puro():
    """H09: K1=40, K2=46 pero k_cilindro=0 y Rx cyl=-2.
    La discrepancia entre k_cilindro (0) y |K1-K2| (6 D) supera la tolerancia instrumental.
    Debe suspender la inferencia etiologica y NO diagnosticar astigmatismo lenticular puro."""
    from app.correlaciones.queratometria import _queratometria_contradictoria, _corneal_cyl_abs

    akr_ojo = AkrOjo(k1_d=40.00, k2_d=46.00, k_cilindro=0.00)
    assert _queratometria_contradictoria(akr_ojo) is True
    assert _corneal_cyl_abs(akr_ojo) is None

    req = _make_request(
        akr=AkrSnapshot(od=akr_ojo),
        refraccion=Refraccion(od=GraduacionOjo(cilindro=-2.00, eje=180)),
    )
    names = _active_names(req)
    assert "astigmatismo_lenticular_puro" not in names
    assert "astigmatismo_corneal_vs_refractivo" not in names


def test_h09_cornea_plana_invarianza_promedio_redundante():
    """H09: K1=37, K2=43 debe activar cornea_plana_extrema de forma invariante,
    independientemente de que se aporte o no el promedio redundante coherente k_promedio_d=40."""
    req_sin_prom = _make_request(
        akr=AkrSnapshot(od=AkrOjo(k1_d=37.00, k2_d=43.00)),
    )
    req_con_prom = _make_request(
        akr=AkrSnapshot(od=AkrOjo(k1_d=37.00, k2_d=43.00, k_promedio_d=40.00)),
    )

    names_sin = _active_names(req_sin_prom)
    names_con = _active_names(req_con_prom)
    assert "cornea_plana_extrema" in names_sin
    assert "cornea_plana_extrema" in names_con

    text_sin = dict(evaluar_correlaciones_con_nombres(req_sin_prom))["cornea_plana_extrema"]
    text_con = dict(evaluar_correlaciones_con_nombres(req_con_prom))["cornea_plana_extrema"]
    # El hallazgo de K baja conserva fuente, valor y texto al aportar la media.
    assert text_sin == text_con
    assert "OD (K1 registrada 37.00D" in text_sin


def test_h09_queratometria_contradictoria_promedio_discordante():
    """H09: K1=42, K2=44 pero k_promedio_d=48.
    El promedio informado (48) discrepa por 5 D del promedio real (43).
    Se detecta contradiccion y se suspenden inferencias queratometricas dependientes."""
    from app.correlaciones.queratometria import _queratometria_contradictoria, _k_promedio

    akr_ojo = AkrOjo(k1_d=42.00, k2_d=44.00, k_promedio_d=48.00)
    assert _queratometria_contradictoria(akr_ojo) is True
    assert _k_promedio(akr_ojo) is None

    # Asimetria interocular no debe dispararse con datos contradictorios
    req = _make_request(
        akr=AkrSnapshot(
            od=akr_ojo,
            oi=AkrOjo(k1_d=42.00, k2_d=42.50, k_promedio_d=42.25),
        ),
    )
    names = _active_names(req)
    assert "queratometria_asimetrica_interocular" not in names


def test_h09_queratometria_ejes_no_ortogonales():
    """H09: Con astigmatismo corneal significativo (>= 0.75 D), los meridianos principales
    deben ser ortogonales. Si k1_eje=90 y k2_eje=90 (paralelos), es contradictorio."""
    from app.correlaciones.queratometria import _queratometria_contradictoria

    akr_ojo_paralelo = AkrOjo(k1_d=42.00, k1_eje=90, k2_d=45.00, k2_eje=90)
    assert _queratometria_contradictoria(akr_ojo_paralelo) is True

    akr_ojo_ortogonal = AkrOjo(k1_d=42.00, k1_eje=90, k2_d=45.00, k2_eje=180)
    assert _queratometria_contradictoria(akr_ojo_ortogonal) is False


def test_h09_queratometria_eje_cilindro_discordante():
    """H09: El eje del cilindro corneal (k_cilindro_eje) debe coincidir con uno de los
    meridianos principales dentro de tolerancia (<= 20 grados). Si discrepa a 45 grados, es contradictorio."""
    from app.correlaciones.queratometria import _queratometria_contradictoria

    # k1_eje=90, k2_eje=180 -> k_cilindro_eje=45 esta a 45 grados de ambos -> contradictorio
    akr_ojo_discordante = AkrOjo(k1_d=42.00, k1_eje=90, k2_d=45.00, k2_eje=180, k_cilindro=-3.00, k_cilindro_eje=45)
    assert _queratometria_contradictoria(akr_ojo_discordante) is True

    # k_cilindro_eje=95 esta a 5 grados de k1_eje -> valido
    akr_ojo_coherente = AkrOjo(k1_d=42.00, k1_eje=90, k2_d=45.00, k2_eje=180, k_cilindro=-3.00, k_cilindro_eje=95)
    assert _queratometria_contradictoria(akr_ojo_coherente) is False


def test_h09_k_steepest_d_no_confunde_kmax():
    """H09: _k_steepest_d retorna el meridiano queratometrico mas curvo (K steep).
    Se verifica preservacion del alias _k_max y comportamiento none-safe ante contradiccion."""
    from app.correlaciones.queratometria import _k_steepest_d, _k_max, _k_flat_d

    akr_ojo = AkrOjo(k1_d=42.00, k2_d=45.50)
    assert _k_steepest_d(akr_ojo) == 45.50
    assert _k_max(akr_ojo) == 45.50
    assert _k_flat_d(akr_ojo) == 42.00

    akr_contra = AkrOjo(k1_d=40.00, k2_d=46.00, k_cilindro=0.00)
    assert _k_steepest_d(akr_contra) is None
    assert _k_max(akr_contra) is None
    assert _k_flat_d(akr_contra) is None


def test_h09_tolerancia_instrumental_aceptada():
    """H09: Diferencias de redondeo normales (<= 0.50 D) no deben marcarse como contradictorias."""
    from app.correlaciones.queratometria import _queratometria_contradictoria, _corneal_cyl_abs

    # K1=42.12, K2=43.37 (|diff|=1.25 D), k_cilindro=-1.25 D, k_promedio_d=42.75 D
    akr_ojo = AkrOjo(k1_d=42.12, k2_d=43.37, k_cilindro=-1.25, k_promedio_d=42.75)
    assert _queratometria_contradictoria(akr_ojo) is False
    assert _corneal_cyl_abs(akr_ojo) == 1.25


# ---------------------------------------------------------------------------
# Tests H10: AV por ojo y contexto orgánico sin atribuir causa exclusiva
# ---------------------------------------------------------------------------

def test_h10_perdida_oi_con_lattice_od_activa_deficit_inexplicado():
    """H10: Caso de auditoria perdida_OI_con_lattice_OD.
    Lattice periferico en OD no debe silenciar deficit visual inexplicado en OI."""
    req = _make_request(
        paciente=ContextoPaciente(edad=30),
        refraccion=Refraccion(
            oi=GraduacionOjo(esfera=0.00, cilindro=0.00, av_cc="20/100"),
        ),
        clinica=DatosClinica(fondo_de_ojo="OD: lattice periferico. OI: no evaluado"),
    )
    names = _active_names(req)
    assert "fondo_periferico_riesgo" in names
    assert "av_cc_limitada" in names
    assert "deficit_visual_inexplicado_refractivo" in names

    from app.correlaciones.contexto import _texto_deficit_visual_inexplicado_refractivo
    txt = _texto_deficit_visual_inexplicado_refractivo(req)
    assert "AV con correccion 20/100 en OI" in txt


def test_h10_patologia_organica_mismo_ojo_no_demuestra_causa_exclusiva():
    """H10: La palabra catarata no explica por sí sola toda la reducción de AV."""
    req = _make_request(
        paciente=ContextoPaciente(edad=30),
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=0.00, cilindro=0.00, av_cc="20/100"),
        ),
        clinica=DatosClinica(
            anexos_oculares="OD: catarata nuclear moderada. OI: cristalino transparente",
        ),
    )
    names = _active_names(req)
    assert "opacidad_cristaliniana" in names
    assert "deficit_visual_inexplicado_refractivo" in names


def test_h10_caso_mixto_describe_ambos_ojos_sin_causa_exclusiva():
    """H10: AV y hallazgos documentados de ambos ojos se conservan sin inventar etiología."""
    req = _make_request(
        paciente=ContextoPaciente(edad=35),
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-1.00, cilindro=0.00, av_cc="20/100"),
            oi=GraduacionOjo(esfera=-1.00, cilindro=0.00, av_cc="20/80"),
        ),
        clinica=DatosClinica(
            anexos_oculares="OD: catarata nuclear densa. OI: transparente",
            fondo_de_ojo="OD: no valorable por catarata. OI: polo posterior normal",
        ),
    )
    names = _active_names(req)
    assert "opacidad_cristaliniana" in names
    assert "deficit_visual_inexplicado_refractivo" in names

    from app.correlaciones.contexto import _texto_deficit_visual_inexplicado_refractivo
    txt = _texto_deficit_visual_inexplicado_refractivo(req)
    assert "AV con correccion 20/80 en OI" in txt
    assert "AV con correccion 20/100 en OD" in txt


def test_h10_lesion_periferica_mismo_ojo_no_suprime_deficit_central():
    """H10: Lesion periferica (lattice) en el MISMO ojo no tiene capacidad explicativa
    para justificar una agudeza visual central reducida de 20/100."""
    req = _make_request(
        paciente=ContextoPaciente(edad=30),
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=0.00, cilindro=0.00, av_cc="20/100"),
        ),
        clinica=DatosClinica(fondo_de_ojo="OD: degeneracion lattice periferica sin desprendimiento"),
    )
    names = _active_names(req)
    assert "fondo_periferico_riesgo" in names
    assert "deficit_visual_inexplicado_refractivo" in names


def test_h10_sospecha_queratometrica_no_suprime_deficit_inexplicado():
    """H10: Sospecha queratometrica (AKR) no confirma causa organica y no debe
    suprimir deficit_visual_inexplicado_refractivo."""
    req = _make_request(
        paciente=ContextoPaciente(edad=28),
        akr=AkrSnapshot(od=AkrOjo(k1_d=48.00, k2_d=49.50)),
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-2.00, cilindro=-1.50, av_cc="20/60"),
        ),
    )
    names = _active_names(req)
    assert "queratocono_ectasia_sospecha" in names
    assert "deficit_visual_inexplicado_refractivo" in names


def test_h10_adulto_mayor_screening_no_suprimido_por_lattice_contralateral():
    """H10: Anciano de 70 anos con deficit en OD no debe ver suprimido el screening
    por la presencia de lattice periferico en OI."""
    req = _make_request(
        paciente=ContextoPaciente(edad=70),
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=0.00, cilindro=0.00, av_cc="20/40"),
        ),
        clinica=DatosClinica(fondo_de_ojo="OD: no evaluado. OI: lattice periferico"),
    )
    names = _active_names(req)
    assert "adulto_mayor_screening" in names


def test_h10_ambliopia_sospecha_no_suprimida_por_hallazgo_contralateral_incidental():
    """H10: Sospecha de ambliopia en OI no debe suprimirse porque OD tenga una lesion periferica."""
    req = _make_request(
        paciente=ContextoPaciente(edad=20),
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-0.50, cilindro=0, av_cc="20/20"),
            oi=GraduacionOjo(esfera=-3.50, cilindro=0, av_cc="20/60", av_sc="20/200"),
        ),
        clinica=DatosClinica(fondo_de_ojo="OD: lattice periferico. OI: polo posterior normal"),
    )
    names = _active_names(req)
    assert "ambliopia_sospecha" in names


def test_h10_bilateral_deficit_inexplicado_reporta_ambos_ojos():
    """H10: Paciente con deficit inexplicable en ambos ojos reporta ambos ojos."""
    req = _make_request(
        paciente=ContextoPaciente(edad=32),
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-1.00, cilindro=0.00, av_cc="20/60"),
            oi=GraduacionOjo(esfera=-1.00, cilindro=0.00, av_cc="20/80"),
        ),
        clinica=DatosClinica(fondo_de_ojo="Polo posterior normal en ambos ojos"),
    )
    names = _active_names(req)
    assert "deficit_visual_inexplicado_refractivo" in names

    from app.correlaciones.contexto import _texto_deficit_visual_inexplicado_refractivo
    txt = _texto_deficit_visual_inexplicado_refractivo(req)
    assert "AV con correccion 20/60 en OD" in txt
    assert "AV con correccion 20/80 en OI" in txt


# ==============================================================================
# H11: Composicion neurooftalmica sin correspondencia de ojo ni tiempo
# ==============================================================================


def test_h11_neuro_ojos_distintos_no_activa_horner():
    """H11: Miosis en OD y ptosis congenita en OI son contralaterales y congenitas,
    no deben sintetizarse en un sindrome urgente de Horner o III par."""
    req = _make_request(
        clinica=DatosClinica(
            reflejos_pupilares="OD: miosis. OI: normal",
            anexos_oculares="OI: ptosis congenita. OD: normal",
        )
    )
    names = _active_names(req)
    assert "horner_o_tercer_par_sospecha" not in names
    assert "pupilas_alteradas" in names
    assert "anexos_patologicos" in names


def test_h11_ipsilateral_activa_horner():
    """H11: Miosis y ptosis no congenitas en el mismo ojo activan Horner urgente."""
    req = _make_request(
        clinica=DatosClinica(
            reflejos_pupilares="OD: miosis. OI: normal",
            anexos_oculares="OD: ptosis palpebral. OI: normal",
        )
    )
    names = _active_names(req)
    assert "horner_o_tercer_par_sospecha" in names
    assert "pupilas_alteradas" not in names  # Retirada por Horner


def test_h11_ptosis_congenita_ipsilateral_no_activa_urgencia():
    """H11: Ptosis congenita en OD con miosis en OD no debe activar alerta urgente de Horner."""
    req = _make_request(
        clinica=DatosClinica(
            reflejos_pupilares="OD: miosis. OI: normal",
            anexos_oculares="OD: ptosis congenita. OI: normal",
        )
    )
    names = _active_names(req)
    assert "horner_o_tercer_par_sospecha" not in names
    assert "pupilas_alteradas" in names
    assert "anexos_patologicos" in names


def test_h11_filtro_farmacologico_por_ojo_no_contamina_contralateral():
    """H11: Midriasis farmacologica en OI no debe eliminar miosis patologica en OD."""
    req = _make_request(
        clinica=DatosClinica(
            reflejos_pupilares="OD: miosis. OI: midriasis farmacologica por tropicamida",
        )
    )
    names = _active_names(req)
    assert "pupilas_alteradas" in names
    from app.correlaciones.pupilas_motilidad import _pupilas_hallazgos
    hallazgos = _pupilas_hallazgos(req.clinica)
    assert "miosis" in hallazgos
    assert "midriasis" not in hallazgos


def test_h11_golden_anisocoria_se_mantiene():
    """H11: Verifica que la regla golden histórica (anisocoria comparativa + ptosis) siga activa."""
    req = _make_request(
        clinica=DatosClinica(
            anexos_oculares="Ptosis palpebral en OD",
            reflejos_pupilares="Anisocoria pupilar OD > OI",
        )
    )
    names = _active_names(req)
    assert "horner_o_tercer_par_sospecha" in names











