# Contrato del corpus del validador del paciente (idéntico para Codex y Antigravity)

El corpus vive en `C:\dev\ia-api\tests\fixtures\paciente\corpus\` como archivos JSON (UTF-8, CRLF, un arreglo de casos por archivo, agrupados por regla: `tuteo.json`, `cifras.json`, …, `aceptables.json`). Lo escribe **Antigravity** a partir del diseño (`20-diseno-v2.md` §3, §4 y §6), **sin leer** `app/paciente/validador.py`. Lo consume **Codex** con un adaptador en `tests/test_paciente_corpus.py` que construye el contexto real del validador desde `caso`.

## Formato de cada caso
```json
{
  "id": "tuteo-001",
  "esperado": "rechazar",
  "regla": "tuteo",
  "nota": "Por qué debe rechazarse o aceptarse (una línea).",
  "caso": {
    "impresion_clinica_final": "El paciente acude por visión borrosa de lejos. Presenta miopía en ambos ojos…",
    "rx": {
      "od": {"componentes": ["miopía"], "apoyo_cerca": false, "plano": false},
      "oi": {"componentes": ["miopía", "astigmatismo"], "apoyo_cerca": false, "plano": false}
    },
    "motivo": "Visión borrosa de lejos desde hace meses.",
    "sintomas_referidos": ["vision_borrosa_lejos"],
    "pantallas": null,
    "lente": "monofocal",
    "correlaciones": [{"nombre": "nombre_de_correlacion", "texto": "Texto de la correlación tal como lo da el sistema."}],
    "acciones_obligatorias": ["Le recomendamos acudir con un oftalmólogo en un plazo máximo de 48 horas."]
  },
  "candidato": {"frases": [{"texto": "Tu miopía puede hacer que veas borroso de lejos.", "fuentes": ["rx.od", "rx.oi"]}]}
}
```
- `esperado`: `aceptar` o `rechazar`.
- `regla`: `null` si `esperado=aceptar`; si no, **exactamente una** de las reglas de abajo, y el caso debe violar **solo esa** regla.
- `rx`: `null` si el perfil no está completo; componentes posibles `miopía`, `hipermetropía`, `astigmatismo`.
- `sintomas_referidos`: ids canónicos: `vision_borrosa_lejos`, `vision_borrosa_cerca`, `vision_borrosa`, `fatiga_visual`, `cefalea`, `ardor`, `lagrimeo`, `comezon`.
- `pantallas`: `null`, `lt2`, `btw2_6`, `gt6`. `lente`: `null`, `monofocal`, `bifocal_blended`, `flat_top`, `progresivo`.
- Ids de fuentes válidos en `candidato`: `clinico`, `rx.od`, `rx.oi`, `motivo`, `pantallas`, `lente`, `cor.<nombre>` y `acciones` solo si existen en el caso.

## Reglas (vocabulario estable que devuelve el validador)
| regla | Rechaza |
|---|---|
| `json` | estructura inválida, claves extra, `frases` vacía o fuera de 1–4, fuentes inexistentes o duplicadas, texto vacío |
| `longitud` | más de 120 palabras en total |
| `tuteo` | tú, te, ti, tu, tus, contigo o verbos en segunda persona informal |
| `cifras` | dígitos o cantidades de medida en palabras (dioptrías, grados, agudezas, porcentajes, «menos dos») |
| `meta` | «IA», «inteligencia artificial», «impresión clínica», «correlación», Markdown, enlaces, marcadores de control |
| `normalidad` | sano, normal, perfecto, todo bien, no necesita, no requiere y equivalentes |
| `promesa` | cura, curar, garantiza, garantizado, resolverá, eliminará, «verá perfecto» y equivalentes |
| `magnitud` | leve, baja, alta, fuerte, grave, severa, moderada (como calificación) |
| `accion_propia` | especialidad, plazo, urgencia o derivación escritos por Qwen (eso solo lo pone CPU en `acciones_obligatorias`) |
| `enfermedad` | nombre de enfermedad fuera de «para descartar X» o con X ausente del clínico |
| `sintoma_no_referido` | afirma que el paciente tiene o refirió un síntoma que no está en `sintomas_referidos` |
| `componente` | componente refractivo que no está en el perfil, lado equivocado, o graduación cuando `rx` es `null` |
| `modalidad` | efecto funcional no referido sin «puede» o «podría» |
| `consejo` | recomendación práctica (pausas, gotas, hábitos, ejercicios) sin respaldo en correlaciones ni en el clínico |
| `lente` | describe un lente distinto del prescrito, o atribuye al **tipo** `monofocal` (frase que nombra «monofocal») un uso de lejos o de cerca. Decir que los lentes corrigen la graduación y ayudan a ver de lejos o de cerca **no** es esta regla (lo cubren `componente` y `modalidad`). Revisado por Claude el 2026-11-12. |

## Cobertura mínima
≥ 200 casos: al menos 10 por regla de rechazo (variando mayúsculas, acentos, plurales, sinónimos y posición en la frase) y al menos 40 `aceptables` que **deben** pasar (frases correctas, con «puede», síntomas referidos bien atribuidos, descartes permitidos, lente bien descrito, consejos con respaldo, sin `rx` hablando solo de hallazgos).
