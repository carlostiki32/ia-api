# Salida clínica y explicación para paciente

Implementación local actualizada: 6 de noviembre de 2026 (F0, C2–C4 y C6). No se desplegó ni se ejecutó el
modelo real: el servidor de destino está apagado y las simulaciones sustituyen
únicamente el proveedor Ollama. El endpoint, prompts, validaciones y caché
se ejecutan en el código real.

## Request y compatibilidad

Se conserva `POST /inferencia/impresion-clinica`, Bearer y los campos del
[diccionario normativo](DICCIONARIO_DATOS_RECETA.md). `salida_version` es un
campo tipado, no un extra ignorado:

| Valor | Comportamiento |
|---|---|
| Omitido o `clinica-v1` | Párrafo clínico y respuesta histórica; `cached:true` solo en hit. |
| `clinica-paciente-v1` | Dos textos con estados, `cached` booleano y procedencia. |
| Nulo o cualquier otro valor | HTTP 422 de validación. |

No se agrega confirmación ni indicador de guardado al payload. El SaaS solicita
la API solo mediante Generar con IA. Guardar, revisar e imprimir no son operaciones
de este endpoint y nunca deben disparar una nueva inferencia.

```json
{
  "receta_id": "ejemplo-sintetico",
  "salida_version": "clinica-paciente-v1",
  "refraccion": {
    "od": {"esfera": -2, "cilindro": -0.75},
    "oi": {"esfera": -1.75, "cilindro": -0.75}
  }
}
```

## Respuesta normal

```json
{
  "status": "ok",
  "impresion_clinica": "Párrafo clínico validado...",
  "explicacion_paciente": "Su graduación incluye corrección para...",
  "explicacion_paciente_estado": "plantilla",
  "correlaciones_activadas": [],
  "salida_version": "clinica-paciente-v1",
  "cached": false,
  "generacion": {
    "origen_clinico": "llm",
    "origen_explicacion": "plantilla",
    "modelo": "qwen3.5:9b",
    "pipeline_version": "clinica-paciente-v1",
    "base_hash_api": "sha256-de-64-caracteres-de-la-clave-normalizada"
  }
}
```

`base_hash_api` incluye la base normalizada, versión, modelo y configuración de
generación pertinente. Sirve para trazabilidad/caché del motor; no equivale a
la huella del payload crudo que guarda Laravel.

| Estado educativo | Texto | Origen educativo |
|---|---|---|
| `plantilla` | Catálogo determinista válido, generado siempre en CPU. | `plantilla` |
| `sin_componentes_refractivos` | Nulo: ESF/CIL completos, ambos ojos cero y sin ADD positiva. | `ninguno` |
| `datos_incompletos` | Nulo: falta ESF/CIL de algún ojo. | `ninguno` |
| `rechazada` | Nulo: la plantilla no pasó su validación (fallo interno inesperado). | `ninguno` |

El contrato HTTP conserva sus campos y valores posibles, incluidos `generada` y
`llm` como valores históricos; el flujo vigente no los emite para la explicación.
El clínico válido se conserva aunque falle la plantilla educativa. Los estados
sin contenido no se sustituyen por texto de normalidad ni por medidas AKR.
`rechazada` no se cachea. El respaldo clínico urgente conserva su contrato separado.

## Perfil educativo y redacción

`app/patient_profile.py` solo recibe la refracción final de lejos normalizada.
No usa edad, AKR, motivo, hallazgos, diseño de lente ni el texto clínico.
ESF/CIL explícitos de **ambos ojos** son necesarios; cero difiere de ausencia.
No agrega una exigencia de eje para nombrar una corrección.

Se calculan `S` y `S+C`, conservando transposición y nulos de Pydantic:

| Potencias registradas | Nombres permitidos |
|---|---|
| CIL cero, ESF negativa/positiva | Miopía/hipermetropía. |
| CIL no cero, ambas potencias negativas/positivas | Miopía/hipermetropía y astigmatismo. |
| CIL no cero, una potencia cero o signos opuestos | Astigmatismo sin subtipo. |
| ESF y CIL explícitamente cero | Ojo plano: describir la receta de lejos con 0.00; no afirmar salud. |
| ADD positiva | Apoyo para enfocar cerca; nunca presbicia automática. |

El perfil cerrado con ojos/nombres se usa exclusivamente en CPU mediante
`build_patient_template(profile)`. Nunca se envía al modelo. El paciente se trata
siempre de **usted**. Se agrupan tipos iguales y se identifica derecho/izquierdo
cuando difieren, con una única oración de apertura: «Su graduación incluye
corrección para astigmatismo en el ojo derecho y para miopía en el ojo izquierdo».

El orden validado es: apertura → frase de ojo plano → definiciones (miopía,
hipermetropía, astigmatismo) → apoyo cercano → cierres sin repeticiones. Si solo
hay ADD, la apertura ya identifica el apoyo y su lateralidad; tras la frase de
plano se explica ese apoyo. Cada plantilla aplicable tiene 60–110 palabras y cada
frase pertenece al catálogo. La edición humana conserva el límite de
almacenamiento de 2000 caracteres.

