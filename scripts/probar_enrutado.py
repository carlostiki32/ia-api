"""Demostración local reproducible; el modo real solo se ejecuta explícitamente."""
import argparse
from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import re
import secrets
import shutil
from contextlib import contextmanager
import socket
import subprocess
import sys
import tempfile
import threading
import time

import httpx

REPO = Path(__file__).resolve().parents[1]
FIXTURES = REPO / "tests" / "fixtures" / "seguimiento_whatsapp"
CLINICA = "/inferencia/impresion-clinica"
ALIAS = "/v1/inferencia/receta-clinica"
SEGUIMIENTO = "/v1/inferencia/seguimiento-whatsapp"


def leer(nombre):
    return json.loads((FIXTURES / (nombre + ".json")).read_text(encoding="utf-8"))


def golden():
    md = (REPO / "DICCIONARIO_DATOS_RECETA.md").read_text(encoding="utf-8")
    bloque = md.split("## 5. Golden Payload", 1)[1]
    return json.loads(re.search(r"```json\s*(.*?)```", bloque, re.S)[1])


def puerto_libre():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def etapa(cuerpo):
    system = cuerpo.get("messages", [{}])[0].get("content", "")
    if system.startswith("Ayude al paciente a entender"):
        return "redaccion", "paciente-redaccion-v2"
    if system.startswith("Revise fidelidad, no redacte."):
        return "verificacion", "paciente-verificacion-v1"
    props = cuerpo.get("format", {}).get("properties", {})
    if "uso_lentes" in props:
        return "uso", "seguimiento-uso-v1"
    if "apertura" in props:
        return "redaccion", "seguimiento-whatsapp-prompt-v3"
    if "afirma_algo_de_salud" in props:
        return "verificacion", "seguimiento-verificacion-v1"
    return "clinica", "clinica-v1"


class Simulado(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self):
        super().__init__(("127.0.0.1", 0), Handler)
        self.cuerpos = []
        self.candado = threading.Lock()
        self.demora = 0
        self.abstencion_paciente = False
        self.redactando = threading.Event()


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_):
        pass

    def responder(self, datos):
        contenido = json.dumps(datos, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(contenido)))
        self.end_headers()
        self.wfile.write(contenido)

    def do_GET(self):
        if self.path not in ("/api/tags", "/api/ps"):
            self.send_error(404)
            return
        self.responder({"models": [{"name": "qwen3.5:9b"}]})

    def do_POST(self):
        if self.path != "/api/chat":
            self.send_error(404)
            return
        cuerpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        # El warmup tiene un mensaje de usuario y no pertenece a una tarea.
        warmup = len(cuerpo.get("messages", [])) == 1
        if not warmup:
            with self.server.candado:
                self.server.cuerpos.append(cuerpo)
            if etapa(cuerpo)[0] == "redaccion":
                self.server.redactando.set()
            time.sleep(self.server.demora)
        nombre = etapa(cuerpo)[0]
        contenido = (json.dumps(leer("g1-modelo-uso"), ensure_ascii=False) if nombre == "uso" else
                     json.dumps(leer("g1-modelo-redaccion"), ensure_ascii=False) if nombre == "redaccion" else
                     '{"afirma_algo_de_salud": false}' if nombre == "verificacion" else
                     "Se registra refraccion final para correccion de lejos y apoyo cercano.")
        if etapa(cuerpo)[1].startswith("paciente-"):
            contenido = json.dumps({"frases": []} if self.server.abstencion_paciente else {
                "frases": [{"texto": "La miopía puede hacer que los letreros se vean poco definidos.",
                            "fuentes": ["rx.od", "rx.oi"]}]}) if nombre == "redaccion" else '{"valido":true}'
        self.responder({"message": {"content": contenido}, "done_reason": "stop",
                        "prompt_eval_count": 100, "eval_count": 30, "eval_duration": 100000000,
                        "total_duration": 100000000, "load_duration": 0})


