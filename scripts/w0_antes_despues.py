"""Compara W0 contra una foto de app/ sin revertir ni importar proveedores.

Ejemplo: python scripts/w0_antes_despues.py --foto-previa <foto> --salida <json>
Captura los payloads reales de la suite, extrae literales AST y cadenas JSON de
pruebas/fixtures y ejecuta evaluar_correlaciones_con_nombres en procesos aislados.
Los literales se prueban en todos los campos libres donde caben por contrato;
no se truncan. Los escenarios sinteticos se identifican como tales en el informe.
"""
from __future__ import annotations

import argparse
import ast
from collections import Counter
import hashlib
import json
import re
from pathlib import Path
import subprocess
import sys


ALIASES = {
    "motivo": ("paciente", "motivo_consulta"), "ocupacion": ("paciente", "ocupacion"),
    "edad": ("paciente", "edad"), "fondo": ("clinica", "fondo_de_ojo"),
    "anexos": ("clinica", "anexos_oculares"), "pupilas": ("clinica", "reflejos_pupilares"),
    "motilidad": ("clinica", "motilidad_ocular"), "campos": ("clinica", "confrontacion_campos_visuales"),
    "amsler": ("clinica", "grid_de_amsler"), "cover": ("clinica", "cover_test"),
    "seguimiento": ("clinica", "recomendacion_seguimiento"), "ppc": ("clinica", "ppc_cm"),
    "but": ("clinica", "ojo_seco_but_seg"), "pantallas": ("clinica", "uso_pantallas"),
    "lente": ("tipo_lente",),
}
LIBRES = ("motivo", "ocupacion", "fondo", "anexos", "pupilas", "motilidad", "campos", "amsler", "cover", "seguimiento")
REPRODUCCIONES = [
    {"motivo": "Niega p\u00e9rdida visual s\u00fabita, destellos nuevos y una sombra sobre la visi\u00f3n."},
    {"motivo": "Niega dolor, destellos y moscas volantes."},
    {"pupilas": "Sin ptosis, miosis y anisocoria."},
    {"motivo": "Niega visi\u00f3n borrosa, cansancio visual y ardor ocular.", "pantallas": "gt6",
     "cover": "OD: Exo y Foria | OI: Exo y Foria", "ppc": 12},
]
EXPECTATIVAS = [
    {'prueba': 'test_barrido_metamorfico: Sin cefalea, diplopia desde hoy.', 'justificacion': 'Restituida: detecta diplopia_aguda. Coma sin coordinador de cierre.'},
    {'prueba': 'test_barrido_metamorfico: Sin hemorragias, edema de papila AO.', 'justificacion': 'Restituida: detecta fondo_hipertensivo con PA critica. Coma sin coordinador de cierre.'},
    {'prueba': 'test_auditoria_correlaciones::test_t1_13_sin_hemorragias_desgarro_temporal_superior', 'justificacion': 'Restituida: detecta fondo_periferico_riesgo urgente. Coma sin coordinador de cierre.'},
    {'prueba': 'test_auditoria_correlaciones::test_t1_14_sin_hemorragias_ni_exudados_drusas_blandas', 'justificacion': 'Restituida: detecta fondo_macular_dmae. Ni esta antes de la coma, no cierra la lista posterior.'},
    {'prueba': 'test_auditoria_correlaciones::test_t1_15_sin_hemorragias_drusas_blandas', 'justificacion': 'Restituida: detecta fondo_macular_dmae. Coma sin coordinador de cierre.'},
    {'prueba': 'test_correlaciones::test_auditoria_bloque_a_falsos_negativos, A-05', 'justificacion': 'Restituida: detecta anexos_patologicos por blefaritis. Coma sin coordinador de cierre.'},
    {'prueba': 'test_correlaciones::test_negacion_quiebre_conector_con_y_cambio_ojo, D1', 'justificacion': 'Restituida: detecta fondo_periferico_riesgo. Con precede al match desgarro, no pertenece a este.'},
]


def guardar(path, valor):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    serializado = json.dumps(valor, ensure_ascii=False, indent=2)
    # Los controles de codificacion del corpus contienen estas marcas como
    # datos. Escaparlas conserva su valor JSON sin contaminar el archivo UTF-8.
    for marca in ("\ufffd", "\u00c3", "\u00c2"):
        serializado = serializado.replace(marca, f"\\u{ord(marca):04x}")
    path.write_bytes((serializado + "\n").replace("\r\n", "\n").replace("\n", "\r\n").encode("utf-8", errors="backslashreplace"))


