"""Detecta pérdida de caracteres en literales y comentarios de la aplicación."""
import io
from pathlib import Path
import re
import tokenize


def test_codificacion_app():
    errores = []
    for ruta in Path('app').rglob('*.py'):
        texto = ruta.read_text(encoding='utf-8')
        assert not any(c in texto for c in ('\ufffd', '\u00c3', '\u00c2')), str(ruta)
        for token in tokenize.generate_tokens(io.StringIO(texto).readline):
            if token.type not in (tokenize.STRING, tokenize.COMMENT):
                continue
            # En regex, ? es un cuantificador válido; se revisan los demás literales.
            if token.type == tokenize.STRING and token.string.lower().startswith(('r"', "r'", 'fr"', "fr'", 'rf"', "rf'")):
                if any(marca in token.string for marca in ('\\', '|', '(')):
                    continue
            if re.search(r'[^\W\d_]\?[^\W\d_]', token.string):
                errores.append((str(ruta), token.start[0]))
    assert not errores, errores
