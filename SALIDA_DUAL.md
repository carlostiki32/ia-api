# Salida clínica y explicación para paciente

Actualización W1b, 8 de noviembre de 2026. Validación local con HTTP simulado;
calidad, latencias y cancelación efectiva de Ollama en GPU siguen pendientes.

## Request y compatibilidad

`POST /inferencia/impresion-clinica` y `/v1/inferencia/receta-clinica`, Bearer.
El [diccionario](DICCIONARIO_DATOS_RECETA.md) es el contrato de entrada.
`salida_version` omitido o `clinica-v1` conserva la llamada, depuración y respuesta
históricas. `clinica-paciente-v1` agrega la explicación; otro valor o nulo: 422.
Generar con IA solicita ambos textos; Guardar y aprobar pertenecen a Óptica.

## Cadena y punto de control

Clínico final no vacío → punto de control y caché clínica → redacción → validador
determinista → verificación → acciones CPU primero y prosa después, con `\n\n`.
La llamada clínica conserva prompts, opciones, reintentos y depuración; el perfil
educativo no entra en su prompt. La explicación usa el clínico final completo,
hechos permitidos, síntomas personales ciertos y correlaciones activas.

La redacción explica graduación y hallazgos en la vida diaria con frases cortas,
lenguaje cotidiano y traducciones del glosario. Efectos no referidos: «puede» o
«podría». No confirma diagnósticos ni añade exploraciones o normalidad.
El hecho `lente` solo autoriza su descripción CPU: monofocal no determina una
distancia de uso. Se admiten efectos de la graduación y ayuda de los lentes
cuando los hechos los sustentan; atribuir lejos, cerca o lectura al diseño
monofocal en la misma frase infringe la regla `lente`.
Salida JSON: una a cuatro frases y hasta 120 palabras; 384 tokens de salida,
temperatura 0.2 y semilla 42. Verificación JSON: solo `{"valido":true}` aprueba;
32 tokens, temperatura 0 y semilla 42. Una tentativa por etapa, `think=false`.
El proveedor determina `num_ctx=min(OLLAMA_NUM_CTX,LIMITE_CONTEXTO_TOKENS,8192)`.

Sin contador exacto, ambas llamadas usan siempre política de presupuesto estricta. La llamada
clínica conserva `PRESUPUESTO_RECETA_SIN_EXACTO`: `estricto` usa bytes UTF-8 como
cota demostrable (una receta típica puede dar 413); `conservador` usa heurística,
con advertencia y sin garantía exacta. Un caso mínimo puede caber incluso en
estricto. Con contador exacto verificado se usa BPE en ambos modos.

Techos de entrada: 7000/7400; entrada más salida: 7384/7432, por debajo de 7782
con contexto efectivo 8192. Conteo oficial del system: redacción 1012 tokens
(incluye objetivo y glosario), verificación 174. El glosario aislado cuenta 419.
El [material generado para revisión](auditoria/2026-11-08-explicacion-paciente/02-catalogo-y-prompts-para-revision.md)
contiene los textos literales y las versiones; se regenera con
`python scripts/catalogo_paciente.py --salida RUTA.md --tokenizer RUTA_TOKENIZER_JSON`.
Cada llamada cuenta la entrada completa con roles y envoltura; el esquema no se concatena al prompt. No existe
un máximo finito de longitud del clínico final: un contexto excesivo usa respaldo.

## Respuesta

```json
{
  "status": "ok",
  "impresion_clinica": "Texto clínico final...",
  "explicacion_paciente": "Acciones obligatorias y explicación...",
  "explicacion_paciente_estado": "generada",
  "correlaciones_activadas": [],
  "salida_version": "clinica-paciente-v1",
  "cached": false,
  "generacion": {
    "origen_clinico": "llm",
    "origen_explicacion": "llm",
    "modelo": "qwen3.5:9b",
    "pipeline_version": "clinica-paciente-v1",
    "paciente_version": "paciente-v1",
    "motivo_explicacion": null,
    "acciones_sin_mapear": 0,
    "cache": {"clinico": false, "paciente": false},
    "base_hash_api": "sha256-de-la-base-normalizada"
  }
}
```

`base_hash_api` identifica la base de la petición dual; no es la huella del
payload crudo de Laravel ni la clave interna del paciente.

