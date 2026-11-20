# Catálogo de WhatsApp de seguimiento y guía de trato al paciente

**Estado: v2-borrador-2026-11-20 (contrato `seguimiento-whatsapp-v2`), pendiente de la firma del optometrista.** El objetivo del mensaje es que el paciente cuente cómo le han funcionado sus lentes; la cita se ofrece como opción suave. El texto vive en `app/seguimiento/catalogo.py` y una prueba exige que coincida con este documento, así que ambos se cambian juntos.
Lo prepararon tres agentes especializados (Psicólogo, Atención al paciente en salud y Evidencia Clínica) y lo consolidó Claude; la versión v2 se rediseñó el 2026-11-20.

**Idea central: invitamos a una persona a cuidarse, no perseguimos una venta.** Si el paciente dice que no, la relación sigue intacta.

---

## 1. Ocho técnicas para tratar al paciente con delicadeza

> La evidencia citada tiene solidez desigual y proviene de otros países y contextos de salud. Es una guía de criterio, no una garantía de resultados.

| # | Técnica | Base | Hacer | Evitar | Frase de ejemplo |
|---|---|---|---|---|---|
| P1 | **La decisión es del paciente** | Teoría de la autodeterminación (Deci y Ryan); reactancia (Brehm); técnica «usted es libre de decidir» | Ofrecer, no ordenar; dejar la puerta abierta | «debe», «tiene que», «es necesario», «no lo deje pasar» | «Usted decide cuándo le acomoda; aquí estamos cuando lo necesite.» |
| P2 | **Escuchar antes de proponer** | Entrevista motivacional (Miller y Rollnick): preguntas abiertas, reflejar, resumir; evocar las razones del paciente | Reflejar lo que dijo y preguntar qué le serviría | Corregir, discutir, soltar una lista de razones | «Entiendo que estas semanas están muy cargadas. ¿Qué le facilitaría venir?» |
| P3 | **Cuidado sin miedo ni culpa** | Los mensajes de miedo sin sensación de control provocan evasión (Witte; metaanálisis de Tannenbaum, 2015) | Hablar de comodidad, acompañamiento y tener la revisión al día | Consecuencias, «antes de que sea tarde», reproches por el tiempo | «Nos dará gusto recibirle cuando a usted le quede bien.» |
| P4 | **Claridad** | Alfabetización en salud: lenguaje llano, una idea por oración; por teléfono, «enseñar de vuelta» | Frases cortas y un solo pedido por mensaje | Tecnicismos, párrafos largos, varias preguntas juntas | «Solo responda este mensaje y le buscamos un horario.» |
| P5 | **Poner las cosas fáciles** | Reducción de fricción (marco EAST) | «Nosotros le agendamos»; aceptar respuestas de una palabra | «Llame al conmutador», pedir datos que ya tenemos | «Con que nos diga mañana o tarde, nosotros nos encargamos.» |
| P6 | **Del «sí» a un plan concreto** | Intenciones de implementación (Gollwitzer; efectos más modestos en estudios recientes) | Si ya mostró interés, fijar día y hora y confirmar | «¿Martes o jueves?» con quien aún no aceptó | «¿Qué día de la semana le resulta más cómodo?» |
| P7 | **Reciprocidad genuina y costo verdadero** | Reciprocidad (Cialdini): legítima si se da sin condición | Decir con claridad si está incluida o tiene costo | Ocultar el costo, regalos condicionados, «ya le apartamos el lugar» sin pedirlo | «La revisión tiene un costo; con gusto le damos el detalle antes de que decida.» |
| P8 | **Respetar el no y el silencio** | La confianza a largo plazo vale más que una cita; insistir aumenta el rechazo | Aplicar el límite de recordatorios y atender la baja de inmediato | «¿Seguro?», pedir explicaciones, volver a escribir tras un no | «Con gusto. Ya no le enviaremos recordatorios; aquí estamos si algún día nos necesita.» |

### La línea roja entre persuadir y manipular
**Prueba de tres preguntas:**
1. ¿Se lo diría igual si el paciente supiera exactamente por qué lo dice?
2. ¿Le conviene al paciente aunque no agende?
3. ¿Puede decir que no sin sentirse mal?

Si alguna respuesta es «no», es manipulación.

