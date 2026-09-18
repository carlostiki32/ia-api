"""Dominio: edad, lente, motivo y agudeza (8 correlaciones).

presbicia_multifocal, presbicia_sin_adicion, adicion_incongruente_edad,
insuficiencia_acomodacion_joven, cvs_sospecha, ambliopia_sospecha,
deficit_visual_inexplicado_refractivo y adulto_mayor_screening. Las redes de
seguridad solo disparan si no hay ya una causa organica documentada que
explique la reduccion visual (de ahi los imports de otros dominios).
"""
from __future__ import annotations

import re

from app.correlaciones.base import _memoize_cond
from app.correlaciones.anexos_cristalino import _KEYWORDS_OPACIDAD_CRISTALINO, _cond_opacidad_cristaliniana
from app.correlaciones.corneal import _cond_astigmatismo_lenticular_puro
from app.correlaciones.fondo_de_ojo import (
    _KEYWORDS_FONDO_DMAE,
    _KEYWORDS_FONDO_GLAUCOMATOSO,
    _KEYWORDS_FONDO_MACULAR_OTROS,
    _KEYWORDS_FONDO_OCLUSION_VASCULAR,
    _KEYWORDS_ISNT_VIOLADA,
    _KEYWORDS_PAPILA_NO_GLAUCOMA,
    _cond_fondo_glaucomatoso,
    _cond_fondo_hipertensivo,
    _cond_fondo_macular_dmae,
    _cond_fondo_macular_otros,
    _cond_fondo_oclusion_vascular_urgente,
    _cond_fondo_periferico_riesgo,
    _cond_fondo_vascular_diabetico,
    _cond_glaucoma_asimetrico,
    _cond_isnt_violada_papila,
    _cond_papila_patologica,
)
from app.correlaciones.pupilas_motilidad import _cond_horner_o_tercer_par_sospecha
from app.correlaciones.queratometria import _req_has_corneal_irregularity
from app.correlaciones.refraccion_utils import _av_denominator, _av_es_limitada, _equivalente_esferico
from app.correlaciones.refractivas import _cond_anisometropia
from app.correlaciones.texto import (
    _AFFIRMATIVE_TRANSITIONS,
    _NEGACIONES_PRE,
    _WHOLE_WORD_KEYWORDS,
    _compiled_keyword,
    _contains_keyword,
    _cover_desviaciones,
    _find_neg_bounded,
    _is_word_bounded,
    _keyword_matches,
    _normalize_cover_text,
    _normalize_text,
)
from app.schemas import ImpresionClinicaRequest

_EYE_MARKERS_EXPLICIT_RE = re.compile(
    r"\b(ao|ambos ojos|bilateral|bilaterales|od|oi|ojo derecho|ojo izquierdo)\b"
)
_AO_MARKERS_RE = re.compile(r"\b(ao|ambos ojos|bilateral|bilaterales)\b")
_OD_MARKERS_RE = re.compile(r"\b(od|ojo derecho)\b")
_OI_MARKERS_RE = re.compile(r"\b(oi|ojo izquierdo)\b")


