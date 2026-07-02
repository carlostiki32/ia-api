"""Golden tests: fijan el TEXTO CLINICO COMPLETO de cada correlacion.

A diferencia de test_correlaciones.py (que valida que una correlacion se ACTIVE
y, a veces, subcadenas), estas pruebas comparan el texto renderizado completo
contra un valor esperado exacto. Su unico proposito es blindar el contenido
clinico: si una futura "optimizacion" recorta una clausula de recomendacion o
atribucion (como ocurrio historicamente), el texto exacto deja de encontrarse y
la prueba falla de inmediato, en lugar de esperar a la siguiente auditoria manual.

Cada caso dispara la correlacion objetivo con datos representativos y verifica
que el texto exacto esperado este entre los textos producidos por
evaluar_correlaciones(). No se exige aislamiento (una correlacion puede coactivar
otras); se exige que SU texto exacto se genere.
"""
import pytest

import app.correlaciones as corr
from app.schemas import (
    AkrOjo,
    AkrSnapshot,
    ContextoPaciente,
    DatosClinica,
    GraduacionOjo,
    ImpresionClinicaRequest,
    Refraccion,
)


def _req(**kwargs) -> ImpresionClinicaRequest:
    defaults = {"receta_id": "golden"}
    defaults.update(kwargs)
    return ImpresionClinicaRequest(**defaults)


