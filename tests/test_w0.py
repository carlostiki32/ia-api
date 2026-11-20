"""W0: negacion coordinada por dominio y presupuesto HTTP, sin proveedor real."""
import asyncio
from types import SimpleNamespace

import httpx
import pytest

from app.correlaciones.pupilas_motilidad import _ocurrencias_oculares
from app.correlaciones.texto import (
    _contains_keyword, _extract_normalized_findings, _is_match_negated, _normalize_text,
)
from app.correlaciones.binocularidad import _sintomas_visuales_actuales
from app.schemas import ImpresionClinicaRequest
from tests.test_auditoria_correlaciones import _req, activas


REPRODUCCIONES = [
    {"motivo": "Niega p\u00e9rdida visual s\u00fabita, destellos nuevos y una sombra sobre la visi\u00f3n."},
    {"motivo": "Niega dolor, destellos y moscas volantes."},
    {"pupilas": "Sin ptosis, miosis y anisocoria."},
    {"motivo": "Niega visi\u00f3n borrosa, cansancio visual y ardor ocular.", "pantallas": "gt6",
     "cover": "OD: Exo y Foria | OI: Exo y Foria", "ppc": 12},
]


@pytest.mark.parametrize("entrada", REPRODUCCIONES)
def test_w0_reproducciones_sin_correlaciones_falsas(entrada):
    resultado = activas(**entrada)
    assert not set(resultado) & {
        "sintomas_alarma_traccion_vitreoretina", "pupilas_alteradas", "horner_o_tercer_par_sospecha",
        "cvs_sospecha", "insuficiencia_convergencia", "cover_exoforia_sintomatica",
    }
    if "motivo" in entrada:
        assert not _sintomas_visuales_actuales(_req(**entrada), binocular=False)


# Cada dominio pasa por su consumidor real, ademas del matcher compartido.
DOMINIOS = [
    ("pupilas", "miosis, midriasis y anisocoria", "pupilas_alteradas"),
    ("anexos", "pterigion, blefaritis y catarata", "anexos_patologicos"),
    ("anexos", "catarata, opacidad nuclear y opacidad cortical", "opacidad_cristaliniana"),
    ("anexos", "huso de Krukenberg, pseudoexfoliacion y rubeosis", "anexos_riesgo_glaucoma_secundario"),
    ("motilidad", "limitacion, nistagmo y paresia", "motilidad_alterada"),
    ("campos", "defecto temporal, escotoma y hemianopsia", "campos_visuales_alterados"),
    ("amsler", "distorsion, micropsia y escotoma", "amsler_alterado"),
    ("cover", "exoforia, endotropia y hipertropia", "endotropia_lente"),
    ("fondo", "hemorragias, desgarro en herradura y desprendimiento de retina", "fondo_periferico_riesgo"),
    ("motivo", "dolor, destellos y moscas volantes", "sintomas_alarma_traccion_vitreoretina"),
]


@pytest.mark.parametrize("campo,lista,nombre", DOMINIOS)
@pytest.mark.parametrize("prefijo", ["Niega", "Sin", "No se observan", "Mi madre presenta", "Si presentara"])
def test_w0_dominios_listas_negadas_familiares_e_hipoteticas(campo, lista, nombre, prefijo):
    resultado = activas(**{campo: f"{prefijo} {lista}."})
    assert nombre not in resultado
    assert not any(t.startswith("Hallazgo urgente:") for t in resultado.values())


@pytest.mark.parametrize("corte", ["pero", "aunque", "sin embargo", "no obstante", ", refiere",
                                      ", reporta", ", presenta", ", nota", ", percibe"])
def test_w0_reporte_positivo_corta_negacion(corte):
    motivo = f"Niega dolor {corte} destellos nuevos en OI."
    texto = activas(motivo=motivo)["sintomas_alarma_traccion_vitreoretina"]
    assert texto.startswith("Hallazgo urgente:")
    assert "48 horas" in texto


