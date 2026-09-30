from comun import ejecutar,historicos,persistir
ID='insuficiencia_convergencia'
BASE={'ppc':7,'cover':'OD: Exo y Foria | OI: Orto'}
scenarios=[
 ('actual','Fatiga visual al leer.',True,False),
 ('historico','En 2020 tenia fatiga visual al leer.',False,False),
 ('resuelto-mas-actual','Fatiga ocular al leer resuelta, ahora diplopia al leer desde hoy.',True,True),
 ('contexto-familiar','Presento vision doble al leer desde hoy mientras cuido a mi madre.',True,True),
 ('familia','Mi madre presenta fatiga ocular al leer; yo sin molestias.',False,False),
 ('general','Fatiga muscular al correr.',False,False),
 ('cefalea','Cefalea cervical al despertar, lectura comoda.',False,False),
 ('monocular','Diplopia monocular al leer.',False,False),
 ('negado','Sin fatiga ocular al leer ni diplopia.',False,False),
 ('hipotesis','Se evaluara posible fatiga ocular al leer.',False,False),
 ('contraste','Antecedente de diplopia resuelta, pero hoy fatiga visual al leer.',True,False),
]
casos=[]
for id,t,active,urgent in scenarios:
 casos.append(ejecutar('R42-'+id,dict(BASE,motivo=t),lambda a,h,active=active,urgent=urgent:(ID in a)==active and (not urgent or (a.get(ID,'').startswith('Hallazgo urgente:') and any(x['id']==ID for x in h))),'Coocurrencia solo con síntoma visual actual/cerca; síntoma agudo del paciente conserva mismo día/H01'))
for edad,ppc in [(0,1),(20,5),(40,6),(None,10),(125,15)]:
 casos.append(ejecutar(f'R42-edad-{edad}-ppc-{ppc}',dict(BASE,edad=edad,ppc=ppc,motivo='Fatiga ocular al leer.'),lambda a,h:ID in a and not any(x in a[ID] for x in ('presbicia','terapia','sospecha de insuficiencia','PPC alejado')),'PPC como número y edad conocida/nula, sin criterio diagnóstico CITT/presbicia'))
