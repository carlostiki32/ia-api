import datetime
import pytest

from app.seguimiento.fechas import formatear_fecha, periodo_en_palabras


def test_formatear_fecha_mismo_ano():
    hoy = datetime.date(2026, 11, 20)
    assert formatear_fecha(datetime.date(2026, 12, 15), hoy) == "15 de diciembre"
    assert formatear_fecha(datetime.date(2026, 1, 1), hoy) == "1 de enero"
    assert formatear_fecha(datetime.date(2026, 9, 30), hoy) == "30 de septiembre"


def test_formatear_fecha_ano_distinto():
    hoy = datetime.date(2026, 11, 20)
    assert formatear_fecha(datetime.date(2027, 1, 3), hoy) == "3 de enero de 2027"
    assert formatear_fecha(datetime.date(2025, 12, 31), hoy) == "31 de diciembre de 2025"


def test_formatear_fecha_por_omision():
    hoy = datetime.date.today()
    resultado = formatear_fecha(hoy)
    assert " de " in resultado


@pytest.mark.parametrize("meses,esperado", [
    (3, "tres meses"),
    (4, "cuatro meses"),
    (5, "cinco meses"),
    (6, "seis meses"),
    (7, "siete meses"),
    (8, "ocho meses"),
    (9, "nueve meses"),
    (10, "diez meses"),
    (11, "once meses"),
    (12, "un año"),
    (13, "un año y un mes"),
    (14, "un año y dos meses"),
    (15, "un año y tres meses"),
    (16, "un año y cuatro meses"),
    (17, "un año y cinco meses"),
    (18, "un año y medio"),
    (19, "un año y siete meses"),
    (20, "un año y ocho meses"),
    (21, "un año y nueve meses"),
    (22, "un año y diez meses"),
    (23, "un año y once meses"),
    (24, "dos años"),
])
def test_periodo_en_palabras(meses, esperado):
    assert periodo_en_palabras(meses) == esperado


@pytest.mark.parametrize("invalido", [0, 1, 2, 25, 30, -5])
def test_periodo_fuera_de_rango(invalido):
    with pytest.raises(ValueError):
        periodo_en_palabras(invalido)
