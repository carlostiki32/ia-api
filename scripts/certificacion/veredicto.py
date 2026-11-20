"""Umbrales firmados. Las igualdades pasan; no hay márgenes añadidos."""
import csv
import io
import json
import math
from pathlib import Path

UMBRALES = {
    "R2_http": ("<=", 88), "R3_p95": ("<=", 60), "R3_max": ("<=", 88),
    "R4_p95": ("<=", 20), "R5_generada": (">=", .90), "R5_timeout": ("<=", .05),
    "R6_valida": (">=", .90), "R7_criticos": ("<=", 0),
    "W1_p95": ("<=", 20), "W1_5xx": ("<=", 0), "W2_generada": (">=", .80),
    "W3_aceptables": (">=", .90), "W3_criticos": ("<=", 0),
    "C1_adicional": ("<=", 20), "C2_http": ("<=", 1),
    "X_recuperacion": ("<=", 3), "X5_recuperacion": ("<=", 90),
    "S1_duracion": (">=", 1800), "S1_memoria": ("<=", 0),
    "S1_reinicios": ("<=", 0), "S1_digest": ("<=", 0),
    "P1_uso": ("<", 10), "P1_reposo": (">=", 10), "X_uso": (">=", 30),
    "P3_limite": ("==", 7782), "R1_http": ("==", 200),
    "R1_5xx": ("==", 0), "R1_413": ("==", 0), "R2_504": ("==", 0),
    "X1_corte": ("==", 2), "apagado_casos": ("==", 5),
    "recetas_cantidad": ("==", 100), "whatsapp_cantidad": ("==", 50),
    "R8_cantidad": ("==", 10), "R8_nuevas": ("==", 0),
}
TEXTOS = {
    "P1": "health/modelo/degradadas/turno único; GPU <10% durante 10 s y colas vacías antes de cada fase; nvidia-smi obligatorio",
    "P2": "exacto y qwen35 en las tres tareas, al empezar y terminar",
    "P3": "límite 7782 y cabe=true en todas las llamadas; context_length informativo",
    "P4": "al menos una receta nueva generada/llm",
    "R1": "100 recetas HTTP 200, clínico no vacío, 0 5xx y 0 413",
    "R2": "frío sin modelo residente ni caché: HTTP <=88 s, 0 504",
    "R3": "caliente sin caché: p95 <=60 s, máximo <=88 s",
    "R4": "redacción + verificación paciente: p95 <=20 s",
    "R5": "elegibles: generada/llm >=90%, timeout <=5%",
    "R6": "todos los elegibles: generada y válida >=90%; respaldo/abstención no válido",
    "R7": "0 críticos en clínico, explicación, plantilla y acciones",
    "R8": "10 recetas generadas y 10 WhatsApp repetidos: caché y 0 llamadas; respaldo reintenta",
    "W1": "50 WhatsApp calientes: 0 5xx, p95 <=20 s",
    "W2": "primera ejecución sin caché: generada >=80%",
    "W3": "aceptables >=90%, críticos=0",
    "C1": "receta durante WhatsApp: 200 con clínico, espera adicional <=20 s",
    "C2": "WhatsApp durante receta: 200 plantilla/ia_ocupada <=1 s",
    "C3": "dos recetas simultáneas con clínico; saturación de cola de 30 s informativa",
    "X1": "corte directo a los 2 s con GPU activa; recuperación <=base+3 s",
    "X2": "timeout redacción=1: plantilla/timeout, GPU activa y recuperación <=base+3 s",
    "X3": "timeout verificación mínimo: respaldo documentado, GPU activa, recuperación <=base+3 s",
    "X4": "plazo global corto vence en clínica, sin 500; GPU activa y recuperación <=base+3 s",
    "X5": "cliente corta clínica activa; siguiente receta <=90 s y turno libre",
    "S1": ">=30 min, 0 errores memoria, 0 reinicios, 0 cambios digest; deriva informativa (+25% alerta)",
    "J1": "informativo: JSON inválido, length, rechazo verificador y tokens/s por etapa",
    "OFF_P": "5 casos con paciente apagado: respaldo correcto y 0 llamadas paciente",
    "OFF_W": "5 casos con WhatsApp apagado: respaldo catálogo correcto y 0 llamadas WhatsApp",
}
PERFILES = {
    "A": tuple(k for k in TEXTOS if k not in ("J1", "OFF_P", "OFF_W")),
    "B": ("P1", "P2", "P3", "R1", "R2", "R3", "R7", "R8", "W1", "W2", "W3", "C1", "C2", "C3", "X1", "X4", "X5", "S1", "OFF_P"),
    "C": ("P1", "P2", "P3", "P4", *tuple("R"+str(i) for i in range(1, 9)), "C3", *tuple("X"+str(i) for i in range(1, 6)), "S1", "OFF_W"),
    "D": ("P1", "P2", "P3", "R1", "R2", "R3", "R7", "C3", "X1", "X4", "X5", "S1", "OFF_P", "OFF_W"),
}


