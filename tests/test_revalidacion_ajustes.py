"""Aceptacion complementaria de ajustes ya declarados implementados."""
import pytest
import json
from pathlib import Path
from datetime import datetime, timedelta, timezone

from tests.test_auditoria_correlaciones import _req, activas, alertas_h01
from app.correlaciones.akr import _akr_comparable
from app.inference import _ensure_emergency_preserved, _ensure_follow_up_last
from tests.test_auditoria_correlaciones import _ANUAL


@pytest.mark.parametrize('fondo,fragmento', [
    ('Hemorragias vitreas OD', 'hemorragia vitrea'),
    ('Roturas retinianas en OI', 'rotura retiniana'),
    ('Agujeros atroficos en OI', 'agujero atrofico'),
    ('Retinosquisis periferica OI con macula normal', 'retinosquisis'),
])
def test_rv01_plural_y_anatomia_independiente(fondo, fragmento):
    assert fragmento in activas(lente='monofocal', fondo=fondo)['fondo_periferico_riesgo']


@pytest.mark.parametrize('fondo', [
    'Desgarro iridiano OD; retina aplicada sin lesiones',
    'Dialisis peritoneal; fondo normal',
    'Dialisis renal; retina aplicada',
])
def test_rv01_no_inventa_lesion_retiniana(fondo):
    assert 'fondo_periferico_riesgo' not in activas(lente='monofocal', fondo=fondo)


@pytest.mark.parametrize('fondo', [
    'Hemorragia vitrea OD en ojo operado de catarata',
    'Antecedente de desgarro tratado OD y desgarro en herradura nuevo OI',
    'Desgarro retiniano OD no tratado',
])
def test_rv01_lesion_actual_no_se_convierte_en_antecedente(fondo):
    assert 'fondo_periferico_riesgo' in alertas_h01(lente='monofocal', fondo=fondo)


def test_rv01_hemorragia_vitrea_explicitamente_antigua_no_es_actual():
    text = activas(lente='monofocal', fondo='Antecedente de hemorragia vitrea OD hace anos')['fondo_periferico_riesgo']
    assert 'antecedente' in text and not text.startswith('Hallazgo urgente:')


@pytest.mark.parametrize('hours', [0, 24, 24.01, -0.001, 2160])
def test_rvt3_metadata_temporal_no_es_filtro_de_datos(hours):
    now = datetime(2026, 9, 26, 12)
    fecha = (now - timedelta(hours=hours)).isoformat()
    req = _req(lente='monofocal', akr={'taken_at': fecha},
               rx_od={'esfera': 0}, akr_od={'esfera': -2})
    assert _akr_comparable(req, ahora=now)
    text = activas(lente='monofocal', akr={'taken_at': fecha},
                   rx_od={'esfera': 0}, akr_od={'esfera': -2})['ar_rx_variabilidad_inespecifica']
    assert 'no acreditan simultaneidad' in text


def test_rvt3_preserva_instante_con_offset():
    req = _req(lente='monofocal', akr={'taken_at': '2026-09-26T06:00:00-06:00'})
    assert req.akr.taken_at.utcoffset() == timedelta(hours=-6)
    assert _akr_comparable(req, ahora=datetime(2026, 9, 26, 12, tzinfo=timezone.utc))
    assert _akr_comparable(req, ahora=datetime(2026, 9, 26, 11, tzinfo=timezone.utc))


def test_rvt3_fechas_mixtas_no_reconstruyen_comparabilidad_temporal():
    req = _req(lente='monofocal', akr={'taken_at': '2026-09-26T06:00:00'})
    assert req.akr.taken_at.utcoffset() is None
    assert _akr_comparable(req, ahora=datetime(2026, 9, 26, 12, tzinfo=timezone.utc))


@pytest.mark.parametrize('motivo,fondo', [
    ('PA 190/100 mmHg', 'Borramiento de bordes papilares OD'),
    ('PA 125/210 mmHg', 'Hemorragias retinianas OD'),
    ('PA 210/125; PA 160/100', 'Hemorragias retinianas OD'),
    ('PA 210/125 mmHg', 'Antecedente de hemorragia retiniana OD resuelta'),
    ('Ejemplo de PA 210/125 mmHg', 'Hemorragias retinianas OD'),
])
def test_rv10_no_fabrica_medicion_ni_papiledema_actual(motivo, fondo):
    assert 'fondo_hipertensivo' not in alertas_h01(lente='monofocal', edad=55, motivo=motivo, fondo=fondo)


def test_rv10_pa_del_paciente_no_se_borra_por_familiar_en_otra_oracion():
    assert 'fondo_hipertensivo' in alertas_h01(
        lente='monofocal', edad=55, motivo='Madre hipertensa. PA actual 190/100 mmHg.', fondo='Hemorragias retinianas OD')


