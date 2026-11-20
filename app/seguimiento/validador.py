import re
import unicodedata

from app.patient_profile import word_count
from app.seguimiento.catalogo import BAJA, FRASES_FECHA, FRASES_USO, POR_ID
from app.seguimiento.combinacion import combinacion_valida
from app.seguimiento.fechas import formatear_fecha, periodo_en_palabras

LEXICO = (
    "miopia", "hipermetropia", "astigmatismo", "presbicia", "catarata", "glaucoma", "enfermedad",
    "diagnostic", "patolog", "sintoma", "borros", "empeor", "progres", "sano", "sana", "normal",
    "riesgo", "urgen", "grave", "peligr", "dano", "danar", "dane", "danad", "danin", "perder la vista", "ceguera", "garantiz", "promet",
    "perfect", "gratis", "descuento", "promocion", "oferta", "precio", "pag", "ultima oportunidad",
    "ultimo lugar", "quedan pocos", "solo esta semana", "hoy mismo", "antes de que", "debe", "tiene que",
    "es necesario", "no lo deje", "atrasad", "retras", "se le paso", "descuid", "no nos ha respondido",
    "sin respuesta", "ignor", "mayoria", "todos nuestros pacientes", "edad", "anos", "mayor", "abuel",
)
LEXICO += (
    "enfoc", "nitid", "clarid", "ve menos", "ve mejor",
    "no espere", "cuanto antes", "lo antes posible", "inmediat", "ya mismo", "apresur", "plazo", "limite",
    "complic", "consecuenc", "deterior", "problema", "afect",
    "hace mucho", "mucho tiempo", "no ha venido", "no viene", "lleva tiempo", "abandon", "olvid",
    "asegur", "saldra", "notara", "estrabism", "ambliop", "queratocon", "fatiga", "conjuntiv",
    "infecc", "inflam", "retin", "macul", "cornea", "pterigi", "carnosidad", "cirug", "operac",
    "laser", "lagrim", "presion ocular", "tension ocular",
)
PALABRAS = (
    "vista", "vision", "ojo", "ojos", "graduacion", "graduaciones",
    "ver", "ve", "vea", "vean", "veia", "viendo", "vio", "vera", "mirar", "mira", "mire",
    "dos", "tres", "cuatro", "cinco", "seis", "siete", "ocho", "nueve", "diez", "once", "doce",
    "quince", "veinte", "treinta", "cuarenta", "cincuenta", "sesenta", "setenta", "ochenta",
    "noventa", "cien", "ciento", "mil", "ano", "mes", "meses",
)
_LEXICO_RE = re.compile(r"\b(?:" + "|".join(map(re.escape, LEXICO)) + r")|\b(?:" + "|".join(PALABRAS) + r")\b|\$")
_TUTEO_RE = re.compile(
    r"\b(?:tu|tus|te|ti|contigo|tienes|puedes|quieres|necesitas|eres|vienes|haces|sabes|ven|dime|"
    r"avisanos|escribenos|cuentanos|visitanos|llamanos|contactanos|olvides|animate|acercate|aprovecha|"
    r"quieras|puedas|tengas|vengas|desees|gustes|apuntate|tuyo|tuya|dinos|prefieres|deseas|aparta|reserva)\b"
    r"|\bestas\s+(?:disponible|interesad\w*|list\w*)\b|(?<!le )(?<!les )\brecuerda\b"
)


def normalizar(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto.lower()) if not unicodedata.combining(c))


def ensamblar(apertura: str, frase_uso: str, frase_fecha: str, hechos: list[str], cierre: str) -> str:
    hechos_str = " ".join(POR_ID[h].texto for h in hechos if h in POR_ID)
    partes = [apertura, frase_uso, frase_fecha, hechos_str, cierre, BAJA]
    return "\n\n".join(p for p in partes if p)


