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


def test_ar_detecta_astigmatismo_no_prescrito_requiere_soporte_queratometrico_si_existe():
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

    assert "ar_detecta_astigmatismo_no_prescrito" not in _active_names(req)


def test_ar_detecta_astigmatismo_no_prescrito_usa_soporte_queratometrico():
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
    assert any("cilindro corneal 1.25D" in text for text in texts)


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

    assert any("demanda acomodativa significativa" in text for text in result)


def test_hipermetropia_alta_menciona_queratometria_plana():
    req = _make_request(
        paciente=ContextoPaciente(edad=45),
        refraccion=Refraccion(od=GraduacionOjo(esfera=+5.50)),
        akr=AkrSnapshot(od=AkrOjo(k_promedio_d=40.00)),
    )

    result = corr.evaluar_correlaciones(req)

    assert any("curvatura corneal plana" in text for text in result)


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
    """La queratometria por si sola (sin cilindro refractivo oblicuo relevante) no
    debe disparar astig_oblicuo: la queratometria solo confirma, nunca dispara
    (ver CORRELACIONES_CLINICAS.md, seccion 5.4)."""
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


def test_astig_oblicuo_confirmado_por_queratometria():
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
    assert any("astigmatismo elevado con eje oblicuo confirmado por queratometria" in text for text in texts)


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


def test_registro_tiene_57_correlaciones_con_nombres_unicos():
    """El paquete por dominio debe seguir registrando exactamente las 57
    correlaciones, con nombres unicos. Blinda el ensamblado de registry.py tras
    el split por dominios y las nuevas expansiones clinicas."""
    names = [c.nombre for c in corr.CORRELACIONES]
    assert len(names) == 57
    assert len(set(names)) == 57


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
    req = _make_request(refraccion=Refraccion(od=GraduacionOjo(av_cc="6/12")))
    result = corr.evaluar_correlaciones(req)
    assert len(result) == 1
    assert "reduccion moderada" in result[0]


def test_av_cc_limitada_acepta_decimal():
    req = _make_request(refraccion=Refraccion(od=GraduacionOjo(av_cc="0.5")))
    assert "av_cc_limitada" in _active_names(req)


def test_av_cc_limitada_no_dispara_en_20_25():
    """20/25 se considera dentro de limites normales (umbral > 25)."""
    req = _make_request(refraccion=Refraccion(od=GraduacionOjo(av_cc="20/25")))
    assert corr.evaluar_correlaciones(req) == []


# --- PPC dependiente de edad (criterio CITT) ---

def test_ppc_exoforia_dispara_en_joven_con_ppc_intermedio():
    req = _make_request(
        paciente=ContextoPaciente(edad=25),
        clinica=DatosClinica(ppc_cm=8),
    )
    assert "ppc_exoforia" in _active_names(req)


def test_ppc_exoforia_no_dispara_en_presbita_con_ppc_intermedio():
    req = _make_request(
        paciente=ContextoPaciente(edad=55),
        clinica=DatosClinica(ppc_cm=8),
    )
    assert "ppc_exoforia" not in _active_names(req)


# --- Correlaciones nuevas disparadas por queratometria ---

def test_queratocono_ectasia_sospecha_dispara_por_curvatura_alta():
    req = _make_request(akr=AkrSnapshot(od=AkrOjo(k2_d=49.00, k_cilindro=-2.00)))
    names = _active_names(req)
    texts = corr.evaluar_correlaciones(req)
    assert "queratocono_ectasia_sospecha" in names
    assert any("queratocono" in text for text in texts)


def test_astigmatismo_corneal_vs_refractivo_dispara_por_discrepancia_de_magnitud():
    req = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(cilindro=-0.75, eje=90)),
        akr=AkrSnapshot(od=AkrOjo(k_cilindro=-3.00, k_cilindro_eje=90)),
    )
    assert "astigmatismo_corneal_vs_refractivo" in _active_names(req)