| Permitido | Prohibido |
|---|---|
| Recordar con anticipación | Urgencia falsa («solo esta semana») |
| Información verdadera y relevante (los hechos firmados) | Escasez falsa («quedan pocos lugares») |
| Facilidad («nosotros le agendamos») | Miedo («antes de que sea tarde», consecuencias) |
| Decir el costo con claridad | Culpa («lleva mucho sin venir», «se ha descuidado») |
| Ofrecer opciones concretas a quien ya mostró interés | Prueba social inventada («la mayoría ya agendó») |
| «Usted decide» | Anclaje de precio, descuentos inventados |
| Calidez y agradecimiento | Regalos condicionados a agendar |
| Una pregunta final abierta | Avergonzar a quien se niega; «debe», «tiene que» |
| | Promesas («garantizamos», «verá perfecto») |
| | Mencionar datos que el paciente no espera que conozcamos |
| | Pasar el límite de recordatorios o ignorar una baja |

### Tono por perfil, sin estereotipos
El perfil cambia el tono, no el respeto. **Nunca se menciona la edad ni se deduce envejecimiento.**

| Perfil | Tono | Motivación |
|---|---|---|
| 18–39 años | Breve y ágil | Que sea práctico y no le quite tiempo |
| 40–59 años | Directo y respetuoso de su agenda | Organizarse con anticipación |
| 60 años o más | Cálido y pausado, **sin infantilizar** (nada de diminutivos ni «abuelito») | Acompañamiento y trato cercano |
| Muchas horas de pantalla | Comprensivo con sus ocupaciones | Comodidad en el día a día (el contenido lo pone el hecho, no la apertura) |
| Revisión vencida | Sin reproche, como un nuevo comienzo | «Retomar», nunca «se atrasó» |
| Con costo | Transparente | Decidir con información (sin cifra en el mensaje) |
| Sin costo | Sencillo | Que el costo no sea obstáculo |

---
---

## 2. Catálogo v2 consolidado (fuente de los textos para el código)

**Versión:** `v2-borrador-2026-11-20`.

### 2.1 Frases de uso (`FU_<etiqueta>_<n>`)
| ID | Texto |
|---|---|
| `FU_ver_de_lejos_1` | Pensamos en sus lentes para ver de lejos y en cómo le han acompañado en este tiempo. |
| `FU_ver_de_lejos_2` | Nos acordamos de sus lentes para ver de lejos, para la calle y para todo lo que mira a distancia. |
| `FU_ver_de_cerca_1` | Pensamos en sus lentes para ver de cerca, para leer o usar el celular. |
| `FU_ver_de_cerca_2` | Nos acordamos de sus lentes para leer y para las cosas que hace de cerca. |
| `FU_computadora_1` | Pensamos en sus lentes y en cómo le han acompañado frente a la computadora y otras pantallas. |
| `FU_computadora_2` | Nos acordamos de sus lentes y del tiempo que pasa frente a la computadora y otras pantallas en su día. |
| `FU_lejos_y_cerca_1` | Pensamos en sus lentes para ver tanto de lejos como de cerca. |
| `FU_lejos_y_cerca_2` | Nos acordamos de sus lentes para pasar de ver de lejos a ver de cerca durante el día. |
| `FU_estudiar_1` | Pensamos en sus lentes y en cómo le han acompañado en sus estudios. |
| `FU_estudiar_2` | Nos acordamos de sus lentes para sus clases y sus horas de estudio. |
| `FU_trabajar_1` | Pensamos en sus lentes para sus actividades de trabajo. |
| `FU_trabajar_2` | Nos acordamos de sus lentes para su jornada de trabajo. |
| `FU_manejar_1` | Pensamos en sus lentes y en cómo le han acompañado cuando maneja. |
| `FU_manejar_2` | Nos acordamos de sus lentes y de sus trayectos cuando maneja. |
| `FU_desconocido_1` | Pensamos en sus lentes y en cómo le han funcionado en su día a día. |
| `FU_desconocido_2` | Nos acordamos de sus lentes y de lo que hace con ellos día con día. |

### 2.2 Frases de fecha (`FF_<tipo>_<n>`)
| ID | Texto |
|---|---|
| `FF_P_1` | El {fecha} cumple {periodo} de su última revisión con nosotros, y nos gustaría ver con usted cómo va su graduación. |
| `FF_P_2` | El {fecha} cumple {periodo} de su última revisión, y por eso quisimos saber de usted. |
| `FF_P_3` | Para el {fecha} cumple {periodo} de su última revisión; será un buen momento para comprobar con calma si su graduación sigue siendo la adecuada para usted. |
| `FF_P_4` | El {fecha} cumple {periodo} desde su última revisión con nosotros, y nos gustaría ver con usted, con calma, cómo va su graduación. |
| `FF_PS_1` | Se acerca el {fecha}, la fecha que le sugerimos para su siguiente revisión, y por eso quisimos saber de usted. |
| `FF_PS_2` | Para el {fecha} le sugerimos su siguiente revisión; será un buen momento para platicar con calma sobre su graduación. |
| `FF_PS_3` | Alrededor del {fecha} le sugerimos su siguiente revisión, y nos gustaría ver juntos cómo va su graduación. |
| `FF_N_1` | Quisimos saber de usted y de cómo le ha ido en este tiempo. |
| `FF_N_2` | Para nosotros es un gusto seguir en contacto con usted, a su ritmo y sin prisas. |
| `FF_N_3` | Nos interesa saber de usted y de lo que hoy necesita de sus lentes. |
| `FF_N_4` | Queremos acompañarle con calma, cuando y como usted lo prefiera. |