@pytest.mark.parametrize("campo,negado,positivo,nombre", [
    ("pupilas", "miosis", "anisocoria", "pupilas_alteradas"),
    ("anexos", "blefaritis", "catarata", "opacidad_cristaliniana"),
    ("motilidad", "nistagmo", "paresia", "motilidad_alterada"),
    ("campos", "escotoma", "hemianopsia", "campos_visuales_alterados"),
    ("amsler", "micropsia", "metamorfopsia", "amsler_alterado"),
    ("cover", "exoforia", "endotropia", "endotropia_lente"),
])
def test_w0_dominios_mixtos_conservan_positivo(campo, negado, positivo, nombre):
    assert nombre in activas(**{campo: f"Niega {negado} en OD, pero presenta {positivo} en OI."})


@pytest.mark.parametrize("union", [" y ", " e ", ", y ", ", e "])
def test_w0_helpers_comparten_alcance_de_lista(union):
    texto = "Niega dolor" + union + "destellos" + union + "moscas volantes."
    mapa = {"dolor": "dolor", "destellos": "fotopsias", "moscas volantes": "miodesopsias"}
    assert not _contains_keyword(texto, tuple(mapa), allow_negation_window=True)
    assert not _extract_normalized_findings(texto, mapa, allow_negation_window=True)


@pytest.mark.parametrize("texto", [
    "Niega dolor con movimientos oculares.",
    "Niega dolor con los movimientos oculares y diplopia.",
    "No refiere dolor con movimientos oculares, diplopia y fotopsias.",
])
def test_w0_con_dentro_del_propio_match_no_corta(texto):
    # Solo el span completo del sintoma incluye con. Otro hallazgo posterior
    # mantiene el comportamiento certificado: con previo rompe la negacion.
    norm = _normalize_text(texto)
    inicio = norm.index("dolor")
    fin = norm.index("oculares") + len("oculares")
    assert _is_match_negated(norm, inicio, fin)
    if "diplopia" in norm:
        inicio = norm.index("diplopia")
        assert not _is_match_negated(norm, inicio, inicio + len("diplopia"))


@pytest.mark.parametrize("dominio", ["reflejos_pupilares", "anexos_oculares", "motilidad_ocular",
                                       "confrontacion_campos_visuales", "grid_de_amsler", "motivo_consulta"])
@pytest.mark.parametrize("negado,positivo", [("destellos", "destellos"), ("miosis", "anisocoria")])
def test_w0_ocurrencias_conservan_offsets_sujeto_y_lateralidad(dominio, negado, positivo):
    texto = f"Niega {negado} en OD, refiere {positivo} en OI."
    norm = _normalize_text(texto)
    hallazgos = _ocurrencias_oculares(texto, {negado: negado, positivo: positivo}, dominio)
    assert [(h.afirmado, h.ojo) for h in hallazgos] == [(False, "OD"), (True, "OI")]
    assert [norm[h.inicio:h.fin] for h in hallazgos] == [negado, positivo]


@pytest.mark.parametrize("texto", [
    "Mi madre presenta miosis, anisocoria y ptosis en OD.",
    "Si presentara miosis, anisocoria y ptosis en OD.",
])
def test_w0_ocurrencias_no_pierden_sujeto_ni_modalidad(texto):
    hallazgos = _ocurrencias_oculares(texto, {k: k for k in ("miosis", "anisocoria", "ptosis")}, "reflejos_pupilares")
    assert len(hallazgos) == 3
    assert not any(h.afirmado for h in hallazgos)



@pytest.mark.parametrize("texto", [
    "Niega miosis OD, ni anisocoria OI.",
    "Niega miosis OD ni anisocoria OI.",
])
def test_w0_lista_entre_ojos_y_negador_antes_del_encabezado(texto):
    hechos = _ocurrencias_oculares(texto, {k: k for k in ("miosis", "anisocoria", "ptosis")}, "reflejos_pupilares")
    assert hechos and not any(h.afirmado for h in hechos)


