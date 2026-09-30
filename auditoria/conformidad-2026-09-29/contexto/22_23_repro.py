from comun import ejecutar,historicos,persistir

for n,ID,span,category in [(22,'but_pantallas','2984–3025',('btw2_6','gt6')),(23,'but_limitrofe','3029–3063',(None,'lt2'))]:
 casos=[]
 for v in (None,1,4,5,7,9,10,15):
  for p in (None,'lt2','btw2_6','gt6'):
   e=v is not None and 5<=v<=9 and p in category
   casos.append(ejecutar(f'R{n}-matriz-{v}-{p}',{'but':v,'pantallas':p},lambda a,h,e=e:(ID in a)==e and not any(x['id']==ID for x in h),'Selección contractual independiente; null no cero/exposición; sin H01 por número'))
 for field in ('motivo','anexos','seguimiento'):
  casos.append(ejecutar(f'R{n}-fiabilidad-{field}',{'but':7,'pantallas':'gt6' if n==22 else None,field:'BUT poco confiable, pendiente repetir.'},lambda a,h:'poco confiable' in a.get(ID,''),'Conservar fiabilidad explícita del propio BUT en fuente contractual'))
 casos.append(ejecutar(f'R{n}-fuentes-exposicion',{'but':7,'pantallas':'gt6' if n==22 else 'lt2','motivo':'Trabajo diez horas al dia en computadora.'},lambda a,h:'diez horas' in a.get(ID,'') and ('mas de 6 horas' if n==22 else 'menos de 2 horas') in a.get(ID,''),'Conservar fuente estructurada y libre sin sustitución silenciosa'))
 casos.append(ejecutar(f'R{n}-tecnica',{'but':7,'pantallas':'gt6' if n==22 else None,'motivo':'BUT medido no invasivo.'},lambda a,h:'tecnica no invasiva' in a.get(ID,''),'Conservar técnica sin diagnosticar inestabilidad universal'))
 casos.append(ejecutar(f'R{n}-fusion-DGM',{'but':7,'pantallas':'gt6' if n==22 else None,'anexos':'Disfuncion meibomiana OI.'},lambda a,h:ID not in a and '7 segundos' in a.get('ojo_seco_evaporativo_dgm',''),'Deduplicación válida conserva BUT/ojos/contexto, sin mecanismo'))
 if n==23:
  casos.append(ejecutar('R23-alarma-independiente',{'but':7,'anexos':'Defecto epitelial corneal OD.','motivo':'Dolor ocular intenso OD con vision reducida desde hoy.'},lambda a,h:ID in a and any(x['id']=='anexos_patologicos' for x in h),'No suavizar ni suprimir alarma independiente por BUTintermedio'))
 hist=historicos(n)
 for r in hist:
  v=r['entrada'].get('but');p=r['entrada'].get('pantallas');e=v is not None and 5<=v<=9 and p in category and not (n==22 and r['id']=='C22-34')
  r['esperado_independiente_activacion']=e;r['cumple_activacion']=(ID in r['salidas'])==e
 especificos='''| Categoría btw2_6/gt6 conservada, sin reconstruir horas exactas/continuas, pausas, parpadeo o ambiente | superficie_ocular.py:75–86,89–98; matriz y fuentes | CUMPLE |
| No síndrome informático, causa de pantalla, mecanismo/gravedad o derivación automática | _aviso_but62–72; controles/corpus | CUMPLE |
| Fuentes discordantes conservadas, sin reemplazar dropdown | _contexto_pantallas75–86; R22-fuentes-exposicion | CUMPLE |
| Corroboración/evaluación y fusión con avisosBUT, sin confirmaciones repetidas | condiciones31/95/108/157; R22-fusion-DGM | CUMPLE cuando21asocia hechos válidos; defecto21 documentado aparte |''' if n==22 else '''| Retirar leve y equivalencias de enfermedad/síntomas/gravedad/normalidad/etiología | superficie_ocular.py:62–72; corpus y matriz | CUMPLE |
| #22/#23 comparten cautela/recomendación; fusión formal opcional conIDsretendidos | ambos textos98–99/110–111 llaman _aviso_but | CUMPLE |
| Null no exposición baja; sin diferencia de gravedad porpantallas ni ausencia de enfermedad por silencio | matriz y texto/contexto75–86 | CUMPLE |
| Alarmas independientes no se suavizan y BUT aislado no crea urgencia | R23-alarma-independiente falla: #19 emite sin urgencia y H01 queda vacío; matriz BUT sola no urgente | PARCIAL, fallo de integración con #19 |
| Verificar Qwen/coexistencias: controles numéricos no validan clínica | no llamada real almodelo en este encargo; corpus determinista | NO VERIFICABLE para respuesta real; coexistencia determinista comprobada |'''
 text=f'''# Conformidad #{n} — {ID}

Veredicto: **PARCIAL**. Intervalo, categorías, texto neutral y fusión válida cumplen. Persiste pérdida de fiabilidad explícita del propio BUT en anexos/seguimiento, compartida con20. No se declara conformidad por copiar goldens.

## Matriz completa

Orden prevalente: AUDITORIA_CORRELACIONES.md:{span}; requisitos generales:234–256; cierre:3988–3996. Contrato: DICCIONARIO_DATOS_RECETA.md:49–55,111–120,125–135,154–170.

| Requisito obligatorio | Código/evidencia | Estado |
|---|---|---|
| Intervalo5–9 y categoría pertinentes; null no medición; no cambiar unidades | superficie_ocular.py:89–111; R{n}-matriz32combinaciones | CUMPLE |
| Conservar número, comprobación y contexto real, sin certeza universal independiente de método | _aviso_but62–72; R{n}-tecnica/corpus | CUMPLE |
| Conservar fiabilidad/técnica explícita y discordancias | _contexto_medicion_but40–60 solo motivo; R{n}-fiabilidad-anexos/seguimiento fallan | PARCIAL |
{especificos}
| No urgencia/plazo automático por BUT/exposición | H01 de matriz y corpus; prefijo ausente en#{n} | CUMPLE para el BUT aislado |

## Desvío y recomendación completa

Con BUT=7 y categoría correspondiente, `BUT poco confiable, pendiente repetir.` en motivo genera advertencia de repetir antes de interpretar; la misma limitación en anexos o seguimiento se omite. Son campos contractuales libres y no se añade ninguna exploración inexistente. Véanse R{n}-fiabilidad-motivo/anexos/seguimiento en el JSON.

Extender extracción de limitaciones/método solo a fragmentos referidos expresamente al BUT en fuentes contractuales pertinentes, manteniendo sujeto, fuente, estado y negación. No importar fiabilidad de Amsler/otra prueba/familiar. Conservar cifra y recomendación de repetición cuando dudosa, y las dos fuentes cuando discrepan. Preservar selección contractual, texto compartido22/23 y deduplicación con21únicamente si sus hechos son válidos; incorporar regresiones independientes porfuente. La corrección de21anatomía/estado/sujeto se exige por su propia orden. **No implementado.**

{'Además, R23-alarma-independiente contiene BUT=7, defecto epitelial corneal OD en anexos y dolor ocular intenso OD con visión reducida desde hoy. #19 se emite sin prefijo urgente y H01 queda vacío. El BUT no causa ni excusa la pérdida de la alarma; la orden de #23 exige conservar esa vía independiente. Revisar la prioridad de #19 con hechos positivos, ojo y cronología concordantes y verificar coexistencia con #23 y H01. No resolverlo declarando urgente el BUT. Recomendación comunicada al auditor responsable de #19, sin implementación.' if n==23 else ''}

## Cobertura y límites

tests/test_ajuste_c{n}.py cubre{len(hist)} históricos y controles de redacción{'/fuentesdiscordantes' if n==23 else ''}; no cubre limitación BUT fuera de motivo. La selección se deriva de entrada normativa, no de textos golden. Se reejecuta corpus completo y32pares de frontera/categoría, técnica, fiabilidad, exposición y fusión en{n}-casos.json; script22_23_repro.py guarda22antes de iniciar23. Respuesta Qwen real y validación clínica no verificables; no se inventan como aprobadas.
'''
 persistir(n,{'veredicto':'PARCIAL','historicos':hist,'controles_independientes':casos},text,['AUDITORIA_CORRELACIONES.md','DICCIONARIO_DATOS_RECETA.md','app/correlaciones/superficie_ocular.py','app/correlaciones/registry.py',f'tests/test_ajuste_c{n}.py'])
 print(n,[x['id'] for x in casos if not x['cumple_expectativa']])
