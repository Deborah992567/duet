"""Structured logging configuration."""

import logging
import sys

from app.core.config import settings

_CONFIGURED = False

_LOGGER_FORMAT = (
    "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)

DEFAULT_LEVEL = logging.DEBUG if settings.debug else logging.INFO


def configure_logging(level: int = DEFAULT_LEVEL) -> None:
    global _CONFIGURED
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOGGER_FORMAT))
    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(handler)
    # Avoid duplicate handlers on hot reload.
    for h in list(root.handlers):
        if h is not handler and isinstance(h, logging.StreamHandler):
            root.removeHandler(h)
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    if not _CONFIGURED:
        configure_logging()
    return logging.getLogger(name)