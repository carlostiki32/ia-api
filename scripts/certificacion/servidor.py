"""Proceso de ia-api y proxy transparente. Nunca exporta contenido ni credenciales."""
import asyncio
from collections import Counter
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
import threading
import time

import httpx
from scripts.probar_enrutado import etapa


class Medidor(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, puerto, upstream, modelo, clave, proxy=True):
        super().__init__(("127.0.0.1", puerto), Handler)
        self.upstream, self.modelo, self.clave, self.proxy = upstream.rstrip("/"), modelo, clave, proxy
        self.registros = []
        self.etiqueta = "arranque"
        self.lock = threading.Lock()
        self.activos = 0

    def info(self):
        with httpx.Client(timeout=120, trust_env=False) as c:
            def get(ruta):
                r = c.get(self.upstream + ruta)
                r.raise_for_status()
                return r.json()
            tags = get("/api/tags")
            model = next((m for m in tags.get("models", []) if m.get("name") == self.modelo), {})
            return dict(version=get("/api/version"), modelo=self.modelo, digest=model.get("digest"),
                        ps=get("/api/ps"), activos=self.activos)


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def enviar(self, dato, status=200):
        raw = json.dumps(dato, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(raw)))
        self.end_headers()
        try:
            self.wfile.write(raw)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            pass

    def autorizada(self):
        return self.headers.get("Authorization") == "Bearer " + self.server.clave

    def do_GET(self):
        if self.path.startswith("/__kit/"):
            if not self.autorizada():
                return self.enviar({}, 401)
            try:
                if self.path == "/__kit/info":
                    return self.enviar(self.server.info())
                if self.path == "/__kit/traza":
                    with self.server.lock:
                        return self.enviar(list(self.server.registros))
            except Exception:
                return self.enviar({"error": "administracion"}, 502)
        self.reenviar(None)

    def do_POST(self):
        cuerpo = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or "{}")
        if not self.path.startswith("/__kit/"):
            return self.reenviar(cuerpo)
        if not self.autorizada():
            return self.enviar({}, 401)
        try:
            if self.path == "/__kit/respaldo":
                from app.schemas import ImpresionClinicaRequest
                from app.paciente.contexto import contexto_desde_receta
                from app.paciente.servicio import construir_respaldo
                from app.correlaciones.registry import evaluar_correlaciones_con_nombres
                req = ImpresionClinicaRequest.model_validate(cuerpo)
                pares = evaluar_correlaciones_con_nombres(req)
                ctx = contexto_desde_receta(req, "", [dict(nombre=n, texto=t) for n, t in pares])
                valor = construir_respaldo(ctx)
                return self.enviar(dict(texto=valor.texto, estado=valor.estado, acciones=ctx.contenido("acciones", [])))
            if self.path == "/__kit/respaldo-whatsapp":
                from app.seguimiento.schemas import SeguimientoWhatsappRequest
                from app.seguimiento.servicio import respaldo
                return self.enviar(respaldo(SeguimientoWhatsappRequest.model_validate(cuerpo), motivo="ia_deshabilitada").model_dump(mode="json"))
            if self.path == "/__kit/etiqueta":
                self.server.etiqueta = cuerpo["etiqueta"]
                return self.enviar({})
            if self.path == "/__kit/ollama":
                ruta = cuerpo["ruta"]
                if ruta not in ("/api/ps", "/api/version", "/api/show", "/api/tags", "/api/chat"):
                    return self.enviar({}, 400)
                with httpx.Client(timeout=120, trust_env=False) as c:
                    body = cuerpo.get("cuerpo")
                    r = c.get(self.server.upstream + ruta) if body is None else c.post(self.server.upstream + ruta, json=body)
                    return self.enviar(r.json(), r.status_code)
            if self.path in ("/__kit/minimo", "/__kit/corte"):
                return self.enviar(asyncio.run(self.directa(cuerpo)))
        except Exception:
            return self.enviar({"error": "administracion"}, 502)
        self.enviar({}, 404)

    async def directa(self, cuerpo):
        body = dict(model=self.server.modelo, messages=[dict(role="user", content="Responda ok." if self.path.endswith("minimo") else "Explique con detalle la óptica geométrica. " * 100)],
                    stream=False, think=False, options=dict(num_predict=1 if self.path.endswith("minimo") else 4096, num_ctx=8192))
        async with httpx.AsyncClient(timeout=120, trust_env=False) as c:
            inicio = time.monotonic()
            t = asyncio.create_task(c.post(self.server.upstream + "/api/chat", json=body))
            if self.path.endswith("corte"):
                await asyncio.sleep(cuerpo["demora"])
                terminada = t.done()
                t.cancel()
                await asyncio.gather(t, return_exceptions=True)
                return dict(terminada_antes=terminada, duracion=time.monotonic()-inicio)
            r = await t
            return dict(status=r.status_code, duracion=time.monotonic()-inicio)

    def reenviar(self, cuerpo):
        inicio = time.monotonic()
        medir = self.path == "/api/chat" and cuerpo and len(cuerpo.get("messages", [])) > 1 and cuerpo.get("options", {}).get("num_predict") != 1
        registro = None
        if medir:
            e, version = etapa(cuerpo)
            tarea = "explicacion-paciente" if version.startswith("paciente-") else "seguimiento-whatsapp" if e != "clinica" else "receta-clinica"
            # Capturar al iniciar, no al terminar, para acreditar el orden concurrente.
            with self.server.lock:
                intento = 1 + sum(r["muestra"] == self.server.etiqueta and r["tarea"] == tarea and r["etapa"] == e for r in self.server.registros)
                registro = dict(muestra=self.server.etiqueta, tarea=tarea, etapa=e, prompt_version=version,
                    intento=intento, inicio=inicio, fin=None, duracion=None,
                    opciones={k: cuerpo.get("options", {}).get(k) for k in ("num_ctx", "num_predict", "temperature", "seed")},
                    formato="format" in cuerpo, keep_alive=cuerpo.get("keep_alive"), status=None, json_valido=None)
                self.server.registros.append(registro)
        self.server.activos += bool(medir)
        try:
            with httpx.Client(timeout=180, trust_env=False) as c:
                r = c.get(self.server.upstream + self.path) if cuerpo is None else c.post(self.server.upstream + self.path, json=cuerpo)
                dato = r.json()
            if registro is not None:
                raw = dato.get("message", {}).get("content", "")
                valido = None
                if "format" in cuerpo:
                    try:
                        json.loads(raw)
                        valido = True
                    except (ValueError, TypeError):
                        valido = False
                with self.server.lock:
                    registro.update(status=r.status_code, json_valido=valido,
                        error_memoria=any(p in str(dato.get("error", "")).lower() for p in ("out of memory", "cuda error", "alloc", "memoria")),
                        **{k: dato.get(k) for k in ("prompt_eval_count", "eval_count", "eval_duration", "prompt_eval_duration", "load_duration", "total_duration", "done_reason")})
                    if registro["etapa"] == "verificacion":
                        try:
                            obj = json.loads(raw)
                            registro["rechazada"] = obj.get("valido") is not True if registro["tarea"] == "explicacion-paciente" else obj.get("afirma_algo_de_salud") is not False
                        except (ValueError, AttributeError):
                            registro["rechazada"] = True
            self.enviar(dato, r.status_code)
        except Exception:
            self.enviar({"error": "transporte"}, 502)
        finally:
            self.server.activos -= bool(medir)
            if registro is not None:
                with self.server.lock:
                    registro.update(fin=time.monotonic(), duracion=time.monotonic()-inicio)


def main():
    # Solo la instancia de la aplicación carga su configuración normal.
    from app.config import settings
    upstream = settings.ollama_url
    puerto = int(os.environ["KIT_CONTROL"])
    proxy = os.environ["KIT_PROXY"] == "1"
    servidor = Medidor(puerto, upstream, settings.ollama_model, settings.api_key, proxy)
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    if proxy:
        settings.ollama_url = f"http://127.0.0.1:{puerto}"
    import uvicorn
    try:
        uvicorn.run("app.main:app", host="127.0.0.1", port=int(os.environ["KIT_PUERTO"]), workers=1,
                    log_level="error", access_log=False)
    finally:
        servidor.shutdown()
        servidor.server_close()


if __name__ == "__main__":
    main()
