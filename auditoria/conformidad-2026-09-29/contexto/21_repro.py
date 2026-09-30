from comun import ejecutar,historicos,persistir
ID='ojo_seco_evaporativo_dgm'
negative=['DGM en la madre.','DGM resuelta.','DGM diagnosticada previamente, controlada.',
 'Meibomio normal. Atrofia conjuntival OI.','Meibomio normal. Secrecion espesa en glandulas de Zeis OD.',
 'Meibomio OD normal y atrofia conjuntival OI.','Madre con DGM.','Posible DGM OD.',
 'Blefaritis anterior OD.','Glandulas de Meibomio sin alteraciones.','DGM estable conocida.']
casos=[ejecutar(f'R21-neg-{i}',{'but':4,'anexos':t},lambda a,h:ID not in a,'No asociar BUT del paciente con anomalía ajena, resuelta, hipotética o de otra estructura') for i,t in enumerate(negative,1)]
casos.append(ejecutar('R21-ojos-mixtos',{'but':4,'anexos':'Glandulas de Meibomio OD normales, glandulas de Meibomio OI atroficas.'},lambda a,h:'atrofia meibomiana descrita OI' in a.get(ID,'') and 'descrita OD' not in a.get(ID,''),'Conservar anomalía OI sin transformar normalidadOD ni asignar lateralidad al BUT'))
for i,t in enumerate(['Obstruccion de orificios meibomianos OD.','Secrecion meibomiana espesa OI.','Glandulas de Meibomio OD no permeables.','No hay atrofia meibomiana, pero secrecion meibomiana espesa OI.'],1):
 casos.append(ejecutar(f'R21-pos-{i}',{'but':4,'anexos':t},lambda a,h:ID in a and '4 segundos' in a[ID] and not {'but_critico','but_limitrofe','but_pantallas'}&a.keys(),'Anatomía y anomalía afirmadas; conservar número y fusionar BUT'))
for v in (None,9,10,15):
 casos.append(ejecutar(f'R21-frontera-{v}',{'but':v,'anexos':'Disfuncion meibomiana OI.'},lambda a,h,v=v:(ID in a)==(v is not None and v<10),'BUT disponible<10, null no positivo'))
hist=historicos(21);positive={1,2,8,15,16,17,18,19,20,21,27,28,29,30,33,34,35,36}
for r in hist:
 r['esperado_independiente_activacion']=int(r['id'].split('-')[1]) in positive;r['cumple_activacion']=(ID in r['salidas'])==r['esperado_independiente_activacion']
