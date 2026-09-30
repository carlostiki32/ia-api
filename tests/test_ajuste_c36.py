"""Aceptacion #36: magnitudes/ejes, fuentes y prescripcion final por ojo."""
import pytest
from tests.test_ajuste_c24 import cases
from tests.test_auditoria_correlaciones import activas, alertas_h01

ACTIVE = {1, 6, 10, 12, 13, 15, 16, 17, 18, 19, 20, 21, 23}


@pytest.mark.parametrize('case', cases(36), ids=lambda c: c['id'])
def test_c36_corpus_contra_orden(case):
    i = int(case['id'].split('-')[1])
    act = activas(**case['entrada'])
    text = act.get('astigmatismo_corneal_vs_refractivo', '')
    assert bool(text) == (i in ACTIVE)
    if text:
        assert 'prescripcion final' in text
        assert 'diferencia de magnitudes' in text
        assert 'no calcula un residual optico' in text
        assert not any(v in text for v in ('origen lenticular', 'error de receta',
            'patologico', 'Javal', 'comparable', 'vigente'))
        assert not alertas_h01(**case['entrada'])
    if i == 6:
        assert 'eje Rx 15 grados' in text and 'meridiano plano K 0 grados' in text
        assert 'diferencia de orientacion 15 grados' in text
    if i == 10:
        assert 'diferencia de orientacion 90 grados' in text
    if i in {12, 13}:
        assert 'orientacion no comparada por datos insuficientes' in text
    if i in {16, 17, 18}:
        assert 'contexto consignado' in text
    if i == 16:
        assert 'reducida deliberadamente' in text
    if i == 21:
        assert 'OD (' in text and 'OI (' in text
        assert 'astigmatismo_lenticular_puro' not in act
    if i == 23:
        assert 'OI (' in text and 'OD (' not in text


@pytest.mark.parametrize('signo', [-1, 1])
@pytest.mark.parametrize('eje', [0, 45, 90, 135])
def test_c36_eje_k_aislado_no_convencion_inventada(signo, eje):
    act = activas(lente='monofocal', akr_od={'k_cilindro': signo * 2,
                    'k_cilindro_eje': eje}, rx_od={'cilindro': -2, 'eje': eje})
    assert 'astigmatismo_corneal_vs_refractivo' not in act


@pytest.mark.parametrize('timestamp', ['1970-01-02 00:00:00', '2020-01-01 12:00:00',
                                      '2030-01-01 12:00:00', '2038-01-18 00:00:00'])
def test_c36_ticket_no_certifica_comparabilidad_ni_suprime(timestamp):
    text = activas(lente='monofocal', akr={'taken_at': timestamp, 'vd': 12},
                   akr_od={'k1_d': 42, 'k2_d': 45},
                   rx_od={'cilindro': -1.5, 'eje': None})['astigmatismo_corneal_vs_refractivo']
    assert 'no acredita simultaneidad' in text and 'residual optico' in text


@pytest.mark.parametrize('signo', [-1, 1])
def test_c36_signo_k_no_rota_geometria_documentada(signo):
    k = {'k1_d': 42, 'k2_d': 44, 'k1_eje': 0, 'k2_eje': 90,
         'k_cilindro': signo * 2, 'k_cilindro_eje': 0}
    text = activas(lente='monofocal', akr_od=k,
                   rx_od={'cilindro': -2, 'eje': 90})['astigmatismo_corneal_vs_refractivo']
    assert 'meridiano plano K 0 grados' in text and 'orientacion 90 grados' in text


def test_c36_contexto_no_fiable_preservado():
    text = activas(lente='monofocal', akr_od={'k1_d': 42, 'k2_d': 45},
        rx_od={'cilindro': -1.5}, motivo='Lectura no fiable; pendiente repetir.')[
        'astigmatismo_corneal_vs_refractivo']
    assert 'Lectura no fiable' in text and 'Verificar' in text


@pytest.mark.parametrize('k2,activa', [(43.995, False), (44, True), (44.005, True)])
def test_c36_diferencia_no_redondea_cilindro_antes_de_comparar(k2, activa):
    assert ('astigmatismo_corneal_vs_refractivo' in activas(
        lente='monofocal', akr_od={'k1_d': 42, 'k2_d': k2},
        rx_od={'cilindro': -0.75})) == activa
