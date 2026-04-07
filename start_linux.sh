#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_ROOT"

if [ -f ".env" ]; then
    set -a
    # shellcheck disable=SC1091
    . ./.env
    set +a
fi

OLLAMA_URL="${OLLAMA_URL:-http://localhost:11434}"
OLLAMA_MODEL="${OLLAMA_MODEL:-qwen2.5:7b}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8888}"
STARTUP_WAIT_SECONDS="${STARTUP_WAIT_SECONDS:-45}"

if [ -f ".venv/bin/activate" ]; then
    VENV_DIR=".venv"
elif [ -f "venv/bin/activate" ]; then
    VENV_DIR="venv"
else
    echo "ERROR: No se encontro un entorno virtual."
    echo "Crea uno con: python3 -m venv .venv"
    echo "Luego instala dependencias con: .venv/bin/python -m pip install -r requirements.txt"
    exit 1
fi

if [ -z "${API_KEY:-}" ] || [ "${API_KEY:-}" = "cambia-este-token-por-uno-seguro" ]; then
    echo "ERROR: Configura un API_KEY valido en .env"
    exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
    echo "ERROR: curl no esta instalado."
    exit 1
fi

if ! command -v ollama >/dev/null 2>&1; then
    echo "ERROR: ollama no esta instalado."
    echo "Instalacion oficial: curl -fsSL https://ollama.com/install.sh | sh"
    exit 1
fi

OLLAMA_PID=""

cleanup() {
    if [ -n "$OLLAMA_PID" ] && kill -0 "$OLLAMA_PID" >/dev/null 2>&1; then
        echo ""
        echo "Deteniendo Ollama iniciado por este script..."
        kill "$OLLAMA_PID" >/dev/null 2>&1 || true
        wait "$OLLAMA_PID" 2>/dev/null || true
    fi
}

trap cleanup EXIT INT TERM

ollama_ready() {
    curl -fsS "${OLLAMA_URL%/}/api/tags" >/dev/null 2>&1
}

is_local_ollama_url() {
    case "$OLLAMA_URL" in
        http://localhost:*|https://localhost:*|http://127.0.0.1:*|https://127.0.0.1:*|http://0.0.0.0:*|https://0.0.0.0:*)
            return 0
            ;;
        *)
            return 1
            ;;
    esac
}

if ollama_ready; then
    echo "Ollama ya esta respondiendo en $OLLAMA_URL"
else
    if is_local_ollama_url; then
        echo "Ollama no responde. Iniciando ollama serve..."
        ollama serve > "$PROJECT_ROOT/ollama.log" 2>&1 &
        OLLAMA_PID="$!"
    else
        echo "ERROR: OLLAMA_URL apunta a un host remoto y no responde: $OLLAMA_URL"
        exit 1
    fi
fi

for _ in $(seq 1 "$STARTUP_WAIT_SECONDS"); do
    if ollama_ready; then
        break
    fi
    sleep 1
done

if ! ollama_ready; then
    echo "ERROR: Ollama no estuvo listo despues de ${STARTUP_WAIT_SECONDS}s."
    if [ -f "$PROJECT_ROOT/ollama.log" ]; then
        echo "Revisa el log: $PROJECT_ROOT/ollama.log"
    fi
    exit 1
fi

if ! ollama list | grep -Fq "$OLLAMA_MODEL"; then
    echo "Modelo $OLLAMA_MODEL no encontrado. Descargando..."
    ollama pull "$OLLAMA_MODEL"
fi

# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

echo "Entorno virtual activo: $VENV_DIR"
echo "Iniciando ia-api en http://$HOST:$PORT"

python -m uvicorn app.main:app --host "$HOST" --port "$PORT"
