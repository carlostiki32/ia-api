import json
from pathlib import Path
import pytest
from tests.test_auditoria_correlaciones import activas, alertas_h01

CASES=[c for c in json.loads((Path(__file__).parents[1]/'auditoria/2026-09-21/casos.json').read_text(encoding='utf-8')) if c['id'].startswith('C23-')]

@pytest.mark.parametrize('case',CASES,ids=lambda c:c['id'])
def test_c23_interpretacion_compartida(case):
    data=case['entrada']; out=activas(**data); but=data.get('but');p=data.get('pantallas')
    assert ('but_limitrofe' in out)==(but is not None and 5<=but<=9 and p in (None,'lt2'))
    if 'but_limitrofe' in out:
        text=out['but_limitrofe']; assert f'{but} segundos' in text
        assert all(x not in text for x in ('leve','grave','ojo seco','urgente'))
        if p is None: assert 'menos de 2' not in text
        assert 'but_limitrofe' not in alertas_h01(**data)
        if case['id']=='C23-25': assert 'poco confiable' in text
        if case['id']=='C23-27': assert 'diez horas' in text

def test_c23_mismo_but_misma_interpretacion_sin_gravedad():
    a=activas(lente='monofocal',but=7)['but_limitrofe']
    b=activas(lente='monofocal',but=7,pantallas='gt6')['but_pantallas']
    assert b.startswith(a)

def test_c23_conserva_fuentes_exposicion_discordantes():
    text=activas(lente='monofocal',but=7,pantallas='lt2',motivo='Trabajo diez horas al dia en computadora.')['but_limitrofe']
    assert 'menos de 2 horas' in text and 'diez horas' in text