### 2.3 Aperturas v2 (`AP_<tipo>_<n>`)
| ID | Texto |
|---|---|
| `AP_PROX_CONT_1` | Buen día, :paciente. Le escribimos de :clinica porque nos da gusto seguir acompañándole y queremos saber de usted. |
| `AP_PROX_CONT_2` | Hola, :paciente, le saludamos de :clinica. Nos da gusto seguir acompañándole y por eso quisimos escribirle hoy. |
| `AP_PROX_CONT_3` | Muy buen día, :paciente. Le saluda con aprecio el equipo de :clinica; nos da gusto seguir acompañándole y saber cómo está. |
| `AP_PROX_CONT_4` | Hola, :paciente. Le escribimos de :clinica para saludarle; nos da gusto seguir acompañándole como hasta ahora. |
| `AP_PROX_CONT_5` | Buen día, :paciente. Para el equipo de :clinica es un gusto seguir acompañándole, y hoy queremos saber de usted. |
| `AP_PROX_PRIM_1` | Hola, :paciente, le saludamos de :clinica. Gracias por la confianza que nos ha dado; queremos acompañarle y saber de usted. |
| `AP_PROX_PRIM_2` | Buen día, :paciente. Le escribimos de :clinica porque queremos acompañarle y saber cómo le ha ido. |
| `AP_PROX_PRIM_3` | Muy buen día, :paciente. Le saluda el equipo de :clinica; nos gustaría seguir en contacto con usted y saber cómo se encuentra. |
| `AP_PROX_PRIM_4` | Hola, :paciente. En :clinica le tenemos presente y queremos acompañarle; por eso le escribimos con gusto. |
| `AP_VENC_1` | Hola, :paciente, le saludamos de :clinica. Nos acordamos de usted con gusto y queremos saber cómo se encuentra. |
| `AP_VENC_2` | Buen día, :paciente. Le escribimos de :clinica porque nos da gusto saber de usted y seguir acompañándole. |
| `AP_VENC_3` | Muy buen día, :paciente. El equipo de :clinica le envía un saludo cordial; queremos saber de usted y acompañarle. |
| `AP_VENC_4` | Hola, :paciente. En :clinica le tenemos presente y nos gustaría volver a saber de usted. |
| `AP_VENC_5` | Hola, :paciente, le saludamos de :clinica. Esperamos que se encuentre muy bien; queremos acompañarle cuando usted lo decida. |
| `AP_SEG_1` | Hola, :paciente, le saludamos de nuevo de :clinica. Solo queremos saber de usted, sin ninguna prisa. |
| `AP_SEG_2` | Buen día, :paciente. Le escribimos otra vez de :clinica, con calma, porque nos interesa saber cómo se encuentra. |
| `AP_SEG_3` | Hola, :paciente. En :clinica seguimos con gusto a sus órdenes y quisimos saludarle una vez más. |
| `AP_SEG_4` | Muy buen día, :paciente. Le saluda nuevamente el equipo de :clinica; queremos acompañarle cuando a usted le acomode. |

