"""Small SQLite repository for personal research and dated source snapshots."""

import json
import sqlite3
import uuid
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path


def utc_now() -> str:
    return datetime.now(UTC).isoformat()


class LocalStore:
    def __init__(self, path: str | Path = "data/local/thesislens.sqlite3"):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS watchlist (
                    ticker TEXT PRIMARY KEY, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS follows (
                    entity_id TEXT PRIMARY KEY, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS theses (
                    id TEXT PRIMARY KEY, ticker TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS evaluations (
                    id TEXT PRIMARY KEY, thesis_id TEXT NOT NULL,
                    evaluated_at TEXT NOT NULL, payload TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS snapshots (
                    kind TEXT NOT NULL, entity_id TEXT NOT NULL, snapshot_id TEXT NOT NULL,
                    saved_at TEXT NOT NULL, payload TEXT NOT NULL,
                    PRIMARY KEY (kind, entity_id, snapshot_id));
            """)

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            with db:
                yield db
        finally:
            db.close()

    def watchlist(self) -> list[str]:
        with self.connect() as db:
            return [row[0] for row in db.execute("SELECT ticker FROM watchlist ORDER BY created_at")]

    def watch(self, ticker: str, enabled: bool = True):
        from src.sec import normalize_ticker

        ticker = normalize_ticker(ticker)
        with self.connect() as db:
            if enabled:
                db.execute("INSERT OR IGNORE INTO watchlist VALUES (?, ?)", (ticker, utc_now()))
            else:
                db.execute("DELETE FROM watchlist WHERE ticker=?", (ticker,))

    def follows(self) -> list[str]:
        with self.connect() as db:
            return [row[0] for row in db.execute("SELECT entity_id FROM follows ORDER BY created_at")]

    def follow(self, entity_id: str, enabled: bool = True):
        with self.connect() as db:
            if enabled:
                db.execute("INSERT OR IGNORE INTO follows VALUES (?, ?)", (entity_id, utc_now()))
            else:
                db.execute("DELETE FROM follows WHERE entity_id=?", (entity_id,))

    def save_thesis(self, ticker: str, text: str, rule: dict | None = None,
                    thesis_id: str | None = None) -> dict:
        if not text.strip():
            raise ValueError("A thesis needs text.")
        previous = next((x for x in self.theses(ticker) if x["id"] == thesis_id), None)
        item = {
            "id": thesis_id or uuid.uuid4().hex,
            "ticker": ticker,
            "text": text.strip(),
            "rule": rule,
            "created_at": previous["created_at"] if previous else utc_now(),
            "updated_at": utc_now(),
            "last_evaluated_at": None,
            "status": "NOT_EVALUATED",
            "supporting_evidence": [],
            "contradicting_evidence": [],
        }
        # An edited claim must be evaluated again; old evaluations stay in history.
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO theses VALUES (?, ?, ?)",
                       (item["id"], ticker, json.dumps(item)))
        return item

    def theses(self, ticker: str) -> list[dict]:
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute(
                "SELECT payload FROM theses WHERE ticker=? ORDER BY rowid", (ticker,))]

    def record_evaluation(self, thesis: dict, evaluation: dict):
        item = {**thesis, **evaluation, "last_evaluated_at": evaluation["evaluated_at"]}
        with self.connect() as db:
            db.execute("INSERT INTO evaluations VALUES (?, ?, ?, ?)",
                       (uuid.uuid4().hex, thesis["id"], evaluation["evaluated_at"], json.dumps(item)))
            db.execute("UPDATE theses SET payload=? WHERE id=?", (json.dumps(item), thesis["id"]))

    def history(self, thesis_id: str) -> list[dict]:
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute(
                "SELECT payload FROM evaluations WHERE thesis_id=? ORDER BY evaluated_at", (thesis_id,))]

    def save_snapshot(self, kind: str, entity_id: str, snapshot_id: str, payload: dict):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO snapshots VALUES (?, ?, ?, ?, ?)",
                       (kind, entity_id, snapshot_id, utc_now(), json.dumps(payload)))

    def snapshots(self, kind: str, entity_id: str) -> list[dict]:
        with self.connect() as db:
            return [json.loads(row[0]) for row in db.execute(
                "SELECT payload FROM snapshots WHERE kind=? AND entity_id=? ORDER BY snapshot_id DESC",
                (kind, entity_id))]
