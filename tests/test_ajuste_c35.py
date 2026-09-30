"""Aceptacion #35: K baja por fuente; no etiologia ni biometria automatica."""
import pytest
from tests.test_ajuste_c24 import cases
from tests.test_auditoria_correlaciones import activas, alertas_h01

ACTIVE = {1, 4, 5, 6, 7, 8, 10, 11, 12, 13, 14, 15, 16, 17, 19, 21}


@pytest.mark.parametrize('case', cases(35), ids=lambda c: c['id'])
def test_c35_corpus_contra_orden(case):
    i = int(case['id'].split('-')[1])
    act = activas(**case['entrada'])
    text = act.get('cornea_plana_extrema', '')
    assert bool(text) == (i in ACTIVE)
    if text:
        assert 'valor de curvatura bajo' in text and 'Verificar lectura' in text
        assert not any(v in text for v in ('CNA1', 'CNA2', 'monitorizacion biometrica',
            'microftalmos', 'cierre angular', 'variante anatomica', 'cornea plana verdadera'))
        assert not alertas_h01(**case['entrada'])
    if i == 4:
        assert 'K promedio registrada 37.99D' in text
        assert 'K1 registrada' not in text
    if i in {5, 6, 7, 21}:
        assert 'K1 registrada 37.00D' in text
    if i == 8:
        assert 'K2 registrada 37.00D' in text and 'queratometria parcial' in text
        assert 'K1 registrada' not in text
    if i in {12, 13, 14, 15}:
        assert 'contexto consignado' in text
    if i == 14:
        assert 'Cornea plana congenita ya diagnosticada' in text
    if i == 21:
        assert 'queratocono_ectasia_sospecha' in act
        assert 'anatomia global' in text


def test_c35_redundancia_no_transforma_minimo_en_media():
    eye = {'k1_d': 37, 'k2_d': 43}
    for k in (eye, dict(eye, k_promedio_d=40)):
        text = activas(lente='monofocal', akr_od=k)['cornea_plana_extrema']
        assert 'K1 registrada 37.00D' in text and 'K promedio registrada' not in text


@pytest.mark.parametrize('campo', ['k1_d', 'k2_d', 'k_promedio_d'])
@pytest.mark.parametrize('valor,active', [(37.99, True), (38, False), (38.01, False)])
def test_c35_frontera_por_fuente(campo, valor, active):
    act = activas(lente='monofocal', akr_oi={campo: valor})
    text = act.get('cornea_plana_extrema', '')
    assert bool(text) == active
    if text:
        assert 'OI (' in text and 'OD (' not in text
