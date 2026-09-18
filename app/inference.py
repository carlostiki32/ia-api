import logging
import re
from difflib import SequenceMatcher

import httpx

from app.config import settings
from app.prompt_builder import build_system_prompt, build_user_prompt, clean_impresion
from app.providers import ollama as ollama_provider
from app.schemas import ImpresionClinicaRequest

logger = logging.getLogger(__name__)

ABBREVIATIONS = {
    "O.D.":  "__ABBR_OD__",
    "O.I.":  "__ABBR_OI__",
    "A.O.":  "__ABBR_AO__",
    "Esf.":  "__ABBR_ESF__",
    "Cil.":  "__ABBR_CIL__",
    "Eje.":  "__ABBR_EJE__",
    "D.":    "__ABBR_D__",
    "s.c.":  "__ABBR_SC__",
    "c.c.":  "__ABBR_CC__",
}
_TOKEN_TO_ABBR = {token: abbr for abbr, token in ABBREVIATIONS.items()}
_ABBR_RE = re.compile(
    "|".join(re.escape(abbr) for abbr in sorted(ABBREVIATIONS, key=len, reverse=True))
)
_TOKEN_RE = re.compile("|".join(re.escape(token) for token in _TOKEN_TO_ABBR))

LIST_BULLET_RE      = re.compile(r"^(?:[-*•])\s+")
LIST_NUMBER_RE      = re.compile(r"^\d{1,2}\.\s+(?=[A-ZÁÉÍÓÚÑ])")
MULTISPACE_RE       = re.compile(r"\s+")
SENTENCE_END_RE     = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÚÑ])")
THINK_BLOCK_RE      = re.compile(r"<think>.*?</think>", re.DOTALL)
CODEFENCE_OPEN_RE   = re.compile(r"^```\w*\n?")
CODEFENCE_CLOSE_RE  = re.compile(r"\n?```\s*$")

# Heuristico calibrado para español con tokenizer Qwen (~3.3 chars/token).
# Es mas conservador ante datos tabulares, signos (+/-) y abreviaturas clinicas.
# Se usa solo para validacion preemptiva; el conteo real viene del
# prompt_eval_count que Ollama devuelve tras la inferencia.
_CHARS_PER_TOKEN_ES = 3.3

# Prefijo que marca ValueError de oversized prompt para que main.py
# lo pueda distinguir de otros ValueError y responder 413 en vez de 500.
CONTEXT_OVERFLOW_PREFIX = "context_overflow:"


def _estimate_tokens(text: str) -> int:
    return int(len(text) / _CHARS_PER_TOKEN_ES)


def _protect_abbreviations(text: str) -> str:
    return _ABBR_RE.sub(lambda m: ABBREVIATIONS[m.group(0)], text)


def _restore_abbreviations(text: str) -> str:
    return _TOKEN_RE.sub(lambda m: _TOKEN_TO_ABBR[m.group(0)], text)


def _split_sentences(text: str) -> list[str]:
    if not text:
        return []
    clean = MULTISPACE_RE.sub(" ", text).strip()
    if not clean:
        return []
    protected = _protect_abbreviations(clean)
    parts = SENTENCE_END_RE.split(protected)
    sentences = []
    for part in parts:
        restored = _restore_abbreviations(part).strip()
        if restored:
            sentences.append(restored)
    return sentences


