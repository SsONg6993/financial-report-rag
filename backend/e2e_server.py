"""Playwright-only backend entrypoint: refuse personal paths, then seed a fresh DB."""

import os
from pathlib import Path

import uvicorn


def isolated_paths() -> tuple[Path, Path]:
    root = Path(__file__).resolve().parents[1]
    runtime = (root / ".e2e-runtime").resolve()
    if runtime.parent != root:
        raise SystemExit("E2E refused: fixture directory must not redirect outside the repository")
    expected = runtime / "thesislens-e2e.sqlite3"
    database = Path(os.environ.get("THESISLENS_E2E_DB", "")).resolve()
    configured = Path(os.environ.get("THESISLENS_DB", "")).resolve()
    cache = Path(os.environ.get("THESISLENS_CACHE_DIR", "")).resolve()
    if database != expected or configured != expected or cache != runtime / "cache":
        raise SystemExit("E2E refused: test database/cache must use the fixed isolated paths")
    if os.environ.get("THESISLENS_OFFLINE", "").lower() != "true":
        raise SystemExit("E2E refused: offline mode is required")
    if expected == (root / "data/local/thesislens.sqlite3").resolve():
        raise SystemExit("E2E refused: personal database path")
    return expected, cache


def main():
    database, cache = isolated_paths()
    database.parent.mkdir(parents=True, exist_ok=True)
    # Delete only the exact, guarded E2E fixture database. Never touch user data.
    database.unlink(missing_ok=True)
    from backend.e2e_seed import seed

    seed(database, cache)
    uvicorn.run("backend.main:app", host="127.0.0.1", port=18765, log_level="warning")


if __name__ == "__main__":
    main()
