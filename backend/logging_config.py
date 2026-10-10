"""Bounded local logging that never serializes configuration or user data."""

import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path


def configure_logging() -> None:
    root = Path(__file__).resolve().parents[1]
    log_dir = Path(os.getenv("THESISLENS_LOG_DIR", root / ".runtime" / "logs"))
    log_dir.mkdir(parents=True, exist_ok=True)
    handler = RotatingFileHandler(
        log_dir / "backend.log",
        maxBytes=2 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z",
        )
    )
    logger = logging.getLogger("thesislens")
    logger.setLevel(logging.INFO)
    if not any(
        isinstance(existing, RotatingFileHandler)
        and Path(existing.baseFilename) == Path(handler.baseFilename)
        for existing in logger.handlers
    ):
        logger.addHandler(handler)
