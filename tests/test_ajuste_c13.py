"""Aceptacion #13 `pupilas_alteradas`: tipo pupilar, cronologia, certeza y hechos cubiertos.

Las expectativas de C13-01..35 se escriben caso por caso a partir de la columna
"Esperado" de la orden (AUDITORIA_CORRELACIONES.md, #13), no del comportamiento
del codigo. Las regresiones posteriores cubren los fallos hallados al certificar.
"""
import json
from pathlib import Path

import pytest

from app.correlaciones.pupilas_motilidad import _extract_finding_eye, _hay_dpar
from app.inference import _ensure_emergency_preserved
from app.schemas import ImpresionClinicaRequest
from tests.test_auditoria_correlaciones import _req, activas, alertas_h01

N = "Reflejo fotomotor, consensual, acomodativo"
_CASOS = {c["id"]: c for c in json.loads(
    (Path(__file__).parents[1] / "auditoria/2026-09-21/casos.json").read_text(encoding="utf-8"))
    if c["id"].startswith("C13-")}

# id -> (fragmentos que deben aparecer, fragmentos que no deben aparecer, urgente, H01)
# Un id ausente de ACTIVAS exige que #13 NO dispare.
_SIN_SALIDA = ("01", "03", "04", "13", "15", "16", "18", "19", "21", "23", "24", "25", "26", "28", "30", "34")
_PROHIBIDO = ("indicativa de patologia", "neurooftalmologica", "confirma", "diagnostico de")
ACTIVAS = {
    "02": (("defecto pupilar aferente relativo; amerita valoracion oftalmologica de retina y via visual aferente",),
           (" OD", " OI"), False, False),                     # chip: dato sin lado ni causa inferidos
    "05": (("defecto pupilar aferente relativo OD",), (" OI",), False, False),
    "06": (("defecto pupilar aferente relativo OD",), (" OI",), False, False),
    "07": (("defecto pupilar aferente relativo OD de evolucion antigua descrita",),
           ("inicio reciente", "Verificar inicio"), False, False),
    "08": (("defecto pupilar aferente relativo OD de inicio reciente", "el mismo dia", "perdida visual referida"),
           ("antigua",), True, True),
    "09": (("pupila no reactiva OD",), ("aferente",), False, False),
    "10": (("pupila no reactiva OD",), ("aferente",), False, False),
    "11": (("respuesta fotomotora ausente OD",), ("aferente", "no reactiva"), False, False),
    "12": (("respuesta fotomotora ausente OD",), ("aferente", "no reactiva"), False, False),
    "14": (("pupila no reactiva OI",), ("OD",), False, False),
    "17": (("midriasis OD",), ("farmacologic",), False, False),
    "20": (("anisocoria OD",), ("fisiologic",), False, False),
    "22": (("respuesta pupilar irregular", "verificar la prueba"), ("pupila irregular",), False, False),
    "27": (("anisocoria OD de inicio reciente", "el mismo dia", "cefalea referida", "diplopia referida"),
           (), True, True),
    "29": (("resultado no concluyente para defecto pupilar aferente relativo OD", "verificar la prueba"),
           ("Hallazgo urgente",), False, False),
    "31": (("midriasis OI de inicio reciente", "el mismo dia", "dolor ocular referido"),
           ("OD", "defecto pupilar"), True, True),
    "32": (("defecto pupilar aferente relativo OD",), ("OI",), False, False),
    "33": (("respuesta consensual ausente OI",), ("aferente", "OD"), False, False),
    "35": (("respuesta fotomotora ausente OD",), ("aferente", "no reactiva"), False, False),
}


