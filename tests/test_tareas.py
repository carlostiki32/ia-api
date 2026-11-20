import asyncio
from dataclasses import replace
from types import SimpleNamespace
import itertools
import json
import httpx
import pytest
from fastapi import FastAPI
from pydantic import BaseModel
from app.config import settings
from app.providers import ollama
from app.gpu_scheduler import GPUScheduler
from app.tareas.nucleo import FichaTarea, LlamadaLLM, ContextoEjecucion
from app.tareas.registro import Registro, REGISTRO
from app.tareas.http import montar_rutas
from app.tareas import presupuesto as p

class Entrada(BaseModel):
    texto: str

def ficha(**kwargs):
    valores = dict(nombre='ficticia', version='1', descripcion='Prueba', rutas=('/v1/inferencia/ficticia',),
        prioridad='fondo', modelo_request=Entrada,
        llamadas=(LlamadaLLM('generar','v1','texto',lambda req: {**ollama.build_options(), 'num_predict':32},lambda:32,500),))
    return FichaTarea(**{**valores, **kwargs})

@pytest.mark.parametrize('cambio', [{'nombre':'ficticia'}, {'nombre':'otra','rutas':('/v1/inferencia/ficticia',)}])
def test_duplicados(cambio):
    r=Registro(); r.registrar(SimpleNamespace(ficha=ficha()))
    with pytest.raises(ValueError): r.registrar(SimpleNamespace(ficha=replace(ficha(), **cambio)))

def test_cpu_y_etapa():
    async def run():
        for f, etapa in [(ficha(prioridad='cpu', llamadas=()),'generar'), (ficha(),'ausente')]:
            ctx=ContextoEjecucion(SimpleNamespace(ficha=f),None,GPUScheduler())
            with pytest.raises(ValueError): await ctx.llamar(etapa,'s','u')
    asyncio.run(run())

def test_degradacion(monkeypatch):
    from app.tareas.registro import cargar_definiciones
    cargar_definiciones()
    monkeypatch.setattr(settings,'ollama_num_ctx',512)
    assert 'seguimiento-whatsapp' in REGISTRO.degradadas()
    assert not REGISTRO.tabla()['seguimiento-whatsapp']['llamadas'][0]['cabe']

@pytest.mark.parametrize('modo', ['estricto','conservador','exacto'])
def test_guardian_modos(monkeypatch,modo):
    token=p.politica_actual.set('estricto' if modo=='exacto' else modo)
    if modo=='exacto':
        monkeypatch.setattr(p.contador,'tokenizador',SimpleNamespace(encode=lambda text: SimpleNamespace(ids=[0]*8000)))
        monkeypatch.setattr(p.contador,'identidad',('v','digest','hash',settings.ollama_num_ctx,settings.ollama_model))
        async def noop(client): pass
        monkeypatch.setattr(p.contador,'actualizar',noop)
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: pytest.fail('No debe enviarse'))) as c:
            with pytest.raises(p.PresupuestoExcedido): await ollama.call('s','9'*16000,c)
    try: asyncio.run(run())
    finally: p.politica_actual.reset(token)

@pytest.mark.parametrize('options', [{'num_predict':0}, {'num_predict':7800}, {'num_ctx':16384}])
def test_opciones_rechazadas(options):
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(lambda req: pytest.fail('Envio prohibido'))) as c:
            with pytest.raises(ValueError): await ollama.call('s','u',c,num_predict=1536,options=options)
    asyncio.run(run())

def test_techo_y_warning(monkeypatch, caplog):
    monkeypatch.setattr(settings,'ollama_num_ctx',32768)
    cuerpos=[]
    def handler(req):
        cuerpos.append(json.loads(req.content))
        return httpx.Response(200,json={'message':{'content':'ok'}, 'prompt_eval_count':500})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as c: await ollama.call('s','u',c)
    asyncio.run(run())
    assert cuerpos[0]['options']['num_ctx']==8192
    assert p.limite_contexto()==7782
    assert 'supera la cota' in caplog.text