texto='''# Conformidad #21 — ojo_seco_evaporativo_dgm

Veredicto: **NO CUMPLE**. La salida ya es descriptiva y el corpus positivo/negativo clásico pasa; faltan requisitos obligatorios de anomalía actual del paciente, anatomía vinculada y lateralidad por mención.

## Matriz completa contra la orden oficial

Fuente prevalente: AUDITORIA_CORRELACIONES.md:2931–2980, A:2935–2939 y D:2967–2977; generales:234–256; cierre:3988–3996. Contrato: DICCIONARIO_DATOS_RECETA.md:49–55,111–120,125–135. El estado4029 no redefine los requisitos.

| Requisito obligatorio | Evidencia/código | Estado |
|---|---|---|
| Retirar predominio evaporativo y ausencia acuosa inferida | superficie_ocular.py:164–166; corpus/salidas | CUMPLE |
| BUT disponible y alteración meibomiana actual afirmada del paciente | superficie_ocular.py:115–161; R21-neg-1/2/3 | NO CUMPLE: familiar pospuesto y estados resuelto/controlado activan |
| No Meibomio/glándula/blefaritis/glandular genéricas como positivos solos | R21-neg-9/10; patrones:132–142 | CUMPLE por sí solos; NO CUMPLE al prestar anatomía a otra cláusula |
| Obstrucción, secreción, expresibilidad y atrofia vinculadas explícitamente a Meibomio | superficie_ocular.py:118–142; R21-neg-4/5/6 | NO CUMPLE: atrofia conjuntival y secreción de Zeis se llaman meibomianas |
| Normalidad, negación, certeza y cronología por mención | superficie_ocular.py:127–152; R21-neg-2/3, controles positivos/negativos | PARCIAL: prefijos/negación básica pasan, estado resuelto sin doble marcador falla |
| Normalidad de un ojo/estructura no borra otra anomalía; conservar ojo del hallazgo | asignación única por frase:143; R21-ojos-mixtos | PARCIAL: anomalía se conserva pero pierde OI cuando la frase contiene ambos ojos |
| No asignar lateralidad/técnica/síntomas al BUT si no constan | texto164–166 y R21-pos-1–4 | CUMPLE en controles; fiabilidad comparte pérdida de fuentes de #20 |
| Aviso de evaluar estabilidad y función, sin confirmar enfermedad; ausencia no descarta | texto164–166; fronterasnull/9/10/15 | CUMPLE en texto; asociación inválida viola requisito de hechos reales |
| Fusionar BUT conservando ambos hechos, sin tres confirmaciones | condiciones31/95/108/157–161; R21-pos y C21 | CUMPLE si extracción válida; falsas asociaciones suprimen BUT neutral |
| Antecedentes estables como contexto, sin nueva sospecha | R21-neg-3/11; patrones128–129 | PARCIAL: 'previa resuelta'/'estable conocida' pasan, 'previamente, controlada' falla |
| Sin urgencia por BUT/DGM, mantener señales independientes | H01 de corpus/control; prefijo ausente | CUMPLE para combinación aislada; no se ensayó Qwen real |

## Desvíos concretos y recomendación completa

Todos los siguientes son textos libres válidos, ≤255 caracteres, con BUT=4 y lente contractual monofocal; no usan campos inexistentes ni cover legacy:

- `DGM en la madre.` activa21 como dato del paciente; `Madre con DGM.` no activa. El sujeto pospuesto cambia el resultado.
- `DGM resuelta.` y `DGM diagnosticada previamente, controlada.` se presentan como alteración actual. El filtro exige simultáneamente un token exacto de antecedente y otro de estabilidad; resuelta sola y previamente no bastan.
- `Meibomio normal. Atrofia conjuntival OI.` produce `atrofia meibomiana descrita OI`. `Meibomio normal. Secrecion espesa en glandulas de Zeis OD.` produce secreción meibomianaOD. La variable de contexto persiste entre cláusulas y solo se reinicia para anatomía lagrimal.
- `Glandulas de Meibomio OD normales, glandulas de Meibomio OI atroficas.` produce atrofia sin ojo, pese a la lateralidadOI explícita. La asignación de ojo por frase solo admite uno cuando no aparece el otro.

Recomendación completa: extraer ocurrencias anatómicas y anomalías como hechos con sujeto, ojo, estado, certeza, negación y fuente; asociar atributos a la mención/estructura correspondiente, nunca mediante un estado global que atraviesa normalidad o cambia a conjuntiva/Zeis. Resolver sujeto antes y después del hallazgo; reconocer resuelto/controlado/previo sin obligar a dos marcadores literales exactos. Preservar antecedentes como contexto y no como nueva asociación. En frases con ambos ojos, mantener solo anomalía afirmada con su ojo; la normalidad contralateral no la elimina. Solo una asociación válida puede deduplicar20/22/23; el aviso conservará número, método/fiabilidad real y hallazgo. Mantener límites<10 y todos los negativos fiables; añadir estos controles con expectativas independientes y sin añadir datos hipotéticos. **No implementado.**

## Cobertura y límites

tests/test_ajuste_c21.py:10–27 usa36 históricos y tres controles de anatomía/negación; no prueba los sujetos pospuestos, resuelto sin antecedente, préstamo anatómico a conjuntiva/Zeis ni ojo de anomalía en una frase bilateral. Las aserciones de texto no exigen lateralidad de cada mención. Evidencia completa en21-casos.json; reproducción21_repro.py. La conformidad con Qwen real y validación clínica son no verificables aquí, sin convertir ese límite en explicación de los fallos deterministas.
'''
persistir(21,{'veredicto':'NO CUMPLE','historicos':hist,'controles_independientes':casos},texto,['AUDITORIA_CORRELACIONES.md','DICCIONARIO_DATOS_RECETA.md','app/correlaciones/superficie_ocular.py','app/correlaciones/registry.py','tests/test_ajuste_c21.py'])
print([(c['id'],c['entrada']) for c in casos if not c['cumple_expectativa']])