@pytest.mark.parametrize("fondo", [
    "Sin estrechamiento arteriolar, hemorragias en llama y edema de papila AO.",
])
def test_w0_fragmentadores_fondo_no_pierden_negador(fondo):
    assert not activas(fondo=fondo)



def test_w0_fragmentacion_fondo_conserva_nuevo_encabezado_positivo():
    resultado = activas(fondo="Sin edema de papila OD, OI: drusas blandas maculares.")
    assert "papila_patologica" not in resultado
    assert "fondo_macular_dmae" in resultado


@pytest.mark.parametrize("corte", [", refiere", ", reporta", ", presenta", ", se observa", ", aunque", ", sin embargo"])
def test_w0_fragmentacion_fondo_conserva_reporte_positivo(corte):
    resultado = activas(fondo=f"Sin hemorragias {corte} drusas blandas maculares.")
    assert "fondo_macular_dmae" in resultado
    assert "sin  refiere" not in resultado["fondo_macular_dmae"]



@pytest.mark.parametrize("verbo", ["refiere", "reporta", "presenta", "nota", "percibe"])
def test_w0_reporte_negado_no_abre_una_afirmacion(verbo):
    assert not activas(motivo=f"No {verbo} dolor, destellos nuevos y moscas volantes.")


@pytest.mark.parametrize("version", ["clinica-v1", "clinica-paciente-v1"])
@pytest.mark.parametrize("ruta", ["/inferencia/impresion-clinica", "/v1/inferencia/receta-clinica"])
@pytest.mark.parametrize("urgente", [False, True])
def test_w0_presupuesto_real_responde_http_413(monkeypatch, version, ruta, urgente):
    import app.main as main
    from app.cache import inference_cache
    from app.config import settings
    from app.gpu_scheduler import GPUScheduler
    from app.tareas import presupuesto as p

    monkeypatch.setattr(settings, "api_key", "w0-secret")
    monkeypatch.setattr(main, "gpu_scheduler", GPUScheduler())
    monkeypatch.setattr(p.contador, "tokenizador", SimpleNamespace(
        encode=lambda texto: SimpleNamespace(ids=[0] * (p.limite_contexto() + 1))))
    monkeypatch.setattr(p.contador, "identidad", ("v", "d", "h", settings.ollama_num_ctx, settings.ollama_model))
    async def actualizar(client):
        pass
    monkeypatch.setattr(p.contador, "actualizar", actualizar)
    payload = _req(motivo="Destellos nuevos desde ayer" if urgente else "Revision").model_dump(mode="json")
    payload["salida_version"] = version
    envios = []
    def transporte(req):
        envios.append(req)
        raise AssertionError("Un presupuesto excedido no debe llegar al proveedor")
    async def run():
        async with httpx.AsyncClient(transport=httpx.MockTransport(transporte)) as proveedor:
            main.app.dependency_overrides[main.get_http_client] = lambda: proveedor
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=main.app), base_url="http://api") as cliente:
                return await cliente.post(ruta, json=payload, headers={"Authorization": "Bearer w0-secret"})
    inference_cache.clear()
    try:
        respuesta = asyncio.run(run())
        assert respuesta.status_code == 413, respuesta.text
        assert "presupuesto de contexto" in respuesta.json()["detail"]
        assert "context_overflow:" not in respuesta.text
        assert not envios
        assert inference_cache.get(ImpresionClinicaRequest.model_validate(payload)) is None
    finally:
        main.app.dependency_overrides.pop(main.get_http_client, None)
        inference_cache.clear()


