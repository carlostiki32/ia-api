"""Reglas deterministas del contrato del corpus, aplicadas al caso completo.

El verificador semántico sigue siendo necesario: las reglas léxicas no certifican
una paráfrasis clínica arbitraria. El orden es estable ante infracciones múltiples.
"""
import json
import re

from app.correlaciones.texto import _is_match_negated
from app.paciente.sintomas import normalizar, ocurrencias

VERSION = "validador-v1"
REGLAS = ("json", "longitud", "tuteo", "cifras", "meta", "normalidad", "promesa", "magnitud",
          "accion_propia", "enfermedad", "sintoma_no_referido", "componente", "modalidad", "consejo", "lente")


def _sin_duplicados(pares):
    obj = {}
    for k, v in pares:
        if k in obj:
            raise ValueError("clave duplicada")
        obj[k] = v
    return obj


def parsear(raw):
    if isinstance(raw, str):
        return json.loads(raw, object_pairs_hook=_sin_duplicados,
                          parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))
    return raw


def estructura(obj, contexto, *, admitir_abstencion=False):
    if not isinstance(obj, dict) or set(obj) != {"frases"} or not isinstance(obj["frases"], list):
        return False
    if not (0 if admitir_abstencion else 1) <= len(obj["frases"]) <= 4:
        return False
    for f in obj["frases"]:
        if not isinstance(f, dict) or set(f) != {"texto", "fuentes"}:
            return False
        if not isinstance(f["texto"], str) or not f["texto"].strip():
            return False
        ids = f["fuentes"]
        if not isinstance(ids, list) or not ids or any(not isinstance(i, str) or i not in contexto.ids for i in ids):
            return False
        if len(ids) != len(set(ids)):
            return False
    return True


_ENFERMEDADES = r"\b(?:glaucoma|presbicia|cataratas?|queratocono|retinopatia(?: diabetica| hipertensiva)?|diabetes|degeneracion macular|dmae|neuropatia(?: optica)?|desprendimiento de retina|rotura retiniana|hipertension(?: intracraneal| arterial)?|arteritis de celulas gigantes|ambliopia|estrabismo|uveitis|conjuntivitis|blefaritis|ojo seco|maculopatia|edema macular|retinosis pigmentaria|sindrome(?: de horner)?|horner|paresia|paralisis|ectasia|oclusion(?: arterial| venosa| vascular)?(?: retiniana)?|desprendimiento vitreo|retinitis|retinosis pigmentaria|enfermedad\w*)\b"
_CONSEJOS = {
    "pausas": r"\b(?:pausas?|descansos?(?: visuales?| periodicos?)?|descansar la vista)\b",
    "gotas": r"\b(?:gotas|lubricantes|lagrimas artificiales|colirios)\b",
    "ejercicios": r"\b(?:ejercicios?|entrenar los ojos)\b",
    "iluminacion": r"\b(?:iluminacion|iluminar|luz ambiental)\b",
    "monitor": r"\b(?:mantenga|coloque|ajuste).{0,40}\b(?:monitor|pantalla)\b",
    "parpadeo": r"\b(?:parpade\w*)\b",
    "hidratacion": r"\b(?:hidratar\w*|hidratacion|beber agua|tomar agua|beba agua)\b",
    "higiene": r"\b(?:limpieza|higiene|lavar\w*|lave|limpie)\b",
    "compresas": r"\bcompresas?\b",
    "distancia": r"\b(?:mantener|mantenga|ajuste|guardar|guarde)\b.{0,35}\bdistancia\b",
    "brillo": r"\b(?:reducir|reduzca|ajustar|ajuste).{0,30}brillo\b",
    "solar": r"\b(?:proteccion solar|lentes oscuros)\b",
    "postura": r"\b(?:evite leer recostado|postura de lectura)\b",
    "habitos": r"\b(?:duerma|dormir|alimentacion|dieta|vitaminas|suplementos|protector solar|filtro azul)\b",
}


