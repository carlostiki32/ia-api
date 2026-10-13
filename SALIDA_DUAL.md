# Salida clínica y explicación para paciente

Implementación local: 12 de octubre de 2026. No se desplegó ni se ejecutó el
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
  "explicacion_paciente": "Tu graduación incluye corrección para...",
  "explicacion_paciente_estado": "generada",
  "correlaciones_activadas": [],
  "salida_version": "clinica-paciente-v1",
  "cached": false,
  "generacion": {
    "origen_clinico": "llm",
    "origen_explicacion": "llm",
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
| `generada` | String válido del modelo. | `llm` |
| `plantilla` | Catálogo determinista válido por rechazo solo educativo. | `plantilla` |
| `sin_componentes_refractivos` | Nulo: ESF/CIL completos, ambos ojos cero y sin ADD positiva. | `ninguno` |
| `datos_incompletos` | Nulo: falta ESF/CIL de algún ojo. | `ninguno` |
| `rechazada` | Nulo: candidato y respaldo educativo inválidos. | `ninguno` |

El clínico válido se conserva aunque falle el campo educativo, incluso si ese
campo llega con un tipo incorrecto. Los estados sin contenido no se sustituyen
por texto de normalidad ni por medidas AKR. `rechazada` recuperable no se cachea.

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
| ESF/CIL cero | Omitir componentes; no afirmar salud. |
| ADD positiva | Apoyo para enfocar cerca; nunca presbicia automática. |

El esquema manda un perfil cerrado con ojos/nombres y una apertura obligatoria.
Se agrupan tipos iguales en los dos ojos y se identifica derecho/izquierdo cuando
difieren. Qwen selecciona las definiciones sencillas y cierres del catálogo
permitido para ese perfil, sin síntomas individuales ni causas anatómicas.
El prompt, la validación y el respaldo CPU usan el mismo catálogo; se conservan
las variantes sencillas ya aprobadas en las simulaciones del flujo dual.

Las guardas exigen 60–110 palabras, tú, apertura que conserve nombres/ojos,
una definición permitida por término, apoyo cercano solo cuando corresponda y
cierres permitidos sin repeticiones. Cada frase debe pertenecer al catálogo:
una definición invertida, una promesa de pérdida permanente de visión o un consejo
ajeno al perfil activa el respaldo CPU sin otra inferencia. Esta comparación
controla la salida del catálogo, no demuestra fidelidad semántica universal del
modelo; el optometrista sigue leyendo y editando en Óptica. La edición
humana no tiene que conservar el objetivo de palabras, pero sí su límite de
almacenamiento de 2000 caracteres.

## Una generación, guardas separadas y fallos

En un miss normal, `run_inference` hace **una** llamada Ollama `/api/chat` con
`format` JSON Schema, `stream:false` y el `think:false` existente. El contenido
íntegro de `message.content` se analiza como JSON antes de limpiar los strings.
La impresión pasa por sus guardas habituales, sustentadas solo en el prompt
clínico, urgencias y seguimiento. La explicación pasa por sus guardas propias.
No se guarda `message.thinking` ni se transforma razonamiento en salida.

El sobre malformado comparte como máximo un reintento de orquestación con el
truncamiento por `done_reason=length`. El proveedor conserva sus intentos acotados
ante transporte/respuesta vacía/500/503. Un rechazo únicamente educativo utiliza
CPU y no hace otra llamada al modelo. JSON ilegible, clínico vacío o truncamiento
persistente producen HTTP 502 sin caché, conservando las demás excepciones 413,
503 y 504 del endpoint.

La excepción urgente existente conserva HTTP 200 con `origen:determinista` y
clínico determinista. En dual añade `salida_version`, `cached:false`, explicación
nula y estado `rechazada`; **no incluye `generacion`**. Por tanto no acredita una
inferencia completa ni habilita los bloques PDF condicionados a origen LLM.
Nunca se cachea este respaldo clínico.

## Caché y configuración local

La RAM conserva los dos textos originales, estado y origen educativo. La clave
excluye `receta_id`, distingue modos y añade versiones de prompt/perfil/pipeline,
modelo y sampling/presupuesto/contexto/límite clínico. La política editorial
`educacion-catalogo-v2` invalida las entradas duales del catálogo anterior sin
cambiar el contrato HTTP ni la clave del modo legacy. Las representaciones
equivalentes normalizadas pueden compartir clave. Se consulta otra vez después
de adquirir turno, evitando dos generaciones secuenciales para solicitudes iguales
que llegaron juntas. TTL 24 horas, LRU 500, concurrencia 1; conservar un worker.

`OLLAMA_NUM_PREDICT=1024` sigue gobernando modo clínico. El nuevo
`OLLAMA_DUAL_NUM_PREDICT=1024` gobierna modo dual, con aumento acotado si se corta
por longitud. Se conserva `OLLAMA_NUM_CTX=8192`, Qwen actual y sampling. No se
ajusta hardware ni se abre conexión nueva al servidor apagado. La aptitud del
presupuesto/JSON Schema en la versión instalada de Ollama no se afirma como
medida: la simulación prueba el comportamiento de la aplicación sin modelo.

## Pruebas y evidencia

`tests/test_patient_profile.py` cubre signos/potencias, transposición, mixtos,
ceros/nulos, ADD sin presbicia, ojos diferentes, fuentes excluidas y las 144
combinaciones de tipos y apoyo cercano del catálogo. `tests/test_dual_output.py`
cubre esquema Ollama, una llamada normal, recuperación independiente, presupuesto
compartido, errores y respuesta urgente, procedencia, clave versionada y deduplicación
de peticiones simultáneas. Las pruebas clínicas históricas conservan el modo legacy.

La evidencia sintética del SaaS está en
`C:/dev/optica/docs/validacion-explicacion-paciente/simulaciones-api.json`:
caso miopía/astigmatismo bilateral (78 palabras, `generada`) y ojos distintos con
ADD (85 palabras, `plantilla` tras candidato malicioso). Cada caso registra una
llamada simulada inicial, cero adicionales por respaldo y cero al repetir con
caché vigente; captura íntegros ambos prompts y las respuestas reales del endpoint.
Estos son fixtures controlados, no resultados obtenidos de Qwen ni benchmarks GPU.