def clave(data):
    return json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def base():
    return {"receta_id": "w0-corpus", "refraccion": {"od": {"esfera": 0}, "oi": {"esfera": 0}}}


def entrada_alias(entrada):
    data = base()
    for k, v in entrada.items():
        if k.startswith("rx_"):
            data["refraccion"].setdefault(k[-2:], {}).update(v)
        elif k.startswith("akr_"):
            data.setdefault("akr", {}).setdefault(k[-2:], {}).update(v)
        elif k == "akr":
            data[k] = v
        elif k in ALIASES:
            ruta = ALIASES[k]
            if len(ruta) == 1:
                data[ruta[0]] = v
            else:
                data.setdefault(ruta[0], {})[ruta[1]] = v
        else:
            return None
    return data


class Captura:
    def __init__(self):
        self.casos = {}
        self.prueba = "coleccion"

    def pytest_sessionstart(self, session):
        import app.correlaciones.registry as registro
        for nombre in ("_evaluar", "nombres_correlaciones_activas"):
            original = getattr(registro, nombre)
            def envolver(req, original=original):
                data = req.model_dump(mode="json", exclude_none=True)
                data["receta_id"] = "w0-corpus"
                data.pop("salida_version", None)
                item = self.casos.setdefault(clave(data), {"payload": data, "fuentes": []})
                if self.prueba not in item["fuentes"]:
                    item["fuentes"].append(self.prueba)
                return original(req)
            setattr(registro, nombre, envolver)

    def pytest_runtest_setup(self, item):
        self.prueba = item.nodeid


def evaluar(root, corpus, resultado, trazar=None):
    sys.path.insert(0, str(Path(root).resolve()))
    from app.correlaciones.registry import evaluar_correlaciones_con_nombres
    from app.schemas import ImpresionClinicaRequest
    salidas = []
    indices = set(json.loads(Path(trazar).read_text(encoding="utf-8"))) if trazar else None
    for indice, caso in enumerate(json.loads(Path(corpus).read_text(encoding="utf-8"))):
        if indices is not None and indice not in indices:
            continue
        req = ImpresionClinicaRequest.model_validate(caso["payload"])
        if indices is None:
            salidas.append(evaluar_correlaciones_con_nombres(req))
        else:
            trazas = {}
            def perfil(frame, event, arg):
                if event == "return" and frame.f_code.co_name == "_is_match_negated":
                    local = frame.f_locals
                    texto, inicio, fin = local["text"], local["start"], local["end"]
                    item = {"texto_normalizado": texto, "inicio": inicio, "fin": fin,
                            "ocurrencia": texto[inicio:fin], "negada": bool(arg), "fin_sufijo": local.get("fin_sufijo")}
                    trazas[clave(item)] = item
            sys.setprofile(perfil)
            try:
                evaluar_correlaciones_con_nombres(req)
            finally:
                sys.setprofile(None)
            salidas.append({"indice": indice, "comprobaciones": list(trazas.values())})
    guardar(resultado, salidas)


