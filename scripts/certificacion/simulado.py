"""Ollama de laboratorio: metadatos, residencia, demoras por etapa y corte observable."""
from contextlib import contextmanager
import json
import select
import socket
import threading
import time

from scripts.probar_enrutado import Simulado as BaseSimulado, Handler as BaseHandler, REPO, etapa, leer


def tokenizador_sintetico():
    from tokenizers import Tokenizer, models, pre_tokenizers, trainers, decoders, Regex
    # Metadatos BPE suficientes para que la aplicación reconstruya y contraste
    # su contador real. No se presenta como tokenizador del modelo auténtico.
    patron = r"(?i:'s|'t|'re|'ve|'m|'ll|'d)|[^\r\n\p{L}\p{N}]?[\p{L}\p{M}]+|\p{N}| ?[^\s\p{L}\p{M}\p{N}]+[\r\n]*|\s*[\r\n]+|\s+(?!\S)|\s+"
    tok = Tokenizer(models.BPE())
    tok.pre_tokenizer = pre_tokenizers.Sequence([pre_tokenizers.Split(Regex(patron), behavior="isolated"),
        pre_tokenizers.ByteLevel(add_prefix_space=False, use_regex=False)])
    tok.decoder = decoders.ByteLevel()
    textos = [(REPO / p).read_text(encoding="utf-8") for p in
        ("app/prompt_builder.py", "app/paciente/prompts.py", "app/seguimiento/prompts.py",
         "app/seguimiento/catalogo.py", "tests/fixtures/certificacion_gpu/corpus.json")]
    especiales = ["<|im_start|>", "<|im_end|>", "<think>", "</think>"]
    tok.train_from_iterator(textos, trainers.BpeTrainer(vocab_size=3500, min_frequency=2,
        initial_alphabet=pre_tokenizers.ByteLevel.alphabet(), special_tokens=especiales, show_progress=False))
    data = json.loads(tok.to_str())
    vocab = data["model"]["vocab"]
    tokens = sorted(vocab, key=vocab.get)
    meta = {"tokenizer.ggml.pre": "qwen35", "tokenizer.ggml.tokens": tokens,
        "tokenizer.ggml.merges": [" ".join(m) if isinstance(m, list) else m for m in data["model"]["merges"]],
        "tokenizer.ggml.token_type": [3 if t in especiales else 1 for t in tokens],
        "tokenizer.ggml.add_bos_token": False}
    return tok, dict(template="<|im_start|>{{ .System }}<think>", model_info=meta)


class Simulado(BaseSimulado):
    def __init__(self, *, reloj=time.monotonic, demoras=None):
        super().__init__()
        self.RequestHandlerClass = Handler
        self.reloj = reloj
        self.demoras = demoras or {}
        self.activos = 0
        self.cancelaciones = []
        self.inicios = []
        self.residente = True
        self.modelo = "qwen3.5:9b"
        self.digest = "sha256:simulado-certificacion-v1"
        self.tok, self.show = tokenizador_sintetico()
        self.forzar_respaldo = False

    def modelos(self):
        return [dict(name=self.modelo, model=self.modelo, digest=self.digest,
            size=6600000000, size_vram=4800000000, context_length=8192)]

    def esperar_etapa(self, tarea, etapa_nombre, desde=0, timeout=10):
        limite = time.monotonic()+timeout
        while time.monotonic() < limite:
            if any(x["tarea"] == tarea and x["etapa"] == etapa_nombre for x in self.inicios[desde:]):
                return True
            time.sleep(.005)
        return False


