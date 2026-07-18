from __future__ import annotations

import logging
from logging.handlers import TimedRotatingFileHandler

from .paths import log_dir


def configure_logging() -> logging.Logger:
    logger = logging.getLogger("autofire")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    handler = TimedRotatingFileHandler(
        log_dir() / "autofire.log",
        when="midnight",
        backupCount=30,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))
    logger.addHandler(handler)
    return logger