# Corpus integro de la sonda de Claude (30 casos, orden original).
SONDA_CORPUS = [
    # Afirmaciones urgentes tras una negación no relacionada (deben detectarse)
    ("motivo_consulta", "Sin antecedentes de importancia, acude por destellos desde ayer.", "si"),
    ("motivo_consulta", "Sin antecedentes de importancia, destellos desde ayer.", "si"),
    ("motivo_consulta", "Sin antecedentes, consulta por cortina en la visión del OD desde hace dos días.", "si"),
    ("motivo_consulta", "Niega antecedentes oculares, desde ayer ve destellos y una sombra en OI.", "si"),
    ("motivo_consulta", "Sin dolor, pérdida visual súbita en OD desde hoy.", "si"),
    ("motivo_consulta", "Sin dolor, destellos desde ayer.", "si"),
    ("motivo_consulta", "Niega dolor, destellos desde ayer.", "si"),
    ("motivo_consulta", "Niega traumatismos, refiere visión doble de inicio súbito.", "si"),
    ("motivo_consulta", "Sin cirugías previas. Destellos y moscas volantes nuevas en OD.", "si"),
    ("motivo_consulta", "Sin uso de lentes previos, presenta pérdida súbita de visión en OI.", "si"),
    ("motivo_consulta", "Niega dolor, sin embargo refiere destellos en OD.", "si"),
    ("motivo_consulta", "Niega dolor\nDestellos en OD desde ayer.", "si"),
    ("motivo_consulta", "Niega dolor | destellos en OD desde ayer.", "si"),
    ("fondo_de_ojo", "Sin alteraciones en OI. OD: desgarro en retina periférica.", "si"),
    ("fondo_de_ojo", "Sin alteraciones OD: desgarro en retina periférica.", "si"),
    ("fondo_de_ojo", "OI sin alteraciones, OD con desgarro en retina periférica.", "si"),
    ("fondo_de_ojo", "Sin hemorragias, con desgarro en retina periférica de OD.", "si"),
    ("fondo_de_ojo", "Retinopatía diabética no proliferativa, hemorragias en llama y edema macular.", "si"),
    ("reflejos_pupilares", "Sin alteraciones en OD; OI con defecto pupilar aferente relativo.", "si"),
    # Enumeraciones negadas (no deben activar)
    ("motivo_consulta", "Niega pérdida visual súbita, destellos nuevos y una sombra sobre la visión.", "no"),
    ("motivo_consulta", "Niega dolor, destellos y moscas volantes.", "no"),
    ("motivo_consulta", "Niega visión borrosa, cansancio visual y ardor ocular.", "no"),
    ("motivo_consulta", "Niega destellos, moscas volantes ni sombras.", "no"),
    ("motivo_consulta", "Sin destellos, moscas ni cortina en la visión.", "no"),
    ("reflejos_pupilares", "Sin ptosis, miosis y anisocoria.", "no"),
    ("fondo_de_ojo", "Sin hemorragias, exudados ni desgarros.", "no"),
    ("fondo_de_ojo", "Sin desgarros, agujeros o desprendimiento en ambos ojos.", "no"),
    # Ambiguos (se registran, no se califican)
    ("motivo_consulta", "Niega cefalea, diplopia.", "?"),
    ("fondo_de_ojo", "Sin desprendimiento con desgarro en periferia.", "?"),
    ("motivo_consulta", "Niega dolor con los movimientos oculares.", "?"),
]

# Ambiguos: deteccion conservadora cuando hay hallazgo soportado; no se
# inventa urgencia para dolor negado dentro del propio sintoma coincidente.
SONDA_AMBIGUOS = {
    28: (False, "Diplopia sin cronologia no activa diplopia aguda; la coma si corta la negacion."),
    29: (True, "Con anterior a desgarro conserva la deteccion certificada."),
    30: (False, "Dolor con los movimientos oculares esta negado dentro del mismo match."),
}


