import pytest
from tests.test_ajuste_c24 import cases
from tests.test_auditoria_correlaciones import activas, alertas_h01

@pytest.mark.parametrize('case', cases(25), ids=lambda c:c['id'])
def test_c25_contrato_y_alcance(case):
    i=int(case['id'].split('-')[1])
    text=activas(**case['entrada']).get('hipermetropia_alta','')
    assert bool(text)==(i not in {1,3,11,12,13,34})
    if text:
        assert 'magnitud hipermetropica elevada' in text
        assert not any(v in text for v in ('demanda acomodativa significativa','no exclusivamente axial','astigmatismo asociado','Kmax'))
        assert 'angulo segun antecedentes' in text
    if i==33:
        assert 'fiable' in text and 'Verificar' in text

@pytest.mark.parametrize('edad',[None,0,5,18,39,40,65])
def test_c25_edad_no_confirma_anatomia(edad):
    text=activas(lente='monofocal',edad=edad,rx_od={'esfera':5,'cilindro':0})['hipermetropia_alta']
    assert 'no demuestra estrechez angular' in text
    assert 'demanda acomodativa significativa' not in text

@pytest.mark.parametrize('contexto',['OD pseudofaquia con camara profunda','OD gonioscopia abierta hoy','OI afaquia conocida estable'])
def test_c25_contexto_literal_con_lateralidad(contexto):
    text=activas(lente='monofocal',rx_od={'esfera':5,'cilindro':0},anexos=contexto)['hipermetropia_alta']
    assert contexto in text


@pytest.mark.parametrize('motivo', [
    'Dolor ocular intenso de inicio hoy, halos y nauseas.',
    'Hoy dolor ocular intenso, halos y nauseas.',
])
def test_c25_sintomas_actuales_tienen_prioridad_independiente_de_ee(motivo):
    assert alertas_h01(lente='monofocal', motivo=motivo,
                      rx_od={'esfera': 0, 'cilindro': 0})


@pytest.mark.parametrize('motivo', [
    'Halos al conducir, sin dolor ocular ni nauseas.',
    'No presenta dolor ocular, halos ni nauseas.',
    'Hace años tuvo dolor ocular intenso, halos y nauseas; actualmente asintomatico.',
])
def test_c25_controles_no_urgentes(motivo):
    assert not alertas_h01(lente='monofocal', motivo=motivo,
                          rx_od={'esfera': 5, 'cilindro': 0})