Ojo plano exige ESF **y** CIL explícitamente 0.00; ESF cero con CIL distinto de
cero sí lleva corrección. Tras la apertura se añade, según corresponda:

- «En el ojo izquierdo, su receta de lejos marca 0.00: ese lado no lleva corrección para ver de lejos.» (o derecho).
- «En los dos ojos, su receta de lejos marca 0.00: no lleva corrección para ver de lejos.» (perfil solo con ADD).

El apoyo cercano sigue indicando en qué ojo(s) hay ADD positiva. Ningún perfil
permite «sano», «sana», «normal», «no necesita», «no requiere», «presbicia»,
«perfecto» ni «perfecta»; tampoco tuteo, síntomas individuales o causas anatómicas.

## Una generación, guardas separadas y fallos

En un miss normal, `run_inference` hace **una** llamada clínica Ollama `/api/chat`,
idéntica a `clinica-v1`: mismo system prompt, mismo user prompt, sin `format`
JSON Schema, con `stream:false`, `think:false` y presupuesto `OLLAMA_NUM_PREDICT`.
`message.content` contiene prosa clínica y pasa por el mismo postprocesado,
guardas, urgencias y seguimiento. La explicación se construye solo con
`build_patient_template(profile)`, fuera del prompt y de la respuesta del LLM.
No se guarda `message.thinking` ni se transforma razonamiento en salida.

Se conserva un reintento acotado por `done_reason=length`, igual al modo clínico,
y los intentos del proveedor ante transporte/respuesta vacía/500/503. No existen
parseo ni reintento de sobre JSON. Una plantilla educativa inválida no hace otra
llamada. Clínico vacío o truncamiento persistente producen HTTP 502 sin caché,
conservando las demás excepciones 413, 503 y 504 del endpoint.

La excepción urgente existente conserva HTTP 200 con `origen:determinista` y
clínico determinista. En dual añade `salida_version`, `cached:false`, explicación
nula y estado `rechazada`; **no incluye `generacion`**. Por tanto no acredita una
inferencia completa ni habilita los bloques PDF condicionados a origen LLM.
Nunca se cachea este respaldo clínico.

## Caché y configuración local

La RAM conserva los dos textos originales, estado y origen educativo. La clave
excluye `receta_id`, distingue modos y añade versiones de prompt/perfil/pipeline,
modelo y sampling/presupuesto/contexto/límite clínico. La política editorial
`educacion-plantilla-usted-v3` y el perfil `refraccion-final-lejos-v2` invalidan las entradas duales anteriores sin
cambiar el contrato HTTP ni la clave del modo legacy. Las representaciones
equivalentes normalizadas pueden compartir clave. Se consulta otra vez después
de adquirir turno, evitando dos generaciones secuenciales para solicitudes iguales
que llegaron juntas. TTL 24 horas, LRU 500, concurrencia 1; conservar un worker.

`OLLAMA_NUM_PREDICT=1024` gobierna ambos modos, con aumento acotado por
truncamiento. `OLLAMA_DUAL_NUM_PREDICT` sigue aceptado por compatibilidad con
`.env` existentes, pero ya no se usa, tampoco en caché. El default de
`OLLAMA_NUM_CTX` sigue siendo 8192. Si el valor efectivo es menor, el `lifespan`
registra «OLLAMA_NUM_CTX=%d < 8192: recetas con AKR y datos clínicos pueden devolver
413». El despliegue debe verificar el valor efectivo en el equipo con GPU; esta
implementación no modifica `.env` ni mide rendimiento del modelo.

## Pruebas y evidencia

`tests/test_patient_profile.py` cubre signos/potencias, transposición, mixtos,
ceros/nulos, ADD sin presbicia, ojos diferentes, fuentes excluidas y las 144
combinaciones de tipos y apoyo cercano del catálogo. `tests/test_dual_output.py`
cubre igualdad de prompts y cuerpo HTTP entre modos sin `format`, una llamada
normal, estados CPU, reintento clínico por longitud, errores y respuesta urgente,
procedencia, clave legacy fijada antes de F0, invalidación dual y deduplicación
de peticiones simultáneas. Las pruebas clínicas históricas conservan el modo legacy.

La evidencia **histórica anterior a F0** del SaaS está en
`C:/dev/optica/docs/validacion-explicacion-paciente/simulaciones-api.json`:
caso miopía/astigmatismo bilateral (78 palabras, `generada`) y ojos distintos con
ADD (85 palabras, `plantilla` tras candidato malicioso). Cada caso registra una
llamada simulada inicial, cero adicionales por respaldo y cero al repetir con
caché vigente; captura íntegros ambos prompts y las respuestas reales del endpoint.
Estos fixtures registran el flujo anterior por LLM y no describen el comportamiento
vigente. No son resultados obtenidos de Qwen ni benchmarks GPU. C1 (leyenda del PDF)
y la UI de Laravel quedan fuera del alcance de este repositorio; F0 ia-api no
certifica por sí solo el cierre completo de C1–C6.