def _finding_applies_to_eye(
    text: str | None,
    keywords: tuple[str, ...] | list[str],
    target_eye: str,
) -> bool:
    """Determina si alguna de las keywords coincide afirmativamente en text y corresponde
    clinicamente al ojo objetivo (target_eye: 'OD' o 'OI').
    
    Respeta lateralidad por ojo, clausulas, cabeceras y ventanas de negacion.
    """
    if not text:
        return False
    target = target_eye.upper()
    if target not in ("OD", "OI"):
        return False

    norm = _normalize_text(text)
    if not norm:
        return False

    has_any_laterality_marker = _EYE_MARKERS_EXPLICIT_RE.search(norm) is not None

    for kw in keywords:
        whole_word = kw in _WHOLE_WORD_KEYWORDS
        for m in _compiled_keyword(kw).finditer(norm):
            if whole_word and not _is_word_bounded(norm, m.start(), m.end()):
                continue

            # Verificar negacion en la oracion local del match
            sentence_start = max([norm.rfind(sep, 0, m.start()) for sep in ".;:!?"] or [-1]) + 1
            sentence_prefix = norm[sentence_start:m.start()]
            sentence_end_candidates = [norm.find(sep, m.end()) for sep in ".;:!?"]
            valid_ends = [pos for pos in sentence_end_candidates if pos != -1]
            sentence_end = min(valid_ends) if valid_ends else len(norm)
            sentence_suffix = norm[m.end():sentence_end].strip()

            is_neg = False
            for neg in _NEGACIONES_PRE:
                pos = _find_neg_bounded(sentence_prefix, neg)
                if pos != -1:
                    intervening = sentence_prefix[pos + len(neg):]
                    if not any(t in intervening for t in _AFFIRMATIVE_TRANSITIONS):
                        is_neg = True
                        break
            if is_neg:
                continue

            # Si el texto clinico carece completamente de cualquier marcador de lateralidad
            # (ej. "catarata senil nuclear"), el hallazgo es global/indeterminado y puede
            # comprometer a cualquiera de los dos ojos.
            if not has_any_laterality_marker:
                return True

            # Delimitar la clausula local entre separadores clinicos (.;|\n)
            clause_start = max([norm.rfind(sep, 0, m.start()) for sep in ".;|\n"] or [-1]) + 1
            clause_prefix = norm[clause_start:m.start()]
            ends = [pos for pos in [norm.find(sep, m.end()) for sep in ".;|\n"] if pos != -1]
            clause_end = min(ends) if ends else len(norm)
            clause_suffix = norm[m.end():clause_end]

            # 1. Marcador bilateral explicito en la clausula
            if _AO_MARKERS_RE.search(clause_prefix) or _AO_MARKERS_RE.search(clause_suffix[:30]):
                return True

            # 2. Marcador de ojo especifico en la clausula
            if target == "OD":
                has_target = bool(_OD_MARKERS_RE.search(clause_prefix) or _OD_MARKERS_RE.search(clause_suffix[:30]))
                has_contra = bool(_OI_MARKERS_RE.search(clause_prefix) or _OI_MARKERS_RE.search(clause_suffix[:30]))
            else:
                has_target = bool(_OI_MARKERS_RE.search(clause_prefix) or _OI_MARKERS_RE.search(clause_suffix[:30]))
                has_contra = bool(_OD_MARKERS_RE.search(clause_prefix) or _OD_MARKERS_RE.search(clause_suffix[:30]))

            if has_target and not has_contra:
                return True
            if has_contra and not has_target:
                continue

            # 3. Si no hay marcador en la clausula inmediata, buscar el marcador anterior mas cercano
            prev_markers = list(_EYE_MARKERS_EXPLICIT_RE.finditer(norm[:m.start()]))
            if prev_markers:
                last_marker = prev_markers[-1].group(1)
                if last_marker in ("ao", "ambos ojos", "bilateral", "bilaterales"):
                    return True
                if target == "OD" and last_marker in ("od", "ojo derecho"):
                    return True
                if target == "OI" and last_marker in ("oi", "ojo izquierdo"):
                    return True
                continue

            return True

    return False


# Categorias de causas con capacidad fisiopatologica demostrada para explicar
# una reduccion de agudeza visual central (<= 20/40).
_KEYWORDS_OPACIDADES_MEDIOS = _KEYWORDS_OPACIDAD_CRISTALINO + (
    "leucoma", "opacidad corneal", "edema corneal", "queratopatia bullosa", "nubecula",
    "hemorragia vitrea", "turbidez vitrea", "opacidad vitrea",
)

_KEYWORDS_MACULOPATIA_EXPLICATIVA = _KEYWORDS_FONDO_DMAE + _KEYWORDS_FONDO_MACULAR_OTROS

_KEYWORDS_NEUROPATIA_OPTICA_EXPLICATIVA = _KEYWORDS_PAPILA_NO_GLAUCOMA

