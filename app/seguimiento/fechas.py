"""Manejo de fechas y periodos en lenguaje natural para seguimiento WhatsApp v2."""
import datetime

MESES = (
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
)

NUMEROS_PALABRAS = {
    1: "un",
    2: "dos",
    3: "tres",
    4: "cuatro",
    5: "cinco",
    6: "seis",
    7: "siete",
    8: "ocho",
    9: "nueve",
    10: "diez",
    11: "once",
}


def formatear_fecha(fecha: datetime.date, hoy: datetime.date | None = None) -> str:
    """Formatea una fecha como «15 de diciembre»; añade « de AAAA» si el año difiere del de hoy."""
    if hoy is None:
        hoy = datetime.date.today()
    texto = f"{fecha.day} de {MESES[fecha.month - 1]}"
    if fecha.year != hoy.year:
        texto += f" de {fecha.year}"
    return texto


def periodo_en_palabras(meses: int) -> str:
    """Convierte un periodo de 3..24 meses a palabras en español."""
    if not (3 <= meses <= 24):
        raise ValueError(f"Periodo {meses} fuera del rango 3..24")
    if meses == 12:
        return "un año"
    if meses == 18:
        return "un año y medio"
    if meses == 24:
        return "dos años"
    if 3 <= meses <= 11:
        return f"{NUMEROS_PALABRAS[meses]} meses"
    m = meses - 12
    if m == 1:
        return "un año y un mes"
    return f"un año y {NUMEROS_PALABRAS[m]} meses"
