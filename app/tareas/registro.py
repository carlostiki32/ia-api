"""Registro explícito, validación estructural y degradación informativa."""
import logging
from app.tareas.presupuesto import limite_contexto, modo_conteo, contador

class Registro:
    def __init__(self): self.tareas = {}
    def registrar(self, tarea):
        f = tarea.ficha
        if f.nombre in self.tareas: raise ValueError('Nombre duplicado')
        if f.montaje == 'registro':
            rutas = [r for t in self.tareas.values() if t.ficha.montaje == 'registro' for r in t.ficha.rutas]
            if len(set(f.rutas)) != len(f.rutas) or any(r in rutas for r in f.rutas): raise ValueError('Ruta duplicada')
        self.tareas[f.nombre] = tarea
        if any(l.entrada() + l.opciones(None)['num_predict'] > limite_contexto() for l in f.llamadas):
            logging.getLogger(__name__).error('Tarea degradada por presupuesto: %s', f.nombre)
        return tarea
    def tabla(self):
        tabla = {}
        for nombre, t in self.tareas.items():
            f = t.ficha
            llamadas = []
            for l in f.llamadas:
                opciones = l.opciones(None)
                llamadas.append(dict(etapa=l.etapa, prompt_version=l.prompt_version, formato=l.formato,
                    **opciones, max_tokens_entrada=l.entrada(), limite_contexto=limite_contexto(),
                    cabe=opciones['num_predict'] > 0 and l.entrada() + opciones['num_predict'] <= limite_contexto()))
            tabla[nombre] = dict(version=f.version, descripcion=f.descripcion, rutas=f.rutas, endpoints=f.rutas,
                padre=f.padre, montaje=f.montaje, prioridad=f.prioridad, modo_fallo=f.modo_fallo, usa_llm=bool(llamadas),
                respaldo=f.respaldo, llamadas=llamadas, degradada=any(not l['cabe'] for l in llamadas),
                modo_conteo=modo_conteo(f.sin_conteo_exacto),
                pre_tokenizador=contador.pre_tokenizador)
        return tabla
    def degradadas(self): return [n for n, f in self.tabla().items() if f['degradada']]

REGISTRO = Registro()
registrar = REGISTRO.registrar

def validar_registro(): return REGISTRO.degradadas()

def cargar_definiciones():
    from app.tareas.definiciones import receta_clinica, explicacion_paciente, seguimiento_whatsapp
    for modulo in (receta_clinica, explicacion_paciente, seguimiento_whatsapp):
        if modulo.tarea.ficha.nombre not in REGISTRO.tareas: registrar(modulo.tarea)