_KEYWORDS_GLAUCOMA_PATOLOGICO = _KEYWORDS_ISNT_VIOLADA + tuple(
    f"{p}{s}{v}"
    for p in (
        "c/d", "cd", "cup/disc", "cup disc", "cup-disc", "e/p",
        "relacion c/d", "relacion cd",
        "relacion copa/disco", "relacion copa disco",
        "copa/disco", "copa disco",
    )
    for s in (" ", ": ", ":", " de ", " del ")
    for v in (
        "0.6", "0.7", "0.8", "0.9", "1.0",
        "0,6", "0,7", "0,8", "0,9", "1,0",
        "6/10", "7/10", "8/10", "9/10",
    )
) + (
    "relacion copa/disco aumentada", "copa/disco aumentada", "copa disco aumentada",
    "relacion c/d aumentada", "relacion cd aumentada",
    "relacion copa/disco amplia", "copa/disco amplia", "copa disco amplia", "relacion c/d amplia",
    "muesca", "escotadura", "notch",
    "hemorragia peripapilar", "hemorragia en astilla",
    "rima neural adelgazada", "anillo neurorretiniano adelgazado",
    "adelgazamiento del anillo", "adelgazamiento neurorretiniano",
    "neuropatia glaucomatosa", "glaucoma avanzado",
)

_KEYWORDS_VASCULARES_CENTRALES_EXPLICATIVAS = _KEYWORDS_FONDO_OCLUSION_VASCULAR + (
    "edema macular diabetico", "emq", "neovasos", "rubeosis",
    "retinopatia diabetica proliferativa", "rdp", "estrella macular",
)


def _ojo_tiene_causa_organica_explicativa(req: ImpresionClinicaRequest, eye: str) -> bool:
    """Determina si el ojo especificado ('OD' o 'OI') presenta una causa organica
    documentada con capacidad demostrada para explicar la perdida de agudeza visual
    central (<= 20/40).

    Causas con capacidad explicativa central demostrada:
    1. Opacidad de medios (cristalino, cornea, vitreo).
    2. Maculopatias (DMAE, MER, agujero macular, edema macular, CSCR).
    3. Neuropatia optica / alteracion papilar (papiledema, atrofia, neuritis,
       neuropatia glaucomatosa con excavacion patologica o regla ISNT violada).
    4. Oclusiones vasculares retinianas o retinopatia proliferativa/macular severa.

    Causas que NO explican la perdida central Snellen (no suprimen):
    - Lesiones de retina periferica (lattice, baba de caracol, desgarro periferico sin desprendimiento macular).
    - Sindromes pupilares o de motilidad (Horner, III par).
    - Astigmatismo lenticular compensado en prescripcion.
    - Sospecha queratometrica en AKR (3 mm).
    """
    clinica = req.clinica
    if clinica is None:
        return False
    target = eye.upper()
    if target not in ("OD", "OI"):
        return False

    # 1. Opacidad de medios (anexos o fondo)
    texto_medios = " ".join(filter(None, [clinica.anexos_oculares, clinica.fondo_de_ojo]))
    if _finding_applies_to_eye(texto_medios, _KEYWORDS_OPACIDADES_MEDIOS, target):
        return True

    # 2. Maculopatia
    if _finding_applies_to_eye(clinica.fondo_de_ojo, _KEYWORDS_MACULOPATIA_EXPLICATIVA, target):
        return True

    # 3. Neuropatia optica / papila no glaucoma
    if _finding_applies_to_eye(clinica.fondo_de_ojo, _KEYWORDS_NEUROPATIA_OPTICA_EXPLICATIVA, target):
        return True

    # 4. Neuropatia glaucomatosa
    if _finding_applies_to_eye(clinica.fondo_de_ojo, _KEYWORDS_GLAUCOMA_PATOLOGICO, target):
        return True

    # 5. Oclusiones vasculares y retinopatia central severa
    if _finding_applies_to_eye(clinica.fondo_de_ojo, _KEYWORDS_VASCULARES_CENTRALES_EXPLICATIVAS, target):
        return True

    return False