### 2.4 Cierres (`CI_<tipo>_<n>`)
| ID | Texto |
|---|---|
| `CI_INC_1` | ¿Cómo le va con sus lentes? Si todo va bien, nos da gusto saberlo; y si quiere que revisemos algo, su revisión está incluida en su atención y nosotros le buscamos un horario. |
| `CI_INC_2` | ¿Cómo le han funcionado sus lentes hasta ahora? Si gusta, también le apartamos una revisión, que está incluida en su atención. |
| `CI_INC_3` | Nos encantaría leerle: ¿cómo se ha sentido con sus lentes en este tiempo? Y si le acomoda, con gusto le buscamos un horario para su revisión, que está incluida en su atención. |
| `CI_INC_4` | ¿Qué tal le han funcionado sus lentes en su día a día? Cuando usted quiera, le apartamos un espacio para su revisión; está incluida en su atención. |
| `CI_INC_5` | Platíquenos, ¿cómo se ha sentido con sus lentes últimamente? Si quiere, también vemos juntos un horario para su revisión, que está incluida en su atención. |
| `CI_INC_6` | Nos dará gusto leerle: ¿cómo le va con sus lentes? Si lo desea, le buscamos un horario para su revisión, que está incluida en su atención. |
| `CI_COS_1` | ¿Cómo le va con sus lentes? Si todo va bien, nos da gusto saberlo. Y si quiere su revisión, tiene un costo; con gusto le informamos el monto y le buscamos un horario, y usted decide. |
| `CI_COS_2` | ¿Cómo le han funcionado sus lentes hasta ahora? Si gusta, también le apartamos una revisión; tiene un costo y con gusto le compartimos el detalle antes de que decida. |
| `CI_COS_3` | Nos encantaría leerle: ¿cómo se ha sentido con sus lentes en este tiempo? Si le interesa una revisión, le compartimos su costo sin compromiso y le buscamos un horario solo si usted lo desea. |
| `CI_COS_4` | ¿Qué tal le han funcionado sus lentes en su día a día? Cuando usted quiera, le contamos el costo de la revisión y, si le parece, le apartamos un espacio. |
| `CI_COS_5` | Platíquenos, ¿cómo se ha sentido con sus lentes últimamente? Si más adelante desea una revisión, con gusto le informamos su costo antes de agendar, sin ningún compromiso. |
| `CI_COS_6` | Nos dará gusto leerle: ¿cómo le va con sus lentes? Si quiere, también le buscamos un horario para su revisión; tiene un costo y se lo compartimos antes de agendar. |

### 2.5 Hechos conservados (6 hechos v1 literales)
| ID | Texto | Regla | Estado |
|---|---|---|---|
| `progresivo_zonas` | En sus lentes progresivos revisamos que la zona de lejos, la intermedia y la de cerca sigan acomodándose a sus actividades. | Reglas de catálogo §E | activo |
| `bifocal_zonas` | En sus lentes bifocales revisamos que la parte de lejos y la de cerca sigan acomodándose a lo que usted hace. | Reglas de catálogo §E | activo |
| `hipermetropia_cerca` | En la revisión verificamos que su graduación para la hipermetropía le resulte cómoda, tanto de lejos como de cerca. | Reglas de catálogo §E | activo |
| `astigmatismo_comodidad` | Con astigmatismo, que el armazón esté bien alineado influye en cómo funcionan sus lentes; en la revisión lo verificamos. | Reglas de catálogo §E | inactivo (requiere armazón) |
| `progresivo_ajuste` | En los lentes progresivos, la altura y el ajuste del armazón influyen mucho en la comodidad, y en la revisión los verificamos con calma. | Reglas de catálogo §E | inactivo (requiere armazón) |
| `ajuste_armazon` | Además de la graduación, revisamos el ajuste de su armazón, que también influye en lo cómodos que se sienten sus lentes. | Reglas de catálogo §E | inactivo (requiere armazón) |

### 2.6 Línea de baja
Línea fija de baja: «Si prefiere no recibir estos mensajes, solo díganoslo.»

### 2.7 Reglas de combinación y longitud
- Máximo 1 hecho por mensaje.
- Rango de 60 a 140 palabras para el cuerpo del mensaje sin la baja.
- Longitud máxima: 2000 caracteres.

---

## 3. Salida de Qwen en v2 (redacción)

JSON con esquema: `{"apertura": str <=300, "hechos": [id] (0-1), "cierre": id}`.
- Apertura redactada de usted, con `:paciente` y `:clinica` exactamente una vez cada uno.
- Sin signos de interrogación «¿» ni «?» en la apertura.
- Verificación en segunda pasada sobre la apertura sola (`afirma_algo_de_salud: false`).

---

## 4. Ejemplos de mensajes v2 completos

**1. Próximo, continuidad, incluida:**
> Buen día, :paciente. Le escribimos de :clinica porque nos da gusto seguir acompañándole y queremos saber de usted.
>
> Pensamos en sus lentes y en cómo le han acompañado en sus estudios.
>
> El 15 de diciembre cumple un año de su última revisión con nosotros, y nos gustaría ver con usted cómo va su graduación.
>
> ¿Cómo le va con sus lentes? Si todo va bien, nos da gusto saberlo; y si quiere que revisemos algo, su revisión está incluida en su atención y nosotros le buscamos un horario.
>
> Si prefiere no recibir estos mensajes, solo díganoslo.