@pytest.mark.parametrize("indice,campo,texto,esperado", [
    (i, *caso) for i, caso in enumerate(SONDA_CORPUS, 1)
])
def test_w0_fix_sonda_completa(indice, campo, texto, esperado):
    from app.correlaciones.registry import evaluar_correlaciones_con_nombres
    data = {"receta_id": "r-1", "salida_version": "clinica-paciente-v1",
            "refraccion": {ojo: {"esfera": -1.0, "cilindro": 0.0} for ojo in ("od", "oi")}}
    data["paciente" if campo == "motivo_consulta" else "clinica"] = {campo: texto}
    resultado = dict(evaluar_correlaciones_con_nombres(ImpresionClinicaRequest.model_validate(data)))
    debe = SONDA_AMBIGUOS[indice][0] if esperado == "?" else esperado == "si"
    assert bool(resultado) == debe, (indice, texto, resultado)
    if indice in (1, 2, 3, 4, 5, 6, 7, 12):
        assert "sintomas_alarma_traccion_vitreoretina" in resultado
    if indice == 15:
        assert "fondo_periferico_riesgo" in resultado


# 42 frases urgentes adicionales, con consumidores reales en siete campos.
URGENTES_FIX = [
    ("motivo", "destellos nuevos en {ojo} desde ayer", "sintomas_alarma_traccion_vitreoretina", {}),
    ("fondo", "desgarro en retina periférica {ojo}", "fondo_periferico_riesgo", {}),
    ("pupilas", "anisocoria de inicio súbito en {ojo}", "pupilas_alteradas", {}),
    ("motilidad", "oftalmoplejia de inicio reciente en {ojo}", "motilidad_alterada", {"motivo": "Diplopia desde hoy"}),
    ("campos", "hemianopsia de inicio súbito", "campos_visuales_alterados", {}),
    ("anexos", "leucocoria {ojo}", "opacidad_cristaliniana", {}),
    ("cover", "endotropia {ojo}", "endotropia_lente", {"motivo": "Diplopia desde hoy"}),
]
ENTRADAS_FIX = [
    "Sin antecedentes de importancia, {hallazgo}.",
    "Niega dolor, desde ayer presenta {hallazgo}.",
    "No presenta irritación, acude por {hallazgo}.",
    "Sin cefalea ni traumatismos, consulta por {hallazgo}.",
    "Niega alergias o cirugías, actualmente observa {hallazgo}.",
    "SIN ANTECEDENTES, AHORA {hallazgo}.",
]


@pytest.mark.parametrize("campo,hallazgo,nombre,extra", URGENTES_FIX)
@pytest.mark.parametrize("variante,plantilla", list(enumerate(ENTRADAS_FIX)))
def test_w0_fix_42_urgencias_tras_negacion_ajena(campo, hallazgo, nombre, extra, variante, plantilla):
    hallazgo = hallazgo.format(ojo=("OD", "OI", "AO")[variante % 3])
    texto = plantilla.format(hallazgo=hallazgo.upper() if variante == 5 else hallazgo)
    resultado = activas(**{**extra, campo: texto})
    assert resultado[nombre].startswith("Hallazgo urgente:"), (texto, resultado)


LISTAS_FIX = [
    ("motivo", "pérdida visual súbita", "destellos", "moscas volantes"),
    ("fondo", "hemorragias", "desgarros", "desprendimiento de retina"),
    ("pupilas", "ptosis", "miosis", "anisocoria"),
    ("motilidad", "limitación", "nistagmo", "paresia"),
    ("campos", "defecto temporal", "escotoma", "hemianopsia"),
    ("anexos", "pterigión", "blefaritis", "catarata"),
    ("cover", "exoforia", "endotropia", "hipertropia"),
]


@pytest.mark.parametrize("campo,a,b,c", LISTAS_FIX)
@pytest.mark.parametrize("negador,coordinador", [
    ("Sin", "ni"), ("Niega", "o"), ("No se observan", "u"),
    ("No refiere", "y"), ("Ausencia de", "e"), ("SIN EVIDENCIA DE", "NI"),
])
def test_w0_fix_42_enumeraciones_negadas_cerradas(campo, a, b, c, negador, coordinador):
    texto = f"{negador} {a}, {b} {coordinador} {c}."
    assert not activas(**{campo: texto}), texto