def test_rv10_cruces_normales_no_borran_estrechamiento_afirmado():
    text = activas(lente='monofocal', fondo='Cruces AV conservados con estrechamiento arteriolar focal OD')['fondo_hipertensivo']
    assert 'estrechamiento arteriolar focal en OD' in text


@pytest.mark.parametrize('fondo,fragment', [
    ('Antecedente de neovasos retinianos OD tratados e inactivos. Microaneurismas OI', 'microaneurismas en OI'),
    ('Sin NVD OD, NVD OI activo', 'neovascularizacion papilar en OI'),
    ('NVD OD; NVE OI', 'neovascularizacion retiniana en OI'),
    ('Hemorragia retiniana OD sin OVCR', 'hemorragia retiniana en OD'),
    ('Hemorragia retiniana OD y OVCR OI', 'hemorragia retiniana en OD'),
    ('IRMA OD', 'valoracion retinologica preferente'),
    ('Exudados duros conjuntivales OD; exudados duros retinianos OI', 'exudados duros retinianos en OI'),
])
def test_rv11_hechos_independientes(fondo, fragment):
    assert fragment in activas(lente='monofocal', fondo=fondo)['fondo_vascular_diabetico']


def test_rv11_ojo_desconocido_no_hereda_otro_hallazgo():
    text = activas(lente='monofocal', fondo='Microaneurismas OD. Exudados duros')['fondo_vascular_diabetico']
    assert 'microaneurismas en OD' in text
    assert 'exudados duros (sin lateralidad documentada)' in text


def test_rv11_rubeosis_historica_no_urgente():
    assert 'fondo_vascular_diabetico' not in activas(lente='monofocal', anexos='Antecedente de rubeosis iridis OD resuelta')


def test_rv11_dolor_no_ocular_no_inventa_sintomas_agudos():
    text = activas(lente='monofocal', motivo='Dolor de rodilla desde hoy', fondo='Rubeosis iridis OD')['fondo_vascular_diabetico']
    assert 'sintomas agudos' not in text and 'triage' in text


def test_rv11_hemorragia_prerretiniana_nueva_preserva_h01():
    assert 'fondo_vascular_diabetico' in alertas_h01(lente='monofocal', fondo='Hemorragia prerretiniana nueva OD')


@pytest.mark.parametrize('motivo,control', [
    ('Madre con DM2. Paciente con DM2 en tratamiento', True),
    ('Sospecha de diabetes', False),
    ('Madre con DM2', False),
    ('Niega DM2', False),
])
def test_rv11_diabetes_personal_confirmada_por_hecho(motivo, control):
    text = activas(lente='monofocal', motivo=motivo, fondo='Microaneurismas OD')['fondo_vascular_diabetico']
    assert ('control glucemico' in text) is control


_C58 = [case for case in json.loads((Path(__file__).resolve().parents[1] / 'auditoria/2026-09-21/casos.json').read_text(encoding='utf-8'))
        if case['id'].startswith('C58-')]


@pytest.mark.parametrize('case', _C58, ids=lambda case: case['id'])
def test_rv58_aceptacion_de_los_42_casos_auditados(case):
    number = int(case['id'].split('-')[1])
    out = activas(**case['entrada'])
    key = 'fondo_embolo_retiniano'
    if number in {12, 13, 14, 15, 16, 17, 18, 25, 26, 27, 39}:
        assert key not in out
        return
    text = out[key]
    urgent = number in {3, 4, 8, 9, 10, 11, 28, 29, 34, 35, 37, 38, 42}
    assert text.startswith('Hallazgo urgente:') is urgent
    assert (key in alertas_h01(**case['entrada'])) is urgent
    if urgent:
        assert 'inmediata' in text and 'urgencias' in text and 'ambulatoria' not in text
    elif number in {2, 33}:
        assert 'ambulatoria' in text
    else:
        assert 'precisar sintomas' in text and 'ambulatoria' not in text
    if number in {19, 20, 21, 22, 24, 32, 42}:
        assert 'Hollenhorst' not in text
    if number == 19:
        assert 'calcificado' in text and 'en OD' in text
    if number == 20:
        assert 'plaquetario' in text and 'en OI' in text
    if number == 21:
        assert 'vena retiniana' in text and 'arteriola' not in text
    if number in {22, 23, 24}:
        assert 'en OI' in text
    if number == 31:
        assert 'en AO' in text
    if number == 32:
        assert 'sin lateralidad documentada' in text
    if number == 4:
        assert 'Hollenhorst en OD' in text and 'transitoria en OI' in text
        assert 'no demuestra una relacion causal' in text
    if number == 40:
        assert 'posible placa' in text and 'Verificar el hallazgo' in text


@pytest.mark.parametrize('motivo', [
    'Sin sintomas visuales actuales. Perdida visual transitoria OD esta manana',
    'Sin sintomas visuales actuales; dificultad para hablar de inicio subitamente hoy',
])
def test_rv58_sintoma_positivo_prevalece_sobre_ausencia_generica(motivo):
    text = activas(lente='monofocal', fondo='Placa de Hollenhorst OD', motivo=motivo)['fondo_embolo_retiniano']
    assert text.startswith('Hallazgo urgente:') and 'ambulatoria' not in text


