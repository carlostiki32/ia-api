"""Conteo del prompt completo; sin dependencias del proveedor."""
import asyncio
from contextvars import ContextVar
import hashlib
import logging
import math
import time
import unicodedata
from app.config import settings

logger = logging.getLogger(__name__)
tarea_actual = ContextVar("tarea_actual", default=None)
politica_actual = ContextVar("politica_presupuesto", default="estricto")

class PresupuestoExcedido(ValueError):
    def __init__(self):
        super().__init__("context_overflow: El prompt y la salida exceden el presupuesto de contexto.")

def limite_contexto():
    return int(.95 * min(settings.ollama_num_ctx, settings.limite_contexto_tokens, 8192))

def renderizar(system, user):
    return ("<|im_start|>system\n" + system + "<|im_end|>\n<|im_start|>user\n" + user
            + "<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n")

def cota_conservadora(system, user):
    total = 16
    for texto in (system, user):
        letras = sum(unicodedata.category(c).startswith("L") for c in texto)
        numeros = sum(unicodedata.category(c).startswith("N") for c in texto)
        simbolos = sum(not c.isspace() and not unicodedata.category(c).startswith(("L", "N")) for c in texto)
        total += numeros + simbolos + texto.count("\n") + math.ceil(letras / 2) + 8
    return total