@pytest.mark.parametrize("senal", [
    "acude por", "consulta por", "viene por", "presenta", "refiere", "reporta", "manifiesta",
    "comenta", "describe", "nota", "percibe", "siente", "ve", "observa", "aqueja", "tiene",
    "padece", "sufre", "inicia", "inició", "comenzó", "empezó", "desde ayer",
    "hace dos días", "hoy", "ayer", "anoche", "actualmente", "ahora", "recientemente",
    "de repente", "súbitamente", "posteriormente", "luego", "después",
])
@pytest.mark.parametrize("coordinador", ["ni", "o", "u", "y", "e"])
def test_w0_fix_senal_nueva_clausula_gana_a_coordinador_posterior(senal, coordinador):
    texto = f"Sin dolor, {senal} destellos {coordinador} moscas volantes nuevas en OD desde ayer."
    assert "sintomas_alarma_traccion_vitreoretina" in activas(motivo=texto), texto


@pytest.mark.parametrize("salto", ["\n", "\r\n", "\r"])
@pytest.mark.parametrize("campo,hallazgo,nombre,extra", URGENTES_FIX)
def test_w0_fix_lineas_cortan_alcance_en_payload_y_consumidor(salto, campo, hallazgo, nombre, extra):
    texto = "Niega dolor" + salto + hallazgo.format(ojo="OD") + "."
    req = _req(**{**extra, campo: texto})
    valor = req.paciente.motivo_consulta if campo == "motivo" else getattr(req.clinica, {
        "fondo": "fondo_de_ojo", "pupilas": "reflejos_pupilares", "motilidad": "motilidad_ocular",
        "campos": "confrontacion_campos_visuales", "anexos": "anexos_oculares", "cover": "cover_test",
    }[campo])
    assert "\n" in valor and "\n" in _normalize_text(valor)
    assert activas(**{**extra, campo: texto})[nombre].startswith("Hallazgo urgente:")


@pytest.mark.parametrize("ojo", ["OD", "OI", "AO"])
def test_w0_fix_encabezado_corta_incluso_sin_punto(ojo):
    assert "fondo_periferico_riesgo" in activas(fondo=f"Sin alteraciones {ojo}: desgarro en retina periférica.")


@pytest.mark.parametrize("texto", [
    "Sin evidencia en OD ni en OI, de desgarro periférico.",
    "Sin evidencia en OD, ni en OI, de desgarro periférico.",
])
def test_w0_fix_conserva_excepcion_ni_de(texto):
    assert not activas(fondo=texto)


@pytest.mark.parametrize("senal", ["ve", "desde ayer", "acude por", "siente", "inició", "luego"])
def test_w0_fix_clausula_nueva_no_se_pierde_tras_otra_coma(senal):
    texto = f"Sin dolor, {senal} manchas, destellos y moscas volantes nuevas en OI desde ayer."
    assert "sintomas_alarma_traccion_vitreoretina" in activas(motivo=texto)


def test_w0_fix_sufijo_normal_de_otro_signo_no_borra_el_primero():
    hechos = _ocurrencias_oculares("Sin dolor, ptosis anisocoria normal",
                                  {"ptosis": "ptosis", "anisocoria": "anisocoria"}, "reflejos_pupilares")
    assert [(h.hallazgo, h.afirmado) for h in hechos] == [("ptosis", True), ("anisocoria", False)]


@pytest.mark.parametrize("senal", ["desde ayer", "acude por", "luego", "de repente", "súbitamente", "consulta por"])
def test_w0_fix_fragmentos_no_reintroducen_negacion_antes_de_nueva_clausula(senal):
    texto = f"Sin hemorragias, {senal} drusas blandas y edema macular."
    assert "fondo_macular_dmae" in activas(fondo=texto)


