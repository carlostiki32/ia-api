"""Aceptacion #33: valores registrados y contexto, sin clasificador de ectasia."""
import pytest
from tests.test_ajuste_c24 import cases
from tests.test_auditoria_correlaciones import activas, alertas_h01, _req
from app.correlaciones.queratometria import _keratometry_suggests_corneal_irregularity

# El dictamen exige que ausencia de cilindro no aporte evidencia positiva,
# mientras un cilindro >=4 conserva su hallazgo al completar K de menor valor.
ACTIVE = {2, 5, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 23, 24,
          26, 27, 31, 32, 33, 34}


@pytest.mark.parametrize('case', cases(33), ids=lambda c: c['id'])
def test_c33_corpus_contra_orden(case):
    i = int(case['id'].split('-')[1])
    text = activas(**case['entrada']).get('queratocono_ectasia_sospecha', '')
    assert bool(text) == (i in ACTIVE)
    if text:
        assert 'queratometria registrada' in text
        assert 'Verificar repetibilidad' in text
        assert not any(v in text for v in ('Kmax', 'sugestivo de irregularidad',
            'ectasia incipiente', 'para descarte de queratocono', 'examen actual'))
        assert not alertas_h01(**case['entrada'])
    if i in {17, 18, 19, 20, 21}:
        assert 'contexto consignado' in text
        assert case['entrada'].get('anexos', case['entrada'].get('motivo')) in text
    if i == 32:
        assert 'K2 registrada 48.70D' in text and 'queratometria parcial' in text
        assert 'K1 registrada' not in text
    if i == 33:
        assert 'K1 registrada 48.70D' in text and 'queratometria parcial' in text
        assert 'K2 registrada' not in text
    if i == 34:
        assert 'K promedio registrada 48.70D' in text
        assert 'K1 registrada' not in text and 'K2 registrada' not in text


def test_c33_cilindro_alto_no_pierde_hallazgo_al_completar_k():
    for k in ({'k_cilindro': 4}, {'k_cilindro': 4, 'k1_d': 42, 'k2_d': 46}):
        eye = _req(lente='monofocal', akr_od=k).akr.od
        assert _keratometry_suggests_corneal_irregularity(eye)


def test_c33_ausencia_no_positivo_y_negativo_no_exclusion():
    for k in ({'k2_d': 47.2}, {'k_promedio_d': 47.2}):
        assert 'queratocono_ectasia_sospecha' not in activas(lente='monofocal', akr_od=k)


def test_c33_signos_clinicos_no_se_inventan_desde_k():
    act = activas(lente='monofocal', akr_od={'k1_d': 42, 'k2_d': 43},
                  anexos='Reflejo en tijera OD y adelgazamiento inferior.')
    assert 'queratocono_ectasia_sospecha' not in act


@pytest.mark.parametrize('meridiano', [{}, {'k1_d': 45}, {'k2_d': 45},
                                     {'k1_d': 49}, {'k2_d': 49}])
def test_c33_media_alta_se_conserva_con_meridiano_parcial_compatible(meridiano):
    text = activas(lente='monofocal', akr_od=dict(k_promedio_d=48.7, **meridiano))[
        'queratocono_ectasia_sospecha']
    assert 'K promedio registrada 48.70D' in text
    if meridiano:
        campo, valor = next(iter(meridiano.items()))
        etiqueta = 'K1' if campo == 'k1_d' else 'K2'
        assert f'{etiqueta} registrada {valor:.2f}D' in text
        assert 'queratometria parcial' in text
    else:
        assert 'meridiano registrado' not in text


def test_c33_media_y_meridianos_completos_contrarios_no_validan_lectura():
    assert 'queratocono_ectasia_sospecha' not in activas(
        lente='monofocal', akr_od={'k_promedio_d': 48.7, 'k1_d': 45, 'k2_d': 45})


@pytest.mark.parametrize('k2,activa', [(43.995, False), (44, True), (44.005, True)])
def test_c33_cilindro_no_redondea_antes_del_umbral(k2, activa):
    assert ('queratocono_ectasia_sospecha' in activas(
        lente='monofocal', akr_od={'k1_d': 40, 'k2_d': k2})) == activa
