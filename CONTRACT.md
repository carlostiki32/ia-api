# Contrato API ia-api - Impresion Clinica Optometrica

## Alcance

Este documento describe el contrato externo entre el SaaS y `ia-api`.
La ruta interna del SaaS que dispara esta llamada es `POST /recetas/api/ia/impresion-clinica`, pero el contrato documentado aqui aplica al endpoint real de `ia-api`.

## Autenticacion

Todas las peticiones requieren el header:

```http
Authorization: Bearer <API_KEY>
```

El token debe coincidir exactamente entre:

- `IA_API_KEY` en el SaaS
- `API_KEY` en `ia-api`

## Endpoint

```http
POST /inferencia/impresion-clinica
```

## Request body

```json
{
  "receta_id": "string",
  "paciente": {
    "edad": "integer | null",
    "ocupacion": "string | null",
    "motivo_consulta": "string | null"
  },
  "refraccion": {
    "od": {
      "esfera": "number | null",
      "cilindro": "number | null",
      "eje": "integer | null",
      "add": "number | null",
      "av_sc": "string | null",
      "av_cc": "string | null"
    },
    "oi": {
      "esfera": "number | null",
      "cilindro": "number | null",
      "eje": "integer | null",
      "add": "number | null",
      "av_sc": "string | null",
      "av_cc": "string | null"
    }
  },
  "akr": {
    "od": { "esfera": "number | null", "cilindro": "number | null", "eje": "integer | null" },
    "oi": { "esfera": "number | null", "cilindro": "number | null", "eje": "integer | null" }
  },
  "clinica": {
    "uso_pantallas": "lt2 | btw2_6 | gt6 | null",
    "anexos_oculares": "string | null",
    "reflejos_pupilares": "string | null",
    "motilidad_ocular": "string | null",
    "confrontacion_campos_visuales": "string | null",
    "fondo_de_ojo": "string | null",
    "grid_de_amsler": "string | null",
    "ojo_seco_but_seg": "integer(1-15) | null",
    "cover_test": "string | null",
    "ppc_cm": "integer(1-15) | null",
    "recomendacion_seguimiento": "string | null"
  },
  "tipo_lente": "string | null"
}
```

## Reglas del request

- `receta_id` es obligatorio.
- Debe existir al menos un dato de `refraccion` o `clinica` con valor no nulo.
- `uso_pantallas` solo acepta `lt2`, `btw2_6` o `gt6`.
- `ojo_seco_but_seg` debe estar entre `1` y `15`.
- `ppc_cm` debe estar entre `1` y `15`.
- Valores `0` y `0.0` siguen contando como datos clinicos validos.

## Datos que el SaaS no envia

El contrato excluye:

- PII del paciente: `nombre`, `telefono`, `fecha_nacimiento`
- datos comerciales: material, tratamientos, armazon, precio, anticipo
- parametros de montaje: `dnp`, `altura_montaje`, `akr_pd`
- campos de laboratorio
- `impresion_clinica_plan`

## Response body

### 200 OK

```json
{ "status": "ok", "impresion_clinica": "texto generado" }
```

### Errores comunes

| Codigo | Significado |
|--------|-------------|
| 401 | Token faltante o invalido |
| 422 | Payload sin datos clinicos o request invalido |
| 503 | Servidor ocupado; demasiadas peticiones en espera |
| 504 | Ollama no respondio a tiempo |
| 502 | Error de comunicacion con Ollama |
| 500 | Error interno |

### Formato de errores

Errores operativos y de negocio:

```json
{ "detail": "mensaje de error" }
```

Errores de validacion de esquema en FastAPI/Pydantic:

```json
{
  "detail": [
    {
      "loc": ["body", "clinica", "uso_pantallas"],
      "msg": "Input should be lt2, btw2_6 or gt6",
      "type": "literal_error"
    }
  ]
}
```

## Timeouts y concurrencia

- `MAX_CONCURRENT=1` procesa una inferencia a la vez para proteger la GPU.
- Si otra inferencia esta corriendo, la nueva peticion espera hasta `QUEUE_WAIT_TIMEOUT`.
- Si se rebasa esa espera, la API responde `503`.
- El SaaS debe usar un timeout mayor que `QUEUE_WAIT_TIMEOUT + OLLAMA_TIMEOUT`.
- Con los defaults actuales (`120s + 120s`), se recomienda `IA_API_TIMEOUT=300`.

## Health check

```http
GET /health
```

Respuesta esperada:

```json
{ "status": "ok", "model": "llama3.1:8b", "ollama": "ok|error" }
```

## Requisitos operativos minimos

Para que este contrato funcione en entorno real, `ia-api` debe tener:

- `.env` creado a partir de `.env.example`
- `API_KEY` configurada
- dependencias instaladas desde `requirements.txt`
- Ollama arriba y con el modelo configurado descargado
- servidor `uvicorn` escuchando en el puerto configurado
- conectividad desde el SaaS hacia `IA_API_URL`
