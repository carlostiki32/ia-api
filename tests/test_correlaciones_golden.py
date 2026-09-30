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
        "diplopia_aguda",
        _req(paciente=ContextoPaciente(motivo_consulta="Diplopia OD desde hoy.")),
        "Hallazgo urgente: se refiere diplopia de inicio reciente en OD. "
        "Requiere valoracion oftalmologica el mismo dia, con evaluacion de la motilidad "
        "y alineacion ocular segun los hallazgos, sin esperar el control periodico. "
        "La refraccion registrada no determina la causa del sintoma.",
    ),
    (
        "fondo_periferico_riesgo",
        _req(clinica=DatosClinica(fondo_de_ojo="Lattice temporal en OI.")),
        "En la retina periferica se documenta degeneracion lattice, "
        "que amerita exploracion programada de la periferia bajo midriasis y educacion al paciente "
        "para acudir a revision sin esperar a la cita programada si presenta fotopsias, "
        "miodesopsias nuevas o sombra en el campo visual.",
    ),
    (
        "fondo_periferico_riesgo_urgente",
        _req(clinica=DatosClinica(fondo_de_ojo="Desgarro retiniano en herradura superior en OI.")),
        "Hallazgo urgente: en el fondo de ojo se documenta desgarro retiniano, "
        "que amerita valoracion retinologica urgente con exploracion de la retina periferica bajo midriasis e indentacion escleral.",
    ),
    (
        "papila_patologica_base",
        _req(clinica=DatosClinica(fondo_de_ojo="Palidez papilar en OD.")),
        "Se documenta alteracion del nervio optico (palidez, atrofia o neuropatia referida), "
        "hallazgo que amerita valoracion oftalmologica preferente con campimetria e imagen del nervio optico "
        "para determinar su causa, incluida neuroimagen a criterio del especialista.",
    ),
    (
        "papila_patologica_urgente",
        _req(clinica=DatosClinica(fondo_de_ojo="Papiledema bilateral.")),
        "Hallazgo urgente: se documenta aspecto de edema de papila en el fondo de ojo, "
        "hallazgo que amerita valoracion oftalmologica o neurooftalmologica dentro de las 24 horas "
        "para verificar si se trata de edema verdadero y, en ese caso, estudiar su causa, incluida la hipertension intracraneal.",
    ),
    (
        "glaucoma_asimetrico",
        _req(clinica=DatosClinica(
            reflejos_pupilares="Marcus Gunn: positivo OD",
            fondo_de_ojo="Excavacion c/d 0.8 en OD, 0.4 en OI.",
        )),
        "Se documenta defecto pupilar aferente relativo en el ojo derecho junto con relacion copa/disco de 0.8, "
        "mayor que la del ojo contralateral (0.4) en el mismo ojo; esta asimetria funcional y estructural de la "
        "via visual aferente amerita valoracion oftalmologica preferente con tonometria, perimetria y OCT de capa "
        "de fibras nerviosas para establecer si su origen es glaucomatoso o de otra causa.",
    ),
    (
        "pupilas_alteradas_base",
        _req(clinica=DatosClinica(reflejos_pupilares="Anisocoria de 2 mm.")),
        "Se registra anisocoria; amerita valoracion oftalmologica de la respuesta y anatomia pupilar "
        "para establecer su causa y revisar su evolucion y seguimiento. "
        "Verificar inicio y sintomas asociados para decidir la prioridad de atencion.",
    ),
    (
        "pupilas_alteradas_dpar",
        _req(clinica=DatosClinica(reflejos_pupilares="DPAR positivo en OI.")),
        "Se registra defecto pupilar aferente relativo OI; amerita valoracion oftalmologica "
        "de retina y via visual aferente para establecer su causa y revisar su evolucion y seguimiento. "
        "Verificar inicio y sintomas asociados para decidir la prioridad de atencion.",
    ),
    (
        "fondo_glaucomatoso",
        _req(clinica=DatosClinica(fondo_de_ojo="Excavacion papilar c/d 0.8 en OD.")),
        "Se documenta en el fondo de ojo relacion copa/disco de 0.8 en OD, hallazgo papilar que amerita "
        "valoracion oftalmologica para estudio de glaucoma con tonometria, gonioscopia, paquimetria, campimetria "
        "y OCT de nervio optico; la relacion copa/disco debe interpretarse segun el tamano del disco.",
    ),
    (
        "fondo_macular_dmae",
        _req(clinica=DatosClinica(fondo_de_ojo="Drusas blandas maculares.")),
        "Se documentan drusas o alteraciones pigmentarias o atroficas maculares, que ameritan valoracion oftalmologica programada "
        "con retinografia u OCT macular para estadificacion y para definir la indicacion de suplementacion antioxidante segun estadio, "
        "junto con educacion en autocontrol con rejilla de Amsler para acudir a revision sin esperar a la cita programada si aparece distorsion o mancha central nueva.",
    ),
    (
        "fondo_macular_otros",
        _req(clinica=DatosClinica(fondo_de_ojo="Membrana epirretiniana macular.")),
        "En la region macular se documenta alteracion estructural que amerita OCT macular y valoracion retinologica programada, "
        "con reconsulta si aparece distorsion o disminucion de la vision central.",
    ),
    (
        "fondo_hipertensivo",
        _req(clinica=DatosClinica(fondo_de_ojo="Estrechamiento arteriolar y cruces AV con pinzamiento.")),
        "Se describe estrechamiento arteriolar y cruce arteriovenoso con pinzamiento en los vasos retinianos, lo que amerita valoracion oftalmologica y revision medica de la presion arterial.",
    ),
    (
        "fondo_vascular_diabetico",
        _req(clinica=DatosClinica(fondo_de_ojo="Microaneurismas y exudados duros.")),
        "Se documentan hallazgos microvasculares retinianos (microaneurismas y exudados duros), "
        "lo que amerita valoracion retinologica y evaluacion medica sistemica, incluida la glucemia y la presion arterial.",
    ),
    (
        "motilidad_alterada",
        _req(clinica=DatosClinica(motilidad_ocular="Limitacion de la abduccion en OD.")),
        "La exploracion documenta limitacion de abduccion OD, que amerita valoracion especializada "
        "para aclarar su origen. Verificar inicio y sintomas asociados (diplopia, dolor, vertigo) "
        "para decidir la prioridad de atencion.",
    ),
    (
        "campos_visuales_alterados",
        _req(clinica=DatosClinica(confrontacion_campos_visuales="Escotoma en cuadrante superior.")),
        "Se documenta escotoma en cuadrante superior durante la confrontacion de campos visuales. "
        "Este hallazgo requiere evaluacion especializada y caracterizacion mediante perimetria formal "
        "segun corresponda. Verificar inicio y sintomas asociados para decidir la prioridad de atencion.",
    ),
    (
        "opacidad_cristaliniana",
        _req(clinica=DatosClinica(anexos_oculares="Catarata nuclear en AO.")),
        'Se documenta opacidad del cristalino nuclear en ambos ojos, que amerita valoracion oftalmologica para '
        'caracterizarla y valorar su repercusion.',
    ),
    (
        "but_critico",
        _req(clinica=DatosClinica(ojo_seco_but_seg=3)),
        "Se registra un tiempo de ruptura lagrimal de 3 segundos, reducido. Conviene corroborar "
        "la medicion y valorar la estabilidad lagrimal en el contexto de los sintomas y la exploracion.",
    ),
    (
        "miopia_magna",
        _req(refraccion=Refraccion(od=GraduacionOjo(esfera=-7.00))),
        'La refraccion final registrada presenta OD (esfera -7.00D; cilindro no registrado, EE exacto no '
        'calculable), dentro del rango refractivo de miopia alta. Este dato amerita valoracion de retina central '
        'y periferica y seguimiento segun los hallazgos y los controles ya documentados. La graduacion no '
        'determina por si sola lesiones, mecanismo axial ni progresion.',
    ),
    (
        "miopia_magna_muy_alta",
        _req(refraccion=Refraccion(od=GraduacionOjo(esfera=-9.00))),
        'La refraccion final registrada presenta OD (esfera -9.00D; cilindro no registrado, EE exacto no '
        'calculable), dentro del rango refractivo de miopia alta. Este dato amerita valoracion de retina central '
        'y periferica y seguimiento segun los hallazgos y los controles ya documentados. La graduacion no '
        'determina por si sola lesiones, mecanismo axial ni progresion.',
    ),
    (
        "hipermetropia_alta_mayor",
        _req(paciente=ContextoPaciente(edad=45), refraccion=Refraccion(od=GraduacionOjo(esfera=5.50, cilindro=0))),
        'La refraccion final registrada presenta OD (EE +5.50D), de magnitud hipermetropica elevada. Conviene '
        'completar la valoracion ocular y ajustar el seguimiento a la agudeza visual, alineacion y examen del '
        'segmento anterior. Valorar la camara anterior y el angulo segun antecedentes y exploraciones '
        'documentadas; la graduacion no demuestra estrechez angular ni esfuerzo acomodativo residual.',
    ),
    (
        "hipermetropia_alta_joven",
        _req(paciente=ContextoPaciente(edad=18), refraccion=Refraccion(od=GraduacionOjo(esfera=5.50, cilindro=0))),
        'La refraccion final registrada presenta OD (EE +5.50D), de magnitud hipermetropica elevada. Conviene '
        'completar la valoracion ocular y ajustar el seguimiento a la agudeza visual, alineacion y examen del '
        'segmento anterior. Valorar la camara anterior y el angulo segun antecedentes y exploraciones '
        'documentadas; la graduacion no demuestra estrechez angular ni esfuerzo acomodativo residual.',
    ),
    (
        "anisometropia",
        _req(refraccion=Refraccion(od=GraduacionOjo(esfera=-1.00, cilindro=0), oi=GraduacionOjo(esfera=-3.50, cilindro=0))),
        'Las refracciones finales registradas difieren 2.50D en equivalente esferico entre OD (-1.00D) y OI '
        '(-3.50D). Conviene valorar la agudeza visual de cada ojo y la tolerancia binocular con la correccion '
        'indicada.',
    ),
    (
        "av_cc_limitada",
        _req(refraccion=Refraccion(od=GraduacionOjo(av_cc="20/40"))),
        'OD: AV con correccion registrada de 20/40. Verificar medicion y correccion utilizada; el registro no '
        'acredita mejor AV corregida. Si persiste reducida sin explicacion documentada, requiere evaluacion '
        'oftalmologica; ajustar el seguimiento a las causas y controles ya consignados. La edad no esta '
        'registrada; limitar la interpretacion hasta completar ese contexto.',
    ),
    (
        # La comparacion entre metodos no demuestra fluctuacion temporal.
        "ar_rx_variabilidad_inespecifica",
        _req(
            paciente=ContextoPaciente(edad=45),
            refraccion=Refraccion(od=GraduacionOjo(esfera=0.50)),
            akr=AkrSnapshot(od=AkrOjo(esfera=2.00)),
        ),
        'Diferencia entre registros: OD: esfera AR +2.00D y Rx prescrita +0.50D (diferencia absoluta 1.50D). '
        'Conviene revisar las mediciones y el criterio de prescripcion antes de interpretar la diferencia; los '
        'registros no acreditan simultaneidad, ejes equivalentes ni el mismo plano optico. La diferencia aislada '
        'no establece su causa ni inestabilidad refractiva.',
    ),
    (
        # Regresion reparada: antes generaba ". lo que" (punto + minuscula). Ahora coma.
        "ar_detecta_astigmatismo_no_prescrito",
        _req(
            refraccion=Refraccion(od=GraduacionOjo(cilindro=-0.25)),
            akr=AkrSnapshot(od=AkrOjo(cilindro=-1.00)),
        ),
        'En los registros consta OD: cilindro AR -1.00D y cilindro prescrito -0.25D. Conviene revisar las '
        'mediciones y el criterio de prescripcion antes de interpretar la diferencia; el cilindro corneal no '
        'representa por si solo todo el componente ocular. No se acredita comparabilidad temporal ni de planos '
        'opticos, y esta seleccion no evalua diferencias de eje.',
    ),
    (
        "astig_oblicuo",
        _req(refraccion=Refraccion(od=GraduacionOjo(cilindro=-2.50, eje=45))),
        'OD: la prescripcion registra cilindro de -2.50D a 45 grados, con orientacion oblicua.',
    ),
    (
        "queratocono_ectasia_sospecha",
        _req(akr=AkrSnapshot(od=AkrOjo(k2_d=49.00, k_cilindro=-2.00))),
        'La queratometria registrada presenta valores elevados en OD (mayor meridiano registrado 49.00D, K2 '
        'registrada 49.00D, queratometria parcial, cilindro corneal 2.00D). Verificar repetibilidad, condiciones '
        'de medicion y antecedentes; si persisten sin explicacion o coexisten hallazgos clinicos, valorar '
        'evaluacion corneal especializada y la necesidad de topografia/tomografia. Estos valores aislados no '
        'establecen la anatomia ni la causa del hallazgo.',
    ),
    (
        "astigmatismo_corneal_vs_refractivo",
        _req(
            refraccion=Refraccion(od=GraduacionOjo(cilindro=-0.75, eje=90)),
            akr=AkrSnapshot(od=AkrOjo(k_cilindro=-3.00, k_cilindro_eje=90)),
        ),
        'Se registra diferencia entre el astigmatismo corneal queratometrico y el cilindro de la prescripcion '
        'final en OD (cilindro de la prescripcion final -0.75D; cilindro corneal queratometrico 3.00D; diferencia'
        ' de magnitudes 2.25D; orientacion no comparada por datos insuficientes). Revisar mediciones, condiciones'
        ' de captura y criterio de prescripcion e interpretar con la exploracion. Esta comparacion descriptiva no'
        ' calcula un residual optico, no acredita simultaneidad de las mediciones ni establece la causa de la '
        'diferencia.',
    ),
    (
        "amsler_alterado",
        _req(clinica=DatosClinica(grid_de_amsler="Metamorfopsia central.")),
        "En la rejilla de Amsler se refiere metamorfopsia. Este hallazgo amerita evaluacion oftalmologica de la "
        "vision central y estudios complementarios segun los hallazgos. Verificar inicio y sintomas asociados "
        "para decidir la prioridad de atencion.",
    ),
    (
        "anexos_patologicos",
        _req(clinica=DatosClinica(anexos_oculares="Blefaritis anterior.")),
        'En anexos oculares se documenta blefaritis anterior, que amerita evaluacion oftalmologica para '
        'caracterizar la lesion y valorar su repercusion.',
    ),
    (
        "insuficiencia_convergencia",
        _req(
            paciente=ContextoPaciente(motivo_consulta="cefalea con lectura"),
            clinica=DatosClinica(ppc_cm=12, cover_test="OD: Exo y Foria | OI: Orto"),
        ),
        'Se registra PPC de 12 cm y exoforia en OD en el cover test; se refiere: cefalea con lectura. Conviene '
        'completar la evaluacion binocular, verificar el protocolo del PPC y cuantificar desviacion cerca/lejos y'
        ' reservas fusionales para determinar la posible relacion con las molestias.',
    ),
    (
        "ppc_exoforia",
        _req(clinica=DatosClinica(ppc_cm=12)),
        'Se registra PPC de 12 cm. Verificar el protocolo de medicion antes de interpretar el PPC.',
    ),
    (
        "cover_exoforia_sintomatica",
        _req(
            paciente=ContextoPaciente(motivo_consulta="diplopia intermitente"),
            clinica=DatosClinica(cover_test="OD: Exo y Foria | OI: Orto"),
        ),
        'Se registra exoforia en OD en el cover test; se refiere: diplopia intermitente. Conviene completar la '
        'evaluacion binocular para determinar la posible relacion entre los hallazgos y las molestias.',
    ),
    (
        "cover_endoforia_sintomatica",
        _req(
            paciente=ContextoPaciente(motivo_consulta="fatiga visual con lectura"),
            clinica=DatosClinica(cover_test="OD: Endo y Foria | OI: Orto"),
        ),
        'Se registra endoforia en OD en el cover test; se refiere: fatiga visual con lectura. Conviene verificar '
        'y cuantificar las desviaciones registradas, precisar subtipos pendientes y completar la evaluacion '
        'binocular para determinar la posible relacion con las molestias.',
    ),
    (
        "desviacion_vertical",
        _req(clinica=DatosClinica(cover_test="OD: Hiper y Foria | OI: Orto")),
        'Se registra hiperforia en OD en el cover test. Conviene verificar y cuantificar la desviacion, precisar '
        'los subtipos pendientes y valorar su relevancia funcional mediante evaluacion binocular.',
    ),
    (
        "cvs_sospecha",
        _req(
            paciente=ContextoPaciente(motivo_consulta="ardor ocular"),
            clinica=DatosClinica(uso_pantallas="gt6"),
        ),
        'Se registra uso de pantallas de mas de 6 horas diarias y se refiere: ardor ocular. Conviene caracterizar'
        ' las molestias y valorar la superficie ocular y la funcion visual; las condiciones de trabajo visual '
        'pueden revisarse segun el contexto referido.',
    ),
    (
        "endotropia_lente",
        _req(clinica=DatosClinica(cover_test="OD: Endo y Tropia | OI: Orto"), tipo_lente="monofocal"),
        'Se registra endotropia en OD en el cover test. Conviene cuantificar la desviacion y completar la '
        'evaluacion de estrabismo, incluida la valoracion refractiva.',
    ),
    (
        "exotropia_lente",
        _req(clinica=DatosClinica(cover_test="OD: Exo y Tropia | OI: Orto"), tipo_lente="monofocal"),
        'Se registra exotropia en OD en el cover test. Conviene completar la evaluacion de estrabismo, '
        'cuantificar la desviacion y caracterizar frecuencia, control, funcion binocular y refraccion.',
    ),
    (
        "but_pantallas",
        _req(clinica=DatosClinica(ojo_seco_but_seg=7, uso_pantallas="gt6")),
        "Se registra un tiempo de ruptura lagrimal de 7 segundos. Conviene corroborar la medicion "
        "y valorar la estabilidad lagrimal en el contexto de los sintomas y la exploracion. "
        "Uso de pantallas declarado: mas de 6 horas al dia.",
    ),
    (
        "but_limitrofe",
        _req(clinica=DatosClinica(ojo_seco_but_seg=7)),
        "Se registra un tiempo de ruptura lagrimal de 7 segundos. Conviene corroborar la medicion "
        "y valorar la estabilidad lagrimal en el contexto de los sintomas y la exploracion.",
    ),
    (
        "ambliopia_sospecha",
        _req(refraccion=Refraccion(
            od=GraduacionOjo(esfera=-0.50, cilindro=0, av_cc="20/20"),
            oi=GraduacionOjo(esfera=-3.00, cilindro=0, av_cc="20/60", av_sc="20/200"),
        )),
        'Se registra AV con correccion 20/60 en OI (sin correccion 20/200). La medicion debe interpretarse segun '
        'la edad y el metodo utilizado, sin equipararla a la mejor AV corregida. Conviene verificar la medicion y'
        ' la correccion utilizada, y completar la evaluacion oftalmologica para aclarar estos hallazgos. Coexiste'
        ' una diferencia entre las recetas registradas: OD esfera -0.50 D, cilindro +0.00 D; OI esfera -3.00 D, '
        'cilindro +0.00 D.',
    ),
    (
        "adulto_mayor_screening",
        _req(paciente=ContextoPaciente(edad=72), refraccion=Refraccion(od=GraduacionOjo(av_cc="20/40"))),
        'Se registra AV con correccion 20/40 en OD. Edad registrada: 72 anos. La medicion debe interpretarse '
        'segun la edad y el metodo utilizado, sin equipararla a la mejor AV corregida. Conviene verificar la '
        'medicion y la correccion utilizada, y completar la evaluacion oftalmologica para aclarar estos '
        'hallazgos.',
    ),
    (
        "horner_o_tercer_par_sospecha",
        _req(clinica=DatosClinica(
            anexos_oculares="Ptosis palpebral en OD",
            reflejos_pupilares="Anisocoria pupilar OD > OI",
        )),
        "Se documentan ptosis OD y anisocoria; estos hallazgos ameritan valoracion especializada "
        "para caracterizar la respuesta pupilar, la motilidad y su causa. "
        "Verificar lateralidad y evolucion para decidir la prioridad de atencion.",
    ),

    (
        "cornea_plana_extrema",
        _req(akr=AkrSnapshot(od=AkrOjo(k1_d=37.50, k2_d=37.80))),
        'La queratometria registra un valor de curvatura bajo en OD (K1 registrada 37.50D). Verificar lectura, '
        'repetibilidad y antecedentes corneales; si persiste sin explicacion o coexisten hallazgos clinicos, '
        'valorar el segmento anterior. Esta medicion aislada no establece la anatomia global ni su causa.',
    ),
    (
        "ojo_seco_evaporativo_dgm",
        _req(clinica=DatosClinica(
            anexos_oculares="Blefaritis anterior y disfuncion meibomio",
            ojo_seco_but_seg=6,
        )),
        "Se registra un tiempo de ruptura lagrimal de 6 segundos. Conviene corroborar la medicion "
        "y valorar la estabilidad lagrimal en el contexto de los sintomas y la exploracion. "
        "En anexos se registra alteracion meibomiana descrita. Conviene evaluar la funcion "
        "de las glandulas de Meibomio junto con la estabilidad lagrimal.",
    ),
    (
        "deficit_visual_inexplicado_refractivo",
        _req(
            paciente=ContextoPaciente(edad=28),
            refraccion=Refraccion(
                od=GraduacionOjo(esfera=-1.50, av_sc="20/100", av_cc="20/50"),
            ),
        ),
        'Se registra AV con correccion 20/50 en OD (sin correccion 20/100). Edad registrada: 28 anos. La medicion'
        ' debe interpretarse segun la edad y el metodo utilizado, sin equipararla a la mejor AV corregida. '
        'Conviene verificar la medicion y la correccion utilizada, y completar la evaluacion oftalmologica para '
        'aclarar estos hallazgos.',
    ),
    (
        "fondo_oclusion_vascular_urgente",
        _req(clinica=DatosClinica(fondo_de_ojo="Sospecha de OVCR con hemorragias 360 grados")),
        "Hallazgo urgente: el fondo de ojo registra signos descritos como oclusion venosa retiniana, "
        "hallazgo que amerita valoracion oftalmologica prioritaria en los proximos dias, sin esperar "
        "a la siguiente cita programada, con medicion de presion intraocular y busqueda de edema macular "
        "y neovascularizacion, asi como evaluacion medica de presion arterial, glucosa y lipidos. "
        "Datos referidos con incertidumbre: sospecha de ovcr con hemorragias 360 grados; "
        "verificar el hallazgo sin establecer un diagnostico.",
    ),
    (
        "fondo_embolo_retiniano",
        _req(clinica=DatosClinica(fondo_de_ojo="Se observa placa de Hollenhorst en arteriola temporal OD")),
        "Se documenta en el fondo de ojo placa de Hollenhorst en OD. Es necesario precisar sintomas visuales "
        "y su temporalidad para definir la prioridad de atencion; la ausencia de ese dato no demuestra que sea "
        "asintomatico. Amerita valoracion oftalmologica y medica de riesgo cardiovascular y posible fuente "
        "embolica, sin establecer su origen.",
    ),
    (
        "sintomas_alarma_traccion_vitreoretina",
        _req(paciente=ContextoPaciente(motivo_consulta="Refiere fotopsias y flashes en periferia")),
        "Se refieren fotopsias sin tiempo de evolucion documentado; si son de inicio "
        "reciente o han aumentado, ameritan exploracion de retina periferica bajo "
        "midriasis para descartar rotura retiniana.",
    ),
    (
        "anexos_riesgo_glaucoma_secundario",
        _req(clinica=DatosClinica(anexos_oculares="Huso de Krukenberg en endotelio corneal")),
        "Se registra huso de Krukenberg en anexos oculares, que amerita evaluacion oftalmologica del "
        "segmento anterior y del riesgo glaucomatoso, incluyendo presion intraocular y gonioscopia "
        "segun corresponda.",
    ),

    (
        "queratometria_asimetrica_interocular",
        _req(akr=AkrSnapshot(
            od=AkrOjo(k_promedio_d=42.50),
            oi=AkrOjo(k_promedio_d=44.00),
        )),
        'Diferencia de K media registrada entre ojos de 1.50D (OD 42.50D vs OI 44.00D). Verificar mediciones, '
        'repetibilidad y antecedentes; si persiste sin explicacion o coexisten hallazgos clinicos, valorar '
        'evaluacion corneal especializada. La diferencia numerica aislada no establece una enfermedad ni su '
        'ausencia.',
    ),
    (
        "ambliopia_isoametropica_bilateral",
        _req(
            paciente=ContextoPaciente(edad=8),
            refraccion=Refraccion(
                od=GraduacionOjo(esfera=+5.00, av_cc="20/50"),
                oi=GraduacionOjo(esfera=+5.00, av_cc="20/50"),
            ),
        ),
        'Se registra AV con correccion 20/50 en OD; AV con correccion 20/50 en OI. Edad registrada: 8 anos. La '
        'medicion debe interpretarse segun la edad y el metodo utilizado, sin equipararla a la mejor AV '
        'corregida. Conviene verificar la medicion y la correccion utilizada, y completar la evaluacion '
        'oftalmologica pediatrica para aclarar estos hallazgos. Graduaciones registradas: OD esfera +5.00 D; OI '
        'esfera +5.00 D.',
    ),
]