@pytest.mark.parametrize("numero", sorted(set(_SIN_SALIDA) | set(ACTIVAS)))
def test_c13_caso_auditoria(numero):
    caso = _CASOS[f"C13-{numero}"]
    resultado = activas(**caso["entrada"])
    if numero in _SIN_SALIDA:
        assert "pupilas_alteradas" not in resultado
        assert "pupilas_alteradas" not in alertas_h01(**caso["entrada"])
        return
    pide, no_pide, urgente, h01 = ACTIVAS[numero]
    texto = resultado["pupilas_alteradas"]
    for fragmento in pide:
        assert fragmento in texto, (fragmento, texto)
    for fragmento in no_pide + _PROHIBIDO:
        assert fragmento not in texto, (fragmento, texto)
    assert texto.startswith("Hallazgo urgente:") == urgente
    assert ("Hallazgo urgente" in texto) == urgente          # nunca a mitad de una oracion
    assert ("pupilas_alteradas" in alertas_h01(**caso["entrada"])) == h01
    if numero == "31":
        assert "glaucoma_asimetrico" in resultado            # #5 conserva su DPAR OD
        assert "glaucoma_asimetrico" not in alertas_h01(**caso["entrada"])


def test_c13_las_35_reproducciones_estan_cubiertas():
    assert len(_CASOS) == 35
    assert set(_SIN_SALIDA) | set(ACTIVAS) == {f"{i:02d}" for i in range(1, 36)}


def test_c13_normal_mas_dpar_positivo_no_son_incompatibles():
    assert "defecto pupilar aferente relativo OD" in activas(pupilas=f"{N}: DPAR positivo OD")["pupilas_alteradas"]


# ---------------------------------------------------------------- mandibulopalpebral
@pytest.mark.parametrize("pupilas", [
    "DPAR OD. Sincinesia mandibulopalpebral OI",
    "DPAR OD, sin sincinesia mandibulopalpebral",
    "Marcus Gunn OD, sin sincinesia mandibulopalpebral",
    "Marcus Gunn mandibulopalpebral OI, DPAR OD",
])
def test_c13_dpar_no_cancelado_por_mencion_de_mandibula(pupilas):
    assert _hay_dpar(pupilas)
    assert "defecto pupilar aferente relativo OD" in activas(pupilas=pupilas)["pupilas_alteradas"]


@pytest.mark.parametrize("pupilas", [
    "Marcus Gunn con sincinesia mandibulopalpebral",
    "Marcus Gunn: ptosis con movimiento mandibular",
    "Marcus Gunn (jaw winking) OI",
    "Fenomeno de Marcus Gunn mandibulopalpebral",
])
def test_c13_fenomeno_mandibulopalpebral_no_es_dpar(pupilas):
    assert "pupilas_alteradas" not in activas(pupilas=pupilas)


# ---------------------------------------------------------------- negaciones y notacion
@pytest.mark.parametrize("pupilas", [
    "DPAR -", "DPAR (-)", "DPAR [neg]", "DPAR: no", "DPAR negativo", "DPAR ausente", "DPAR descartado",
    "Sin DPAR", "No hay DPAR", "Ni anisocoria ni DPAR", "sin anisocoria ni DPAR",
    f"{N}: no se observa anisocoria ni DPAR", f"{N}: pupilas normales, no anisocoria",
    "Marcus Gunn: negativo OD", "Sin reflejo corneal", "Reflejo corneal ausente", "Fotomotor no evaluado",
    "Irregular", "Respuesta regular por distraccion", "Pupila no irregular OD",
])
def test_c13_negados_o_sin_examen_pupilar_no_disparan(pupilas):
    assert "pupilas_alteradas" not in activas(pupilas=pupilas)


@pytest.mark.parametrize("pupilas", ["DPAR (+)", "DPAR +", "DPAR OD grado II", "RAPD OD"])
def test_c13_notacion_positiva_conserva_dpar(pupilas):
    assert "defecto pupilar aferente relativo" in activas(pupilas=pupilas)["pupilas_alteradas"]


