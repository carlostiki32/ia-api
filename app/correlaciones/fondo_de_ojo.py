"""Dominio: fondo de ojo (8 correlaciones).

fondo_periferico_riesgo, glaucoma_asimetrico, fondo_glaucomatoso,
papila_patologica, fondo_macular_dmae, fondo_macular_otros, fondo_hipertensivo,
fondo_vascular_diabetico. Todas leen `clinica.fondo_de_ojo` con ventana de
negacion por oracion; la jerarquia de supresion se resuelve dentro del dominio.
"""
from __future__ import annotations

from app.correlaciones.base import _memoize_cond
from app.correlaciones.texto import (
    _extract_normalized_findings,
    _fondo_contains,
    _join_hallazgos,
    _keyword_matches,
    _normalize_text,
)
from app.schemas import ImpresionClinicaRequest

_KEYWORDS_VASCULARES_DIABETICOS = (
    "microaneurisma", "microaneurismas",
    "exudado", "exudados", "exudados duros", "exudado duro",
    "exudados lipidicos", "exudado lipidico",
    "hemorragia retiniana", "hemorragia intraretin", "hemorragia intrarretin",
    "hemorragia en mancha", "hemorragia puntiforme", "hemorragia en punto",
    "neovas", "rubeosis",
    "retinopatia diabetica", "rdnp", "rdp",
    "arrosariamiento", "rosario venoso", "arrosariamiento venoso", "irma",
)
_KEYWORDS_FONDO_GLAUCOMATOSO = (
    "c/d 0.6", "c/d 0.7", "c/d 0.8", "c/d 0.9", "c/d 1.0",
    "cup/disc 0.6", "cup/disc 0.7", "cup/disc 0.8", "cup/disc 0.9", "cup/disc 1.0",
    "e/p 0.6", "e/p 0.7", "e/p 0.8", "e/p 0.9", "e/p 1.0",
    "cd 0.6", "cd 0.7", "cd 0.8", "cd 0.9", "cd 1.0",
    "c/d 0,6", "c/d 0,7", "c/d 0,8", "c/d 0,9", "c/d 1,0",
    "e/p 0,6", "e/p 0,7", "e/p 0,8", "e/p 0,9", "e/p 1,0",
    "excavacion", "excavada", "excavado", "papila asimetrica", "asimetria c/d",
    "asimetria de la excavacion", "muesca", "escotadura", "notch",
    "hemorragia peripapilar", "hemorragia en astilla",
    "rima neural adelgazada", "anillo neurorretiniano adelgazado",
    "adelgazamiento del anillo", "adelgazamiento neurorretiniano",
    "violacion de la regla isnt", "violacion isnt", "isnt violada",
)
_KEYWORDS_ISNT_VIOLADA = (
    "isnt violada", "violacion isnt", "violacion de la regla isnt",
    "regla isnt no se cumple", "anillo temporal mas grueso",
    "muesca inferior", "notch inferior", "escotadura inferior",
    "muesca superior", "notch superior", "escotadura superior",
)


def _es_excavacion_fisiologica_pura(fondo_norm: str) -> bool:
    """Descarta excavacion normal/fisiologica (0.1, 0.2, 0.3, 0.4, 0.5 o calificada de fisiologica)
    cuando no hay signos glaucomatosos patologicos asociados."""
    tokens_patologicos = (
        "0.6", "0.7", "0.8", "0.9", "1.0", "0,6", "0,7", "0,8", "0,9", "1,0",
        "asimetr", "muesca", "notch", "astilla", "adelgaz", "violacion", "aumentad",
    )
    if any(p in fondo_norm for p in tokens_patologicos):
        return False
    return any(b in fondo_norm for b in ("0.1", "0.2", "0.3", "0.4", "0.5", "fisiologic", "normal"))