class Handler(BaseHandler):
    def do_GET(self):
        if self.path == "/api/version":
            return self.responder(dict(version="simulado-gpu-v1"))
        if self.path == "/api/tags":
            return self.responder(dict(models=self.server.modelos()))
        if self.path == "/api/ps":
            return self.responder(dict(models=self.server.modelos() if self.server.residente else []))
        self.send_error(404)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        if self.path == "/api/show":
            return self.responder(self.server.show)
        if self.path not in ("/api/chat", "/api/generate"):
            return self.send_error(404)
        if body.get("keep_alive") == 0 and not body.get("messages") and not body.get("prompt"):
            self.server.residente = False
            return self.responder(dict(done=True, done_reason="unload"))
        self.server.residente = True
        e, version = etapa(body)
        tarea = "explicacion-paciente" if version.startswith("paciente-") else "seguimiento-whatsapp" if e != "clinica" else "receta-clinica"
        sonda = body.get("options", {}).get("num_predict") == 1
        with self.server.candado:
            self.server.activos += 1
            self.server.cuerpos.append(body)
            self.server.inicios.append(dict(tarea=tarea, etapa=e, t=self.server.reloj()))
        inicio = time.monotonic()
        demora = 0 if sonda else self.server.demoras.get((tarea, e), self.server.demora)
        # Un socket cerrado se observa antes de terminar la demora.
        try:
            while time.monotonic()-inicio < demora:
                listo, _, _ = select.select([self.connection], [], [], min(.02, demora))
                if listo:
                    try:
                        dato = self.connection.recv(1, socket.MSG_PEEK)
                    except (OSError, ConnectionError):
                        dato = b""
                    if not dato:
                        self.server.cancelaciones.append(dict(tarea=tarea, etapa=e, t=self.server.reloj()))
                        return
                time.sleep(.001)
            raw = "Se registra refraccion final para correccion de lejos y apoyo cercano."
            if e == "uso":
                raw = json.dumps(dict(uso_lentes="estudiar", fuente="ocupacion"), ensure_ascii=False)
            elif e == "redaccion":
                if tarea == "explicacion-paciente":
                    user = body.get("messages", [{}])[-1].get("content", "")
                    obj = dict(frases=[])
                    if not (self.server.abstencion_paciente or self.server.forzar_respaldo):
                        try:
                            caso = json.loads(user.split("\n", 1)[1])
                            rx = [h for h in caso.get("hechos", []) if h.get("id", "").startswith("rx.")]
                            m_fuentes = [h["id"] for h in rx if "miopía" in h["contenido"].get("componentes", [])]
                            h_fuentes = [h["id"] for h in rx if "hipermetropía" in h["contenido"].get("componentes", [])]
                            a_fuentes = [h["id"] for h in rx if "astigmatismo" in h["contenido"].get("componentes", [])]
                            p_fuentes = [h["id"] for h in rx if "apoyo cercano" in h["contenido"].get("componentes", []) or "visión cercana" in h["contenido"].get("componentes", [])]
                            if m_fuentes:
                                obj = dict(frases=[dict(texto="La miopía puede hacer que los letreros se vean poco definidos.", fuentes=m_fuentes)])
                            elif h_fuentes:
                                obj = dict(frases=[dict(texto="La hipermetropía puede requerir mayor esfuerzo para enfocar objetos.", fuentes=h_fuentes)])
                            elif a_fuentes:
                                obj = dict(frases=[dict(texto="El astigmatismo puede hacer que las imágenes se perciban poco nítidas a varias distancias.", fuentes=a_fuentes)])
                            elif p_fuentes:
                                obj = dict(frases=[dict(texto="El apoyo para visión cercana facilita enfocar objetos a corta distancia.", fuentes=p_fuentes)])
                        except (ValueError, KeyError, IndexError):
                            obj = dict(frases=[])
                    raw = json.dumps(obj, ensure_ascii=False)
                else:
                    enum = body.get("format", {}).get("properties", {}).get("hechos", {}).get("items", {}).get("enum")
                    cierres_enum = body.get("format", {}).get("properties", {}).get("cierre", {}).get("enum", [])
                    if enum is not None and not (self.server.abstencion_paciente or self.server.forzar_respaldo):
                        from app.seguimiento.combinacion import seleccionar_respaldo, ordenar_hechos
                        from app.seguimiento.catalogo import APERTURAS_V2
                        user_text = body.get("messages", [{}])[-1].get("content", "")
                        con_costo = "Condición: con_costo" in user_text
                        vencido = "Retomar sin reproche" in user_text
                        notificado = "Segundo recordatorio" in user_text
                        visitado = "Ya nos ha visitado" in user_text
                        ids = ordenar_hechos(seleccionar_respaldo(enum, 0))
                        grupo_a = ("AP_SEG" if notificado else "AP_VENC" if vencido else "AP_PROX_CONT" if visitado else "AP_PROX_PRIM")
                        apertura_texto = APERTURAS_V2[grupo_a][0][1]
                        c_id = cierres_enum[0] if cierres_enum else ("CI_COS_1" if con_costo else "CI_INC_1")
                        obj = dict(apertura=apertura_texto, hechos=ids, cierre=c_id)
                        raw = json.dumps(obj, ensure_ascii=False)
                    else:
                        raw = json.dumps(leer("g1-modelo-redaccion"), ensure_ascii=False)
            elif e == "verificacion":
                raw = '{"valido":true}' if tarea == "explicacion-paciente" else '{"afirma_algo_de_salud":false}'
            mensajes = body.get("messages", [])
            if len(mensajes) == 2:
                system, user = (m["content"] for m in mensajes)
                render = "<|im_start|>system\n"+system+"<|im_end|>\n<|im_start|>user\n"+user+"<|im_end|>\n<|im_start|>assistant\n<think>\n\n</think>\n\n"
                cantidad = len(self.server.tok.encode(render).ids)
            else:
                cantidad = 10
            self.responder(dict(message=dict(content=raw), done=True, done_reason="stop",
                prompt_eval_count=cantidad, eval_count=30, eval_duration=100000000,
                prompt_eval_duration=20000000, total_duration=130000000, load_duration=10000000))
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            self.server.cancelaciones.append(dict(tarea=tarea, etapa=e, t=self.server.reloj()))
        finally:
            with self.server.candado:
                self.server.activos -= 1


@contextmanager
def servir_simulado(**kwargs):
    servidor = Simulado(**kwargs)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    try:
        yield servidor
    finally:
        servidor.shutdown()
        servidor.server_close()
        hilo.join(timeout=5)
