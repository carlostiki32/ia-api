"""Medición de muestras y reglas A1; las respuestas completas solo van a las hojas."""
from collections import Counter
from copy import deepcopy
import statistics
import time

import httpx
from scripts.probar_enrutado import ALIAS, SEGUIMIENTO
from scripts.certificacion.veredicto import criterio, cumple, percentil


def clinico(m):
    return m["status"] == 200 and bool(m["obj"].get("impresion_clinica", "").strip())


def generada(m):
    o = m["obj"]
    return (o.get("explicacion_paciente_estado") == "generada" and
            o.get("generacion", {}).get("origen_explicacion") == "llm") if m["tipo"] == "receta" else o.get("estado") == "generada"


def auditar(m):
    o, llamadas = m["obj"], m["llamadas"]
    gen = o.get("generacion", {})
    cache = gen.get("cache", {}) if m["tipo"] == "receta" else {"whatsapp": gen.get("cached")}
    if any(cache.values()):
        return "muestra contaminada"
    if m["tipo"] == "receta" and set(cache) != {"clinico", "paciente"}:
        return "faltan indicadores de caché"
    if m["tipo"] == "whatsapp" and "cached" not in gen:
        return "falta indicador de caché"
    if not llamadas:
        return "sin llamada nueva"
    conteos = Counter((c["tarea"], c["etapa"]) for c in llamadas)
    if m["tipo"] == "receta":
        if not conteos["receta-clinica", "clinica"]:
            return "sin etapa clínica"
        r = conteos["explicacion-paciente", "redaccion"]
        v = conteos["explicacion-paciente", "verificacion"]
        motivo = gen.get("motivo_explicacion")
        if generada(m) and not (r and v):
            return "generada sin sus dos etapas"
        if motivo in ("validacion", "abstencion") and (not r or v):
            return "etapas incompatibles con respaldo"
        if motivo == "verificacion" and not (r and v):
            return "verificación no observada"
    else:
        r = conteos["seguimiento-whatsapp", "redaccion"]
        v = conteos["seguimiento-whatsapp", "verificacion"]
        motivo = o.get("motivo") or ""
        if generada(m) and not (r and v):
            return "generada sin sus dos etapas"
        if (motivo.startswith("validacion:") or motivo == "json_invalido") and (not r or v):
            return "etapas incompatibles con respaldo"
        if motivo == "verificacion" and not (r and v):
            return "verificación no observada"
    return None