def peticiones(client, simulado=None):
    p = golden()
    dual = {"receta_id": "dual-simulado", "salida_version": "clinica-paciente-v1",
            "refraccion": {"od": {"esfera": -2, "cilindro": 0}, "oi": {"esfera": -2, "cilindro": 0}}}
    respaldo = {**dual, "paciente": {"motivo_consulta": "Ardor ocular."}, "refraccion": {"od": {"esfera": -1, "cilindro": 0}, "oi": {"esfera": -1, "cilindro": 0}}}
    # Descubrimiento recorre el registro: cualquier tarea nueva aparece aqui.
    descubrimiento = client.get('/v1/tareas').json()
    print('Tarea | etapa | max_tokens_entrada | num_predict | limite | cabe')
    for nombre, ficha in descubrimiento.items():
        for llamada in ficha['llamadas']:
            print(f"{nombre} | {llamada['etapa']} | {llamada['max_tokens_entrada']} | {llamada['num_predict']} | {llamada['limite_contexto']} | {llamada['cabe']}")
    casos = [("GET", "/v1/tareas", None, "tareas"),
             ("POST", CLINICA, {**p, "salida_version": "clinica-v1"}, "clinica-v1"),
             ("POST", CLINICA, dual, "clinica-paciente-v1"),
             ("POST", CLINICA, respaldo, "dual-respaldo"),
             ("POST", ALIAS, {**p, "salida_version": "clinica-v1"}, "alias/cache"),
             *[("POST", SEGUIMIENTO, leer(f"g{n}-request"), f"G{n}") for n in (1, 2, 3)]]
    tabla = None
    fallos = False
    if simulado:
        print("Endpoint (caso) | llamadas Qwen | etapa / prompt_version / system SHA / temperatura / num_predict / format | respuesta")
        print("--- | --- | --- | ---")
    else:
        print("Endpoint (caso) | status | latencia | estado | motivo")
        print("--- | --- | --- | --- | ---")
    for metodo, ruta, datos, caso in casos:
        if simulado:
            simulado.abstencion_paciente = caso == "dual-respaldo"
        inicio_idx = len(simulado.cuerpos) if simulado else 0
        inicio = time.monotonic()
        r = client.request(metodo, ruta, json=datos)
        duracion = time.monotonic() - inicio
        if simulado:
            assert r.status_code == 200, f"{ruta}: status {r.status_code}"
        try:
            obj = r.json()
        except ValueError:
            obj = {}
        if caso == "tareas":
            tabla = obj
        if simulado:
            cuerpos = simulado.cuerpos[inicio_idx:]
            detalles = []
            for cuerpo in cuerpos:
                nombre, version = etapa(cuerpo)
                sha = hashlib.sha256(cuerpo["messages"][0]["content"].encode()).hexdigest()[:12]
                opciones = cuerpo["options"]
                detalles.append(f"{nombre} / {version} / {sha} / {opciones['temperature']} / {opciones['num_predict']} / {'sí' if 'format' in cuerpo else 'no'}")
                tarea = "explicacion-paciente" if version.startswith("paciente-") else "seguimiento-whatsapp" if nombre != "clinica" else "receta-clinica"
                declarada = next(e for e in tabla[tarea]["llamadas"] if e["etapa"] == nombre)
                detalles[-1] += f" / entrada<={declarada['max_tokens_entrada']} / limite={declarada['limite_contexto']} / cabe={declarada['cabe']}"
                assert declarada["prompt_version"] == version
                assert declarada["temperature"] == opciones["temperature"]
                assert declarada["num_predict"] == opciones["num_predict"]
                assert (declarada["formato"] == "json-schema") == ("format" in cuerpo)
            estado = obj.get("estado", obj.get("explicacion_paciente_estado", obj.get("status", "ok")))
            motivo = obj.get("motivo", obj.get("generacion", {}).get("motivo_explicacion"))
            print(f"{ruta} ({caso}) | {len(cuerpos)} | {'; '.join(detalles) or '—'} | {r.status_code} {estado}" + (f"/{motivo}" if motivo else ""))
            esperado = {"tareas": 0, "clinica-v1": 1, "clinica-paciente-v1": 3, "dual-respaldo": 2, "alias/cache": 0, "G1": 3, "G2": 2, "G3": 3}[caso]
            assert len(cuerpos) == esperado, f"{caso}: esperaba {esperado} llamadas"
            if caso == "clinica-paciente-v1":
                assert obj["explicacion_paciente_estado"] == "generada"
                assert obj["generacion"]["motivo_explicacion"] is None
            if caso == "dual-respaldo":
                assert obj["generacion"]["motivo_explicacion"] == "abstencion"
            if caso in ("G1", "G3"):
                assert estado == "generada"
            if caso == "G2":
                assert estado == "plantilla"  # El modelo fijo G1 no es válido para G2 (costo con_costo).
        else:
            print(f"{ruta} ({caso}) | {r.status_code} | {duracion:.2f}s | {obj.get('estado', '—')} | {obj.get('motivo') or '—'}")
            fallos = fallos or r.status_code != 200
    if fallos:
        raise AssertionError("Hubo respuestas HTTP no satisfactorias")
    return tabla


def prioridad(client, simulado):
    print("\nDemostración de prioridad (1,5 s por llamada):")
    simulado.demora = 1.5
    simulado.redactando.clear()
    inicio = len(simulado.cuerpos)
    req = {**leer("g1-request"), "variante": 99}
    receta = golden()
    receta["paciente"]["edad"] = 49  # Otra clave clínica, para evitar caché.
    with ThreadPoolExecutor(max_workers=2) as pool:
        fondo = pool.submit(client.post, SEGUIMIENTO, json=req)
        assert simulado.redactando.wait(10), "No inició redacción"
        interactiva = pool.submit(client.post, ALIAS, json=receta)
        # Esperar confirmación de que la receta quedó en cola, sin depender de un sleep.
        limite = time.monotonic() + 10
        while time.monotonic() < limite:
            if client.get("/health").json()["gpu"]["en_espera_interactiva"]:
                break
            time.sleep(.01)
        else:
            raise AssertionError("La receta no quedó en cola")
        a, b = fondo.result(), interactiva.result()
    orden = [etapa(c)[0] for c in simulado.cuerpos[inicio:]]
    print("Orden real de atención: " + " → ".join(orden))
    print(f"Seguimiento: HTTP {a.status_code}, {a.json()['estado']}/{a.json()['motivo']}")
    print(f"Receta: HTTP {b.status_code}, {b.json()['status']}")
    print("Verificación: rechazada inmediatamente porque la receta esperaba el turno.")
    assert orden == ["uso", "redaccion", "clinica"]
    assert a.status_code == b.status_code == 200
    assert a.json()["motivo"] == "ia_ocupada"


