"""Contrapruebas de ambas auditorías: contrato, sujeto y negación por ocurrencia."""
import pytest

from app.clinical_data import has_clinical_data
from app.correlaciones.hechos_textuales import _certeza_local, _es_hipotetico, _sujeto_es_paciente
from app.correlaciones.registry import evaluar_correlaciones_con_nombres
from app.correlaciones.texto import _contains_keyword, _normalize_text
from app.schemas import AkrOjo, DatosClinica, GraduacionOjo, ImpresionClinicaRequest


@pytest.mark.parametrize("texto,paciente,hipotesis", [
    ("Mi madre tiene diabetes y perdida visual desde hoy.", False, False),
    ("Mi padre presento perdida visual desde hoy.", False, False),
    ("Mi padre perdio vision: perdida visual desde hoy.", False, False),
    ("Presento perdida visual desde hoy mientras cuido a mi madre.", True, False),
    ("Mi madre tiene diabetes y el paciente refiere perdida visual desde hoy.", True, False),
    ("Mi madre tiene diabetes y yo presento perdida visual desde hoy.", True, False),
    ("Mi madre tuvo fotopsias y yo tengo perdida visual desde hoy.", True, False),
    ("Mi madre tiene diabetes, paciente: perdida visual desde hoy.", True, False),
    ("Perdida visual en la madre.", False, False),
    ("Si presentara perdida visual, volveria.", True, True),
    ("Acudir si hay perdida visual.", True, True),
    ("En caso de perdida visual acudir.", True, True),
    ("Posible perdida visual OD.", True, False),
])
def test_sujeto_y_modalidad_conservan_offsets(texto, paciente, hipotesis):
    texto = _normalize_text(texto)
    i = texto.index("perdida visual")
    assert _sujeto_es_paciente(texto, i, i + 14) is paciente
    assert _es_hipotetico(texto, i, i + 14) is hipotesis


@pytest.mark.parametrize("texto,keyword,esperado", [
    ("No se observa en OD desgarro retiniano.", "desgarro", False),
    ("Sin evidencia en OD de desprendimiento de retina.", "desprendimiento", False),
    ("OD sin desgarro retiniano.", "desgarro", False),
    ("OD sin edema; OI edema retiniano.", "edema", True),
    ("OD sin edema OI edema retiniano.", "edema", True),
    ("Sin edema OD y edema OI.", "edema", True),
    ("No hay edema OD ni edema OI.", "edema", False),
    ("No hay edema OD o edema OI.", "edema", False),
])
def test_negacion_no_se_rompe_por_localizador_ocular(texto, keyword, esperado):
    assert _contains_keyword(texto, (keyword,), allow_negation_window=True) is esperado


@pytest.mark.parametrize("texto,keyword,certeza", [
    ("Probable embolo OD.", "embolo", "probable"),
    ("Posible desgarro OD.", "desgarro", "posible"),
    ("Posibles fotopsias desde ayer.", "fotopsias", "posible"),
    ("Fotopsias posibles desde ayer.", "fotopsias", "posible"),
    ("Se observa muesca OD, para descartar glaucoma.", "muesca", None),
    ("Se observa muesca OD, para descartar glaucoma.", "glaucoma", "a descartar"),
])
def test_certeza_por_hallazgo(texto, keyword, certeza):
    texto = _normalize_text(texto)
    i = texto.index(keyword)
    assert _certeza_local(texto, i, i + len(keyword)) == certeza


def test_atribucion_familiar_despues_de_valor_y_calificador():
    assert not _sujeto_es_paciente("bcva maxima 20/20 en la madre", 0, 4)
    assert _sujeto_es_paciente("bcva maxima 20/20 mientras cuido a mi madre", 0, 4)
    assert not _sujeto_es_paciente("mi padre perdio la mitad del campo visual", 9, 39)
    assert _es_hipotetico("si se midiera but poco confiable, se repetiria", 14, 17)
    assert not _sujeto_es_paciente("madre operada de catarata hace tres dias", 16, 24)


@pytest.mark.parametrize("modelo", [GraduacionOjo, AkrOjo])
def test_transposicion_conserva_ausencia_distinta_de_plano(modelo):
    assert modelo(cilindro=2, eje=90).esfera is None
    assert modelo(esfera=0, cilindro=2, eje=90).esfera == 2


def test_esfera_ar_ausente_no_genera_diferencia_inventada():
    req = ImpresionClinicaRequest(receta_id="null-ar", refraccion={"od": {"esfera": 0}},
                                  akr={"od": {"cilindro": 2, "eje": 90}})
    assert "ar_rx_variabilidad_inespecifica" not in dict(evaluar_correlaciones_con_nombres(req))


@pytest.mark.parametrize("cilindro", [-8, -12, -30])
def test_cilindro_persistido_conserva_rango_contractual(cilindro):
    assert GraduacionOjo(cilindro=cilindro).cilindro == cilindro