def test_cota_digitos():
    from app.inference import _estimate_tokens
    for text in ['1234567890', 'Texto clinico con 123 cifras.', '?'*100]:
        assert p.cota_conservadora(text,'') >= _estimate_tokens(text)
    assert p.cota_conservadora('1'*100,'')-p.cota_conservadora('','')==100

@pytest.mark.parametrize('modo', ['http','respaldo'])
def test_ficticia_ruta_metricas_presupuesto_prioridad(monkeypatch, modo):
    class Tarea:
        ficha=ficha(modo_fallo=modo)
        async def ejecutar(self,req,ctx):
            raw,_=await ctx.llamar('generar','system',req.texto)
            return {'estado':'generada','texto':raw}
        def respaldo(self,req,motivo): return {'estado':'plantilla','motivo':motivo}
    r=Registro();r.registrar(Tarea());app=FastAPI();prioridades=[]
    class Plan:
        def turno(self,prioridad):
            prioridades.append(prioridad)
            return GPUScheduler().turno(prioridad)
    async def run():
        llamadas=[]
        def handler(req):
            llamadas.append(req)
            return httpx.Response(200,json={'message':{'content':'ok'},'prompt_eval_count':10,'eval_count':1})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as proveedor:
            montar_rutas(app,r,autenticar=lambda:None,cliente=lambda:proveedor,planificador=Plan)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://api') as c:
                assert (await c.get('/v1/tareas')).json()['ficticia']['llamadas'][0]['max_tokens_entrada']==500
                assert (await c.post('/v1/inferencia/ficticia',json={'texto':'hola'})).status_code==200
                bad=await c.post('/v1/inferencia/ficticia',json={'texto':'9'*1000})
                assert bad.status_code==(413 if modo=='http' else 200)
                if modo=='respaldo': assert bad.json()['motivo']=='presupuesto'
                assert len(llamadas)==1 and prioridades==['fondo']
                metricas=(await c.get('/v1/metricas')).json()['ficticia']
                assert metricas['presupuesto_excedido']>=1
                assert 'hola' not in json.dumps(metricas) and 'system' not in json.dumps(metricas)
    asyncio.run(run())

def test_peor_seguimiento_admitido(monkeypatch):
    from tests.seguimiento_helpers import fixture
    from app.seguimiento.schemas import SeguimientoWhatsappRequest
    from app.seguimiento.elegibilidad import hechos_elegibles
    from app.seguimiento.prompts import SYSTEM_PROMPT_REDACCION, build_user_prompt_redaccion
    monkeypatch.setattr(settings,'ollama_num_ctx',8192)
    maximo=0
    for edad,estado,costo,pantallas,lente,armazon,notificado in itertools.product(
        ('18_39','40_59','60_mas'),('proximo','vencido'),('incluida','con_costo'),('gt6',None),
        ('monofocal','bifocal','progresivo',None),(True,False,None),(True,False)):
        for esfera,cilindro,add in [(-20,-6,None),(10,-6,4),(0,0,None)]:
            req=SeguimientoWhatsappRequest(**{**fixture('g1-request'),'tramo_edad':edad,'estado_seguimiento':estado,
                'costo':costo,'uso_pantallas':pantallas,'tipo_lente':lente,'usa_armazon':armazon,
                'ya_notificado_en_ciclo':notificado,'recetas_previas':1000,'variante':1000,'meses_desde_ultima_receta':600,
                'rx_lejos':{lado:dict(esfera=esfera,cilindro=cilindro,add=add) for lado in ('od','oi')}})
            n=p.contar(SYSTEM_PROMPT_REDACCION,build_user_prompt_redaccion(req,hechos_elegibles(req)),'estricto')
            maximo=max(n,maximo)
    assert maximo<=7400
    assert maximo+settings.seguimiento_num_predict<=p.limite_contexto()

