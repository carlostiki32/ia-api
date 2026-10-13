"""Educación desde Rx final de lejos, sin AKR, correlaciones ni diagnósticos."""
from dataclasses import dataclass
import math
import re
import unicodedata

from app.schemas import ImpresionClinicaRequest


@dataclass(frozen=True)
class PatientEye:
    lado: str
    nombres: tuple[str, ...]
    apoyo_cerca: bool


@dataclass(frozen=True)
class PatientProfile:
    ojos: tuple[PatientEye, ...]
    estado: str

    @property
    def nombres(self) -> tuple[str, ...]:
        return tuple(name for name in _NAMES if any(name in eye.nombres for eye in self.ojos))


_NAMES = ("miopía", "hipermetropía", "astigmatismo")
_DEFINITIONS = {
    "miopía": (
        "La miopía puede hacer que veas borroso lo que está lejos, como un letrero.",
        "La miopía hace que los objetos lejanos puedan verse borrosos.",
    ),
    "hipermetropía": (
        "La hipermetropía puede hacer más difícil enfocar, sobre todo al mirar cosas de cerca.",
    ),
    "astigmatismo": (
        "El astigmatismo puede hacer que las letras y los detalles se vean borrosos, de cerca o de lejos.",
        "El astigmatismo puede hacer que algunas letras o bordes se vean poco definidos.",
    ),
}
# La primera variante conserva el respaldo existente; las otras y sus cierres
# son las frases sencillas ya usadas en la simulación válida del flujo dual.
_NEAR_DEFINITION = "Ese apoyo está pensado para ayudarte al mirar algo cerca, como un libro o un mensaje en el teléfono."
_CLOSINGS = (
    "Tus lentes llevan la graduación de cada ojo para ayudarte a ver más claro.",
    "Si alguna palabra no te queda clara, podemos explicártela en la óptica.",
    "Puedes preguntar qué significa cada parte de tu receta con palabras sencillas.",
    "Con tus lentes, la imagen puede verse más clara y cómoda en las actividades diarias.",
    "Cada ojo recibe la graduación que necesita.",
    "Los lentes ayudan a enfocar mientras los usas.",
    "Si tienes dudas sobre cómo utilizarlos, tu optometrista puede explicártelo durante la entrega.",
)


def build_patient_profile(req: ImpresionClinicaRequest) -> PatientProfile:
    eyes = []
    for side, eye in (("derecho", req.refraccion.od), ("izquierdo", req.refraccion.oi)):
        s, c = eye.esfera, eye.cilindro
        # Cero explícito es válido; nulo/no finito no se imputa ni se sustituye con AKR.
        if s is None or c is None or not math.isfinite(s) or not math.isfinite(c):
            return PatientProfile((), "datos_incompletos")
        names: tuple[str, ...] = ()
        if c == 0:
            if s < 0:
                names = ("miopía",)
            elif s > 0:
                names = ("hipermetropía",)
        else:
            # Potencias principales invariantes frente a la transposición del schema.
            other = s + c
            if s < 0 and other < 0:
                names = ("miopía", "astigmatismo")
            elif s > 0 and other > 0:
                names = ("hipermetropía", "astigmatismo")
            else:
                names = ("astigmatismo",)
        near = eye.add is not None and math.isfinite(eye.add) and eye.add > 0
        eyes.append(PatientEye(side, names, near))
    state = "aplicable" if any(e.nombres or e.apoyo_cerca for e in eyes) else "sin_componentes_refractivos"
    return PatientProfile(tuple(eyes), state)


def _join_names(names: tuple[str, ...]) -> str:
    return " y ".join(names)


def patient_opening(profile: PatientProfile) -> str:
    if profile.estado != "aplicable":
        return ""
    od, oi = profile.ojos
    if od.nombres and od.nombres == oi.nombres:
        return f"Tu graduación incluye corrección para {_join_names(od.nombres)} en los dos ojos."
    parts = [
        f"Tu graduación incluye corrección para {_join_names(e.nombres)} en el ojo {e.lado}."
        for e in profile.ojos if e.nombres
    ]
    if parts:
        return " ".join(parts)
    return _near_sentence(profile, initial=True)


def _near_sentence(profile: PatientProfile, *, initial: bool = False) -> str:
    sides = [e.lado for e in profile.ojos if e.apoyo_cerca]
    if not sides:
        return ""
    place = "en los dos ojos" if len(sides) == 2 else f"en el ojo {sides[0]}"
    connector = "" if initial else "también "
    return f"Tu receta {connector}incluye un apoyo extra para enfocar de cerca {place}."


def build_patient_context(profile: PatientProfile) -> dict:
    """La fuente educativa solo contiene hechos cerrados, sin cifras del expediente."""
    return {
        "estado": profile.estado,
        "ojos": [
            {"lado": e.lado, "correcciones_permitidas": list(e.nombres), "apoyo_cerca": e.apoyo_cerca}
            for e in profile.ojos
        ],
        "apertura_obligatoria": patient_opening(profile),
        "definiciones_permitidas": {name: list(_DEFINITIONS[name]) for name in profile.nombres},
        "frase_apoyo_cerca": _near_sentence(profile) if profile.nombres else "",
        "definicion_apoyo_cerca": _NEAR_DEFINITION if profile.estado == "aplicable" and not profile.nombres else "",
        "cierres_permitidos": list(_CLOSINGS) if profile.estado == "aplicable" else [],
    }


def _normalized(text: str) -> str:
    return " ".join("".join(ch for ch in unicodedata.normalize("NFD", text.lower()) if not unicodedata.combining(ch)).split())


def word_count(text: str) -> int:
    return len(re.findall(r"\b[\wáéíóúñü]+\b", text))


def _sentences(text: str) -> tuple[str, ...]:
    return tuple(_normalized(part) + "." for part in text[:-1].split("."))


def validate_patient_text(candidate: object, profile: PatientProfile) -> str | None:
    if profile.estado != "aplicable" or not isinstance(candidate, str):
        return None
    text = re.sub(r"\s+", " ", candidate).strip()
    if not text or len(text) > 2000 or not 60 <= word_count(text) <= 110:
        return None
    if not text.endswith("."):
        return None
    # Cada frase procede del mismo catálogo que recibe el modelo y usa el
    # respaldo CPU. No inferimos fidelidad semántica a partir de nombre + 'puede'.
    sentences = _sentences(text)
    opening = _sentences(patient_opening(profile))
    if sentences[:len(opening)] != opening:
        return None
    remaining = list(sentences[len(opening):])
    for name in profile.nombres:
        if not remaining or remaining.pop(0) not in {_normalized(s) for s in _DEFINITIONS[name]}:
            return None
    extra = _near_sentence(profile) if profile.nombres else _NEAR_DEFINITION
    if extra:
        if not remaining or remaining.pop(0) != _normalized(extra):
            return None
    closings = {_normalized(s) for s in _CLOSINGS}
    if any(sentence not in closings for sentence in remaining) or len(set(remaining)) != len(remaining):
        return None
    return text


def build_patient_template(profile: PatientProfile) -> str | None:
    if profile.estado != "aplicable":
        return None
    parts = [patient_opening(profile)]
    parts.extend(_DEFINITIONS[name][0] for name in profile.nombres)
    if profile.nombres:
        near = _near_sentence(profile)
        if near:
            parts.append(near)
    else:
        parts.append(_NEAR_DEFINITION)
    for closing in _CLOSINGS:
        if word_count(" ".join(parts)) >= 60:
            break
        parts.append(closing)
    return validate_patient_text(" ".join(parts), profile)
