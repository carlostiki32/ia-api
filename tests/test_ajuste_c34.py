"""Aceptacion #34: medias completas y conservacion de la asimetria."""
import pytest
from tests.test_ajuste_c24 import cases
from tests.test_auditoria_correlaciones import activas, alertas_h01

ACTIVE = {2, 3, 4, 5, 6, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 22}


@pytest.mark.parametrize('case', cases(34), ids=lambda c: c['id'])
def test_c34_corpus_contra_orden(case):
    i = int(case['id'].split('-')[1])
    act = activas(**case['entrada'])
    text = act.get('queratometria_asimetrica_interocular', '')
    assert bool(text) == (i in ACTIVE)
    if text:
        assert 'Diferencia de K media registrada entre ojos' in text
        assert 'OD ' in text and 'OI ' in text
        assert not any(v in text for v in ('interocular significativa',
            'sin ectasia corneal manifiesta', 'queratocono frustro',
            'monitorizacion biometrica', 'periodica', 'examen actual'))
        assert not alertas_h01(**case['entrada'])
    if i in {11, 12, 13, 14, 15}:
        assert 'contexto consignado' in text
    if i == 14:
        assert 'no fiable' in text and 'Verificar' in text
    if i == 15:
        assert 'Queratocono OI ya confirmado' in text
    if i == 18:
        assert 'queratocono_ectasia_sospecha' in act
    if i in {19, 20}:
        assert 'queratocono_ectasia_sospecha' not in act
        assert '5.20D' in text


@pytest.mark.parametrize('od,oi', [({'k1_d': 42}, {'k2_d': 44}),
                                 ({'k2_d': 42}, {'k1_d': 44})])
def test_c34_no_compara_meridianos_como_medias(od, oi):
    assert 'queratometria_asimetrica_interocular' not in activas(
        lente='monofocal', akr_od=od, akr_oi=oi)


def test_c34_redundancia_e_intercambio_conservan_diferencia():
    eye_a = {'k1_d': 41.5, 'k2_d': 42.5}
    eye_b = {'k1_d': 42.5, 'k2_d': 43.5}
    for a, b in [(eye_a, eye_b), (eye_b, eye_a),
                 (dict(eye_a, k_promedio_d=42), dict(eye_b, k_promedio_d=43))]:
        text = activas(lente='monofocal', akr_od=a, akr_oi=b)[
            'queratometria_asimetrica_interocular']
        assert '1.00D' in text


@pytest.mark.parametrize('od,oi,activa', [
    ({'k1_d': 42, 'k2_d': 42.01}, {'k1_d': 43, 'k2_d': 43}, False),
    ({'k1_d': 43, 'k2_d': 43}, {'k1_d': 42, 'k2_d': 42.01}, False),
    ({'k_promedio_d': 42.005}, {'k_promedio_d': 43}, False),
    ({'k1_d': 42, 'k2_d': 42.01}, {'k1_d': 43, 'k2_d': 43.01}, True),
    ({'k1_d': 42, 'k2_d': 42}, {'k1_d': 43, 'k2_d': 43.01}, True),
])
def test_c34_umbral_no_redondea_medias_antes_de_comparar(od, oi, activa):
    assert ('queratometria_asimetrica_interocular' in activas(
        lente='monofocal', akr_od=od, akr_oi=oi)) == activa
