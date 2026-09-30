from comun import ejecutar,historicos,persistir
CONFIG={
43:('ppc_exoforia','3700–3714','OD: Exo y Foria | OI: Orto',{'ppc':7},[
('Parser canónico primero: Tropia no vuelve a Exo sin clasificar; ojos/subtipos heterogéneos fieles','binocularidad.py:23–63,173–175,202–225; controlesparser'),
('PPC numérico y protocolo pendiente, no rotura/recuperación/anormalidad universal ni presbicia por edad nula','texto211–225; controlesPPC y corpus15–16'),
('Deduplicar42/48 conservando números y lateralidad;43asintomático no referencia automática','condición202–208; parsermixto y R43-dedupe'),
('Coexistencia con molestias sin etiqueta etiológica; nunca perder episodio agudo documentado','prioridad107–163; controlesagudos')]),
44:('cover_exoforia_sintomatica','3716–3730','OD: Exo y Foria | OI: Orto',{},[
('Síntomas visuales afirmados actuales: no fatiga general/cefalea aislada/monocular/resuelto','detector73–104; historico y controlesnegativos'),
('Exoforia por ojo y síntoma real; evaluación de relación sin descompensación/causalidad/prismas/terapia','texto237–241; controlactual/corpus'),
('No inventar magnitud/reservas/cerca-lejos/control; respeto de tropía mixta/compensación','descripción50–63; mixto/corpus18'),
('Dedupe42 conserva datos y no eleva especificidad; triage agudo con acción/plazo propios','condición228–234 y prioridad156–163; R44-dedupe/agudos')]),
45:('cover_endoforia_sintomatica','3732–3746','OD: Endo y Foria | OI: Orto',{},[
('Manifestaciones visuales afirmadas actuales, literales y sin atribución causal','detector73–104; controleshistorico/negativos'),
('Tipo/subtipo/ojo fieles: Endo sin subtipo no endoforia; precisar registros discordantes','descripción50–63; controlsinsubtipo/mixto'),
('Sin veto global de tropía contralateral; conservar todos los datos','condición244–250; mixto'),
('Retirar exceso de convergencia/disfunción; cuantificar/evaluar relación, no AC/A/mecanismo/terapia','docstring244–245 y texto252–257; corpus'),
('Inicio agudo requiere triage específico y preservación del episodio real','prioridad107–163; controlesagudos')]),
46:('desviacion_vertical','3748–3760','OD: Hiper y Foria | OI: Hipo y Tropia',{},[
('Cada entrada canónica conserva ojo/dirección/subtipo; no llamar manifiesta a foria','descripción50–63; controlesparser/mixto'),
('Conservar Hiper/Hipo sin subtipo y pedir precisarlo; otro subtipo no lo borra','condición260–269 y texto272–277; controlsinsubtipo'),
('Confirmar/cuantificar/relevancia funcional; no síntomas hipotéticos, enfermedad/paresia/prismas','texto272–277; controlasintomatico'),
('Conservar contexto conocido/estable y duda; inicio agudo/asociados con prioridad independiente','contexto166–170 y prioridad107–163; contextoestable/agudos'),
('Hiper/Hipo solos no urgencia ni causa','controlasintomatico/corpus')]),
47:('endotropia_lente','3762–3774','OD: Endo y Tropia | OI: Orto',{},[
('Endotropía por ojo, cuantificar/evaluar estrabismo incluida refracción','condición280–287; controlesparser/mixto'),
('Sin respuesta a corrección/cicloplejia/completitud/uso/componenteacomodativo inventados','texto284–287; controlsinRx y diseños'),
('Rx0dato y Rxnullausente; tipo de lente obligatorio no sustituye receta ni causa','controls sinRx/diseños; contrato65–71,125–135'),
('Conservar conocido/estable, otros hallazgos y respuesta óptica solo documentada','contexto166–170; contextoestable y corpus11/14/15'),
('Inicio/síntomas determinan evaluación y plazo; clasificación no edad/lente/hipermetropía','prioridad107–163; agudos/diseños')]),
48:('exotropia_lente','3780–3792','OD: Exo y Tropia | OI: Orto',{},[
('Entrada por ojo/subtipo;43 no vuelve a llamar sinclasificar a Tropia','condición290–299 y cover23–63; parsermixto'),
('Evaluar/cuantificar frecuencia/control/función/refracción como pendientes','texto295–299; controlasintomatico'),
('No uso/BCVA/intermitencia/control/progresión/causa/terapia/prismas/cirugía inventados','texto295–299; controlsinRx/diseños'),
('Respuesta óptica solo con datos, lente no la acredita; contexto de antecedentes/síntomas fiel','contexto166–170; contextoestable y corpus9/10/14'),
('Evaluación general no reemplaza priorización aguda; C48-12 mantiene H01','prioridad107–163; agudos/corpus12')]),
}
for n,(ID,span,cover,extra,requirements) in CONFIG.items():
 base={'cover':cover,**extra};casos=[]
 actual='Fatiga ocular al leer.' if n in (44,45) else 'Evaluacion optometrica.'
 casos.append(ejecutar(f'R{n}-actual',dict(base,motivo=actual),lambda a,h:ID in a,'Conservar datoobservado/contextosintomático pertinente sin diagnóstico'))
 for key,motivo,urgent in [('agudo','Diplopia desde hoy.',True),('resuelto-mas-actual','Fatiga ocular resuelta, ahora diplopia desde hoy.',True),('contexto-familiar','Presento diplopia desde hoy mientras cuido a mi madre.',True),('familia','Mi madre presenta diplopia desde hoy; yo sin molestias.',False),('hipotesis','Descartar diplopia subita en el estudio actual.',False),('antiguo','Diplopia desde hace diez anos, hoy revision rutinaria.',False)]:
  expected_active=True if n not in (44,45) else urgent
  casos.append(ejecutar(f'R{n}-{key}',dict(base,motivo=motivo),lambda a,h,urgent=urgent,expected_active=expected_active:(ID in a)==expected_active and (a.get(ID,'').startswith('Hallazgo urgente:')==urgent) and (any(x['id']==ID for x in h)==urgent),'Urgencia solo desde episodio actual afirmado del paciente; no borrar episodio nuevo ni transferir familiar/hipótesis/control'))
 if n in (44,45):
  casos.append(ejecutar(f'R{n}-historico',dict(base,motivo='En 2020 tenia fatiga ocular al leer.'),lambda a,h:ID not in a,'Historia fechada no coocurrencia con síntoma actual'))
  for key,t in [('general','Fatiga muscular al correr.'),('cefalea','Cefalea cervical al despertar.'),('monocular','Diplopia monocular.'),('negado','Sin fatiga ocular ni diplopia.')]:
   casos.append(ejecutar(f'R{n}-{key}',dict(base,motivo=t),lambda a,h:ID not in a,'Síntomaextravisual, monocular o negado no sostiene asociaciónbinocular'))
 if n in (46,47,48):
  m='Hallazgo del cover ya evaluado, sin cambios durante anos.'
  casos.append(ejecutar(f'R{n}-contexto-estable',dict(base,motivo=m),lambda a,h:any(x in a.get(ID,'') for x in ('sin cambios','ya evaluado','estable')),'Conservar contexto explícito de estabilidad/evaluación previa, no repetir como hallazgo nuevo sin contexto'))
  casos.append(ejecutar(f'R{n}-conocido',dict(base,motivo='Hallazgo conocido y estable.'),lambda a,h:'conocido y estable' in a.get(ID,''),'Control léxico de antecedenteestable síconservado'))
 if n==43:
  casos.append(ejecutar('R43-tropia-no-foria',{'cover':'OD: Exo y Tropia | OI: Orto'},lambda a,h:ID not in a and 'exotropia_lente' in a,'Tropia aislada no Exo sinclasificar'))
  casos.append(ejecutar('R43-parser-mixto',{'cover':'OD: Exo y Foria | OI: Exo y Tropia'},lambda a,h:'exoforia en OD' in a.get(ID,'') and 'exotropia en OI' in a.get('exotropia_lente','') and 'no clasificada' not in ' '.join(a.values()),'Los dos ojos/subtipos preservados sin fallback'))
  casos.append(ejecutar('R43-dedupe',{'ppc':7,'cover':cover,'motivo':'Fatiga ocular al leer.'},lambda a,h:ID not in a and 'PPC de 7 cm' in a.get('insuficiencia_convergencia','') and 'exoforia en OD' in a.get('insuficiencia_convergencia',''),'42conserva dato al suprimir43'))
 if n==44:
  casos.append(ejecutar('R44-dedupe',{'ppc':7,'cover':cover,'motivo':'Fatiga ocular al leer.'},lambda a,h:ID not in a and 'exoforia en OD' in a.get('insuficiencia_convergencia',''),'42preserva dato y síntoma'))
  mixed='OD: Exo y Foria | OI: Endo y Tropia'
 elif n==45:mixed='OD: Endo y Foria | OI: Endo y Tropia'
 elif n==46:mixed='OD: Hiper y Foria | OI: Hipo'
 elif n==47:mixed='OD: Exo y Foria | OI: Endo y Tropia'
 else:mixed='OD: Endo y Foria | OI: Exo y Tropia'
 if n!=43:
  casos.append(ejecutar(f'R{n}-mixto',{'cover':mixed,'motivo':'Fatiga ocular al leer.'},lambda a,h:ID in a and ('OI' in a[ID] or n==44),'Conservar hallazgos por ojo/subtipo; sin veto global'))
 if n in (45,46):
  c='OD: Endo | OI: Orto' if n==45 else 'OD: Hiper | OI: Hipo'
  casos.append(ejecutar(f'R{n}-sin-subtipo',{'cover':c,'motivo':'Fatiga ocular al leer.'},lambda a,h:ID in a and 'no clasificada' in a[ID],'Tipo sin subtipo permanece sinclasificar'))
 if n in (47,48):
  for lente in ('monofocal','progresivo','bifocal_blended','flat_top'):
   casos.append(ejecutar(f'R{n}-sinRx-{lente}',dict(base,lente=lente,rx_od={'esfera':None,'cilindro':None},rx_oi={'esfera':None,'cilindro':None}),lambda a,h:ID in a and all(x not in a[ID] for x in ('correccion prescrita','cicloplejia','acomodativa','mejor AV','intermitente')),'Lentecontractual no fabrica receta/respuesta/etiología'))
 casos.append(ejecutar(f'R{n}-condicional-subjuntivo',dict(base,motivo='Fatiga ocular actual. Si presentara perdida visual subita, volveria.'),lambda a,h:ID in a and not a[ID].startswith('Hallazgo urgente: ') and not any(x['id']==ID for x in h),'Dato/síntoma actual no se eleva a urgente por una pérdida visual hipotética futura'))
 hist=historicos(n)
 verdict='NO CUMPLE' if n in (44,45) else 'PARCIAL'
 filas='\n'.join(f'| {req} | {src} | '+('PARCIAL/NO CUMPLE en estado/sujeto/cronología: véanse controles fallidos' if any(k in req for k in ('actual','agudo','contexto','prioriz','triage')) else 'CUMPLE en controles/corpus reproducidos')+' |' for req,src in requirements)
 failed=[x['id'] for x in casos if not x['cumple_expectativa']]
 text=f'''# Conformidad #{n} — {ID}

Veredicto: **{verdict}** (conformidad determinista). No se adopta la certificación previa ni golden como especificación. Respuesta Qwen real separada, no verificada.

## Matriz completa contra la orden

Orden prevalente: AUDITORIA_CORRELACIONES.md:{span}; generales234–256 y cierre3988–3996. Contrato: DICCIONARIO_DATOS_RECETA.md:49–71,111–120,125–135,154–170. La nota4029es un estado, no una excepción normativa.

| Requisito obligatorio | Código/evidencia | Estado |
|---|---|---|
{filas}
| Texto como aviso, sin diagnóstico/normalidad ni campos inventados | textosdelID, controles/corpus | CUMPLE en las salidas descriptivas |
| Urgencia por prefijo único, acción/plazo y estado/sujeto compatibles | binocularidad.py:107–163; controlesagudo/resuelto/familiar/condicional-subjuntivo | PARCIAL: se pierden episodios reales y una hipótesis se convierte en urgente |

## Desvíos reproducidos y ajuste completo recomendado

Controles fallidos: {', '.join(failed)}. Las entradas y salidas exactas están en{n}-casos.json; todas las nuevas entradas usan cover canónico conambos ojos, lente del enum y texto libre contractual.

La frase `Fatiga ocular resuelta, ahora diplopia desde hoy.` es descartada íntegramente porresuelta; se pierde el episodio actual y el mismo día/H01. `Presento diplopia desde hoy mientras cuido a mi madre.` se descarta íntegramente por mencionar madre aunque el paciente es sujeto y ella objeto del cuidado. {'Además, `En 2020 tenia fatiga ocular al leer.` activa la asociación que requiere síntomas actuales; el detector no aplica cronología a la selección.' if n in (44,45) else ''} {'El contexto `Hallazgo del cover ya evaluado, sin cambios durante anos.` no se conserva, mientras `conocido y estable` sí: la preservación depende de una lista léxica incompleta.' if n in (46,47,48) else ''}

`Fatiga ocular actual. Si presentara perdida visual subita, volveria.` añade a #{n} falsa urgencia inmediata y alarma H01: la pérdida visual es una hipótesis futura, no un síntoma actual. El condicional en subjuntivo no es reconocido como modalidad hipotética.

Recomendación completa: trabajar por ocurrencias con sujeto/estado/certeza/cronología/modalidad condicional, no descartar por palabra global en todo el fragmento; separar antecedente/resuelto de nuevo episodio e identificar al familiar como sujeto u objeto. Aplicar cronología a síntomas quefundan coocurrencia, preservando síntomas actuales y exclusiones extravisuales/monoculares; una hipótesis futura no es alarma actual. Conservar contexto explícito equivalente a estable/sin cambios y evaluaciónprevia, sin inventar evolución o confirmar una causa. Mantener cover canónico con ojos/subtipos y los datos ya deduplicados. Una alarma real debe conservar acción/plazo/H01; un dato aislado no creaurgencia. Añadir parescontrafactuales del JSON con expectativas independientes sin cambiar cortes ni reactivar inferencias. **Solo recomendación; no implementado.**

## Cobertura y límites

tests/test_ajuste_c{n}.py y las pruebas comunes42/44/46 cubren{len(hist)}historicos delID y variantes; los controles conpero o familiares como sujetos no cubren ahora después de resuelta ni familiar como objeto. El JSON conserva categoría contratoversuslegacy para cada histórico; los casos fuera de serialización canónica no se usan como prueba de conformidad SaaS. Se reejecutó motor/H01 real, sin llamaralLLM. La ausencia de proveedor no es defecto de implementación; no se valida rendimiento clínico a partir de estas muestras.
'''
 persistir(n,{'veredicto':verdict,'historicos':hist,'controles_independientes':casos},text,['AUDITORIA_CORRELACIONES.md','DICCIONARIO_DATOS_RECETA.md','app/correlaciones/binocularidad.py','app/correlaciones/registry.py',f'tests/test_ajuste_c{n}.py'])
 print(n,failed)
