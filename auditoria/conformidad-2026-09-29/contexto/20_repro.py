from comun import ejecutar,historicos,persistir
ID='but_critico'
casos=[]
for v in [None,*range(1,16)]:
 casos.append(ejecutar(f'R20-frontera-{v}',{'but':v},lambda a,h,v=v:(ID in a)==(v is not None and v<5) and not any(x['id']==ID for x in h),'#20 solo 1-4; null no es cero; sin urgencia numerica'))
for field in ('motivo','anexos','seguimiento'):
 casos.append(ejecutar(f'R20-fiabilidad-{field}',{'but':4,field:'BUT poco confiable, pendiente repetir.'},lambda a,h:'poco confiable' in a.get(ID,''),'Conservar limitacion explicita de la medicion, sin restringirla a un campo no impuesto por la orden'))
casos.append(ejecutar('R20-tecnica',{'but':4,'motivo':'BUT medido con fluoresceina.'},lambda a,h:'tecnica con fluoresceina' in a.get(ID,''),'Conservar tecnica afirmada'))
casos.append(ejecutar('R20-tecnica-ajena',{'but':4,'motivo':'Madre con BUT medido con fluoresceina. Paciente sin tecnica registrada.'},lambda a,h:'tecnica' not in a.get(ID,''),'No transferir tecnica del familiar'))
casos.append(ejecutar('R20-pediatrico',{'but':4,'edad':3},lambda a,h:'4 segundos' in a.get(ID,'') and not any(x in a.get(ID,'') for x in ('grave','critico','diagnostico','bilateral')),'Dato corto y evaluacion, sin estadio pediatrico inventado'))
casos.append(ejecutar('R20-alarma-independiente',{'but':4,'anexos':'Ulcera corneal OD.','motivo':'Dolor ocular OD desde hoy.'},lambda a,h:ID in a and any(x['id']=='anexos_patologicos' for x in h),'BUT no crea urgencia; lesion independiente conserva H01'))
hist=historicos(20)
for r in hist:
 v=r['entrada'].get('but');espera=v is not None and v<5 and r['id']!='C20-23'
 r['esperado_independiente_activacion']=espera;r['cumple_activacion']=(ID in r['salidas'])==espera
texto='''# Conformidad #20 — but_critico

Veredicto: **PARCIAL**. El intervalo y la salida neutral cumplen; se omite una limitacion de fiabilidad del propio BUT cuando esta en anexos o seguimiento. Auditoria de conformidad, no validacion clinica ni implementacion.

## Especificacion prevalente y matriz completa

Fuente: AUDITORIA_CORRELACIONES.md:2883–2927, en especial D:2916–2924; reglas generales:234–256 y cierre global:3988–3996. La nota de implementacion:4029 no sustituye estos requisitos. Contrato: DICCIONARIO_DATOS_RECETA.md:49–71,111–120,125–135,154–170.

| Requisito obligatorio | Codigo / evidencia | Estado |
|---|---|---|
| BUT disponible, 1–4, null no cero; conservar unidades/rango | superficie_ocular.py:25–37; R20-frontera-null/1–15 | CUMPLE |
| Numero y aviso de comprobacion/estabilidad, sin graduar enfermedad | superficie_ocular.py:62–72; corpus C20 y R20-pediatrico | CUMPLE |
| Conservar mala fiabilidad y repetir antes de interpretar | superficie_ocular.py:40–60 solo lee motivo; R20-fiabilidad-anexos/seguimiento fallan | PARCIAL |
| No inventar ojo, bilateralidad, tecnica, repeticiones, sintomas ni mecanismo | superficie_ocular.py:62–72; R20-tecnica/tecnica-ajena/pediatrico | CUMPLE en controles reproducidos |
| Critico solo ID; ni gravedad/H01 por numero ni normalidad por silencio | registro:155; fronteras1–15 y corpus | CUMPLE |
| Mantener alarmas independientes y evitar atribucion etiologica | R20-alarma-independiente; prefijo urgente solo #19 | CUMPLE determinista; respuesta Qwen real no verificada |
| Separar contexto/etiologia y fusionar hechos pertinentes sin duplicaciones | superficie_ocular.py:31,157–166; C20-23 conserva4s en #21 | CUMPLE en corpus; validez del extractor21 auditada aparte |
| No certificar diagnostico/pediatria desde estos controles | Salidas y R20-pediatrico | CUMPLE; no existe validacion clinica prospectiva acreditada |

## Desvio reproducible y ajuste completo recomendado

R20-fiabilidad-anexos: BUT=4, anexos=`BUT poco confiable, pendiente repetir.`. R20-fiabilidad-seguimiento coloca la misma frase en el campo libre de seguimiento. Ambos estan dentro del contrato y producen un aviso reducido sin la limitacion que si conserva el caso identico en motivo. La orden exige conservar la mala fiabilidad si el registro la informa y no limita esa exigencia a motivo. No se fabrica la tecnica ni se interpreta un campo nulo: el dato explicito se pierde.

Recomendacion completa: extraer limitaciones/tecnica de fragmentos explicitamente referidos al BUT en las fuentes textuales contractuales pertinentes; conservar fuente, sujeto, estado y certeza. No importar la fiabilidad de otra prueba o familiar ni atribuir ojo al BUT. Si hay discrepancias entre lecturas/textos, conservarlas y pedir contraste; la lectura poco confiable mantiene numero y repeticion previa a interpretacion. Añadir aceptacion independiente de estos dos casos sin cambiar umbrales ni otros avisos. No implementado.

## Cobertura y limites

tests/test_ajuste_c20.py:8–22 cubre30 historicos y un control de Amsler. La activacion usa presencia de21 como parte del oracle; esto no demuestra por si solo que la deduplicacion21 conserve datos validos. Nuevos controles en20_repro.py y salidas/payloads/hashes en20-casos.json. Los casos historicos se vuelven a ejecutar sin adoptar goldens como verdad. Sin llamada al LLM; fidelidad real de Qwen y rendimiento clinico no verificables en este encargo.
'''
persistir(20,{'veredicto':'PARCIAL','historicos':hist,'controles_independientes':casos},texto,['AUDITORIA_CORRELACIONES.md','DICCIONARIO_DATOS_RECETA.md','app/correlaciones/superficie_ocular.py','app/correlaciones/registry.py','tests/test_ajuste_c20.py'])
print([(c['id'],c['cumple_expectativa']) for c in casos if not c['cumple_expectativa']])
