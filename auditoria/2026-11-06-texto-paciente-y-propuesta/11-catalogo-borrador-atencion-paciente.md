# Borrador del catálogo de hechos — WhatsApp de seguimiento

> **Para revisión y firma del optometrista.** Nada de este documento se usa con pacientes hasta que usted lo apruebe. Puede cambiar cualquier palabra, quitar hechos o pedir otros. Las marcas "Nota para el optometrista" señalan las frases que conviene mirar con más cuidado.

**Datos que usan las reglas (y ningún otro):**

| Dato | Valores |
|---|---|
| `correccion` | conjunto de: `miopia`, `hipermetropia`, `astigmatismo` (derivado de la última receta de lejos) |
| `apoyo_cerca` | `sí` / `no` (hay ADD en la última receta) |
| `tramo_edad` | `18-39`, `40-59`, `60+` (menores: no reciben mensaje personalizado) |
| `estado` | `proxima`, `vencida` |
| `costo` | `incluida`, `con_costo` |
| `pantallas` | `lt2`, `btw2_6`, `gt6`, o sin registro |
| `tipo_lente` | `monofocal`, `bifocal`, `progresivo`, o sin registro |

**Decisión de diseño:** ningún hecho depende de `tramo_edad`. Así se evita que la edad "desbloquee" frases que insinúen envejecimiento o cambios por la edad. La edad solo sirve para que Qwen ajuste el tono de la apertura y la invitación (siempre sin afirmaciones clínicas).

---

## 1. Catálogo de hechos (20)

Cada hecho es una oración independiente, en usted, sin cifras, sin miedo, sin promesas y sin afirmar nada sobre el estado actual del paciente. El servidor la inserta **literal**.

### Grupo A: según la corrección y el tipo de lente

| id | grupo | Texto exacto | Regla de elegibilidad | Por qué le ayuda al paciente | Palabras |
|---|---|---|---|---|---|
| `miopia_ajuste` | miopía | Con el tiempo la miopía puede cambiar, y revisarla periódicamente permite ajustar sus lentes cuando haga falta. | `correccion incluye miopia` | Entiende por qué conviene revisar aunque hoy vea bien, sin sentir alarma. | 17 |
| `miopia_lejos` | miopía | En la revisión comprobamos que sus lentes le sigan ofreciendo una visión de lejos cómoda para manejar, caminar o leer letreros. | `correccion incluye miopia` | Relaciona la revisión con actividades concretas de su vida diaria. | 21 |
| `hipermetropia_ajuste` | hipermetropía | La graduación para la hipermetropía puede necesitar ajustes con el tiempo, y la revisión periódica nos permite saber si hace falta alguno. | `correccion incluye hipermetropia` | Sabe que la revisión sirve para decidir con información, no por suposición. | 22 |
| `hipermetropia_cerca` | hipermetropía | Con hipermetropía, unos lentes con la graduación adecuada ayudan a que enfocar, sobre todo en tareas de cerca, le resulte más cómodo. | `correccion incluye hipermetropia` | Conecta la revisión con su comodidad al leer o trabajar de cerca. | 22 |
| `astigmatismo_detalle` | astigmatismo | En el astigmatismo, pequeños ajustes en la graduación pueden marcar una diferencia en la comodidad, por eso conviene revisarla periódicamente. | `correccion incluye astigmatismo` | Explica, sin tecnicismos, por qué vale la pena una revisión cuidadosa. | 20 |
| `astigmatismo_comodidad` | astigmatismo | Con astigmatismo, una graduación revisada y un armazón bien ajustado ayudan a que sus lentes se sientan más cómodos. | `correccion incluye astigmatismo` | Le muestra un beneficio tangible: lentes más cómodos en el día a día. | 19 |
| `cerca_adecuado` | apoyo de cerca | Revisar su graduación ayuda a confirmar que su apoyo para ver de cerca siga siendo el adecuado para lo que usted hace. | `apoyo_cerca = sí` | Le da la tranquilidad de que su apoyo de cerca corresponde a sus actividades. | 22 |
| `cerca_distancias` | apoyo de cerca | Si lee o usa el celular con frecuencia, en la consulta podemos revisar su apoyo de cerca según las distancias que más utiliza. | `apoyo_cerca = sí` | Personaliza la revisión a cómo usa realmente sus ojos de cerca. | 23 |
| `progresivo_zonas` | progresivo | En sus lentes progresivos revisamos que la zona de lejos, la intermedia y la de cerca sigan acomodándose a sus actividades. | `tipo_lente = progresivo` | Le recuerda que sus progresivos tienen varias zonas y todas cuentan para su comodidad. | 21 |
| `progresivo_ajuste` | progresivo | En los lentes progresivos, la altura y el ajuste del armazón influyen mucho en la comodidad, y en la revisión los verificamos con calma. | `tipo_lente = progresivo` | Si se ha sentido incómodo con ellos, sabe que hay algo concreto que se puede revisar. | 24 |
| `bifocal_zonas` | bifocal | En sus lentes bifocales revisamos que la parte de lejos y la de cerca sigan acomodándose a lo que usted hace. | `tipo_lente = bifocal` | Relaciona la revisión con las dos partes de su lente y sus actividades. | 21 |
| `ajuste_armazon` | armazón | Además de la graduación, revisamos el ajuste de su armazón, que también influye en lo cómodos que se sienten sus lentes. | `tipo_lente ∈ {monofocal, bifocal}` | Sabe que la revisión también cuida detalles prácticos como el ajuste del armazón. | 21 |

