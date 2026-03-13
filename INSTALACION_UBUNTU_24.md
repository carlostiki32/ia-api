# Instalacion de `ia-api` en Ubuntu 24.04

Esta guia deja la API lista desde cero en un servidor Linux, con foco en Ubuntu 24.04 y aislando completamente Python para evitar choques con otras versiones o paquetes del sistema.

Tambien incluye un script de arranque Linux al final:

```bash
./start_linux.sh
```

Ese script:

- carga el `.env`
- valida `API_KEY`
- intenta arrancar Ollama si no esta respondiendo
- espera a que Ollama quede disponible
- descarga el modelo configurado si aun no existe
- activa el entorno virtual aislado
- inicia la API con Uvicorn

## 1. Requisitos del servidor

Minimos:

- Ubuntu 24.04
- acceso a terminal con `sudo`
- `git`
- `curl`
- Python 3.12 con `venv`
- Ollama instalado

Para instalar las dependencias base del sistema:

```bash
sudo apt update
sudo apt install -y git curl ca-certificates python3 python3-venv python3-pip
```

Verifica versiones:

```bash
python3 --version
git --version
curl --version
```

En Ubuntu 24.04 normalmente `python3` sera `3.12.x`.

## 2. Descargar el proyecto desde GitHub

Clona el repo y entra a la carpeta:

```bash
git clone <URL_DEL_REPO> ia-api
cd ia-api
```

Si descargaste un `.zip` desde GitHub:

```bash
unzip ia-api-main.zip
cd ia-api-main
```

## 3. Aislar Python para no chocar con otras versiones

No uses `sudo pip install`.
No instales dependencias globales del proyecto.
Todo debe quedar dentro del entorno virtual del repo.

Crea un entorno virtual local:

```bash
python3 -m venv .venv
```

Activalo:

```bash
source .venv/bin/activate
```

Cuando esta activo, tu shell normalmente muestra `(.venv)` al inicio.

Confirma que estas usando el Python aislado del proyecto:

```bash
which python
which pip
python --version
```

Las rutas deben apuntar a algo como:

```text
/ruta/al/proyecto/ia-api/.venv/bin/python
/ruta/al/proyecto/ia-api/.venv/bin/pip
```

Instala dependencias solo dentro del entorno virtual:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Si despues cierras la terminal, vuelve a activarlo con:

```bash
cd /ruta/al/proyecto/ia-api
source .venv/bin/activate
```

## 4. Crear el archivo `.env`

Copia el ejemplo:

```bash
cp .env.example .env
```

Edita `.env`:

```bash
nano .env
```

Configuracion minima recomendada:

```env
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=llama3.1:8b
OLLAMA_TIMEOUT=120.0
OLLAMA_TEMPERATURE=0.1
OLLAMA_NUM_PREDICT=768
MAX_CONCURRENT=1
QUEUE_WAIT_TIMEOUT=120.0
HOST=0.0.0.0
PORT=8888
API_KEY=cambia-este-token-por-uno-seguro
MAX_SENTENCES=10
HEALTH_CHECK_TIMEOUT=5.0
LOG_LEVEL=INFO
```

Muy importante:

- `MAX_CONCURRENT=1` es el valor correcto para este proyecto cuando corre en una GPU casera
- eso hace que solo se procese una inferencia a la vez
- las demas peticiones esperan en cola hasta que se libere la GPU
- `QUEUE_WAIT_TIMEOUT` define cuanto tiempo puede esperar una peticion en la cola antes de recibir `503`

Genera un token seguro para `API_KEY`:

```bash
openssl rand -hex 32
```

## 5. Instalar Ollama en Ubuntu 24

La instalacion recomendada por la documentacion oficial de Ollama para Linux, verificada el 13 de marzo de 2026, es:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Fuente oficial:

- https://docs.ollama.com/linux
- https://ollama.com/download/linux

Verifica que quedo instalado:

```bash
ollama -v
```

Si tu servidor tiene GPU Nvidia o AMD, la configuracion exacta de drivers depende de tu hardware. La parte de `ia-api` no cambia, pero Ollama necesita que la aceleracion del sistema ya este sana.

## 6. Arrancar Ollama manualmente por primera vez

Puedes probarlo manualmente antes de usar el script:

```bash
ollama serve
```

En otra terminal:

```bash
curl http://localhost:11434/api/tags
```

Si responde JSON, Ollama ya esta escuchando.