def test_pre_no_soportado():
    # Se rechaza antes de necesitar la dependencia opcional.
    with pytest.raises(ValueError):
        p.ContadorExacto.reconstruir({'model_info':{'tokenizer.ggml.pre':'desconocido'}})


def test_render_completo():
    texto=p.renderizar('S','U')
    assert texto=='<|im_start|>system\nS<|im_end|>\n<|im_start|>user\nU<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n'
    assert p.contar('S','U','estricto')==len(texto.encode())

@pytest.mark.parametrize('discrepancia',[False,True])
def test_seis_sondas_y_candado(monkeypatch,discrepancia):
    async def run():
        contador=p.ContadorExacto()
        tok=SimpleNamespace(encode=lambda texto:SimpleNamespace(ids=list(texto.encode())))
        monkeypatch.setattr(contador,'reconstruir',lambda info:tok)
        sondas=[]
        bloqueado=asyncio.Event(); continuar=asyncio.Event()
        async def handler(req):
            if req.url.path=='/api/version': return httpx.Response(200,json={'version':'1'})
            if req.url.path=='/api/tags': return httpx.Response(200,json={'models':[{'name':settings.ollama_model,'digest':'abc'}]})
            if req.url.path=='/api/show': return httpx.Response(200,json={'template':'<|im_start|><think>'})
            body=json.loads(req.content); sondas.append(body)
            if len(sondas)==1:
                bloqueado.set(); await continuar.wait()
            n=len(p.renderizar(*[m['content'] for m in body['messages']]).encode())
            return httpx.Response(200,json={'prompt_eval_count':n+int(discrepancia)})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            verificacion=asyncio.create_task(contador.verificar(client))
            await bloqueado.wait()
            assert contador.verificando and not contador.disponible()
            continuar.set(); await verificacion
            assert contador.disponible() is (not discrepancia)
            assert len(sondas)==(1 if discrepancia else 6)
            assert all(b['think'] is False and b['options']['num_predict']==1 for b in sondas)
    asyncio.run(run())

@pytest.mark.parametrize('cambio',['version','digest','template','ctx'])
def test_reverifica_identidad(monkeypatch,cambio):
    import hashlib
    plantilla='<|im_start|><think>'
    contador=p.ContadorExacto()
    contador.identidad=('1','abc',hashlib.sha256(plantilla.encode()).hexdigest(),settings.ollama_num_ctx,settings.ollama_model)
    contador.tokenizador=object()
    revisiones=[]
    async def verificar(client): revisiones.append(True)
    monkeypatch.setattr(contador,'verificar',verificar)
    if cambio=='ctx': monkeypatch.setattr(settings,'ollama_num_ctx',4096)
    def handler(req):
        if req.url.path=='/api/version': return httpx.Response(200,json={'version':'2' if cambio=='version' else '1'})
        if req.url.path=='/api/tags': return httpx.Response(200,json={'models':[{'name':settings.ollama_model,'digest':'otro' if cambio=='digest' else 'abc'}]})
        return httpx.Response(200,json={'template':plantilla+('X' if cambio=='template' else '')})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await contador.actualizar(client)
            await contador._actualizacion
    asyncio.run(run())
    assert revisiones==[True] and contador.tokenizador is None

def test_receta_golden_textos_maximos(monkeypatch):
    import re
    from pathlib import Path
    from app.schemas import ImpresionClinicaRequest
    from app.prompt_builder import build_system_prompt,build_user_prompt
    documento=Path('DICCIONARIO_DATOS_RECETA.md').read_text(encoding='utf-8').split('## 5. Golden Payload',1)[1]
    payload=json.loads(re.search(r'```json\s*(.*?)```',documento,re.S)[1])
    payload['paciente']['ocupacion']='Texto libre '*21+'abc'
    payload['paciente']['motivo_consulta']='Texto libre '*21+'abc'
    for campo in ('anexos_oculares','reflejos_pupilares','motilidad_ocular','confrontacion_campos_visuales','fondo_de_ojo','grid_de_amsler','cover_test'):
        payload['clinica'][campo]=('Hallazgo documentado '*13)[:255]
    payload['clinica']['recomendacion_seguimiento']='Seguimiento '*5000
    req=ImpresionClinicaRequest(**payload)
    cota=p.cota_conservadora(build_system_prompt(),build_user_prompt(req))
    monkeypatch.setattr(settings,'ollama_num_ctx',8192)
    assert cota<=6200
    assert cota+int(settings.ollama_num_predict*1.5)<=p.limite_contexto()