def validar_estilo(apertura: str, invitacion: str = "") -> str | None:
    texto = (apertura + " " + invitacion).strip() if invitacion else apertura
    marcadores = re.findall(r":[a-z_]+", texto, re.I)
    if (sorted(marcadores) != [":clinica", ":paciente"] or
        apertura.count(":paciente") != 1 or apertura.count(":clinica") != 1 or
        re.search(r"[{}<>*_~`]|http|www", texto, re.I)):
        return "placeholders"
    if re.search(r"\d", texto):
        return "cifras"
    if "¿" in apertura or "?" in apertura:
        return "apertura"
    libre = normalizar(texto)
    if _TUTEO_RE.search(libre):
        return "tuteo"
    sin_lentes_condicionales = re.sub(r"\bsi usa lentes\b", "", libre)
    if _LEXICO_RE.search(libre) or re.search(r"\blentes\b", sin_lentes_condicionales):
        return "lexico"
    return None


def validar(req, partes_v2, elegibles: list[str], uso_lentes: str, *, mensaje: str | None = None) -> str | None:
    if hasattr(partes_v2, "apertura"):
        apertura = partes_v2.apertura
        frase_uso = partes_v2.frase_uso
        frase_fecha = partes_v2.frase_fecha
        hechos = partes_v2.hechos
        cierre = partes_v2.cierre
        cierre_id = partes_v2.cierre_id
    else:
        apertura = partes_v2.get("apertura", "")
        frase_uso = partes_v2.get("frase_uso", "")
        frase_fecha = partes_v2.get("frase_fecha", "")
        hechos = partes_v2.get("hechos", [])
        cierre = partes_v2.get("cierre", "")
        cierre_id = partes_v2.get("cierre_id", "")

    hechos_texto = " ".join(POR_ID[h].texto for h in hechos if h in POR_ID)
    cuerpo = "\n\n".join(p for p in (apertura, frase_uso, frase_fecha, hechos_texto, cierre) if p)
    palabras = word_count(cuerpo)
    total_len = len(cuerpo) + len(BAJA) + 2

    if not apertura.strip() or not (60 <= palabras <= 140) or total_len > 2000:
        return "palabras"

    if len(apertura) > 300 or "\n" in apertura or "\r" in apertura:
        return "apertura"

    estilo = validar_estilo(apertura)
    if estilo:
        return estilo

    if not cierre.strip() or len(cierre) > 300 or "\n" in cierre or "\r" in cierre:
        return "cierre"
    if cierre.count("¿") != 1 or cierre.count("?") != 1:
        return "cierre"
    cierre_norm = normalizar(cierre)
    if req.costo == "incluida":
        if not cierre_id.startswith("CI_INC_") or "incluida" not in cierre_norm or "costo" in cierre_norm:
            return "cierre"
    else:
        if not cierre_id.startswith("CI_COS_") or "costo" not in cierre_norm or any(w in cierre_norm for w in ("incluida", "gratis", "sin costo")):
            return "cierre"

    frases_validas_uso = [texto for _, texto in FRASES_USO.get(uso_lentes, [])]
    if frase_uso not in frases_validas_uso:
        return "uso"

    if req.estado_seguimiento == "proximo" and not req.ya_notificado_en_ciclo and req.fecha_revision is not None:
        if req.meses_periodo is not None and 3 <= req.meses_periodo <= 24:
            grupo_fecha = "P"
        else:
            grupo_fecha = "PS"
    else:
        grupo_fecha = "N"

    frases_validas_fecha = []
    for _, plantilla in FRASES_FECHA.get(grupo_fecha, []):
        if grupo_fecha == "P":
            frases_validas_fecha.append(plantilla.format(
                fecha=formatear_fecha(req.fecha_revision),
                periodo=periodo_en_palabras(req.meses_periodo),
            ))
        elif grupo_fecha == "PS":
            frases_validas_fecha.append(plantilla.format(fecha=formatear_fecha(req.fecha_revision)))
        else:
            frases_validas_fecha.append(plantilla)

    if frase_fecha not in frases_validas_fecha:
        return "fecha"

    if not combinacion_valida(hechos, elegibles):
        return "hechos"

    if mensaje is not None and mensaje != ensamblar(apertura, frase_uso, frase_fecha, hechos, cierre):
        return "hechos"

    return None
