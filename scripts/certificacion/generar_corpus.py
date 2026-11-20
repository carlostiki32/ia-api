"""Corpus sintético determinista y verosímil. Ejecutar: python -m scripts.certificacion.generar_corpus.

Escenarios clínicos realistas, sin datos reales de pacientes:
- Las edades corresponden a cada categoría; por ejemplo, la ADD solo aparece en présbitas de 42 años o más.
- Hay motivos en español clínico mexicano: multilínea, con urgencias, síntomas negados o informante.
- Los hallazgos vienen en el formato que envía Laravel.

Cada caso tiene una clave de caché distinta, por la combinación de edad y refracción.
"""
import hashlib
import json
from pathlib import Path

DESTINO = Path(__file__).resolve().parents[2] / "tests/fixtures/certificacion_gpu"
CATEGORIAS = ("miopia_baja", "miopia_alta", "hipermetropia_baja", "hipermetropia_alta",
              "astigmatismo", "presbita_add", "anisometropia", "ojo_plano",
              "sin_componentes_refractivos", "datos_incompletos")

EDADES = {
    "miopia_baja": (9, 12, 15, 17, 21, 24, 28, 33, 37, 40),
    "miopia_alta": (16, 19, 23, 27, 31, 35, 39, 44, 49, 55),
    "hipermetropia_baja": (6, 8, 10, 13, 16, 20, 25, 29, 34, 38),
    "hipermetropia_alta": (5, 6, 7, 9, 11, 14, 22, 36, 48, 60),
    "astigmatismo": (10, 14, 18, 22, 26, 31, 37, 43, 52, 60),
    "presbita_add": (42, 45, 48, 51, 54, 57, 61, 65, 70, 76),
    "anisometropia": (8, 11, 15, 19, 26, 32, 38, 45, 53, 60),
    "ojo_plano": (10, 13, 17, 23, 29, 34, 41, 47, 55, 63),
    "sin_componentes_refractivos": (18, 22, 27, 31, 36, 41, 46, 52, 58, 64),
    "datos_incompletos": (12, 19, 25, 30, 38, 44, 50, 57, 63, 71),
}

MOTIVOS = {
    "miopia_baja": ("Ve borroso el pizarrón desde hace unos meses.",
                    "Visión borrosa de lejos al manejar, sobre todo de noche.",
                    "Le cuesta leer los letreros de la calle y del transporte.",
                    "Entrecierra los ojos para ver la televisión.",
                    "Revisión anual; siente que ya no ve igual de lejos con sus lentes."),
    "miopia_alta": ("Usa lentes desde la primaria; quiere actualizar su graduación.",
                    "Siente que sus lentes ya no le ayudan de lejos.",
                    "Le pesan los lentes y pregunta por micas más delgadas.",
                    "Visión borrosa de lejos aun con sus lentes actuales."),
    "hipermetropia_baja": ("Dolor de cabeza al terminar de leer o de hacer la tarea.",
                           "Cansancio visual por la tarde frente a la computadora.",
                           "Se le juntan las letras después de un rato de lectura.",
                           "Ardor y lagrimeo al final del día."),
    "hipermetropia_alta": ("La mamá refiere que el niño desvía un ojo hacia adentro cuando está cansado.",
                           "Ve borroso de cerca y de lejos; le duelen los ojos al leer.",
                           "Usa lentes gruesos desde niño; viene a revisión."),
    "astigmatismo": ("Ve las letras borrosas, como barridas, de cerca y de lejos.",
                     "Las luces de los autos se ven estiradas de noche.",
                     "Dolor de cabeza frontal al final del día."),
    "presbita_add": ("Necesita alejar el celular para poder leer.",
                     "Ya no alcanza a leer las etiquetas ni los mensajes.",
                     "Usa lentes de lectura de farmacia y quiere algo para todo el día.",
                     "Ve bien de lejos, pero de cerca se le cansa la vista."),
    "anisometropia": ("Siente que ve mucho mejor con un ojo que con el otro.",
                      "Al taparse el ojo izquierdo nota que el derecho ve borroso.",
                      "Mareo leve con sus lentes actuales."),
    "ojo_plano": ("Ve borroso de lejos con un solo ojo.",
                  "En el examen de manejo le dijeron que un ojo no ve igual que el otro."),
}
SEGUNDAS_LINEAS = ("Usa la computadora unas 8 horas al día.",
                   "Trabaja de noche y maneja con frecuencia.",
                   "Niega dolor, destellos y moscas volantes.",
                   "Niega visión doble y dolor de cabeza intenso.",
                   "Sin destellos, sombras ni cortinas en la visión.")
