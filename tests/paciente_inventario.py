"""Inventario AST independiente del catálogo: detecta nuevas ramas de acción.

Las interpolaciones de plazo, examen y pediatría se enumeran explícitamente.
No ejecuta ni altera constructores clínicos; omite cadenas de documentación.
"""
import ast
from itertools import product
from pathlib import Path
import re

VARIABLES = {
    "plazo": ("el mismo dia", "urgente", "inmediata en urgencias"),
    "examen": ("de retina y via visual aferente", "de la respuesta y anatomia pupilar"),
    "pediatrico": ("", " pediatrica"),
    "valoracion": ("valoracion retinologica", "valoracion retinologica preferente"),
    "texto": ("Hallazgo urgente: hallazgo",),
}
ALIASES = {"_eval_fondo_periferico": "fondo_periferico_riesgo", "_eval_fondo_oclusion_raw": "fondo_oclusion_vascular_urgente",
           "_eval_fondo_embolo": "fondo_embolo_retiniano", "_texto_revision_av": "deficit_visual_inexplicado_refractivo"}


def _plantillas(n, variables=None):
    variables = variables or VARIABLES
    if isinstance(n, ast.IfExp): return (*_plantillas(n.body, variables), *_plantillas(n.orelse, variables))
    if isinstance(n, ast.Constant) and isinstance(n.value, str): return (n.value,)
    if isinstance(n, ast.JoinedStr):
        partes = [_plantillas(v, variables) if not isinstance(v, ast.FormattedValue) else _variable(v.value, variables) for v in n.values]
        return tuple("".join(p) for p in product(*partes))
    if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Add):
        return tuple(a + b for a, b in product(_plantillas(n.left, variables), _plantillas(n.right, variables)))
    return _variable(n, variables)


def _variable(n, variables):
    return variables.get(n.id, ("hallazgo",)) if isinstance(n, ast.Name) else ("hallazgo",)


def inventario():
    resultado = []
    for path in sorted(Path("app/correlaciones").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        padres = {hijo: padre for padre in ast.walk(tree) for hijo in ast.iter_child_nodes(padre)}
        for fn in (n for n in tree.body if isinstance(n, ast.FunctionDef)):
            nombre = ALIASES.get(fn.name, re.sub(r"^_(?:eval|texto)_", "", fn.name).removesuffix("_info"))
            if not fn.name.startswith(("_eval_", "_texto_", "_con_prioridad_visual")): continue
            variables = dict(VARIABLES)
            for asignacion in ast.walk(fn):
                if isinstance(asignacion, ast.Assign) and isinstance(asignacion.value, (ast.IfExp, ast.Constant)):
                    for target in asignacion.targets:
                        if isinstance(target, ast.Name) and target.id in VARIABLES:
                            variables[target.id] = _plantillas(asignacion.value, variables)
            for n in ast.walk(fn):
                if not isinstance(n, (ast.Constant, ast.JoinedStr, ast.BinOp, ast.IfExp)): continue
                if isinstance(padres.get(n), (ast.JoinedStr, ast.BinOp, ast.FormattedValue, ast.IfExp)): continue
                if isinstance(padres.get(n), ast.Expr): continue
                if isinstance(padres.get(n), ast.Assign) and any(isinstance(t, ast.Name) and t.id == "valoracion" for t in padres[n].targets): continue
                for texto in _plantillas(n, variables):
                    if re.search(r"(?:valoracion (?:oftalmolog|retinolog|medica|especializada|de retina|con su medico)|evaluacion (?:oftalmolog|medica|corneal especializada|especializada)|derivacion|referencia a oftalmologia|exploracion (?:programada de la periferia|de retina periferica)|(?:mantener|verificar) (?:su |el )?seguimiento (?:retinologico|oftalmologico)|contacto con oftalmologia)", texto):
                        resultado.append({"archivo": str(path).replace("\\", "/"), "funcion": fn.name, "correlacion": nombre, "texto": texto})
    # Una misma rama puede contener fragmentos equivalentes.
    return list({(r["archivo"], r["funcion"], r["texto"]): r for r in resultado}.values())


def expandir_consumidores(inventario_base, binoculares):
    resultado = []
    for x in inventario_base:
        if x["funcion"] == "_con_prioridad_visual":
            nombres = binoculares
        elif x["funcion"] == "_texto_revision_av":
            nombres = ("ambliopia_sospecha", "ambliopia_isoametropica_bilateral", "deficit_visual_inexplicado_refractivo", "adulto_mayor_screening")
        else:
            nombres = (x["correlacion"],)
        for nombre in nombres:
            texto = x["texto"]
            if nombre == "ambliopia_isoametropica_bilateral" and x["funcion"] == "_texto_revision_av":
                texto = texto.replace("evaluacion oftalmologica", "evaluacion oftalmologica pediatrica")
            resultado.append({**x, "correlacion": nombre, "texto": texto})
    return resultado