def test_astigmatismo_corneal_vs_refractivo_dispara_por_discrepancia_de_eje():
    req = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(cilindro=-2.00, eje=90)),
        akr=AkrSnapshot(od=AkrOjo(k_cilindro=-2.00, k_cilindro_eje=180)),
    )
    assert "astigmatismo_corneal_vs_refractivo" in _active_names(req)


def test_astigmatismo_corneal_vs_refractivo_no_dispara_si_concuerdan():
    req = _make_request(
        refraccion=Refraccion(od=GraduacionOjo(cilindro=-2.00, eje=90)),
        akr=AkrSnapshot(od=AkrOjo(k_cilindro=-2.25, k_cilindro_eje=92)),
    )
    assert "astigmatismo_corneal_vs_refractivo" not in _active_names(req)


def test_presbicia_sin_adicion_dispara():
    req = _make_request(
        paciente=ContextoPaciente(edad=50),
        refraccion=Refraccion(od=GraduacionOjo(esfera=+0.50)),
        tipo_lente="monofocal",
    )
    names = _active_names(req)
    assert "presbicia_sin_adicion" in names
    assert "presbicia_multifocal" not in names


def test_presbicia_sin_adicion_no_dispara_si_hay_adicion():
    req = _make_request(
        paciente=ContextoPaciente(edad=50),
        refraccion=Refraccion(od=GraduacionOjo(esfera=+0.50, add=2.00)),
    )
    assert "presbicia_sin_adicion" not in _active_names(req)


def test_presbicia_sin_adicion_no_dispara_en_miope_funcional():
    """Un miope de -2.50 lee quitandose los lentes: la falta de add es lo esperable."""
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
    assert "adicion_incongruente_edad" in _active_names(req)


def test_adicion_incongruente_por_add_en_no_presbita():
    req = _make_request(
        paciente=ContextoPaciente(edad=28),
        refraccion=Refraccion(od=GraduacionOjo(add=1.50)),
    )
    assert "adicion_incongruente_edad" in _active_names(req)


def test_adicion_congruente_no_dispara():
    req = _make_request(
        paciente=ContextoPaciente(edad=60),
        refraccion=Refraccion(od=GraduacionOjo(add=2.25)),
    )
    assert "adicion_incongruente_edad" not in _active_names(req)


def test_hipermetropia_alta_no_dispara_por_astigmatismo_que_infla_el_ee():
    """+1.00 esf +8.00 cil da EE +5.00 pero no es hipermetropia alta (esfera baja).
    La Rx final NO se transpone (ver test_graduacion_ojo_rx_no_se_transpone), de
    modo que el piso de esfera de la correlacion sigue vigente tal como lo exige
    CORRELACIONES_CLINICAS.md 5.2."""
    req = _make_request(refraccion=Refraccion(od=GraduacionOjo(esfera=+1.00, cilindro=+8.00)))
    assert "hipermetropia_alta" not in _active_names(req)


def test_ambliopia_sospecha_por_anisometropia_y_av_limitada():
    req = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-0.50, av_cc="20/20"),
            oi=GraduacionOjo(esfera=-3.00, av_cc="20/60", av_sc="20/200"),
        ),
    )
    names = _active_names(req)
    texts = corr.evaluar_correlaciones(req)
    assert "ambliopia_sospecha" in names
    assert any("ambliopia" in t and "20/200" in t for t in texts)


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


def test_convergencia_usa_ocupacion_como_demanda_proxima():
    """Sin sintoma en el motivo, pero la ocupacion aporta la demanda de cerca."""
    req = _make_request(
        paciente=ContextoPaciente(edad=30, ocupacion="programador", motivo_consulta="revision anual"),
        clinica=DatosClinica(ppc_cm=12, cover_test="OD: Exo y Foria | OI: Orto"),
    )
    assert "insuficiencia_convergencia" in _active_names(req)


# --- Refuerzo de disparadores en texto libre (sinonimos, coloquialismos, abreviaturas) ---