@pytest.mark.parametrize('fields,fragment', [
    ({'fondo': 'Hemorragia prerretiniana nueva OD'}, 'mismo dia'),
    ({'fondo': 'Placa de Hollenhorst OD', 'motivo': 'Perdida visual transitoria OD hoy'}, 'derivacion inmediata'),
    ({'fondo': 'Placa de Hollenhorst OD', 'motivo': 'Dificultad para hablar de inicio subitamente hoy'}, 'evaluacion neurologica'),
])
def test_rvt8_h01_inyecta_y_no_diluye_nuevas_rutas(fields, fragment):
    req = _req(lente='monofocal', seguimiento=_ANUAL, **fields)
    text = _ensure_emergency_preserved('Fondo de ojo normal. Se recomienda control anual.', req)
    text = _ensure_follow_up_last(text, _ANUAL, payload=req)
    assert fragment in text
    assert 'control anual' not in text.lower()
    assert 'revision optometrica anual' not in text.lower()
    assert 'fondo de ojo normal' not in text.lower()


@pytest.mark.parametrize('llm', [
    'Placa de Hollenhorst OD que amerita evaluacion medica ambulatoria.',
    'Placa de Hollenhorst OD que amerita valoracion medica.',
])
def test_rv58_h01_no_acepta_mencion_generica_como_derivacion_inmediata(llm):
    req = _req(lente='monofocal', fondo='Placa de Hollenhorst OD', motivo='Perdida visual subita OD hoy')
    text = _ensure_emergency_preserved(llm, req)
    assert 'derivacion inmediata' in text and 'urgencias' in text
    assert 'ambulatoria' not in text


def test_rv11_h01_no_acepta_valoracion_sin_plazo_en_hemorragia_nueva():
    req = _req(lente='monofocal', fondo='Hemorragia prerretiniana nueva OD')
    text = _ensure_emergency_preserved('Hemorragia prerretiniana OD que amerita oftalmologia.', req)
    assert 'mismo dia' in text


@pytest.mark.parametrize('fondo', ['Posible edema de papila OD', 'Madre con hemorragias retinianas'])
def test_rv10_revision_independiente_no_fabrica_certeza_ni_sujeto(fondo):
    assert 'fondo_hipertensivo' not in alertas_h01(lente='monofocal', edad=55, motivo='PA 190/100 mmHg', fondo=fondo)


def test_rv10_revision_independiente_plan_no_es_hallazgo():
    assert 'fondo_hipertensivo' not in activas(lente='monofocal', fondo='Descartar estrechamiento arteriolar OD')


def test_rv10_revision_independiente_familia_no_borra_pa_personal():
    assert 'fondo_hipertensivo' in alertas_h01(lente='monofocal', edad=55,
        motivo='Madre hipertensa y PA actual del paciente 190/100 mmHg', fondo='Hemorragias retinianas OD')


def test_rv11_revision_independiente_no_reciente():
    text = activas(lente='monofocal', fondo='Hemorragia prerretiniana OD no reciente')['fondo_vascular_diabetico']
    assert not text.startswith('Hallazgo urgente:') and 'preferente' in text


def test_rv11_revision_independiente_dolor_cronico_no_agudo():
    text = activas(lente='monofocal', fondo='Rubeosis OD', motivo='Dolor ocular cronico estable desde hace diez anos')['fondo_vascular_diabetico']
    assert 'sintomas agudos' not in text and 'mismo dia' not in text


def test_rv11_revision_independiente_dolor_contralateral_no_ipsilateral():
    text = activas(lente='monofocal', fondo='Rubeosis OD', motivo='Dolor ocular OI desde hoy')['fondo_vascular_diabetico']
    assert 'sintomas agudos' not in text
    assert 'en iris en OD' in text and 'dolor ocular en OI' in text


def test_rv58_revision_independiente_asintomatico_historico():
    text = activas(lente='monofocal', fondo='Placa de Hollenhorst OD', motivo='Era asintomatico hace diez anos')['fondo_embolo_retiniano']
    assert 'ambulatoria' not in text and 'precisar sintomas' in text


def test_rv58_revision_independiente_historia_de_otro_hecho_no_borra_sintoma():
    assert 'fondo_embolo_retiniano' in alertas_h01(lente='monofocal', fondo='Placa de Hollenhorst OD',
        motivo='Antecedente de catarata operada OD y perdida visual transitoria OD hoy')


def test_rv58_revision_independiente_embolo_sistemico_no_borra_placa():
    text = activas(lente='monofocal', fondo='Placa de Hollenhorst OD y antecedente de embolo pulmonar resuelto')['fondo_embolo_retiniano']
    assert 'Hollenhorst en OD' in text and 'pulmonar' not in text
