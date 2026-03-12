# Guia de instalacion y arranque - ia-api

## Objetivo

Esta guia deja `ia-api` lista para ser consumida por el SaaS.
La integracion del lado SaaS ya existe; lo pendiente para operar end-to-end es que esta API quede levantada y accesible.

## Requisitos minimos

- Python 3.11 o superior
- Ollama instalado y funcionando
- modelo disponible en Ollama (`llama3.1:8b` por default)
- acceso de red desde el SaaS hacia el host donde correra `ia-api`

GPU Nvidia es recomendable para tiempos de respuesta razonables, pero no cambia el contrato HTTP.

## Paso 1: Clonar el repo

```bash
git clone <url-del-repo> ia-api
cd ia-api
```

## Paso 2: Crear `.env`

```bash
cp .env.example .env
```

Editar `.env` y ajustar como minimo:

```env
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
OLLAMA_TIMEOUT=120.0
MAX_CONCURRENT=1
QUEUE_WAIT_TIMEOUT=120.0
HOST=0.0.0.0
PORT=8888
API_KEY=cambia-este-token-por-uno-seguro
```

Importante:

- `API_KEY` no debe quedarse con el valor placeholder.
- Ese mismo valor debe configurarse como `IA_API_KEY` en el SaaS.
- Si el SaaS usa esta configuracion default, `IA_API_TIMEOUT=300` sigue siendo la recomendacion correcta.

Para generar un token seguro:

```bash
openssl rand -hex 32
```

## Paso 3: Instalar dependencias Python

### Linux / macOS

```bash
python3 -m venv venv
source venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### Windows PowerShell

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Verificacion recomendada:

```bash
python -m pip show fastapi
python -m pip show uvicorn
python -m pip show httpx
```

Si `fastapi` no aparece, la API no va a arrancar.

## Paso 4: Verificar Ollama

```bash
ollama --version
ollama list
```

Levantar Ollama si hace falta:

```bash
ollama serve
```

Verificar salud:

```bash
curl http://localhost:11434/api/tags
```

Si el modelo configurado no existe, descargarlo:

```bash
ollama pull llama3.1:8b
```

## Paso 5: Arrancar ia-api

### Opcion A: Unix con `run.sh`

```bash
chmod +x run.sh
./run.sh
```

`run.sh` es una conveniencia para Unix. No aplica en Windows.

### Opcion B: arranque directo con Uvicorn

Linux / macOS:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8888 --reload
```

Windows PowerShell:

```powershell
python -m uvicorn app.main:app --host 0.0.0.0 --port 8888 --reload
```

## Paso 6: Verificar `health`

```bash
curl http://localhost:8888/health
```

Respuesta esperada:

```json
{ "status": "ok", "model": "llama3.1:8b", "ollama": "ok" }
```

Si esto no responde, el SaaS no podra usar la integracion aunque el codigo este correcto.

## Paso 7: Probar el endpoint manualmente

```bash
curl -X POST http://localhost:8888/inferencia/impresion-clinica \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer TU_API_KEY" \
  -d '{
    "receta_id": "test-001",
    "paciente": {
      "edad": 42,
      "ocupacion": "disenador grafico",
      "motivo_consulta": "cefalea frontal y vision borrosa de cerca"
    },
    "refraccion": {
      "od": { "esfera": -1.50, "cilindro": -0.75, "eje": 180, "av_sc": "20/200", "av_cc": "20/20" },
      "oi": { "esfera": -1.25, "cilindro": null, "eje": null, "av_sc": "20/100", "av_cc": "20/20" }
    },
    "akr": {
      "od": { "esfera": -1.75, "cilindro": -0.50, "eje": 175 },
      "oi": { "esfera": -1.50, "cilindro": -0.25, "eje": 10 }
    },
    "clinica": {
      "uso_pantallas": "gt6",
      "anexos_oculares": "sin alteraciones OU",
      "reflejos_pupilares": "normales OU",
      "motilidad_ocular": "completa sin restricciones",
      "confrontacion_campos_visuales": "sin defectos aparentes OU",
      "fondo_de_ojo": "papila de bordes nitidos, c/d 0.3, macula centrada",
      "grid_de_amsler": "sin distorsiones OU",
      "ojo_seco_but_seg": 6,
      "cover_test": "ortoforia",
      "ppc_cm": 8,
      "recomendacion_seguimiento": "control en 12 meses"
    },
    "tipo_lente": "progresivo"
  }'
```

Respuesta esperada:

```json
{ "status": "ok", "impresion_clinica": "texto generado" }
```

## Paso 8: Conectar el SaaS

Configurar en el `.env` del SaaS:

```env
IA_API_URL=http://localhost:8888
IA_API_KEY=<mismo API_KEY de ia-api>
IA_API_TIMEOUT=300
IA_API_ENABLED=true
```

Ruta interna real del SaaS usada por la UI:

- path: `POST /recetas/api/ia/impresion-clinica`
- route name: `recetas.api.ia.impresion-clinica`

Esa ruta llama a esta API en segundo plano.

## Errores frecuentes

| Sintoma | Causa probable | Accion recomendada |
|--------|----------------|--------------------|
| `No module named fastapi` | Dependencias Python no instaladas | `python -m pip install -r requirements.txt` |
| `GET /health` no responde | Uvicorn no esta levantado o puerto incorrecto | revisar comando de arranque y `PORT` |
| `401` | token faltante o distinto | igualar `API_KEY` e `IA_API_KEY` |
| `503` | cola saturada | esperar o ajustar `QUEUE_WAIT_TIMEOUT` |
| `504` | Ollama lento o caido | revisar `ollama serve` y disponibilidad del modelo |
| SaaS no conecta a `ia-api` | host o puerto inaccesible | revisar `IA_API_URL`, firewall y reachability |
| SaaS corta antes | timeout del cliente insuficiente | subir `IA_API_TIMEOUT` a `300` o mas |

## Checklist final

1. `.env` existe en `ia-api`.
2. `API_KEY` ya no usa el placeholder.
3. dependencias Python instaladas.
4. Ollama arriba.
5. modelo descargado.
6. `uvicorn` arriba en `:8888`.
7. `GET /health` responde `200`.
8. el SaaS apunta al host correcto.
9. `IA_API_KEY` coincide.

Con eso, la integracion de codigo ya existente en el SaaS puede operar de punta a punta.