def _suprime_causa_organica(req: ImpresionClinicaRequest) -> bool:
    """Helper de compatibilidad legacy: retorna True si alguno de los ojos presenta
    una causa organica explicativa demostrada."""
    return _ojo_tiene_causa_organica_explicativa(req, "OD") or _ojo_tiene_causa_organica_explicativa(req, "OI")

# La adicion no rebasa este techo fisiologico en la practica optometrica; por
# encima conviene revisar la distancia de trabajo o la refraccion de lejos.
_ADD_TECHO_ABSOLUTO_D = 3.00
_KEYWORDS_TROPIA = ("endotropia", "exotropia", "hipertropia", "hipotropia")

_KEYWORDS_CVS = (
    "ardor ocular", "sequedad ocular", "ojo seco", "resequedad",
    "vision borrosa intermitente", "dolor ocular",
    "ardor", "sequedad", "arenilla", "cuerpo extrano", "cefalea",
    "picazon", "prurito", "comezon", "lagrimeo", "enrojecimiento",
    "fotofobia", "fatiga visual", "cansancio visual", "fatiga ocular",
    "dificultad para enfocar",
)
# Catalogo de tipo_lente del SaaS: monofocal, bifocal_blended, progresivo,
# flat_top. El flat_top ES un bifocal de segmento visible, por lo que cuenta
# como multifocal para presbicia. Los tokens cubren la clave canonica y las
# variantes de escritura libre legacy.
_MULTIFOCAL_TOKENS = ("bifocal", "progresivo", "multifocal", "flat_top", "flat-top", "flat top")


def _es_lente_multifocal(req: ImpresionClinicaRequest) -> bool:
    tipo = _normalize_text(req.tipo_lente)
    return any(token in tipo for token in _MULTIFOCAL_TOKENS)


def _cond_presbicia_multifocal(req: ImpresionClinicaRequest) -> bool:
    paciente = req.paciente
    refraccion = req.refraccion
    if paciente is None or refraccion is None:
        return False
    edad = paciente.edad
    # Jamas presbicia en menores de 40 anos (evita contradiccion con disfuncion acomodativa)
    if edad is not None and edad < 40:
        return False
    es_multifocal = _es_lente_multifocal(req)
    hay_edad = edad is not None and edad >= 40
    hay_add = refraccion.od.add is not None or refraccion.oi.add is not None
    return (es_multifocal and (hay_edad or hay_add)) or (hay_edad and hay_add)


def _texto_presbicia_multifocal(req: ImpresionClinicaRequest) -> str:
    edad = req.paciente.edad if req.paciente is not None else None
    refraccion = req.refraccion
    hay_add = refraccion is not None and (refraccion.od.add is not None or refraccion.oi.add is not None)
    sufijo_lente = " y el lente multifocal indicado" if _es_lente_multifocal(req) else ""
    if hay_add:
        justificacion = f"lo que justifica la adicion prescrita{sufijo_lente}"
    else:
        justificacion = "lo que justifica el diseno multifocal indicado" if _es_lente_multifocal(req) else "lo que sugiere evaluar la necesidad de adicion proxima"
    if edad is not None:
        return (
            f"El paciente de {edad} anos presenta reduccion fisiologica de la amplitud "
            f"acomodativa propia de la edad, {justificacion}."
        )
    return (
        f"Se documenta reduccion fisiologica de la amplitud acomodativa, {justificacion}."
    )


def _hay_refraccion_distancia(req: ImpresionClinicaRequest) -> bool:
    refraccion = req.refraccion
    if refraccion is None:
        return False
    return any(
        getattr(ojo, attr) is not None
        for ojo in (refraccion.od, refraccion.oi)
        for attr in ("esfera", "cilindro")
    )