def recopilar(repo, foto, captura):
    from app.schemas import ImpresionClinicaRequest
    casos, textos = {}, {}
    def agregar(data, fuente):
        if data is None:
            return
        try:
            req = ImpresionClinicaRequest.model_validate(data)
        except ValueError:
            return
        data = req.model_dump(mode="json", exclude_none=True)
        data["receta_id"] = "w0-corpus"
        data.pop("salida_version", None)
        item = casos.setdefault(clave(data), {"payload": data, "fuentes": []})
        if fuente not in item["fuentes"]:
            item["fuentes"].append(fuente)
    for item in captura:
        for fuente in item["fuentes"]:
            agregar(item["payload"], "prueba:" + fuente)
    archivos = {}
    for origen, raiz in (("previa", foto), ("actual", repo)):
        rutas = list((raiz / "tests").rglob("*.py")) + list((raiz / "tests" / "fixtures").rglob("*"))
        if origen == "actual":
            rutas += list((raiz / "auditoria").rglob("*.json"))
        for p in sorted(set(rutas)):
            if not p.is_file() or p.suffix not in (".py", ".json", ".txt", ".csv", ".tsv"):
                continue
            rel = p.relative_to(raiz).as_posix()
            raw = p.read_bytes()
            archivos[origen + ":" + rel] = hashlib.sha256(raw).hexdigest()
            if p.suffix == ".py":
                tree = ast.parse(raw.decode("utf-8-sig"))
                for nodo in ast.walk(tree):
                    if isinstance(nodo, ast.Constant) and isinstance(nodo.value, str) and nodo.value.strip():
                        textos.setdefault(nodo.value, set()).add(f"{origen}:{rel}:{nodo.lineno}")
            elif p.suffix == ".json":
                def visitar(obj, ruta):
                    if isinstance(obj, str) and obj.strip():
                        textos.setdefault(obj, set()).add(f"{origen}:{rel}:{ruta}")
                    elif isinstance(obj, list):
                        for i, v in enumerate(obj):
                            visitar(v, f"{ruta}[{i}]")
                    elif isinstance(obj, dict):
                        if "entrada" in obj and isinstance(obj["entrada"], dict):
                            agregar(entrada_alias(obj["entrada"]), f"fixture:{rel}:{obj.get('id', ruta)}")
                        if "receta_id" in obj and ("clinica" in obj or "refraccion" in obj):
                            agregar(obj, f"fixture:{rel}:{ruta}")
                        for k, v in obj.items():
                            visitar(v, f"{ruta}.{k}")
                visitar(json.loads(raw.decode("utf-8-sig")), "$")
            else:
                valor = raw.decode("utf-8-sig")
                textos.setdefault(valor, set()).add(f"{origen}:{rel}")
    omitidas = []
    for i, (texto, fuentes) in enumerate(sorted(textos.items())):
        if len(texto) > 60000:
            omitidas.append({"longitud": len(texto), "fuentes": sorted(fuentes), "motivo": "Excede todos los campos libres del contrato; no se trunca."})
            continue
        for campo in LIBRES:
            if len(texto) > (60000 if campo == "seguimiento" else 120 if campo == "ocupacion" else 1000 if campo == "motivo" else 255):
                continue
            entrada = {campo: texto}
            # Un segundo contexto activa consumidores de sintomas de cerca/pantallas.
            contextos = [entrada]
            if campo == "motivo":
                contextos.append({**entrada, "pantallas": "gt6", "cover": "OD: Exo y Foria | OI: Exo y Foria", "ppc": 12})
            for j, contexto in enumerate(contextos):
                agregar(entrada_alias(contexto), f"literal:{i}:{campo}:{j}")
    for i, entrada in enumerate(REPRODUCCIONES, 1):
        agregar(entrada_alias(entrada), f"diseno:reproduccion-{i}")
    return list(casos.values()), archivos, textos, omitidas


