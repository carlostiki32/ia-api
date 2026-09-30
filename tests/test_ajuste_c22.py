import json
from pathlib import Path
import pytest
from tests.test_auditoria_correlaciones import activas, alertas_h01

CASES=[c for c in json.loads((Path(__file__).parents[1]/'auditoria/2026-09-21/casos.json').read_text(encoding='utf-8')) if c['id'].startswith('C22-')]

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_c22_contexto_no_causal(case):
    data=case['entrada']; out=activas(**data); but=data.get('but'); p=data.get('pantallas')
    assert ('but_pantallas' in out)==(but is not None and 5<=but<=9 and p in ('btw2_6','gt6') and 'ojo_seco_evaporativo_dgm' not in out)
    text=out.get('but_pantallas') or out.get('ojo_seco_evaporativo_dgm')
    if text:
        assert f'{but} segundos' in text
        assert ('entre 2 y 6 horas' if p=='btw2_6' else 'mas de 6 horas') in text
        assert all(x not in text for x in ('lo que indica','causado','parpadeo','evaporativo','ojo seco'))
        assert 'but_pantallas' not in alertas_h01(**data)
    if case['id']=='C22-33': assert 'poco confiable' in text

def test_c22_no_confirma_inestabilidad_por_exposicion():
    text=activas(lente='monofocal',but=7,pantallas='gt6')['but_pantallas']
    assert 'valorar la estabilidad' in text
