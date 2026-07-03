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

    assert len(result) == 1
    assert "demanda acomodativa significativa" in result[0]


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


def test_registro_tiene_41_correlaciones_con_nombres_unicos():
    """El paquete por dominio debe seguir registrando exactamente las 41
    correlaciones, con nombres unicos. Blinda el ensamblado de registry.py tras
    el split por dominios."""
    names = [c.nombre for c in corr.CORRELACIONES]
    assert len(names) == 41
    assert len(set(names)) == 41


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