# Síntomas de alarma (urgencias) que el código certificado ya detecta.
URGENCIAS = ("Desde ayer ve destellos de luz y una cortina oscura en el ojo derecho.",
             "Visión doble de inicio súbito desde esta mañana.",
             "Pérdida súbita de visión en OI hace dos horas.",
             "Moscas volantes nuevas y destellos en OD desde anoche.",
             "Sombra que avanza desde abajo en la visión del OD desde hace un día.",
             "Destellos en el ojo izquierdo desde hace tres días.")
OCUPACIONES = ("Estudiante", "Contadora", "Chofer de transporte", "Docente", "Programador",
               "Ama de casa", "Comerciante", "Enfermera", "Albañil", "Jubilado")
LENTES_JOVEN = ("monofocal", "monofocal", "monofocal", None)
LENTES_PRESBITA = ("progresivo", "bifocal_blended", "flat_top", "monofocal", "progresivo")
FONDOS = ("Papilas de bordes nítidos, excavación 0.3 en ambos ojos, mácula con brillo foveal, retina aplicada.",
          "Papilas rosadas de bordes definidos, excavación 0.4 en ambos ojos, retina aplicada sin hemorragias.",
          "Creciente miópico peripapilar en ambos ojos, mácula sin alteraciones, retina aplicada.",
          "Papilas de bordes nítidos, excavación 0.2, cruces arteriovenosos sin alteraciones.")
ANEXOS = ("Párpados y pestañas sin alteraciones; conjuntiva clara.",
          "Bordes palpebrales con leve hiperemia y escamas en pestañas.",
          "Conjuntiva clara, córnea transparente.")


def _av(esfera, cilindro):
    """Agudeza sin corrección aproximada, solo para que el caso sea coherente."""
    poder = abs(esfera or 0) + abs(cilindro or 0) / 2
    for limite, av in ((0.5, "20/25"), (1.25, "20/40"), (2.5, "20/80"), (4, "20/200")):
        if poder <= limite:
            return av
    return "20/400"


def _ojo(esfera, cilindro=0.0, eje=180, add=None, av_cc="20/20"):
    ojo = dict(esfera=esfera, cilindro=cilindro, eje=eje if cilindro else None,
               av_sc=_av(esfera, cilindro), av_cc=av_cc)
    if add is not None:
        ojo["add"] = add
    return ojo


def _refraccion(categoria, i, edad):
    if categoria == "miopia_baja":
        e = -(0.50 + 0.25 * i)
        return _ojo(e, -0.50 if i % 2 else 0, 180), _ojo(e + 0.25 * (i % 3 == 0), -0.50 if i % 2 else 0, 175)
    if categoria == "miopia_alta":
        e = -(6.00 + 0.50 * i)
        return _ojo(e, -0.75, 10, av_cc="20/25"), _ojo(e + 0.50, -1.00, 170, av_cc="20/25")
    if categoria == "hipermetropia_baja":
        e = 0.75 + 0.25 * i
        return _ojo(e), _ojo(e - 0.25 * (i % 2))
    if categoria == "hipermetropia_alta":
        e = 4.00 + 0.50 * i
        return _ojo(e, -0.50, 90, av_cc="20/25"), _ojo(e - 0.25, -0.50, 90, av_cc="20/25")
    if categoria == "astigmatismo":
        cil = -(1.00 + 0.25 * i)
        eje = (10 + 17 * i) % 180 or 180
        return _ojo(-0.25 * (i % 3), cil, eje), _ojo(-0.25 * (i % 2), cil + 0.25, (180 - eje) or 180)
    if categoria == "presbita_add":
        e = (0.50, -0.75, 1.25, 0.0, -1.50, 0.75, -0.25, 1.75, -2.00, 0.25)[i]
        add = min(3.00, 0.75 + 0.25 * round((edad - 40) / 3))
        return _ojo(e, -0.50 if i % 3 == 0 else 0, 90, add), _ojo(e + 0.25 * (i % 2), 0, None, add)
    if categoria == "anisometropia":
        if i % 3 == 0:  # antimetropía
            return _ojo(1.00 + 0.25 * i), _ojo(-1.50 - 0.25 * i, av_cc="20/25")
        od = -(0.75 + 0.25 * i)
        return _ojo(od), _ojo(od - (2.00 + 0.25 * i), av_cc="20/25")
    if categoria == "ojo_plano":
        corregido = _ojo(-(1.25 + 0.25 * i), -0.50 if i % 2 else 0, 180)
        plano = _ojo(0.0, 0.0, None)
        return (corregido, plano) if i % 2 == 0 else (plano, corregido)
    if categoria == "sin_componentes_refractivos":
        return _ojo(0.0, 0.0, None), _ojo(0.0, 0.0, None)
    # datos_incompletos: falta la esfera, como lo manda Laravel cuando no se capturó.
    return dict(esfera=None, cilindro=0.0, eje=90), dict(esfera=None, cilindro=0.0, eje=90)