casos.append(ejecutar('R42-mixto',{'ppc':7,'cover':'OD: Exo y Foria | OI: Endo y Tropia','motivo':'Fatiga ocular al leer.'},lambda a,h:ID in a and all(x in a[ID] for x in ('PPC de 7 cm','exoforia en OD','endotropia en OI')) and 'ppc_exoforia' not in a and 'cover_exoforia_sintomatica' not in a,'Deduplicar conservando todos los datos reales por ojo/subtipo'))
casos.append(ejecutar('R42-condicional-subjuntivo',dict(BASE,motivo='Fatiga ocular al leer. Si presentara perdida visual subita, volveria.'),lambda a,h:ID in a and not a[ID].startswith('Hallazgo urgente: ') and not any(x['id']==ID for x in h),'Coocurrencia actual neutral no se vuelve urgente por una pérdida visual hipotética futura'))
casos.append(ejecutar('R42-distancia-contradictoria',dict(BASE,motivo='Fatiga ocular al leer. Cover test de lejos; ortoforia de cerca.'),lambda a,h:ID in a and 'de lejos' in a[ID] and 'ortoforia de cerca' in a[ID],'Conservar distancia y alineación cercana expresamente informadas, sin asociar exoforia lejana a la tarea de cerca'))
hist=historicos(42)
text='''# Conformidad #42 — insuficiencia_convergencia

Veredicto: **NO CUMPLE**. La reformulación neutral, PPC y cover cumplen; el requisito de síntomas actuales y conservación del inicio agudo falla por filtros globales/ausencia de cronología en el detector sintomático.

## Matriz de todos los requisitos

Orden: AUDITORIA_CORRELACIONES.md:3682–3698, especialmente recomendaciones3694 y aceptación3696. Generales234–256 y cierre3988–3996. Contrato: DICCIONARIO_DATOS_RECETA.md:49–55,111–120,125–135,154–170; cover canónico por ojo y PPC1–15. Las órdenes prevalecen sobre declaración4029.

| Requisito obligatorio | Código/evidencia | Estado |
|---|---|---|
| Retirar etiología/IC/terapia; conservar coocurrencia para evaluación | binocularidad.py:183–199; corpus/controlactual | CUMPLE |
| Valores observados, ojo/subtipo, cuantificar cerca/lejos/PPC/reservas como pendientes | descripción50–63 y texto194–199; R42-mixto | CUMPLE |
| Síntomas visuales afirmados actuales y relacionados con cerca antes de asociación | detector73–104; R42-historico/resuelto-mas-actual | NO CUMPLE: historia2020activa; actual después de resuelta se pierde |
| Fatiga general/cefalea aislada/monocular no justifican esta asociación | R42-general/cefalea/monocular/negado | CUMPLE en controles |
| Negación/antecedentes/diagnóstico conocido/contradicciones/sujeto fieles | filtros66–104; R42-contexto-familiar/resuelto-mas-actual/distancia-contradictoria | PARCIAL: familiar objeto elimina síntoma real; se omite cover lejana/ortoforia cercana explícita |
| PPC sin protocolo no es anormalidad universal; no inventar rotura/recuperación | texto198; R42-edad y C42-15 | CUMPLE |
| Edad ausente no es presbicia; no campos hipotéticos obligatorios | condición183–191 sin cortesedad, controlesedad | CUMPLE |
| Deduplicación42/43/44 conserva número, ojos y todos los hallazgos | R42-mixto; condiciones202–208/228–234 | CUMPLE en registro canónico mixto |
| Inicio agudo/prioridad debe conservar sujeto, estado, certeza y plazo | filtros107–163; R42-resuelto-mas-actual/contexto-familiar/condicional-subjuntivo | NO CUMPLE: se omiten alarmas reales y una hipótesis genera falsa urgencia |
| Corpus13–15/21 sin nueva sospechaIC/terapia; conocido no nuevo descubrimiento y contradicción expresa respetada | corpus22reproducido; C42-21 es canónico con distancia/ortoforia próxima en motivo, omitidas en salida | CUMPLE en etiquetas, PARCIAL en contexto; no validación clínica ni Qwen real |

## Desvíos exactos y recomendación completa

Con PPC7 y `OD: Exo y Foria | OI: Orto`:

- `En 2020 tenia fatiga visual al leer.` activa42 como coocurrencia que exige síntomas actuales; el detector no aplica cronología a las ocurrencias que selecciona.
- `Fatiga ocular al leer resuelta, ahora diplopia al leer desde hoy.` elimina todo el fragmento por la palabra resuelta. Desaparece42;43queda sin prefijo urgente/H01 pese al nuevo episodio del paciente.
- `Presento vision doble al leer desde hoy mientras cuido a mi madre.` elimina todo el fragmento por mencionar madre, aunque es objeto del cuidado y el paciente es sujeto explícito. Tampoco conserva urgencia.
- `Fatiga ocular al leer. Si presentara perdida visual subita, volveria.` activa42 como coocurrencia actual, pero añade falsa urgencia inmediata y alarma propia H01 por una pérdida visual hipotética futura. La modalidad condicional no se reconoce.
- `Fatiga ocular al leer. Cover test de lejos; ortoforia de cerca.` activa42, pero omite ambas precisiones explícitas. La salida conserva la exoforia y la tarea cercana sin el contexto de que aquella fue lejana y la alineación cercana fue ortofórica. El campo cover sigue siendo canónico; las precisiones están en motivo contractual, como en C42-21. No se propone eliminar los datos numéricos ni inventar magnitud/protocolo.

Recomendación completa: extraer síntomas por ocurrencia con sujeto real y cronología, certeza, negación y modalidad condicional propios; distinguir antecedente/resuelto de nuevo episodio dentro de una misma oración y reconocer cambios como ahora/actualmente. La mención de un familiar no debe borrar hechos del paciente si es acompañante/objeto; la hipótesis futura no crea una alarma actual. Mantener exclusión de fatiga extravisual/monocular y relación de cerca, cubrir relatos fechados con año, sin inventar actualidad desde hora de consulta. Conservar distancia/alineación cercana y otras contradicciones expresas de fuentes contractuales pertinentes, sin importar atributos de otra prueba ni reinterpretar la exoforia lejana como próxima. Conservar datos numéricos y cover en deduplicaciones, y activar prioridad únicamente desde episodio actual documentado, con acción/plazo/H01. Añadir los cinco pares contrafactuales al arnés independiente; no nuevos campos, cortes diagnósticos o terapia. No implementado.

## Cobertura

tests/test_ajuste_c42.py:81–109 cubre22históricos, PPC/edad, fatiga general y mezcla. tests/test_ajuste_c44.py:53–57 cubre contraste conpero, pero no ahora después de resuelta ni familiares como objeto ni conservación de las precisiones del C42-21. JSON42-casos.json contiene históricos y19controles independientes; los legacy, si existen, se clasifican aparte y no prueban serialización del SaaS. Sin llamada almodelo ni acreditación de rendimiento clínico.
'''
persistir(42,{'veredicto':'NO CUMPLE','historicos':hist,'controles_independientes':casos},text,['AUDITORIA_CORRELACIONES.md','DICCIONARIO_DATOS_RECETA.md','app/correlaciones/binocularidad.py','app/correlaciones/registry.py','tests/test_ajuste_c42.py','tests/test_ajuste_c44.py'])
print([x['id'] for x in casos if not x['cumple_expectativa']])
