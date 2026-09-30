"""#55 preserva datos bilaterales y contexto pediatrico sin etiologia, simetria ni tratamiento."""
import pytest
from app.correlaciones import contexto as dominio
from tests.test_ajuste_c42 import cases, request

CASOS = cases(55)
EXPECTATIVAS = {n: n not in {"05", "06", "07", "08", "09", "11", "16", "17", "28", "29"} for n in CASOS}


@pytest.mark.parametrize("numero", CASOS)
def test_c55_reproduccion(numero):
    req = request(**CASOS[numero]["entrada"])
    assert dominio._cond_ambliopia_isoametropica_bilateral(req) == EXPECTATIVAS[numero]
    if EXPECTATIVAS[numero]:
        texto = dominio._texto_ambliopia_isoametropica_bilateral(req)
        assert "20/" in texto and " en OD" in texto and " en OI" in texto
        assert not any(p in texto.lower() for p in ("sospecha de ambliopia", "isoametropica", "simetrica", "ausencia de patologia", "optica total", "estimulacion", "subnormal"))
        assert texto.startswith("Hallazgo urgente:") == (numero == "26")
        if numero in {"22", "23", "24", "25"}:
            assert "Contexto referido:" in texto
        if numero == "27":
            assert "es mejor" in texto and "OD y OI" in texto


def test_c55_igual_ee_no_equivale_simetria_de_componentes():
    texto = dominio._texto_ambliopia_isoametropica_bilateral(request(**CASOS["13"]["entrada"]))
    assert "OD esfera +4.00 D, cilindro +0.00 D" in texto
    assert "OI esfera +6.00 D, cilindro -4.00 D" in texto
    assert "simetrica" not in texto


def test_c55_faltantes_no_se_imputan_ni_inventan_ee():
    for numero in ("14", "15"):
        texto = dominio._texto_ambliopia_isoametropica_bilateral(request(**CASOS[numero]["entrada"]))
        assert "equivalente" not in texto
        assert ("cilindro" not in texto) if numero == "14" else ("esfera" not in texto)


def test_c55_dedupe_por_hechos_con54_conserva_ambos_ojos_y_recetas():
    for numero in ("16", "17", "29"):
        req = request(**CASOS[numero]["entrada"])
        assert dominio._cond_ambliopia_sospecha(req)
        texto = dominio._texto_ambliopia_sospecha(req)
        assert "20/40 en OD" in texto and "20/40 en OI" in texto
        assert "OD esfera" in texto and "OI esfera" in texto
