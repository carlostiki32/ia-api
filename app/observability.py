"""Logging y trazabilidad de requests.

- `request_id_var`: ContextVar con el id corto del request en curso. El middleware
  de main.py lo asigna al entrar cada request (propaga el header X-Request-ID si el
  cliente lo envia, o genera uno) y TODOS los registros de log lo incluyen como
  `[rid]` via RequestIdFilter, de modo que se puede seguir un request completo con
  `grep <rid> logs/inference.log`.
- `setup_logging()`: configura el logger raiz con tres destinos:
    * consola (todo, segun LOG_LEVEL);
    * logs/inference.log rotatorio (10 MB x 5 archivos) con el mismo nivel;
    * logs/errors.log rotatorio SOLO con WARNING+ — el primer lugar a revisar
      cuando algo falla.

Este modulo solo usa stdlib (sin imports de app.*) para poder ser importado por
config.py sin ciclos.
"""
from __future__ import annotations

import contextvars
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)

_LOG_DIR = Path("logs")
_MAX_BYTES = 10 * 1024 * 1024  # 10 MB por archivo antes de rotar
_BACKUP_COUNT = 5              # inference.log + .1 .. .5

_configured = False


class RequestIdFilter(logging.Filter):
    """Inyecta el request-id del contexto en cada registro como %(rid)s."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.rid = request_id_var.get()
        return True


def setup_logging(level_name: str) -> Path:
    """Configura el logger raiz. Idempotente: llamadas repetidas (reload de
    uvicorn, imports en tests) no duplican handlers."""
    global _configured

    level = getattr(logging, level_name.upper(), logging.INFO)
    _LOG_DIR.mkdir(exist_ok=True)
    log_file = _LOG_DIR / "inference.log"
    error_file = _LOG_DIR / "errors.log"

    root = logging.getLogger()
    root.setLevel(level)

    # httpx loggea cada request a INFO; es ruido que duplica nuestros propios
    # logs (el POST a Ollama ya se reporta con metricas). Solo warnings.
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if _configured:
        return log_file
    _configured = True

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] [%(rid)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    rid_filter = RequestIdFilter()

    console_handler = logging.StreamHandler()

    file_handler = RotatingFileHandler(
        log_file, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )

    # Solo WARNING+ con traceback completo: el archivo que se revisa primero.
    error_handler = RotatingFileHandler(
        error_file, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    error_handler.setLevel(logging.WARNING)

    for handler in (console_handler, file_handler, error_handler):
        handler.setFormatter(formatter)
        handler.addFilter(rid_filter)
        root.addHandler(handler)

    return log_file
