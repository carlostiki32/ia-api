"""Regresiones normativas de sujeto/estado/anatomia/protocolo/triage; sin LLM."""
import importlib.util
from pathlib import Path
import pytest
from tests.test_auditoria_correlaciones import activas,alertas_h01,_req
from app.correlaciones.binocularidad import _prioridad_sintomas_agudos

PATH=Path(__file__).parents[1]/'auditoria/certificacion-2026-09-29/contexto/reproducciones.py'
spec=importlib.util.spec_from_file_location('reproducciones_cierre_contexto',PATH)
repro=importlib.util.module_from_spec(spec);spec.loader.exec_module(repro)
CONTROLES=repro.controles_actuales()
CASES=[c for d in CONTROLES.values() for c in d['controles_independientes']]

@pytest.mark.parametrize('caso',CASES,ids=lambda c:c['id'])
def test_expectativas_independientes_de_auditoria(caso):
    assert caso['cumple_expectativa'],(caso['entrada'],caso['esperado_independiente'],caso['salidas'],caso['h01'])

@pytest.mark.parametrize('campo',['motivo','anexos','seguimiento'])
@pytest.mark.parametrize('but,pantallas,ID',[(4,None,'but_critico'),(7,None,'but_limitrofe'),(7,'gt6','but_pantallas')])
def test_but_limites_de_medicion_conservados_por_fuente(campo,but,pantallas,ID):
    texto=activas(lente='monofocal',but=but,pantallas=pantallas,**{campo:'BUT no invasivo, poco confiable, pendiente repetir.'})[ID]
    assert 'tecnica no invasiva' in texto and 'poco confiable' in texto and 'repetirla antes de interpretarla' in texto

@pytest.mark.parametrize('nota',['AV: prueba poco confiable.','Amsler: prueba poco confiable.','BUT poco confiable en la madre.','Si se midiera BUT poco confiable, se repetiria.'])
def test_but_no_toma_fiabilidad_de_otra_prueba_sujeto_o_hipotesis(nota):
    texto=activas(lente='monofocal',but=4,seguimiento=nota)['but_critico']
    assert 'poco confiable' not in texto

@pytest.mark.parametrize('anexos',[
    'Meibomio normal; atrofia conjuntival OI.',
    'Meibomio OD normal. Secrecion espesa OD.',
    'Meibomio OD normal; secrecion espesa en Zeis OI.',
    'Si presentara DGM, volveria.',
    'DGM previamente controlada.',
    'DGM desde hace diez anos.',
    'En 2020 tenia DGM.',
])
def test_dgm_no_presta_estructura_estado_o_modalidad(anexos):
    out=activas(lente='monofocal',but=4,anexos=anexos)
    assert 'ojo_seco_evaporativo_dgm' not in out and 'but_critico' in out

@pytest.mark.parametrize('anexos,esperado',[
    ('Meibomio OD obstruido; glandulas lagrimales OI normales.','obstruccion meibomiana descrita OD'),
    ('Meibomio OD con secrecion espesa, OI normal.','secrecion meibomiana espesa OD'),
    ('Meibomio OD con secrecion espesa; sin secrecion espesa en Meibomio OI.','secrecion meibomiana espesa OD'),
    ('DGM resuelta, ahora disfuncion meibomiana OD.','alteracion meibomiana descrita OD'),
    ('DGM conocida y controlada OD, obstruccion de Meibomio OI desde hoy.','obstruccion meibomiana descrita OI'),
])
def test_dgm_normalidad_y_estado_de_otro_hallazgo_no_borran_actual(anexos,esperado):
    texto=activas(lente='monofocal',but=4,anexos=anexos)['ojo_seco_evaporativo_dgm']
    assert esperado in texto and 'Hallazgo urgente:' not in texto

@pytest.mark.parametrize('motivo,prioridad',[
    ('Fatiga ocular resuelta y diplopia desde hoy.','mismo dia'),
    ('Madre con diplopia antigua. Presento vision doble desde hoy.','mismo dia'),
    ('Mi madre presenta perdida visual, yo presento diplopia desde hoy.','mismo dia'),
    ('No presenta diplopia, pero hoy presenta perdida visual subita OD.','inmediata'),
    ('Dolor ocular OD, ojo rojo OI y fotofobia OI desde hoy.',None),
    ('Dolor ocular OD tras traumatismo OD desde hoy.','inmediata'),
    ('Cefalea desde hoy, diplopia desde hace diez anos.',None),
    ('Fatiga ocular actual. Si presenta perdida visual, debe volver.',None),
])
def test_prioridad_independiente_respeta_episodio_sujeto_modalidad_y_ojo(motivo,prioridad):
    assert _prioridad_sintomas_agudos(_req(lente='monofocal',motivo=motivo))==prioridad

BASES={
54:dict(edad=8,rx_od={'esfera':0,'cilindro':0,'av_cc':'20/40'},rx_oi={'esfera':2,'cilindro':0,'av_cc':'20/60'}),
55:dict(edad=8,rx_od={'esfera':4,'cilindro':0,'av_cc':'20/40'},rx_oi={'esfera':4,'cilindro':0,'av_cc':'20/40'}),
56:dict(edad=35,rx_od={'av_cc':'20/40'}),57:dict(edad=70,rx_od={'av_cc':'20/40'})}
IDS={54:'ambliopia_sospecha',55:'ambliopia_isoametropica_bilateral',56:'deficit_visual_inexplicado_refractivo',57:'adulto_mayor_screening'}

@pytest.mark.parametrize('n',BASES)
@pytest.mark.parametrize('fuente',['motivo','anexos','seguimiento'])
def test_av_no_confunde_fiabilidad_ajena_con_la_suya(n,fuente):
    texto=activas(lente='monofocal',**BASES[n],**{fuente:'AV con correccion registrada. BUT poco confiable, repetir BUT.'})[IDS[n]]
    assert 'repetir la medicion de AV' not in texto

@pytest.mark.parametrize('n',BASES)
def test_maxima_av_familiar_no_es_contexto_de_av_del_paciente(n):
    texto=activas(lente='monofocal',**BASES[n],seguimiento='BCVA maxima 20/20 en la madre.')[IDS[n]]
    assert '20/20' not in texto

@pytest.mark.parametrize('n',BASES)
def test_contexto_av_negacion_de_poca_fiabilidad_no_recomienda_repetir_por_ella(n):
    texto=activas(lente='monofocal',**BASES[n],motivo='La AV no fue poco confiable.')[IDS[n]]
    assert 'repetir la medicion de AV' not in texto
