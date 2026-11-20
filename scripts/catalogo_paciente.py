"""Exporta el material vigente del paciente sin cargar settings ni proveedores."""
import argparse
import ast
from collections import defaultdict
import hashlib
from pathlib import Path
import sys

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))

from app.paciente.acciones import CATALOGO  # noqa: E402
from app.paciente.contexto import LENTES  # noqa: E402
from app.paciente.prompts import GLOSARIO, SYSTEM_REDACCION, SYSTEM_VERIFICACION  # noqa: E402


def versiones(rutas):
    """Lee constantes sin importar servicio/integración (configuración y transporte)."""
    for ruta in rutas:
        arbol = ast.parse(ruta.read_text(encoding="utf-8"))
        for nodo in arbol.body:
            if isinstance(nodo, ast.Assign):
                for destino in nodo.targets:
                    if isinstance(destino, ast.Name) and (
                        destino.id == "VERSION" or destino.id.endswith("_VERSION")
                    ):
                        yield ruta.relative_to(RAIZ).as_posix(), destino.id, ast.literal_eval(nodo.value)


def bloque(texto):
    # Conserva el contenido literal incluso si un prompt incorpora fences.
    import re
    ancho = max([2, *(len(m.group()) for m in re.finditer(r"`+", texto))]) + 1
    cerca = "`" * ancho
    return f"{cerca}text\n{texto}\n{cerca}\n"


def generar(tokenizer=None):
    rutas = sorted((RAIZ / "app/paciente").glob("*.py")) + [RAIZ / "app/dual_contract.py"]
    lineas = [
        "# Catálogo y prompts del paciente para revisión",
        "",
        "Generado por `scripts/catalogo_paciente.py` desde el código vigente.",
        "Las frases son el valor literal de `Accion.texto`; no son paráfrasis editoriales.",
        "",
        "## Versiones",
        "",
        "| Archivo | Constante | Valor |",
        "|---|---|---|",
    ]
    for ruta, nombre, valor in versiones(rutas):
        lineas.append(f"| `{ruta}` | `{nombre}` | `{valor}` |")
    lineas += ["", "## Catálogo de acciones", "",
        f"{len(CATALOGO)} variantes de {len({v.accion.correlacion for v in CATALOGO})} correlaciones.",
        "Se conserva el orden del catálogo: en cada correlación se elige la primera",
        "variante compatible de cada grupo; los grupos distintos conservan acciones independientes.",
        "Esta lista no implica que todas las variantes puedan activarse juntas.",
        "La variante dinámica `sin_mapear` se construye a partir del texto clínico",
        "en `_desconocida`; no tiene una frase fija que pueda enumerarse aquí.", ""]
    grupos = defaultdict(list)
    for variante in CATALOGO:
        grupos[variante.accion.correlacion].append(variante)
    for correlacion, variantes in grupos.items():
        lineas += [f"### {correlacion}", ""]
        for variante in variantes:
            accion = variante.accion
            lineas += [f"#### Variante `{accion.variante}`", "",
                f"- Grupo: `{variante.grupo}`.",
                f"- Prioridad: `{accion.prioridad}`.",
                f"- Plazo explícito: {accion.plazo or '(vacío en el catálogo)'}.",
                "", "Frase exacta para el paciente:", "", bloque(accion.texto)]
    glosario = "\n".join(k + ": " + v + "." for k, v in GLOSARIO.items())
    textos = [
        ("Glosario", glosario),
        ("System prompt de redacción", SYSTEM_REDACCION),
        ("System prompt de verificación", SYSTEM_VERIFICACION),
    ]
    lineas += ["## Glosario y system prompts", "",
        "El glosario se muestra con el mismo formato con que se incorpora a redacción.",
        "Los conteos corresponden a cada texto aislado, sin tokens especiales añadidos,",
        "roles, envoltura de chat, user prompt ni esquema JSON; no son el presupuesto por llamada.",
        ""]
    conteos = {}
    for titulo, texto in textos:
        lineas += [f"### {titulo}", ""]
        if tokenizer is None:
            lineas += ["Tokens: sin conteo (use `--tokenizer`).", ""]
        else:
            conteos[titulo] = len(tokenizer.encode(texto, add_special_tokens=False).ids)
            lineas += [f"Tokens: **{conteos[titulo]}**.", ""]
        lineas.append(bloque(texto))
    lineas += ["## Descripciones CPU del lente", ""]
    for nombre, descripcion in LENTES.items():
        lineas += [f"### `{nombre}`", "", bloque(descripcion)]
    lineas += ["## Huellas de las fuentes", "",
        "| Archivo | SHA-256 |", "|---|---|"]
    for ruta in rutas:
        lineas.append(f"| `{ruta.relative_to(RAIZ).as_posix()}` | `{hashlib.sha256(ruta.read_bytes()).hexdigest()}` |")
    return "\n".join(lineas) + "\n", conteos


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--salida", required=True, type=Path)
    parser.add_argument("--tokenizer", type=Path, help="tokenizer.json oficial local")
    args = parser.parse_args()
    tokenizer = None
    if args.tokenizer is not None:
        from tokenizers import Tokenizer
        tokenizer = Tokenizer.from_file(str(args.tokenizer))
    texto, conteos = generar(tokenizer)
    if args.tokenizer is not None:
        texto += ("\nTokenizador local: `" + args.tokenizer.name + "`. SHA-256: `"
                  + hashlib.sha256(args.tokenizer.read_bytes()).hexdigest() + "`.\n")
    args.salida.parent.mkdir(parents=True, exist_ok=True)
    # Normalizar primero evita duplicar CR cuando se ejecuta en Windows.
    texto = texto.replace("\r\n", "\n").replace("\r", "\n")
    args.salida.write_text(texto, encoding="utf-8", newline="\r\n")
    print(f"Salida: {args.salida}")
    print(f"Acciones: {len(CATALOGO)} variantes; {len({v.accion.correlacion for v in CATALOGO})} correlaciones")
    for titulo, cantidad in conteos.items():
        print(f"{titulo}: {cantidad} tokens")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
