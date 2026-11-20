import re
import unicodedata

from app.patient_profile import word_count
from app.seguimiento.catalogo import BAJA, POR_ID
from app.seguimiento.combinacion import combinacion_valida

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


def ensamblar(apertura: str, ids: list[str], invitacion: str) -> str:
    return "\n\n".join(p for p in (apertura, " ".join(POR_ID[id].texto for id in ids), invitacion, BAJA) if p)


def validar_estilo(apertura: str, invitacion: str) -> str | None:
    texto = apertura + " " + invitacion
    marcadores = re.findall(r":[a-z_]+", texto, re.I)
    if (sorted(marcadores) != [":clinica", ":paciente"] or
        apertura.count(":paciente") != 1 or apertura.count(":clinica") != 1 or
        re.search(r"[{}<>*_~`]|http|www", texto, re.I)):
        return "placeholders"
    if re.search(r"\d", texto):
        return "cifras"
    libre = normalizar(texto)
    if _TUTEO_RE.search(libre):
        return "tuteo"
    sin_lentes_condicionales = re.sub(r"\bsi usa lentes\b", "", libre)
    if _LEXICO_RE.search(libre) or re.search(r"\blentes\b", sin_lentes_condicionales):
        return "lexico"
    return None


def validar(req, apertura: str, ids: list[str], invitacion: str, elegibles: list[str], *, mensaje: str | None = None) -> str | None:
    frases = " ".join(POR_ID[id].texto for id in ids if id in POR_ID)
    texto = " ".join((apertura, frases, invitacion))
    if (not apertura.strip() or not invitacion.strip() or
        any(len(p) > 300 or "\n" in p or "\r" in p for p in (apertura, invitacion)) or
        not 50 <= word_count(texto) <= 110 or len(texto) + len(BAJA) + 8 > 2000):
        return "palabras"
    estilo = validar_estilo(apertura, invitacion)
    # El orden normativo pone pregunta antes que tuteo y léxico.
    if estilo in ("placeholders", "cifras"):
        return estilo
    if not invitacion.endswith("?") or "¿" not in invitacion:
        return "pregunta"
    if estilo:
        return estilo
    libre = normalizar(apertura + " " + invitacion)
    invit = normalizar(invitacion)
    # La condición se comunica en el hecho o la invitación, una sola vez.
    if re.search(r"\b(?:costo|incluid[oa]s?)\b", normalizar(apertura)):
        return "costo"
    if req.costo == "con_costo":
        if re.search(r"\b(?:incluid[oa]s?|sin costo|gratis)\b|\bgratuit", libre):
            return "costo"
        if ("costo" in invit) == ("con_costo_claro" in ids):
            return "costo"
        if invit.count("costo") > 1:
            return "costo"
    else:
        if re.search(r"\b(?:tiene costo|tiene un costo|monto|tarifa|arancel|cuota|importe)\b|\b(?:cobr|pag)", libre):
            return "costo"
        if "incluida_sin_costo" in ids:
            if "incluida" in invit or "costo" in invit:
                return "costo"
        elif "incluida" not in invit:
            return "costo"
        if invit.count("incluida") > 1:
            return "costo"
    if not combinacion_valida(ids, elegibles):
        return "combinacion"
    if mensaje is not None and mensaje != ensamblar(apertura, ids, invitacion):
        return "hechos"
    return None