---

## 5. Guiones para el equipo cuando el paciente responde

| El paciente dice | Respuesta sugerida | Regla |
|---|---|---|
| «Ahorita no puedo» | «Claro, entiendo perfectamente. ¿Le parece si le escribimos más adelante, o prefiere avisarnos usted cuando le acomode?» | Si dice «yo les aviso», no se le vuelve a escribir en este ciclo. |
| «No tengo dinero» | «Gracias por la confianza de decírnoslo. Sin ningún compromiso: si quiere, le comparto qué incluye y cuál es el costo para que lo considere con calma. Y si por ahora no es posible, lo entendemos.» | Si la revisión está incluida, se dice con claridad. Nunca se inventan descuentos. |
| «Veo bien, no lo necesito» | «Qué bueno que se siente a gusto. La revisión es solo un control de rutina; si en algún momento quiere hacerla, aquí estamos.» | No se discute ni se dan argumentos clínicos. |
| «Ya no me manden mensajes» | «Con gusto, ya no le enviaremos recordatorios. Gracias por avisarnos.» | La baja se registra **en ese momento**, sin pedir motivos, y se avisa al responsable de datos personales. Vale hasta que el propio paciente pida volver. |
| «¿Cuánto cuesta?» | Con costo: «Con gusto: [costo real y qué incluye]. ¿Le gustaría que le busquemos un horario?» Incluida: «Está incluida en su atención. ¿Le buscamos un horario?» | Se da el costo verdadero y completo, sin comparaciones. |
| Silencio | — | Es un «ahora no». Máximo **2 mensajes por ciclo** (el aviso y un recordatorio a los 7–10 días) y **una** llamada en horario razonable. Después, pausa hasta el siguiente ciclo. |
| Enojo | «Lamento mucho la molestia, no era nuestra intención. ¿Prefiere que dejemos de escribirle o que le contactemos de otra forma?» | Se valida la emoción sin justificarse. Si pide la baja, se aplica. |
| «No me hallo con los lentes» o dificultad de adaptación | «Gracias por contarnos. Lo mejor es revisarlo con sus lentes puestos para ver a qué se debe; ¿le parece si le buscamos un espacio?» | No prometer una solución ni explicar causas antes de ver los lentes con el optometrista. |
| «Ya me gradué en otro lugar» | «Qué bueno que ya resolvió su graduación; lo importante es que esté cómodo. Si en algún momento gusta volver con nosotros, aquí estamos.» | Competir, criticar a otra óptica o a otro profesional, o pedir los datos de su nueva receta. |
| **Síntomas de alarma** | Cualquier punto de la lista 3.2. Respuesta: la frase fija del nivel que corresponda (3.3), sin agregar nada más. | Nivel 1 → 911 o urgencias ahora, sin esperar llamada de la óptica; nivel 2 → llamada ahora y atención hoy mismo; si no hay quien atienda hoy, urgencias. Fuera de horario, ambos niveles van a urgencias. El equipo solo da las tres indicaciones fijas de 3.3 (lavado con agua, no frotar ni sacar objetos, retirar lentes de contacto) y ninguna otra. Se anotan la hora del aviso, el nivel, la frase enviada y a quién se pasó. |

---

### Guiones v2 cuando el paciente responde sobre su experiencia

Reglas generales:
- Ante cualquier molestia de la vista o de los ojos, el equipo **solo compara las palabras del paciente con la lista de síntomas de alarma** (§5.1 de este documento). No decide si algo es grave. Si el paciente menciona algo de la lista, o si hay **cualquier duda**, se sigue la conducta de alarma. Si no menciona nada de la lista, se pasa al optometrista el mismo día hábil.
- El equipo **no** interpreta síntomas, no dice «es normal», «es la graduación» ni «necesita lentes nuevos».