@pytest.mark.parametrize('nombre,etapa',[('receta-clinica','clinica'),('seguimiento-whatsapp','redaccion'),('seguimiento-whatsapp','verificacion')])
def test_descubrimiento_opciones_reales(nombre,etapa):
    from app.tareas.registro import cargar_definiciones
    cargar_definiciones()
    declarada=next(l for l in REGISTRO.tabla()[nombre]['llamadas'] if l['etapa']==etapa)
    tarea=REGISTRO.tareas[nombre]
    async def run():
        cuerpos=[]
        def handler(req):
            cuerpos.append(json.loads(req.content)); return httpx.Response(200,json={'message':{'content':'ok'}})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            ctx=ContextoEjecucion(tarea,client,GPUScheduler())
            await ctx.llamar(etapa,'s','u',format={} if declarada['formato']=='json-schema' else None)
        assert cuerpos[0]['options']['temperature']==declarada['temperature']
        assert cuerpos[0]['options']['num_predict']==declarada['num_predict']
    asyncio.run(run())


def test_reintento_clinico_excede_antes_del_segundo_envio(monkeypatch):
    from app import inference
    from app.schemas import ImpresionClinicaRequest
    monkeypatch.setattr(inference,'build_system_prompt',lambda:'9'*6250)
    monkeypatch.setattr(inference,'build_user_prompt',lambda req:'u')
    monkeypatch.setattr(settings,'ollama_num_ctx',8192)
    monkeypatch.setattr(settings,'ollama_num_predict',1024)
    cuerpos=[]
    def handler(req):
        cuerpos.append(json.loads(req.content))
        return httpx.Response(200,json={'message':{'content':'Texto truncado'},'done_reason':'length'})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            with pytest.raises(p.PresupuestoExcedido):
                await inference.run_inference(ImpresionClinicaRequest(receta_id='test',refraccion={'od':{'esfera':-2}}),client)
    asyncio.run(run())
    assert len(cuerpos)==1 and cuerpos[0]['options']['num_predict']==1024


def test_health_lista_degradadas_sin_cambiar_disponibilidad(monkeypatch):
    import app.main as main
    monkeypatch.setattr(settings,'api_key','secret')
    monkeypatch.setattr(settings,'ollama_num_ctx',1024)
    def handler(req):
        return httpx.Response(200,json={'models':[{'name':settings.ollama_model}]})
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            main.app.dependency_overrides[main.get_http_client]=lambda:client
            try:
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app),base_url='http://api') as c:
                    response=await c.get('/health')
                    assert response.status_code==200 and response.json()['status']=='ok'
                    assert 'seguimiento-whatsapp' in response.json()['tareas_degradadas']
            finally: main.app.dependency_overrides.pop(main.get_http_client,None)
    asyncio.run(run())