> **Nota para el optometrista:** `hipermetropia_cerca` y `astigmatismo_comodidad` usan "ayudan a que…": es una afirmación general, no una promesa al paciente. Si prefiere un tono más prudente, puede cambiarse por "pueden ayudar a que…". En `cerca_distancias` puede agregar otras actividades de cerca comunes entre sus pacientes, siempre que la frase no pase de 25 palabras.

### Grupo B: contexto (pantallas, estado de la revisión, costo, utilidad general)

| id | grupo | Texto exacto | Regla de elegibilidad | Por qué le ayuda al paciente | Palabras |
|---|---|---|---|---|---|
| `pantallas_muchas` | pantallas | Si pasa muchas horas frente a pantallas, en la revisión podemos ver qué tan cómodos le resultan sus lentes para ese trabajo. | `pantallas = gt6` | Reconoce su rutina real y le ofrece atención a su comodidad frente a pantallas. | 22 |
| `pantallas_ratos` | pantallas | Si usa pantallas durante parte del día, en la revisión podemos platicar sobre distancias y pausas que le resulten cómodas. | `pantallas = btw2_6` | Le ofrece orientación práctica y útil, más allá de la graduación. | 20 |
| `vencida_retomar` | estado | Si ha pasado un tiempo desde su última revisión, retomarla es sencillo y la hacemos a su ritmo, sin prisas. | `estado = vencida` | Le quita la pena o la incomodidad de "haberse atrasado", sin reproche. | 20 |
| `incluida_sin_costo` | costo | Su revisión de seguimiento está incluida en su atención, sin ningún costo adicional para usted. | `costo = incluida` | Sabe con certeza que puede venir sin preocuparse por un gasto. | 15 |
| `con_costo_claro` | costo | La revisión tiene un costo, y con gusto le informamos el monto antes de agendar para que decida con calma. | `costo = con_costo` | Recibe información honesta desde el inicio y decide sin sorpresas. | 20 |
| `comodidad_general` | comodidad | Si algo de sus lentes le incomoda o nota que ya no le acomodan igual, la revisión es un buen momento para comentarlo. | siempre | Le da permiso de expresar molestias que quizá no pensaba mencionar. | 23 |
| `general_periodica` | general | La revisión periódica nos permite confirmar que sus lentes sigan acompañándole bien en sus actividades de todos los días. | siempre | Sirve a cualquier paciente: explica para qué es la revisión sin suponer nada sobre él. | 19 |
| `traer_lentes` | práctico | Le sugerimos traer los lentes que usa actualmente, así podemos revisarlos junto con su graduación. | siempre | Le facilita la visita y aprovecha mejor su tiempo en la consulta. | 15 |

> **Nota para el optometrista:** `con_costo_claro` no da cifra a propósito (prohibido mencionar precios); solo anuncia con honestidad que la revisión tiene costo. `traer_lentes` es una recomendación práctica más que un "hecho"; se incluye porque es útil para todos y no afirma nada clínico.

---

## 2. Reglas de combinación

### 2.1 Límite

- **Máximo 2 hechos por mensaje.** Se permite 0 (el mensaje se arma solo con apertura e invitación).
- **Como máximo 1 hecho del Grupo A y 1 del Grupo B.** Solo si no hay ningún hecho del Grupo A elegible, se permiten 2 del Grupo B (respetando las parejas prohibidas).
- **Nunca dos hechos del mismo grupo** (por ejemplo, `miopia_ajuste` + `miopia_lejos`, o `progresivo_zonas` + `progresivo_ajuste`).

### 2.2 Parejas que se deben evitar

