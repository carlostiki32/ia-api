"""Pruebas del kit de certificación en GPU, sin GPU real."""
import csv
import json
from pathlib import Path
import pytest

from app.cache import inference_cache
from app.schemas import ImpresionClinicaRequest
from app.seguimiento.servicio import clave_cache
from app.seguimiento.schemas import SeguimientoWhatsappRequest
from scripts.certificacion.generar_corpus import cargar
from scripts.certificacion.infra import RelojSimulado, TelemetriaSimulada
from scripts.certificacion.kit import Kit
from scripts.certificacion.simulado import servir_simulado
from scripts.certificacion.veredicto import UMBRALES, cerrar, cumple, escribir, perfiles


def test_fronteras_umbrales():
    """Verifica ambos lados de la frontera para cada umbral de UMBRALES."""
    for nombre, (op, limite) in UMBRALES.items():
        if op == "<=":
            assert cumple(nombre, limite) is True, f"{nombre} en límite debe ser True"
            assert cumple(nombre, limite - 0.001) is True, f"{nombre} bajo límite debe ser True"
            assert cumple(nombre, limite + 0.001) is False, f"{nombre} sobre límite debe ser False"
        elif op == ">=":
            assert cumple(nombre, limite) is True, f"{nombre} en límite debe ser True"
            assert cumple(nombre, limite + 0.001) is True, f"{nombre} sobre límite debe ser True"
            assert cumple(nombre, limite - 0.001) is False, f"{nombre} bajo límite debe ser False"
        elif op == "<":
            assert cumple(nombre, limite - 0.001) is True, f"{nombre} bajo límite debe ser True"
            assert cumple(nombre, limite) is False, f"{nombre} en límite debe ser False"
            assert cumple(nombre, limite + 0.001) is False, f"{nombre} sobre límite debe ser False"
        elif op == "==":
            assert cumple(nombre, limite) is True, f"{nombre} en límite debe ser True"
            if isinstance(limite, int):
                assert cumple(nombre, limite + 1) is False, f"{nombre} fuera de límite debe ser False"
                assert cumple(nombre, limite - 1) is False, f"{nombre} fuera de límite debe ser False"
            else:
                assert cumple(nombre, limite + 0.001) is False, f"{nombre} fuera de límite debe ser False"


def test_claves_cache_unicas():
    """El corpus debe tener claves de caché distintas para todas las recetas y mensajes."""
    corpus = cargar()
    recetas = corpus["recetas"]
    whatsapp = corpus["whatsapp"]
    assert len(recetas) == 100
    assert len(whatsapp) == 50

    r_keys = {inference_cache.build_key(ImpresionClinicaRequest.model_validate(r["payload"])) for r in recetas}
    assert len(r_keys) == 100, f"Se esperaban 100 claves únicas de receta, se obtuvieron {len(r_keys)}"

    w_keys = {clave_cache(SeguimientoWhatsappRequest.model_validate(w["payload"])) for w in whatsapp}
    assert len(w_keys) == 50, f"Se esperaban 50 claves únicas de whatsapp, se obtuvieron {len(w_keys)}"


