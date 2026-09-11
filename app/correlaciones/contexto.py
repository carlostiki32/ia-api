"""Dominio: edad, lente, motivo y agudeza (8 correlaciones).

presbicia_multifocal, presbicia_sin_adicion, adicion_incongruente_edad,
insuficiencia_acomodacion_joven, cvs_sospecha, ambliopia_sospecha,
deficit_visual_inexplicado_refractivo y adulto_mayor_screening. Las redes de
seguridad solo disparan si no hay ya una causa organica documentada que
explique la reduccion visual (de ahi los imports de otros dominios).
"""
from __future__ import annotations

from app.correlaciones.base import _memoize_cond
from app.correlaciones.anexos_cristalino import _cond_opacidad_cristaliniana
from app.correlaciones.corneal import _cond_astigmatismo_lenticular_puro
from app.correlaciones.fondo_de_ojo import (
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
    _contains_keyword,
    _normalize_cover_text,
    _normalize_text,
)
from app.schemas import ImpresionClinicaRequest

# Causas organicas que, si estan documentadas, explican la baja de agudeza y
# suprimen las redes de seguridad (screening del adulto mayor, sospecha de
# ambliopia): en ese caso el mensaje generico seria redundante o enganoso.
# NOTA CLINICA: La miopia magna es factor de riesgo (catarata, glaucoma, maculopatia miopica)
# y NO una causa organica que deba silenciar el screening del adulto mayor.
def _suprime_causa_organica(req: ImpresionClinicaRequest) -> bool:
    return any(
        cond(req) for cond in (
            _cond_opacidad_cristaliniana,
            _cond_fondo_periferico_riesgo,
            _cond_fondo_oclusion_vascular_urgente,
            _cond_fondo_glaucomatoso,
            _cond_glaucoma_asimetrico,
            _cond_isnt_violada_papila,
            _cond_fondo_macular_dmae,
            _cond_fondo_macular_otros,
            _cond_fondo_vascular_diabetico,
            _cond_fondo_hipertensivo,
            _cond_papila_patologica,
            _cond_horner_o_tercer_par_sospecha,
            _cond_astigmatismo_lenticular_puro,
            _req_has_corneal_irregularity,
        )
    )

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
    return _contains_keyword(paciente.motivo_consulta, _KEYWORDS_ASTENOPIA_JOVEN)


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
    cover = _normalize_cover_text(clinica.cover_test if clinica is not None else None)
    return any(keyword in cover for keyword in _KEYWORDS_TROPIA)


def _ojo_av_limitada(req: ImpresionClinicaRequest):
    """(label, av_cc, av_sc) del primer ojo con AV con correccion limitada."""
    refraccion = req.refraccion
    for label, ojo in (("OD", refraccion.od), ("OI", refraccion.oi)):
        if _av_es_limitada(ojo.av_cc):
            return label, ojo.av_cc, ojo.av_sc
    return None