| Pareja | Motivo |
|---|---|
| `vencida_retomar` + `miopia_ajuste` / `hipermetropia_ajuste` / `astigmatismo_detalle` | "Ha pasado un tiempo" junto a "puede cambiar" insinúa que su graduación ya cambió; suena a presión y a afirmar algo sobre su estado. |
| `vencida_retomar` + `con_costo_claro` | Juntar "se le pasó" con "tiene costo" suena a cobro o a reclamo. |
| `cerca_adecuado` / `cerca_distancias` + `progresivo_zonas` / `bifocal_zonas` | Redundante: las zonas del lente ya incluyen la de cerca. |
| `comodidad_general` + cualquier otro hecho de comodidad (`pantallas_muchas`, `astigmatismo_comodidad`, `hipermetropia_cerca`, `ajuste_armazon`, `progresivo_ajuste`) | Dos frases sobre "comodidad" seguidas suenan repetitivas. |
| `ajuste_armazon` + `astigmatismo_comodidad` | Las dos hablan del armazón. |
| `general_periodica` + `miopia_ajuste` / `hipermetropia_ajuste` / `astigmatismo_detalle` | Repiten la idea de "revisión periódica". |
| `general_periodica` + `traer_lentes` | Válida solo cuando no hay nada más elegible; nunca si hay alternativas más personales. |

**Reglas para la prosa de Qwen (apertura e invitación) según los hechos elegidos:**

- Si se usa `incluida_sin_costo`, la invitación **no** repite que es sin costo.
- Si `costo = con_costo` y **no** se usa `con_costo_claro`, la invitación **debe** decir con honestidad que la revisión tiene costo (sin cifra). Nunca puede decir "sin costo", "gratis" ni "incluida".
- Si `estado = vencida`, ni la apertura ni la invitación pueden decir "atrasado", "pendiente desde hace", "ya se le pasó" ni nada parecido.

### 2.3 Prioridad sugerida cuando hay más de 2 elegibles

**Hueco A (uno, el más personal):**

1. Si `tipo_lente` es `progresivo` o `bifocal`: `progresivo_zonas` o `bifocal_zonas`.
2. Si no, y `apoyo_cerca = sí`: `cerca_adecuado`.
3. Si no, por corrección: `miopia_ajuste` > `hipermetropia_ajuste` > `astigmatismo_detalle`.

**Hueco B (uno, de contexto):**

1. `pantallas_muchas`
2. `vencida_retomar`
3. `pantallas_ratos`
4. `incluida_sin_costo` / `con_costo_claro` (este último cuando la invitación no lo cubra)
5. `comodidad_general`
6. `general_periodica`
7. `traer_lentes`

**Variedad entre ciclos:** las segundas opciones de cada grupo (`miopia_lejos`, `hipermetropia_cerca`, `astigmatismo_comodidad`, `cerca_distancias`, `progresivo_ajuste`, `ajuste_armazon`) existen para que el paciente no reciba la misma frase cada vez. Sugerencia: si el último mensaje aprobado usó la primera opción de un grupo, este ciclo se prefiere la segunda (respetando las parejas prohibidas).

### 2.4 Línea para no recibir más mensajes

Se sugiere que el **servidor** agregue siempre, al final y como línea fija, el texto: *"Si prefiere no recibir estos recordatorios, solo díganoslo."* No la escribe Qwen y no cuenta para el rango de 50 a 110 palabras. El validador D-14 debe revisar que la **invitación** termine en pregunta (la línea fija va después).

---

## 3. Genérico corregido (respaldo sin IA)

Reemplazos propuestos para `lang/es/whatsapp.php`. Se mantiene el estilo actual (negritas de WhatsApp con `*…*` y saltos `\n\n`). Cada uno sirve igual para revisión próxima o vencida.

### `seguimiento.sin_costo` (63 palabras)

```
Hola :paciente, le saludamos de *:clinica*.

Según su expediente, es momento de su revisión visual de seguimiento, que está *incluida en su atención, sin costo* para usted.

Revisar su graduación periódicamente nos permite confirmar que sus lentes sigan siendo cómodos y adecuados para sus actividades.

¿Le gustaría que le busquemos un horario que le acomode?

Si prefiere no recibir estos recordatorios, solo díganoslo.
```

### `seguimiento.con_costo` (73 palabras)

```
Hola :paciente, le saludamos de *:clinica*.

Según su expediente, es momento de su revisión visual periódica. Le comentamos que esta revisión tiene costo; con gusto le informamos el monto antes de agendar, para que decida con calma.

Revisar su graduación periódicamente nos permite confirmar que sus lentes sigan siendo cómodos y adecuados para sus actividades.

¿Le gustaría que le busquemos un horario que le acomode?

Si prefiere no recibir estos recordatorios, solo díganoslo.
```

**Qué cambia respecto al texto actual:** se quita "garantizar" y "mantengan óptimos" (promesa); se quita "prevenir la fatiga visual" (afirmación clínica con tono de promesa); la variante con costo ahora dice con honestidad que tiene costo; "esta semana" se cambia por "un horario que le acomode" (sin urgencia); se agrega la línea para no recibir más mensajes.