PRETOKENIZADORES = {
    'qwen2': r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?\p{L}+|\p{N}| ?[^\s\p{L}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+",
    'qwen35': r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?[\p{L}\p{M}]+|\p{N}| ?[^\s\p{L}\p{M}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+",
}
PRETOKENIZADORES.update({alias: PRETOKENIZADORES['qwen35'] for alias in ('qwen3.5', 'qwen3_5')})

class ContadorExacto:
    """Publica el tokenizador solo tras seis concordancias, con candado."""
    def __init__(self):
        self.tokenizador = None
        self.identidad = None
        self.verificando = False
        self._lock = asyncio.Lock()
        self.pre_tokenizador = None
        self._ultima_identidad = float('-inf')
        self._ultimo_intento = float('-inf')
        self._actualizacion = None

    async def mantener(self, client):
        """Verifica al iniciar y reintenta incluso sin tráfico."""
        while True:
            if not self.disponible():
                await self.verificar(client)
            await asyncio.sleep(settings.presupuesto_reverificar_s)

    async def cerrar(self):
        if self._actualizacion is not None:
            self._actualizacion.cancel()
            await asyncio.gather(self._actualizacion, return_exceptions=True)

    @staticmethod
    def reconstruir(info):
        meta = info['model_info']
        nombre = meta.get('tokenizer.ggml.pre')
        if nombre not in PRETOKENIZADORES:
            logger.warning('Pre-tokenizador no soportado: %s', nombre)
            raise ValueError('Pre-tokenizador no soportado')
        from tokenizers import Tokenizer, models, pre_tokenizers, decoders, AddedToken, processors
        tokens = meta['tokenizer.ggml.tokens']
        merges = [tuple(m.split(' ', 1)) for m in meta['tokenizer.ggml.merges']]
        tok = Tokenizer(models.BPE({t: i for i, t in enumerate(tokens)}, merges, fuse_unk=False))
        tok.pre_tokenizer = pre_tokenizers.Sequence([
            pre_tokenizers.Split(__import__('tokenizers').Regex(
                PRETOKENIZADORES[nombre]), behavior='isolated'),
            pre_tokenizers.ByteLevel(add_prefix_space=False, use_regex=False)])
        tok.decoder = decoders.ByteLevel()
        tipos = meta.get('tokenizer.ggml.token_type', [1] * len(tokens))
        tok.add_special_tokens([AddedToken(t, special=True, normalized=False) for t, tipo in zip(tokens, tipos) if tipo in (3, 4)])
        prefijo, sufijo, especiales = '', '', []
        for clave, destino in [('bos', 'prefijo'), ('eos', 'sufijo')]:
            if meta.get('tokenizer.ggml.add_' + clave + '_token', False):
                i = meta['tokenizer.ggml.' + clave + '_token_id']
                especiales.append((tokens[i], i))
                if destino == 'prefijo': prefijo = tokens[i] + ' '
                else: sufijo = ' ' + tokens[i]
        if especiales:
            tok.post_processor = processors.TemplateProcessing(single=prefijo + '$A' + sufijo, special_tokens=especiales)
        return tok

    async def actualizar(self, client):
        if self.verificando or (self._actualizacion is not None and not self._actualizacion.done()):
            return
        ahora = time.monotonic()
        if self.identidad is None:
            if ahora - self._ultimo_intento >= settings.presupuesto_reverificar_s:
                self._ultimo_intento = ahora
                self._actualizacion = asyncio.create_task(self.verificar(client))
            return
        if ahora - self._ultima_identidad < 60:
            return
        self._ultima_identidad = ahora
        self._actualizacion = asyncio.create_task(self._comprobar_identidad(client))

    async def _comprobar_identidad(self, client):
        try:
            r = await client.get(settings.ollama_url + '/api/version'); r.raise_for_status()
            version = r.json()['version']
            r = await client.get(settings.ollama_url + '/api/tags'); r.raise_for_status()
            digest = next(m['digest'] for m in r.json()['models'] if m['name'] == settings.ollama_model)
            r = await client.post(settings.ollama_url + '/api/show', json={'model': settings.ollama_model})
            r.raise_for_status()
            identidad = (version, digest, hashlib.sha256(r.json()['template'].encode()).hexdigest(), settings.ollama_num_ctx, settings.ollama_model)
            if identidad != self.identidad:
                self.tokenizador = None
                await self.verificar(client)
        except Exception:
            self.tokenizador = None
            self.identidad = None

    async def verificar(self, client):
        if self._lock.locked():
            return
        async with self._lock:
            self._ultimo_intento = time.monotonic()
            self.verificando = True
            self.tokenizador = None
            try:
                async def get(path, **kwargs):
                    r = await client.get(settings.ollama_url + path, **kwargs); r.raise_for_status(); return r.json()
                version = await get('/api/version')
                tags = await get('/api/tags')
                digest = next(m['digest'] for m in tags['models'] if m['name'] == settings.ollama_model)
                r = await client.post(settings.ollama_url + '/api/show', json={'model': settings.ollama_model, 'verbose': True})
                r.raise_for_status(); info = await asyncio.to_thread(r.json)
                plantilla = info['template']
                self.pre_tokenizador = info.get('model_info', {}).get('tokenizer.ggml.pre')
                # Solo se admite la familia Qwen sin herramientas ni imágenes.
                if '<|im_start|>' not in plantilla or '<think>' not in plantilla:
                    raise ValueError('Plantilla no soportada')
                identidad = (version['version'], digest, hashlib.sha256(plantilla.encode()).hexdigest(), settings.ollama_num_ctx, settings.ollama_model)
                tok = await asyncio.to_thread(self.reconstruir, info)
                import secrets
                for texto in ('Hola', '1234567890', 'Ñandú: revisión óptica 😀👓 ¿qué día?', 'a\nb\n', '{"x":true}', '<|im_end|> signos !?'):
                    system, user = secrets.token_hex(12) + ' Cuenta.', texto
                    from app.gpu_scheduler import gpu_scheduler
                    async with gpu_scheduler.turno('fondo'):
                        r = await client.post(settings.ollama_url + '/api/chat', json={
                            'model': settings.ollama_model, 'messages': [{'role':'system','content':system}, {'role':'user','content':user}],
                            'think':False, 'stream':False, 'options':{'num_predict':1, 'num_ctx':min(settings.ollama_num_ctx, settings.limite_contexto_tokens, 8192)}})
                    r.raise_for_status()
                    if len(tok.encode(renderizar(system, user)).ids) != r.json()['prompt_eval_count']:
                        raise ValueError('Sonda discrepante')
                self.tokenizador, self.identidad = tok, identidad
                self._ultima_identidad = time.monotonic()
            except Exception:
                self.identidad = None
                logger.warning('Conteo exacto no verificado; se usa respaldo')
            finally:
                self.verificando = False

    def disponible(self):
        return (not self.verificando and self.tokenizador is not None and self.identidad is not None
                and self.identidad[3:] == (settings.ollama_num_ctx, settings.ollama_model))

contador = ContadorExacto()

def modo_conteo(politica='estricto'):
    return 'exacto' if contador.disponible() else politica

def contar(system, user, politica=None):
    politica = politica or politica_actual.get()
    if contador.disponible():
        return len(contador.tokenizador.encode(renderizar(system, user)).ids)
    if politica == 'conservador':
        logger.warning('Presupuesto clínico usa respaldo conservador sin garantía exacta')
        return cota_conservadora(system, user)
    return len(renderizar(system, user).encode('utf-8'))

def verificar(system, user, num_predict, max_tokens_entrada=None, politica=None):
    cota = contar(system, user, politica)
    if num_predict <= 0 or cota + num_predict > limite_contexto() or (max_tokens_entrada is not None and cota > max_tokens_entrada):
        raise PresupuestoExcedido()
    return cota
