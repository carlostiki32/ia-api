import asyncio
import json
from types import SimpleNamespace
import httpx
import pytest
import threading
from app.tareas import presupuesto as p
from app.config import settings


def test_reintento_no_bloquea_y_es_unico(monkeypatch):
    async def run():
        contador = p.ContadorExacto()
        inicio = asyncio.Event()
        fin = asyncio.Event()
        intentos = []
        async def verificar(client):
            intentos.append(1)
            inicio.set()
            await fin.wait()
        monkeypatch.setattr(contador, 'verificar', verificar)
        await contador.actualizar(None)
        await inicio.wait()
        await contador.actualizar(None)
        assert intentos == [1]
        fin.set()
        await contador._actualizacion
        await contador.actualizar(None)
        assert intentos == [1]
        contador._ultimo_intento -= settings.presupuesto_reverificar_s
        await contador.actualizar(None)
        await contador._actualizacion
        assert intentos == [1, 1]
    asyncio.run(run())


def test_identidad_ligera_limitada(monkeypatch):
    async def run():
        import hashlib
        contador = p.ContadorExacto()
        contador.identidad = ('1', 'abc', hashlib.sha256(b'template').hexdigest(), settings.ollama_num_ctx, settings.ollama_model)
        contador.tokenizador = object()
        llamadas = []
        def handler(req):
            llamadas.append(req)
            if req.url.path == '/api/version': return httpx.Response(200, json={'version':'1'})
            if req.url.path == '/api/tags': return httpx.Response(200, json={'models':[{'name':settings.ollama_model,'digest':'abc'}]})
            assert 'verbose' not in json.loads(req.content)
            return httpx.Response(200, json={'template':'template'})
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await contador.actualizar(client)
            await contador._actualizacion
            for _ in range(10): await contador.actualizar(client)
        assert len(llamadas) == 3
    asyncio.run(run())


def test_aliases_y_sonda_nfc():
    import unicodedata
    assert all(p.PRETOKENIZADORES[a] == p.PRETOKENIZADORES['qwen35'] for a in ('qwen3.5','qwen3_5'))
    fuente = __import__('inspect').getsource(p.ContadorExacto.verificar)
    assert 'Ñandú: revisión óptica 😀👓 ¿qué día?' in fuente
    assert unicodedata.normalize('NFC', fuente) == fuente


def test_mantenimiento_reintenta_sin_solicitudes(monkeypatch):
    async def run():
        contador = p.ContadorExacto()
        intentos = []
        async def verificar(client):
            intentos.append(1)
            if len(intentos) == 2:
                contador.tokenizador = object()
                contador.identidad = ('v','d','h',settings.ollama_num_ctx,settings.ollama_model)
        async def pausa(segundos):
            assert segundos == settings.presupuesto_reverificar_s
            if len(intentos) == 2:
                raise asyncio.CancelledError()
        monkeypatch.setattr(contador, 'verificar', verificar)
        monkeypatch.setattr(p.asyncio, 'sleep', pausa)
        try:
            await contador.mantener(None)
        except asyncio.CancelledError:
            pass
        assert len(intentos) == 2 and contador.disponible()
    asyncio.run(run())


def test_pre_desconocido_registra_nombre(caplog):
    import pytest
    with pytest.raises(ValueError):
        p.ContadorExacto.reconstruir({'model_info':{'tokenizer.ggml.pre':'nuevo-pre'}})
    assert 'nuevo-pre' in caplog.text


def test_mantenimiento_disponible_no_envia_sondas(monkeypatch):
    async def run():
        contador = p.ContadorExacto()
        contador.tokenizador = object()
        contador.identidad = ('v', 'd', 'h', settings.ollama_num_ctx, settings.ollama_model)
        tokenizador = contador.tokenizador
        vueltas = []
        async def pausa(segundos):
            assert segundos == settings.presupuesto_reverificar_s
            vueltas.append(1)
            if len(vueltas) == 4:
                raise asyncio.CancelledError()
        def handler(req):
            raise AssertionError(f'Solicitud inesperada: {req.url}')
        monkeypatch.setattr(p.asyncio, 'sleep', pausa)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            try:
                await contador.mantener(client)
            except asyncio.CancelledError:
                pass
        assert len(vueltas) == 4
        assert contador.disponible() and contador.tokenizador is tokenizador
    asyncio.run(run())