def test_anexos_dispara_por_coloquialismo_carnosidad():
    req = _make_request(clinica=DatosClinica(anexos_oculares="Se observa carnosidad nasal en OD."))
    result = corr.evaluar_correlaciones(req)
    assert "anexos_patologicos" in _active_names(req)
    assert any("pterigion" in t for t in result)


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
    assert any("urgente" in t for t in texts)


def test_campos_dispara_por_vision_tubular():
    req = _make_request(clinica=DatosClinica(confrontacion_campos_visuales="Vision tubular bilateral."))
    assert "campos_visuales_alterados" in _active_names(req)


def test_amsler_dispara_por_micropsia():
    req = _make_request(clinica=DatosClinica(grid_de_amsler="Refiere micropsia en OI."))
    assert "amsler_alterado" in _active_names(req)


def test_fondo_vascular_diabetico_dispara_por_termino_directo():
    req = _make_request(clinica=DatosClinica(fondo_de_ojo="Datos de retinopatia diabetica no proliferativa."))
    assert "fondo_vascular_diabetico" in _active_names(req)


def test_opacidad_cristaliniana_dispara_por_iol():
    req = _make_request(clinica=DatosClinica(anexos_oculares="Se observa IOL en saco capsular en OD."))
    assert "opacidad_cristaliniana" in _active_names(req)


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
    """irma/adie/iol como substring de palabras comunes no deben disparar."""
    r_irma = _make_request(clinica=DatosClinica(fondo_de_ojo="El paciente afirma no tener sintomas."))
    r_adie = _make_request(clinica=DatosClinica(reflejos_pupilares="No hay nadie con anisocoria en la familia."))
    r_iol = _make_request(clinica=DatosClinica(anexos_oculares="Coloracion violeta del parpado por trauma."))
    assert "fondo_vascular_diabetico" not in _active_names(r_irma)
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
    assert any("desviacion vertical no clasificada" in text for text in texts)


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


def test_flat_top_cuenta_como_multifocal_para_presbicia():
    req = _make_request(
        paciente=ContextoPaciente(edad=55),
        refraccion=Refraccion(od=GraduacionOjo(esfera=+1.00, add=2.00)),
        tipo_lente="flat_top",
    )

    names = _active_names(req)
    texts = corr.evaluar_correlaciones(req)

    assert "presbicia_multifocal" in names
    assert any("lente multifocal indicado" in text for text in texts)


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
    # Sin add real, la red de seguridad correcta es presbicia_sin_adicion.
    assert "presbicia_sin_adicion" in names


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
    assert "pupilas_alteradas" not in names  # Suprimida


def test_nueva_correlacion_isnt_violada_papila():
    req = _make_request(
        clinica=DatosClinica(fondo_de_ojo="Regla ISNT violada en papila de OD.")
    )
    names = _active_names(req)
    assert "isnt_violada_papila" in names


def test_nueva_correlacion_cornea_plana_extrema():
    req = _make_request(
        akr=AkrSnapshot(od=AkrOjo(k1_d=38.50, k2_d=39.00))
    )
    names = _active_names(req)
    assert "cornea_plana_extrema" in names


def test_nueva_correlacion_astigmatismo_lenticular_puro():
    req = _make_request(
        akr=AkrSnapshot(od=AkrOjo(k1_d=43.00, k2_d=43.25)),
        refraccion=Refraccion(od=GraduacionOjo(cilindro=-2.00, eje=180)),
    )
    names = _active_names(req)
    assert "astigmatismo_lenticular_puro" in names
    assert "astigmatismo_corneal_vs_refractivo" not in names  # Suprimida


def test_nueva_correlacion_ojo_seco_evaporativo_dgm():
    req = _make_request(
        clinica=DatosClinica(
            anexos_oculares="Blefaritis anterior y disfuncion meibomio",
            ojo_seco_but_seg=6,
        )
    )
    names = _active_names(req)
    assert "ojo_seco_evaporativo_dgm" in names


def test_nueva_correlacion_aniseiconia_queratometrica_severa():
    req = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-1.00),
            oi=GraduacionOjo(esfera=-4.00),
        ),
        akr=AkrSnapshot(
            od=AkrOjo(k_promedio_d=42.00),
            oi=AkrOjo(k_promedio_d=44.25),
        ),
    )
    names = _active_names(req)
    assert "aniseiconia_queratometrica_severa" in names


