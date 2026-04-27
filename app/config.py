import logging

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # Ollama — conexión y modelo
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen3.5:9b"
    ollama_timeout: float = 120.0

    # Ollama — sampling
    ollama_temperature: float = 0.7
    ollama_num_predict: int = 1024      # Budget de salida. 1024 elimina el
                                        # truncado (done_reason=length) en
                                        # casos con 4+ correlaciones activas
                                        # + recomendacion; impacto de VRAM
                                        # marginal con num_ctx=4096.
    ollama_num_ctx: int = 4096          # Minimo operacional seguro: cubre
                                        # system prompt (~300 tok) + user
                                        # prompt peak (~1200 tok) + correlaciones
                                        # (~400 tok) + num_predict (1024) con
                                        # margen. KV extra sobre 2048 son ~80MB
                                        # en Q4_K_M, absorbible en la 3070 Ti.
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
    max_queue_size: int = 5             # Requests maximas en espera antes de 503.

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

    # Web inference (NVIDIA NIM)
    web_inference: bool = False
    nvidia_api_key: str = ""
    nvidia_base_url: str = "https://integrate.api.nvidia.com/v1"
    nvidia_model: str = "deepseek-ai/deepseek-v3.2"
    nvidia_timeout: float = 60.0
    nvidia_max_tokens: int = 1024
    nvidia_temperature: float = 0.7
    nvidia_top_p: float = 0.95
    nvidia_thinking: bool = False          # chat_template_kwargs thinking mode
    nvidia_max_retries: int = 2

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