@pytest.mark.parametrize('bos',[False,True])
def test_reconstruccion_bpe_sintetico(bos):
    tokenizers=pytest.importorskip('tokenizers',reason='Dependencia no disponible offline')
    tokens=sorted(tokenizers.pre_tokenizers.ByteLevel.alphabet())+['ab','<|im_start|>','<|im_end|>']
    meta={'tokenizer.ggml.pre':'qwen2','tokenizer.ggml.tokens':tokens,
          'tokenizer.ggml.merges':['a b'], 'tokenizer.ggml.token_type':[1]*(len(tokens)-2)+[3,3],
          'tokenizer.ggml.add_bos_token':bos,'tokenizer.ggml.bos_token_id':len(tokens)-2}
    tok=p.ContadorExacto.reconstruir({'model_info':meta})
    assert len(tok.encode('ab').ids)==1+int(bos)
    assert tok.encode('<|im_end|>',add_special_tokens=False).ids==[len(tokens)-1]
    assert len(tok.encode(p.renderizar('S','U')).ids)>len(tok.encode('SU').ids)


def test_metricas_duraciones_por_etapa_sin_contenido(monkeypatch, caplog):
    import logging
    from app.tareas import nucleo, http
    medidas = nucleo.Metricas()
    monkeypatch.setattr(nucleo, 'metricas', medidas)
    monkeypatch.setattr(http, 'metricas', medidas)
    async def noop(client): pass
    monkeypatch.setattr(p.contador, 'actualizar', noop)
    caplog.set_level(logging.INFO, logger=ollama.__name__)
    campos = ('load_duration', 'prompt_eval_duration', 'eval_duration', 'total_duration')
    cuerpos, respuestas = [], []

    class Tarea:
        ficha = ficha(llamadas=(ficha().llamadas[0], replace(ficha().llamadas[0], etapa='verificar')))
        async def ejecutar(self, req, ctx):
            for etapa in ('generar', 'verificar'):
                raw, datos = await ctx.llamar(etapa, 'SECRETO_SYSTEM', req.texto)
                assert raw == 'SECRETO_RESPUESTA' and datos == respuestas[-1]
            return {'estado': 'generada'}

    def handler(req):
        cuerpos.append(json.loads(req.content))
        escala = len(cuerpos)
        datos = {'message': {'content': 'SECRETO_RESPUESTA'}, 'prompt_eval_count': 10, 'eval_count': 2,
                 **{campo: escala * (i + 1) * 100000000 for i, campo in enumerate(campos)}}
        respuestas.append(datos)
        return httpx.Response(200, json=datos)

    async def run():
        registro = Registro(); registro.registrar(Tarea())
        app = FastAPI()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as proveedor:
            montar_rutas(app, registro, autenticar=lambda: None, cliente=lambda: proveedor, planificador=GPUScheduler)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url='http://api') as client:
                for _ in range(2):
                    r = await client.post('/v1/inferencia/ficticia', json={'texto': 'SECRETO_ENTRADA'})
                    assert r.status_code == 200
                r = await client.get('/v1/metricas')
                assert r.status_code == 200
                etapas = r.json()['ficticia']['etapas']
                for etapa, escalas in (('generar', (1, 3)), ('verificar', (2, 4))):
                    assert etapas[etapa]['llamadas'] == 2
                    for i, campo in enumerate(campos):
                        assert etapas[etapa][campo + '_suma'] == sum(escalas) * (i + 1) * 100000000
                        assert etapas[etapa][campo + '_max'] == max(escalas) * (i + 1) * 100000000
                    assert all(isinstance(v, (int, float)) for v in etapas[etapa].values())
                assert 'SECRETO' not in r.text and 'SECRETO' not in caplog.text
    asyncio.run(run())
    assert '0.4s total (0.1s carga, 0.2s prompt)' in caplog.text
    for cuerpo in cuerpos:
        assert cuerpo['messages'] == [{'role': 'system', 'content': 'SECRETO_SYSTEM'}, {'role': 'user', 'content': 'SECRETO_ENTRADA'}]
        assert cuerpo['think'] is False and cuerpo['stream'] is False
    medidas.llamada('sin-datos', 'generar', 0, {})
    for campo in campos:
        assert medidas.datos['sin-datos']['etapas']['generar'][campo + '_suma'] == 0
        assert medidas.datos['sin-datos']['etapas']['generar'][campo + '_max'] == 0
