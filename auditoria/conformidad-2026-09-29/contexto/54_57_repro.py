from copy import deepcopy
from comun import ejecutar,historicos,persistir
IDS={54:'ambliopia_sospecha',55:'ambliopia_isoametropica_bilateral',56:'deficit_visual_inexplicado_refractivo',57:'adulto_mayor_screening'}
BASE={54:dict(edad=8,rx_od={'esfera':0,'cilindro':0,'av_cc':'20/40'},rx_oi={'esfera':2,'cilindro':0,'av_cc':'20/60'}),55:dict(edad=8,rx_od={'esfera':4,'cilindro':0,'av_cc':'20/40'},rx_oi={'esfera':4,'cilindro':0,'av_cc':'20/40'}),56:dict(edad=35,rx_od={'esfera':0,'cilindro':0,'av_cc':'20/40'},rx_oi={'esfera':0,'cilindro':0}),57:dict(edad=70,rx_od={'esfera':0,'cilindro':0,'av_cc':'20/40'},rx_oi={'esfera':0,'cilindro':0})}
for n,ID in IDS.items():
 casos=[];b=deepcopy(BASE[n])
 casos.append(ejecutar(f'R{n}-base',b,lambda a,h:ID in a and '20/40 en OD' in a[ID] and not any(w in a[ID].lower() for w in ('ambliopia','isoametrop','inexplicado','subnormal','catarata','glaucoma','maculopatia','ausencia de','simetric','estimula')),'Descripción exacta de AV, coocurrencia y evaluación neutral; no BCVA/etiología/gravedad/normalidad universal'))
 for field in ('motivo','anexos','seguimiento'):
  txt='BCVA maxima 20/20 obtenida con graduacion completa, receta actual deliberadamente parcial.'
  casos.append(ejecutar(f'R{n}-maxima-parcial-{field}',{**b,field:txt},lambda a,h:ID in a and 'maxima 20/20' in a[ID] and 'deliberadamente parcial' in a[ID],'Conservar máxima AV referida y corrección parcial documentadas en fuente contractual, no llamar BCVA a AVcc'))
 casos.append(ejecutar(f'R{n}-fiabilidad', {**b,'motivo':'AV poco confiable, repetir por respuestas inconsistentes.'},lambda a,h:ID in a and 'poco confiable' in a[ID],'Conservar fiabilidad explícita y contextualizar/repetir medición antes de interpretar'))
 casos.append(ejecutar(f'R{n}-adaptacion-control',{**b,'motivo':'Sin adaptacion a la receta actual; graduacion conocida y estable.'},lambda a,h:ID in a and 'Sin adaptacion' in a[ID] and 'estable' in a[ID],'Adaptación y hallazgo previo documentados no se convierten en descubrimiento nuevo'))
 for suf,txt in [('perdida-actual','Perdida visual subita OD desde hoy.'),('resuelto-mas-actual','Fatiga ocular resuelta, ahora perdida visual subita OD desde hoy.'),('familiar-objeto','Presento perdida visual subita OD desde hoy mientras cuido a mi madre.')]:
  casos.append(ejecutar(f'R{n}-{suf}',{**b,'motivo':txt},lambda a,h:ID in a and a[ID].startswith('Hallazgo urgente: ') and 'inmediata' in a[ID] and any(x['id']==ID for x in h),'Síntoma actual del paciente conserva prioridad inmediata de esta ruta y su alarma H01; distinguir alarma independiente #2 si existe'))
 for suf,txt in [('diplopia-actual','Diplopia desde hoy.'),('diplopia-resuelta-mas-actual','Fatiga ocular resuelta, ahora diplopia desde hoy.'),('diplopia-familiar-objeto','Presento diplopia desde hoy mientras cuido a mi madre.')]:
  casos.append(ejecutar(f'R{n}-{suf}',{**b,'motivo':txt},lambda a,h:ID in a and a[ID].startswith('Hallazgo urgente: ') and 'mismo dia' in a[ID] and any(x['id']==ID for x in h),'Diplopia nueva mantiene acción del mismo día, sin veto de otro episodio resuelto/familiar objeto'))
 for suf,txt in [('familiar-real','Mi madre tiene perdida visual subita desde hoy.'),('negado','Sin perdida visual ni diplopia.'),('hipotetico','Si presentara perdida visual subita, volveria.'),('historico','Diplopia desde hace diez anos, hoy revision rutinaria.')]:
  casos.append(ejecutar(f'R{n}-{suf}',{**b,'motivo':txt},lambda a,h:ID in a and not a[ID].startswith('Hallazgo urgente: '),'AV sigue presente; familiar/negación/hipótesis/episodio antiguo no generan alarma propia'))
 sc=deepcopy(b);sc['rx_od']['av_sc']='20/20'
 casos.append(ejecutar(f'R{n}-avsc-mejor',sc,lambda a,h:ID in a and '20/20' in a[ID] and '20/40' in a[ID] and 'revisar la concordancia' in a[ID],'Conservar AVsc mejor que AVcc y pedir concordancia sin eliminar el ojo'))
 cc=deepcopy(b);cc['rx_od']['av_cc']=None;cc['rx_oi']['av_cc']=None
 casos.append(ejecutar(f'R{n}-avcc-null',cc,lambda a,h:ID not in a,'AV ausente no es normal ni deficiente; no imputar exploración'))
 for hallazgo in ('Pseudofaquia OI sin opacidad.','Lesion macular OD conocida.','Blefaritis OI leve.'):
  casos.append(ejecutar(f'R{n}-coexistencia-{hallazgo}',{**b,'anexos':hallazgo},lambda a,h:ID in a and '20/40 en OD' in a[ID],'Contexto orgánico/implante contralateral no acredita una explicación completa ni borra AV de otro ojo'))
 if n==54:
  inc=deepcopy(b);inc['rx_od']['cilindro']=None
  casos.append(ejecutar('R54-EE-incompleto',inc,lambda a,h:ID not in a,'Comparación EE necesita esfera y cilindro de ambos ojos; null no 0'))
  tro=deepcopy(b);tro['rx_od'].update(esfera=None,cilindro=None);tro['rx_oi'].update(esfera=None,cilindro=None);tro['cover']='OD: Orto | OI: Endo y Tropia'
  casos.append(ejecutar('R54-tropia-sin-Rx',tro,lambda a,h:ID in a and 'endotropia en OI' in a[ID] and '20/40 en OD' in a[ID] and '20/60 en OI' in a[ID] and 'correccion completa' not in a[ID],'Tropia documentada permite coocurrencia neutral; conserva ambos ojos sin suponer corrección completa'))
 if n in (54,55,56):
  child=deepcopy(b);child['edad']=3;child['rx_od']['av_cc']='20/30'
  if n in (54,55):child['rx_oi']['av_cc']='20/30'
  casos.append(ejecutar(f'R{n}-infante20-30',child,lambda a,h:ID in a and '20/30' in a[ID] and 'segun la edad y el metodo' in a[ID] and not any(w in a[ID] for w in ('subnormal','deficit','ambliopia')),'Umbral operativo no demuestra normalidad o déficit universal infantil/BCVA'))
 if n==55:
  dif=deepcopy(b);dif['rx_oi']['esfera']=4.5
  casos.append(ejecutar('R55-bilateral-no-simetria',dif,lambda a,h:ID in a and '+4.00' in a[ID] and '+4.50' in a[ID] and 'simetric' not in a[ID],'Bilateralidad no acredita simetría ni causalidad'))
  partial=deepcopy(b);partial['rx_od']['cilindro']=None;partial['rx_oi']['cilindro']=None
  casos.append(ejecutar('R55-esferas-conocidas-componentes-null',partial,lambda a,h:ID in a and '+4.00' in a[ID] and 'equivalente esferico' not in a[ID],'Esferas documentadas conservadas como esferas; no se calculan EE con componentes null'))
 if n in (55,56,57):
  fused=deepcopy(b);fused['rx_od'].update(esfera=4,cilindro=0,av_cc='20/40');fused['rx_oi'].update(esfera=6,cilindro=0,av_cc='20/60')
  casos.append(ejecutar(f'R{n}-dedupe54-ambos-ojos',fused,lambda a,h:ID not in a and 'ambliopia_sospecha' in a and all(t in a['ambliopia_sospecha'] for t in ('20/40 en OD','20/60 en OI','+4.00','+6.00')),'Deduplicar solo hechos descritos; #54 conserva ambos ojos/AV/Rx/recomendación'))
 if n in (56,57):
  nr=deepcopy(b);nr['rx_od'].update(esfera=None,cilindro=None);nr['rx_oi'].update(esfera=None,cilindro=None)
  casos.append(ejecutar(f'R{n}-sin-Rx',nr,lambda a,h:ID in a and '20/40 en OD' in a[ID] and 'mejor AV corregida' in a[ID],'No exigir Rx documentada como si demostrara corrección óptima; describir AV sin BCVA'))
  cases59=deepcopy(b);cases59['edad']=59
  cases60=deepcopy(b);cases60['edad']=60
  r59=ejecutar(f'R{n}-borde59',cases59);r60=ejecutar(f'R{n}-borde60',cases60)
  t59=r59['salidas'].get(IDS[56],'');t60=r60['salidas'].get(IDS[57],'')
  eq=t59.replace('59 anos','EDAD')==t60.replace('60 anos','EDAD') and bool(t59) and bool(t60)
  for r in (r59,r60):r.update(esperado_independiente='Misma descripción y conducta neutral a59/60, sin causa biológica nueva',cumple_expectativa=eq)
  casos.extend((r59,r60))
  casos.append(ejecutar(f'R{n}-estenopeico', {**b,'motivo':'AV medida con estenopeico sin mejora; graduacion parcial.'},lambda a,h:ID in a and 'estenopeico sin mejora' in a[ID] and 'graduacion parcial' in a[ID] and 'descarta' not in a[ID],'Pinhole opcional como contexto; su resultado no excluye Rx ni equivale a BCVA'))
 hist=historicos(n)
 spans={54:'3874–3888',55:'3890–3904',56:'3906–3920',57:'3922–3936'}
 specific={
 54:'''| Retirar etiología ambliopía; AV + Rx/tropia como coocurrencia neutral, conservando dato y ojo | contexto.py:81–94; R54-base/tropia-sin-Rx | CUMPLE |
| EE solo con esfera/cilindro conocidos en ambos ojos, sin null=0 | _diferencia_refraccion_completa32–39; R54-EE-incompleto | CUMPLE |
| BCVA normal explícita/corrección parcial/adaptación/fiabilidad/diagnóstico previo conservados, sin hallazgo nuevo | _texto_revision_av59–77 solo motivo y vocabulario restringido; controles máximas/fiabilidad/contexto | PARCIAL |
| Implantes/lesión menor/ausencia de keywords no prueban explicación ni ausencia orgánica; no veto global | selección81–83; controles coexistencia y corpus | CUMPLE |
| Dedupe56/57 por hechos/ojos, conservando ambos ojos con pérdida de AV aunque causa coexista | #54 texto toma todos los ojos24–29; corpus y R54-tropia-sin-Rx | CUMPLE |''',
 55:'''| Retirar ambliopía isoametrópica/ausencia orgánica/simetría y aval de corrección completa/estimulación; evaluación pediátrica neutral | contexto.py:98–118; R55-base/no-simetria/coexistencia | CUMPLE |
| No EE con null ni esfera aislada como EE; ambos ojos/rx literales incluso con otros factores de un ojo | _refraccion_registrada42–56; condición102–113; controles componentes-null/coexistencia | CUMPLE |
| Adaptación/máxima AV/fiabilidad/estado previo preservados y contextualizados | _texto_revision_av59–77; R55-maxima-parcial-* /fiabilidad/adaptacion-control | PARCIAL |
| Dedupe54 sin eliminar AV bilateral/cilindros/factores conocidos | condición103–104; R55-dedupe54-ambos-ojos; corpus | CUMPLE |''',
 56:'''| Retirar «inexplicado por Rx», ausencia de factores ambliogénicos/causa, diagnóstico/causalidad automática; no exigir Rx como corrección óptima | contexto.py:139–167; R56-base/sin-Rx/coexistencia | CUMPLE |
| Retirar veto global54/55; restar ojos ya descritos sin borrar AV del otro ojo ni prioridad independiente | _ojos_deficit_inexplicado139–147; R56-dedupe54-ambos-ojos/corpus | CUMPLE para hechos, PARCIAL para prioridad compartida |
| Implante transparente/lesión menor/absence dekeywords no explican toda AV ni descartan orgánico | Sin filtro orgánico139–147; controles coexistencia | CUMPLE |
| Máxima AV/fiabilidad/corrección parcial/adaptación/antecedente literal preservados | _texto_revision_av59–77; máximas/fiabilidad/contexto | PARCIAL |
| Estenopeico opcional/individual no es BCVA ni excluye causa refractiva; cicloplejía no universal | texto no prescribe pinhole/cicloplejía; R56-estenopeico | CUMPLE |
| Umbral60 no introduce explicación etiológica distinta; misma función56/57 | condiciones157–177/textos166–182; R56-borde59/60 | CUMPLE |''',
 57:'''| Edad + AV son datos, no BCVA ni causa orgánica exclusiva; retirar triada catarata/glaucoma/maculopatía y derivación etiológica por edad | contexto.py:170–182; R57-base | CUMPLE |
| Diferencial orgánico solo con hechos adicionales; ausencia/presencia de keywords no justifica veto causal | No filtro orgánico139–147; R57-coexistencia y corpus | CUMPLE |
| Dedupe54 por ojos/hechos conserva AV y recomendación del otro ojo | _ojos_deficit_inexplicado139–147; R57-dedupe54-ambos-ojos/corpus | CUMPLE para hechos, PARCIAL para prioridad compartida |
| Unificar función56/57, sin cambiar causa validada en límite59/60 | Ambos textos comparten _texto_revision_av; R57-borde59/60 | CUMPLE |
| Máxima AV/fiabilidad/corrección parcial/adaptación/estado previo preservados; no asumir máxima AV | _texto_revision_av59–77; R57-maxima-parcial-*/fiabilidad/adaptacion-control | PARCIAL |'''}[n]
 md=f'''# Conformidad #{n} — {ID}

Veredicto determinista: **PARCIAL**. La descripción neutral de AV, los nulos, la lateralidad y la deduplicación cumplen. Persiste omisión de contexto explícito de medición/corrección y de prioridad en episodios actuales junto a otro resuelto o un familiar objeto. El ID legacy no es diagnóstico.

## Matriz de requisitos obligatorios

Orden prevalente: AUDITORIA_CORRELACIONES.md:{spans[n]}; generales:234–256; cierre:3972–4006. Contrato: DICCIONARIO_DATOS_RECETA.md:20–55,70–88,125–135,154–170.

| Requisito obligatorio | Código/evidencia | Estado |
|---|---|---|
{specific}
| AV literal porojo con/sin corrección y comparación si AVsc mejor; no eliminar dato incoherente | _ojos_av_para_revision24–29/_texto_revision_av59–77; R{n}-avsc-mejor/avcc-null | CUMPLE |
| Edad/método contextualizan umbral operativo; no normalidad universal infantil ni AVcc=BCVA | _texto_revision_av63–65 y filtro >20/25; controles infante/corpus | CUMPLE determinista; umbral no se certifica como norma clínica |
| Verificar medición/corrección y evaluar conforme al contexto, sin diagnóstico/certeza, causalidad ni exploraciones inventadas | _texto_revision_av59–77; corpus y controles neutros | PARCIAL por pérdida de límites expresos de fiabilidad/corrección |
| Pérdida visual súbita actual inmediata; diplopía nueva mismo día; no alarma por negación, familiar sujeto, hipótesis o hecho antiguo | binocularidad.py:66–71,107–163; controles actuales básicos correctos; mixto/familiar objeto omiten prioridad; subjuntivo hipotético crea falsa alarma | PARCIAL |
| Prefijo/plazo urgente conservado sin contradicción y reflejado en H01; fusión no reduce prioridad | textos delegan _con_prioridad_visual; R{n}-resuelto-mas-actual/familiar-objeto y variantes diplopía | PARCIAL; distingue H01 de#2 cuando sí existe |
| Qwen real/validación clínica de coocurrencias/umbrales | Sin llamada al proveedor; caso determinista no equivale a salida clínica real | NO VERIFICABLE por separado, sin penalizar implementación por ausencia de proveedor |

## Desvíos reproducidos

- `AV poco confiable, repetir por respuestas inconsistentes.` en motivo no aparece en la salida de #{n}. La regex de contexto acepta «fiable», pero no «confiable»; la recomendación genérica de verificar medición pierde el límite explícito y la necesidad ya documentada de repetirla.
- `BCVA maxima 20/20 obtenida con graduacion completa, receta actual deliberadamente parcial.` se preserva en motivo, pero se omite en anexos/seguimiento. Son fuentes contractuales y contienen literalmente máxima AV y corrección parcial; no se están suponiendo datos fuera del contrato. La entrada puede coexistir con AVcc inferior registrada. Deben conservarse las dos fuentes como referidas y contextualizar su discrepancia, sin convertir AVcc en BCVA.
- `Presento perdida visual subita OD desde hoy mientras cuido a mi madre.` conserva #{n} como aviso no urgente y **H01 queda vacío**. El paciente es sujeto del síntoma y la madre objeto del cuidado. La exclusión por palabra familiar borra la prioridad. También falla la variante de diplopía.
- `Fatiga ocular resuelta, ahora perdida visual subita OD desde hoy.` conserva #{n} sin urgencia. **H01 sí tiene #2**, que reconoce la pérdida súbita y recomienda el mismo día; no se afirma pérdida total de H01 en este caso. La ruta #{n} pierde su acción inmediata por veto global de «resuelta». La variante «ahora diplopia desde hoy» pierde la prioridad propia y deja H01 vacío en la entrada reproducida. Véanse payload/salidas completas y alarmas exactas en JSON.
- `Si presentara perdida visual subita, volveria.` genera falsa urgencia en #{n} y H01. El modo hipotético explícito no equivale a pérdida visual actual. El filtro de certeza/por descartar no reconoce este condicional en subjuntivo.

La dependencia reside en contexto.py:59–77 y binocularidad.py:66–71,107–163; se comparte con42–48/53 y la prioridad de #32. El caso de madre objeto está cruzado con el dictamen de #32 del auditor refractivo. No se atribuye un fallo de H01 al mero hecho de no producir una correlación urgente: la pérdida anterior ocurre al seleccionar/priorizar los hechos que le llegan.

## Ajuste completo recomendado y cobertura

Conservar límites de fiabilidad, protocolo, adaptación, máxima AV y corrección parcial desde las fuentes contractuales que los refieran expresamente a la medición/corrección pertinente. Mantener fuente/certeza/sujeto/estado y dos valores discrepantes sin sustituirlos ni inferir BCVA. Reconocer fiabilidad explícita con su variante léxica «confiable» y orientar repetición/contextualización antes de interpretación cuando lo requiere el registro. Aplicar negación, resolución, cronología, sujeto y modalidad hipotética/condicional por episodio; un familiar objeto o una molestia resuelta no borra una alarma actual del paciente y una posibilidad futura no crea un episodio actual. Selección, acción/plazo y H01 deben usar hechos consistentes y conservar prioridad al fusionar ojos. Preservar la descripción neutral, nulos, Rx literal y deduplicación comprobadas. Incorporar regresiones de las fuentes/episodios anteriores junto a controles familiares sujetos, negados, hipotéticos, antiguos y actuales. **Recomendaciones sin implementar.**

tests/test_ajuste_c{n}.py cubre los{len(hist)} históricos de su corpus, nulos, ojos, contexto básico/urgencia y deduplicación; los controles fallidos nuevos no están cubiertos. {n}-casos.json guarda{len(casos)} controles independientes y el corpus entero con payload/salidas/H01 y etiquetas contractual/legacy. El umbral >20/25 se juzga como operativo y redactado con cautela, no como normalidad clínica universal. Generación Qwen real y validación clínica separadas quedan no verificables.
'''
 persistir(n,{'veredicto':'PARCIAL','historicos':hist,'controles_independientes':casos},md,['AUDITORIA_CORRELACIONES.md','DICCIONARIO_DATOS_RECETA.md','app/correlaciones/contexto.py','app/correlaciones/binocularidad.py','app/correlaciones/registry.py','app/inference.py',f'tests/test_ajuste_c{n}.py'])
 print(n,[r['id'] for r in casos if not r['cumple_expectativa']])