@pytest.mark.parametrize("continuacion", ["y consulta hoy", "e inicia otra consulta", "o viene hoy", "u observa otra cosa", "y se observa hoy"])
def test_w0_fix_coordinador_de_otra_clausula_no_cierra_lista_negada(continuacion):
    texto = f"Niega dolor, destellos desde ayer {continuacion}."
    assert "sintomas_alarma_traccion_vitreoretina" in activas(motivo=texto)


# Corpus integro de sonda_negacion2.py, en su orden original.
SONDA2_CORPUS = [
    ("motivo_consulta", "No usa lentes, desde anoche nota destellos en el ojo izquierdo.", "si"),
    ("motivo_consulta", "Sin antecedentes familiares de glaucoma, refiere sombra en la visión de OD.", "si"),
    ("motivo_consulta", "Niega diabetes e hipertensión, acude por pérdida brusca de visión en OI.", "si"),
    ("motivo_consulta", "Sin molestias previas; hoy amaneció viendo doble.", "si"),
    ("motivo_consulta", "Niega alergias, ve moscas volantes nuevas y destellos desde hace tres días.", "si"),
    ("motivo_consulta", "Sin traumatismo ocular, presenta cortina en la parte superior de la visión.", "si"),
    ("motivo_consulta", "No refiere dolor, pero ve destellos al mover los ojos.", "si"),
    ("motivo_consulta", "Sin cirugías, súbitamente perdió la visión del OD hace 2 horas.", "si"),
    ("motivo_consulta", "Niega uso de medicamentos. Visión doble desde esta mañana.", "si"),
    ("motivo_consulta", "Sin lentes previos, comenzó con destellos ayer.", "si"),
    ("motivo_consulta", "SIN ANTECEDENTES, DESTELLOS Y SOMBRA EN OD DESDE AYER.", "si"),
    ("motivo_consulta", "Niega dolor\r\nVe destellos en OI desde ayer", "si"),
    ("motivo_consulta", "Niega destellos, sombras, cortinas ni pérdida de visión.", "no"),
    ("motivo_consulta", "Sin visión doble, destellos o moscas volantes.", "no"),
    ("motivo_consulta", "No refiere destellos, moscas volantes y sombras.", "no"),
    ("motivo_consulta", "Niega pérdida súbita de la visión y destellos.", "no"),
    ("motivo_consulta", "Niega diplopia, cefalea y dolor ocular.", "no"),
    ("fondo_de_ojo", "OD sin desgarros; OI: desgarro en herradura en periferia temporal.", "si"),
    ("fondo_de_ojo", "Sin desgarros, agujeros ni desprendimientos en OD y OI.", "no"),
    ("fondo_de_ojo", "Periferia sin lesiones, mácula con hemorragias en OD.", "?"),
]


@pytest.mark.parametrize("indice,campo,texto,esperado", [
    pytest.param(i, *caso)
    for i, caso in enumerate(SONDA2_CORPUS, 1)
])
def test_w0_fix2_sonda_completa(indice, campo, texto, esperado):
    from app.correlaciones.registry import evaluar_correlaciones_con_nombres
    # VOCAB: 2, 4 y 8 verifican las formas coloquiales antes ausentes.
    data = {"receta_id": "r-1", "salida_version": "clinica-paciente-v1",
            "refraccion": {ojo: {"esfera": -1.0, "cilindro": 0.0} for ojo in ("od", "oi")}}
    data["paciente" if campo == "motivo_consulta" else "clinica"] = {campo: texto}
    resultado = dict(evaluar_correlaciones_con_nombres(ImpresionClinicaRequest.model_validate(data)))
    # Caso 20 ambiguo: conserva hemorragias afirmadas, pero el dato aislado
    # no satisface una correlacion. No se inventan hallazgos para activarla.
    if esperado == "?":
        assert _contains_keyword(texto, ("hemorragias",), allow_negation_window=True)
        assert not resultado
    else:
        assert bool(resultado) == (esperado == "si"), (indice, texto, resultado)


