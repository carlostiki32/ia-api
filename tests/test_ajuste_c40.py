from datetime import datetime, timezone

import pytest

from app.correlaciones.akr import _akr_comparable
from tests.test_ajuste_c24 import cases
from tests.test_auditoria_correlaciones import _req, activas


@pytest.mark.parametrize('case', cases(40), ids=lambda c: c['id'])
def test_c40_diferencia_descriptiva_con_componentes_explicitos(case):
    i = int(case['id'].split('-')[1])
    text = activas(**case['entrada']).get('ar_rx_variabilidad_inespecifica', '')
    assert bool(text) == (i not in {2, 5, 7, 10, 12})
    if text:
        assert 'Diferencia entre registros:' in text
        assert 'diferencia absoluta' in text
        assert 'Rx prescrita' in text
        assert 'no acreditan simultaneidad' in text
        assert 'no establece su causa ni inestabilidad refractiva' in text
        assert 'queratometria' not in text
    if i == 8:
        assert 'esfera AR -1.50D' in text and 'cilindro AR' not in text
    if i in {6, 9}:
        assert 'cilindro AR -1.50D' in text and 'esfera AR' not in text
    if i == 21:
        assert 'OI:' in text and 'OD:' not in text
    if i == 22:
        assert 'OD:' in text and 'OI:' in text


@pytest.mark.parametrize('fecha', [None, '2020-01-01 12:00:00', '2030-01-01 12:00:00',
                                  '2026-09-29T12:00:00-06:00'])
def test_c40_fechas_no_inventan_comparabilidad_ni_silencian_datos(fecha):
    req = _req(lente='monofocal', akr={'taken_at': fecha},
               rx_od={'esfera': 0, 'cilindro': 0}, akr_od={'esfera': -1.5})
    assert _akr_comparable(req, ahora=datetime(2026, 9, 29, tzinfo=timezone.utc))
    from app.correlaciones.akr import _cond_ar_rx_variabilidad_inespecifica
    assert _cond_ar_rx_variabilidad_inespecifica(req)
