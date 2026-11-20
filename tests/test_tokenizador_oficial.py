"""Comparación opcional con el tokenizador oficial local."""
import json
import os
import pytest
import unicodedata
from pathlib import Path


from app.tareas.presupuesto import ContadorExacto, renderizar  # noqa: E402
from app.prompt_builder import build_system_prompt, build_user_prompt  # noqa: E402
from app.schemas import ImpresionClinicaRequest  # noqa: E402
from app.seguimiento.prompts import SYSTEM_PROMPT_REDACCION, build_user_prompt_redaccion  # noqa: E402
from app.seguimiento.schemas import SeguimientoWhatsappRequest  # noqa: E402
from app.seguimiento.catalogo import HECHOS  # noqa: E402



def test_tokenizador_oficial():
    ruta_env = os.environ.get("QWEN_TOKENIZER_JSON")
    if not ruta_env:
        pytest.skip("QWEN_TOKENIZER_JSON no configurado")
    from tokenizers import Tokenizer
    ruta = Path(ruta_env)
    assert ruta.is_file(), ruta
    oficial = Tokenizer.from_file(str(ruta))
    datos = json.loads((ruta).read_text(encoding="utf-8"))
    vocab = datos["model"]["vocab"]
    tokens = [None] * (max(vocab.values()) + 1)
    for t, i in vocab.items():
        tokens[i] = t
    tipos = [1] * len(tokens)
    for a in datos["added_tokens"]:
        while len(tokens) <= a["id"]:
            tokens.append(None); tipos.append(1)
        tokens[a["id"]] = a["content"]; tipos[a["id"]] = 3 if a["special"] else 4
    faltan = [i for i, t in enumerate(tokens) if t is None]
    for i in faltan:
        tokens[i] = f"<|relleno_{i}|>"; tipos[i] = 3
    info = {"model_info": {"tokenizer.ggml.pre": "qwen35", "tokenizer.ggml.tokens": tokens,
                           "tokenizer.ggml.merges": [" ".join(m) if isinstance(m, list) else m for m in datos["model"]["merges"]], "tokenizer.ggml.token_type": tipos,
                           "tokenizer.ggml.add_bos_token": False}}
    w3 = ContadorExacto.reconstruir(info)
    dicc = Path("DICCIONARIO_DATOS_RECETA.md").read_text(encoding="utf-8")
    import re  # noqa: E402
    golden = json.loads(re.search(r"## 5\. Golden Payload.*?```json\s*(\{.*?\})\s*```", dicc, re.S).group(1))
    req = ImpresionClinicaRequest.model_validate(golden)
    sreq = SeguimientoWhatsappRequest.model_validate(json.loads(
        Path("tests/fixtures/seguimiento_whatsapp/g2-request.json").read_text(encoding="utf-8")))
    corpus = {
        "prosa": "La revisión periódica permite comprobar si su graduación sigue siendo la adecuada para sus actividades.",
        "cifras": "OD -2.25 -0.50 x 180 ADD +2.25; OI +1.75 -0.75 x 90; K1 43.25 D @ 175, K2 44.50 D @ 85; PIO 14 mmHg.",
        "simbolos": "¿Qué día? ¡Hola! (o/i) <<>> {json: [1, 2]} --- *** ~~~ ### @@@ $$$ %%% &&& «comillas»",
        "emoji": "Gracias 😀👍🏽 nos vemos 🧪👓✨ — ñandú Ü ç ß 日本語 עברית العربية",
        "saltos": "línea 1\nlínea 2\r\n\n\t tabulado   espacios    finales   \n",
        "marcadores": "Texto con <|im_start|> y <|im_end|> y <think> literal dentro del contenido.",
        "chatml": renderizar("Eres un asistente.", "Hola, ¿cómo está?"),
        "clinico_system": build_system_prompt(),
        "clinico_user": build_user_prompt(req),
        "clinico_renderizado": renderizar(build_system_prompt(), build_user_prompt(req)),
        "seguimiento_renderizado": renderizar(SYSTEM_PROMPT_REDACCION, build_user_prompt_redaccion(sreq, [h.id for h in HECHOS])),
        "acento_descompuesto": unicodedata.normalize("NFD", "revisión óptica señal"),
    }
    for nombre, texto in corpus.items():
        esperado = len(oficial.encode(texto).ids)
        obtenido = len(w3.encode(texto).ids)
        if nombre == "acento_descompuesto":
            assert obtenido >= esperado, nombre
        else:
            assert obtenido == esperado, (nombre, esperado, obtenido)
        print(nombre, esperado, obtenido)