def test_c13_negacion_de_un_signo_no_borra_el_otro():
    texto = activas(pupilas=f"{N}: sin anisocoria, con DPAR OD")["pupilas_alteradas"]
    assert "defecto pupilar aferente relativo OD" in texto and "anisocoria" not in texto
    texto = activas(pupilas=f"{N}: anisocoria fisiologica, sin otros hallazgos. DPAR OD")["pupilas_alteradas"]
    assert "defecto pupilar aferente relativo OD" in texto and "anisocoria" not in texto


def test_c13_lado_de_dpar_es_la_ocurrencia_afirmada():
    texto = "DPAR OD negativo. DPAR OI positivo"
    assert _extract_finding_eye(texto, ("dpar",)) == "OI"
    resultado = activas(pupilas=texto, fondo="C/D 0.8 OD, 0.3 OI", edad=60)
    assert "glaucoma_asimetrico" not in resultado
    assert "defecto pupilar aferente relativo OI" in resultado["pupilas_alteradas"]


# ---------------------------------------------------------------- funcion ausente
@pytest.mark.parametrize("nota,esperado", [
    ("reflejo fotomotor ausente OI", "respuesta fotomotora ausente OI"),
    ("reflejo fotomotor abolido OD", "respuesta fotomotora ausente OD"),
    ("sin reflejo fotomotor OD", "respuesta fotomotora ausente OD"),
    ("sin respuesta fotomotora OD", "respuesta fotomotora ausente OD"),
    ("no hay respuesta fotomotora OD", "respuesta fotomotora ausente OD"),
    ("no hay reflejo fotomotor OI", "respuesta fotomotora ausente OI"),
    ("ausencia de reflejo fotomotor OD", "respuesta fotomotora ausente OD"),
    ("no responde a la luz OD", "respuesta fotomotora ausente OD"),
    ("sin respuesta a la luz OI", "respuesta fotomotora ausente OI"),
    ("respuesta consensual ausente OI", "respuesta consensual ausente OI"),
    ("sin respuesta consensual OI", "respuesta consensual ausente OI"),
    ("reflejo acomodativo ausente OD", "respuesta acomodativa ausente OD"),
    ("fotomotor y consensual ausentes", "respuestas fotomotora y consensual ausentes"),
])
def test_c13_funcion_ausente_conserva_su_nombre_exacto(nota, esperado):
    texto = activas(pupilas=f"{N}: {nota}")["pupilas_alteradas"]
    assert esperado in texto and "aferente" not in texto


@pytest.mark.parametrize("nota,esperado", [
    ("Pupilas arreactivas", "pupila no reactiva bilateral"),
    ("pupilas fijas", "pupila no reactiva bilateral"),
    ("pupilas no reactivas", "pupila no reactiva bilateral"),
    ("pupilas hiporreactivas", "respuesta pupilar disminuida bilateral"),
    ("pupilas irregulares", "pupila irregular bilateral"),
    ("pupilas tonicas", "pupila tonica bilateral"),
    ("reflejos fotomotores ausentes", "respuesta fotomotora ausente bilateral"),
    ("reflejos consensuales ausentes", "respuesta consensual ausente bilateral"),
    ("reflejos pupilares ausentes", "respuesta pupilar ausente bilateral"),
    ("OD: pupila fija; OI: pupilas normales", "pupila no reactiva OD"),
])
def test_c13_plurales_se_detectan_y_son_bilaterales(nota, esperado):
    texto = activas(pupilas=f"{N}: {nota}")["pupilas_alteradas"]
    assert esperado in texto
    if nota.startswith("OD:"):
        assert "bilateral" not in texto


def test_c13_plural_no_convierte_la_anisocoria_en_bilateral():
    texto = activas(pupilas=f"{N}: anisocorias")["pupilas_alteradas"]
    assert "anisocoria" in texto and "bilateral" not in texto