| El paciente dice | Respuesta sugerida | Regla |
|---|---|---|
| «Me siento bien», «me han funcionado muy bien» | «Qué gusto leerle, gracias por contarnos. Si quiere, le buscamos un horario cerca de la fecha de su revisión; y si prefiere dejarlo para más adelante, también está bien.» | Una sola oferta; si dice que no, se cierra con calidez y no se vuelve a escribir en el ciclo. |
| «Veo borroso de lejos» | «Gracias por decírnoslo. Para revisarlo bien, lo mejor es que lo vea el optometrista. ¿Esto le empezó de repente o lo ha ido notando poco a poco?» Si contesta «poco a poco» y no menciona nada de la lista de alarma: «Gracias. Se lo pasamos al optometrista para que platique con usted hoy, y con gusto le buscamos un espacio en estos días; ¿le acomoda más por la mañana o por la tarde?» | Si empezó de repente (horas o de un día para otro), si no sabe decirlo o si menciona algo de la lista: conducta de alarma. Si es gradual: pase al optometrista el mismo día hábil y cita en la semana. No se dice que "ya cambió su graduación". |
| «Me duele la cabeza al leer» | «Lamentamos que se sienta así, gracias por contarnos. Se lo comentamos al optometrista para que platique con usted y vean juntos qué está pasando. ¿Le parece si le llama hoy o mañana?» | No se atribuye la causa a los lentes ni a la graduación. Se pasa al optometrista el mismo día hábil. Si el dolor de cabeza es nuevo y viene con cualquier cambio en la vista, dolor en la sien o al masticar, ojo rojo, náusea o vómito, o si es súbito y muy fuerte: conducta de alarma (lista 3.2, A1, A5 y A7). |
| «Ya no los uso» | «Gracias por la confianza de decírnoslo. Si quiere platicarnos, ¿qué pasó con ellos?» | Sin reproche ni «debería usarlos». Se anota para el optometrista. |
| «Los perdí» o «se me rompieron» | «Qué pena, entendemos lo incómodo que es quedarse sin ellos. Con gusto le ayudamos a ver opciones; si quiere, le buscamos un horario para que pase.» | No se vende ni se da precio si no lo pide. El equipo no promete hacer lentes con receta anterior sin aval del optometrista. |
| «Me cambié de trabajo» o «ahora estudio» | «Qué bien que nos lo cuenta, nos sirve mucho saberlo. Se lo comentamos al optometrista para que tome en cuenta sus nuevas actividades. ¿Le gustaría que le busquemos un espacio?» | Se actualiza la ocupación solo con lo que el paciente dijo. Se anota para el optometrista. |
| **Síntomas de alarma** | Cualquier punto de la lista 3.2. Respuesta: la frase fija del nivel que corresponda (3.3), sin agregar nada más. | Nivel 1 → 911 o urgencias ahora, sin esperar llamada de la óptica; nivel 2 → llamada ahora y atención hoy mismo; si no hay quien atienda hoy, urgencias. Fuera de horario, ambos niveles van a urgencias. El equipo solo da las tres indicaciones fijas de 3.3 (lavado con agua, no frotar ni sacar objetos, retirar lentes de contacto) y ninguna otra. Se anotan la hora del aviso, el nivel, la frase enviada y a quién se pasó. |

### 5.1 Lista final de síntomas de alarma (sección 3.2)

> **Para quien atiende WhatsApp.** Compare lo que escribe el paciente con esta lista. No tiene que saber qué enfermedad es ni decidir si es grave. Si aparece algo de la lista, o si tiene duda, siga la conducta del nivel. Si un mensaje encaja en los dos niveles, use el **nivel 1**.

**Nivel 1: 911 o urgencias ahora. No se espera la llamada de la óptica.**