def cumple(nombre, valor):
    op, limite = UMBRALES[nombre]
    if valor is None or not math.isfinite(valor):
        return False
    return {"<=": lambda: valor <= limite, ">=": lambda: valor >= limite,
            "<": lambda: valor < limite, "==": lambda: valor == limite}[op]()


def percentil(valores, p=.95):
    """Rango más próximo; no interpola para ocultar una observación lenta."""
    return sorted(valores)[max(0, math.ceil(len(valores)*p)-1)] if valores else None


def criterio(nombre, valido=None, medido=None, *, verificado=True):
    return dict(umbral=TEXTOS[nombre], medido=medido, estado=(
        "NO VERIFICADO" if not verificado else "PENDIENTE" if valido is None else "APTO" if valido else "NO APTO"))


def perfiles(informe):
    c = informe["criterios"]
    bloqueo = informe.get("rapido") or informe.get("simulado") or informe.get("fases_omitidas") or not informe.get("completa")
    salida = {}
    for perfil, requeridos in PERFILES.items():
        estados = {}
        for k in requeridos:
            valor = c.get(k, {}).get("estado", "NO VERIFICADO")
            if k == "R8" and perfil == "B":
                valor = "APTO" if informe.get("cache_clinico_ok") else "NO APTO"
            if k == "R7" and perfil in ("B", "D"):
                valor = informe.get("revision_respaldo_estado", "PENDIENTE")
            estados[k] = valor
        salida[perfil] = dict(estado="APTO" if not bloqueo and all(v == "APTO" for v in estados.values()) else "NO APTO",
                             criterios=estados)
    informe["perfiles"] = salida
    informe["veredicto_global"] = salida["A"]["estado"]
    return informe


def resumen(medido):
    """Versión corta para informe.md; el detalle completo queda en informe.json."""
    if medido is None:
        return "—"
    if isinstance(medido, list):
        if medido and all(isinstance(x, dict) for x in medido):
            ultimo = medido[-1]
            if "valido" in ultimo:
                partes = [f"{len(medido)} intento(s)", "válido" if ultimo.get("valido") else "no válido"]
                for clave, nombre in (("base", "base"), ("recuperacion", "recuperación")):
                    if isinstance(ultimo.get(clave), (int, float)):
                        partes.append(f"{nombre} {ultimo[clave]:.2f} s")
                return "; ".join(partes)
            return f"{len(medido)} muestras (detalle en informe.json)"
        return f"{len(medido)} elementos"
    if isinstance(medido, dict):
        if medido and all(isinstance(v, dict) and "eval_s" in v for v in medido.values()):
            etapas = []
            for nombre, v in medido.items():
                tiempos = ", ".join(f"{etiqueta} {v.get(campo, 0):.2f} s" for campo, etiqueta in (
                    ("load_s", "carga"), ("prompt_eval_s", "lectura del prompt"),
                    ("eval_s", "decodificación"), ("total_s", "total")))
                tasa = v.get("tokens_s")
                tasa = f"{tasa:.1f} tok/s" if tasa is not None else "tok/s sin datos"
                etapas.append(f"{nombre}: {v['llamadas']} llamadas; {tiempos}; {tasa}; "
                    f"JSON inválido={v['json_invalido']}, length={v['length']}, rechazo={v['verificaciones_rechazadas']}")
            return "<br>".join(etapas)
        partes = []
        for clave, valor in medido.items():
            if isinstance(valor, bool):
                partes.append(f"{clave}={'sí' if valor else 'no'}")
            elif isinstance(valor, int):
                partes.append(f"{clave}={valor}")
            elif isinstance(valor, float):
                partes.append(f"{clave}={valor:.3g}")
            elif isinstance(valor, str) and len(valor) <= 40:
                partes.append(f"{clave}={valor}")
        return ", ".join(partes[:8]) or "detalle en informe.json"
    return str(medido)[:80]


QUE_HACER = {
    "A": "Producción con todo activo (valores por omisión del .env).",
    "B": "Producción con PACIENTE_LLM_HABILITADO=false en el .env de ia-api y reiniciarla.",
    "C": "Producción con SEGUIMIENTO_LLM_HABILITADO=false en el .env de ia-api y reiniciarla.",
    "D": "Producción con PACIENTE_LLM_HABILITADO=false y SEGUIMIENTO_LLM_HABILITADO=false, y reiniciar ia-api.",
}