@pytest.mark.parametrize("nota", [
    "pupilas isocoricas, reactivas", "pupilas iso y normorreactivas",
    "pupilas regulares, normorreactivas", "pupilas simetricas y reactivas",
])
def test_c13_plural_normal_no_dispara(nota):
    assert "pupilas_alteradas" not in activas(pupilas=f"{N}: {nota}")


def test_c13_ausencia_de_una_funcion_no_es_dpar():
    assert not _hay_dpar(f"{N}: reflejo fotomotor ausente OD")


# ---------------------------------------------------------------- certeza
@pytest.mark.parametrize("pupilas,frase", [
    ("DPAR dudoso OD, repetir", "resultado no concluyente para defecto pupilar aferente relativo OD"),
    ("posible DPAR OD", "resultado no concluyente para defecto pupilar aferente relativo OD"),
    ("sospecha de DPAR OI", "resultado no concluyente para defecto pupilar aferente relativo OI"),
    ("Descartar DPAR", "sospecha por descartar de defecto pupilar aferente relativo"),
    ("DPAR?", "sospecha por descartar de defecto pupilar aferente relativo"),
])
def test_c13_hallazgo_incierto_no_se_declara_medido(pupilas, frase):
    texto = activas(pupilas=pupilas)["pupilas_alteradas"]
    assert frase in texto and "Hallazgo urgente" not in texto
    assert ("Completar la prueba pupilar" in texto) == ("descartar" in frase)
    assert ("verificar la prueba" in texto) == ("descartar" not in frase)


def test_c13_dpar_dudoso_no_cancela_perdida_visual_aguda():
    texto = activas(pupilas="DPAR dudoso OD, repetir", motivo="Perdida visual OD desde hoy")["pupilas_alteradas"]
    assert texto.startswith("Hallazgo urgente:")
    assert "no concluyente" in texto and "el mismo dia" in texto and "verificar la prueba" in texto


def test_c13_dpar_dudoso_no_alimenta_combinacion_5_como_demostrado():
    resultado = activas(pupilas="DPAR dudoso OD", fondo="C/D 0.8 OD, 0.3 OI", edad=60)
    assert "glaucoma_asimetrico" not in resultado
    assert "no concluyente" in resultado["pupilas_alteradas"]


# ---------------------------------------------------------------- farmacos y variantes fisiologicas
@pytest.mark.parametrize("nota", [
    "midriasis OD post dilatacion", "midriasis bilateral por tropicamida",
    "midriasis OD, tropicamida instilada hace 1 hora", "pupila fija OD, tropicamida instilada",
    "arreactiva OD por atropina", "OD: midriasis farmacologica por tropicamida",
    "Midriasis OD farmacologica por tropicamida", "anisocoria fisiologica de 1 mm",
    "Anisocoria simple, sin cambios", "Miosis fisiologica bilateral con la luz",
    "Midriasis bilateral en oscuridad",
])
def test_c13_explicacion_afirmada_excluye_el_signo(nota):
    assert "pupilas_alteradas" not in activas(pupilas=f"{N}: {nota}")


@pytest.mark.parametrize("nota,frase", [
    ("OD: midriasis espontanea, sin uso de tropicamida", "midriasis OD"),
    ("arreactiva OD, sin uso de atropina", "pupila no reactiva OD"),
    ("Anisocoria no fisiologica OD", "anisocoria OD"),
])
def test_c13_explicacion_negada_no_excluye(nota, frase):
    assert frase in activas(pupilas=f"{N}: {nota}")["pupilas_alteradas"]


# ---------------------------------------------------------------- cronologia y prioridad
def test_c13_dpar_desconocido_no_inventa_fecha_ni_plazo():
    texto = activas(pupilas="Marcus Gunn")["pupilas_alteradas"]
    assert "retina y via visual aferente" in texto
    assert "inicio reciente" not in texto and "Hallazgo urgente:" not in texto
    assert "decidir la prioridad" in texto
    assert not alertas_h01(pupilas="Marcus Gunn")