| # | El paciente dice algo como… | Conducta | Por qué no espera (uso interno, no se le dice al paciente) | Evidencia |
|---|---|---|---|---|
| A1 | Debilidad, adormecimiento u hormigueo de un lado del cuerpo; la cara «chueca»; dificultad para hablar o entender; confusión o pérdida del equilibrio repentinas; o un dolor de cabeza súbito y muy fuerte («el peor de mi vida»), **junto con cualquier cambio en la vista**. | Frase N1. **911.** | ACV o hemorragia cerebral: el tratamiento depende de los minutos. | E (AHA/ASA, guías de ACV agudo) |
| A2 | Perdió la vista **de repente**, total o en parte, en uno o en los dos ojos, **aunque ya haya regresado** («se me apagó un ojo unos minutos»). | Frase N1. Urgencias de un hospital, de inmediato. | Oclusión de la arteria central de la retina o pérdida transitoria de visión: son equivalentes de ACV y tienen alto riesgo de ACV en los días siguientes. | E (AHA/ASA, declaración científica sobre la oclusión de la arteria central de la retina, 2021; AAO PPP de oclusiones arteriales y venosas de la retina) |
| A3 | Le cayó o le salpicó **una sustancia química** en el ojo: cloro, cal, cemento, limpiadores, destapacaños, ácido de batería, pegamento, etc. | Frase N1-Q (lavado primero). Después, urgencias o 911. | Quemadura química: el daño avanza mientras la sustancia siga en el ojo. El tiempo hasta el lavado es el principal factor de pronóstico. | E (consenso: AAO; guías de primeros auxilios AHA/Cruz Roja Americana; series observacionales) |
| A4 | **Golpe fuerte** en el ojo; herida o corte; algo **clavado**; algo que entró a gran velocidad (al esmerilar, martillar metal o cortar con disco); sangre dentro del ojo después de un golpe. | Frase N1-T (no frotar ni sacar). Urgencias. | Posible herida abierta del globo ocular o hemorragia: frotar o presionar el ojo puede empeorarlo. | E/C (AAO; consenso de trauma ocular) |
| A5 | **Dolor fuerte** en el ojo con ojo rojo, visión borrosa, **halos de colores** alrededor de las luces, dolor de cabeza, **náusea o vómito**. | Frase N1. Urgencias, de preferencia con oftalmología. | Glaucoma agudo por cierre angular: la presión alta daña el nervio óptico en horas. | E (AAO PPP de enfermedad por cierre angular primario) |
| A6 | **Visión doble** que apareció de repente. | Frase N1. Urgencias. | Puede deberse a un ACV, un aneurisma o una lesión de un nervio craneal; el equipo no puede distinguir la causa. | C (consenso de neurooftalmología) |
| A7 | Dolor de cabeza **nuevo** con cualquier cambio en la vista (visión borrosa, doble o que se apaga), **dolor o sensibilidad en la sien o en el cuero cabelludo**, o dolor de mandíbula al masticar. | Frase N1. Urgencias **hoy mismo**. | Arteritis de células gigantes: sin esteroide el mismo día, puede dejar ciego el otro ojo. (No se pregunta la edad: el equipo no filtra por edad.) | E (ACR/Vasculitis Foundation 2021; BSR 2020) |
| A8 | Una **sombra o cortina** que tapa parte de la visión. | Frase N1. Urgencias, de preferencia con oftalmología. | Desprendimiento de retina: si alcanza la mácula, la pérdida de visión puede ser permanente. | E (AAO PPP de desprendimiento posterior del vítreo, desgarros retinianos y degeneración en empalizada) |
| A9 | **Cirugía de ojos reciente** (catarata, refractiva u otra, en las últimas semanas) con dolor que aumenta, ojo rojo o baja de la visión. | Frase N1. Urgencias, o su cirujano oftalmólogo **ahora**. | Endoftalmitis posoperatoria: es una urgencia de horas. | E (consenso; literatura sobre endoftalmitis) |

**Nivel 2: valoración hoy mismo. Llamada inmediata de la óptica; si no hay quien lo valore hoy, urgencias.**

| # | El paciente dice algo como… | Conducta | Por qué hoy | Evidencia |
|---|---|---|---|---|
| B1 | **Destellos** de luz nuevos, o muchas **«moscas»** o manchas flotantes nuevas que aparecieron de golpe (sin sombra ni cortina; si las hay, A8). | Frase N2. Valoración hoy con fondo de ojo dilatado (pregunta F2). | Desgarro de retina: tratarlo antes de que se desprenda evita la cirugía mayor. | E (AAO PPP de desprendimiento posterior del vítreo) |
| B2 | **Usa lentes de contacto** y tiene ojo rojo, dolor, sensibilidad a la luz, lagrimeo o visión borrosa. | Frase N2-LC (retirar los lentes). Valoración hoy con lámpara de hendidura. | Queratitis infecciosa o úlcera de córnea (bacterias o *Acanthamoeba*): puede perforar la córnea o dejar cicatriz en días. | E (AAO PPP de queratitis bacteriana) |
| B3 | Líneas rectas que **de pronto** se ven torcidas u onduladas, o una **mancha nueva** en el centro de la visión. | Frase N2. Valoración hoy o, como máximo, en 24 a 48 h, según lo que diga el optometrista. | Degeneración macular neovascular u otra lesión de la mácula: el antiangiogénico temprano protege la visión. | E/C (AAO PPP de degeneración macular relacionada con la edad) |
| B4 | Ojo rojo **con dolor**, o con secreción abundante, o con sensibilidad intensa a la luz (no usa lentes de contacto). | Frase N2. | Queratitis, uveítis o conjuntivitis grave: el equipo no puede distinguirlas. | C |
| B5 | Le entró algo (basurita, polvo, una pestaña) y la molestia **sigue**, sin golpe fuerte ni objeto a gran velocidad (si los hubo, A4). | Frase N2-T. | Cuerpo extraño en la córnea: se puede infectar si se queda. | C |

### 5.2 Frases fijas (sección 3.3)

