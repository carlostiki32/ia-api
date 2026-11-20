"""Orquestación de una sola corrida; no se descartan muestras contaminadas."""
from collections import defaultdict
from contextlib import nullcontext
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import statistics
import threading
import time

from scripts.certificacion import VERSION
from scripts.certificacion.fases import Fases
from scripts.certificacion.generar_corpus import cargar, huella
from scripts.certificacion.infra import Muestreador, Nvidia, Reloj
from scripts.certificacion.medicion import Medicion, clinico, generada
from scripts.certificacion.veredicto import TEXTOS, criterio, cumple, escribir, escribir_csv
from scripts.probar_enrutado import REPO

FASES = ("frio", "recetas", "whatsapp", "cache", "concurrencia", "cancelacion", "perfiles", "sostenida")


class Kit(Medicion, Fases):
    def __init__(self, salida, *, rapido=False, omitir=(), simulado=None, reloj=None, telemetria=None, progreso=print):
        self.salida = Path(salida).resolve()
        if self.salida == REPO or REPO in self.salida.parents:
            raise ValueError("La salida debe estar fuera del repositorio")
        self.salida.mkdir(parents=True, exist_ok=True)
        if any(self.salida.iterdir()):
            raise ValueError("Use una carpeta vacía para una corrida nueva")
        self.rapido, self.omitir, self.simulado = rapido, tuple(omitir), simulado
        self.reloj = reloj or Reloj()
        self.fuente = telemetria or Nvidia()
        self.simulado_url = f"http://127.0.0.1:{simulado.server_port}" if simulado else None
        self.corpus, self.serial, self.progreso = cargar(), 0, progreso
        self.recetas, self.whatsapp = [], []
        self.plantillas = {}
        self.informe = dict(kit_version=VERSION, corpus_sha256=huella(), rapido=rapido,
            simulado=bool(simulado), fases_omitidas=list(omitir), completa=False, ejecucion_completa=False,
            revision_completa=False, reposos=[], fases={}, recetas=[], whatsapp=[],
            criterios={k: criterio(k, verificado=False) for k in TEXTOS})
        self.informe["criterios"].update({k: criterio(k) for k in ("R6", "R7", "W3")})
        # Huellas del código y de prompts, sin copiar ni cambiar sus textos.
        rutas = ["app/prompt_builder.py", "app/paciente/prompts.py", "app/seguimiento/prompts.py"]
        self.informe["prompts_sha256"] = {r: hashlib.sha256((REPO/r).read_bytes()).hexdigest() for r in rutas}
        self.informe["kit_sha256"] = {str(p.relative_to(REPO)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted((REPO/"scripts/certificacion").glob("*.py"))}

    def fase(self, nombre, instancia, accion):
        if nombre in self.omitir:
            self.informe["fases"][nombre] = "OMITIDA"
            return
        self.progreso("Fase: " + nombre)
        try:
            accion()
            self.informe["fases"][nombre] = "COMPLETA"
        except Exception as exc:
            # Las excepciones HTTP pueden incluir URL/clave: solo se conserva el tipo.
            self.informe["fases"][nombre] = "ERROR: " + type(exc).__name__

    def sostenida(self, instancia, inicio):
        self.reposo(instancia, "sostenida")
        extras = []
        minimo = 0 if self.rapido else 1800
        ultimo_info = self.reloj.ahora()
        identidades = [self.informe["configuracion_inicio"]["ollama"]]
        while self.reloj.ahora()-inicio < minimo:
            m = self.pedir(instancia, self.nueva(indice=len(extras) % 100), etiqueta="sostenida-"+str(len(extras)))
            extras.append(self.metadatos_muestra(m))
            if self.reloj.ahora()-ultimo_info >= 5:
                identidades.append(instancia.info())
                ultimo_info = self.reloj.ahora()
            if not clinico(m):
                # No enmascarar errores, pero continuar para medir la estabilidad.
                self.informe.setdefault("fallos_sostenida", []).append(m["status"])
            if self.simulado:
                self.reloj.dormir(5)
        identidades.append(instancia.info())
        self.informe["sostenida_extra"] = extras
        self.informe["identidades"] = identidades

    def hojas(self, instancia):
        from scripts.certificacion.generar_corpus import cargar
        originales = self.corpus
        por_r = {m["id"]: m for m in self.recetas}
        por_w = {m["id"]: m for m in self.whatsapp}
        filas_r, filas_w = [], []
        self.informe["recetas"], self.informe["whatsapp"] = [], []
        for tipo, casos, por_id, filas in (("receta", originales["recetas"], por_r, filas_r),
                                          ("whatsapp", originales["whatsapp"], por_w, filas_w)):
            for caso in casos:
                m = por_id.get(caso["id"], dict(id=caso["id"], tipo=tipo, status=0, obj={}, duracion=0,
                    llamadas=[], caso=caso, problema_a1="fase omitida o incompleta"))
                self.informe["recetas" if tipo == "receta" else "whatsapp"].append(self.metadatos_muestra(m))
                o = m["obj"]
                fila = dict(caso=caso["id"], categoria=caso["categoria"],
                    elegible_personalizacion="sí" if caso["elegible_personalizacion"] else "no",
                    entrada=json.dumps(caso["payload"], ensure_ascii=False),
                    estado=o.get("explicacion_paciente_estado" if tipo == "receta" else "estado", ""),
                    motivo=o.get("generacion", {}).get("motivo_explicacion", "") if tipo == "receta" else o.get("motivo", ""))
                if tipo == "receta":
                    plantilla = {}
                    if instancia:
                        plantilla = instancia.control.post("/__kit/respaldo", json=caso["payload"]).json()
                    fila.update(clinico=o.get("impresion_clinica", ""), explicacion=o.get("explicacion_paciente") or "",
                        acciones=" ".join(plantilla.get("acciones", [])), plantilla_paciente=plantilla.get("texto") or "",
                        valida="", critico_clinico="", critico_explicacion="", critico_acciones="", critico_plantilla="", observaciones="")
                else:
                    fila.update(mensaje=o.get("mensaje", ""), aceptable="", critico="", observaciones="")
                filas.append(fila)
        escribir_csv(self.salida, "revision_paciente.csv", filas_r)
        escribir_csv(self.salida, "revision_whatsapp.csv", filas_w)

    def finalizar(self, instancia, inicio):
        i = self.informe
        c = i["criterios"]
        final_exacto = self.comprobar_conteo(instancia, "fin")
        c["P1"] = criterio("P1", bool(i["reposos"]) and all(x["valido"] for x in i["reposos"]), dict(fases=len(i["reposos"])))
        c["P2"] = criterio("P2", self.exacto_inicio and final_exacto)
        tablas = [i["configuracion_"+s]["tareas"] for s in ("inicio", "fin")]
        c["P3"] = criterio("P3", all(l["limite_contexto"] == 7782 and l["cabe"] is True for t in tablas for f in t.values() for l in f["llamadas"]))
        self.evaluar_series(self.recetas, self.whatsapp)
        traza = instancia.traza()
        i["llamadas"] = traza
        j = defaultdict(lambda: dict(llamadas=0, json_invalido=0, length=0, verificaciones_rechazadas=0, tokens=0, eval_s=0., load_s=0., prompt_eval_s=0., total_s=0., opciones=[]))
        for r in traza:
            t = j[r["tarea"]+"/"+r["etapa"]]
            t["llamadas"] += 1
            t["json_invalido"] += r.get("json_valido") is False
            t["length"] += r.get("done_reason") == "length"
            t["verificaciones_rechazadas"] += r.get("rechazada") is True
            t["tokens"] += r.get("eval_count") or 0
            t["eval_s"] += (r.get("eval_duration") or 0)/1e9
            t["load_s"] += (r.get("load_duration") or 0)/1e9
            t["prompt_eval_s"] += (r.get("prompt_eval_duration") or 0)/1e9
            t["total_s"] += (r.get("total_duration") or 0)/1e9
            opciones = {**r["opciones"], "format": r["formato"], "keep_alive": r["keep_alive"]}
            if opciones not in t["opciones"]:
                t["opciones"].append(opciones)
        for v in j.values():
            v["tokens_s"] = v["tokens"]/v["eval_s"] if v["eval_s"] else None
        c["J1"] = criterio("J1", medido=dict(j))
        c["J1"]["estado"] = "INFORMATIVO"
        duracion = self.reloj.ahora()-inicio
        muestras = self.telemetria.datos
        daemons = [m["valor"].get("daemon") for m in muestras if m["valor"]]
        memoria = sum(x.get("error_memoria", False) for x in traza)
        reinicios = sum(a != b for a, b in zip(daemons, daemons[1:]))
        identidades = i.get("identidades", []) + [i["configuracion_fin"]["ollama"]]
        digest = sum(x.get("digest") != i["configuracion_inicio"]["ollama"].get("digest") for x in identidades)
        lat = [m["duracion"] for m in self.recetas] + [m["duracion"] for m in i.get("sostenida_extra", [])]
        deriva = statistics.median(lat[-20:])/statistics.median(lat[:20])-1 if len(lat) >= 40 and statistics.median(lat[:20]) else None
        limpio = all(not m["problema_a1"] for m in self.recetas+self.whatsapp) and all(not m["problema_a1"] for m in i.get("sostenida_extra", []))
        valido = all((cumple("S1_duracion", duracion), cumple("S1_memoria", memoria), cumple("S1_reinicios", reinicios), cumple("S1_digest", digest), limpio))
        c["S1"] = criterio("S1", valido, dict(duracion=duracion, errores_memoria=memoria, reinicios=reinicios,
            cambios_digest=digest, deriva_mediana=deriva, alerta_deriva=deriva is not None and deriva > .25),
            verificado=bool(daemons) and all(daemons) and "sostenida" not in self.omitir)
        i["telemetria"] = muestras
        i["entradas_maximas"] = [self.metadatos_muestra(m) for m in self.recetas if m["caso"].get("entrada_maxima")]
        self.hojas(instancia)
        i["ejecucion_completa"] = not self.omitir and all(i["fases"].get(f) == "COMPLETA" for f in FASES)
        i["completa"] = i["ejecucion_completa"]
        escribir(self.salida, i)

    def ejecutar(self):
        inicio = self.reloj.ahora()
        with Muestreador(self.fuente, self.reloj) as self.telemetria:
            with self.instancia() as instancia:
                self.exacto_inicio = self.comprobar_conteo(instancia, "inicio")
                def frio():
                    self.reposo(instancia, "frio")
                    modelo = instancia.info()["modelo"]
                    descarga = instancia.ollama("/api/chat", dict(model=modelo, keep_alive=0))
                    ps = instancia.ollama("/api/ps")
                    ausente = not any(m.get("name") == modelo for m in ps.get("models", []))
                    m = self.pedir(instancia, self.corpus["recetas"][0])
                    m["frio"] = True
                    self.recetas.append(m)
                    self.informe["criterios"]["R2"] = criterio("R2", ausente and clinico(m) and m["problema_a1"] is None and cumple("R2_http", m["duracion"]),
                        dict(duracion=m["duracion"], status=m["status"], ausente=ausente, ps=ps, descarga=descarga.get("done_reason")))
                self.fase("frio", instancia, frio)
                def recetas():
                    self.reposo(instancia, "recetas")
                    inicio_corpus = 1 if self.recetas else 0
                    for caso in self.corpus["recetas"][inicio_corpus:]:
                        self.recetas.append(self.pedir(instancia, caso))
                self.fase("recetas", instancia, recetas)
                def whatsapp():
                    self.reposo(instancia, "whatsapp")
                    for caso in self.corpus["whatsapp"]:
                        self.whatsapp.append(self.pedir(instancia, caso, "whatsapp"))
                self.fase("whatsapp", instancia, whatsapp)
                self.fase("cache", instancia, lambda: self.cache(instancia, self.recetas, self.whatsapp))
                self.fase("concurrencia", instancia, lambda: self.concurrencia(instancia))
                self.fase("cancelacion", instancia, lambda: self.cancelacion(instancia))
                self.fase("perfiles", instancia, self.apagados)
                self.fase("sostenida", instancia, lambda: self.sostenida(instancia, inicio))
                self.finalizar(instancia, inicio)
        return self.informe
