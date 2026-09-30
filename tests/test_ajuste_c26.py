import pytest
from tests.test_ajuste_c24 import cases
from tests.test_auditoria_correlaciones import activas

@pytest.mark.parametrize('case',cases(26),ids=lambda c:c['id'])
def test_c26_dictamen(case):
    i=int(case['id'].split('-')[1]);text=activas(**case['entrada']).get('anisometropia','')
    assert bool(text)==(i not in {1,15,16,17,18,19})
    if text:
        assert 'tolerancia binocular con la correccion indicada' in text
        assert not any(v in text for v in ('anisometropia leve','anisometropia moderada','anisometropia severa','compromiso fusional','correccion optica temprana'))
    if i in {7,8}: assert 'signos opuestos' in text
    if i==29: assert 'K promedio' not in text
    if i==32: assert 'fiable' in text

@pytest.mark.parametrize('edad',[8,9,17])
def test_c26_no_frontera_descarte_a_ocho(edad):
    text=activas(lente='monofocal',edad=edad,rx_od={'esfera':0,'cilindro':0},rx_oi={'esfera':2,'cilindro':0})['anisometropia']
    assert 'desarrollo visual' in text

@pytest.mark.parametrize('k', [{'k1_d':42},{'k2_d':42}])
def test_c26_meridiano_aislado_no_media(k):
    text=activas(lente='monofocal',rx_od={'esfera':0,'cilindro':0},rx_oi={'esfera':2,'cilindro':0},akr_od=k,akr_oi={'k1_d':44})['anisometropia']
    assert 'K promedio' not in text
