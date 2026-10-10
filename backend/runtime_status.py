"""Version-aware, side-effect-free runtime diagnostics for local operation."""

from __future__ import annotations

import os
import sqlite3
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlparse

import requests

from src.config import AppConfig

APP_VERSION = "0.1.0"
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _git_commit() -> str:
    configured = os.getenv("THESISLENS_BUILD_COMMIT", "").strip()
    if configured:
        return configured
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            check=True,
            text=True,
            timeout=2,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return "unknown"


BUILD_COMMIT = _git_commit()
INSTANCE_ID = os.getenv("THESISLENS_RUNTIME_INSTANCE", "").strip() or None


def build_metadata() -> dict:
    return {
        "service": "ThesisLens Backend",
        "api_version": APP_VERSION,
        "build_commit": BUILD_COMMIT,
        "instance_id": INSTANCE_ID,
    }


def liveness() -> dict:
    """Cheap process liveness check; never touches external dependencies."""
    return {"status": "ok", **build_metadata()}


def probe_ollama(config: AppConfig, timeout: float = 2.0) -> dict:
    """Inspect Ollama without loading a model or sending user content."""
    endpoint = config.ollama_base_url.rstrip("/")
    parsed = urlparse(endpoint)
    if parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
        return {
            "status": "configuration_mismatch",
            "model": config.ollama_model,
            "model_available": False,
            "detail": "Configured Ollama endpoint is not local; automatic access is disabled.",
        }
    try:
        response = requests.get(f"{endpoint}/api/tags", timeout=(1, timeout))
        response.raise_for_status()
        models = response.json().get("models", [])
        installed = {
            name
            for item in models
            for name in (item.get("name"), item.get("model"))
            if isinstance(name, str)
        }
    except requests.ConnectionError:
        return {
            "status": "service_unavailable",
            "model": config.ollama_model,
            "model_available": False,
            "detail": "Ollama is not accepting local connections.",
        }
    except requests.Timeout:
        return {
            "status": "loading",
            "model": config.ollama_model,
            "model_available": False,
            "detail": "Ollama did not finish its readiness response in time.",
        }
    except (requests.RequestException, TypeError, ValueError, KeyError):
        return {
            "status": "invalid_response",
            "model": config.ollama_model,
            "model_available": False,
            "detail": "Ollama returned an invalid readiness response.",
        }
    available = config.ollama_model in installed
    return {
        "status": "ready" if available else "model_missing",
        "model": config.ollama_model,
        "model_available": available,
        "detail": (
            "Configured local model is installed."
            if available
            else "Configured model is not installed; downloads require approval."
        ),
    }


def _database_status(service) -> dict:
    try:
        with service.store.connect() as database:
            database.execute("SELECT 1").fetchone()
        return {"status": "ready", "accessible": True}
    except (sqlite3.Error, OSError) as exc:
        return {
            "status": "unavailable",
            "accessible": False,
            "detail": type(exc).__name__,
        }


def _cache_status() -> dict:
    path = Path(os.getenv("THESISLENS_CACHE_DIR", "data/cache"))
    candidate = path if path.exists() else path.parent
    accessible = candidate.exists() and os.access(candidate, os.R_OK | os.W_OK)
    return {
        "status": "ready" if accessible else "unavailable",
        "accessible": accessible,
    }


def readiness(service) -> dict:
    """Deep health summary. Optional dependencies never make the API crash."""
    database = _database_status(service)
    cache = _cache_status()
    ollama = probe_ollama(service.config)
    try:
        pulse = service.market_pulse.feed()
        market_pulse = {
            "status": pulse.get("status", "empty_cache"),
            "detail": pulse.get("diagnostic", "Market Pulse status unavailable."),
        }
    except (requests.RequestException, sqlite3.Error, OSError, ValueError, TypeError, KeyError) as exc:
        market_pulse = {
            "status": "error",
            "detail": f"Market Pulse diagnostic failed ({type(exc).__name__}).",
        }
    core_ready = database["accessible"] and cache["accessible"]
    return {
        "status": "ready" if core_ready else "degraded",
        **build_metadata(),
        "checked_at": datetime.now(UTC).isoformat(),
        "backend": {"status": "ready" if core_ready else "degraded"},
        "database": database,
        "cache": cache,
        "market_pulse": market_pulse,
        "ollama": ollama,
    }
