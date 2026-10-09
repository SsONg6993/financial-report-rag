"""SEC identity matching uses disposable fixtures, never personal research data."""

import json
from datetime import UTC, datetime, timedelta

import pytest
import requests

from src.company_directory import DIRECTORY_URL, CompanyDirectory, CompanyIdentity
from src.sec import get_json


@pytest.fixture
def directory(tmp_path, monkeypatch):
    entries = [
        CompanyIdentity("TSLA", 1318605, "Tesla, Inc.", "Nasdaq"),
        CompanyIdentity("KEYS", 1601046, "Keysight Technologies, Inc.", "NYSE"),
        CompanyIdentity("AAPL", 320193, "Apple Inc.", "Nasdaq"),
        CompanyIdentity("NVDA", 1045810, "NVIDIA Corporation", "Nasdaq"),
        CompanyIdentity("GOOGL", 1652044, "Alphabet Inc.", "Nasdaq"),
        CompanyIdentity("GOOG", 1652044, "Alphabet Inc.", "Nasdaq"),
        CompanyIdentity("MSFT", 789019, "Microsoft Corporation", "Nasdaq"),
        CompanyIdentity("BRK-B", 1067983, "Berkshire Hathaway Inc.", "NYSE"),
    ]
    instance = CompanyDirectory(tmp_path / "directory.json")
    monkeypatch.setattr(instance, "load", lambda refresh=False: (
        entries, {"checked_at": "2026-10-09T00:00:00+00:00", "stale": False, "error": None}
    ))
    return instance


@pytest.mark.parametrize(("query", "expected"), [
    ("TSLA", "TSLA"), ("tesla", "TSLA"), ("Tesla, Inc.", "TSLA"),
    ("KEYS", "KEYS"), ("keysight", "KEYS"), ("Keysight Technologies", "KEYS"),
    ("AAPL", "AAPL"), ("apple", "AAPL"), ("NVDA", "NVDA"),
    ("MSFT", "MSFT"), ("BRK.B", "BRK-B"), ("brk-b", "BRK-B"),
    ("GOOGL", "GOOGL"), ("GOOG", "GOOG"),
])
def test_exact_company_resolution(directory, query, expected):
    result = directory.resolve(query)
    assert result["status"] == "resolved"
    assert result["company"]["ticker"] == expected
    assert result["company"]["source_url"] == DIRECTORY_URL


def test_share_classes_and_fuzzy_names_require_user_choice(directory):
    assert directory.resolve("Alphabet")["status"] == "ambiguous"
    assert {x["ticker"] for x in directory.resolve("Alphabet")["matches"]} == {"GOOG", "GOOGL"}
    suggestion = directory.resolve("Telsa")
    assert suggestion["status"] == "unknown"
    assert suggestion["matches"][0]["ticker"] == "TSLA"


def test_invalid_and_unsupported_are_distinct(directory):
    assert directory.resolve("TSLA$")["status"] == "invalid"
    assert directory.resolve("SHOP.TO")["status"] == "unsupported_market"
    assert directory.resolve("NOTAREALTICKER")["status"] == "unknown"


def test_validated_cache_is_used_and_stale_data_survives_provider_failure(tmp_path, monkeypatch):
    path = tmp_path / "directory.json"
    payload = {"fields": ["cik", "name", "ticker", "exchange"],
               "data": [[1318605, "Tesla, Inc.", "TSLA", "Nasdaq"]]}
    path.write_text(json.dumps({
        "checked_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
        "directory": payload,
    }), encoding="utf-8")
    instance = CompanyDirectory(path)

    class FailingSession:
        def get(self, *_args, **_kwargs):
            raise requests.Timeout("temporary outage")

    monkeypatch.setattr("src.company_directory.sec_session", lambda: FailingSession())
    monkeypatch.setattr("src.company_directory.time.sleep", lambda _seconds: None)
    entries, state = instance.load()
    assert entries[0].ticker == "TSLA"
    assert state["stale"] is True
    assert "Timeout" in state["error"]
    assert json.loads(path.read_text(encoding="utf-8"))["directory"] == payload


def test_invalid_directory_does_not_replace_last_good_cache(tmp_path, monkeypatch):
    path = tmp_path / "directory.json"
    payload = {"fields": ["cik", "name", "ticker", "exchange"],
               "data": [[1601046, "Keysight Technologies, Inc.", "KEYS", "NYSE"]]}
    path.write_text(json.dumps({
        "checked_at": (datetime.now(UTC) - timedelta(days=2)).isoformat(),
        "directory": payload,
    }), encoding="utf-8")
    instance = CompanyDirectory(path)

    class InvalidResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"fields": ["ticker"], "data": [["WRONG"]]}

    class InvalidSession:
        def get(self, *_args, **_kwargs):
            return InvalidResponse()

    monkeypatch.setattr("src.company_directory.sec_session", lambda: InvalidSession())
    entries, state = instance.load()
    assert entries[0].ticker == "KEYS"
    assert state["stale"] is True
    assert json.loads(path.read_text(encoding="utf-8"))["directory"] == payload


def test_transient_directory_timeout_retries_then_validates_and_caches(tmp_path, monkeypatch):
    path = tmp_path / "directory.json"
    attempts = []

    class ValidResponse:
        def raise_for_status(self):
            pass

        def json(self):
            return {"fields": ["cik", "name", "ticker", "exchange"],
                    "data": [[1318605, "Tesla, Inc.", "TSLA", "Nasdaq"]]}

    class RecoveringSession:
        def get(self, *_args, **_kwargs):
            attempts.append(1)
            if len(attempts) == 1:
                raise requests.Timeout("temporary")
            return ValidResponse()

    monkeypatch.setattr("src.company_directory.sec_session", lambda: RecoveringSession())
    monkeypatch.setattr("src.company_directory.time.sleep", lambda _seconds: None)
    entries, state = CompanyDirectory(path).load()
    assert len(attempts) == 2
    assert entries[0].ticker == "TSLA"
    assert state["stale"] is False
    assert path.exists()


def test_sec_json_retry_is_bounded_to_transient_failures(monkeypatch):
    attempts = []

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"ok": True}

    class Session:
        def get(self, *_args, **_kwargs):
            attempts.append(1)
            if len(attempts) == 1:
                raise requests.Timeout("temporary")
            return Response()

    monkeypatch.setattr("src.sec.time.sleep", lambda _seconds: None)
    assert get_json(Session(), "https://data.sec.gov/example") == {"ok": True}
    assert len(attempts) == 2