@_memoize_cond
def _cond_ambliopia_sospecha(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: AV con correccion limitada + factor ambliogenico (anisometropia
    o desviacion manifiesta) sin causa organica documentada, patron sugestivo de
    ambliopia funcional. Usa av_sc/av_cc para caracterizar la respuesta a la Rx."""
    refraccion = req.refraccion
    if refraccion is None:
        return False
    if not (_av_es_limitada(refraccion.od.av_cc) or _av_es_limitada(refraccion.oi.av_cc)):
        return False
    if not (_cond_anisometropia(req) or _hay_tropia(req)):
        return False
    return not _suprime_causa_organica(req)


def _texto_ambliopia_sospecha(req: ImpresionClinicaRequest) -> str:
    label, av_cc, av_sc = _ojo_av_limitada(req)
    factor = "anisometropia significativa" if _cond_anisometropia(req) else "una desviacion ocular manifiesta"
    detalle = f"{label} ({av_cc})"
    if av_sc is not None:
        detalle += f", con agudeza visual sin correccion de {av_sc}"
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
    if _suprime_causa_organica(req):
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
    return _contains_keyword(req.paciente.motivo_consulta, _KEYWORDS_CVS)


_texto_cvs_sospecha = (
    "El perfil de uso de pantallas se correlaciona con la sintomatologia visual "
    "referida, sugestiva de fatiga visual digital / sindrome visual informatico, ameritando recomendaciones "
    "ergonomicas y eventual correccion optica para vision intermedia."
)


def _ojo_deficit_inexplicado(req: ImpresionClinicaRequest):
    """(label, av_cc, av_sc) del primer ojo con:
    - refraccion prescrita (esfera o cilindro no nulos),
    - AV c/c subnormal (denominador >= 40, i.e. 20/40 o peor),
    - AV s/c no contradictoria (si existe dato, denominador >= 50).
    """
    refraccion = req.refraccion
    if refraccion is None:
        return None
    for label, ojo in (("OD", refraccion.od), ("OI", refraccion.oi)):
        if ojo.esfera is None and ojo.cilindro is None:
            continue
        denom_cc = _av_denominator(ojo.av_cc)
        if denom_cc is None or denom_cc < 40:
            continue
        denom_sc = _av_denominator(ojo.av_sc)
        if denom_sc is not None and denom_sc < 50:
            continue
        return label, ojo.av_cc, ojo.av_sc
    return None


@_memoize_cond
def _cond_deficit_visual_inexplicado_refractivo(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: reduccion de agudeza visual con correccion (<= 20/40) en paciente
    no senil (< 60 anos o edad no especificada) en ausencia de causa organica documentada
    o factor ambliogenico (anisometropia/estrabismo). Sugiere patologia subclinica,
    astigmatismo irregular o defecto refractivo no corregido que amerita estenopeico
    o ciclopejia."""
    if req.refraccion is None:
        return False
    if req.paciente is not None and req.paciente.edad is not None and req.paciente.edad >= 60:
        return False
    if _ojo_deficit_inexplicado(req) is None:
        return False
    if _cond_ambliopia_sospecha(req) or _cond_ambliopia_isoametropica_bilateral(req):
        return False
    return not _suprime_causa_organica(req)


def _texto_deficit_visual_inexplicado_refractivo(req: ImpresionClinicaRequest) -> str:
    ojo_info = _ojo_deficit_inexplicado(req)
    if ojo_info is not None:
        label, av_cc, av_sc = ojo_info
        sc_detalle = f" (AV sin correccion {av_sc})" if av_sc is not None else ""
        detalle = f"en {label} con correccion ({av_cc}){sc_detalle}"
    else:
        detalle = "con la mejor correccion optica"
    return (
        f"Se registra agudeza visual subnormal {detalle} sin hallazgos organicos evidentes en el examen "
        "actual ni factores ambliogenicos manifiestos; se recomienda prueba con agujero estenopeico, "
        "reevaluar refraccion bajo ciclopejia o descartar patologia corneal o macular subclinica."
    )


def _cond_adulto_mayor_screening(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: adulto mayor con AV corregida reducida amerita descarte dirigido."""
    if req.paciente is None or req.refraccion is None:
        return False
    edad = req.paciente.edad
    if edad is None or edad < 60:
        return False
    if not (_av_es_limitada(req.refraccion.od.av_cc) or _av_es_limitada(req.refraccion.oi.av_cc)):
        return False
    return not (
        _suprime_causa_organica(req)
        or _cond_ambliopia_sospecha(req)
        or _cond_ambliopia_isoametropica_bilateral(req)
        or _cond_deficit_visual_inexplicado_refractivo(req)
    )


def _texto_adulto_mayor_screening(req: ImpresionClinicaRequest) -> str:
    edad = req.paciente.edad
    return (
        f"En paciente de {edad} anos con reduccion de agudeza visual sin causa "
        "identificada en el examen actual, se recomienda descarte activo de catarata, "
        "glaucoma y maculopatia asociada a la edad mediante exploracion dirigida."
    )

