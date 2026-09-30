from comun import ejecutar,historicos,persistir
ID='cvs_sospecha'
cases=[]
for p in (None,'lt2','btw2_6','gt6'):
 for motivo,activa in [('Fatiga ocular al leer.',True),('Cefalea general.',False),('Dolor gastrico y prurito cutaneo.',False),('Sin fatiga ocular ni vision borrosa.',False),('Madre con fatiga ocular al leer.',False),('Posible diplopia por verificar.',False),('En 2020 tenia fatiga visual al leer.',False)]:
  expected=p is not None and activa
  cases.append(ejecutar(f'R53-matriz-{p}-{motivo}',{'pantallas':p,'motivo':motivo},lambda a,h,e=expected:(ID in a)==e,'Categoría conocida + síntoma ocular/visual actual afirmado del paciente; histórico/familiar/hipotético no positivo'))
for suf,motivo in [('actual','Diplopia desde hoy.'),('resuelto-mas-actual','Fatiga ocular resuelta, ahora diplopia desde hoy.'),('familiar-objeto','Presento diplopia desde hoy mientras cuido a mi madre.')]:
 cases.append(ejecutar(f'R53-{suf}',{'pantallas':'lt2','motivo':motivo},lambda a,h:ID in a and a[ID].startswith('Hallazgo urgente: ') and 'mismo dia' in a[ID] and any(x['id']==ID for x in h),'Diplopia actual del paciente mantiene selección y plazo de mismo día; estado/familiar se vincula a su episodio/sujeto'))
for suf,motivo in [('dolor-trauma','Dolor ocular OD tras traumatismo ocular OD de hoy.'),('dolor-rojo-foto','Dolor ocular OD con ojo rojo y fotofobia OD desde hoy.'),('perdida','Perdida visual subita OD desde hoy.')]:
 cases.append(ejecutar(f'R53-{suf}',{'pantallas':'gt6','motivo':motivo},lambda a,h:ID in a and a[ID].startswith('Hallazgo urgente: ') and 'inmediata' in a[ID] and any(x['id']==ID for x in h),'Alarma ocular actual requiere urgencias inmediatas; exposición no sustituye acción clínica'))
for suf,motivo in [('relacion-explicita','Fatiga ocular que empeora con pantallas desde ayer.'),('sin-relacion','Vision borrosa que no empeora con pantallas.'),('causa-conocida','Fatiga ocular al leer atribuida a migrana ya evaluada por especialista.')]:
 cases.append(ejecutar(f'R53-{suf}',{'pantallas':'btw2_6','motivo':motivo},lambda a,h:ID in a and motivo.rstrip('.') in a[ID] and 'por uso de pantallas' not in a[ID],'Conservar relación/negación/causa referida literalmente, sin atribuir causa a pantallas'))
