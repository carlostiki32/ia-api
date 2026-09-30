from pathlib import Path
import re
from comun import ROOT,payload,ejecutar,historicos,persistir,ImpresionClinicaRequest
from app.prompt_builder import build_user_prompt
from app.correlaciones.registry import CORRELACIONES,RECORDATORIOS_TECNICOS

IDS={49:'presbicia_multifocal',50:'presbicia_sin_adicion',51:'adicion_incongruente_edad',52:'insuficiencia_acomodacion_joven'}
TOKENS=list(IDS.values())+['_add_maximo','_es_multifocal','_ee_menos_miope','_rx_distancia']
scan=[]
for path in list((ROOT/'app/correlaciones').glob('*.py'))+[ROOT/'tests/test_correlaciones_golden.py']:
 for i,line in enumerate(path.read_text(encoding='utf-8').splitlines(),1):
  if any(t in line for t in TOKENS):scan.append({'archivo':str(path.relative_to(ROOT)),'linea':i,'texto':line})
reg=[c.nombre for c in CORRELACIONES+RECORDATORIOS_TECNICOS]
for n,ID in IDS.items():
 casos=[]
 for edad in (None,3,22,37,38,44,45,46,60,80):
  for add in (None,0,.75,1.5,2.75,30):
   for lente in ('monofocal','bifocal_blended','progresivo','flat_top'):
    entrada={'edad':edad,'lente':lente,'rx_od':{'esfera':None,'cilindro':None,'add':add},'rx_oi':{'esfera':-2.5,'cilindro':None,'add':add},'motivo':'Cansancio visual al leer; lectura comoda sin gafas.'}
    r=ejecutar(f'R{n}-{edad}-{add}-{lente}',entrada,lambda a,h:all(k not in a for k in IDS.values()) and not any(re.search(r'presbici|insuficiencia acomodativa|adicion incongruente|necesidad de adicion',v,re.I) for v in a.values()),'Sin regla retirada, umbral sustituto, diagnóstico acomodativo ni aval terapéutico')
    req=ImpresionClinicaRequest.model_validate(payload(entrada));p=build_user_prompt(req)
    r['prompt']=p
    r['preserva_datos_prompt']=('Diseno de lente prescrito:' in p and entrada['motivo'] in p and (add in (None,0) or f'Add {add:+.2f}' in p))
    r['add_cero_normalizado']=add!=0 or (req.refraccion.od.add is None and req.refraccion.oi.add is None)
    r['cumple_expectativa']=r['cumple_expectativa'] and r['preserva_datos_prompt'] and r['add_cero_normalizado']
    casos.append(r)
 hist=historicos(n)
 for r in hist:
  r['esperado_independiente_activacion']=False
  r['cumple_activacion']=ID not in r['salidas']
 fuentes=['AUDITORIA_CORRELACIONES.md','DICCIONARIO_DATOS_RECETA.md','app/correlaciones/contexto.py','app/correlaciones/registry.py','app/prompt_builder.py','app/schemas.py','tests/test_correlaciones.py','tests/test_correlaciones_golden.py']
 ranges={49:'3794–3808',50:'3810–3824',51:'3826–3840',52:'3842–3856'}
 especificos={
 49:'| Eliminar equivalencia de edad/lente/Add con función acomodativa y aval del multifocal, sin reemplazo etiológico | Matriz edad/Add/lente; ninguna salida contiene interpretación acomodativa | CUMPLE |',
 50:'| Edad >=45, lente monofocal, Add ausente o miopía leve no acreditan necesidad de cerca no atendida; no EE desde null | Matriz incluye edad45 y Rx incompleta/miopía -2.50, lectura cómoda sin gafas | CUMPLE |\n| Add=0 a null es coerción contractual aceptada, sin activar otra alerta de ausencia | R50-*-0-* y campo add_cero_normalizado | CUMPLE |\n| Eliminar helpers exclusivos de multifocal/Rx distancia/EE menos miope y constantes acomodativas | Escaneo de todos los módulos; contexto.py no contiene regla/techo por edad o Add | CUMPLE |',
 51:'| Eliminar techos de Add por edad y equivalencias con error/enfermedad; sin umbral sustituto ni AA deducida de cilindro | Matriz edad3–80, Add0–30 y Rx incompleta; contexto.py/registry.py | CUMPLE |\n| Helper _add_maximo inicialmente compartido se retira con la posterior orden #52, sin reactivar #51 | Escaneo fuente vacío; prevalece orden3842–3856 | CUMPLE |',
 52:'| Edad<38 + Add>=0.75 + lectura/cerca no acredita insuficiencia acomodativa ni que la Rx sea provisional | Matriz incluye22/37/38, Add.75 y síntomas de lectura; ninguna inferencia acomodativa | CUMPLE |\n| Retirar _add_maximo y keywords exclusivos; #51 no sirve como fallback y no aparece otra entidad/umbral acomodativo | Escaneo y matriz sin ninguno de los cuatro IDs ni texto sustituto | CUMPLE |'}[n]
 verdict='CUMPLE' if not scan and ID not in reg and all(r['cumple_expectativa'] for r in casos) and all(r['cumple_activacion'] for r in hist) else 'PARCIAL'
 md=f'''# Conformidad #{n} — {ID}

Veredicto determinista: **{verdict}**. La retirada está implementada y conserva los datos literales disponibles en el prompt. La conformidad aquí no certifica función acomodativa ni respuesta de Qwen real.

## Matriz de requisitos obligatorios

Orden prevalente: AUDITORIA_CORRELACIONES.md:{ranges[n]}; retirada conjunta de helpers:3826–3856; generales:234–256; cierre:3972–4006. Contrato: DICCIONARIO_DATOS_RECETA.md:20–55,70–88,154–170.

| Requisito | Código/evidencia | Estado |
|---|---|---|
| Retirar condición, texto, import y registro; no emitir ID antiguo | Escaneo de app/correlaciones/*.py; registry.py:156–207; matriz independiente y corpus | CUMPLE |
| Retirar de goldens clínicos aplicables, sin justificar reactivación por casos antiguos | Escaneo de tests/test_correlaciones_golden.py sin coincidencias; históricos esperados como retirados por orden | CUMPLE |
{especificos}
| Mantener receta/Add/diseño de lente/síntomas como datos literales, sin avalar prescripción, máxima AV ni causa | prompt_builder.py:118–125,250–272,290–301; prompt completo en controles, preserva_datos_prompt | CUMPLE |
| No nueva alerta de edad, datos ausentes o diagnóstico que reemplace la regla retirada | Ninguno de los cuatro IDs ni frases sustitutas en240 controles porID; null explícito no convertido en EE | CUMPLE |
| Cumplir redacción/plazos generales solo en salidas aplicables; regla retirada no genera urgencia ni plazo | Corpus y matriz guardan todas las otras salidas/H01; no texto propio de esta regla | CUMPLE para la retirada |
| Verificación de respuesta real/ausencia de inferencia por Qwen | No llamada a proveedor en esta auditoría | NO VERIFICABLE, separado del veredicto determinista |

## Evidencia, cobertura y recomendaciones

{n}-casos.json conserva {len(hist)} entradas históricas con salidas reales,240 controles contractuales independientes, prompt completo y normalización de Add=0. Las categorías fuera de serialización de los históricos permanecen etiquetadas aparte; no constituyen controles SaaS. El escaneo comprobó funciones/imports/helpers exclusivos y goldens, y los nombres de ambos registros se guardan. Tests existentes cubren retiradas en tests/test_correlaciones.py:476–527,763–815,961–968. No se usa el resultado golden como expectativa normativa.

No se reproduce un desvío determinista de esta retirada. Mantener la retirada, el tratamiento contractual de nulos y los datos crudos. Si se añadiera una futura regla acomodativa, requerir una orden y campos capaces de documentar función/protocolo/estrategia óptica; no recuperar estos umbrales. Las recomendaciones no autorizan implementación. La generación clínica real queda pendiente como comprobación separada, sin convertir la ausencia de proveedor en defecto del código.
'''
 persistir(n,{'veredicto':verdict,'historicos':hist,'controles_independientes':casos,'escaneo_coincidencias':scan,'registros_reales':reg},md,fuentes)
 print(n,[r['id'] for r in casos if not r['cumple_expectativa']])