def _componentes(texto, contexto):
    rx = {lado: contexto.contenido("rx." + lado) for lado in ("od", "oi")}
    if not all(rx.values()):
        return bool(re.search(r"\b(?:miopia|hipermetropia|astigmatismo|graduacion|prescripcion|formula(?: de sus lentes)?|correccion|compensa\w*|apoyo (?:para |de )?cerca)\b", texto))
    for frase in re.split(r"[.;]|\b(?:mientras(?: que)?|en tanto que|pero)\b", texto):
        # Separar cláusulas de ojos; no usar las fuentes citadas como autorización.
        frase = re.sub(r"(ojo (?:derecho|izquierdo))\s+[ye]\s+(?=(?:miopia|hipermetropia|astigmatismo))", r"\1;", frase)
        partes = re.split(r";", frase) if ";" in frase else re.split(r"\s+y\s+(?=(?:(?:en )?(?:su|el) )?ojo (?:derecho|izquierdo) (?:presenta|muestra|tiene|combina|se|no))", frase)
        for parte in partes:
            ojos = []
            if re.search(r"\b(?:derech[oa]|od)\b", parte): ojos.append("od")
            if re.search(r"\b(?:izquierd[oa]|oi)\b", parte): ojos.append("oi")
            if not ojos:
                ojos = ["od", "oi"]
                sin_lado = not re.search(r"\b(?:ambos|dos|sus ojos|sus graduaciones)\b", parte)
            else:
                sin_lado = False
            for c in ("miopia", "hipermetropia", "astigmatismo"):
                for m in re.finditer(r"\b" + c + r"\b", parte):
                    negada = bool(re.search(r"\b(?:sin|no presenta[n]?|no tiene[n]?)\b.{0,30}$", parte[:m.start()]))
                    presentes = [c in [normalizar(x) for x in rx[lado]["componentes"]] for lado in ojos]
                    if (negada and any(presentes)) or (not negada and not (any(presentes) if sin_lado else all(presentes))):
                        return True
            if re.search(r"\b(?:apoyo|ayuda|adicion)(?: extra)? (?:para (?:enfocar (?:de )?)?|de )?(?:cerca|cercan\w*)\b", parte):
                if not all(rx[lado]["apoyo_cerca"] for lado in ojos):
                    return True
            if re.search(r"\b(?:plano|sin graduacion|no (?:tiene|presenta) graduacion)\b", parte):
                if not all(rx[lado]["plano"] for lado in ojos): return True
    # El orden derecho-izquierdo también es parte de la correspondencia del perfil.
    der, izq = texto.find("derecho"), texto.find("izquierdo")
    return der >= 0 and izq >= 0 and izq < der