hist=historicos(53)
md=f'''# Conformidad #53 — cvs_sospecha

Veredicto determinista: **NO CUMPLE**. La redacción es neutral y admite las tres categorías de pantallas, pero el criterio obligatorio de síntomas actuales se incumple y pueden perderse síntomas agudos reales del paciente. El ID legacy se conserva sin diagnosticar síndrome visual informático.

## Matriz de requisitos obligatorios

Orden prevalente: AUDITORIA_CORRELACIONES.md:3858–3872; generales:234–256; cierre:3972–4006. Contrato: DICCIONARIO_DATOS_RECETA.md:20–55,111–120,125–135,154–170.

| Requisito obligatorio | Código/evidencia | Estado |
|---|---|---|
| Seleccionar solo síntomas oculares/visuales afirmados, actuales y del paciente; no cansancio/cefalea generales o de otra estructura | contexto.py:121–127; binocularidad.py:66–104; matriz extraocular/negada/familiar/hipotética; R53-perdida | PARCIAL: histórico2020 activa y pérdida visual actual no selecciona |
| Vincular negación, sujeto, certeza y cronología a cada síntoma; no reinterpretar resuelto/antiguo o causa conocida como hallazgo nuevo | _fragmentos_paciente66–71/_sintomas_visuales_actuales73–104; R53-resuelto-mas-actual/familiar-objeto; causa referida conservada | NO CUMPLE: veto global de fragmento oculta otro episodio o sujeto real |
| Texto literal y coocurrencia, sin confirmar CVS, causa de pantallas, mecanismo o recomendar Rx intermedia | contexto.py:130–136; matriz y relación explícita/no relación | CUMPLE |
| lt2 es exposición declarada, no nula ni garantía de bajo riesgo; categoría ausente no reconstruida desde ocupación/horas | condición121–127 y texto131–133; cuatro categorías de matriz | CUMPLE |
| Relación temporal con pantallas solo cuando referida; conservar discordancias/causa ya informada sin atribución nueva | Texto copia fragmento real; R53-relacion-explicita/sin-relacion/causa-conocida | CUMPLE en episodios seleccionados |
| Neutralmente caracterizar síntomas y considerar superficie/función/contexto de trabajo; sin inventar CVS-Q, mediciones o exploraciones | contexto.py:130–136; todas las salidas | CUMPLE |
| Dolor, trauma, fotofobia y síntomas agudos no quedan como consejo ergonómico; prioridad y plazo clínicos fieles | _con_prioridad_visual156–163 y episodios107–153; dolor/trauma y diplopía básicos correctos; mixto/familiar objeto omiten #53 y H01; pérdida visual omitida conserva H01 por #2 | PARCIAL |
| Redacción general sin diagnóstico/prefijo/plazo urgente injustificado; coexistencia y datos no borrados | Corpus completo y controles guardan salidas/H01; prefijo básico correcto | PARCIAL por selección temporal y prioridad anteriores |
| Comprobar generación real con Qwen/coexistencias clínicas | Auditoría solo determinista, sin proveedor | NO VERIFICABLE por separado; no es defecto de implementación |

## Desvíos reproducidos y ajuste completo recomendado

1. `En 2020 tenia fatiga visual al leer.` con pantallas=lt2/btw2_6/gt6 activa #53 como síntoma referido actual. La cronología explícita antigua no es ausencia de información. El detector actual no usa la cronología por ocurrencia.
2. `Fatiga ocular resuelta, ahora diplopia desde hoy.` con pantallas=lt2 elimina todo el fragmento al encontrar «resuelta»: no emite #53 y H01 queda vacío para esta entrada. La resolución afecta a la fatiga, no a la diplopia nueva.
3. `Presento diplopia desde hoy mientras cuido a mi madre.` con pantallas=lt2 elimina todo el fragmento por «madre». El paciente es sujeto de la diplopia y la madre objeto del cuidado; tampoco se emite #53 ni alarma H01.
4. `Perdida visual subita OD desde hoy.` con pantallas=gt6 no activa #53: la lista de síntomas actuales no contempla este hecho visual. **H01 sí conserva #2 con acción del mismo día**, por lo que no se afirma pérdida total de alarma en este control. La ruta #53 no conserva este síntoma ni su prioridad inmediata prevista por el helper de pérdida aguda.

Aplicar estado, cronología, negación, certeza y sujeto por ocurrencia/episodio y conservar el síntoma actual aunque coexista otro resuelto. Distinguir familiares sujetos de antecedentes de familiares que son objetos de una acción del paciente. Reutilizar el análisis temporal para selección y prioridad, manteniendo independencia de episodios y ojos; la selección de síntomas debe incluir pérdida visual documentada en lugar de depender de una lista que la omite. Conservar coocurrencia neutral, categoría exacta, contexto y relación explícita, y evaluar prioridad ocular antes del consejo sobre pantallas. Reproducir los cuatro desvíos junto con controles negados, hipotéticos, familiares auténticos, históricos y mixtos, verificando texto y H01. **Solo recomendado; no implementado.**

## Cobertura y límites

tests/test_ajuste_c53.py cubre23 históricos, categorías, negaciones, extraocular, familiares sujetos y nuevo síntoma separado por «pero». No cubre los casos temporales/de sujeto aquí fallidos. 53-casos.json guarda{len(hist)} históricos y{len(cases)} controles independientes, payload completo, categoría contractual/legacy, todas las salidas y H01. Se juzgan requisitos de la orden, no goldens. No se valida clínica ni respuesta real de Qwen en este dictamen.
'''
persistir(53,{'veredicto':'NO CUMPLE','historicos':hist,'controles_independientes':cases},md,['AUDITORIA_CORRELACIONES.md','DICCIONARIO_DATOS_RECETA.md','app/correlaciones/contexto.py','app/correlaciones/binocularidad.py','app/correlaciones/registry.py','app/inference.py','tests/test_ajuste_c53.py'])
print([r['id'] for r in cases if not r['cumple_expectativa']])
