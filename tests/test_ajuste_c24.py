import json
from pathlib import Path
import pytest
from tests.test_auditoria_correlaciones import activas, alertas_h01, _req
from app.correlaciones.refraccion_utils import _equivalente_esferico
from app.correlaciones.queratometria import _format_corneal_irregularity


def cases(number):
    data = json.loads((Path(__file__).parents[1] / 'auditoria/2026-09-21/casos.json').read_text(encoding='utf-8'))
    return [c for c in data if c['id'].startswith(f'C{number:02d}-')]


@pytest.mark.parametrize('case', cases(24), ids=lambda c: c['id'])
def test_c24_corpus_contra_dictamen(case):
    i = int(case['id'].split('-')[1])
    result = activas(**case['entrada'])
    text = result.get('miopia_magna', '')
    assert bool(text) == (i not in {1, 4, 10, 26, 30})
    if text:
        assert 'retina central y periferica' in text
        assert not any(s in text for s in ('muy alta', 'significativamente elevado', 'no exclusivamente axial', 'antes de asumir', 'Kmax'))
    if i == 11:
        assert 'EE exacto no calculable' in text and 'EE -6.00' not in text
    if i in {13, 14, 15, 20}:
        assert 'componente corneal' not in text
    if i == 23:
        assert 'provisionalmente' in text and 'Verificar' in text
    if i == 21:
        assert 'sin lesiones' in text
    if i == 32:
        assert 'OI: miopia patologica conocida con atrofia estable' in text
    if i == 28:
        assert alertas_h01(**case['entrada'])
    elif i in {2, 6}:
        assert not alertas_h01(**case['entrada'])


@pytest.mark.parametrize('s,c,expected', [(None,None,None),(None,-2,None),(-6,None,None),(0,0,0),(-5.75,-.5,-6)])
def test_c24_ee_no_imputa(s,c,expected):
    assert _equivalente_esferico(s,c) == expected


@pytest.mark.parametrize('eye,label', [({'k1_d':48,'k2_d':49},'mayor meridiano registrado'),({'k_promedio_d':48.7},'K promedio registrada')])
def test_c24_fuente_queratometrica(eye,label):
    text = _format_corneal_irregularity(_req(lente='monofocal', akr_od=eye))
    assert label in text and 'Kmax' not in text
