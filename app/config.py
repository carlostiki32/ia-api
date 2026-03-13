import logging

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Ollama
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_timeout: float = 120.0
    ollama_temperature: float = 0.1
    ollama_num_predict: int = 768

    # Concurrency / queue
    max_concurrent: int = 1
    queue_wait_timeout: float = 120.0

    # Server
    host: str = "0.0.0.0"
    port: int = 8888

    # Auth
    api_key: str = ""

    # Inference post-processing
    max_sentences: int = 10

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