class Medicion:
    def nueva(self, tipo="receta", indice=1):
        self.serial += 1
        casos = self.corpus["recetas" if tipo == "receta" else "whatsapp"]
        caso = deepcopy(casos[indice % len(casos)])
        caso["id"] = f"extra-{self.serial}"
        if tipo == "receta":
            caso["payload"]["paciente"]["motivo_consulta"] = f"Solicita revisión visual durante lectura de {self.serial+100} minutos."
        else:
            caso["payload"]["variante"] = (self.serial + 100) % 1001
            caso["payload"]["meses_desde_ultima_receta"] = self.serial % 601
        return caso

    def pedir(self, instancia, caso, tipo="receta", *, etiqueta=None, auditar_nueva=True):
        etiqueta = etiqueta or caso["id"]
        instancia.etiqueta(etiqueta)
        inicio = time.monotonic()
        try:
            r = instancia.client.post(ALIAS if tipo == "receta" else SEGUIMIENTO, json=caso["payload"])
            status = r.status_code
            try:
                obj = r.json()
            except ValueError:
                obj = {}
        except httpx.TransportError:
            status, obj = 0, {}
        duracion = time.monotonic()-inicio
        # El proxy finaliza después de escribir al cliente.
        llamadas = [x for x in instancia.traza() if x["muestra"] == etiqueta]
        m = dict(id=caso["id"], tipo=tipo, status=status, obj=obj, duracion=duracion,
                 llamadas=llamadas, caso=caso)
        m["problema_a1"] = auditar(m) if auditar_nueva else None
        return m

    def reposo(self, instancia, fase):
        limite = time.monotonic() + 30
        muestras = []
        valido = False
        while time.monotonic() < limite:
            inicio = self.reloj.ahora()
            muestras = []
            valido = True
            for _ in range(3):
                t = self.telemetria.tomar()
                h = instancia.client.get("/health")
                obj = h.json()
                gpu = obj.get("gpu", {})
                v = bool(t and t.get("gpus")) and all(cumple("P1_uso", g["uso"]) for g in (t or {}).get("gpus", []))
                v &= h.status_code == 200 and obj.get("status") == "ok" and obj.get("model_available") is True
                v &= obj.get("tareas_degradadas") == [] and obj.get("concurrencia", {}).get("max_concurrent") == 1
                v &= not gpu.get("ocupada", True) and gpu.get("en_espera_interactiva") == 0 and gpu.get("en_espera_fondo") == 0
                valido &= v
                muestras.append(dict(t=self.reloj.ahora(), telemetria=t, health=obj))
                if not v:
                    break
                if len(muestras) < 3:
                    self.reloj.dormir(5)
            if valido and len(muestras) == 3 and cumple("P1_reposo", self.reloj.ahora() - inicio):
                break
            time.sleep(.1)
        info = instancia.info()
        self.informe["reposos"].append(dict(fase=fase, valido=bool(valido), muestras=muestras, ps=info["ps"]))
        return bool(valido)

    def evaluar_series(self, recetas, whatsapp):
        c = self.informe["criterios"]
        if recetas:
            limpias = all(m["problema_a1"] is None for m in recetas)
            elegibles = [m for m in recetas if m["caso"]["elegible_personalizacion"]]
            n = len(elegibles)
            tasa = sum(generada(m) for m in elegibles)/n if n else 0
            timeout = sum(m["obj"].get("generacion", {}).get("motivo_explicacion") == "timeout" for m in elegibles)/n if n else 0
            c["P4"] = criterio("P4", any(generada(m) for m in recetas) and limpias)
            c["R1"] = criterio("R1", len(recetas) == 100 and all(clinico(m) for m in recetas) and limpias,
                dict(cantidad=len(recetas), http200=sum(m["status"] == 200 for m in recetas),
                     errores_5xx=sum(m["status"] >= 500 for m in recetas), errores_413=sum(m["status"] == 413 for m in recetas)))
            calientes = [m["duracion"] for m in recetas if not m.get("frio")]
            c["R3"] = criterio("R3", limpias and cumple("R3_p95", percentil(calientes)) and cumple("R3_max", max(calientes, default=999)),
                dict(p95=percentil(calientes), maximo=max(calientes, default=None)))
            paciente = [sum(x["duracion"] or 0 for x in m["llamadas"] if x["tarea"] == "explicacion-paciente") for m in recetas]
            c["R4"] = criterio("R4", limpias and cumple("R4_p95", percentil(paciente)), dict(p95=percentil(paciente)))
            c["R5"] = criterio("R5", limpias and cumple("R5_generada", tasa) and cumple("R5_timeout", timeout),
                               dict(elegibles=n, generada=tasa, timeout=timeout))
        if whatsapp:
            limpias = all(m["problema_a1"] is None for m in whatsapp)
            lat = [m["duracion"] for m in whatsapp]
            tasa = sum(generada(m) for m in whatsapp)/len(whatsapp)
            errores = sum(m["status"] >= 500 or m["status"] == 0 for m in whatsapp)
            c["W1"] = criterio("W1", len(whatsapp) == 50 and limpias and cumple("W1_5xx", errores) and cumple("W1_p95", percentil(lat)),
                               dict(cantidad=len(whatsapp), errores_5xx=errores, p95=percentil(lat)))
            c["W2"] = criterio("W2", limpias and cumple("W2_generada", tasa), dict(generada=tasa))

    def metadatos_muestra(self, m):
        o = m["obj"]
        return dict(id=m["id"], categoria=m["caso"]["categoria"], entrada_maxima=m["caso"].get("entrada_maxima", False),
            elegible_personalizacion=m["caso"]["elegible_personalizacion"], status=m["status"], duracion=m["duracion"],
            generada=generada(m), motivo=o.get("generacion", {}).get("motivo_explicacion") if m["tipo"] == "receta" else o.get("motivo"),
            estado=o.get("explicacion_paciente_estado") if m["tipo"] == "receta" else o.get("estado"),
            cache=o.get("generacion", {}).get("cache") if m["tipo"] == "receta" else o.get("generacion", {}).get("cached"),
            problema_a1=m["problema_a1"], llamadas=m["llamadas"])

    def comprobar_conteo(self, instancia, sufijo):
        h = instancia.client.get("/health").json()
        tabla = instancia.client.get("/v1/tareas").json()
        self.informe["configuracion_"+sufijo] = dict(health=h, tareas=tabla, ollama=instancia.info())
        return len(tabla) == 3 and all(f["modo_conteo"] == "exacto" and f["pre_tokenizador"] == "qwen35" for f in tabla.values())

    def cache(self, instancia, recetas, whatsapp):
        self.reposo(instancia, "cache")
        rg = [m for m in recetas if generada(m)][:10]
        wg = [m for m in whatsapp if generada(m)][:10]
        repetidas_r = [self.pedir(instancia, m["caso"], etiqueta="cache-"+m["id"], auditar_nueva=False) for m in rg]
        repetidas_w = [self.pedir(instancia, m["caso"], "whatsapp", etiqueta="cache-"+m["id"], auditar_nueva=False) for m in wg]
        cr = len(rg) == 10 and all(m["obj"].get("generacion", {}).get("cache") == dict(clinico=True, paciente=True) and not m["llamadas"] for m in repetidas_r)
        cw = len(wg) == 10 and all(m["obj"].get("generacion", {}).get("cached") is True and not m["llamadas"] for m in repetidas_w)
        respaldo = next((m for m in recetas if not generada(m) and m["caso"]["elegible_personalizacion"] and clinico(m)), None)
        reintento = None
        if respaldo:
            m = self.pedir(instancia, respaldo["caso"], etiqueta="reintento-respaldo", auditar_nueva=False)
            reintento = any(x["tarea"] == "explicacion-paciente" for x in m["llamadas"])
        # Si el modelo no produjo respaldo, provocarlo en una instancia con timeout
        # corto, con la personalización encendida (sin contaminar las 100 muestras).
        if reintento is None:
            reintento = self.cache_respaldo()
        clinica = len(repetidas_r) == 10 and all(m["obj"].get("generacion", {}).get("cache", {}).get("clinico") is True and not any(x["tarea"] == "receta-clinica" for x in m["llamadas"]) for m in repetidas_r)
        self.informe["cache_clinico_ok"] = clinica
        self.informe["criterios"]["R8"] = criterio("R8", cr and cw and reintento,
            dict(recetas=len(rg), whatsapp=len(wg), dual=cr, seguimiento=cw, respaldo_reintenta=reintento))
