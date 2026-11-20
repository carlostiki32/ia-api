"""Fases de concurrencia, cancelación y comprobación de los interruptores."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import time

import httpx
from scripts.certificacion.infra import Instancia
from scripts.certificacion.medicion import clinico
from scripts.certificacion.veredicto import criterio, cumple
from scripts.probar_enrutado import ALIAS


class Fases:
    def instancia(self, *, ajustes=None, proxy=True):
        valores = dict(PACIENTE_LLM_HABILITADO="true", SEGUIMIENTO_LLM_HABILITADO="true")
        valores.update(ajustes or {})
        return Instancia(self.salida, simulado_url=self.simulado_url, ajustes=valores, proxy=proxy)

    @contextmanager
    def demoras(self, valores):
        if self.simulado:
            anterior = self.simulado.demoras.copy()
            self.simulado.demoras.update(valores)
        try:
            yield
        finally:
            if self.simulado:
                self.simulado.demoras = anterior

    def esperar_activa(self, instancia, futuro, tarea, etapa, desde, metricas=None):
        limite = time.monotonic() + 90
        while not futuro.done() and time.monotonic() < limite:
            if self.simulado:
                activa = any(x["tarea"] == tarea and x["etapa"] == etapa for x in self.simulado.inicios[desde:])
            elif etapa == "clinica":
                activa = instancia.client.get("/health").json().get("gpu", {}).get("ocupada", False)
            else:
                actual = instancia.client.get("/v1/metricas").json()
                previa_tarea, previa_etapa = ("receta-clinica", "clinica") if etapa == "redaccion" else ("explicacion-paciente", "redaccion")
                extraer = lambda m: m.get(previa_tarea, {}).get("etapas", {}).get(previa_etapa, {}).get("llamadas", 0)
                activa = extraer(actual) > extraer(metricas or {})
            if activa:
                muestra = self.telemetria.tomar()
                if muestra and muestra.get("gpus") and any(cumple("X_uso", g["uso"]) for g in muestra["gpus"]):
                    return dict(verificada=True, muestra=muestra, t=time.monotonic())
            time.sleep(.02)
        return dict(verificada=False)

    def concurrencia(self, instancia):
        self.reposo(instancia, "concurrencia")
        c = self.informe["criterios"]
        base = self.pedir(instancia, self.nueva(indice=1), etiqueta="C1-base")
        with self.demoras({("seguimiento-whatsapp", "redaccion"): .4, ("receta-clinica", "clinica"): .35}):
            with ThreadPoolExecutor(max_workers=2) as pool:
                desde = len(self.simulado.inicios) if self.simulado else 0
                w = pool.submit(self.pedir, instancia, self.nueva("whatsapp", 1), "whatsapp", etiqueta="C1-w")
                activa = self.esperar_activa(instancia, w, "seguimiento-whatsapp", "redaccion", desde)
                r = self.pedir(instancia, self.nueva(indice=1), etiqueta="C1-r")
                w.result()
                adicional = r["duracion"]-base["duracion"]
                c["C1"] = criterio("C1", clinico(r) and cumple("C1_adicional", adicional), dict(adicional=adicional, activa=activa),
                                   verificado=activa["verificada"])
                desde = len(self.simulado.inicios) if self.simulado else 0
                r = pool.submit(self.pedir, instancia, self.nueva(indice=1), etiqueta="C2-r")
                activa = self.esperar_activa(instancia, r, "receta-clinica", "clinica", desde)
                w = self.pedir(instancia, self.nueva("whatsapp", 1), "whatsapp", etiqueta="C2-w", auditar_nueva=False)
                r.result()
                valido = w["status"] == 200 and w["obj"].get("estado") == "plantilla" and w["obj"].get("motivo") == "ia_ocupada" and cumple("C2_http", w["duracion"])
                c["C2"] = criterio("C2", valido, dict(status=w["status"], estado=w["obj"].get("estado"), motivo=w["obj"].get("motivo"), duracion=w["duracion"]),
                                   verificado=activa["verificada"])
                inicio = time.monotonic()
                a = pool.submit(self.pedir, instancia, self.nueva(indice=1), etiqueta="C3-a")
                b = pool.submit(self.pedir, instancia, self.nueva(indice=2), etiqueta="C3-b")
                par = [a.result(), b.result()]
                c["C3"] = criterio("C3", all(clinico(m) for m in par), dict(status=[m["status"] for m in par], duracion=time.monotonic()-inicio))
        if self.rapido:
            self.informe["saturacion"] = dict(estado="NO VERIFICADO", motivo="modo rápido: prueba informativa de cola de 30 s omitida")
        else:
            # No modificar el planificador: se observa el vencimiento real.
            with ThreadPoolExecutor(max_workers=2) as pool:
                a = pool.submit(self.pedir, instancia, self.nueva(indice=0), etiqueta="saturacion-a")
                limite = time.monotonic()+10
                while not a.done() and time.monotonic() < limite:
                    if instancia.client.get("/health").json().get("gpu", {}).get("ocupada"):
                        break
                    time.sleep(.02)
                b = self.pedir(instancia, self.nueva(indice=20), etiqueta="saturacion-b", auditar_nueva=False)
                a.result()
                self.informe["saturacion"] = dict(status=b["status"], duracion=b["duracion"],
                    cola_30s_observada=b["status"] == 503 and b["duracion"] >= 30, informativo=True)

    async def cortar_http(self, instancia, caso, cortar):
        async with httpx.AsyncClient(timeout=180, trust_env=False) as c:
            t = asyncio.create_task(c.post(str(instancia.client.base_url).rstrip("/") + ALIAS,
                headers={"Authorization": "Bearer " + instancia.clave}, json=caso["payload"]))
            while not cortar.is_set() and not t.done():
                await asyncio.sleep(.005)
            terminada = t.done()
            t.cancel()
            await asyncio.gather(t, return_exceptions=True)
            return dict(terminada_antes=terminada)

    def cancelacion(self, principal):
        import threading
        c = self.informe["criterios"]
        for nombre in ("X1", "X2", "X3", "X4", "X5"):
            intentos = []
            for intento in range(3):
                ajustes = {"X2": dict(PACIENTE_TIMEOUT_REDACCION_S="1"),
                    "X3": dict(PACIENTE_TIMEOUT_VERIFICACION_S="0.5"),
                    "X4": dict(PLAZO_GLOBAL_RECETA_S="1")}.get(nombre, {})
                demora = {("receta-clinica", "clinica"): .04, ("explicacion-paciente", "redaccion"): .04,
                          ("explicacion-paciente", "verificacion"): .04}
                if nombre == "X1":
                    demora[("receta-clinica", "clinica")] = 3 + intento
                if nombre == "X2":
                    demora[("explicacion-paciente", "redaccion")] = 1.5 + intento
                if nombre == "X3":
                    demora[("explicacion-paciente", "verificacion")] = 1 + intento
                if nombre == "X4":
                    demora[("receta-clinica", "clinica")] = 1.5 + intento
                if nombre == "X5":
                    demora[("receta-clinica", "clinica")] = .5 + intento
                with self.demoras(demora), self.instancia(ajustes=ajustes, proxy=False) as instancia:
                    self.reposo(instancia, nombre+f"-{intento+1}")
                    base = instancia.minimo()
                    desde = len(self.simulado.inicios) if self.simulado else 0
                    antes = instancia.client.get("/v1/metricas").json()
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        corte = threading.Event()
                        if nombre == "X1":
                            futuro = pool.submit(instancia.corte_directo, 2)
                            # La muestra inmediatamente anterior al corte se toma cerca
                            # de los 2 s; no se reemplaza por /api/ps.
                            time.sleep(1.8)
                            activa = self.esperar_activa(instancia, futuro, "receta-clinica", "clinica", desde)
                        else:
                            caso = self.nueva(indice=(0, 20, 40)[intento] if nombre in ("X4", "X5") else 1)
                            if nombre == "X5":
                                futuro = pool.submit(asyncio.run, self.cortar_http(instancia, caso, corte))
                            else:
                                futuro = pool.submit(self.pedir, instancia, caso, etiqueta=nombre, auditar_nueva=False)
                            etapa = "redaccion" if nombre == "X2" else "verificacion" if nombre == "X3" else "clinica"
                            activa = self.esperar_activa(instancia, futuro,
                                "explicacion-paciente" if nombre in ("X2", "X3") else "receta-clinica", etapa, desde, antes)
                            if nombre == "X5":
                                corte.set()
                        resultado = futuro.result()
                    terminada = resultado.get("terminada_antes", False)
                    # Caída de GPU informativa, con límite de observación de 5 s.
                    bajada = None
                    inicio_bajada = time.monotonic()
                    while time.monotonic()-inicio_bajada <= 5:
                        t = self.telemetria.tomar()
                        if t and all(g["uso"] < 30 for g in t["gpus"]):
                            bajada = time.monotonic()-inicio_bajada
                            break
                        time.sleep(.05)
                    if nombre == "X5":
                        inicio_recuperacion = time.monotonic()
                        siguiente = self.pedir(instancia, self.nueva(indice=1), etiqueta="X5-siguiente", auditar_nueva=False)
                        recuperacion = time.monotonic()-inicio_recuperacion
                        libre = not instancia.client.get("/health").json().get("gpu", {}).get("ocupada", True)
                        valido = clinico(siguiente) and cumple("X5_recuperacion", recuperacion) and libre
                        respuesta = dict(status=siguiente["status"], turno_libre=libre)
                    else:
                        siguiente = instancia.minimo()
                        recuperacion = siguiente.get("duracion")
                        valido = siguiente.get("status") == 200 and cumple("X_recuperacion", recuperacion-base.get("duracion", 0))
                        respuesta = {}
                        if nombre != "X1":
                            o = resultado["obj"]
                            respuesta = dict(status=resultado["status"], estado=o.get("explicacion_paciente_estado"),
                                             motivo=o.get("generacion", {}).get("motivo_explicacion"))
                            if nombre in ("X2", "X3"):
                                valido &= respuesta["status"] == 200 and respuesta["estado"] == "plantilla" and respuesta["motivo"] == "timeout"
                            if nombre == "X4":
                                valido &= respuesta["status"] == 504
                    dato = dict(intento=intento+1, activa=activa, terminada_antes=terminada,
                        base=base.get("duracion"), recuperacion=recuperacion, bajada_gpu_s=bajada,
                        respuesta=respuesta, valido=bool(valido))
                    intentos.append(dato)
                    if activa["verificada"] and not terminada:
                        break
            verificada = intentos[-1]["activa"]["verificada"] and not intentos[-1]["terminada_antes"]
            c[nombre] = criterio(nombre, intentos[-1]["valido"], intentos, verificado=verificada)

    def apagados(self):
        for codigo, ajustes, tipo in (
            ("OFF_P", dict(PACIENTE_LLM_HABILITADO="false"), "receta"),
            ("OFF_W", dict(SEGUIMIENTO_LLM_HABILITADO="false"), "whatsapp")):
            with self.instancia(ajustes=ajustes) as instancia:
                self.reposo(instancia, codigo)
                resultados = [self.pedir(instancia, self.nueva(tipo, i*10+1), tipo,
                    etiqueta=f"{codigo}-{i}", auditar_nueva=False) for i in range(5)]
                valido = True
                for m in resultados:
                    o = m["obj"]
                    prohibida = "explicacion-paciente" if tipo == "receta" else "seguimiento-whatsapp"
                    valido &= m["status"] == 200 and not any(x["tarea"] == prohibida for x in m["llamadas"])
                    if tipo == "receta":
                        esperado = instancia.control.post("/__kit/respaldo", json=m["caso"]["payload"]).json()
                        valido &= clinico(m) and o.get("explicacion_paciente_estado") == esperado.get("estado") and o.get("generacion", {}).get("motivo_explicacion") is None
                        valido &= o.get("explicacion_paciente") == esperado.get("texto")
                    else:
                        esperado = instancia.control.post("/__kit/respaldo-whatsapp", json=m["caso"]["payload"]).json()
                        valido &= o == esperado
                self.informe["criterios"][codigo] = criterio(codigo, bool(valido),
                    [self.metadatos_muestra(m) for m in resultados])

    def cache_respaldo(self):
        with self.demoras({("explicacion-paciente", "redaccion"): 1.2}), self.instancia(
            ajustes=dict(PACIENTE_TIMEOUT_REDACCION_S="1")) as instancia:
            self.reposo(instancia, "cache-respaldo")
            caso = self.nueva(indice=1)
            a = self.pedir(instancia, caso, etiqueta="respaldo-1", auditar_nueva=False)
            b = self.pedir(instancia, caso, etiqueta="respaldo-2", auditar_nueva=False)
            return a["obj"].get("explicacion_paciente_estado") != "generada" and any(
                x["tarea"] == "explicacion-paciente" for x in b["llamadas"])
