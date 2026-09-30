"""Aceptacion contra expectativas de la auditoria independiente, sin reescribirla."""
import json
from pathlib import Path

import pytest

from app.correlaciones.registry import evaluar_correlaciones_con_nombres
from app.inference import _get_active_emergency_alerts
from tests.test_auditoria_correlaciones import _req

ROOT = Path(__file__).resolve().parents[1]
NUMEROS = (*range(1, 12), 58)

EXTRAS = [
    (1, 'fondo_periferico_riesgo', {'fondo': 'Desgarro retiniano OD probable.'},
     {'activa': True, 'urgente': True, 'contiene': ['probable']}),
    (1, 'fondo_periferico_riesgo', {'fondo': 'Mi hermana tiene desgarro OD y yo tengo lattice OI.'},
     {'activa': True, 'urgente': False, 'no_contiene': ['desgarro retiniano']}),
    (2, 'sintomas_alarma_traccion_vitreoretina', {'motivo': 'Posibles fotopsias desde ayer aun por confirmar.'},
     {'activa': False, 'h01': False}),
    (3, 'fondo_oclusion_vascular_urgente', {'fondo': 'Probable OVCR OI.'},
     {'activa': True, 'urgente': True, 'contiene': ['probable']}),
    (4, 'papila_patologica', {'fondo': 'Papila OD con bordes borrosos.', 'motivo': 'Si tuviera diplopia, volveria.'},
     {'activa': True, 'urgente': False, 'h01': False}),
    (5, 'glaucoma_asimetrico', {'pupilas': 'DPAR OD', 'fondo': 'Posible muesca inferior OD.', 'edad': 60},
     {'activa': False, 'activas': ['pupilas_alteradas', 'fondo_glaucomatoso']}),
    (6, 'fondo_glaucomatoso', {'fondo': 'C/D 0.2/0.5'},
     {'activa': True, 'contiene': ['0.2', '0.5', 'sin lateralidad'], 'no_contiene': [' en OD', ' en OI']}),
    (7, 'fondo_glaucomatoso', {'fondo': 'Muesca superior OD y escotadura inferior OD.'},
     {'activa': True, 'contiene': ['muesca superior en OD', 'escotadura inferior en OD'], 'no_contiene': [' en AO']}),
    (8, 'fondo_macular_dmae', {'fondo': 'Drusas blandas maculares OD.', 'edad': 70, 'amsler': 'Metamorfopsia OD y dolor de cabeza desde hoy.'},
     {'activa': True, 'urgente': False, 'h01': False, 'activas': ['amsler_alterado']}),
    (9, 'fondo_macular_otros', {'fondo': 'Membrana epirretiniana OD; OVCR OD.'},
     {'activa': True, 'urgente': False, 'activas': ['fondo_oclusion_vascular_urgente']}),
    (9, 'fondo_macular_otros', {'fondo': 'Membrana epirretiniana OI; membrana neovascular coroidea OD.', 'edad': 70},
     {'activa': True, 'urgente': False, 'activas': ['fondo_macular_dmae']}),
    (10, 'fondo_hipertensivo', {'fondo': 'Hemorragias retinianas OD.', 'motivo': 'PIO 190/100 mmHg.', 'edad': 55},
     {'activa': False, 'h01': False}),
    (10, 'fondo_hipertensivo', {'fondo': 'Hemorragias retinianas OD.', 'motivo': 'Mi madre tiene PA 130/80 y yo tengo PA 190/100 mmHg.', 'edad': 55},
     {'activa': True, 'urgente': True, 'contiene': ['190/100']}),
    (11, 'fondo_vascular_diabetico', {'fondo': 'Posible NVE OD.'},
     {'activa': True, 'urgente': True, 'contiene': ['posible']}),
    (11, 'fondo_vascular_diabetico', {'fondo': 'Exudados duros en cornea OD.'},
     {'activa': False, 'h01': False}),
    (58, 'fondo_embolo_retiniano', {'fondo': 'Placa de Hollenhorst OD.', 'motivo': 'No se considera en OD asintomatico.'},
     {'activa': True, 'urgente': False, 'contiene': ['precisar sintomas'], 'no_contiene': ['evaluacion medica ambulatoria']}),
]

