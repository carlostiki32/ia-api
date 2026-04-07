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
- GPU Nvidia con al menos 8 GB de VRAM (referencia: RTX 3070 Ti)

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

## 2. Instalar drivers Nvidia (referencia RTX 3070 Ti)

Si tu GPU es Nvidia, necesitas los drivers propietarios y el CUDA toolkit para que Ollama use la GPU.

```bash
sudo apt install -y nvidia-driver-550
sudo reboot
```

Despues de reiniciar, verifica que el driver detecte la GPU:

```bash
nvidia-smi
```

Deberias ver algo como:

```text
+-----------------------------------------------------------------------------------------+
| NVIDIA-SMI 550.x       Driver Version: 550.x       CUDA Version: 12.x                  |
|   GPU  Name       ...        Memory-Usage                                               |
|   0    NVIDIA GeForce RTX 3070 Ti   ...   8192MiB                                       |
+-----------------------------------------------------------------------------------------+
```

Si `nvidia-smi` no muestra tu GPU, revisa que el driver se instalo correctamente antes de continuar.

Ollama detecta automaticamente la GPU Nvidia si los drivers estan instalados. No necesitas instalar CUDA por separado para Ollama.

## 3. Descargar el proyecto desde GitHub

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

## 4. Aislar Python para no chocar con otras versiones

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

Las dependencias del proyecto son:

- `fastapi` - framework web
- `uvicorn[standard]` - servidor ASGI
- `httpx` - cliente HTTP async para comunicarse con Ollama
- `pydantic` / `pydantic-settings` - validacion y configuracion
- `python-dotenv` - carga de variables de entorno

Si despues cierras la terminal, vuelve a activarlo con:

```bash
cd /ruta/al/proyecto/ia-api
source .venv/bin/activate
```

## 5. Crear el archivo `.env`

Copia el ejemplo:

```bash
cp .env.example .env
```

Edita `.env`:

```bash
nano .env
```

Configuracion minima recomendada (RTX 3070 Ti):

```env
OLLAMA_URL=http://localhost:11434
OLLAMA_MODEL=qwen2.5:7b
OLLAMA_TIMEOUT=120.0
OLLAMA_TEMPERATURE=0.1
OLLAMA_NUM_PREDICT=400
MAX_CONCURRENT=1
QUEUE_WAIT_TIMEOUT=120.0
HOST=0.0.0.0
PORT=8888
API_KEY=cambia-este-token-por-uno-seguro
MAX_SENTENCES=10
HEALTH_CHECK_TIMEOUT=5.0
LOG_LEVEL=INFO
```

Sobre las variables:

- `OLLAMA_MODEL=qwen2.5:7b` es el modelo default del proyecto. Funciona bien en GPUs con 8 GB de VRAM como la RTX 3070 Ti
- `OLLAMA_NUM_PREDICT=400` limita la cantidad de tokens que genera el modelo por respuesta
- `OLLAMA_TEMPERATURE=0.1` mantiene las respuestas consistentes y poco creativas (ideal para uso clinico)
- `MAX_CONCURRENT=1` es el valor correcto para este proyecto cuando corre en una GPU casera. Solo se procesa una inferencia a la vez, las demas esperan en cola
- `QUEUE_WAIT_TIMEOUT` define cuanto tiempo puede esperar una peticion en la cola antes de recibir `503`
- `CACHE_TTL_SECONDS` y `CACHE_MAX_SIZE` no necesitan estar en `.env` a menos que quieras cambiar los defaults (86400 segundos y 500 entradas respectivamente). Si los omites, `config.py` usa esos defaults

Genera un token seguro para `API_KEY`:

```bash
openssl rand -hex 32
```

## 6. Instalar Ollama en Ubuntu 24

La instalacion recomendada por la documentacion oficial de Ollama para Linux:

```bash
curl -fsSL https://ollama.com/install.sh | sh
```

Verifica que quedo instalado:

```bash
ollama -v
```

Si tu servidor tiene GPU Nvidia con drivers correctamente instalados (paso 2), Ollama la detectara automaticamente.

## 7. Arrancar Ollama manualmente por primera vez

Puedes probarlo manualmente antes de usar el script:

```bash
ollama serve
```

En otra terminal:

```bash
curl http://localhost:11434/api/tags
```

Si responde JSON, Ollama ya esta escuchando.

## 8. Descargar el modelo configurado

Con el modelo default del proyecto:

```bash
ollama pull qwen2.5:7b
```

Si cambiaste `OLLAMA_MODEL` en `.env`, descarga exactamente ese modelo:

```bash
ollama pull <MODELO_CONFIGURADO>
```

## 9. Probar la API manualmente

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
{"status":"ok","model":"qwen2.5:7b","ollama":"ok"}
```

## 10. Script Linux de arranque completo

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

## 11. Comandos de uso diario

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

## 12. Problemas comunes

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
- que el modelo correcto este descargado (`ollama list` debe mostrar `qwen2.5:7b`)
- que la GPU tenga memoria suficiente (`nvidia-smi`)
- que `OLLAMA_TIMEOUT` sea razonable para tu equipo

### `start_linux.sh` dice que no encuentra el entorno virtual

Debes crear `.venv` primero:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

### Ollama no usa la GPU

Verifica que `nvidia-smi` detecta tu GPU. Si no la detecta:

```bash
sudo apt install -y nvidia-driver-550
sudo reboot
```

Despues de reiniciar, ejecuta `nvidia-smi` de nuevo. Si la GPU aparece, Ollama la usara automaticamente.

## 13. Recomendacion operativa para este proyecto

Si esta API va a vivir en una PC o servidor casero con GPU (como una RTX 3070 Ti con 8 GB de VRAM):

- deja `MAX_CONCURRENT=1`
- no subas concurrencia aunque tengas varios usuarios
- deja que las peticiones esperen en cola
- ajusta `QUEUE_WAIT_TIMEOUT` segun el tiempo real de tu modelo
- `qwen2.5:7b` cabe holgadamente en 8 GB de VRAM

Eso protege la VRAM y evita errores por OOM cuando dos inferencias se disparan al mismo tiempo.

## 14. Cache de respuestas

La API incluye un cache en memoria que evita enviar peticiones duplicadas a la GPU.

Como funciona:

- cada peticion genera un hash SHA-256 del payload clinico completo (sin `receta_id`)
- si el hash ya existe en cache y no ha expirado, se retorna la respuesta anterior sin tocar Ollama
- la respuesta cacheada incluye `"cached": true` en el JSON
- cuando se reinicia la API, el cache se limpia automaticamente

Configuracion (valores default en `config.py`, se pueden sobreescribir en `.env`):

- `CACHE_TTL_SECONDS=86400` - tiempo en segundos que una entrada permanece valida (24 horas)
- `CACHE_MAX_SIZE=500` - maximo de entradas en cache. Al llenarse, se descarta la mas antigua

Si quieres cambiar los defaults, agrega las variables a tu `.env`:

```env
CACHE_TTL_SECONDS=86400
CACHE_MAX_SIZE=500
```

Esto es especialmente util cuando el optometrista envia la misma consulta varias veces por accidente o impaciencia: la GPU solo trabaja la primera vez.