def test_cambios_identidad_fuerzan_reverificacion(monkeypatch):
    import hashlib
    async def run(campo):
        contador = p.ContadorExacto()
        identidad = ['1', 'abc', hashlib.sha256(b'template').hexdigest(), settings.ollama_num_ctx, settings.ollama_model]
        identidad[campo] = 'anterior'
        contador.identidad = tuple(identidad)
        contador.tokenizador = object()
        intentos = []
        async def verificar(client):
            assert contador.tokenizador is None
            intentos.append(1)
        def handler(req):
            if req.url.path == '/api/version': return httpx.Response(200, json={'version': '1'})
            if req.url.path == '/api/tags': return httpx.Response(200, json={'models': [{'name': settings.ollama_model, 'digest': 'abc'}]})
            return httpx.Response(200, json={'template': 'template'})
        monkeypatch.setattr(contador, 'verificar', verificar)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await contador.actualizar(client)
            await contador._actualizacion
        assert intentos == [1]
    for campo in range(5):
        asyncio.run(run(campo))


@pytest.mark.parametrize('fase', ['json', 'reconstruccion'])
def test_carga_tokenizador_deja_avanzar_ciclo(monkeypatch, fase):
    async def run():
        contador = p.ContadorExacto()
        loop = asyncio.get_running_loop()
        hilo_api = threading.get_ident()
        inicio = asyncio.Event()
        continuar = threading.Event()
        tok = SimpleNamespace(encode=lambda texto: SimpleNamespace(ids=list(texto.encode())))
        sondas = []

        def bloquear():
            assert threading.get_ident() != hilo_api
            loop.call_soon_threadsafe(inicio.set)
            assert continuar.wait(5), 'El ciclo no avanzo durante la carga'

        class Show(httpx.Response):
            def json(self):
                if fase == 'json':
                    bloquear()
                return super().json()

        def reconstruir(info):
            if fase == 'reconstruccion':
                bloquear()
            assert contador.tokenizador is None and not contador.disponible()
            return tok

        def handler(req):
            if req.url.path == '/api/version': return httpx.Response(200, json={'version': '1'})
            if req.url.path == '/api/tags': return httpx.Response(200, json={'models': [{'name': settings.ollama_model, 'digest': 'abc'}]})
            if req.url.path == '/api/show': return Show(200, json={'template': '<|im_start|><think>'})
            assert contador.tokenizador is None and not contador.disponible()
            body = json.loads(req.content)
            sondas.append(body)
            cantidad = len(p.renderizar(*[m['content'] for m in body['messages']]).encode())
            return httpx.Response(200, json={'prompt_eval_count': cantidad})

        monkeypatch.setattr(contador, 'reconstruir', reconstruir)
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            tarea = asyncio.create_task(contador.verificar(client))
            try:
                await asyncio.wait_for(inicio.wait(), 2)
                avances = []
                for i in range(5):
                    await asyncio.sleep(0)
                    avances.append(i)
                assert len(avances) == 5 and not tarea.done()
                assert contador.verificando and contador.tokenizador is None
            finally:
                continuar.set()
                await tarea
        assert len(sondas) == 6
        assert contador.disponible() and contador.tokenizador is tok
    asyncio.run(run())


@pytest.mark.parametrize('sonda_fallida', [1, 6])
def test_verificacion_fallida_no_publica_tokenizador_nuevo(monkeypatch, sonda_fallida):
    async def run():
        contador = p.ContadorExacto()
        contador.tokenizador = object()
        contador.identidad = ('anterior', 'd', 'h', settings.ollama_num_ctx, settings.ollama_model)
        nuevo = SimpleNamespace(encode=lambda texto: SimpleNamespace(ids=list(texto.encode())))
        monkeypatch.setattr(contador, 'reconstruir', lambda info: nuevo)
        sondas = []

        def handler(req):
            assert contador.verificando and contador.tokenizador is None
            assert not contador.disponible()
            if req.url.path == '/api/version': return httpx.Response(200, json={'version': '2'})
            if req.url.path == '/api/tags': return httpx.Response(200, json={'models': [{'name': settings.ollama_model, 'digest': 'nuevo'}]})
            if req.url.path == '/api/show': return httpx.Response(200, json={'template': '<|im_start|><think>'})
            body = json.loads(req.content)
            sondas.append(body)
            cantidad = len(p.renderizar(*[m['content'] for m in body['messages']]).encode())
            return httpx.Response(200, json={'prompt_eval_count': cantidad + int(len(sondas) == sonda_fallida)})

        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
            await contador.verificar(client)
        assert len(sondas) == sonda_fallida
        assert contador.tokenizador is None and contador.identidad is None
        assert not contador.verificando and not contador.disponible()
    asyncio.run(run())
