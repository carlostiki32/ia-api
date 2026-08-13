import logging

from pydantic_settings import BaseSettings, SettingsConfigDict

from app.observability import setup_logging


class Settings(BaseSettings):
    # Ollama — conexión y modelo
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"
    ollama_timeout: float = 120.0

    # Ollama — sampling
    ollama_temperature: float = 0.2     # Tarea de EXTRACCION/reporte fiel, no chat
                                        # general: la guia de Qwen3.5 recomienda
                                        # 0.1-0.3 para extraccion. Con seed fijo da
                                        # salida casi determinista y reproducible
                                        # (auditable) y reduce la cola de tokens
                                        # improbables donde asoma la invencion.
                                        # Coste de VRAM: cero.
    ollama_num_predict: int = 1024      # Budget de salida. 1024 elimina el
                                        # truncado (done_reason=length) en
                                        # casos con 4+ correlaciones activas
                                        # + recomendacion; los reportes reales
                                        # promedian ~100 tok, asi que sobra.
    ollama_num_ctx: int = 8192          # El system prompt afinado pesa ~1595 tok y
                                        # el payload MAXIMO del diccionario (6 campos
                                        # de texto libre a 255 char + AKR completo)
                                        # da ~3300 tok de prompt; con num_predict
                                        # 1024 = ~4328 tok, que NO cabe en 4096 (413).
                                        # MEDIDO en la 3070 Ti (8GB): 4096->8192 solo
                                        # sube el footprint de 8.9GB a 9.1GB y el split
                                        # se mantiene ~72% GPU (la arquitectura hibrida
                                        # de Qwen3.5 -24/32 capas Gated DeltaNet sin
                                        # KV-cache- hace el contexto barato). El modelo
                                        # ya corre ~28% en CPU a CUALQUIER num_ctx por
                                        # el tamano de los pesos, no por el contexto.
    ollama_repeat_penalty: float = 1.0  # 1.0 = desactivado. La terminología
                                        # clínica requiere repetición exacta
                                        # de términos (OD/OI, agudeza visual);
                                        # penalizarla genera circunloquios.
                                        # NOTA: el preset non-thinking oficial de
                                        # Qwen3.5 lista presence_penalty=1.5, que
                                        # Ollama NO expone. NO mapear a
                                        # repeat_penalty: son semánticas distintas
                                        # (la doc del modelo lo prohíbe explícitamente).
    ollama_top_p: float = 0.8
    ollama_top_k: int = 20              # Qwen3.5 non-thinking mode requiere top_k=20
    ollama_min_p: float = 0.0           # Qwen3.5 non-thinking mode requiere min_p=0.0
    ollama_seed: int = 42               # Fija reproducibilidad. -1 para
                                        # desactivar y obtener variabilidad.
    ollama_max_retries: int = 2         # Intentos ante ReadTimeout o error 5xx.

    # Concurrencia / cola
    max_concurrent: int = 1
    queue_wait_timeout: float = 30.0
    max_queue_size: int = 5             # Requests maximas en espera antes de 503.

    # Autenticación
    api_key: str = ""

    # Postprocesamiento de inferencia
    max_sentences: int = 10

    # Cache
    cache_ttl_seconds: int = 86400
    cache_max_size: int = 500

    # Health check
    health_check_timeout: float = 5.0

    # Logging
    log_level: str = "INFO"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()

# Logging: consola + logs/inference.log (rotatorio) + logs/errors.log (WARNING+).
# Cada registro incluye el request-id ([rid]) que asigna el middleware de main.py.
_LOG_FILE = setup_logging(settings.log_level)
logging.info(
    "Logging iniciado — %s (nivel %s; errores tambien en logs/errors.log)",
    _LOG_FILE.resolve(), settings.log_level.upper(),
)
