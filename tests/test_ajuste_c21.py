import json
from pathlib import Path
import pytest
from tests.test_auditoria_correlaciones import activas, alertas_h01

CASES=[c for c in json.loads((Path(__file__).parents[1]/'auditoria/2026-09-21/casos.json').read_text(encoding='utf-8')) if c['id'].startswith('C21-')]
POS={1,2,8,15,16,17,18,19,20,21,27,28,29,30,33,34,35,36}
ID='ojo_seco_evaporativo_dgm'

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_c21_hechos_suficientes_sin_etiologia(case):
    n=int(case['id'].split('-')[1]); out=activas(**case['entrada'])
    assert (ID in out)==(n in POS)
    if ID in out:
        text=out[ID]
        assert f"{case['entrada']['but']} segundos" in text
        assert 'Meibomio' in text
        assert all(x not in text for x in ('evaporativo','ojo seco','sospecha','grave','urgente'))
        assert not {'but_critico','but_limitrofe','but_pantallas'} & out.keys()
        assert ID not in alertas_h01(**case['entrada'])

@pytest.mark.parametrize('anexos',['Meibomio normal. Secrecion lagrimal espesa.','Sin disfuncion meibomiana.','Glandulas lagrimales obstruidas.'])
def test_c21_no_importa_anatomia_ni_negacion(anexos):
    assert ID not in activas(lente='monofocal',but=4,anexos=anexos)