| Estado/origen | Contenido |
|---|---|
| `generada` / `llm` | Prosa validada y verificada, con acciones primero. |
| `plantilla` / `plantilla` | Acciones y plantilla CPU, o acciones solas. |
| `datos_incompletos` / `ninguno` | Nulo: sin explicación validada, perfil incompleto y sin acciones. |
| `sin_componentes_refractivos` / `ninguno` | Nulo: sin explicación validada, perfil sin componentes y sin acciones. |
| `rechazada` / `ninguno` | Nulo ante fallo interno o imposibilidad de ensamblar dentro del límite. |

Sin ESF/CIL completos se pueden explicar hallazgos documentados y devolver
`generada/llm`. Si falla, las acciones aún se entregan; sin ellas se conserva
el estado del perfil. AKR nunca completa el perfil educativo.

`motivo_explicacion`: nulo al generar con éxito o con el interruptor apagado
(salvo fallo de ensamblado, que conserva `error`);
ante respaldo por fallo: `validacion`, `verificacion`, `abstencion`, `timeout`,
`presupuesto`, `ocupado` o `error`. La explicación ensamblada admite hasta 2000
puntos de código. Si no cabe, se descarta toda la prosa, nunca se corta una acción.
Si las acciones solas exceden 2000: nulo, `rechazada`, motivo `error`, conservando
el clínico. Esta decisión fue aceptada en la auditoría W1a.
La excepción heredada de la plantilla «marca 0.00… no lleva corrección para ver
de lejos» sigue limitada al respaldo; las guardas de Qwen no se aplican a esa plantilla.

## Plazos, carga e interruptor

En dual el plazo empieza en el middleware al llegar, antes de validación y cola:
`PLAZO_GLOBAL_RECETA_S=85`, acotado también por el timeout exterior existente.
Después del punto de control cualquier error o vencimiento responde 200 con
clínico y respaldo. Antes se conservan errores clínicos 413/502/504; cola rechazada:
503. El respaldo clínico urgente conserva `origen=determinista`, sin metadata LLM.
`clinica-v1` mantiene su timeout histórico y su contrato.

`PACIENTE_TIMEOUT_REDACCION_S=15`, `PACIENTE_TIMEOUT_VERIFICACION_S=5`: la cadena
paciente tiene la suma como techo, dentro del global. Ventanas mínimas:
`PACIENTE_MINIMO_REDACCION_S=1`, `PACIENTE_MINIMO_VERIFICACION_S=0.5`, reserva
CPU 0.1 s. Son valores iniciales, sin benchmark GPU. Todos los plazos configurables
exigen valores positivos. Cada etapa usa el mínimo entre techo y plazo restante.
`PACIENTE_OMITIR_SI_ESPERA=true` cede antes de cada etapa si espera otra interactiva.
`PACIENTE_LLM_HABILITADO=false` evita ambas llamadas y entrega acciones + plantilla,
con motivo nulo salvo fallo de ensamblado; también evita servir prosa LLM del
paciente ya cacheada.
Cambiar configuración requiere recargar el proceso para aplicar los settings.

## Caché, registro y métricas

La caché clínica usa la clave histórica `clinica-v1` en ambas presentaciones.
Se publica al alcanzar el punto de control; un fallo posterior no exige repetirla.
La caché paciente LRU/TTL solo guarda `generada`, con SHA-256 de JSON canónico
(`sort_keys`, Unicode sin escapes y separadores compactos): clínico final,
contexto, modelo, opciones efectivas y versiones de perfil, servicio, contexto,
prompt, esquema, glosario, validador, verificador, acciones y respaldo.
Se conservan los límites de caché configurados; no se cachean respaldos.

Clínico cacheado y paciente ausente: se publica el clínico, se pide turno
`interactiva` solo para el paciente y se consume el plazo restante. Si falla la
espera: 200 con clínico y motivo `ocupado` o `timeout`. `cached=true` exige ambos
aciertos; `generacion.cache` informa los parciales. El interruptor apagado no
cachea la plantilla. Las dos cachés se vuelven a consultar tras adquirir turno.

`GET /v1/tareas` describe `explicacion-paciente` como hija de `receta-clinica`,
interactiva y de montaje manual, con dos llamadas. `GET /v1/metricas` cuenta
solicitudes, motivos e intentos físicos por tarea y etapa, incluidos intentos
fallidos o cancelados; no guarda prompts, respuestas ni datos del paciente.
`scripts/probar_enrutado.py --modo simulado` comprueba tres llamadas en éxito
y un respaldo. Las pruebas HTTP usan además el tokenizador oficial offline.