def _motivo(categoria, i, n):
    base = MOTIVOS[categoria][i % len(MOTIVOS[categoria])]
    if n % 8 == 3:
        return URGENCIAS[(n // 8) % len(URGENCIAS)] + "\n" + base
    if n % 3 == 0:
        return base + "\n" + SEGUNDAS_LINEAS[(n // 3) % len(SEGUNDAS_LINEAS)]
    return base


def _clinica(categoria, i, n, edad):
    clinica = dict(uso_pantallas=("lt2", "btw2_6", "gt6")[n % 3])
    if n % 4 == 1:
        return clinica  # El optometrista no siempre llena toda la exploración.
    clinica.update(
        anexos_oculares=ANEXOS[n % len(ANEXOS)],
        reflejos_pupilares="Reflejo fotomotor, consensual y acomodativo presentes.",
        motilidad_ocular="Versiones: Suaves y completas Ducciones: Libres Sacadicos: Adecuados Seguimiento: Continuo",
        confrontacion_campos_visuales="Sin defectos periféricos evidentes.",
        fondo_de_ojo=FONDOS[2] if categoria == "miopia_alta" else FONDOS[n % len(FONDOS)],
        grid_de_amsler="Sin alteraciones.",
        cover_test="OD: Endo | OI: Orto" if categoria == "hipermetropia_alta" and edad < 12 else "OD: Orto | OI: Orto",
        ojo_seco_but_seg=6 + n % 7,
        ppc_cm=6 + n % 5,
        recomendacion_seguimiento=("Se recomienda revisión optométrica de control. Próxima cita en: "
                                   + ("6 meses" if edad < 18 else "12 meses")),
    )
    return clinica


def _akr(od, oi):
    def lado(ojo):
        e = (ojo.get("esfera") or 0) - 0.25
        return dict(esfera=e, cilindro=ojo.get("cilindro") or 0, eje=ojo.get("eje") or 180,
                    k1_d=43.00, k1_mm=7.85, k1_eje=180, k2_d=43.75, k2_mm=7.71, k2_eje=90,
                    k_promedio_d=43.37, k_promedio_mm=7.78, k_cilindro=-0.75, k_cilindro_eje=180)
    return dict(taken_at="2026-11-01 10:00:00", pd=62.5, vd=12.0, ker_index=1.3375, od=lado(od), oi=lado(oi))


# Cinco casos de entrada máxima representativa: textos largos pero clínicamente plausibles.
MAXIMOS = {
    14: dict(  # miopía alta, 31 años
        motivo=("Usa lentes desde los 8 años y cada año siente que la graduación sube.\n"
                "Refiere visión borrosa de lejos aun con sus lentes actuales, sobre todo al manejar de noche y al ver "
                "los letreros de la carretera.\n"
                "Trabaja como diseñadora gráfica frente a dos monitores unas 9 horas al día y termina con ardor, "
                "lagrimeo y sensación de arenilla.\n"
                "Pregunta por micas más delgadas y por lentes de contacto para hacer deporte.\n"
                "Niega dolor, destellos, moscas volantes nuevas y sombras en la visión.\n"
                "Antecedente familiar: su madre usa lentes de alta graduación; no conoce otros padecimientos oculares en la familia."),
        ocupacion="Diseñadora gráfica; trabaja frente a dos monitores unas 9 horas al día y maneja de noche.",
        fondo=("OD: papila inclinada con creciente miópico temporal, excavación 0.3, mácula con brillo foveal, "
               "retina aplicada; degeneración en empalizada en periferia temporal inferior sin agujeros ni desgarros.\n"
               "OI: creciente miópico peripapilar, excavación 0.3, mácula sin alteraciones, retina aplicada en los cuatro cuadrantes.")),
    52: dict(  # presbicia, 48 años
        motivo=("Desde hace un año necesita alejar el celular y el periódico para poder leer.\n"
                "Usa lentes de lectura de farmacia de +1.50, pero se le cansa la vista después de media hora y le duele "
                "la frente al final del día.\n"
                "Trabaja como contadora con hojas de cálculo y documentos impresos; alterna entre la computadora y el papel.\n"
                "Maneja de noche y siente que los faros de los autos la deslumbran.\n"
                "Niega visión doble, dolor ocular y pérdida súbita de visión.\n"
                "Tiene diabetes tipo 2 desde hace 6 años, controlada con metformina; su último control fue hace 4 meses."),
        ocupacion="Contadora; alterna computadora y documentos impresos, maneja de noche.",
        fondo=("OD: papila de bordes nítidos, excavación 0.4, cruces arteriovenosos sin alteraciones, mácula sin "
               "exudados ni hemorragias, retina aplicada.\n"
               "OI: papila de bordes nítidos, excavación 0.4, sin microaneurismas ni hemorragias visibles, retina aplicada.")),
    63: dict(  # anisometropía, 19 años
        motivo=("Refiere que con el ojo izquierdo siempre ha visto peor y que en la escuela le dijeron que tenía un ojo flojo.\n"
                "Con sus lentes actuales siente mareo al bajar escaleras y le cuesta calcular distancias al estacionarse.\n"
                "Estudia ingeniería y pasa muchas horas leyendo en la computadora y en el celular.\n"
                "Le arden los ojos al final del día y a veces se le juntan las letras.\n"
                "Niega destellos, moscas volantes, sombras y dolor ocular."),
        ocupacion="Estudiante de ingeniería; lectura prolongada en computadora y celular.",
        fondo=("OD: papila de bordes nítidos, excavación 0.3, mácula con brillo foveal, retina aplicada.\n"
               "OI: papila de bordes nítidos, excavación 0.3, mácula sin alteraciones, retina aplicada; sin lesiones en periferia.")),
    46: dict(  # astigmatismo, 37 años
        motivo=("Ve las letras borrosas y como barridas de cerca y de lejos desde hace varios años.\n"
                "De noche las luces de los autos y del alumbrado se ven estiradas, lo que le dificulta manejar.\n"
                "Presenta dolor de cabeza frontal al final de la jornada y se talla los ojos con frecuencia.\n"
                "Trabaja como chofer de transporte de personal en turnos nocturnos.\n"
                "Niega dolor ocular intenso, visión doble y destellos."),
        ocupacion="Chofer de transporte de personal en turnos nocturnos.",
        fondo=("OD: papila de bordes nítidos, excavación 0.3, retina aplicada, mácula con brillo foveal.\n"
               "OI: papila de bordes nítidos, excavación 0.3, retina aplicada, sin alteraciones vasculares.")),
    32: dict(  # hipermetropía alta, niño de 7 años, informante
        motivo=("La mamá refiere que desde hace unos meses el niño desvía el ojo derecho hacia adentro cuando está "
                "cansado o cuando ve la tableta de cerca.\n"
                "En la escuela la maestra comentó que se acerca mucho al cuaderno y que se frota los ojos.\n"
                "Se queja de dolor de cabeza por la tarde y a veces cierra un ojo para ver la televisión.\n"
                "Nació a término, sin complicaciones; nunca ha usado lentes.\n"
                "La mamá niega que el niño vea doble y niega golpes en la cabeza."),
        ocupacion="Estudiante de primaria.",
        fondo=("OD: papila de bordes nítidos y color normal, excavación 0.2, mácula con brillo foveal, retina aplicada.\n"
               "OI: papila de bordes nítidos, excavación 0.2, mácula con brillo foveal, retina aplicada.")),
}


def _maximo(req, datos):
    req["paciente"]["motivo_consulta"] = datos["motivo"]
    req["paciente"]["ocupacion"] = datos["ocupacion"]
    req["clinica"].update(
        anexos_oculares=("OD: bordes palpebrales con leve hiperemia y escamas finas en la base de las pestañas; conjuntiva "
                         "bulbar con hiperemia leve interpalpebral.\nOI: hallazgos similares, sin secreción; córnea transparente "
                         "en ambos ojos con tinción puntiforme inferior leve."),
        reflejos_pupilares="Pupilas isocóricas, redondas y reactivas a la luz; reflejo fotomotor, consensual y acomodativo presentes; sin defecto pupilar aferente.",
        motilidad_ocular="Versiones: Suaves y completas Ducciones: Libres Sacadicos: Adecuados Seguimiento: Continuo",
        confrontacion_campos_visuales="Campos por confrontación sin defectos periféricos evidentes en ambos ojos, en los cuatro cuadrantes.",
        fondo_de_ojo=datos["fondo"],
        grid_de_amsler="OD: líneas rectas, sin distorsión ni áreas faltantes.\nOI: líneas rectas, sin distorsión ni áreas faltantes.",
        cover_test="OD: Endo | OI: Orto" if "niño" in datos["motivo"] else "OD: Orto | OI: Orto",
        ojo_seco_but_seg=5,
        ppc_cm=10,
        recomendacion_seguimiento=("Se recomienda control optométrico con la nueva graduación, uso de lubricante ocular "
                                   "sin conservadores y pausas visuales cada 20 minutos frente a pantallas. "
                                   "Próxima cita en: 6 meses"),
    )


def generar():
    recetas = []
    for n in range(100):
        k, i = n // 10, n % 10
        categoria = CATEGORIAS[k]
        edad = EDADES[categoria][i]
        od, oi = _refraccion(categoria, i, edad)
        no_elegible = categoria in ("sin_componentes_refractivos", "datos_incompletos")
        # Caso sin perfil educativo: no se añaden hallazgos, lente ni síntomas.
        req = dict(receta_id=f"gpu-r-{n:03}", salida_version="clinica-paciente-v1",
                   paciente=dict(edad=edad), refraccion=dict(od=od, oi=oi), clinica={}, tipo_lente=None)
        if not no_elegible:
            req["paciente"]["motivo_consulta"] = _motivo(categoria, i, n)
            req["paciente"]["ocupacion"] = OCUPACIONES[n % len(OCUPACIONES)] if edad >= 18 else "Estudiante"
            req["clinica"] = _clinica(categoria, i, n, edad)
            req["tipo_lente"] = (LENTES_PRESBITA[i % len(LENTES_PRESBITA)] if categoria == "presbita_add"
                                 else LENTES_JOVEN[n % len(LENTES_JOVEN)])
        maximo = n in MAXIMOS
        if maximo or (not no_elegible and n % 3 == 0):
            req["akr"] = _akr(od, oi)
        if maximo:
            _maximo(req, MAXIMOS[n])
        recetas.append(dict(id=f"R{n+1:03}", categoria=categoria,
            elegible_personalizacion=not no_elegible, entrada_maxima=maximo, payload=req))
    whatsapps = []
    for n in range(50):
        r = recetas[n * 2 % 80]["payload"]["refraccion"]  # solo recetas con graduación completa
        rx = {lado: {c: r[lado].get(c) for c in ("esfera", "cilindro", "add")} for lado in ("od", "oi")}
        estado = "vencido" if n % 2 else "proximo"
        costo = "incluida" if n % 4 < 2 else "con_costo"
        tramo = ("18_39", "40_59", "60_mas")[n % 3]
        req = dict(contrato_version="seguimiento-whatsapp-v1", paciente_ref=f"{n+1:016x}",
            tramo_edad=tramo, estado_seguimiento=estado,
            meses_desde_ultima_receta=None if n % 11 == 0 else 6 + n % 19,
            recetas_previas=n % 5, costo=costo,
            ya_notificado_en_ciclo=bool(n % 3), variante=n,
            rx_lejos=None if n % 10 == 9 else rx,
            tipo_lente=(None, "monofocal", "bifocal", "progresivo", "otro")[n % 5],
            uso_pantallas=(None, "lt2", "btw2_6", "gt6")[n % 4],
            usa_armazon=(None, True, False)[n % 3])
        whatsapps.append(dict(id=f"W{n+1:03}", categoria=f"{estado}_{costo}_{tramo}",
            elegible_personalizacion=True, payload=req))
    return dict(version="corpus-gpu-v2", recetas=recetas, whatsapp=whatsapps)


def guardar(destino=DESTINO):
    destino.mkdir(parents=True, exist_ok=True)
    data = json.dumps(generar(), ensure_ascii=False, indent=2) + "\n"
    (destino / "corpus.json").write_bytes(data.replace("\n", "\r\n").encode("utf-8"))


def cargar():
    return json.loads((DESTINO / "corpus.json").read_text(encoding="utf-8"))


def huella():
    return hashlib.sha256((DESTINO / "corpus.json").read_bytes()).hexdigest()


if __name__ == "__main__":
    guardar()
