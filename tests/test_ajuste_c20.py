import json
from pathlib import Path
import pytest
from tests.test_auditoria_correlaciones import activas, alertas_h01

CASES = [c for c in json.loads((Path(__file__).parents[1]/'auditoria/2026-09-21/casos.json').read_text(encoding='utf-8')) if c['id'].startswith('C20-')]

@pytest.mark.parametrize('case', CASES, ids=lambda c:c['id'])
def test_c20_contrato_y_aviso(case):
    data=case['entrada']; out=activas(**data); but=data.get('but')
    # #21 fusiona el aviso de BUT cuando hay una anomalia meibomiana real.
    assert ('but_critico' in out) == (but is not None and but < 5 and 'ojo_seco_evaporativo_dgm' not in out)
    if 'but_critico' in out:
        text=out['but_critico']
        assert f'{but} segundos' in text
        assert all(k not in text.lower() for k in ('grave','evaporativo','marcadamente','ojo seco','urgente'))
        assert 'but_critico' not in alertas_h01(**data)
    if case['id']=='C20-26': assert 'poco confiable' in out['but_critico']
    if case['id']=='C20-29': assert 'tecnica con fluoresceina' in out['but_critico']
    if case['id']=='C20-30': assert 'tecnica no invasiva' in out['but_critico']

def test_c20_no_importa_fiabilidad_de_amsler():
    text=activas(lente='monofocal',but=4,motivo='Amsler: prueba poco confiable.')['but_critico']
    assert 'poco confiable' not in text