_KEYWORDS_FONDO_DMAE = (
    "drusas", "drusa", "drusen", "alteracion pigmentaria", "cambios pigmentarios",
    "alteracion del epr", "atrofia del epr", "hiperplasia del epr",
    "atrofia geografica", "membrana neovascular", "membrana neovascular coroidea",
    "neovascularizacion coroidea", "mnvc", "cnv", "mev",
    "epiteliopatia", "dmae", "dmre", "degeneracion macular",
    "maculopatia relacionada con la edad", "maculopatia senil",
)
_KEYWORDS_PAPILA_EMERGENCIA = (
    "papiledema", "edema de papila", "edema papilar", "edema del disco",
    "papila edematosa", "disco edematoso",
    "borramiento de bordes", "borramiento de los bordes",
    "bordes borrosos", "bordes difuminados", "bordes mal definidos",
    "margenes borrosos", "limites borrosos",
)
_KEYWORDS_PAPILA_NO_GLAUCOMA = (
    "palidez papilar", "palidez de papila", "papila palida", "disco palido",
    "atrofia optica", "atrofia papilar", "atrofia del nervio optico",
    "neuritis optica", "neuropatia optica",
) + _KEYWORDS_PAPILA_EMERGENCIA
_KEYWORDS_FONDO_MACULAR_OTROS = (
    "edema macular", "membrana epirretiniana", "membrana epiretiniana", "mer",
    "gliosis macular", "gliosis premacular", "pucker",
    "traccion vitreomacular", "agujero macular", "quiste macular",
    "coroidopatia serosa", "corioretinopatia serosa", "coriorretinopatia serosa",
    "crsc", "cscr", "emq",
)
_KEYWORDS_FONDO_HIPERTENSIVO = (
    "cruces arteriovenosos", "cruces av",
    "cruce arteriovenoso", "cruce av", "signo de gunn", "signo de salus",
    "signo de bonnet", "estrechamiento arterial", "estrechamiento arteriolar",
    "adelgazamiento arteriolar", "relacion a/v disminuida",
    "hilos de cobre", "hilos de plata", "alambre de cobre", "alambre de plata",
    "algodonoso", "cotton wool", "salus",
    "ingurgitacion venosa", "hemorragia en llama", "hemorragia en flama",
    "retinopatia hipertensiva",
)
_KEYWORDS_FONDO_PERIFERICO_MAP = {
    "desgarro": "desgarro retiniano",
    "rotura retiniana": "desgarro retiniano",
    "ruptura retiniana": "desgarro retiniano",
    "dialisis retiniana": "dialisis retiniana",
    "agujero retiniano": "agujero retiniano",
    "agujero atrofico": "agujero atrofico",
    "agujero operculado": "agujero operculado",
    "lattice": "degeneracion lattice",
    "degeneracion reticular": "degeneracion reticular",
    "degeneracion en empalizada": "degeneracion lattice",
    "empalizada": "degeneracion lattice",
    "palizada": "degeneracion lattice",
    "baba de caracol": "degeneracion en baba de caracol",
    "huella de caracol": "degeneracion en baba de caracol",
    "blanco con presion": "blanco con presion",
    "desprendimiento de retina": "desprendimiento de retina",
    "desprendimiento regmatogeno": "desprendimiento de retina",
    "desprendimiento neurosensorial": "desprendimiento de retina",
    "schisis": "schisis periferica",
    "retinosquisis": "retinosquisis",
}
_KEYWORDS_FONDO_PERIFERICO = tuple(_KEYWORDS_FONDO_PERIFERICO_MAP)


