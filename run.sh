#!/bin/bash
set -e

# Verificar que API_KEY está configurada
if [ -f .env ]; then
    API_KEY=$(grep API_KEY .env | cut -d= -f2)
    if [ -z "$API_KEY" ] || [ "$API_KEY" = "cambia-este-token-por-uno-seguro" ]; then
        echo "ERROR: Configura un API_KEY seguro en .env"
        echo "Genera uno con: openssl rand -hex 32"
        exit 1
    fi
fi

# Verificar que Ollama está corriendo
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "ERROR: Ollama no está corriendo. Ejecuta: ollama serve"
    exit 1
fi

# Verificar que el modelo está descargado
MODEL=$(grep OLLAMA_MODEL .env | cut -d= -f2 || echo "llama3.1:8b")
if ! ollama list | grep -q "$MODEL"; then
    echo "Modelo $MODEL no encontrado. Descargando..."
    ollama pull "$MODEL"
fi

# Activar virtualenv si existe
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# Arrancar la API
uvicorn app.main:app --host 0.0.0.0 --port 8888 --reload