def test_seguimiento_contractual_conserva_ultima_recomendacion():
    texto = "Seguimiento previo. " * 100 + "Próxima cita en: 2 semanas."
    assert DatosClinica(recomendacion_seguimiento=texto).recomendacion_seguimiento == texto
    assert len(DatosClinica(recomendacion_seguimiento="x" * 60001).recomendacion_seguimiento) == 60000


@pytest.mark.parametrize("akr", [{"ticket_id": 42}, {"taken_at": "2026-09-29"},
                                {"vd": 12}, {"ker_index": 1.3375}, {"pd": 62}])
def test_metadatos_akr_no_habilitan_impresion(akr):
    assert not has_clinical_data(ImpresionClinicaRequest(receta_id="meta", akr=akr))


def test_k_media_baja_no_desaparece_con_meridiano_parcial():
    req = ImpresionClinicaRequest(receta_id="media", akr={"od": {"k2_d": 39, "k_promedio_d": 37.99}})
    texto = dict(evaluar_correlaciones_con_nombres(req))["cornea_plana_extrema"]
    assert "K promedio registrada 37.99D" in texto
    assert "K1" not in texto and "K2 registrada 37.99D" not in texto


@pytest.mark.parametrize("motivo,activo", [
    ("Desde hoy diplopia binocular vertical de inicio subito.", True),
    ("Fatiga ocular resuelta, ahora diplopia desde hoy.", True),
    ("Desde hoy presento diplopia mientras cuido a mi madre.", True),
    ("Mi madre tiene diabetes y diplopia desde hoy.", False),
    ("Niega diplopia de inicio reciente.", False),
    ("Diplopia desde 2020, estable sin cambios.", False),
    ("Si presentara diplopia desde hoy volveria.", False),
    ("Si presento diplopia subita OD, debo volver.", False),
])
def test_c27_diplopia_prioridad_independiente_de_refraccion(motivo, activo):
    from app.inference import _get_active_emergency_alerts, _ensure_emergency_preserved
    req = ImpresionClinicaRequest(receta_id="c27-cierre", paciente={"motivo_consulta": motivo},
                                  refraccion={"od": {"esfera": -.75, "cilindro": 0},
                                              "oi": {"esfera": .75, "cilindro": 0}})
    correlaciones = dict(evaluar_correlaciones_con_nombres(req))
    assert ("diplopia_aguda" in correlaciones) is activo
    assert "antimetropia_pura_acomodativa" not in correlaciones
    assert "anisometropia" in correlaciones
    assert bool(_get_active_emergency_alerts(req)) is activo
    final = _ensure_emergency_preserved("Se recomienda control anual.", req)
    if activo:
        assert "mismo dia" in _normalize_text(final)
        assert "diplopia" in final and "control anual" not in final
        assert _ensure_emergency_preserved(final, req) == final


@pytest.mark.parametrize("clinica,motivo,degradado,plazo", [
    ({"fondo_de_ojo": "Papiledema bilateral."}, None,
     "Edema de papila que requiere valoracion oftalmologica.", "24 horas"),
    ({"fondo_de_ojo": "Drusas blandas maculares OD.", "grid_de_amsler": "Metamorfopsia nueva OD."}, None,
     "Hallazgos maculares OD que requieren OCT macular y derivacion a retina.", "1 dia habil"),
    ({}, "Fotopsias OD desde ayer.",
     "Fotopsias OD que requieren evaluacion oftalmologica.", "48 horas"),
    ({}, "Diplopia OD desde hoy.",
     "Diplopia de inicio reciente que requiere evaluacion el mismo dia.", "mismo dia"),
])
def test_h01_no_acepta_valoracion_generica_sin_plazo_o_sin_ojo(clinica, motivo, degradado, plazo):
    from app.inference import _ensure_emergency_preserved
    req = ImpresionClinicaRequest(receta_id="h01-cierre", clinica=clinica, paciente={"motivo_consulta": motivo, "edad": 70})
    final = _ensure_emergency_preserved(degradado, req)
    assert plazo in _normalize_text(final)
    if "Diplopia" in degradado:
        assert "OD" in final
    assert _ensure_emergency_preserved(final, req) == final


@pytest.mark.parametrize("degradado", [
    "Presenta diplopia OD. Hoy vino para renovar su receta. Se recomienda valoracion urgente cuando sea posible.",
    "La madre presenta diplopia OD desde hoy. Se recomienda valoracion urgente el mismo dia.",
])
def test_h01_no_toma_fecha_de_consulta_ni_hallazgo_de_familiar(degradado):
    from app.inference import _ensure_emergency_preserved, _get_active_emergency_alerts
    req = ImpresionClinicaRequest(receta_id="revision-independiente", paciente={"motivo_consulta": "Presento diplopia OD desde hoy."})
    alerta = next(a for a in _get_active_emergency_alerts(req) if a.id == "diplopia_aguda")
    final = _ensure_emergency_preserved(degradado, req)
    assert alerta.texto_determinista in final
    assert "La madre presenta" not in final
    assert "cuando sea posible" not in final
    assert _ensure_emergency_preserved(final, req) == final
