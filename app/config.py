import logging

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Ollama — conexión y modelo
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"
    ollama_timeout: float = 120.0

    # Ollama — sampling
    ollama_temperature: float = 0.7
    ollama_num_predict: int = 600
    ollama_num_ctx: int = 2048          # Consumo real máximo ~1700 tokens;
                                        # 2048 ahorra ~256MB de VRAM vs 4096.
    ollama_repeat_penalty: float = 1.0  # 1.0 = desactivado. La terminología
                                        # clínica requiere repetición exacta
                                        # de términos (OD/OI, agudeza visual);
                                        # penalizarla genera circunloquios.
    ollama_top_p: float = 0.8
    ollama_top_k: int = 20              # Qwen3.5 non-thinking mode requiere top_k=20
    ollama_min_p: float = 0.0           # Qwen3.5 non-thinking mode requiere min_p=0.0
    ollama_seed: int = 42               # Fija reproducibilidad. -1 para
                                        # desactivar y obtener variabilidad.
    ollama_max_retries: int = 2         # Intentos ante ReadTimeout o error 5xx.

    # Concurrencia / cola
    max_concurrent: int = 1
    queue_wait_timeout: float = 120.0

    # Servidor
    host: str = "0.0.0.0"
    port: int = 8888

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

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