@pytest.mark.parametrize("tiempo", [
    "desde ayer", "hace 2 horas", "hace tres dias", "hace poco", "hoy", "ayer", "anoche",
    "esta mañana", "esta tarde", "esta noche", "de inicio", "inició", "comenzó", "empezó",
    "actualmente", "ahora",
])
@pytest.mark.parametrize("posicion", ["{t} destellos y sombra", "destellos {t} y sombra", "destellos y sombra {t}"])
def test_w0_fix2_tiempo_corta_en_toda_la_clausula(tiempo, posicion):
    texto = "Sin dolor, " + posicion.format(t=tiempo) + " en OD."
    assert _contains_keyword(texto, ("destellos",), allow_negation_window=True)


@pytest.mark.parametrize("nucleo", [
    "antecedentes", "cirugías", "traumatismos", "alergias", "enfermedades", "padecimientos",
    "medicamentos", "tratamientos", "uso de lentes", "lentes previos", "traumatismo ocular",
    "antecedentes ni dolor",
])
def test_w0_fix2_antecedentes_cortan_sin_tiempo(nucleo):
    texto = f"Sin {nucleo}, destellos y moscas volantes en OD."
    assert "sintomas_alarma_traccion_vitreoretina" in activas(motivo=texto)


@pytest.mark.parametrize("calificador", ["súbita", "nuevos", "reciente", "brusca", "hace falta"])
def test_w0_fix2_calificador_solo_no_corta(calificador):
    texto = f"Niega pérdida visual súbita, destellos {calificador} y una sombra sobre la visión."
    assert not activas(motivo=texto)


def test_w0_fix2_tiempo_de_otra_clausula_no_corta():
    assert not activas(motivo="Niega pérdida visual súbita, destellos y moscas volantes. Control hoy.")


@pytest.mark.parametrize("salto", ["\n", "\r\n", "\r", "\n\n", "\t\n  "])
def test_w0_fix2_prompt_aplana_textos_y_conserva_lineas(salto):
    from app.prompt_builder import build_user_prompt
    data = {"receta_id": "w0-prompt", "refraccion": {"od": {"esfera": -1.0}},
            "paciente": {"motivo_consulta": f"Revision{salto}de lentes"},
            "clinica": {campo: f"Registro{salto}clinico" for campo in (
                "fondo_de_ojo", "anexos_oculares", "reflejos_pupilares", "confrontacion_campos_visuales",
                "grid_de_amsler", "recomendacion_seguimiento", "motilidad_ocular", "cover_test")}}
    req = ImpresionClinicaRequest.model_validate(data)
    plano = {**data, "paciente": {"motivo_consulta": "Revision de lentes"},
             "clinica": {campo: "Registro clinico" for campo in data["clinica"]}}
    assert "\n" in req.paciente.motivo_consulta
    assert all("\n" in getattr(req.clinica, campo) for campo in data["clinica"])
    assert build_user_prompt(req).encode("utf-8") == build_user_prompt(
        ImpresionClinicaRequest.model_validate(plano)).encode("utf-8")


def test_w0_fix2_prompt_aplana_correlacion_sin_aplanar_request(monkeypatch):
    from app import prompt_builder
    req = _req(motivo="Niega dolor\nDestellos en OI desde ayer")
    def correlaciones(original):
        assert original is req and "\n" in original.paciente.motivo_consulta
        return ["Hallazgo\r\n  clinico\tcon\nseguimiento."]
    monkeypatch.setattr(prompt_builder, "evaluar_correlaciones", correlaciones)
    prompt = prompt_builder.build_user_prompt(req)
    assert "Motivo de consulta: Niega dolor Destellos en OI desde ayer" in prompt
    assert "- Hallazgo clinico con seguimiento." in prompt