def _similitud(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _normalize_sentence(text: str) -> str:
    text = MULTISPACE_RE.sub(" ", text.strip())
    text = text.rstrip(".!?")
    return text.lower()


def _strip_leading_list_markers(line: str) -> str:
    line = LIST_BULLET_RE.sub("", line)
    line = LIST_NUMBER_RE.sub("", line)
    return line.strip()


def _postprocess(text: str) -> str:
    # Qwen 3.5 puede emitir <think>..</think> aun con think=False.
    text = text.strip()

    if "<think>" in text or "</think>" in text:
        logger.info("Output crudo contenia tags <think>; se remueven")

    # Caso 1: bloques completos — eliminarlos.
    text = THINK_BLOCK_RE.sub("", text).strip()

    # Caso 2: </think> residual (apertura implicita al inicio, cierre presente).
    # Conservar solo lo posterior al ultimo </think>.
    if "</think>" in text:
        text = text.rsplit("</think>", 1)[-1].strip()

    # Caso 3: <think> sin cerrar (num_predict agoto el budget dentro del
    # razonamiento). Conservar solo lo ANTERIOR al primer <think>: si hay
    # parrafo valido antes se mantiene, si no queda vacio y cae al ValueError
    # final para disparar retry.
    if "<think>" in text:
        text = text.split("<think>", 1)[0].strip()

    text = CODEFENCE_OPEN_RE.sub("", text)
    text = CODEFENCE_CLOSE_RE.sub("", text)
    text = text.strip("`").strip()

    cleaned_lines = []
    for line in text.splitlines():
        line = _strip_leading_list_markers(line.strip())
        if line:
            cleaned_lines.append(line)

    text = " ".join(cleaned_lines)
    text = MULTISPACE_RE.sub(" ", text).strip()
    sentences = _split_sentences(text)
    text = " ".join(sentences).strip()

    if text and not text.endswith("."):
        text = f"{text}."

    if not text:
        raise ValueError("Model returned empty output after postprocessing")

    return text


def _ensure_follow_up_last(
    text: str,
    recommendation: str | None,
    payload: ImpresionClinicaRequest | None = None,
) -> str:
    """
    Agrega la recomendación de seguimiento al final del párrafo.

    El system prompt ya fue construido con effective_max = max_sentences - 1
    cuando hay recomendación, así que el modelo dejó espacio y no hay truncamiento.
    Esta función solo remueve duplicados y asegura posición final.
    Si existe una urgencia activa y la recomendación es un control anual/rutinario,
    se suprime para evitar contradicciones clínicas fatales (H01).
    """
    if not recommendation:
        return text

    if payload is not None and _has_active_emergencies(payload):
        from app.correlaciones.texto import _normalize_text
        norm_rec = _normalize_text(recommendation)
        if _INCOMPATIBLE_TIMEFRAME_RE.search(norm_rec):
            logger.warning(
                "Recomendacion de seguimiento rutinaria '%s' suprimida "
                "por colisionar con alerta de urgencia activa (H01).",
                recommendation,
            )
            return text

    follow_up = MULTISPACE_RE.sub(" ", recommendation.strip())
    if not follow_up:
        return text
    if not follow_up.endswith("."):
        follow_up = f"{follow_up}."

    sentences = _split_sentences(text)

    # Remover si el modelo ya incluyó la recomendación (detección exacta)
    normalized_follow_up = _normalize_sentence(follow_up)
    if sentences and _normalize_sentence(sentences[-1]) == normalized_follow_up:
        logger.info("Removed duplicate follow-up sentence generated by model")
        sentences = sentences[:-1]

    if sentences:
        similitud = _similitud(_normalize_sentence(sentences[-1]),
                               _normalize_sentence(follow_up))
        if similitud >= 0.70:
            logger.warning(
                "Removed semantically similar follow-up from model output "
                "(similarity: %.2f)", similitud
            )
            sentences = sentences[:-1]

    sentences.append(follow_up)

    final_text = " ".join(s.strip() for s in sentences if s.strip()).strip()
    final_text = MULTISPACE_RE.sub(" ", final_text)

    return final_text


from typing import NamedTuple, Callable


class AlertaUrgencia(NamedTuple):
    id: str
    prioridad: str
    ojo: str | None
    hallazgo_keywords: tuple[str, ...]
    accion_keywords: tuple[str, ...]
    texto_determinista: str


_EMERGENCY_SPECS = {
    "fondo_periferico_riesgo": {
        "hallazgo_keywords": (
            "desgarro", "desprendimiento", "rotura", "ruptura", "dialisis", "agujero operculado",
            "lattice", "empalizada", "palizada", "caracol", "retinosquisis", "schisis",
            "retina periferica", "agujero atrofico", "agujero retiniano",
        ),
        "accion_keywords": ("urgente", "urgencia", "retinolog", "inmediat", "midriasis"),
        "field_getter": lambda req: req.clinica.fondo_de_ojo if req.clinica else None,
        "is_manifest_urgent": lambda texto_corr: any(
            k in texto_corr.lower() for k in ("desgarro", "desprendimiento", "rotura", "ruptura", "dialisis", "urgente")
        ),
    },
    "glaucoma_asimetrico": {
        "hallazgo_keywords": (
            "defecto pupilar", "dpar", "rapd", "marcus gunn", "asimetric", "glaucomatosa"
        ),
        "accion_keywords": ("urgente", "urgencia", "prioritari", "oftalmol", "evaluacion"),
        "field_getter": lambda req: f"{req.clinica.reflejos_pupilares or ''} {req.clinica.fondo_de_ojo or ''}" if req.clinica else None,
        "is_manifest_urgent": lambda texto_corr: True,
    },
    "horner_o_tercer_par_sospecha": {
        "hallazgo_keywords": ("horner", "tercer par", "iii par", "ptosis"),
        "accion_keywords": ("urgente", "urgencia", "neurooftalmol"),
        "field_getter": lambda req: f"{req.clinica.reflejos_pupilares or ''} {req.clinica.anexos_oculares or ''}" if req.clinica else None,
        "is_manifest_urgent": lambda texto_corr: True,
    },
    "papila_patologica": {
        "hallazgo_keywords": (
            "papiledema", "borramiento", "hipertension intracraneal", "atrofia optica", "edema de papila"
        ),
        "accion_keywords": ("urgente", "urgencia", "neurolog", "neurooftalmol", "oftalmol"),
        "field_getter": lambda req: req.clinica.fondo_de_ojo if req.clinica else None,
        "is_manifest_urgent": lambda texto_corr: any(
            k in texto_corr.lower() for k in ("urgente", "papiledema", "borramiento")
        ),
    },
    "fondo_oclusion_vascular_urgente": {
        "hallazgo_keywords": (
            "oclusion", "vascular retiniana", "trombosis", "mancha rojo cereza", "arterial o venosa"
        ),
        "accion_keywords": ("urgente", "urgencia", "retinolog", "emergencia", "inmediat"),
        "field_getter": lambda req: req.clinica.fondo_de_ojo if req.clinica else None,
        "is_manifest_urgent": lambda texto_corr: True,
    },
    "pupilas_alteradas": {
        "hallazgo_keywords": (
            "defecto pupilar", "dpar", "rapd", "marcus gunn", "via optica"
        ),
        "accion_keywords": ("urgente", "urgencia", "neurooftalmol", "evaluacion urgente", "oftalmol"),
        "field_getter": lambda req: req.clinica.reflejos_pupilares if req.clinica else None,
        "is_manifest_urgent": lambda texto_corr: any(
            k in texto_corr.lower() for k in ("defecto pupilar", "dpar", "urgente")
        ),
    },
    "sintomas_alarma_traccion_vitreoretina": {
        "hallazgo_keywords": (
            "fotopsias", "miodesopsias", "destellos", "traccion vitreorretiniana", "traccion vitreo", "desprendimiento de vitreo"
        ),
        "accion_keywords": ("midriasis", "tres espejos", "indentacion", "descartar desgarros", "retina periferica", "retinolog"),
        "field_getter": lambda req: f"{req.paciente.motivo_consulta if req.paciente else ''} {req.clinica.fondo_de_ojo if req.clinica else ''}",
        "is_manifest_urgent": lambda texto_corr: True,
    },
}

_EMERGENCY_RULES = {
    nombre: spec["hallazgo_keywords"] + spec["accion_keywords"]
    for nombre, spec in _EMERGENCY_SPECS.items()
}

_INCOMPATIBLE_TIMEFRAME_RE = re.compile(
    r"\b("
    r"control\s+(?:anual|de\s+rutina|rutinario|en\s+(?:1|un)\s+a[nñ]o|cada\s+a[nñ]o)|"
    r"cita\s+(?:anual|de\s+rutina|rutinaria|en\s+(?:1|un)\s+a[nñ]o)|"
    r"seguimiento\s+(?:anual|de\s+rutina|rutinario|en\s+(?:1|un)\s+a[nñ]o)|"
    r"revisi[oó]n\s+(?:anual|de\s+rutina|rutinaria|en\s+(?:1|un)\s+a[nñ]o)|"
    r"(?:se\s+cita|se\s+recomienda|se\s+indica|se\s+sugiere)\s+.*?\b(?:anual|en\s+(?:1|un)\s+a[nñ]o)\b|"
    r"(?:en|dentro\s+de)\s+(?:1|un)\s+a[nñ]o|"
    r"pr[oó]ximo\s+a[nñ]o"
    r")\b",
    re.IGNORECASE,
)

_CONSULTATION_REASON_PREFIX_RE = re.compile(
    r"\b(?:acude|asiste|motivo\s+de\s+consulta|ingresa|refiere\s+que\s+acude)\b",
    re.IGNORECASE,
)

_FALSE_NORMALITY_RE = re.compile(
    r"\b("
    r"(?:examen|exploraci[oó]n|revisi[oó]n|estudio)\s+normal\w*|"
    r"(?:sin|no\s+se\s+(?:aprecian|observan|detectan|documentan))\s+(?:hallazgos|signos|alteraciones|patolog[ií]a)\w*|"
    r"todo\s+(?:dentro\s+de\s+la\s+)?normal\w*|"
    r"paciente\s+sano"
    r")\b",
    re.IGNORECASE,
)

_EXPLICIT_NEGATION_PREFIXES = (
    "no hay",
    "sin evidencia de",
    "sin evidencia",
    "sin hallazgos de",
    "sin signos de",
    "sin sospecha de",
    "sin presencia de",
    "sin",
    "niega",
    "descarta",
    "descarte de",
    "se descarta",
    "no se observa",
    "no se observan",
    "no se aprecia",
    "no se aprecian",
    "no se detecta",
    "no se detectan",
    "no se documenta",
    "no presenta",
    "ausencia de",
    "libre de",
    "negativo para",
)


def _extract_finding_laterality(text: str | None, keywords: tuple[str, ...]) -> str | None:
    if not text:
        return None
    from app.correlaciones.texto import _normalize_text
    norm = _normalize_text(text)
    for kw in keywords:
        for m in re.finditer(re.escape(kw), norm):
            clause_start = max([norm.rfind(sep, 0, m.start()) for sep in ".;|"] or [-1]) + 1
            clause_prefix = norm[clause_start:m.start()]
            ends = [pos for pos in [norm.find(sep, m.end()) for sep in ".;|"] if pos != -1]
            clause_end = min(ends) if ends else len(norm)
            clause_suffix = norm[m.end():clause_end]

            if re.search(r"\b(ao|ambos ojos|bilateral)\b", clause_prefix):
                return "AO"
            has_od = bool(re.search(r"\b(od|ojo derecho)\b", clause_prefix))
            has_oi = bool(re.search(r"\b(oi|ojo izquierdo)\b", clause_prefix))
            if has_od and not has_oi:
                return "OD"
            if has_oi and not has_od:
                return "OI"

            if re.search(r"\b(ao|ambos ojos|bilateral)\b", clause_suffix[:30]):
                return "AO"
            has_od_suf = bool(re.search(r"\b(od|ojo derecho)\b", clause_suffix[:30]))
            has_oi_suf = bool(re.search(r"\b(oi|ojo izquierdo)\b", clause_suffix[:30]))
            if has_od_suf and not has_oi_suf:
                return "OD"
            if has_oi_suf and not has_od_suf:
                return "OI"
    return None


def _get_active_emergency_alerts(payload: ImpresionClinicaRequest) -> list[AlertaUrgencia]:
    from app.correlaciones.registry import evaluar_correlaciones_con_nombres

    activas = evaluar_correlaciones_con_nombres(payload)
    if not activas:
        return []

    alerts: list[AlertaUrgencia] = []
    for nombre, texto_corr in activas:
        spec = _EMERGENCY_SPECS.get(nombre)
        if spec:
            if not spec["is_manifest_urgent"](texto_corr):
                continue
            raw_field_val = spec["field_getter"](payload)
            eye = _extract_finding_laterality(raw_field_val, spec["hallazgo_keywords"])
            alerts.append(
                AlertaUrgencia(
                    id=nombre,
                    prioridad="URGENTE",
                    ojo=eye,
                    hallazgo_keywords=spec["hallazgo_keywords"],
                    accion_keywords=spec["accion_keywords"],
                    texto_determinista=texto_corr.strip(),
                )
            )
        elif "hallazgo urgente" in texto_corr.lower():
            # Derivacion dinamica de urgencia para reglas con 'Hallazgo urgente:' en su texto,
            # garantizando cobertura universal por metadatos (H02).
            alerts.append(
                AlertaUrgencia(
                    id=nombre,
                    prioridad="URGENTE",
                    ojo=None,
                    hallazgo_keywords=(nombre.replace("_", " "),),
                    accion_keywords=("urgente", "urgencia", "prioritari", "inmediat", "evaluacion", "valoracion"),
                    texto_determinista=texto_corr.strip(),
                )
            )
    return alerts


def _has_active_emergencies(payload: ImpresionClinicaRequest) -> bool:
    return bool(_get_active_emergency_alerts(payload))


def _is_sentence_contradictory(sentence: str, alert: AlertaUrgencia) -> bool:
    from app.correlaciones.texto import _normalize_text

    norm_s = _normalize_text(sentence)
    if not norm_s:
        return False

    # 1. Negacion del hallazgo (prefija o sufija con limites de palabra estrictos)
    for kw in alert.hallazgo_keywords:
        if kw in norm_s:
            for neg in _EXPLICIT_NEGATION_PREFIXES:
                neg_pat = r"\b" + re.escape(neg.strip()) + r"\s+(?:[^\.\;\,]*\b)?" + re.escape(kw) + r"\b"
                if re.search(neg_pat, norm_s):
                    return True
            suf_pat = r"\b" + re.escape(kw) + r"\s+(?:[^\.\;\,]*\b)?(descartad\w*|ausente\w*|negativ\w*|normal\w*)\b"
            if re.search(suf_pat, norm_s):
                return True

    # 2. Negacion de la urgencia / accion requerida
    for ak in ("urgente", "urgencia", "inmediat"):
        if ak in norm_s:
            for neg in ("no es", "no reviste", "no requiere", "sin", "no hay", "descarta", "se descarta", "no amerita"):
                neg_pat = r"\b" + re.escape(neg) + r"\s+(?:[^\.\;\,]*\b)?" + re.escape(ak) + r"\b"
                if re.search(neg_pat, norm_s):
                    return True

    # 3. Plazo incompatible (control anual / rutinario en presencia de urgencia)
    if not _CONSULTATION_REASON_PREFIX_RE.search(norm_s):
        if _INCOMPATIBLE_TIMEFRAME_RE.search(norm_s):
            return True

    # 4. Falsa normalidad global o de la estructura afectada frente a una urgencia activa (H02)
    if not _CONSULTATION_REASON_PREFIX_RE.search(norm_s):
        if _FALSE_NORMALITY_RE.search(norm_s):
            return True
        if alert.id in ("pupilas_alteradas", "horner_o_tercer_par_sospecha", "glaucoma_asimetrico"):
            if re.search(r"\b(?:pupilas?|reflejos?\s+pupilares?)\s+normal\w*\b", norm_s):
                return True
        if alert.id in ("fondo_periferico_riesgo", "papila_patologica", "fondo_oclusion_vascular_urgente", "sintomas_alarma_traccion_vitreoretina"):
            if re.search(r"\b(?:fondo\s+de\s+ojo|retina|nervio\s+[oó]ptico|papila)\s+normal\w*\b", norm_s):
                return True

    # 5. Lateralidad contradictoria
    if alert.ojo in ("OD", "OI"):
        sentence_eye = _extract_finding_laterality(sentence, alert.hallazgo_keywords)
        if sentence_eye and sentence_eye != "AO" and sentence_eye != alert.ojo:
            return True

    return False


def _ensure_emergency_preserved(text: str, payload: ImpresionClinicaRequest) -> str:
    """
    Salvaguarda determinista de seguridad clinica (H01):
    Garantiza que si el paciente presenta un hallazgo urgente (desgarro retiniano,
    DPAR, sospecha de Horner/III par, papiledema u oclusion vascular):
    1. Se detecten y purguen oraciones del LLM que nieguen el hallazgo, nieguen la urgencia,
       adjudiquen una lateralidad incorrecta o sugieran plazos diferidos incompatibles (ej. control anual).
    2. Se verifique que el texto remanente preserve tanto el hallazgo como la conducta
       de derivacion urgente.
    3. Si la alerta fue omitida, negada o diluida, se inyecta deterministamente
       la conducta obligatoria.
    """
    alerts = _get_active_emergency_alerts(payload)
    if not alerts:
        return text

    from app.correlaciones.texto import _keyword_matches, _normalize_text

    sentences = _split_sentences(text)
    clean_sentences: list[str] = []
    contradictions_purged_for: set[str] = set()

    for s in sentences:
        contradictory = False
        for alert in alerts:
            if _is_sentence_contradictory(s, alert):
                logger.warning(
                    "Salvaguarda H01: Purgando oracion contradictoria/negada para alerta '%s': '%s'",
                    alert.id,
                    s,
                )
                contradictory = True
                contradictions_purged_for.add(alert.id)
                break
        if not contradictory:
            clean_sentences.append(s)

    candidate_text = " ".join(s.strip() for s in clean_sentences if s.strip()).strip()
    candidate_norm = _normalize_text(candidate_text)

    missing_alerts_text: list[str] = []

    for alert in alerts:
        # Si se purgo una contradiccion en el texto del LLM para esta alerta,
        # no confiamos en fragmentos ambiguos: inyectamos deterministamente la conducta obligatoria.
        if alert.id in contradictions_purged_for:
            missing_alerts_text.append(alert.texto_determinista)
            continue

        # Comprobar presencia afirmativa del hallazgo (cualquier oracion con negacion ya fue purgada)
        has_finding_affirmed = any(
            kw in candidate_norm
            for kw in alert.hallazgo_keywords
        )

        # Comprobar presencia afirmativa de la accion / urgencia (cualquier oracion con negacion ya fue purgada)
        has_action_affirmed = any(
            ak in candidate_norm
            for ak in alert.accion_keywords
        )

        # Comprobar lateralidad coherente si aplica
        correct_laterality = True
        if alert.ojo in ("OD", "OI"):
            eye_found = _extract_finding_laterality(candidate_text, alert.hallazgo_keywords)
            if eye_found and eye_found != "AO" and eye_found != alert.ojo:
                correct_laterality = False

        if not (has_finding_affirmed and has_action_affirmed and correct_laterality):
            logger.warning(
                "Salvaguarda H01: Alerta urgente '%s' incompleta u omitida en texto LLM; inyectando deterministamente.",
                alert.id,
            )
            missing_alerts_text.append(alert.texto_determinista)

    if not missing_alerts_text and len(clean_sentences) == len(sentences):
        return text

    final_sentences = list(clean_sentences)
    for alert_text in missing_alerts_text:
        formatted = alert_text.strip()
        if not formatted.endswith("."):
            formatted += "."
        final_sentences.append(formatted)

    final_text = " ".join(s.strip() for s in final_sentences if s.strip()).strip()
    final_text = MULTISPACE_RE.sub(" ", final_text)
    if final_text and not final_text.endswith("."):
        final_text += "."
    return final_text



async def run_inference(
    payload: ImpresionClinicaRequest,
    client: httpx.AsyncClient,
) -> str:
    """
    Orquesta la inferencia contra Ollama (qwen3.5:9b): construye los prompts,
    valida el contexto de forma preemptiva, llama al modelo y aplica el
    postprocesado + guardarraíles. Devuelve el párrafo final.
    """
    # System prompt inmutable: permite que Ollama mantenga y reutilice el KV Prefix Cache
    # de los ~1595 tokens a traves de peticiones consecutivas (reduciendo TTFT).
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(payload)

    # Logging detallado del prompt renderizado antes de enviar a inferencia
    logger.debug(
        "\n"
        "╔═══════════════════════════════════════════════════════════════════════╗\n"
        "║          PROMPT RENDERIZADO ANTES DE INFERENCIA                      ║\n"
        "╚═══════════════════════════════════════════════════════════════════════╝\n"
        "\n📋 SYSTEM PROMPT (%d caracteres, ~%d tokens):\n"
        "────────────────────────────────────────────────────────────────────────\n"
        "%s\n"
        "────────────────────────────────────────────────────────────────────────\n"
        "\n📝 USER PROMPT (%d caracteres, ~%d tokens):\n"
        "────────────────────────────────────────────────────────────────────────\n"
        "%s\n"
        "────────────────────────────────────────────────────────────────────────\n"
        "\n⚙️  TOTALES: ~%d tokens estimados\n",
        len(system_prompt),
        _estimate_tokens(system_prompt),
        system_prompt,
        len(user_prompt),
        _estimate_tokens(user_prompt),
        user_prompt,
        _estimate_tokens(system_prompt) + _estimate_tokens(user_prompt),
    )

    # Validacion preemptiva de contexto: el prompt + la salida deben caber en num_ctx.
    est_input = _estimate_tokens(system_prompt + user_prompt)
    est_total = est_input + settings.ollama_num_predict
    ctx_budget = int(settings.ollama_num_ctx * 0.95)
    if est_total > ctx_budget:
        raise ValueError(
            f"{CONTEXT_OVERFLOW_PREFIX} prompt estimado ({est_input} tok) + "
            f"salida ({settings.ollama_num_predict} tok) excede num_ctx "
            f"({settings.ollama_num_ctx}). Revisar longitud de campos "
            "clinicos de texto libre."
        )

    raw_text, _ = await ollama_provider.call(system_prompt, user_prompt, client)

    try:
        text = _postprocess(raw_text)
    except ValueError:
        logger.error(
            "Model output empty after postprocessing. Raw length: %d chars",
            len(raw_text),
        )
        raise

    text = clean_impresion(text)  # ← aquí, después de postprocess y antes de follow-up
    text = _ensure_emergency_preserved(text, payload)

    return _ensure_follow_up_last(text, payload.clinica.recomendacion_seguimiento, payload=payload)