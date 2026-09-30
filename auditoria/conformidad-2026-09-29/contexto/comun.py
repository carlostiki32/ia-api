"""Arnes read-only; evidencia persistida exclusivamente en este directorio."""
from pathlib import Path
import hashlib,json,re,sys
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT))
OUT=Path(__file__).resolve().parent
from app.schemas import ImpresionClinicaRequest
from app.correlaciones.registry import evaluar_correlaciones_con_nombres
from app.inference import _get_active_emergency_alerts
ALIAS={'fondo':('clinica','fondo_de_ojo'),'anexos':('clinica','anexos_oculares'),
 'pupilas':('clinica','reflejos_pupilares'),'motilidad':('clinica','motilidad_ocular'),
 'campos':('clinica','confrontacion_campos_visuales'),'amsler':('clinica','grid_de_amsler'),
 'cover':('clinica','cover_test'),'ppc':('clinica','ppc_cm'),'but':('clinica','ojo_seco_but_seg'),
 'pantallas':('clinica','uso_pantallas'),'seguimiento':('clinica','recomendacion_seguimiento'),
 'motivo':('paciente','motivo_consulta'),'ocupacion':('paciente','ocupacion'),
 'edad':('paciente','edad'),'lente':('tipo_lente',)}
AV={'20/'+str(n) for n in (10,15,20,25,30,40,50,60,70,80,100,120,160,200,400,600)}

def payload(entrada):
 d={'receta_id':'auditoria-conformidad-sintetica','tipo_lente':'monofocal',
 'paciente':{'ocupacion':'No referida','motivo_consulta':'Evaluacion optometrica'},
 'refraccion':{'od':{'esfera':0.0},'oi':{'esfera':0.0}}}
 for k,v in entrada.items():
  if k in ('rx_od','rx_oi'):d['refraccion'][k[-2:]].update(v)
  elif k in ('akr_od','akr_oi'):d.setdefault('akr',{}).setdefault(k[-2:],{}).update(v)
  elif k=='akr':d.setdefault('akr',{}).update(v)
  else:
   ruta=ALIAS[k]
   if len(ruta)==1:d[ruta[0]]=v
   else:d.setdefault(ruta[0],{})[ruta[1]]=v
 return d

def categoria(d):
 problemas=[]
 if d.get('tipo_lente') not in ('monofocal','bifocal_blended','progresivo','flat_top'):problemas.append('lente fuera de enum')
 age=d.get('paciente',{}).get('edad')
 if age is not None and (not isinstance(age,int) or not 0<=age<=125):problemas.append('edad fuera de entero0..125')
 clinica=d.get('clinica',{})
 for key in ('ojo_seco_but_seg','ppc_cm'):
  v=clinica.get(key)
  if v is not None and (not isinstance(v,int) or not 1<=v<=15):problemas.append(f'{key} fuera de entero1..15')
 if clinica.get('uso_pantallas') not in (None,'lt2','btw2_6','gt6'):problemas.append('pantallas fuera de enum')
 for key in ('anexos_oculares','fondo_de_ojo','reflejos_pupilares','motilidad_ocular','confrontacion_campos_visuales','grid_de_amsler'):
  if clinica.get(key) is not None and len(clinica[key])>255:problemas.append(f'{key} excede255')
 if clinica.get('recomendacion_seguimiento') is not None and len(clinica['recomendacion_seguimiento'])>60000:problemas.append('seguimiento excede60000')
 for key,maxlen in (('motivo_consulta',1000),('ocupacion',120)):
  if d.get('paciente',{}).get(key) is not None and len(d['paciente'][key])>maxlen:problemas.append(f'{key} excede{maxlen}')
 for side in ('od','oi'):
  eye=d.get('refraccion',{}).get(side,{})
  for key in ('av_sc','av_cc'):
   if eye.get(key) is not None and eye[key] not in AV:problemas.append(f'{side}.{key} fuera de dropdown')
  if eye.get('cilindro') is not None and not (-8<=eye['cilindro']<=0):problemas.append(f'{side}.cilindro fuera de dropdown')
  for key in ('esfera','cilindro','add'):
   v=eye.get(key)
   if v is not None and abs(v*4-round(v*4))>1e-8:problemas.append(f'{side}.{key} fuera de paso0.25')
  if eye.get('esfera') is not None and not -30<=eye['esfera']<=30:problemas.append(f'{side}.esfera fuera de persistencia-30..30')
  if eye.get('add') is not None and not 0<=eye['add']<=30:problemas.append(f'{side}.add fuera de rango0..30')
  if eye.get('eje') is not None and (not isinstance(eye['eje'],int) or not 0<=eye['eje']<=180):problemas.append(f'{side}.eje fuera de entero0..180')
 cover=d.get('clinica',{}).get('cover_test')
 patron=r'OD: (?:Orto|Endo|Exo|Hiper|Hipo)(?: y (?:Tropia|Foria))? \| OI: (?:Orto|Endo|Exo|Hiper|Hipo)(?: y (?:Tropia|Foria))?'
 if cover and not re.fullmatch(patron,cover):problemas.append('cover fuera de serializacion canonica')
 return {'categoria':'legacy/tolerancia fuera de serializacion' if problemas else 'contrato SaaS','motivos_categoria':problemas}

def ejecutar(id,entrada,check=None,esperado=None):
 raw=payload(entrada);req=ImpresionClinicaRequest.model_validate(raw)
 active=dict(evaluar_correlaciones_con_nombres(req));alerts=[{'id':a.id,'repr':str(a)} for a in _get_active_emergency_alerts(req)]
 result={'id':id,'entrada':entrada,'payload':raw,**categoria(raw),'salidas':active,'h01':alerts}
 if esperado is not None:result['esperado_independiente']=esperado
 if check is not None:result['cumple_expectativa']=bool(check(active,alerts))
 return result

def historicos(n):
 rows=json.loads((ROOT/'auditoria/2026-09-21/casos.json').read_text(encoding='utf-8'))
 return [ejecutar(c['id'],c['entrada']) for c in rows if c['id'].startswith(f'C{n}-')]

def persistir(n,datos,markdown,fuentes):
 hashes={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in fuentes}
 artifact={'correlacion':n,'fecha':'2026-09-29','modo':'SOLO AUDITORIA; sin LLM ni cambios de produccion/pruebas/catalogo',
 'hashes':hashes,'base_explicita':'Rx esfera0 por ojo y tipo_lente monofocal; payload completo conservado, sin BCVA ni exploraciones imputadas.',**datos}
 (OUT/f'{n}-casos.json').write_text(json.dumps(artifact,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
 (OUT/f'{n}.md').write_text(markdown.strip()+'\n',encoding='utf-8')
 print(f'{n}: informe y evidencia persistidos')