# (id, request, texto_exacto_esperado)
GOLDEN: list[tuple[str, ImpresionClinicaRequest, str]] = [
    (
        "fondo_periferico_riesgo",
        _req(clinica=DatosClinica(fondo_de_ojo="Lattice temporal en OI.")),
        "Hallazgo urgente: en la retina periferica se documenta degeneracion lattice, "
        "que amerita valoracion retinologica urgente y posible tratamiento profilactico.",
    ),
    (
        "papila_patologica_base",
        _req(clinica=DatosClinica(fondo_de_ojo="Palidez papilar en OD.")),
        "Se documenta alteracion del nervio optico no asociada a excavacion glaucomatosa, "
        "ameritando valoracion neurooftalmologica para caracterizacion etiologica.",
    ),
    (
        "papila_patologica_urgente",
        _req(clinica=DatosClinica(fondo_de_ojo="Bordes borrosos de papila en AO.")),
        "Hallazgo urgente: los hallazgos del nervio optico documentados son compatibles "
        "con edema de papila, lo que amerita evaluacion neurooftalmologica urgente para "
        "descarte de hipertension intracraneal.",
    ),
    (
        "glaucoma_asimetrico",
        _req(clinica=DatosClinica(
            reflejos_pupilares="Marcus Gunn: positivo OD",
            fondo_de_ojo="Excavacion c/d 0.8 en OD.",
        )),
        "Hallazgo urgente: se documenta excavacion papilar aumentada con defecto pupilar "
        "aferente relativo, lo que indica compromiso asimetrico del nervio optico con "
        "probable repercusion funcional, ameritando valoracion oftalmologica priorizada.",
    ),
    (
        "pupilas_alteradas_base",
        _req(clinica=DatosClinica(reflejos_pupilares="Anisocoria de 2 mm.")),
        "En la exploracion pupilar se documenta anisocoria, lo que amerita valoracion "
        "neurooftalmologica.",
    ),
    (
        "pupilas_alteradas_dpar",
        _req(clinica=DatosClinica(reflejos_pupilares="DPAR positivo en OI.")),
        "En la exploracion pupilar se documenta defecto pupilar aferente relativo, lo que "
        "amerita valoracion neurooftalmologica. Hallazgo urgente: la presencia de defecto "
        "pupilar aferente relativo es indicativa de patologia de via optica y requiere "
        "evaluacion urgente.",
    ),
    (
        "fondo_glaucomatoso",
        _req(clinica=DatosClinica(fondo_de_ojo="Excavacion papilar c/d 0.8 en OD.")),
        "Se documentan hallazgos papilares con excavacion aumentada y/o alteracion del "
        "anillo neurorretiniano, ameritando valoracion oftalmologica con tonometria y "
        "perimetria para descarte de glaucoma.",
    ),
    (
        "fondo_macular_dmae",
        _req(clinica=DatosClinica(fondo_de_ojo="Drusas blandas maculares.")),
        "Se documentan hallazgos maculares degenerativos en fondo de ojo, ameritando OCT "
        "macular para caracterizacion y monitorizacion.",
    ),
    (
        "fondo_macular_otros",
        _req(clinica=DatosClinica(fondo_de_ojo="Membrana epirretiniana macular.")),
        "En la region macular se documenta alteracion estructural que amerita OCT y "
        "valoracion retinologica.",
    ),
    (
        "fondo_hipertensivo",
        _req(clinica=DatosClinica(fondo_de_ojo="Cruces arteriovenosos y tortuosidad vascular.")),
        "Se documentan hallazgos vasculares en fondo de ojo con alteraciones "
        "arteriovenosas, ameritando correlacion con cifras tensionales sistemicas.",
    ),
    (
        "fondo_vascular_diabetico",
        _req(clinica=DatosClinica(fondo_de_ojo="Microaneurismas y exudados duros.")),
        "Se documentan hallazgos vasculares en fondo de ojo con presencia de alteraciones "
        "microvasculares, ameritando correlacion sistemica (control glucemico) y "
        "valoracion retinologica.",
    ),
    (
        "motilidad_alterada",
        _req(clinica=DatosClinica(motilidad_ocular="Limitacion de la abduccion en OD.")),
        "Se documenta alteracion de la motilidad ocular, lo que amerita estudio de vias "
        "motoras y posible interconsulta neurooftalmologica.",
    ),
    (
        "campos_visuales_alterados",
        _req(clinica=DatosClinica(confrontacion_campos_visuales="Escotoma en cuadrante superior.")),
        "La confrontacion de campos visuales revela alteracion que amerita perimetria "
        "automatizada para caracterizacion del defecto.",
    ),
    (
        "opacidad_cristaliniana",
        _req(clinica=DatosClinica(anexos_oculares="Catarata nuclear en AO.")),
        "Se documenta alteracion del cristalino, ameritando evaluacion biomicroscopica "
        "para caracterizacion y estadificacion de la opacidad.",
    ),
    (
        "but_critico",
        _req(clinica=DatosClinica(ojo_seco_but_seg=3)),
        "El tiempo de ruptura lagrimal de 3s es patologicamente bajo, compatible con ojo "
        "seco clinico que amerita evaluacion.",
    ),
    (
        "miopia_magna",
        _req(refraccion=Refraccion(od=GraduacionOjo(esfera=-7.00))),
        "Se documenta miopia de magnitud alta en OD (EE -7.00D), lo que conlleva mayor "
        "riesgo de patologia retiniana periferica y macular.",
    ),
    (
        "miopia_magna_muy_alta",
        _req(refraccion=Refraccion(od=GraduacionOjo(esfera=-9.00))),
        "Se documenta miopia de magnitud muy alta en OD (EE -9.00D), lo que conlleva "
        "riesgo significativamente elevado de patologia retiniana periferica y macular.",
    ),
    (
        "hipermetropia_alta_mayor",
        _req(paciente=ContextoPaciente(edad=45), refraccion=Refraccion(od=GraduacionOjo(esfera=5.50))),
        "Se documenta hipermetropia alta en OD (EE +5.50D), lo que amerita evaluacion de "
        "la profundidad de camara anterior ante el riesgo asociado de angulo camerular "
        "estrecho.",
    ),
    (
        "hipermetropia_alta_joven",
        _req(paciente=ContextoPaciente(edad=18), refraccion=Refraccion(od=GraduacionOjo(esfera=5.50))),
        "Se documenta hipermetropia alta en OD (EE +5.50D), con demanda acomodativa "
        "significativa que amerita vigilancia de esoforia o esotropia acomodativa.",
    ),
    (
        "anisometropia",
        _req(refraccion=Refraccion(od=GraduacionOjo(esfera=-1.00), oi=GraduacionOjo(esfera=-3.50))),
        "Existe anisometropia moderada por diferencia de equivalente esferico de 2.50D "
        "entre OD (-1.00) y OI (-3.50); con posible impacto en la fusion binocular.",
    ),
    (
        "av_cc_limitada",
        _req(refraccion=Refraccion(od=GraduacionOjo(av_cc="20/40"))),
        "OD (20/40): reduccion moderada de la agudeza visual con correccion.",
    ),
    (
        "ar_rx_espasmo_acomodativo",
        _req(
            paciente=ContextoPaciente(edad=25),
            clinica=DatosClinica(uso_pantallas="gt6"),
            refraccion=Refraccion(od=GraduacionOjo(esfera=-1.00)),
            akr=AkrSnapshot(od=AkrOjo(esfera=-1.75)),
        ),
        "El autorrefractometro documenta mayor componente miopico que la refraccion "
        "subjetiva final en un paciente joven con uso intensivo de pantallas, patron "
        "compatible con espasmo acomodativo que amerita control posterior y eventual "
        "refraccion bajo cicloplejia.",
    ),
    (
        "ar_rx_cambio_cristalino",
        _req(
            paciente=ContextoPaciente(edad=67),
            refraccion=Refraccion(od=GraduacionOjo(esfera=1.00)),
            akr=AkrSnapshot(od=AkrOjo(esfera=-0.50)),
        ),
        "Se documenta discrepancia entre autorrefractometro y refraccion final en un "
        "paciente mayor de 55 anos, sin patron queratometrico que explique primariamente "
        "la diferencia refractiva, lo que puede reflejar cambios en el indice refractivo "
        "del cristalino y amerita evaluacion biomicroscopica del segmento anterior.",
    ),
    (
        # Regresion reparada: la clausula "compatible con variabilidad refractiva
        # durante la exploracion" habia sido recortada. Este golden la blinda.
        "ar_rx_variabilidad_inespecifica",
        _req(
            paciente=ContextoPaciente(edad=45),
            refraccion=Refraccion(od=GraduacionOjo(esfera=0.50)),
            akr=AkrSnapshot(od=AkrOjo(esfera=2.00)),
        ),
        "Se documenta discrepancia entre autorrefractometro y refraccion final, "
        "compatible con variabilidad refractiva durante la exploracion.",
    ),
    (
        # Regresion reparada: antes generaba ". lo que" (punto + minuscula). Ahora coma.
        "ar_detecta_astigmatismo_no_prescrito",
        _req(
            refraccion=Refraccion(od=GraduacionOjo(cilindro=-0.25)),
            akr=AkrSnapshot(od=AkrOjo(cilindro=-1.00)),
        ),
        "El autorrefractometro detecta astigmatismo no incluido en la refraccion "
        "subjetiva final en OD (AKR -1.00D), lo que puede corresponder a astigmatismo "
        "subumbral con tolerancia clinica adecuada o variabilidad de la medicion "
        "automatizada.",
    ),
    (
        "astig_oblicuo",
        _req(refraccion=Refraccion(od=GraduacionOjo(cilindro=-2.50, eje=45))),
        "OD (-2.50 x 45): astigmatismo elevado con eje oblicuo.",
    ),
    (
        "amsler_alterado",
        _req(clinica=DatosClinica(grid_de_amsler="Metamorfopsia central.")),
        "El test de Amsler revela alteracion compatible con patologia macular funcional "
        "que amerita OCT macular.",
    ),
    (
        "anexos_patologicos",
        _req(clinica=DatosClinica(anexos_oculares="Blefaritis anterior.")),
        "En anexos oculares se documenta blefaritis.",
    ),
    (
        "insuficiencia_convergencia",
        _req(
            paciente=ContextoPaciente(motivo_consulta="cefalea con lectura"),
            clinica=DatosClinica(ppc_cm=12, cover_test="OD: Exo y Foria | OI: Orto"),
        ),
        "La combinacion de punto proximo de convergencia alejado, exoforia y "
        "sintomatologia de vision proxima es compatible con insuficiencia de "
        "convergencia, ameritando evaluacion binocular completa para confirmar el "
        "diagnostico y plantear terapia visual si procede.",
    ),
    (
        "ppc_exoforia",
        _req(clinica=DatosClinica(ppc_cm=12)),
        "El paciente presenta punto proximo de convergencia alejado (12 cm).",
    ),
    (
        "cover_exoforia_sintomatica",
        _req(
            paciente=ContextoPaciente(motivo_consulta="diplopia intermitente"),
            clinica=DatosClinica(cover_test="OD: Exo y Foria | OI: Orto"),
        ),
        "Se documenta exoforia con sintomatologia binocular asociada, compatible con "
        "disfuncion binocular de tipo divergente que amerita evaluacion funcional.",
    ),
    (
        "cover_endoforia_sintomatica",
        _req(
            paciente=ContextoPaciente(motivo_consulta="cefalea frontal"),
            clinica=DatosClinica(cover_test="OD: Endo y Foria | OI: Orto"),
        ),
        "Se documenta endoforia con sintomatologia binocular asociada, compatible con "
        "exceso de convergencia o disfuncion acomodativa que amerita evaluacion funcional.",
    ),
    (
        "desviacion_vertical",
        _req(clinica=DatosClinica(cover_test="OD: Hiper y Foria | OI: Orto")),
        "Se documenta hiperforia, que puede generar sintomatologia binocular especifica y "
        "amerita cuantificacion prismatica para evaluar compensacion.",
    ),
    (
        "cvs_sospecha",
        _req(
            paciente=ContextoPaciente(motivo_consulta="ardor ocular"),
            clinica=DatosClinica(uso_pantallas="gt6"),
        ),
        "El perfil de uso de pantallas se correlaciona con la sintomatologia visual "
        "referida, compatible con sindrome visual informatico, ameritando recomendaciones "
        "ergonomicas y eventual correccion optica para vision intermedia.",
    ),
    (
        "endotropia_lente",
        _req(clinica=DatosClinica(cover_test="OD: Endo y Tropia | OI: Orto"), tipo_lente="monofocal"),
        "Se documenta endotropia en el cover test, ameritando evaluacion de la respuesta a "
        "la correccion optica prescrita, con cover test bajo correccion para clasificar el "
        "tipo de desviacion.",
    ),
    (
        "exotropia_lente",
        _req(clinica=DatosClinica(cover_test="OD: Exo y Tropia | OI: Orto"), tipo_lente="monofocal"),
        "Se documenta exotropia en el cover test, ameritando evaluacion binocular completa "
        "para determinar frecuencia y magnitud de la desviacion, asi como la respuesta a "
        "la correccion optica prescrita.",
    ),
    (
        "but_pantallas",
        _req(clinica=DatosClinica(ojo_seco_but_seg=7, uso_pantallas="gt6")),
        "El tiempo de ruptura lagrimal de 7 segundos es reducido en el contexto del uso "
        "de pantallas, lo que indica inestabilidad de la pelicula lagrimal.",
    ),
    (
        "but_limitrofe",
        _req(clinica=DatosClinica(ojo_seco_but_seg=7)),
        "El tiempo de ruptura lagrimal de 7s se encuentra en rango suboptimo, sugiriendo "
        "inestabilidad leve de la pelicula lagrimal.",
    ),
    (
        "presbicia_multifocal",
        _req(paciente=ContextoPaciente(edad=48), refraccion=Refraccion(od=GraduacionOjo(add=2.00))),
        "El paciente de 48 anos presenta reduccion fisiologica de la amplitud acomodativa "
        "propia de la edad, lo que justifica la adicion prescrita.",
    ),
    (
        "adulto_mayor_screening",
        _req(paciente=ContextoPaciente(edad=72), refraccion=Refraccion(od=GraduacionOjo(av_cc="20/40"))),
        "En paciente de 72 anos con reduccion de agudeza visual sin causa identificada en "
        "el examen actual, se recomienda descarte activo de catarata, glaucoma y "
        "maculopatia asociada a la edad mediante exploracion dirigida.",
    ),
]


@pytest.mark.parametrize("caso_id, req, esperado", GOLDEN, ids=[g[0] for g in GOLDEN])
def test_texto_clinico_exacto(caso_id, req, esperado):
    textos = corr.evaluar_correlaciones(req)
    assert esperado in textos, (
        f"[{caso_id}] el texto exacto esperado no se genero.\n"
        f"Esperado: {esperado!r}\nProducidos: {textos!r}"
    )


def test_golden_cubre_todas_las_correlaciones():
    """Garantiza que cada una de las 36 correlaciones registradas tenga al menos
    un golden que fije su texto. Si se agrega una correlacion nueva sin golden,
    esta prueba falla y obliga a documentar su texto exacto."""
    cubiertas = set()
    for _caso_id, req, _esperado in GOLDEN:
        for c in corr.CORRELACIONES:
            if c.condicion(req):
                cubiertas.add(c.nombre)
    registradas = {c.nombre for c in corr.CORRELACIONES}
    faltantes = registradas - cubiertas
    assert not faltantes, f"Correlaciones sin golden que fije su texto: {sorted(faltantes)}"