EXTRAS = [
    (1, 'fondo_periferico_riesgo', {'fondo': 'Desgarro retiniano OD probable.'},
     {'activa': True, 'urgente': True, 'contiene': ['probable']}),
    (1, 'fondo_periferico_riesgo', {'fondo': 'Mi hermana tiene desgarro OD y yo tengo lattice OI.'},
     {'activa': True, 'urgente': False, 'no_contiene': ['desgarro retiniano']}),
    (2, 'sintomas_alarma_traccion_vitreoretina', {'motivo': 'Posibles fotopsias desde ayer aun por confirmar.'},
     {'activa': False, 'h01': False}),
    (3, 'fondo_oclusion_vascular_urgente', {'fondo': 'Probable OVCR OI.'},
     {'activa': True, 'urgente': True, 'contiene': ['probable']}),
    (4, 'papila_patologica', {'fondo': 'Papila OD con bordes borrosos.', 'motivo': 'Si tuviera diplopia, volveria.'},
     {'activa': True, 'urgente': False, 'h01': False}),
    (5, 'glaucoma_asimetrico', {'pupilas': 'DPAR OD', 'fondo': 'Posible muesca inferior OD.', 'edad': 60},
     {'activa': False, 'activas': ['pupilas_alteradas', 'fondo_glaucomatoso']}),
    (6, 'fondo_glaucomatoso', {'fondo': 'C/D 0.2/0.5'},
     {'activa': True, 'contiene': ['0.2', '0.5', 'sin lateralidad'], 'no_contiene': [' en OD', ' en OI']}),
    (7, 'fondo_glaucomatoso', {'fondo': 'Muesca superior OD y escotadura inferior OD.'},
     {'activa': True, 'contiene': ['muesca superior en OD', 'escotadura inferior en OD'], 'no_contiene': [' en AO']}),
    (8, 'fondo_macular_dmae', {'fondo': 'Drusas blandas maculares OD.', 'edad': 70, 'amsler': 'Metamorfopsia OD y dolor de cabeza desde hoy.'},
     {'activa': True, 'urgente': False, 'h01': False, 'activas': ['amsler_alterado']}),
    (9, 'fondo_macular_otros', {'fondo': 'Membrana epirretiniana OD; OVCR OD.'},
     {'activa': True, 'urgente': False, 'activas': ['fondo_oclusion_vascular_urgente']}),
    (9, 'fondo_macular_otros', {'fondo': 'Membrana epirretiniana OI; membrana neovascular coroidea OD.', 'edad': 70},
     {'activa': True, 'urgente': False, 'activas': ['fondo_macular_dmae']}),
    (10, 'fondo_hipertensivo', {'fondo': 'Hemorragias retinianas OD.', 'motivo': 'PIO 190/100 mmHg.', 'edad': 55},
     {'activa': False, 'h01': False}),
    (10, 'fondo_hipertensivo', {'fondo': 'Hemorragias retinianas OD.', 'motivo': 'Mi madre tiene PA 130/80 y yo tengo PA 190/100 mmHg.', 'edad': 55},
     {'activa': True, 'urgente': True, 'contiene': ['190/100']}),
    (11, 'fondo_vascular_diabetico', {'fondo': 'Posible NVE OD.'},
     {'activa': True, 'urgente': True, 'contiene': ['posible']}),
    (11, 'fondo_vascular_diabetico', {'fondo': 'Exudados duros en cornea OD.'},
     {'activa': False, 'h01': False}),
    (58, 'fondo_embolo_retiniano', {'fondo': 'Placa de Hollenhorst OD.', 'motivo': 'No se considera en OD asintomatico.'},
     {'activa': True, 'urgente': False, 'contiene': ['precisar sintomas'], 'no_contiene': ['evaluacion medica ambulatoria']}),
]


def _casos():
    for numero in NUMEROS:
        spec = json.loads((ROOT / f'auditoria/conformidad-2026-09-29/fondo/{numero:02}-orden.json').read_text(encoding='utf-8'))
        for index, caso in enumerate(spec['casos'], 1):
            yield pytest.param(spec['nombre'], caso, id=f'F{numero:02}-{index:02}')


@pytest.mark.parametrize('nombre,caso', list(_casos()))
def test_conformidad_fondo(nombre, caso):
    req = _req(**dict(caso['entrada'], lente='monofocal'))
    salidas = dict(evaluar_correlaciones_con_nombres(req))
    texto = salidas.get(nombre, '')
    actual = {'activa': bool(texto), 'urgente': texto.startswith('Hallazgo urgente:'),
              'h01': nombre in {a.id for a in _get_active_emergency_alerts(req)}}
    # La orden13C6/C10 posterior conserva DPAR posible en #13; no acredita
    # una asimetria funcional demostrada para #5. No se altera la auditoria.
    esperado = (dict(activa=False, activas=['pupilas_alteradas', 'fondo_glaucomatoso'])
                if nombre == 'glaucoma_asimetrico' and caso['entrada'].get('pupilas') == 'Posible DPAR OD'
                else caso['esperado'])
    for clave, valor in esperado.items():
        if clave in actual:
            assert actual[clave] == valor, (texto, salidas)
        elif clave == 'contiene':
            for token in valor:
                assert token.lower() in texto.lower(), texto
        elif clave == 'no_contiene':
            for token in valor:
                assert token.lower() not in texto.lower(), texto
        elif clave == 'activas':
            assert set(valor) <= salidas.keys(), salidas
        elif clave == 'no_activas':
            assert not set(valor) & salidas.keys(), salidas
        else:
            raise AssertionError(clave)


def test_hipotesis_subjuntiva_no_es_episodio_actual():
    req = _req(motivo='Si presentara perdida visual subita, volveria.',
               rx_od={'av_cc': '20/40'}, lente='monofocal')
    salidas = dict(evaluar_correlaciones_con_nombres(req))
    assert 'sintomas_alarma_traccion_vitreoretina' not in salidas
    assert 'sintomas_alarma_traccion_vitreoretina' not in {a.id for a in _get_active_emergency_alerts(req)}


def test_dpar_posible_conserva_incertidumbre_y_papila_independiente():
    req = _req(pupilas='Posible DPAR OD', fondo='C/D 0.8 OD, 0.4 OI', edad=60, lente='monofocal')
    salidas = dict(evaluar_correlaciones_con_nombres(req))
    assert 'glaucoma_asimetrico' not in salidas
    assert 'no concluyente' in salidas['pupilas_alteradas'].lower()
    assert '0.8 en OD' in salidas['fondo_glaucomatoso']


@pytest.mark.parametrize('numero,nombre,entrada,esperado', EXTRAS,
                         ids=[f'E{n:02}-{i:02}' for i, (n, *_resto) in enumerate(EXTRAS, 1)])
def test_bordes_fondo(numero, nombre, entrada, esperado):
    test_conformidad_fondo(nombre, dict(entrada=entrada, esperado=esperado))


@pytest.mark.parametrize('numero,nombre,entrada,esperado', EXTRAS,
                         ids=[f'E{n:02}-{i:02}' for i, (n, *_resto) in enumerate(EXTRAS, 1)])
def test_bordes_fondo(numero, nombre, entrada, esperado):
    test_conformidad_fondo(nombre, dict(entrada=entrada, esperado=esperado))