def test_c13_5_activa_pero_perdida_visual_aguda_conserva_alerta_propia():
    """Orden #13 ítem 10: #5 no borra el dato agudo del mismo ojo."""
    kw = dict(pupilas="Marcus Gunn: OD", fondo="C/D 0.8 OD, 0.3 OI", edad=62)
    sin = activas(**kw)
    assert "glaucoma_asimetrico" in sin and "pupilas_alteradas" not in sin
    con = activas(**kw, motivo="Perdida visual OD desde hoy")
    assert "glaucoma_asimetrico" in con and con["pupilas_alteradas"].startswith("Hallazgo urgente:")
    assert alertas_h01(**kw, motivo="Perdida visual OD desde hoy") == {"pupilas_alteradas"}


def test_c13_dpar_nuevo_con_5_conserva_prioridad():
    resultado = activas(pupilas="DPAR OD nuevo", fondo="C/D 0.8 OD, 0.3 OI", edad=60)
    assert "glaucoma_asimetrico" in resultado
    assert resultado["pupilas_alteradas"].startswith("Hallazgo urgente:")


@pytest.mark.parametrize("motivo,urgente", [
    ("Perdida de vision OD hace 3 dias", True),
    ("Perdida de vision OD hace 2 semanas", True),
    ("Perdida visual subita OD", True),
    ("Perdida de vision OD desde hace 3 meses", False),
    ("Perdida de vision OD hace 3 anos", False),
    ("Revision de rutina, sin sintomas", False),
])
def test_c13_perdida_visual_con_dpar_de_fecha_desconocida(motivo, urgente):
    texto = activas(pupilas="Marcus Gunn OD", motivo=motivo)["pupilas_alteradas"]
    assert texto.startswith("Hallazgo urgente:") == urgente
    assert ("perdida visual referida" in texto) == urgente
    assert ("pupilas_alteradas" in alertas_h01(pupilas="Marcus Gunn OD", motivo=motivo)) == urgente


def test_c13_dpar_antiguo_no_cancela_perdida_visual_aguda():
    texto = activas(pupilas="DPAR OD conocido hace diez anos sin cambios",
                    motivo="Perdida visual OD desde hoy")["pupilas_alteradas"]
    assert texto.startswith("Hallazgo urgente:")
    assert "evolucion antigua" in texto and "el mismo dia" in texto and "perdida visual referida" in texto


def test_c13_dpar_antiguo_no_se_reactiva_por_sintoma_ajeno():
    texto = activas(pupilas="DPAR OD conocido hace diez anos sin cambios", motivo="Cefalea desde ayer")
    assert "Hallazgo urgente" not in texto["pupilas_alteradas"]


@pytest.mark.parametrize("nota,esperado", [
    ("pupila fija OD desde hace 2 dias", True),
    ("pupila fija OD desde hace 2 semanas", True),
    ("DPAR OD hoy", True),
    ("pupila fija OD desde hace 5 meses", False),
    ("pupila fija OD desde hace 5 anos", False),
    ("corectopia OI congenita, valorada hoy", False),
])
def test_c13_cronologia_relativa(nota, esperado):
    texto = activas(pupilas=f"{N}: {nota}")["pupilas_alteradas"]
    assert texto.startswith("Hallazgo urgente:") == esperado


@pytest.mark.parametrize("motivo", ["Dolor cervical", "Dolor ocular OD", "Disartria", "Debilidad de extremidades"])
def test_c13_sintoma_de_alarma_sin_fecha_no_difiere_la_valoracion(motivo):
    texto = activas(pupilas=f"{N}: anisocoria OD", motivo=motivo)["pupilas_alteradas"]
    assert texto.startswith("Hallazgo urgente:") and "el mismo dia" in texto


def test_c13_anisocoria_fisiologica_con_dolor_cervical_no_dispara():
    assert "pupilas_alteradas" not in activas(pupilas=f"{N}: anisocoria fisiologica", motivo="Dolor cervical")