---

## 4. Tres mensajes de ejemplo

Cada parte va marcada. `[cierre fijo]` es la línea del servidor (no cuenta para el rango). El conteo de palabras es de apertura + hechos + invitación, con `:paciente` y `:clinica` contados como una palabra cada uno.

### Ejemplo 1: adulto (18–39), miopía, más de 6 h de pantallas, revisión próxima, incluida

Datos: `correccion = {miopia}`, `pantallas = gt6`, `tipo_lente = monofocal`, `estado = proxima`, `costo = incluida`.
Hechos elegidos: `miopia_ajuste` (hueco A) + `pantallas_muchas` (hueco B).

> **[apertura · Qwen]** Hola :paciente, le saludamos de :clinica. Se acerca la fecha de su revisión visual de control y quisimos recordársela con tiempo.
> **[hecho · catálogo]** Con el tiempo la miopía puede cambiar, y revisarla periódicamente permite ajustar sus lentes cuando haga falta.
> **[hecho · catálogo]** Si pasa muchas horas frente a pantallas, en la revisión podemos ver qué tan cómodos le resultan sus lentes para ese trabajo.
> **[invitación · Qwen]** Su revisión está incluida en su atención y nosotros le buscamos el horario que mejor le acomode. ¿Le gustaría que le apartemos una cita en los próximos días?
> **[cierre fijo]** Si prefiere no recibir estos recordatorios, solo díganoslo.

Palabras: 88.

### Ejemplo 2: 60+, lentes progresivos, revisión vencida, incluida

Datos: `correccion = {hipermetropia}`, `apoyo_cerca = sí`, `tipo_lente = progresivo`, `estado = vencida`, `costo = incluida`.
Hechos elegidos: `progresivo_zonas` (hueco A, tiene prioridad sobre `cerca_adecuado` y evita la pareja redundante) + `vencida_retomar` (hueco B). No se usa `hipermetropia_ajuste` porque está prohibido junto a `vencida_retomar`.

> **[apertura · Qwen]** Hola :paciente, reciba un cordial saludo de :clinica. Le escribimos para recordarle su revisión visual de seguimiento y saber cómo le podemos ayudar.
> **[hecho · catálogo]** En sus lentes progresivos revisamos que la zona de lejos, la intermedia y la de cerca sigan acomodándose a sus actividades.
> **[hecho · catálogo]** Si ha pasado un tiempo desde su última revisión, retomarla es sencillo y la hacemos a su ritmo, sin prisas.
> **[invitación · Qwen]** La revisión está incluida en su atención, y con gusto le buscamos el día y la hora que le resulten más cómodos. ¿Le parece si le apartamos un espacio?
> **[cierre fijo]** Si prefiere no recibir estos recordatorios, solo díganoslo.

Palabras: 93.

### Ejemplo 3: 40–59, astigmatismo, revisión próxima, con costo

Datos: `correccion = {astigmatismo}`, `apoyo_cerca = no`, `tipo_lente = monofocal`, `pantallas` sin registro, `estado = proxima`, `costo = con_costo`.
Hechos elegidos: `astigmatismo_detalle` (hueco A) + `con_costo_claro` (hueco B; con él la invitación ya no necesita mencionar el costo).

> **[apertura · Qwen]** Hola :paciente, le saludamos de :clinica. Se acerca el momento de su revisión visual periódica y quisimos avisarle con anticipación.
> **[hecho · catálogo]** En el astigmatismo, pequeños ajustes en la graduación pueden marcar una diferencia en la comodidad, por eso conviene revisarla periódicamente.
> **[hecho · catálogo]** La revisión tiene un costo, y con gusto le informamos el monto antes de agendar para que decida con calma.
> **[invitación · Qwen]** Nosotros nos encargamos de buscarle un horario que se acomode a sus actividades. ¿Le gustaría que le compartamos los horarios disponibles?
> **[cierre fijo]** Si prefiere no recibir estos recordatorios, solo díganoslo.

Palabras: 81.

---

## 5. Puntos para que el optometrista decida

1. ¿Aprueba que **ningún hecho dependa de la edad**?
2. ¿Prefiere "ayudan a que" o "pueden ayudar a que" en `hipermetropia_cerca` y `astigmatismo_comodidad`?
3. ¿Aprueba que la línea para no recibir más mensajes la agregue siempre el servidor, fuera del conteo?
4. ¿Quiere conservar `traer_lentes` aunque sea una recomendación práctica y no un hecho?
5. ¿Hay alguna actividad de los ejemplos (manejar, caminar, leer letreros, usar el celular) que prefiera cambiar por otras más comunes entre sus pacientes?

Firma del optometrista: ______________________  Fecha: ____________  Versión del catálogo: `v1-borrador`