def test_respaldo_no_valido_en_r6(tmp_path):
    """Un caso en respaldo/abstención no suma como válido en R6, aunque se marque 'sí'."""
    # 10 casos elegibles: 8 generadas y 2 en respaldo
    recetas = []
    filas_csv = []
    for i in range(10):
        es_generada = i < 8
        caso_id = f"R{i+1:03}"
        recetas.append(dict(id=caso_id, elegible_personalizacion=True, generada=es_generada))
        # El dueño erróneamente marca "sí" a todos los 10
        filas_csv.append(dict(caso=caso_id, valida="sí", critico_clinico="no", critico_explicacion="no",
                              critico_acciones="no", critico_plantilla="no"))

    informe = dict(completa=True, ejecucion_completa=True, rapido=False, simulado=False,
                   fases_omitidas=[], recetas=recetas, whatsapp=[],
                   criterios={"R6": {}, "R7": {}, "W3": {}})
    escribir(tmp_path, informe)

    # Escribir revision_paciente.csv y revision_whatsapp.csv
    with (tmp_path / "revision_paciente.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas_csv[0]), lineterminator="\r\n")
        w.writeheader()
        w.writerows(filas_csv)

    with (tmp_path / "revision_whatsapp.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["caso", "aceptable", "critico"], lineterminator="\r\n")
        w.writeheader()

    res = cerrar(tmp_path)
    # Tasa = 8 / 10 = 0.80 (< 0.90), por lo que R6 debe ser NO APTO
    medido = res["criterios"]["R6"]["medido"]
    assert medido["validas"] == 8
    assert medido["elegibles"] == 10
    assert medido["tasa"] == 0.80
    assert res["criterios"]["R6"]["estado"] == "NO APTO"


def test_fase_omitida_o_rapido_o_casilla_vacia_nunca_apto(tmp_path):
    """Modo rápido, fase omitida o casilla vacía impiden un veredicto APTO global."""
    # 1. Rapido=True
    inf_rapido = dict(completa=True, ejecucion_completa=True, rapido=True, simulado=False,
                      fases_omitidas=[], criterios={k: {"estado": "APTO"} for k in (
                          "P1", "P2", "P3", "P4", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8",
                          "W1", "W2", "W3", "C1", "C2", "C3", "X1", "X2", "X3", "X4", "X5", "S1")})
    perfiles(inf_rapido)
    assert inf_rapido["veredicto_global"] == "NO APTO"
    assert all(v["estado"] == "NO APTO" for v in inf_rapido["perfiles"].values())

    # 2. Fases omitidas
    inf_omitida = dict(completa=True, ejecucion_completa=False, rapido=False, simulado=False,
                       fases_omitidas=["concurrencia"], criterios=inf_rapido["criterios"])
    perfiles(inf_omitida)
    assert inf_omitida["veredicto_global"] == "NO APTO"

    # 3. Casilla vacía al cerrar
    recetas = [dict(id="R001", elegible_personalizacion=True, generada=True)]
    filas_p = [dict(caso="R001", valida="", critico_clinico="no", critico_explicacion="no",
                    critico_acciones="no", critico_plantilla="no")]
    filas_w = [dict(caso="W001", aceptable="sí", critico="no")]
    inf_cerrar = dict(completa=True, ejecucion_completa=True, rapido=False, simulado=False,
                      fases_omitidas=[], recetas=recetas, whatsapp=[dict(id="W001", generada=True)],
                      criterios={"R6": {}, "R7": {}, "W3": {}})
    escribir(tmp_path, inf_cerrar)
    with (tmp_path / "revision_paciente.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas_p[0]), lineterminator="\r\n")
        w.writeheader()
        w.writerows(filas_p)
    with (tmp_path / "revision_whatsapp.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas_w[0]), lineterminator="\r\n")
        w.writeheader()
        w.writerows(filas_w)

    res = cerrar(tmp_path)
    assert res["revision_completa"] is False
    assert res["completa"] is False
    assert res["veredicto_global"] == "NO APTO"


def test_clave_nunca_aparece_en_archivos(tmp_path):
    """La clave efímera nunca se persiste en informe ni CSVs."""
    clave_secreta = "CLAVE_EFIMERA_SUPER_SECRETA_XYZ_12345"
    informe = dict(completa=True, rapido=False, simulado=False, fases_omitidas=[],
                   recetas=[dict(id="R001", categoria="miopia", entrada_maxima=False,
                                 elegible_personalizacion=True, status=200, duracion=1.0,
                                 generada=True, motivo=None, estado="generada", cache=None,
                                 problema_a1=None, llamadas=[])],
                   whatsapp=[], criterios={"P1": {"umbral": "test", "medido": {}, "estado": "APTO"}})
    escribir(tmp_path, informe)
    with (tmp_path / "revision_paciente.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["caso", "valida"], lineterminator="\r\n")
        w.writeheader()
        w.writerow(dict(caso="R001", valida="sí"))
    with (tmp_path / "revision_whatsapp.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["caso", "aceptable"], lineterminator="\r\n")
        w.writeheader()

    for archivo in tmp_path.iterdir():
        contenido = archivo.read_text(encoding="utf-8", errors="replace")
        assert clave_secreta not in contenido, f"La clave se filtró en {archivo.name}"


def test_veredicto_por_perfil():
    """Matriz de perfiles A, B, C y D según criterios aplicables."""
    todos_aptos = {k: {"estado": "APTO"} for k in (
        "P1", "P2", "P3", "P4", "R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8",
        "W1", "W2", "W3", "C1", "C2", "C3", "X1", "X2", "X3", "X4", "X5", "S1",
        "OFF_P", "OFF_W")}

    # Caso 1: Todo APTO
    inf1 = dict(completa=True, rapido=False, simulado=False, fases_omitidas=[],
                cache_clinico_ok=True, revision_respaldo_estado="APTO", criterios=dict(todos_aptos))
    perfiles(inf1)
    assert inf1["perfiles"]["A"]["estado"] == "APTO"
    assert inf1["perfiles"]["B"]["estado"] == "APTO"
    assert inf1["perfiles"]["C"]["estado"] == "APTO"
    assert inf1["perfiles"]["D"]["estado"] == "APTO"
    assert inf1["veredicto_global"] == "APTO"

    # Caso 2: Calidad de paciente falla (R5 NO APTO) -> A NO APTO, pero B es APTO
    inf2 = dict(completa=True, rapido=False, simulado=False, fases_omitidas=[],
                cache_clinico_ok=True, revision_respaldo_estado="APTO",
                criterios={**todos_aptos, "R5": {"estado": "NO APTO"}})
    perfiles(inf2)
    assert inf2["perfiles"]["A"]["estado"] == "NO APTO"
    assert inf2["perfiles"]["B"]["estado"] == "APTO"
    assert inf2["perfiles"]["C"]["estado"] == "NO APTO"

    # Caso 3: Calidad de WhatsApp falla (W2 NO APTO) -> A NO APTO, pero C es APTO
    inf3 = dict(completa=True, rapido=False, simulado=False, fases_omitidas=[],
                cache_clinico_ok=True, revision_respaldo_estado="APTO",
                criterios={**todos_aptos, "W2": {"estado": "NO APTO"}})
    perfiles(inf3)
    assert inf3["perfiles"]["A"]["estado"] == "NO APTO"
    assert inf3["perfiles"]["B"]["estado"] == "NO APTO"
    assert inf3["perfiles"]["C"]["estado"] == "APTO"

    # Caso 4: Fallan paciente y WhatsApp -> D es APTO
    inf4 = dict(completa=True, rapido=False, simulado=False, fases_omitidas=[],
                cache_clinico_ok=True, revision_respaldo_estado="APTO",
                criterios={**todos_aptos, "R5": {"estado": "NO APTO"}, "W2": {"estado": "NO APTO"}})
    perfiles(inf4)
    assert inf4["perfiles"]["A"]["estado"] == "NO APTO"
    assert inf4["perfiles"]["B"]["estado"] == "NO APTO"
    assert inf4["perfiles"]["C"]["estado"] == "NO APTO"
    assert inf4["perfiles"]["D"]["estado"] == "APTO"

    # Caso 5: Falla criterio base P1 -> ningún perfil es APTO
    inf5 = dict(completa=True, rapido=False, simulado=False, fases_omitidas=[],
                cache_clinico_ok=True, revision_respaldo_estado="APTO",
                criterios={**todos_aptos, "P1": {"estado": "NO APTO"}})
    perfiles(inf5)
    assert all(p["estado"] == "NO APTO" for p in inf5["perfiles"].values())

    # Caso 6: Falla clínico R1 -> ningún perfil es APTO
    inf6 = dict(completa=True, rapido=False, simulado=False, fases_omitidas=[],
                cache_clinico_ok=True, revision_respaldo_estado="APTO",
                criterios={**todos_aptos, "R1": {"estado": "NO APTO"}})
    perfiles(inf6)
    assert all(p["estado"] == "NO APTO" for p in inf6["perfiles"].values())


def test_cerrar_con_hojas_marcadas_ejemplo(tmp_path):
    """--cerrar completa R6, R7 y W3 a partir de CSVs marcados."""
    recetas = [dict(id=f"R{i:03}", elegible_personalizacion=True, generada=True) for i in range(1, 101)]
    whatsapp = [dict(id=f"W{i:03}", elegible_personalizacion=True, generada=True) for i in range(1, 51)]

    informe = dict(completa=True, ejecucion_completa=True, rapido=False, simulado=False,
                   fases_omitidas=[], recetas=recetas, whatsapp=whatsapp,
                   criterios={"R6": {}, "R7": {}, "W3": {}})
    escribir(tmp_path, informe)

    filas_p = [dict(caso=r["id"], valida="sí", critico_clinico="no", critico_explicacion="no",
                    critico_acciones="no", critico_plantilla="no") for r in recetas]
    filas_w = [dict(caso=w["id"], aceptable="sí", critico="no") for w in whatsapp]

    with (tmp_path / "revision_paciente.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas_p[0]), lineterminator="\r\n")
        w.writeheader()
        w.writerows(filas_p)

    with (tmp_path / "revision_whatsapp.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas_w[0]), lineterminator="\r\n")
        w.writeheader()
        w.writerows(filas_w)

    res = cerrar(tmp_path)
    assert res["criterios"]["R6"]["estado"] == "APTO"
    assert res["criterios"]["R7"]["estado"] == "APTO"
    assert res["criterios"]["W3"]["estado"] == "APTO"
    assert res["revision_completa"] is True


def test_corrida_completa_modo_rapido(tmp_path):
    """Corrida completa contra el simulado en modo rápido."""
    with servir_simulado() as sim:
        reloj = RelojSimulado()
        telemetria = TelemetriaSimulada(sim)
        kit = Kit(tmp_path, rapido=True, simulado=sim, reloj=reloj, telemetria=telemetria, progreso=lambda _: None)
        inf = kit.ejecutar()

        assert (tmp_path / "informe.json").exists()
        assert (tmp_path / "informe.md").exists()
        assert (tmp_path / "revision_paciente.csv").exists()
        assert (tmp_path / "revision_whatsapp.csv").exists()

        assert len(inf["recetas"]) == 100
        assert len(inf["whatsapp"]) == 50
        j1 = inf["criterios"]["J1"]["medido"]
        for nombre, tiempos in j1.items():
            tarea, etapa = nombre.split('/')
            llamadas = [r for r in inf['llamadas'] if r['tarea'] == tarea and r['etapa'] == etapa]
            for campo, origen in (('load_s', 'load_duration'), ('prompt_eval_s', 'prompt_eval_duration'),
                                  ('eval_s', 'eval_duration'), ('total_s', 'total_duration')):
                assert tiempos[campo] > 0
                assert tiempos[campo] == pytest.approx(sum(r[origen] for r in llamadas) / 1e9)
        fila_j1 = next(f for f in (tmp_path / 'informe.md').read_text(encoding='utf-8').splitlines() if f.startswith('| J1 |'))
        assert all(nombre in fila_j1 for nombre in j1)
        assert 'lectura del prompt' in fila_j1 and 'detalle en informe.json' not in fila_j1
        assert all(inf["fases"][f] == "COMPLETA" for f in (
            "frio", "recetas", "whatsapp", "cache", "concurrencia", "cancelacion", "perfiles", "sostenida"
        ))

        # En modo rápido nunca da APTO global
        assert inf["veredicto_global"] == "NO APTO"

        # Marcar las hojas y cerrar
        pr_path = tmp_path / "revision_paciente.csv"
        with pr_path.open(encoding="utf-8-sig", newline="") as f:
            filas_p = list(csv.DictReader(f))
        for row in filas_p:
            row["valida"] = "sí"
            row["critico_clinico"] = "no"
            row["critico_explicacion"] = "no"
            row["critico_acciones"] = "no"
            row["critico_plantilla"] = "no"
        with pr_path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(filas_p[0]), lineterminator="\r\n")
            w.writeheader()
            w.writerows(filas_p)

        wr_path = tmp_path / "revision_whatsapp.csv"
        with wr_path.open(encoding="utf-8-sig", newline="") as f:
            filas_w = list(csv.DictReader(f))
        for row in filas_w:
            row["aceptable"] = "sí"
            row["critico"] = "no"
        with wr_path.open("w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(filas_w[0]), lineterminator="\r\n")
            w.writeheader()
            w.writerows(filas_w)

        cerrado = cerrar(tmp_path)
        assert cerrado["criterios"]["R6"]["estado"] == "APTO"
        assert cerrado["criterios"]["R7"]["estado"] == "APTO"
        assert cerrado["criterios"]["W3"]["estado"] == "APTO"
        # Sigue siendo NO APTO global porque rapido=True
        assert cerrado["veredicto_global"] == "NO APTO"
@pytest.mark.parametrize("codificacion,separador", [("cp1252", ","), ("cp1252", ";"), ("utf-8-sig", ";")])
def test_cerrar_acepta_hojas_guardadas_por_excel(tmp_path, codificacion, separador):
    """Excel en español puede guardar en ANSI y con punto y coma: «sí» no debe romper el cierre."""
    recetas = [dict(id=f"R{i:03}", elegible_personalizacion=True, generada=True) for i in range(1, 101)]
    whatsapp = [dict(id=f"W{i:03}", elegible_personalizacion=True, generada=True) for i in range(1, 51)]
    escribir(tmp_path, dict(completa=True, ejecucion_completa=True, rapido=False, simulado=False,
                            fases_omitidas=[], recetas=recetas, whatsapp=whatsapp,
                            criterios={"R6": {}, "R7": {}, "W3": {}}))
    hojas = (("revision_paciente.csv", [dict(caso=r["id"], valida="Sí", critico_clinico="no", critico_explicacion="NO",
                                             critico_acciones="no", critico_plantilla="no") for r in recetas]),
             ("revision_whatsapp.csv", [dict(caso=w["id"], aceptable="sí", critico="no") for w in whatsapp]))
    for nombre, filas in hojas:
        with (tmp_path / nombre).open("w", encoding=codificacion, newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(filas[0]), delimiter=separador, lineterminator="\r\n")
            w.writeheader()
            w.writerows(filas)
    res = cerrar(tmp_path)
    assert [res["criterios"][k]["estado"] for k in ("R6", "R7", "W3")] == ["APTO"] * 3


def test_informe_md_legible(tmp_path):
    """informe.md resume las mediciones; el detalle completo queda en informe.json."""
    from scripts.certificacion.veredicto import resumen
    intentos = [dict(valido=True, base=0.5, recuperacion=1.25, activa={"muestra": {"gpus": [1] * 50}})]
    assert resumen(intentos) == "1 intento(s); válido; base 0.50 s; recuperación 1.25 s"
    assert resumen(dict(p95=12.3456, maximo=40.0, ok=True, ps={"models": []})) == "p95=12.3, maximo=40, ok=sí"
    assert resumen([dict(id=i) for i in range(5)]) == "5 muestras (detalle en informe.json)"
    assert resumen(None) == "—"


def test_proxy_duraciones_sin_contenido(monkeypatch):
    from types import SimpleNamespace
    from threading import Lock
    from http import HTTPStatus
    import httpx
    from scripts.certificacion import servidor
    from app.prompt_builder import build_system_prompt

    duraciones = dict(load_duration=10000000, prompt_eval_duration=20000000,
                      eval_duration=100000000, total_duration=130000000)
    respuesta = dict(message={'content': 'SECRETO_RESPUESTA'}, prompt_eval_count=10,
                     eval_count=30, done_reason='stop', **duraciones)
    cuerpo = dict(messages=[{'role': 'system', 'content': build_system_prompt()},
                           {'role': 'user', 'content': 'SECRETO_ENTRADA'}],
                  options={'num_predict': 100})
    capturado = []
    def upstream(req):
        assert json.loads(req.content) == cuerpo
        return httpx.Response(HTTPStatus.OK, json=respuesta)
    cliente = httpx.Client(transport=httpx.MockTransport(upstream))
    monkeypatch.setattr(servidor.httpx, 'Client', lambda **kwargs: cliente)
    handler = object.__new__(servidor.Handler)
    handler.path = '/api/chat'
    handler.server = SimpleNamespace(upstream='http://simulado', lock=Lock(), etiqueta='prueba', registros=[], activos=0)
    handler.enviar = lambda dato, status=200: capturado.append((dato, status))
    handler.reenviar(cuerpo)
    assert capturado == [(respuesta, HTTPStatus.OK)]
    assert len(handler.server.registros) == 1
    registro = handler.server.registros[0]
    for campo, valor in duraciones.items():
        assert registro[campo] == valor
    assert 'SECRETO' not in json.dumps(registro)
    assert build_system_prompt() not in json.dumps(registro)
    assert not {'messages', 'message', 'content', 'response', 'prompt'} & registro.keys()


def test_resumen_j1_tiempos_en_segundos(tmp_path):
    from scripts.certificacion.veredicto import resumen, criterio
    etapas = {nombre: dict(llamadas=2, load_s=.12, prompt_eval_s=1.23, eval_s=4.56,
                          total_s=5.91, tokens_s=25., json_invalido=0, length=1,
                          verificaciones_rechazadas=0)
              for nombre in ('receta-clinica/clinica', 'explicacion-paciente/redaccion', 'explicacion-paciente/verificacion')}
    texto = resumen(etapas)
    for nombre in etapas:
        assert nombre in texto
    assert 'carga 0.12 s' in texto and 'lectura del prompt 1.23 s' in texto
    assert 'decodificaci\u00f3n 4.56 s' in texto and 'total 5.91 s' in texto
    assert '25.0 tok/s' in texto and 'length=1' in texto
    informe = dict(criterios={'J1': criterio('J1', medido=etapas)})
    escribir(tmp_path, informe)
    fila = next(f for f in (tmp_path / 'informe.md').read_text(encoding='utf-8').splitlines() if f.startswith('| J1 |'))
    assert texto in fila and 'detalle en informe.json' not in fila