- **N1 (nivel 1):** «Gracias por avisarnos. Lo que nos cuenta necesita atención médica ahora mismo. Por favor llame al 911 o acuda de inmediato al servicio de urgencias más cercano; no espere a una cita con nosotros.»
- **N1-Q (sustancia química, A3):** «Gracias por avisarnos. Lávese el ojo **ahora mismo** con abundante agua limpia de la llave, con el ojo bien abierto, durante al menos 15 minutos sin parar. Si usa lentes de contacto, quíteselos mientras se enjuaga. No se ponga gotas ni ninguna otra sustancia. Mientras se lava, pida a alguien que llame al 911; al terminar, acuda de inmediato a urgencias.»
- **N1-T (golpe, herida u objeto, A4):** «Gracias por avisarnos. No se frote ni se apriete el ojo, y si tiene algo clavado, no intente sacarlo. Por favor llame al 911 o acuda de inmediato al servicio de urgencias más cercano.»
- **N2 (nivel 2):** «Gracias por avisarnos. Lo que nos cuenta necesita que lo valoren hoy mismo. Le llamamos ahora para darle un espacio hoy; si no logramos atenderle hoy, por favor acuda a un servicio de urgencias.»
- **N2-LC (lentes de contacto, B2):** la frase N2 y, a continuación: «Mientras tanto, quítese los lentes de contacto, guárdelos en su estuche, tráigalos y no se los vuelva a poner hasta que le revisen.»
- **N2-T (basurita, B5):** la frase N2 y, a continuación: «Mientras tanto, no se frote el ojo.»
- **Fuera de horario (respuesta automática):** «Recibimos su mensaje. En este momento no hay personal para atenderle. Si tiene un problema en los ojos o en la vista que empezó de repente, dolor fuerte, un golpe o una sustancia en el ojo, llame al 911 o acuda a urgencias ahora. Si no es urgente, le respondemos el siguiente día hábil.»

Después de enviar la frase, el equipo **llama** (en el nivel 1, solo para confirmar que el paciente va en camino o que ya llamó al 911, sin retrasarlo), anota la hora, el nivel y la frase, y avisa al optometrista.

**Sobre la quemadura química (la pregunta de la tarea).** Sí: el lavado inmediato, abundante y prolongado con agua limpia es la indicación estándar de primeros auxilios. El agua de la llave es aceptable; no hay que retrasar el lavado para buscar suero. Así lo indican la AAO, las guías de primeros auxilios de la AHA y la Cruz Roja Americana y los textos de urgencias oftalmológicas, y el factor pronóstico con más respaldo es el tiempo hasta el lavado (evidencia observacional; no existen ensayos controlados por razones éticas). El equipo puede darla porque:
1. es una instrucción fija de primeros auxilios para el público general, no la interpretación de un síntoma;
2. se activa por un hecho que el paciente declara («me cayó cloro»), no por un juicio del equipo;
3. el equipo no agrega nada más: ni gotas, ni leche, ni «neutralizar», ni tiempos distintos.

Lo mismo vale para «no frotar ni sacar el objeto» (A4) y «retirar los lentes de contacto» (B2). Fuera de esas tres frases, el equipo no da ninguna otra indicación.


## 6. Decisiones para firmar

1. **Confirmar que la consulta incluye** los pasos que nombran los hechos marcados con P: comodidad de lejos, lejos y cerca en hipermetropía, alineación del armazón, distancias de cerca, zonas y altura de los progresivos, bifocales, ajuste del armazón y orientación sobre pantallas. Un hecho cuyo paso no se haga se retira.
2. **Aprobar que ningún hecho dependa de la edad** (recomendado).
3. **Aprobar el límite de recordatorios**: 2 mensajes y 1 llamada por ciclo, y la baja inmediata y permanente.
4. **Reglas para nombrar la corrección**:
   - Umbral mínimo de ESF y CIL para nombrar una condición (hoy cualquier valor distinto de 0 la nombra).
   - Astigmatismo mixto: se nombra solo «astigmatismo» (así funciona ya en ia-api).
   - Antimetropía: un ojo con miopía y el otro con hipermetropía.
   - Si el caso es dudoso, se usan solo hechos que no nombran la condición.
5. **Si conserva `traer_lentes`**, que es una recomendación práctica más que un hecho.
6. **Datos que hoy no existen en el sistema**: «usa armazón» frente a solo lentes de contacto, y que el tipo de lente venga de la misma consulta que la última receta. Hasta que existan, los hechos que los exigen no se usan.

Firma del optometrista: ______________  Fecha: ________  Versión: `v1-revisado`