import pytest
from tests.test_ajuste_c24 import cases
from tests.test_auditoria_correlaciones import _req, alertas_h01
from app.correlaciones.refractivas import _cond_distancia_vertice_alta_ametropia as cond, _texto_distancia_vertice_alta_ametropia as texto
from app.correlaciones.registry import evaluar_correlaciones_con_nombres, evaluar_recordatorios_tecnicos
from app.prompt_builder import build_user_prompt

@pytest.mark.parametrize('case',cases(29),ids=lambda c:c['id'])
def test_c29_recordatorio_tecnico(case):
    i=int(case['id'].split('-')[1]);req=_req(**case['entrada'])
    assert cond(req)==(i not in {1,4,7,11,13,21})
    if cond(req):
        text=texto(req)
        assert text.startswith('Recordatorio tecnico:')
        assert 'si cambia el plano' in text and '|esfera|' not in text
        assert 'clinicamente significativo' not in text
        if i in {8,9,10,11,12}: assert 'S+C' in text
        if i==14: assert 'S+C' not in text
    assert not alertas_h01(**case['entrada'])

@pytest.mark.parametrize('vd',[None,0,12,30])
def test_c29_no_utiliza_vd_akr_como_distancia_subjetiva(vd):
    text=texto(_req(lente='monofocal',rx_od={'esfera':4,'cilindro':-8},akr={'vd':vd}))
    assert 'S +4.00D; S+C -4.00D' in text
    assert 'no las sustituye' in text


def test_c29_excluido_de_hallazgos_medicos_y_prompt():
    req = _req(lente='monofocal', rx_od={'esfera': 4, 'cilindro': 0})
    assert 'distancia_vertice_alta_ametropia' not in dict(evaluar_correlaciones_con_nombres(req))
    assert 'distancia_vertice_alta_ametropia' in dict(evaluar_recordatorios_tecnicos(req))
    assert 'Recordatorio tecnico:' not in build_user_prompt(req)

