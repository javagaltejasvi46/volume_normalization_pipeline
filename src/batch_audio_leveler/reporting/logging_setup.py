"""Structured logging configuration."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional


def setup_logger(log_file: Optional[Path] = None, level: int = logging.INFO) -> logging.Logger:
    """Configure application logger with file and optional console handler."""
    logger = logging.getLogger("batch_audio_leveler")
    logger.setLevel(level)

    # Avoid duplicate handlers if already configured
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if log_file:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(str(log_file), encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(level)
        logger.addHandler(file_handler)

    # Null handler to prevent "no handler" warning if no handlers attached
    logger.addHandler(logging.NullHandler())
    return logger