_REGLAS_REGISTRADAS = {c.nombre: c for c in corr.CORRELACIONES}


def _resolver_target_regla(caso_id: str) -> str:
    """Resuelve la correlacion objetivo a partir del identificador del caso golden."""
    matching = [r for r in _REGLAS_REGISTRADAS.keys() if caso_id == r or caso_id.startswith(r + "_")]
    if not matching:
        raise ValueError(f"No se encontro una correlacion registrada para caso_id='{caso_id}'")
    return max(matching, key=len)


@pytest.mark.parametrize("caso_id, req, esperado", GOLDEN, ids=[g[0] for g in GOLDEN])
def test_texto_clinico_exacto(caso_id, req, esperado):
    target_regla = _resolver_target_regla(caso_id)

    # 1. Comprobar que la regla objetivo este efectivamente activa para este caso
    activas = corr.nombres_correlaciones_activas(req)
    assert target_regla in activas, (
        f"[{caso_id}] La regla objetivo '{target_regla}' no se activo con este caso.\n"
        f"Activas: {activas}"
    )

    # 2. Comprobar que el texto renderizado especificamente por esa regla coincida exactamente
    c = _REGLAS_REGISTRADAS[target_regla]
    texto_renderizado = c.render(req)
    assert texto_renderizado == esperado, (
        f"[{caso_id}] Discrepancia en texto exacto para '{target_regla}'.\n"
        f"Esperado:    {esperado!r}\n"
        f"Renderizado: {texto_renderizado!r}"
    )

    # 3. Comprobar que este presente en la lista global producida por evaluar_correlaciones
    textos = corr.evaluar_correlaciones(req)
    assert esperado in textos, (
        f"[{caso_id}] El texto exacto esperado no se encontro en la salida global.\n"
        f"Esperado: {esperado!r}\nProducidos: {textos!r}"
    )


def test_golden_cubre_todas_las_correlaciones():
    """Garantiza que cada una de las 47 correlaciones medicas registradas tenga al menos
    un caso golden que audite directamente su activacion y su texto exacto.

    A diferencia de una suma incidental de condiciones secundarias, este test
    exige cobertura directa: la regla debe ser el target explícito de al menos
    un fixture golden."""
    cubiertas_directas = {_resolver_target_regla(caso_id) for caso_id, _req, _esperado in GOLDEN}
    registradas = {c.nombre for c in corr.CORRELACIONES}
    faltantes = registradas - cubiertas_directas
    assert not faltantes, (
        f"Existen {len(faltantes)} correlaciones sin prueba golden directa que audite su texto: "
        f"{sorted(faltantes)}"
    )
    assert len(registradas) == 47, f"Se esperaban 47 correlaciones medicas, hay {len(registradas)}"