def escribir(carpeta, informe):
    carpeta = Path(carpeta)
    perfiles(informe)
    def guardar(nombre, texto):
        (carpeta / nombre).write_bytes(texto.replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8"))
    guardar("informe.json", json.dumps(informe, ensure_ascii=False, indent=2) + "\n")
    tabla = ["# Certificación GPU", "", "Veredicto global: **" + informe["veredicto_global"] + "**",
             "", "La revisión manual se realiza antes de consultar este informe.", "",
             "| Criterio | Umbral | Medido | Veredicto |", "|---|---|---|---|"]
    for k, v in informe["criterios"].items():
        medida = resumen(v.get("medido")).replace("|", "/")
        tabla.append(f"| {k} | {v.get('umbral', '')} | {medida} | {v.get('estado', '')} |")
    tabla += ["", "| Perfil | Veredicto | Si es APTO |", "|---|---|---|"]
    tabla += [f"| {k} | {v['estado']} | {QUE_HACER[k]} |" for k, v in informe["perfiles"].items()]
    tabla += ["", "Si ningún perfil es APTO, no se despliega la ia-api nueva. El detalle de cada medición está en informe.json."]
    guardar("informe.md", "\n".join(tabla) + "\n")


def escribir_csv(carpeta, nombre, filas):
    with (Path(carpeta) / nombre).open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]), lineterminator="\r\n")
        w.writeheader()
        w.writerows(filas)


def cerrar(carpeta):
    carpeta = Path(carpeta)
    informe = json.loads((carpeta / "informe.json").read_text(encoding="utf-8"))
    def leer(nombre, originales, columnas):
        crudo = (carpeta / nombre).read_bytes()
        try:
            texto = crudo.decode("utf-8-sig")
        except UnicodeDecodeError:
            # Excel guarda «CSV (delimitado por comas)» en ANSI (Windows-1252).
            texto = crudo.decode("cp1252")
        primera = texto.split("\n", 1)[0]
        separador = ";" if primera.count(";") > primera.count(",") else ","
        filas = list(csv.DictReader(io.StringIO(texto, newline=""), delimiter=separador))
        if len(filas) != len(originales) or [f.get("caso") for f in filas] != [f["id"] for f in originales]:
            raise ValueError("Las filas originales no coinciden")
        for fila in filas:
            for col in columnas:
                if fila.get(col, "").strip().lower() not in ("si", "sí", "no", ""):
                    raise ValueError("Marque únicamente sí o no")
        return filas
    pc = ("valida", "critico_clinico", "critico_explicacion", "critico_acciones", "critico_plantilla")
    wc = ("aceptable", "critico")
    pr = leer("revision_paciente.csv", informe["recetas"], pc)
    wr = leer("revision_whatsapp.csv", informe["whatsapp"], wc)
    si = lambda x: x.strip().lower() in ("si", "sí")
    def revision(filas, columnas):
        criticos = sum(si(f[col]) for f in filas for col in columnas)
        completa = all(f[col].strip() for f in filas for col in columnas)
        return ("NO APTO" if criticos else "APTO" if completa else "PENDIENTE"), criticos
    elegibles = [(r, f) for r, f in zip(informe["recetas"], pr) if r["elegible_personalizacion"]]
    validas = sum(r["generada"] and si(f["valida"]) for r, f in elegibles)
    completa = bool(elegibles) and all(f["valida"].strip() for r, f in elegibles)
    tasa = validas / len(elegibles) if elegibles else 0
    c = informe["criterios"]
    c["R6"] = criterio("R6", cumple("R6_valida", tasa) if completa else None,
                        dict(validas=validas, elegibles=len(elegibles), tasa=tasa))
    estado, n = revision(pr, pc[1:])
    c["R7"] = criterio("R7", None, dict(criticos=n))
    c["R7"]["estado"] = estado
    informe["revision_respaldo_estado"] = revision(pr, ("critico_clinico", "critico_acciones", "critico_plantilla"))[0]
    estado, n = revision(wr, ("critico",))
    marcada = all(f["aceptable"].strip() for f in wr)
    tasa = sum(si(f["aceptable"]) for f in wr) / len(wr) if wr else 0
    c["W3"] = criterio("W3", False if estado == "NO APTO" else
        cumple("W3_aceptables", tasa) if marcada and estado == "APTO" else None,
        dict(aceptables=tasa, criticos=n))
    informe["revision_completa"] = all(f[col].strip() for f in pr for col in pc) and all(f[col].strip() for f in wr for col in wc)
    # Una casilla vacía bloquea TODOS los perfiles, aunque no aplique esa calidad.
    if not informe["revision_completa"]:
        informe["completa"] = False
    else:
        informe["completa"] = informe.get("ejecucion_completa", False)
    escribir(carpeta, informe)
    return informe
