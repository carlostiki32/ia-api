import pytest

from tests.test_ajuste_c24 import cases
from tests.test_auditoria_correlaciones import activas


@pytest.mark.parametrize('case', cases(41), ids=lambda c: c['id'])
def test_c41_compara_solo_cilindros_explicitos_sin_veto_k(case):
    i = int(case['id'].split('-')[1])
    text = activas(**case['entrada']).get('ar_detecta_astigmatismo_no_prescrito', '')
    assert bool(text) == (i not in {2, 4, 5, 8})
    if text:
        assert 'cilindro AR' in text and 'cilindro prescrito' in text
        assert 'revisar las mediciones y el criterio de prescripcion' in text
        assert 'no evalua diferencias de eje' in text
        assert not any(v in text for v in (
            'no incluido', 'no fue incluido', 'subumbral',
            'tolerancia clinica adecuada', 'variabilidad de la medicion',
        ))
    if i in {7, 19}:
        assert 'cilindro prescrito -0.25D' in text
    if i == 17:
        assert 'OI:' in text and 'OD:' not in text
    if i == 15:
        assert 'no fiable' in text


@pytest.mark.parametrize('k', [{}, {'k1_d': 43}, {'k1_d': 43, 'k2_d': 43},
                              {'k1_d': 43, 'k2_d': 43.5}])
def test_c41_cilindro_ocular_no_depende_de_confirmacion_corneal(k):
    text = activas(lente='monofocal', rx_od={'cilindro': 0},
                  akr_od={'cilindro': -3, **k})['ar_detecta_astigmatismo_no_prescrito']
    assert 'cilindro AR -3.00D y cilindro prescrito +0.00D' in text


@pytest.mark.parametrize('rx', [None, 0, -0.25, -0.5])
def test_c41_cero_y_cilindro_parcial_no_son_ausencia(rx):
    result = activas(lente='monofocal', rx_od={'esfera': None, 'cilindro': rx},
                     akr_od={'cilindro': -1})
    assert ('ar_detecta_astigmatismo_no_prescrito' in result) == (rx in {0, -0.25})