def comparar(args):
    repo = Path(__file__).resolve().parents[1]
    foto, salida = Path(args.foto_previa).resolve(), Path(args.salida).resolve()
    trabajo = salida.parent
    trabajo.mkdir(parents=True, exist_ok=True)
    assert (foto / "app/correlaciones/texto.py").is_file()
    sys.path.insert(0, str(repo))
    captura_path = trabajo / "w0-payloads-pruebas.json"
    log = trabajo / "w0-pytest-completo.txt"
    if args.reutilizar_captura:
        captura = json.loads(captura_path.read_text(encoding="utf-8"))
        codigo_pytest = None
    else:
        import contextlib
        import pytest
        plugin = Captura()
        with log.open("w", encoding="utf-8", newline="\r\n") as stream, contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
            codigo_pytest = int(pytest.main(["-q", "-p", "no:cacheprovider"], plugins=[plugin]))
        captura = list(plugin.casos.values())
        guardar(captura_path, captura)
        print("pytest:", codigo_pytest, "payloads unicos:", len(captura), "log:", log, flush=True)
    import logging
    logging.disable(logging.CRITICAL)
    casos, archivos, textos, omitidas = recopilar(repo, foto, captura)
    corpus = trabajo / "w0-corpus.json"
    guardar(corpus, casos)
    print("Corpus:", len(casos), "casos;", len(textos), "cadenas unicas", flush=True)
    resultados = []
    for nombre, raiz in (("antes", foto), ("despues", repo)):
        destino = trabajo / f"w0-{nombre}.json"
        subprocess.run([sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve()),
                        "--evaluar-root", str(raiz), "--corpus", str(corpus), "--resultado", str(destino)],
                       cwd=trabajo, check=True)
        resultados.append(json.loads(destino.read_text(encoding="utf-8")))
        print(nombre, "evaluado", flush=True)
    cambios, solo_texto, tipos = [], [], Counter()
    for i, (caso, antes, despues) in enumerate(zip(casos, *resultados)):
        an, de = {n for n, _ in antes}, {n for n, _ in despues}
        if antes == despues:
            continue
        if an == de:
            solo_texto.append({"indice": i, "payload": caso["payload"], "fuentes": caso["fuentes"], "antes": antes, "despues": despues,
                               "justificacion": "Mismo conjunto; cambian las menciones afirmadas o la variante al respetar la negacion por ocurrencia."})
            continue
        quitadas, agregadas = sorted(an - de), sorted(de - an)
        tipo = "retiro_falso_positivo" if quitadas and not agregadas else "reporte_positivo_recuperado" if agregadas and not quitadas else "jerarquia_tras_negacion"
        tipos[tipo] += 1
        razones = {
            "retiro_falso_positivo": "Revisar evidencia por ocurrencia: solo se admite retirar elementos de enumeraciones negadas cerradas por coordinador.",
            "reporte_positivo_recuperado": "El reporte positivo/adversativo o el encabezado de otro ojo corta la negacion; la ocurrencia posterior conserva su afirmacion y su lado.",
            "jerarquia_tras_negacion": "Al corregir la afirmacion por ocurrencia cambia la supresion entre correlaciones; se retiran las basadas en menciones negadas y quedan las respaldadas por hechos afirmados.",
        }
        cambios.append({"indice": i, "payload": caso["payload"], "fuentes": caso["fuentes"], "antes": antes, "despues": despues,
                        "quitadas": quitadas, "agregadas": agregadas, "tipo": tipo, "justificacion": razones[tipo]})
    # Evidencia por ocurrencia de cada cambio: texto, offsets y decision real
    # del matcher en cada version, incluidas llamadas desde fragmentadores.
    indices_path = trabajo / "w0-indices-cambios.json"
    guardar(indices_path, [c["indice"] for c in cambios + solo_texto])
    for nombre, raiz in (("antes", foto), ("despues", repo)):
        destino = trabajo / f"w0-trazas-{nombre}.json"
        subprocess.run([sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve()),
                        "--evaluar-root", str(raiz), "--corpus", str(corpus), "--resultado", str(destino),
                        "--trazar", str(indices_path)], cwd=trabajo, check=True)
        trazas = {t["indice"]: t["comprobaciones"] for t in json.loads(destino.read_text(encoding="utf-8"))}
        for cambio in cambios + solo_texto:
            cambio["evidencia_" + nombre] = trazas[cambio["indice"]]
    for cambio in cambios:
        cambio["justificacion_por_correlacion"] = {
            nombre: ("Se retira " if nombre in cambio["quitadas"] else "Se activa ") + nombre + ": " + cambio["justificacion"]
            for nombre in cambio["quitadas"] + cambio["agregadas"]
        }
        cambio["escenario"] = "prueba_o_fixture" if any(f.startswith(("prueba:", "fixture:", "diseno:")) for f in cambio["fuentes"]) else "literal_sintetico"
    # Toda baja queda visible, incluso si se agrega otra correlacion en el
    # mismo payload: no confundir cambios de jerarquia con ausencia de bajas.
    perdidas = [{"indice": c["indice"], "payload": c["payload"], "fuentes": c["fuentes"],
                 "correlaciones_perdidas": c["quitadas"],
                 "evidencia_antes": c["evidencia_antes"], "evidencia_despues": c["evidencia_despues"]}
                for c in cambios if c["quitadas"]]
    # La evidencia debe localizar un hallazgo realmente negado dentro de la
    # lista del payload original, con coordinador de cierre y sin reporte nuevo.
    from app.correlaciones.texto import (
        _normalize_text, _find_neg_bounded, _NEGACIONES_PRE, _NUEVA_CLAUSULA_RE,
        _INICIO_TIEMPO_RE, _NUCLEO_ANTECEDENTES_RE,
    )
    sin_justificar = []
    for perdida in perdidas:
        enumeraciones = []
        for bloque in ("paciente", "clinica"):
            for campo, valor in perdida["payload"].get(bloque, {}).items():
                if not isinstance(valor, str):
                    continue
                norm = _normalize_text(valor)
                hechos = []
                for t in perdida["evidencia_despues"]:
                    if t["texto_normalizado"].rstrip(" .;:!?|\n") != norm.rstrip(" .;:!?|\n") or not t["negada"]:
                        continue
                    ini, fin = t["inicio"], t["fin"]
                    inicio_clausula = max(norm.rfind(sep, 0, ini) for sep in ".;:!?|\n") + 1
                    finales = [pos for sep in ".;:!?|\n" if (pos := norm.find(sep, fin)) != -1]
                    fin_clausula = min(finales) if finales else len(norm)
                    coma = norm.rfind(",", inicio_clausula, ini)
                    # Tambien hay listas cerradas sin coma: "Niega A y B".
                    # La traza exige que el hallazgo este realmente negado.
                    fin_prefijo = coma if coma != -1 else ini
                    inicio_lista = coma + 1 if coma != -1 else inicio_clausula
                    prefijo_negado = norm[inicio_clausula:fin_prefijo]
                    if not any(_find_neg_bounded(prefijo_negado, neg) != -1 for neg in _NEGACIONES_PRE):
                        continue
                    coordinadores = re.findall(r"\b(?:ni|o|u|y|e)\b", norm[inicio_lista:fin_clausula])
                    if (not coordinadores or _NUEVA_CLAUSULA_RE.search(norm[inicio_lista:ini])
                            or _INICIO_TIEMPO_RE.search(norm[inicio_lista:fin_clausula])
                            or _NUCLEO_ANTECEDENTES_RE.search(prefijo_negado)):
                        continue
                    hechos.append({"ocurrencia": t["ocurrencia"], "inicio": ini, "fin": fin,
                                   "coordinadores_de_cierre": sorted(set(coordinadores))})
                if hechos:
                    enumeraciones.append({"campo": bloque + "." + campo, "texto": valor, "hallazgos_negados": hechos})
        perdida["enumeraciones_negadas_cerradas"] = enumeraciones
        perdida["justificacion"] = ("Retiro permitido: enumeracion negada cerrada por coordinador, sin tiempo ni nucleo de antecedentes."
                                     if enumeraciones else "BAJA FUERA DEL PRINCIPIO: requiere correccion.")
        if not enumeraciones:
            sin_justificar.append(perdida["indice"])
    codigo_fuentes = {}
    for nombre, raiz in (("antes", foto), ("despues", repo)):
        codigo_fuentes[nombre] = {str(p.relative_to(raiz)): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in sorted((raiz / "app").rglob("*.py"))}
    guardar(salida, {"alcance": "Solo W0. Foto previa copiada del arbol de trabajo; no se usa git checkout ni se revierten archivos.",
                     "metodo": "Payloads reales capturados en la suite, fixtures JSON y todas las cadenas literales AST/JSON (incluidas expectativas y controles no clinicos), en todos los campos libres validos. Los escenarios literal:* son sinteticos, no pacientes ni casos originales completos.",
                     "foto_previa": str(foto), "corpus": str(corpus), "pytest_log": str(log), "pytest_exit_code": codigo_pytest,
                     "archivos_fuente_sha256": archivos, "codigo_fuente_sha256": codigo_fuentes,
                     "cadenas": [{"indice": i, "texto": t, "fuentes": sorted(f)} for i, (t, f) in enumerate(sorted(textos.items()))],
                     "resumen": {"payloads_pruebas": len(captura), "cadenas_unicas": len(textos), "casos": len(casos),
                                 "cambian_conjunto": len(cambios), "cambian_solo_detalles": len(solo_texto), "tipos": dict(tipos),
                                 "cadenas_fuera_de_contrato": len(omitidas), "casos_con_detecciones_perdidas": len(perdidas),
                                 "perdidas_fuera_de_enumeraciones_cerradas": len(sin_justificar),
                                 "cambios_pruebas_fixtures": sum(c["escenario"] == "prueba_o_fixture" for c in cambios)},
                     "fuera_de_contrato": omitidas, "expectativas_corregidas": EXPECTATIVAS,
                     "detecciones perdidas respecto a la foto": perdidas,
                     "perdidas_sin_justificar": sin_justificar,
                     "cambios": cambios, "mismo_conjunto_distintos_detalles": solo_texto})
    print(json.dumps({"informe": str(salida), "casos": len(casos), "cambian_conjunto": len(cambios), "solo_detalles": len(solo_texto), "tipos": tipos, "detecciones_perdidas": len(perdidas), "perdidas_fuera_de_enumeraciones_cerradas": len(sin_justificar)}, ensure_ascii=False), flush=True)

    if sin_justificar:
        raise SystemExit("Hay detecciones perdidas fuera de enumeraciones cerradas: " + str(sin_justificar))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--foto-previa")
    parser.add_argument("--salida")
    parser.add_argument("--reutilizar-captura", action="store_true")
    parser.add_argument("--evaluar-root")
    parser.add_argument("--corpus")
    parser.add_argument("--resultado")
    parser.add_argument("--trazar")
    args = parser.parse_args()
    if args.evaluar_root:
        evaluar(args.evaluar_root, args.corpus, args.resultado, args.trazar)
    else:
        if not args.foto_previa or not args.salida:
            parser.error("Se requieren --foto-previa y --salida")
        comparar(args)