@_memoize_cond
def _cond_fondo_periferico_riesgo(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: fondo con lattice o desgarro periferico activa urgencia retinologica."""
    if req.clinica is None or req.clinica.fondo_de_ojo is None:
        return False
    fondo = _normalize_text(req.clinica.fondo_de_ojo)
    # Excluir DVP (vitreo) y DEP (epitelio pigmentario macular) si no hay hallazgos de retina periferica
    if "desprendimiento" in fondo and not any(k in fondo for k in ("desprendimiento de retina", "desprendimiento regmatogeno", "desprendimiento neurosensorial")):
        if any(v in fondo for v in ("vitreo", "epitelio pigmentario", "dep", "dvp")):
            otros_perifericos = tuple(k for k in _KEYWORDS_FONDO_PERIFERICO if "desprendimiento" not in k)
            return any(_keyword_matches(fondo, k, allow_negation_window=True) for k in otros_perifericos)
    return _fondo_contains(req, _KEYWORDS_FONDO_PERIFERICO)


def _texto_fondo_periferico_riesgo(req: ImpresionClinicaRequest) -> str:
    hallazgos = _extract_normalized_findings(
        req.clinica.fondo_de_ojo if req.clinica is not None else None,
        _KEYWORDS_FONDO_PERIFERICO_MAP,
        allow_negation_window=True,
    )
    hallazgo = _join_hallazgos(hallazgos) if hallazgos else "hallazgo periferico de riesgo"
    fondo_text = _normalize_text(req.clinica.fondo_de_ojo if req.clinica is not None else None)
    es_rotura_o_desgarro = any(
        _keyword_matches(fondo_text, k, allow_negation_window=True)
        for k in (
            "desgarro", "rotura", "ruptura", "dialisis", "agujero operculado",
            "desprendimiento de retina", "desprendimiento regmatogeno",
        )
    )
    if es_rotura_o_desgarro:
        return (
            f"Hallazgo urgente: en la retina periferica se documenta {hallazgo}, que amerita "
            "valoracion retinologica urgente y posible tratamiento profilactico."
        )
    return (
        f"En la retina periferica se documenta {hallazgo}, que amerita seguimiento retinologico "
        "preventivo y educacion sobre sintomas de alarma (fotopsias y miodesopsias)."
    )


@_memoize_cond
def _cond_glaucoma_asimetrico(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: DPAR + fondo glaucomatoso confirman neuropatia optica glaucomatosa asimetrica con compromiso funcional."""
    if req.clinica is None:
        return False
    txt_pupilas = _normalize_text(req.clinica.reflejos_pupilares)
    hay_dpar = any(
        _keyword_matches(txt_pupilas, k, allow_negation_window=True)
        for k in ("dpar", "rapd", "marcus gunn", "defecto pupilar aferente")
    )
    if not hay_dpar:
        return False
    return _fondo_contains(req, _KEYWORDS_FONDO_GLAUCOMATOSO)


_texto_glaucoma_asimetrico = (
    "Hallazgo urgente: se documenta excavacion papilar aumentada con defecto pupilar "
    "aferente relativo, lo que indica compromiso asimetrico del nervio optico con "
    "probable repercusion funcional, ameritando valoracion oftalmologica priorizada."
)


@_memoize_cond
def _cond_fondo_glaucomatoso(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: excavacion aumentada o notch papilar activa sospecha glaucomatosa."""
    if _cond_glaucoma_asimetrico(req) or _cond_isnt_violada_papila(req):
        return False
    if req.clinica is not None and req.clinica.fondo_de_ojo is not None:
        texto = _normalize_text(req.clinica.fondo_de_ojo)
        if _es_excavacion_fisiologica_pura(texto):
            return False
    return _fondo_contains(req, _KEYWORDS_FONDO_GLAUCOMATOSO)


_texto_fondo_glaucomatoso = (
    "Se documentan hallazgos papilares con excavacion aumentada y/o alteracion "
    "del anillo neurorretiniano, ameritando valoracion oftalmologica con "
    "tonometria y perimetria para descarte de glaucoma."
)


@_memoize_cond
def _cond_isnt_violada_papila(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: violacion de la regla ISNT o muesca papilar focal indica dano glaucomatoso temprano."""
    if _cond_glaucoma_asimetrico(req):
        return False
    return _fondo_contains(req, _KEYWORDS_ISNT_VIOLADA)


_texto_isnt_violada_papila = (
    "Se documenta alteracion focal del anillo neurorretiniano con violacion de la regla ISNT "
    "en la papila optica, hallazgo sugestivo de neuropatia glaucomatosa inicial que amerita "
    "tonometria y perimetria priorizada."
)


@_memoize_cond
def _cond_papila_patologica(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: palidez, edema o neuritis papilar activan alerta neurooftalmica."""
    return _fondo_contains(req, _KEYWORDS_PAPILA_NO_GLAUCOMA)


def _texto_papila_patologica(req: ImpresionClinicaRequest) -> str:
    fondo = _normalize_text(req.clinica.fondo_de_ojo if req.clinica is not None else None)
    if "pseudopapiledema" in fondo and not any(k in fondo for k in ("edema real", "hipertension intracraneal")):
        es_emergencia = False
    else:
        es_emergencia = any(
            _keyword_matches(fondo, token, allow_negation_window=True)
            for token in _KEYWORDS_PAPILA_EMERGENCIA
        )
    if es_emergencia:
        return (
            "Hallazgo urgente: los hallazgos del nervio optico documentados son compatibles "
            "con edema de papila, lo que amerita evaluacion neurooftalmologica urgente para "
            "descarte de hipertension intracraneal."
        )
    return (
        "Se documenta alteracion del nervio optico no asociada a excavacion glaucomatosa, "
        "ameritando valoracion neurooftalmologica para caracterizacion etiologica."
    )


_EXCLUSIONES_DRUSAS_NO_MACULARES = (
    "drusas de papila", "drusas papilar", "drusas papilares",
    "drusas del disco", "drusa de papila", "drusa del disco",
    "drusas en papila", "drusas del nervio optico", "drusas de nervio optico",
    "drusas en nervio optico", "drusas peripapilares", "drusa peripapilar",
)
_DRUSAS_MACULARES_EXPLICITAS = (
    "drusas maculares", "drusa macular", "drusas en macula", "drusa en macula",
    "drusas paramaculares", "drusa paramacular", "drusas blandas", "drusa blanda",
    "drusas duras", "drusa dura",
)


@_memoize_cond
def _cond_fondo_macular_dmae(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: drusas o alteracion del EPR en fondo sugieren patron de DMAE."""
    if not _fondo_contains(req, _KEYWORDS_FONDO_DMAE):
        return False
    fondo = _normalize_text(req.clinica.fondo_de_ojo if req.clinica is not None else None)
    if any(dp in fondo for dp in _EXCLUSIONES_DRUSAS_NO_MACULARES):
        # Si hay drusas maculares explicitas ademas de drusas del disco/papila, se conserva DMAE
        if any(_keyword_matches(fondo, dm, allow_negation_window=True) for dm in _DRUSAS_MACULARES_EXPLICITAS):
            return True
        otros_dmae = [k for k in _KEYWORDS_FONDO_DMAE if not k.startswith("drus")]
        return any(_keyword_matches(fondo, k, allow_negation_window=True) for k in otros_dmae)
    return True


_texto_fondo_macular_dmae = (
    "Se documentan hallazgos maculares degenerativos en fondo de ojo, ameritando "
    "OCT macular para caracterizacion y monitorizacion."
)


@_memoize_cond
def _cond_fondo_macular_otros(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: edema macular o MER en fondo activa correlacion macular no DMAE."""
    return _fondo_contains(req, _KEYWORDS_FONDO_MACULAR_OTROS)


_texto_fondo_macular_otros = (
    "En la region macular se documenta alteracion estructural que amerita OCT y "
    "valoracion retinologica."
)


@_memoize_cond
def _cond_fondo_hipertensivo(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: cruces AV o signos de retinopatia hipertensiva."""
    return _fondo_contains(req, _KEYWORDS_FONDO_HIPERTENSIVO)


_texto_fondo_hipertensivo = (
    "Se documentan hallazgos vasculares en fondo de ojo con alteraciones "
    "arteriovenosas, ameritando correlacion con cifras tensionales sistemicas."
)


@_memoize_cond
def _cond_fondo_vascular_diabetico(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: microaneurismas o exudados activan correlacion vascular metabolica.

    No se suprime ante patologias maculares, perifericas o glaucomatosas: la retinopatia
    diabetica es una manifestacion microvascular sistemica que exige correlacion
    metabolica (control glucemico) con total independencia de otras patologias oculares.
    """
    if not _fondo_contains(req, _KEYWORDS_VASCULARES_DIABETICOS):
        return False
    fondo = _normalize_text(req.clinica.fondo_de_ojo if req.clinica is not None else None)
    # Exudado algodonoso aislado corresponde a infarto de fibras nerviosas (isquemia/HTA), no a retinopatia diabetica
    if "algodonoso" in fondo:
        otros_diabeticos = (
            "microaneurisma", "hemorragia en mancha", "hemorragia puntiforme",
            "hemorragia en punto", "neovas", "rubeosis", "retinopatia diabetica",
            "rdnp", "rdp", "arrosariamiento", "rosario venoso", "irma",
            "exudado duro", "exudados duros", "exudado lipidico", "exudados lipidicos",
        )
        return any(_keyword_matches(fondo, k, allow_negation_window=True) for k in otros_diabeticos)
    return True


_texto_fondo_vascular_diabetico = (
    "Se documentan hallazgos vasculares en fondo de ojo con presencia de "
    "alteraciones microvasculares, ameritando correlacion sistemica (control "
    "glucemico) y valoracion retinologica."
)


_KEYWORDS_FONDO_OCLUSION_VASCULAR = (
    "ovcr", "oacr", "obvr", "obar", "crvo", "crao", "brvo", "brao",
    "oclusion venosa", "oclusion arterial",
    "trombosis venosa", "trombosis retiniana", "trombosis de rama",
    "trombosis de vena central", "trombosis de arteria",
    "trombosis venosa retiniana", "trombosis de rama venosa",
    "embolia retiniana", "embolia de arteria retiniana", "infarto retiniano",
    "mancha rojo cereza", "mancha cereza", "cherry red",
    "oclusion de rama venosa", "oclusion de rama arterial",
    "oclusion de vena central", "oclusion de arteria central",
)


@_memoize_cond
def _cond_fondo_oclusion_vascular_urgente(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: sospecha o confirmacion de oclusion vascular retiniana (emergencia oftalmologica)."""
    return _fondo_contains(req, _KEYWORDS_FONDO_OCLUSION_VASCULAR)


_texto_fondo_oclusion_vascular_urgente = (
    "Hallazgo urgente: los hallazgos en fondo de ojo son compatibles con oclusion vascular retiniana "
    "(arterial o venosa), emergencia oftalmologica que amerita valoracion retinologica urgente y "
    "descarte sistemico cardiovascular y tromboembolico prioritario."
)


_KEYWORDS_SINTOMAS_TRACCION = (
    "fotopsias", "fotopsia", "flashes", "centelleos", "luces intermitentes",
    "destellos", "destello", "relampagos", "relampago",
    "miodesopsias agudas", "miodesopsias de aparicion subita", "lluvia de manchas",
    "moscas volantes", "mosca volante", "telaranas", "telarana",
    "manchas negras flotantes", "puntos negros flotantes", "cuerpos flotantes",
    "anillo de weiss",
)


@_memoize_cond
def _cond_sintomas_alarma_traccion_vitreoretina(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: fotopsias y miodesopsias agudas sugieren traccion vitreorretiniana en evolucion."""
    if _cond_fondo_periferico_riesgo(req):
        return False
    textos = []
    if req.paciente is not None and req.paciente.motivo_consulta:
        textos.append(req.paciente.motivo_consulta)
    if req.clinica is not None and req.clinica.fondo_de_ojo:
        textos.append(req.clinica.fondo_de_ojo)
    if not textos:
        return False
    combinado = _normalize_text(" ".join(textos))
    return any(_keyword_matches(combinado, k, allow_negation_window=True) for k in _KEYWORDS_SINTOMAS_TRACCION)


_texto_sintomas_alarma_traccion_vitreoretina = (
    "La presencia de fotopsias y/o miodesopsias agudas sugiere traccion vitreorretiniana "
    "en el contexto de desprendimiento de vitreo posterior en evolucion, ameritando examen "
    "bajo midriasis de la retina periferica con lente de tres espejos o indentacion escleral "
    "para descartar desgarros retinianos subclinicos."
)

