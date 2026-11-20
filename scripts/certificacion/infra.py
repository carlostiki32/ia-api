"""Infraestructura local reutilizable, sin contenido clínico en las trazas."""
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
import ctypes
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import threading
import time

import httpx
from scripts.probar_enrutado import REPO, puerto_libre


class Reloj:
    def ahora(self):
        return time.monotonic()

    def dormir(self, segundos):
        time.sleep(segundos)


class RelojSimulado(Reloj):
    def __init__(self):
        self.desplazamiento = 0

    def ahora(self):
        return time.monotonic() + self.desplazamiento

    def dormir(self, segundos):
        self.desplazamiento += segundos
        time.sleep(.001)


def ram_sistema():
    if os.name == "nt":
        class Estado(ctypes.Structure):
            _fields_ = [("length", ctypes.c_ulong), ("load", ctypes.c_ulong)] + [
                (n, ctypes.c_ulonglong) for n in ("total", "available", "page", "availpage", "virtual", "availvirtual", "extended")]
        estado = Estado()
        estado.length = ctypes.sizeof(estado)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(estado)):
            return dict(total=estado.total, disponible=estado.available)
    return None


class Nvidia:
    def __init__(self):
        self.ejecutable = shutil.which("nvidia-smi")

    def muestra(self):
        if not self.ejecutable:
            return None
        try:
            r = subprocess.run([self.ejecutable, "--query-gpu=index,memory.used,memory.total,utilization.gpu,temperature.gpu,clocks.sm,clocks.mem",
                "--format=csv,noheader,nounits"], capture_output=True, timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            r.check_returncode()
            gpus = []
            for linea in r.stdout.decode("utf-8").strip().splitlines():
                v = [float(x.strip()) for x in linea.split(",")]
                gpus.append(dict(zip(("indice", "vram_mb", "vram_total_mb", "uso", "temperatura", "reloj_sm", "reloj_mem"), v)))
            if os.name == "nt":
                proceso = subprocess.run(["powershell", "-NoProfile", "-Command",
                    "Get-Process -Name ollama -ErrorAction SilentlyContinue | Select-Object Id,@{Name='Inicio';Expression={$_.StartTime.ToUniversalTime().ToString('o')}} | ConvertTo-Json -Compress"],
                    capture_output=True, timeout=10, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                try:
                    daemon = json.loads(proceso.stdout.decode("utf-8-sig"))
                except (ValueError, UnicodeError):
                    daemon = None
            else:
                proceso = subprocess.run(["ps", "-C", "ollama", "-o", "pid=,lstart="], capture_output=True, timeout=10)
                daemon = proceso.stdout.decode("utf-8").strip() or None
            return dict(gpus=gpus, ram=ram_sistema(), daemon=daemon)
        except (OSError, ValueError, subprocess.SubprocessError):
            return None


class TelemetriaSimulada:
    def __init__(self, servidor):
        self.servidor = servidor

    def muestra(self):
        return dict(gpus=[dict(indice=0, vram_mb=1024, vram_total_mb=8192,
            uso=60 if self.servidor.activos else 0, temperatura=50, reloj_sm=1500, reloj_mem=7000)],
            ram=dict(total=16000000000, disponible=8000000000), daemon=dict(pid=1, inicio="simulado"))


class Muestreador:
    def __init__(self, fuente, reloj):
        self.fuente, self.reloj = fuente, reloj
        self.datos = []
        self.fin = threading.Event()

    def tomar(self):
        valor = self.fuente.muestra()
        self.datos.append(dict(t=self.reloj.ahora(), valor=valor))
        return valor

    def __enter__(self):
        def bucle():
            while not self.fin.wait(5):
                self.tomar()
        self.tomar()
        self.hilo = threading.Thread(target=bucle, daemon=True)
        self.hilo.start()
        return self

    def __exit__(self, *exc):
        self.fin.set()
        self.hilo.join(timeout=12)
        self.tomar()


class Instancia:
    """El hijo carga su configuración normal desde cwd=REPO; la clave es efímera."""
    def __init__(self, carpeta, *, simulado_url=None, ajustes=None, proxy=True):
        self.carpeta = Path(carpeta)
        self.puerto, self.puerto_control = puerto_libre(), puerto_libre()
        self.clave = secrets.token_urlsafe(32)
        self.ajustes = ajustes or {}
        self.simulado_url, self.proxy = simulado_url, proxy

    def __enter__(self):
        env = {**os.environ, "API_KEY": self.clave, "PYTHONIOENCODING": "utf-8",
               "PYTHONPATH": str(REPO), "KIT_PUERTO": str(self.puerto),
               "KIT_CONTROL": str(self.puerto_control), "KIT_PROXY": str(int(self.proxy))}
        if self.simulado_url:
            env.update(OLLAMA_URL=self.simulado_url, OLLAMA_MODEL="qwen3.5:9b",
                OLLAMA_NUM_CTX="8192", LIMITE_CONTEXTO_TOKENS="8192",
                OLLAMA_NUM_PREDICT="1024", MAX_CONCURRENT="1", CACHE_MAX_SIZE="500",
                CACHE_TTL_SECONDS="86400", OLLAMA_TIMEOUT="120", LOG_LEVEL="ERROR",
                PRESUPUESTO_RECETA_SIN_EXACTO="estricto")
        env.update({k: str(v) for k, v in self.ajustes.items()})
        self.proceso = subprocess.Popen([sys.executable, "-B", "-m", "scripts.certificacion.servidor"],
            cwd=REPO, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.client = httpx.Client(base_url=f"http://127.0.0.1:{self.puerto}",
            headers={"Authorization": "Bearer " + self.clave}, timeout=180, trust_env=False)
        self.control = httpx.Client(base_url=f"http://127.0.0.1:{self.puerto_control}",
            headers={"Authorization": "Bearer " + self.clave}, timeout=180, trust_env=False)
        try:
            limite = time.monotonic() + 180
            while time.monotonic() < limite:
                if self.proceso.poll() is not None:
                    raise RuntimeError("La instancia propia no arrancó")
                try:
                    h = self.client.get("/health")
                    if h.status_code == 200:
                        # Dejar terminar las sondas exactas antes de medir.
                        if all(x == "exacto" for x in h.json().get("modo_conteo", {}).values()):
                            return self
                except httpx.TransportError:
                    pass
                time.sleep(.1)
            # La falta de conteo exacto debe figurar en P2; no ocultarla como error del arnés.
            return self
        except BaseException:
            self.__exit__()
            raise

    def __exit__(self, *exc):
        self.client.close()
        self.control.close()
        self.proceso.terminate()
        try:
            self.proceso.wait(10)
        except subprocess.TimeoutExpired:
            self.proceso.kill()
            self.proceso.wait()

    def info(self):
        return self.control.get("/__kit/info").json()

    def traza(self):
        return self.control.get("/__kit/traza").json()

    def etiqueta(self, etiqueta):
        self.control.post("/__kit/etiqueta", json={"etiqueta": etiqueta}).raise_for_status()

    def ollama(self, ruta, cuerpo=None):
        # Solo operaciones administrativas. Las cancelaciones las ejecuta el hijo
        # directamente contra el transporte original, fuera del proxy.
        return self.control.post("/__kit/ollama", json={"ruta": ruta, "cuerpo": cuerpo}).json()

    def minimo(self):
        return self.control.post("/__kit/minimo", json={}).json()

    def corte_directo(self, demora):
        return self.control.post("/__kit/corte", json={"demora": demora}).json()