def test_nueva_correlacion_insuficiencia_acomodacion_joven():
    req = _make_request(
        paciente=ContextoPaciente(edad=22, motivo_consulta="Cansancio visual y fatiga al leer"),
        refraccion=Refraccion(od=GraduacionOjo(add=1.00)),
    )
    names = _active_names(req)
    assert "insuficiencia_acomodacion_joven" in names
    assert "adicion_incongruente_edad" not in names  # Suprimida


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

    # A-05: Blefaritis tras 'ao sin pterigion' sin puntuacion
    req = _make_request(clinica=DatosClinica(anexos_oculares="ao sin pterigion blefaritis moderada bilateral"))
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

    # B-15: Astigmatismo corneal regular 4.10 D con Kmax normal
    req = _make_request(akr=AkrSnapshot(od=AkrOjo(k1_d=42.0, k2_d=46.1, k1_eje=180)))
    assert "queratocono_ectasia_sospecha" not in _active_names(req)

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
    assert "cvs_sospecha" not in _active_names(req)

    # B-21: Tortuosidad vascular aislada
    req = _make_request(clinica=DatosClinica(fondo_de_ojo="tortuosidad vascular aumentada"))
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
    assert "aniseiconia_queratometrica_severa" in _active_names(req)


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

    # Caso 2: Rx final SI prescribe cilindro >= 1.50 con cornea esferica (<=0.50D) -> SI dispara
    req_rx_real = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-1.00, cilindro=-1.75),
            oi=GraduacionOjo(esfera=-1.00, cilindro=0.00),
        ),
        akr=AkrSnapshot(
            od=AkrOjo(k1_d=43.00, k2_d=43.25, cilindro=-1.75),
        ),
    )
    assert "astigmatismo_lenticular_puro" in _active_names(req_rx_real)


def test_h1_suprime_causa_organica_glaucoma_especifico():
    """H1: adulto_mayor_screening debe suprimirse si se detecta ISNT violada o glaucoma asimetrico."""
    req_isnt = _make_request(
        paciente=ContextoPaciente(edad=68),
        clinica=DatosClinica(fondo_de_ojo="Regla ISNT violada en OD"),
    )
    names_isnt = _active_names(req_isnt)
    assert "isnt_violada_papila" in names_isnt
    assert "adulto_mayor_screening" not in names_isnt

    req_asimetrico = _make_request(
        paciente=ContextoPaciente(edad=65),
        clinica=DatosClinica(
            fondo_de_ojo="Excavacion aumentada en papila",
            reflejos_pupilares="DPAR positivo en OD",
        ),
    )
    names_asimetrico = _active_names(req_asimetrico)
    assert "glaucoma_asimetrico" in names_asimetrico
    assert "adulto_mayor_screening" not in names_asimetrico


def test_h2_cornea_plana_meridiano_invertido():
    """H2: Si k1_d es 40.50 y k2_d es 38.50 sin promedio, debe detectar cornea plana por el meridiano menor."""
    req = _make_request(
        akr=AkrSnapshot(od=AkrOjo(k1_d=40.50, k2_d=38.50))
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
    assert "distancia_vertice_alta_ametropia" in names


def test_nueva_correlacion_antimetropia_pura_acomodativa():
    req = _make_request(
        refraccion=Refraccion(
            od=GraduacionOjo(esfera=-1.50),
            oi=GraduacionOjo(esfera=+1.50),
        ),
    )
    names = _active_names(req)
    assert "antimetropia_pura_acomodativa" in names


def test_nueva_correlacion_astigmatismo_contra_regla_joven():
    req = _make_request(
        paciente=ContextoPaciente(edad=25),
        refraccion=Refraccion(od=GraduacionOjo(cilindro=-1.75, eje=90)),
    )
    names = _active_names(req)
    assert "astigmatismo_contra_regla_joven" in names


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




