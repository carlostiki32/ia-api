import pytest

from tests.test_ajuste_c24 import cases
from tests.test_auditoria_correlaciones import activas, alertas_h01


@pytest.mark.parametrize('case', cases(32), ids=lambda c: c['id'])
def test_c32_av_documentada_sin_etiologia_ni_discapacidad(case):
    i = int(case['id'].split('-')[1])
    text = activas(**case['entrada']).get('av_cc_limitada', '')
    assert bool(text) == (i not in {1, 2, 3, 4, 17, 31})
    if text:
        assert 'AV con correccion registrada de' in text
        assert 'Verificar medicion y correccion utilizada' in text
        assert 'no acredita mejor AV corregida' in text
        assert 'si persiste reducida' in text.lower()
        assert not any(v in text for v in (
            'leve reduccion', 'reduccion moderada', 'reduccion marcada',
            'deficit visual severo', 'puede explicar', 'irregularidad de la superficie',
        ))
    if i in {20, 21}:
        assert 'pruebas adecuadas a la edad' in text
    if i == 22:
        assert 'AV sin correccion registrada (20/20) es mejor' in text
        assert 'inconsistencia' in text
    if i == 23:
        assert 'AV tomada con lente habitual' in text
    if i == 24:
        assert 'ambliopia conocida estable en seguimiento' in text
    if i == 28:
        assert 'Topografia OD regular, sin ectasia' in text
    if i == 29:
        assert 'medicion no fiable' in text
    if i == 25:
        assert alertas_h01(**case['entrada'])


def test_c32_dato_de_av_sin_esfera_cilindro_es_describible():
    text = activas(lente='monofocal', rx_oi={
        'esfera': None, 'cilindro': None, 'av_cc': '20/40',
    })['av_cc_limitada']
    assert 'OI: AV con correccion registrada de 20/40' in text
    assert 'OD: AV con correccion registrada' not in text