def _ee_menos_miope(req: ImpresionClinicaRequest) -> float | None:
    """Equivalente esferico del ojo MENOS miope (el mayor EE) entre los que tienen
    dato. Es el que determina si el paciente puede leer quitandose los lentes."""
    refraccion = req.refraccion
    if refraccion is None:
        return None
    ees = [
        _equivalente_esferico(ojo.esfera, ojo.cilindro)
        for ojo in (refraccion.od, refraccion.oi)
    ]
    ees = [ee for ee in ees if ee is not None]
    return max(ees) if ees else None


def _cond_presbicia_sin_adicion(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: paciente en edad presbita con refraccion de distancia pero sin
    adicion prescrita ni lente multifocal; conviene verificar la vision proxima.

    No dispara en el miope funcional: un miope de EE <= -1.50 D en ambos ojos lee
    comodamente quitandose los lentes y no requiere adicion, de modo que la falta
    de add no es un olvido sino lo esperable.
    """
    paciente = req.paciente
    refraccion = req.refraccion
    if paciente is None or refraccion is None:
        return False
    edad = paciente.edad
    if edad is None or edad < 45:
        return False
    if refraccion.od.add is not None or refraccion.oi.add is not None:
        return False
    if _es_lente_multifocal(req):
        return False
    if not _hay_refraccion_distancia(req):
        return False
    ee = _ee_menos_miope(req)
    return ee is not None and ee > -1.50


def _texto_presbicia_sin_adicion(req: ImpresionClinicaRequest) -> str:
    edad = req.paciente.edad
    return (
        f"El paciente de {edad} anos no presenta adicion prescrita pese a encontrarse en el rango "
        "de edad con reduccion fisiologica de la amplitud acomodativa, por lo que conviene "
        "verificar la necesidad de correccion para vision proxima."
    )


def _add_maximo(req: ImpresionClinicaRequest) -> float | None:
    refraccion = req.refraccion
    if refraccion is None:
        return None
    adds = [ojo.add for ojo in (refraccion.od, refraccion.oi) if ojo.add is not None]
    return max(adds) if adds else None


def _add_esperado_max(edad: int) -> float:
    """Techo superior tipico de la adicion segun la edad."""
    if edad < 45:
        return 1.25
    if edad < 50:
        return 1.75
    if edad < 55:
        return 2.25
    if edad < 60:
        return 2.50
    return 3.00


_KEYWORDS_ASTENOPIA_JOVEN = (
    "astenopia", "fatiga", "cansancio", "dificultad para enfocar",
    "borrosa de cerca", "borroso al leer", "lectura", "cerca",
    "dolor ocular", "cefalea",
)


def _cond_insuficiencia_acomodacion_joven(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: paciente no presbita (< 38 anos) con adicion prescrita y astenopia
    o sintomas en vision proxima en el motivo de consulta, sugerente de insuficiencia
    o disfuncion acomodativa."""
    paciente = req.paciente
    if paciente is None:
        return False
    edad = paciente.edad
    if edad is None or edad >= 38:
        return False
    add = _add_maximo(req)
    if add is None or add < 0.75:
        return False
    return _contains_keyword(
        paciente.motivo_consulta,
        _KEYWORDS_ASTENOPIA_JOVEN,
        allow_negation_window=True,
    )


def _texto_insuficiencia_acomodacion_joven(req: ImpresionClinicaRequest) -> str:
    add = _add_maximo(req)
    edad = req.paciente.edad if req.paciente is not None else None
    edad_str = f" de {edad} anos" if edad is not None else ""
    return (
        f"El paciente{edad_str} presenta sintomatologia astenopica en vision cercana asociada a la "
        f"prescripcion de adicion (+{add:.2f}D), patron sugestivo de insuficiencia o disfuncion acomodativa; "
        "se recomienda evaluar la amplitud de acomodacion (metodo de Donders o Sheard) y la flexibilidad "
        "acomodativa con flippers antes de consolidar la adicion definitiva."
    )


def _cond_adicion_incongruente_edad(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: la adicion prescrita no es congruente con la edad (add en un no
    presbita, o add por encima del rango fisiologico esperado para la edad)."""
    if _cond_insuficiencia_acomodacion_joven(req):
        return False
    paciente = req.paciente
    if paciente is None:
        return False
    add = _add_maximo(req)
    if add is None:
        return False
    edad = paciente.edad
    if edad is None:
        return add > _ADD_TECHO_ABSOLUTO_D
    if edad < 40:
        return add >= 0.75
    return add > _ADD_TECHO_ABSOLUTO_D or add > _add_esperado_max(edad) + 0.50


def _texto_adicion_incongruente_edad(req: ImpresionClinicaRequest) -> str:
    add = _add_maximo(req)
    edad = req.paciente.edad
    if edad is not None and edad < 40:
        return (
            f"Se prescribe una adicion de +{add:.2f}D en un paciente de {edad} anos, edad en la que "
            "la amplitud acomodativa suele ser suficiente para la vision proxima; conviene verificar "
            "la indicacion (disfuncion acomodativa) o descartar una sobrecorreccion miopica de lejos."
        )
    contexto_edad = f"para la edad de {edad} anos" if edad is not None else "fisiologico habitual (mayor de +3.00 D)"
    return (
        f"La adicion prescrita (+{add:.2f}D) supera el rango {contexto_edad}; conviene verificar la "
        "distancia de trabajo y descartar una subcorreccion hipermetropica o una sobreestimacion de la "
        "refraccion de lejos."
    )


def _hay_tropia(req: ImpresionClinicaRequest) -> bool:
    clinica = req.clinica
    if clinica is None or not clinica.cover_test:
        return False
    tokens = _cover_desviaciones(clinica.cover_test)
    if any(keyword in tokens for keyword in _KEYWORDS_TROPIA):
        return True
    cover = _normalize_cover_text(clinica.cover_test)
    return any(_keyword_matches(cover, keyword, allow_negation_window=True) for keyword in _KEYWORDS_TROPIA)


def _ojo_av_limitada(req: ImpresionClinicaRequest):
    """(label, av_cc, av_sc) del primer ojo con AV con correccion limitada (preferentemente sin causa organica)."""
    refraccion = req.refraccion
    if refraccion is None:
        return None
    for label, ojo in (("OD", refraccion.od), ("OI", refraccion.oi)):
        if _av_es_limitada(ojo.av_cc) and not _ojo_tiene_causa_organica_explicativa(req, label):
            return label, ojo.av_cc, ojo.av_sc
    for label, ojo in (("OD", refraccion.od), ("OI", refraccion.oi)):
        if _av_es_limitada(ojo.av_cc):
            return label, ojo.av_cc, ojo.av_sc
    return None


@_memoize_cond
def _cond_ambliopia_sospecha(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: AV con correccion limitada + factor ambliogenico (anisometropia
    o desviacion manifiesta) sin causa organica documentada en ese ojo, patron sugestivo de
    ambliopia funcional. Usa av_sc/av_cc para caracterizar la respuesta a la Rx."""
    refraccion = req.refraccion
    if refraccion is None:
        return False

    ojos_limitados = []
    for label, ojo in (("OD", refraccion.od), ("OI", refraccion.oi)):
        if ojo and _av_es_limitada(ojo.av_cc):
            ojos_limitados.append(label)
    if not ojos_limitados:
        return False

    if not (_cond_anisometropia(req) or _hay_tropia(req)):
        return False

    # Si todos los ojos con deficit visual presentan una causa organica explicativa
    # demostrada en ese ojo (ej. catarata u atrofia optica), el deficit es organico.
    if all(_ojo_tiene_causa_organica_explicativa(req, eye) for eye in ojos_limitados):
        return False

    return True


def _texto_ambliopia_sospecha(req: ImpresionClinicaRequest) -> str:
    ojo_info = _ojo_av_limitada(req)
    if ojo_info is not None:
        label, av_cc, av_sc = ojo_info
        detalle = f"{label} ({av_cc})"
        if av_sc is not None:
            detalle += f", con agudeza visual sin correccion de {av_sc}"
    else:
        detalle = "el ojo afectado"
    factor = "anisometropia significativa" if _cond_anisometropia(req) else "una desviacion ocular manifiesta"
    return (
        f"Se documenta agudeza visual con correccion limitada en {detalle} en presencia de {factor}, "
        "patron sugestivo de ambliopia; amerita verificar el antecedente de ambliopia y la fijacion, "
        "y descartar una causa organica no evidente en el examen actual."
    )


@_memoize_cond
def _cond_ambliopia_isoametropica_bilateral(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: paciente menor de 18 anos con AV reducida bilateral (<=20/30 en AO)
    y alta ametropia bilateral simetrica sin causa organica ni factor anisometropico/estrabico."""
    if req.refraccion is None or req.paciente is None or req.paciente.edad is None:
        return False
    if req.paciente.edad >= 18:
        return False
    od = req.refraccion.od
    oi = req.refraccion.oi
    if not (_av_es_limitada(od.av_cc) and _av_es_limitada(oi.av_cc)):
        return False
    if _cond_anisometropia(req) or _hay_tropia(req):
        return False
    if _ojo_tiene_causa_organica_explicativa(req, "OD") or _ojo_tiene_causa_organica_explicativa(req, "OI"):
        return False
    ambos_hiper = (od.esfera is not None and od.esfera >= 4.00) and (oi.esfera is not None and oi.esfera >= 4.00)
    ambos_astig = (od.cilindro is not None and od.cilindro <= -2.50) and (oi.cilindro is not None and oi.cilindro <= -2.50)
    return ambos_hiper or ambos_astig


def _texto_ambliopia_isoametropica_bilateral(req: ImpresionClinicaRequest) -> str:
    od = req.refraccion.od
    oi = req.refraccion.oi
    edad = req.paciente.edad
    return (
        f"En paciente de {edad} anos con agudeza visual corregida bilateralmente limitada "
        f"(OD {od.av_cc}, OI {oi.av_cc}) asociada a alta ametropia simetrica en ausencia de patologia organica, "
        "el cuadro orienta a sospecha de ambliopia isoametropica (bilateral refractiva), ameritando prescripcion "
        "optica total y valoracion de terapia visual de estimulacion."
    )


def _cond_cvs_sospecha(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: pantallas y ardor o cefalea sugieren sindrome visual informatico."""
    if req.clinica is None or req.paciente is None:
        return False
    if req.clinica.uso_pantallas not in ("btw2_6", "gt6"):
        return False
    return _contains_keyword(req.paciente.motivo_consulta, _KEYWORDS_CVS, allow_negation_window=True)


_texto_cvs_sospecha = (
    "El perfil de uso de pantallas se correlaciona con la sintomatologia visual "
    "referida, sugestiva de fatiga visual digital / sindrome visual informatico, ameritando recomendaciones "
    "ergonomicas y eventual correccion optica para vision intermedia."
)


def _ojos_deficit_inexplicado(req: ImpresionClinicaRequest) -> list[tuple[str, str, str | None]]:
    """(label, av_cc, av_sc) de todos los ojos con:
    - refraccion prescrita (esfera o cilindro no nulos),
    - AV c/c subnormal (denominador >= 40, i.e. 20/40 o peor),
    - AV s/c no contradictoria (si existe dato, denominador >= 50),
    - y sin causa organica explicativa demostrada para ese ojo.
    """
    refraccion = req.refraccion
    if refraccion is None:
        return []
    ojos = []
    for label, ojo in (("OD", refraccion.od), ("OI", refraccion.oi)):
        if ojo.esfera is None and ojo.cilindro is None:
            continue
        denom_cc = _av_denominator(ojo.av_cc)
        if denom_cc is None or denom_cc < 40:
            continue
        denom_sc = _av_denominator(ojo.av_sc)
        if denom_sc is not None and denom_sc < 50:
            continue
        if _ojo_tiene_causa_organica_explicativa(req, label):
            continue
        ojos.append((label, ojo.av_cc, ojo.av_sc))
    return ojos


def _ojo_deficit_inexplicado(req: ImpresionClinicaRequest):
    """Compatibilidad: tupla (label, av_cc, av_sc) del primer ojo inexplicado, o None."""
    ojos = _ojos_deficit_inexplicado(req)
    return ojos[0] if ojos else None


@_memoize_cond
def _cond_deficit_visual_inexplicado_refractivo(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: reduccion de agudeza visual con correccion (<= 20/40) en paciente
    no senil (< 60 anos o edad no especificada) en ausencia de causa organica documentada
    en ese ojo o factor ambliogenico (anisometropia/estrabismo). Sugiere patologia subclinica,
    astigmatismo irregular o defecto refractivo no corregido que amerita estenopeico
    o ciclopejia."""
    if req.refraccion is None:
        return False
    if req.paciente is not None and req.paciente.edad is not None and req.paciente.edad >= 60:
        return False
    if not _ojos_deficit_inexplicado(req):
        return False
    if _cond_ambliopia_sospecha(req) or _cond_ambliopia_isoametropica_bilateral(req):
        return False
    return True


def _texto_deficit_visual_inexplicado_refractivo(req: ImpresionClinicaRequest) -> str:
    ojos = _ojos_deficit_inexplicado(req)
    if not ojos:
        ojo_info = _ojo_deficit_inexplicado(req)
        ojos = [ojo_info] if ojo_info is not None else []

    if len(ojos) == 1:
        label, av_cc, av_sc = ojos[0]
        sc_detalle = f" (AV sin correccion {av_sc})" if av_sc is not None else ""
        detalle = f"en {label} con correccion ({av_cc}){sc_detalle}"
    elif len(ojos) > 1:
        partes = []
        for label, av_cc, av_sc in ojos:
            sc_detalle = f" (AV sin correccion {av_sc})" if av_sc is not None else ""
            partes.append(f"{label} ({av_cc}){sc_detalle}")
        detalle = f"en {' y '.join(partes)} con correccion"
    else:
        detalle = "con correccion"

    return (
        f"Se registra agudeza visual subnormal {detalle} al no constar una causa organica evidente en los datos "
        "disponibles ni factores ambliogenicos manifiestos; se recomienda prueba con agujero estenopeico, "
        "reevaluar refraccion bajo ciclopejia o descartar patologia corneal o macular subclinica."
    )


def _cond_adulto_mayor_screening(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: adulto mayor con AV corregida reducida amerita descarte dirigido."""
    if req.paciente is None or req.refraccion is None:
        return False
    edad = req.paciente.edad
    if edad is None or edad < 60:
        return False

    ojos_limitados = []
    for label, ojo in (("OD", req.refraccion.od), ("OI", req.refraccion.oi)):
        if ojo and _av_es_limitada(ojo.av_cc):
            ojos_limitados.append(label)
    if not ojos_limitados:
        return False

    # Si todos los ojos que presentan deficit visual ya tienen una causa organica explicativa
    # documentada en ese ojo, el screening general ("sin causa identificada") no procede.
    if all(_ojo_tiene_causa_organica_explicativa(req, eye) for eye in ojos_limitados):
        return False

    return not (
        _cond_ambliopia_sospecha(req)
        or _cond_ambliopia_isoametropica_bilateral(req)
        or _cond_deficit_visual_inexplicado_refractivo(req)
    )


def _texto_adulto_mayor_screening(req: ImpresionClinicaRequest) -> str:
    edad = req.paciente.edad
    return (
        f"En paciente de {edad} anos con reduccion de agudeza visual sin causa identificada en "
        "los datos disponibles, se recomienda descarte activo de catarata, glaucoma y "
        "maculopatia asociada a la edad mediante exploracion dirigida."
    )