@contextmanager
def directorio_temporal():
    temporal = tempfile.mkdtemp(prefix="ia-api-enrutado-")
    try:
        yield temporal
    finally:
        for intento in range(6):
            try:
                shutil.rmtree(temporal)
                break
            except FileNotFoundError:
                break
            except OSError:
                if intento == 5:
                    sys.stdout.flush()
                    print("AVISO: no se pudo limpiar el directorio temporal; las comprobaciones conservan su resultado.", file=sys.stderr)
                else:
                    time.sleep(.1 * (intento + 1))


def simular():
    servidor = Simulado()
    hilo = threading.Thread(target=servidor.serve_forever, daemon=True)
    hilo.start()
    proceso = None
    try:
        with directorio_temporal() as temporal:
            puerto = puerto_libre()
            clave = secrets.token_urlsafe(32)
            entorno = {**os.environ, "PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8", "API_KEY": clave,
                       "OLLAMA_URL": f"http://127.0.0.1:{servidor.server_port}", "OLLAMA_MODEL": "qwen3.5:9b",
                       "OLLAMA_NUM_CTX": "8192", "OLLAMA_TEMPERATURE": "0.2", "OLLAMA_NUM_PREDICT": "1024",
                       "SEGUIMIENTO_TEMPERATURE": "0.4", "SEGUIMIENTO_NUM_PREDICT": "320", "VERIFICACION_NUM_PREDICT": "32",
                       "SEGUIMIENTO_TIMEOUT": "45", "FONDO_QUEUE_WAIT_TIMEOUT": "10", "QUEUE_WAIT_TIMEOUT": "30",
                       "OLLAMA_TIMEOUT": "120", "OLLAMA_SEED": "42", "CACHE_MAX_SIZE": "500", "CACHE_TTL_SECONDS": "86400",
                       "MAX_CONCURRENT": "1", "MAX_QUEUE_SIZE": "5", "LOG_LEVEL": "WARNING",
                       "PRESUPUESTO_RECETA_SIN_EXACTO": "conservador", "PACIENTE_LLM_HABILITADO": "true"}
            with open(Path(temporal) / "servidor.log", "wb") as salida:
                proceso = subprocess.Popen([sys.executable, "-B", "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                                            "--port", str(puerto), "--workers", "1", "--log-level", "warning"],
                                           cwd=temporal, env=entorno, stdout=salida, stderr=subprocess.STDOUT,
                                           creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                try:
                    with httpx.Client(base_url=f"http://127.0.0.1:{puerto}", headers={"Authorization": f"Bearer {clave}"},
                                      timeout=60, trust_env=False) as client:
                        limite = time.monotonic() + 30
                        while time.monotonic() < limite:
                            if proceso.poll() is not None:
                                raise RuntimeError("Uvicorn terminó antes de estar listo")
                            try:
                                if client.get("/health").status_code == 200:
                                    break
                            except httpx.TransportError:
                                pass
                            time.sleep(.1)
                        else:
                            raise RuntimeError("El servidor no quedó listo")
                        tabla = peticiones(client, servidor)
                        assert len(tabla["explicacion-paciente"]["llamadas"]) == 2
                        assert tabla["explicacion-paciente"]["padre"] == "receta-clinica"
                        prioridad(client, servidor)
                        print("\nResultado: todas las comprobaciones coinciden.")
                finally:
                    proceso.terminate()
                    try:
                        proceso.wait(timeout=10)
                    except subprocess.TimeoutExpired:
                        proceso.kill()
                        proceso.wait()
    finally:
        servidor.shutdown()
        servidor.server_close()
        hilo.join(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--modo", choices=("simulado", "real"), default="simulado")
    parser.add_argument("--url")
    parser.add_argument("--api-key-env")
    args = parser.parse_args()
    try:
        if args.modo == "simulado":
            simular()
        else:
            if not args.url or not args.api_key_env:
                parser.error("El modo real requiere --url y --api-key-env")
            clave = os.environ.get(args.api_key_env)
            if not clave:
                parser.error("La variable indicada no contiene una API key")
            with httpx.Client(base_url=args.url.rstrip("/"), headers={"Authorization": f"Bearer {clave}"},
                              timeout=180, trust_env=False) as client:
                peticiones(client)
        return 0
    except Exception as exc:
        # No mostrar excepciones HTTP completas: pueden contener credenciales.
        sys.stdout.flush()
        print(f"FALLO: {type(exc).__name__}; no se completaron las comprobaciones.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(main())