# ---------------------------------------------------------------- deduplicacion / integracion
def test_c13_chip_y_expansion_no_duplican_dpar():
    texto = activas(pupilas="Marcus Gunn: DPAR OD")["pupilas_alteradas"]
    assert texto.count("defecto pupilar aferente relativo") == 1 and "OD" in texto


def test_c13_forma_irregular_con_sustantivo_anatomico():
    assert "pupila irregular OD" in activas(pupilas="Contorno pupilar irregular OD")["pupilas_alteradas"]


def test_c13_adie_no_duplica_nombre():
    assert activas(pupilas="Pupila tonica de Adie OD")["pupilas_alteradas"].count("pupila tonica") == 1


def test_c13_dpar_y_otro_signo_de_otro_ojo_se_conservan_juntos():
    texto = activas(pupilas=f"{N}: DPAR OD y anisocoria OI")["pupilas_alteradas"]
    assert "defecto pupilar aferente relativo OD" in texto and "anisocoria OI" in texto


# ---------------------------------------------------------------- H01
def _payload(**campos):
    return _req(**campos)


def test_c13_h01_purga_normalidad_y_control_anual_ante_signo_agudo():
    req = _payload(pupilas=f"{N}: anisocoria OD", motivo="Dolor cervical y cefalea desde ayer")
    salida = _ensure_emergency_preserved("Pupilas normales. Se recomienda control anual.", req)
    assert "normales" not in salida and "control anual" not in salida.lower()
    assert "anisocoria OD" in salida and "el mismo dia" in salida


def test_c13_h01_exige_el_plazo_mismo_dia_y_no_una_mencion_generica():
    req = _payload(pupilas=f"{N}: anisocoria OD", motivo="Dolor cervical")
    salida = _ensure_emergency_preserved("Anisocoria OD; se sugiere valoracion oftalmologica.", req)
    assert "el mismo dia" in salida                       # se inyecta la conducta determinista


def test_c13_h01_conserva_el_texto_que_ya_cumple():
    req = _payload(pupilas=f"{N}: anisocoria OD", motivo="Dolor cervical")
    texto = "Anisocoria OD con dolor cervical referido; requiere valoracion oftalmologica el mismo dia."
    assert _ensure_emergency_preserved(texto, req) == texto


def test_c13_h01_no_purga_oracion_correcta_del_otro_ojo():
    caso = _CASOS["C13-31"]["entrada"]
    req = _payload(**caso)
    texto = "Midriasis OI de inicio reciente con dolor ocular y diplopia; requiere valoracion oftalmologica el mismo dia."
    assert _ensure_emergency_preserved(texto, req) == texto


def test_c13_h01_detecta_sin_anisocoria_como_contradiccion():
    req = _payload(pupilas=f"{N}: anisocoria OD", motivo="Dolor cervical")
    salida = _ensure_emergency_preserved("Sin anisocoria. Valorar en control anual.", req)
    assert "Sin anisocoria" not in salida and "anisocoria OD" in salida


def test_c13_h01_dpar_de_fecha_desconocida_no_es_urgencia_por_si_solo():
    assert not alertas_h01(pupilas="DPAR positivo en OD")
    assert alertas_h01(pupilas="DPAR positivo en OD de inicio hoy") == {"pupilas_alteradas"}


def test_c13_h01_payload_directo_sin_efectos_en_otros_campos():
    req = ImpresionClinicaRequest.model_validate({
        "receta_id": "c13", "refraccion": {"od": {"esfera": 0.0}, "oi": {"esfera": 0.0}},
        "clinica": {"reflejos_pupilares": "DPAR positivo en OD de inicio hoy"},
    })
    salida = _ensure_emergency_preserved("Examen normal.", req)
    assert "Examen normal" not in salida and "defecto pupilar aferente relativo OD" in salida
