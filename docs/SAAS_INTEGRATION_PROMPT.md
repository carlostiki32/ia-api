# Estado de integracion consumida por el SaaS

## Resumen

Este documento describe como el SaaS de Optica consume `ia-api` hoy.
La integracion de codigo en el SaaS ya esta implementada. Para operar de punta a punta, `ia-api` debe estar desplegada, configurada y accesible desde el SaaS.

## Punto de entrada desde el SaaS

Ruta interna del SaaS que dispara la llamada a esta API:

- Path real: `POST /recetas/api/ia/impresion-clinica`
- Route name: `recetas.api.ia.impresion-clinica`

Esa ruta interna del SaaS no reemplaza este contrato. Solo actua como proxy autenticado entre la UI del formulario y `ia-api`.

## Endpoint de ia-api

- Path: `POST /inferencia/impresion-clinica`
- Auth: `Authorization: Bearer <API_KEY>`

## Flujo real

1. El optometrista llena el formulario de receta en el SaaS.
2. La UI del SaaS hace `fetch()` a `route('recetas.api.ia.impresion-clinica')`.
3. El SaaS construye el payload en `IaApiService::buildPayload()`.
4. El SaaS envia `POST` a `ia-api` con Bearer token.
5. `ia-api` valida, corre inferencia contra Ollama y responde JSON.
6. El SaaS inserta `impresion_clinica` en el textarea editable.

## Variables del SaaS que deben apuntar a esta API

```env
IA_API_URL=http://localhost:8888
IA_API_KEY=cambia-este-token-por-uno-seguro
IA_API_TIMEOUT=300
IA_API_ENABLED=true
```

Reglas:

- `IA_API_KEY` debe ser exactamente igual a `API_KEY` de esta API.
- `IA_API_TIMEOUT` debe ser mayor que `QUEUE_WAIT_TIMEOUT + OLLAMA_TIMEOUT`.
- Con los defaults actuales (`120 + 120`), usar `300` es lo recomendado.

## Payload que envia el SaaS

El SaaS envia estas secciones:

- `receta_id`
- `paciente.edad`, `paciente.ocupacion`, `paciente.motivo_consulta`
- `refraccion.od` y `refraccion.oi`
- `akr.od` y `akr.oi`
- `clinica.*`
- `tipo_lente`

No envia:

- PII del paciente: `nombre`, `telefono`, `fecha_nacimiento`
- campos comerciales: material, tratamientos, armazon, precio, anticipo
- parametros de montaje: `dnp`, `altura_montaje`, `akr_pd`
- campos de laboratorio
- `impresion_clinica_plan`

## Respuesta esperada por el SaaS

Exito:

```json
{ "status": "ok", "impresion_clinica": "texto generado" }
```

Errores:

- Para errores operativos y de negocio, FastAPI suele responder `{"detail":"mensaje"}`.
- Para errores de validacion de request, FastAPI puede responder `{"detail":[...]}` con una lista estructurada.

Nota sobre el consumidor actual:

- El SaaS muestra bien `detail` cuando es string.
- Cuando `detail` es estructurado, hoy puede mostrarse como JSON serializado en el frontend.

## Requisitos operativos de esta API

Para que el SaaS pueda usar esta API, esta API debe tener:

- archivo `.env` creado desde `.env.example`
- `API_KEY` configurada
- dependencias Python instaladas (`python -m pip install -r requirements.txt`)
- Ollama corriendo en `OLLAMA_URL`
- modelo configurado disponible en Ollama
- servidor `uvicorn` escuchando en `PORT` (`8888` por default)
- `GET /health` respondiendo `200`

## Verificacion recomendada antes de probar desde el SaaS

1. `GET /health` responde correctamente.
2. `API_KEY` de esta API coincide con `IA_API_KEY` del SaaS.
3. El host del SaaS puede llegar a `IA_API_URL`.
4. El modelo configurado existe en Ollama.
5. El timeout del SaaS es suficiente.

## Estado actual

- Contrato principal SaaS -> `ia-api`: alineado.
- Integracion de codigo en el SaaS: lista.
- Validacion end-to-end real: depende del despliegue y arranque operativo de esta API.
