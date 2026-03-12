from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_timeout: float = 120.0
    max_concurrent: int = 1
    queue_wait_timeout: float = 120.0
    host: str = "0.0.0.0"
    port: int = 8888
    api_key: str = ""

    model_config = {"env_file": ".env"}


settings = Settings()
