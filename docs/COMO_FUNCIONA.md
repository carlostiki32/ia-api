# Como funciona ia-api

## Estado actual

El acople de codigo entre el SaaS y `ia-api` ya esta implementado.
Lo que determina si la funcionalidad opera end-to-end no es el contrato de codigo, sino el estado operativo de `ia-api`:

- `.env` creado
- dependencias Python instaladas
- Ollama arriba
- modelo descargado
- `uvicorn` escuchando
- `GET /health` respondiendo

## Arquitectura real

```text
Navegador del optometrista
    -> POST /recetas/api/ia/impresion-clinica   (ruta interna del SaaS)
SaaS Laravel
    -> arma payload clinico
    -> Authorization: Bearer <IA_API_KEY>
    -> POST /inferencia/impresion-clinica       (endpoint de ia-api)
ia-api (FastAPI)
    -> valida auth
    -> valida esquema y presencia de datos clinicos
    -> espera semaforo si la GPU esta ocupada
    -> construye prompt
    -> llama a Ollama
    -> postprocesa texto
    -> responde JSON
Ollama
    -> genera la impresion clinica
```

## Flujo paso a paso

### 1. El optometrista llena el formulario

Llena datos del paciente, refraccion, AKR, hallazgos clinicos y tipo de lente.

### 2. Click en Generar con IA

La vista del SaaS hace `fetch()` a:

- path real: `POST /recetas/api/ia/impresion-clinica`
- route name: `recetas.api.ia.impresion-clinica`

### 3. El SaaS arma el payload

`IaApiService::buildPayload()` construye un JSON con:

- `receta_id`
- `paciente.edad`, `ocupacion`, `motivo_consulta`
- `refraccion.od` y `refraccion.oi`
- `akr.od` y `akr.oi`
- `clinica.*`
- `tipo_lente`

No envia:

- nombre, telefono o fecha de nacimiento
- material, tratamientos, armazon, precio o anticipo
- dnp, altura_montaje o akr_pd
- campos de laboratorio
- `impresion_clinica_plan`

### 4. El SaaS llama a ia-api

El SaaS usa `POST /inferencia/impresion-clinica` con Bearer token.

Reglas practicas:

- `IA_API_KEY` del SaaS debe ser igual a `API_KEY` de `ia-api`
- `IA_API_TIMEOUT` debe ser mayor que `QUEUE_WAIT_TIMEOUT + OLLAMA_TIMEOUT`
- con la configuracion actual, usar `300` sigue siendo lo recomendado

### 5. ia-api valida y procesa

1. Verifica `Authorization`
2. Valida el request con Pydantic
3. Verifica que exista al menos un dato clinico o de refraccion
4. Espera el semaforo si ya hay otra inferencia en curso
5. Construye el prompt con `prompt_builder.py`
6. Llama a Ollama desde `inference.py`
7. Limpia el texto final

### 6. Respuesta al SaaS

Exito:

```json
{ "status": "ok", "impresion_clinica": "texto generado" }
```

Errores:

- `401` por auth faltante o invalida
- `422` por request sin datos clinicos o por error de esquema
- `503` por cola saturada
- `504` por timeout de Ollama
- `500` o `502` por error interno o de comunicacion

Importante:

- Si FastAPI rechaza el request por validacion de esquema, `detail` puede venir como arreglo estructurado.
- El consumidor actual del SaaS maneja bien `detail` string.
- Los `detail` estructurados hoy pueden verse como JSON serializado en el frontend del SaaS.

## Manejo de concurrencia

`MAX_CONCURRENT=1` significa que solo se procesa una inferencia a la vez.
Eso evita saturar la GPU, pero introduce espera en cola.

Ejemplo:

```text
Optometrista A -> procesando
Optometrista B -> esperando semaforo
Optometrista A -> termina
Optometrista B -> empieza a procesar
```

Si la espera excede `QUEUE_WAIT_TIMEOUT`, la API responde `503`.

## Prompt y salida

La API construye:

- `SYSTEM_PROMPT`: reglas fijas de estilo y seguridad
- `user prompt`: datos clinicos formateados desde el payload

El texto final se postprocesa para:

- remover bullets o listas numeradas
- truncar a un maximo de 5 oraciones
- garantizar punto final

## Seguridad

- El SaaS autentica al usuario y verifica permiso `recetas.clinica`
- `ia-api` autentica con `Authorization: Bearer <API_KEY>`
- no hay acceso directo de `ia-api` a la base del SaaS
- no se envia PII innecesaria del paciente

## Checklist operativo

Antes de probar desde el formulario del SaaS:

1. `python -m pip install -r requirements.txt`
2. crear `.env` desde `.env.example`
3. poner `API_KEY` valido
4. verificar que Ollama este corriendo
5. verificar que el modelo configurado exista
6. levantar `uvicorn`
7. comprobar `GET /health`
8. comprobar que el SaaS apunta al host correcto en `IA_API_URL`

## Conclusion

La arquitectura y el contrato ya estan alineados.
Si la funcionalidad no responde en entorno real, primero revisar despliegue y salud operativa de `ia-api`; despues revisar payload, auth y timeouts.
