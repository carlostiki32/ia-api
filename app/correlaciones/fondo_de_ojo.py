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
    "exudado",
    "hemorragia retiniana", "hemorragia intraretin", "hemorragia intrarretin",
    "hemorragia en mancha", "hemorragia puntiforme", "hemorragia en punto",
    "neovas", "rubeosis",
    "retinopatia diabetica", "rdnp", "rdp",
    "arrosariamiento", "rosario venoso", "arrosariamiento venoso", "irma",
)
_KEYWORDS_FONDO_GLAUCOMATOSO = (
    "c/d 0.6", "c/d 0.7", "c/d 0.8", "c/d 0.9",
    "cup/disc 0.6", "cup/disc 0.7", "cup/disc 0.8", "cup/disc 0.9",
    "e/p 0.6", "e/p 0.7", "e/p 0.8", "e/p 0.9",
    "cd 0.6", "cd 0.7", "cd 0.8", "cd 0.9",
    "excavacion", "excavada", "excavado", "papila asimetrica", "asimetria c/d",
    "asimetria de la excavacion", "muesca", "escotadura", "notch",
    "hemorragia peripapilar", "hemorragia en astilla",
    "rima neural adelgazada", "anillo neurorretiniano adelgazado",
    "adelgazamiento del anillo", "adelgazamiento neurorretiniano", "isnt",
)
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
    "tortuosidad vascular", "tortuosidad", "cruces arteriovenosos", "cruces av",
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
    "desprendimiento": "desprendimiento de retina",
    "schisis": "schisis periferica",
    "retinosquisis": "retinosquisis",
}
_KEYWORDS_FONDO_PERIFERICO = tuple(_KEYWORDS_FONDO_PERIFERICO_MAP)


@_memoize_cond
def _cond_fondo_periferico_riesgo(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: fondo con lattice o desgarro periferico activa urgencia retinologica."""
    return _fondo_contains(req, _KEYWORDS_FONDO_PERIFERICO)


def _texto_fondo_periferico_riesgo(req: ImpresionClinicaRequest) -> str:
    hallazgos = _extract_normalized_findings(
        req.clinica.fondo_de_ojo if req.clinica is not None else None,
        _KEYWORDS_FONDO_PERIFERICO_MAP,
        allow_negation_window=True,
    )
    hallazgo = _join_hallazgos(hallazgos) if hallazgos else "hallazgo periferico de riesgo"
    return (
        f"Hallazgo urgente: en la retina periferica se documenta {hallazgo}, que amerita "
        "valoracion retinologica urgente y posible tratamiento profilactico."
    )


@_memoize_cond
def _cond_glaucoma_asimetrico(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: DPAR + fondo glaucomatoso confirman neuropatia optica glaucomatosa asimetrica con compromiso funcional."""
    if req.clinica is None:
        return False
    txt_pupilas = _normalize_text(req.clinica.reflejos_pupilares)
    hay_dpar = any(
        _keyword_matches(txt_pupilas, k, allow_negation_window=True)
        for k in ("dpar", "marcus gunn")
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
    if _cond_glaucoma_asimetrico(req):
        return False
    return _fondo_contains(req, _KEYWORDS_FONDO_GLAUCOMATOSO)


_texto_fondo_glaucomatoso = (
    "Se documentan hallazgos papilares con excavacion aumentada y/o alteracion "
    "del anillo neurorretiniano, ameritando valoracion oftalmologica con "
    "tonometria y perimetria para descarte de glaucoma."
)


@_memoize_cond
def _cond_papila_patologica(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: palidez, edema o neuritis papilar activan alerta neurooftalmica."""
    return _fondo_contains(req, _KEYWORDS_PAPILA_NO_GLAUCOMA)


def _texto_papila_patologica(req: ImpresionClinicaRequest) -> str:
    fondo = _normalize_text(req.clinica.fondo_de_ojo if req.clinica is not None else None)
    es_emergencia = any(token in fondo for token in _KEYWORDS_PAPILA_EMERGENCIA)
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


@_memoize_cond
def _cond_fondo_macular_dmae(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: drusas o alteracion del EPR en fondo sugieren patron de DMAE."""
    return _fondo_contains(req, _KEYWORDS_FONDO_DMAE)


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
    """Caso clinico: cruces AV o tortuosidad vascular sugieren retinopatia hipertensiva."""
    return _fondo_contains(req, _KEYWORDS_FONDO_HIPERTENSIVO)


_texto_fondo_hipertensivo = (
    "Se documentan hallazgos vasculares en fondo de ojo con alteraciones "
    "arteriovenosas, ameritando correlacion con cifras tensionales sistemicas."
)


@_memoize_cond
def _cond_fondo_vascular_diabetico(req: ImpresionClinicaRequest) -> bool:
    """Caso clinico: microaneurismas o exudados activan correlacion vascular metabolica.

    No se suprime contra `fondo_hipertensivo`: retinopatia diabetica e hipertensiva
    coexisten con frecuencia clinica (comorbilidad DM2 + HTA) y usan hallazgos
    vasculares distintos que ambos merecen mencionarse, a diferencia de las demas
    correlaciones de fondo (glaucomatosa, macular, periferica) que describen procesos
    anatomicamente distintos y donde la supresion evita solo redundancia narrativa.
    """
    if any((
        _cond_fondo_periferico_riesgo(req),
        _cond_fondo_glaucomatoso(req),
        _cond_fondo_macular_dmae(req),
        _cond_fondo_macular_otros(req),
    )):
        return False
    return _fondo_contains(req, _KEYWORDS_VASCULARES_DIABETICOS)


_texto_fondo_vascular_diabetico = (
    "Se documentan hallazgos vasculares en fondo de ojo con presencia de "
    "alteraciones microvasculares, ameritando correlacion sistemica (control "
    "glucemico) y valoracion retinologica."
)
