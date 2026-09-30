"""Aceptacion #42: hechos de PPC/cover y molestias actuales, sin etiqueta etiologica."""
import hashlib
import json
from pathlib import Path

import pytest

from app.correlaciones import binocularidad as dominio
from app.schemas import ImpresionClinicaRequest

ROOT = Path(__file__).parents[1]
CORPUS = json.loads((ROOT / "auditoria/2026-09-21/casos.json").read_text(encoding="utf-8"))
ALIAS = {"fondo": ("clinica", "fondo_de_ojo"), "anexos": ("clinica", "anexos_oculares"),
         "pupilas": ("clinica", "reflejos_pupilares"), "motilidad": ("clinica", "motilidad_ocular"),
         "campos": ("clinica", "confrontacion_campos_visuales"), "amsler": ("clinica", "grid_de_amsler"),
         "cover": ("clinica", "cover_test"), "ppc": ("clinica", "ppc_cm"),
         "but": ("clinica", "ojo_seco_but_seg"), "pantallas": ("clinica", "uso_pantallas"),
         "motivo": ("paciente", "motivo_consulta"), "ocupacion": ("paciente", "ocupacion"),
         "edad": ("paciente", "edad"), "seguimiento": ("clinica", "recomendacion_seguimiento")}


def request(**datos):
    """Sin defaults refractivos: lo ausente sigue ausente en estas reproducciones."""
    payload = {"receta_id": "ajuste-clinico", "tipo_lente": datos.get("lente", "monofocal")}
    for clave, valor in datos.items():
        if clave == "lente":
            continue
        if clave.startswith("rx_"):
            payload.setdefault("refraccion", {})[clave[-2:]] = valor
        elif clave.startswith("akr_"):
            payload.setdefault("akr", {})[clave[-2:]] = valor
        elif clave == "akr":
            payload[clave] = valor
        else:
            bloque, nombre = ALIAS[clave]
            payload.setdefault(bloque, {})[nombre] = valor
    return ImpresionClinicaRequest.model_validate(payload)


def cases(numero):
    return {c["id"].split("-")[1]: c for c in CORPUS if c["id"].startswith(f"C{numero}-")}


def persistir(numero, modulo, condicion, texto, expectativas, resumen, fuentes, pytest_resultado):
    """Se ejecuta tras cada caso cerrado, antes de editar la siguiente correlacion."""
    carpeta = ROOT / "auditoria/implementacion-2026-09-29"
    carpeta.mkdir(parents=True, exist_ok=True)
    archivos = [ROOT / "DICCIONARIO_DATOS_RECETA.md", ROOT / modulo.__file__,
                ROOT / f"tests/test_ajuste_c{numero}.py", ROOT / "auditoria/2026-09-21/casos.json"]
    hashes = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in archivos}
    reproducciones = []
    for numero_caso, caso in cases(numero).items():
        req = request(**caso["entrada"])
        activa = condicion(req)
        salida = (texto(req) if callable(texto) else texto) if activa else None
        reproducciones.append({**caso, "esperado_activa": expectativas[numero_caso],
                               "activa": activa, "texto": salida,
                               "entrada_con_texto_danado": "\ufffd" in json.dumps(caso, ensure_ascii=False)})
    assert all(c["activa"] == c["esperado_activa"] for c in reproducciones)
    artefacto = {"correlacion": numero, "fecha": "2026-09-29", "hashes_sha256": hashes,
                "expectativas_origen": "Orden individual de AUDITORIA_CORRELACIONES.md y contrato; no snapshot de salida",
                "pruebas": pytest_resultado, "casos": reproducciones}
    (carpeta / f"{numero}-casos.json").write_text(json.dumps(artefacto, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    md = (f"# Implementacion #{numero} — 2026-09-29\n\n{resumen}\n\n"
          f"## Evidencia y veredicto\n\n{pytest_resultado}. {len(reproducciones)} casos historicos reproducidos con expectativas explicitas. "
          "Los controles adicionales del archivo de pruebas verifican negativos, faltantes, lateralidad y contexto. "
          "Implementacion verificada para estas entradas; no constituye validacion clinica universal ni certificacion del LLM.\n\n"
          "## Fuentes y limites\n\n" + "\n".join(f"- {f}" for f in fuentes) + "\n\n"
          "El payload no aporta protocolos completos, BCVA garantizada ni exploraciones no registradas. "
          "El corpus Unicode se reproduce sin reconstruccion; las rutas de sintomas/prioridad se prueban adicionalmente con controles negativos. "
          "Las identidades internas legacy requieren evaluar migracion de catalogo/consumidores por compatibilidad. "
          "Conservar comprobacion de regresion y prioridad temporal al integrar; estudiar validacion clinica prospectiva antes de atribuir exactitud.\n\n"
          "## Hashes SHA-256 al cierre\n\n" + "\n".join(f"- `{p}`: `{h}`" for p, h in hashes.items()) + "\n")
    (carpeta / f"{numero}.md").write_text(md, encoding="utf-8")


CASOS = cases(42)
EXPECTATIVAS = {n: n not in {"11", "12", "13", "14", "16", "17", "18", "19"} for n in CASOS}


@pytest.mark.parametrize("numero", CASOS)
def test_c42_historico_con_expectativa_de_orden(numero):
    req = request(**CASOS[numero]["entrada"])
    assert dominio._cond_insuficiencia_convergencia(req) == EXPECTATIVAS[numero]
    if EXPECTATIVAS[numero]:
        texto = dominio._texto_insuficiencia_convergencia(req)
        assert f"PPC de {req.clinica.ppc_cm} cm" in texto
        assert "exoforia en OD" in texto
        assert not any(p in texto.lower() for p in ("sospecha de insuficiencia", "terapia visual", "alejado", "anormal"))


@pytest.mark.parametrize("edad,ppc", [(20, 5), (40, 6), (None, 10), (0, 1)])
def test_c42_no_traslada_umbral_citt_ni_presbicia(edad, ppc):
    req = request(edad=edad, ppc=ppc, cover="OD: Orto | OI: Exo y Foria", motivo="Fatiga al leer")
    assert dominio._cond_insuficiencia_convergencia(req)
    assert "exoforia en OI" in dominio._texto_insuficiencia_convergencia(req)


@pytest.mark.parametrize("motivo", ["Fatiga muscular al correr", "Cefalea al despertar, lectura comoda",
                                    "Antecedente de fatiga al leer ya resuelta", "Sin fatiga al leer ni diplopia"])
def test_c42_no_inventa_sintomas_de_cerca(motivo):
    assert not dominio._cond_insuficiencia_convergencia(request(ppc=6, cover="OD: Exo y Foria", motivo=motivo))


def test_c42_mixto_y_protocolo_se_conservan_sin_diagnostico():
    req = request(ppc=6, cover="OD: Exo y Foria | OI: Endo y Tropia",
                  motivo="Fatiga al leer. PPC en recuperacion, rotura 3 cm")
    texto = dominio._texto_insuficiencia_convergencia(req)
    assert "exoforia en OD" in texto and "endotropia en OI" in texto and "protocolo" in texto
