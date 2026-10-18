from types import SimpleNamespace

import requests

from backend import runtime_status
from src.config import AppConfig
from src.local_store import LocalStore


def config(**overrides):
    values = {
        "sec_user_agent": "",
        "embedding_model": "test",
        "qdrant_path": "test",
        "ollama_base_url": "http://127.0.0.1:11434",
        "ollama_model": "qwen3:4b",
        "ollama_readiness_timeout": 1,
        "ollama_inference_timeout": 5,
        "ollama_readiness_retries": 0,
        "allow_remote_llm": False,
        "enable_jev": False,
        "typesafe_api_key": "",
        "jev_model": "jev-latest",
        "jev_confidence_threshold": 0.7,
        "chunk_size": 100,
        "chunk_overlap": 10,
    }
    values.update(overrides)
    return AppConfig(**values)


def test_liveness_has_version_without_dependency_checks(monkeypatch):
    monkeypatch.setattr(runtime_status, "BUILD_COMMIT", "abc123")
    result = runtime_status.liveness()
    assert result == {
        "status": "ok",
        "service": "ThesisLens Backend",
        "api_version": "0.1.0",
        "build_commit": "abc123",
        "instance_id": runtime_status.INSTANCE_ID,
    }


def test_ollama_probe_distinguishes_stopped_and_missing(monkeypatch):
    monkeypatch.setattr(
        runtime_status.requests,
        "get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            requests.ConnectionError("refused")
        ),
    )
    assert runtime_status.probe_ollama(config())["status"] == "service_unavailable"

    class Tags:
        def raise_for_status(self):
            return None

        def json(self):
            return {"models": [{"name": "llama3.2:latest"}]}

    monkeypatch.setattr(runtime_status.requests, "get", lambda *_a, **_k: Tags())
    result = runtime_status.probe_ollama(config())
    assert result["status"] == "model_missing"
    assert result["model"] == "qwen3:4b"


def test_readiness_keeps_market_pulse_failure_optional(tmp_path, monkeypatch):
    store = LocalStore(tmp_path / "runtime.sqlite3")

    class BrokenPulse:
        def feed(self):
            raise ValueError("synthetic provider failure")

    service = SimpleNamespace(store=store, config=config(), market_pulse=BrokenPulse())
    monkeypatch.setattr(
        runtime_status,
        "probe_ollama",
        lambda *_args, **_kwargs: {
            "status": "service_unavailable",
            "model": "qwen3:4b",
            "model_available": False,
            "detail": "offline",
        },
    )
    monkeypatch.setenv("THESISLENS_CACHE_DIR", str(tmp_path))
    result = runtime_status.readiness(service)
    assert result["status"] == "ready"
    assert result["database"]["accessible"]
    assert result["market_pulse"]["status"] == "error"
    assert result["ollama"]["status"] == "service_unavailable"


def test_remote_ollama_is_never_probed_without_local_configuration(monkeypatch):
    monkeypatch.setattr(
        runtime_status.requests,
        "get",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("must not contact remote endpoint")
        ),
    )
    result = runtime_status.probe_ollama(
        config(ollama_base_url="https://example.invalid")
    )
    assert result["status"] == "configuration_mismatch"