## 7. Descargar el modelo configurado

Si dejaste el default:

```bash
ollama pull llama3.1:8b
```

Si cambiaste `OLLAMA_MODEL` en `.env`, descarga exactamente ese modelo:

```bash
ollama pull <MODELO_CONFIGURADO>
```

## 8. Probar la API manualmente

Con el entorno virtual activo:

```bash
source .venv/bin/activate
python -m uvicorn app.main:app --host 0.0.0.0 --port 8888
```

En otra terminal:

```bash
curl http://localhost:8888/health
```

Respuesta esperada:

```json
{"status":"ok","model":"llama3.1:8b","ollama":"ok"}
```

## 9. Script Linux de arranque completo

En la raiz del proyecto se incluye:

```bash
start_linux.sh
```

Dale permisos de ejecucion:

```bash
chmod +x start_linux.sh
```

Ejecutalo desde la raiz del proyecto:

```bash
./start_linux.sh
```

Comportamiento esperado:

1. carga el `.env`
2. busca `.venv` y, si no existe, intenta usar `venv`
3. valida que `API_KEY` no siga como placeholder
4. revisa si Ollama ya responde en `OLLAMA_URL`
5. si no responde y la URL es local, lanza `ollama serve`
6. espera hasta que el API de Ollama quede arriba
7. verifica si el modelo existe
8. si falta, ejecuta `ollama pull`
9. activa el entorno virtual
10. ejecuta `python -m uvicorn app.main:app --host "$HOST" --port "$PORT"`

Para detener todo:

- presiona `Ctrl + C`
- si `start_linux.sh` fue quien lanzo `ollama serve`, tambien intentara detener ese proceso

## 10. Comandos de uso diario

Entrar al proyecto y activar el entorno:

```bash
cd /ruta/al/proyecto/ia-api
source .venv/bin/activate
```

Levantar todo con el script:

```bash
./start_linux.sh
```

Health check:

```bash
curl http://localhost:8888/health
```

Prueba del endpoint:

```bash
curl --location 'http://localhost:8888/inferencia/impresion-clinica' \
  --header 'Authorization: Bearer TU_API_KEY' \
  --header 'Content-Type: application/json' \
  --data '{
    "receta_id": "test-001",
    "paciente": {
      "edad": 42,
      "ocupacion": "disenador grafico",
      "motivo_consulta": "cefalea frontal y vision borrosa de cerca"
    },
    "refraccion": {
      "od": {
        "esfera": -1.50,
        "cilindro": -0.75,
        "eje": 180,
        "av_sc": "20/200",
        "av_cc": "20/20"
      },
      "oi": {
        "esfera": -1.25,
        "cilindro": null,
        "eje": null,
        "av_sc": "20/100",
        "av_cc": "20/20"
      }
    },
    "akr": {
      "od": {
        "esfera": -1.75,
        "cilindro": -0.50,
        "eje": 175
      },
      "oi": {
        "esfera": -1.50,
        "cilindro": -0.25,
        "eje": 10
      }
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

## 11. Problemas comunes

### `No module named fastapi`

El entorno virtual no esta activo o las dependencias no se instalaron dentro de `.venv`.

Solucion:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### `externally-managed-environment`

Estas intentando instalar paquetes en el Python del sistema.

Solucion:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### `401 Token invalido`

El `Authorization: Bearer ...` no coincide con `API_KEY` del `.env`.

### `503 Servidor ocupado`

La GPU esta ocupada y la peticion se quedo esperando en cola mas tiempo que `QUEUE_WAIT_TIMEOUT`.

### `504 Ollama no respondio a tiempo`

El modelo esta tardando demasiado.

Revisa:

- que Ollama este vivo
- que el modelo correcto este descargado
- que la GPU tenga memoria suficiente
- que `OLLAMA_TIMEOUT` sea razonable para tu equipo

### `start_linux.sh` dice que no encuentra el entorno virtual

Debes crear `.venv` primero:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 12. Recomendacion operativa para este proyecto

Si esta API va a vivir en una PC o servidor casero con GPU:

- deja `MAX_CONCURRENT=1`
- no subas concurrencia aunque tengas varios usuarios
- deja que las peticiones esperen en cola
- ajusta `QUEUE_WAIT_TIMEOUT` segun el tiempo real de tu modelo

Eso protege la VRAM y evita errores por OOM cuando dos inferencias se disparan al mismo tiempo.
