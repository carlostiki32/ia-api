import pytest
from tests.test_ajuste_c24 import cases
from tests.test_auditoria_correlaciones import activas

@pytest.mark.parametrize('case',cases(30),ids=lambda c:c['id'])
def test_c30_orientacion_descriptiva(case):
    i=int(case['id'].split('-')[1]);text=activas(**case['entrada']).get('astig_oblicuo','')
    # Orden #30 A/C: bandas abiertas (20,70) y (110,160).
    # C30-03/07 son 69/159 (dentro); C30-04/08 son 70/160 (fuera).
    assert bool(text)==(i not in {1,4,5,8,9,10,11,14,21,22})
    if text:
        assert 'prescripcion registra cilindro' in text
        assert not any(v in text for v in ('muy alta','astigmatismo alto','concordante con','amerita topografia'))
    if i in {24,25,28,29}: assert 'aproximadamente coincidente' in text
    if i in {26,27,30,31,32}: assert 'aproximadamente coincidente' not in text
    if i==36: assert 'fiable' in text and 'Verificar' in text

@pytest.mark.parametrize('c,e',[(-2.5,45),(-2.5,135)])
def test_c30_cilindro_sin_esfera_describible(c,e):
    text=activas(lente='monofocal',rx_od={'esfera':None,'cilindro':c,'eje':e})['astig_oblicuo']
    assert f'{e} grados' in text