def validar(candidato, contexto, *, done_reason=None):
    try:
        obj = parsear(candidato)
    except (ValueError, TypeError, RecursionError):
        return "json"
    if done_reason == "length" or not estructura(obj, contexto):
        return "json"
    textos = [normalizar(f["texto"]) for f in obj["frases"]]
    texto = " ".join(textos)
    if len(re.findall(r"\b\w+\b", texto)) > 120:
        return "longitud"
    if any(len(f["texto"]) > 320 for f in obj["frases"]):
        return "json"
    if re.search(r"\b(?:tu|te|ti|tus|contigo|tienes|presentas|ves|notas|usas|sientes|puedes|debes|haz|mira|utiliza tus|procura|recuerda|mantente|cuidas|padeces)\b|\b(?:ayudarte|explicarte|cuidarte|recordarte|darte|recomendarte|ponerte|moverte|decirte|sentirte|mirarte|lavarte|aplicarte|adaptarte)\b", texto):
        return "tuteo"
    if re.search(r"\d|\b(?:dioptrias?|grados?|por ciento|porcentajes?|menos (?:un[oa]?|dos|tres|cuatro|cinco|seis|siete|ocho|nueve|diez)|veinte cuarenta)\b", texto):
        return "cifras"
    if re.search(r"\bi\.\s*a\.", texto) or re.search(r"\b(?:ia|inteligencia artificial|i\.a\.|impresion clinica|correlacion(?:es)?|modelo de lenguaje|soy un modelo|prompt)\b|(?:[a-z][a-z0-9+.-]*://|mailto:|data:)|www\.|[<>\[\]`#*_]|(?:^|\s)[-•]\s|\n", " ".join(f["texto"].lower() for f in obj["frases"])) or re.search(r"\b(?:impresion clinica|correlacion(?:es)?)\b", texto) or re.search(r"[\x00-\x1f\x7f-\x9f\u200b-\u200f\u202a-\u202e\u2060-\u206f\ud800-\udfff\ufeff]", " ".join(f["texto"] for f in obj["frases"])):
        return "meta"
    if re.search(r"\b(?:sano[s]?|sana[s]?|normal(?:es)?|perfect\w*|todo (?:esta )?bien|todo en orden|sin alteraciones|saludables?|sin patologia|no necesita\w*|no requiere\w*)\b", texto):
        # «verá perfecto» se clasifica como promesa antes que normalidad.
        if not re.search(r"\bvera perfecto\b", texto): return "normalidad"
    if re.search(r"\b(?:cura\w*|garantiz\w*|resolvera\w*|eliminara\w*|solucionara\w*|desaparecera\w*|vera (?:perfecto|bien))\b", texto):
        return "promesa"
    if re.search(r"\b(?:leve(?:s|mente)?|baj[oa]s?|alt[oa]s?|fuerte[s]?|grave[s]?|sever[oa]s?|moderad[oa]s?|elevad[oa]s?)\b", texto):
        return "magnitud"
    if re.search(r"\b(?:\w*oftalmolog\w*|retinolog\w*|neurolog\w*|especialista(?:s)?|urgente\w*|urgencias|de inmediato|hoy mismo|proxim[oa]s? (?:dias?|horas?|semanas?)|plazo|sin demora|derivacion|derivar\w*|referencia a|valoracion medica|revision medica|cita medica|medico|facultativo)\b", texto):
        return "accion_propia"
    clinico = normalizar(contexto.contenido("clinico", ""))
    for m in re.finditer(_ENFERMEDADES, texto):
        enfermedad = m.group()
        if not re.search(r"\bpara descartar\s+(?:(?:una?|el|la)\s+)?$", texto[:m.start()]):
            return "enfermedad"
        if not re.search(r"\b(?:para descartar|descarte de|a descartar)\s+(?:(?:una?|el|la)\s+)?" + re.escape(enfermedad) + r"\b", clinico):
            return "enfermedad"
    referidos = set(contexto.contenido("motivo", {}).get("sintomas_referidos", []))
    for frase in textos:
        atribuye = bool(re.search(r"\b(?:usted (?:nos )?(?:refiere|refirio|comento|comenta|indico|conto|presenta|tiene|padece|ve|siente|nota|experimenta)|nos (?:comento|refirio|indico)|que usted refiere|su (?:dolor|ardor|lagrimeo|comezon|fatiga)|le duele|por eso siente)\b", frase))
        if atribuye:
            for id, *_ in ocurrencias(frase):
                if id not in referidos:
                    return "sintoma_no_referido"
            if re.search(r"\b(?:destellos|moscas|sombras? (?:sobre|en) la vision|vision doble|dolor intenso)\b", frase):
                return "sintoma_no_referido"
    if _componentes(texto, contexto):
        return "componente"
    for frase in textos:
        # Una posibilidad de otra oración no autoriza el efecto afirmado.
        for oracion in re.split(r"[.;!?]|\b(?:pero|aunque|mientras|y (?:el|la))\b", frase):
            efecto = re.search(r"\b(?:genera\w*|provoca\w*|causa\w*|ocasiona\w*|dificulta\w*|impide|disminuye|desencadena\w*|distorsiona\w*|compromete|produce|hace que|exige|demanda|resta|ve borroso|vea borroso|fatiga\w*|cansa\w*)\b", oracion)
            neutral = re.search(r"\b(?:correccion|compensa|incluye|presenta|apoyo|lentes?)\b", oracion) and not efecto
            referido = any(id in referidos for id, *_ in ocurrencias(oracion)) and re.search(r"\b(?:refiere|comento|refirio|indico|presenta|percibe)\b", oracion)
            if efecto and not neutral and not referido and not re.search(r"\b(?:puede[n]?|podria[n]?)\b", oracion):
                return "modalidad"
    respaldo = normalizar(" ".join(str(h["contenido"]) for h in contexto.hechos if h["id"] == "clinico" or h["id"].startswith("cor.")))
    for patron in _CONSEJOS.values():
        if re.search(patron, texto) and not any(not _is_match_negated(respaldo, m.start(), m.end()) for m in re.finditer(patron, respaldo)):
            # Describir una película lagrimal no equivale a indicar gotas.
            if patron == _CONSEJOS["parpadeo"] and not re.search(r"\b(?:parpadear|parpadee|parpadeando)\b", texto): continue
            return "consejo"
    lente = contexto.contenido("lente", {}).get("id")
    menciones = {
        "monofocal": r"\bmonofocal\w*\b",
        "progresivo": r"\b(?:progresiv\w*|multifocal\w*)\b",
        "bifocal_blended": r"\b(?:blended|bifocal(?:es)? (?:combinad\w*|invisible\w*|sin linea))\b",
        "flat_top": r"\b(?:flat.?top|segmento (?:recto|plano|visible)|bifocal(?:es)? de segmento)\b",
    }
    if any(re.search(patron, texto) and id != lente for id, patron in menciones.items()):
        return "lente"
    if re.search(r"\bbifocal\w*\b", texto) and lente not in ("bifocal_blended", "flat_top"):
        return "lente"
    if lente == "monofocal":
        for frase in textos:
            if re.search(r"\bmonofocal\w*\b", frase) and re.search(r"\b(?:lejos|cerca|lejan\w*|cercan\w*|distantes|lectura)\b", frase):
                return "lente"
    if lente == "progresivo" and re.search(r"\b(?:linea divisoria|segmento visible)\b", texto) and not re.search(r"\bsin linea\b", texto):
        return "lente"
    if lente == "flat_top" and re.search(r"transicion gradual|invisible|sin cortes|no presentan? (?:ninguna )?division visible", texto):
        return "lente"
    if lente == "bifocal_blended" and re.search(r"linea divisoria (?:muy )?marcada|segmento visible", texto):
        return "lente"
    return None
