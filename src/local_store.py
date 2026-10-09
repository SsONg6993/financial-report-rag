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
                BEGIN IMMEDIATE;
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
                CREATE TABLE IF NOT EXISTS tracked_entities (
                    id TEXT PRIMARY KEY, cik INTEGER UNIQUE NOT NULL, payload TEXT NOT NULL,
                    verified_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS source_follows (
                    source_id TEXT PRIMARY KEY, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS intelligence_events (
                    id TEXT PRIMARY KEY, event_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL, ticker TEXT NOT NULL,
                    published_at TEXT NOT NULL, detected_at TEXT NOT NULL,
                    payload TEXT NOT NULL, read_at TEXT);
                CREATE INDEX IF NOT EXISTS idx_intelligence_events_published
                    ON intelligence_events(published_at DESC);
                CREATE TABLE IF NOT EXISTS notification_outbox (
                    event_id TEXT NOT NULL, channel TEXT NOT NULL,
                    priority TEXT NOT NULL, status TEXT NOT NULL,
                    created_at TEXT NOT NULL, attempted_at TEXT,
                    delivered_at TEXT, read_at TEXT, error TEXT,
                    PRIMARY KEY (event_id, channel));
                CREATE TABLE IF NOT EXISTS schema_migrations (
                    version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
                INSERT OR IGNORE INTO schema_migrations VALUES (2, CURRENT_TIMESTAMP);
                COMMIT;
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
            return [
                row[0]
                for row in db.execute(
                    "SELECT ticker FROM watchlist ORDER BY created_at"
                )
            ]

    def watch(self, ticker: str, enabled: bool = True):
        from src.sec import normalize_ticker

        ticker = normalize_ticker(ticker)
        with self.connect() as db:
            if enabled:
                db.execute(
                    "INSERT OR IGNORE INTO watchlist VALUES (?, ?)", (ticker, utc_now())
                )
            else:
                db.execute("DELETE FROM watchlist WHERE ticker=?", (ticker,))

    def follows(self) -> list[str]:
        with self.connect() as db:
            return [
                row[0]
                for row in db.execute(
                    "SELECT entity_id FROM follows ORDER BY created_at"
                )
            ]

    def follow(self, entity_id: str, enabled: bool = True):
        with self.connect() as db:
            if enabled:
                db.execute(
                    "INSERT OR IGNORE INTO follows VALUES (?, ?)",
                    (entity_id, utc_now()),
                )
            else:
                db.execute("DELETE FROM follows WHERE entity_id=?", (entity_id,))

    def source_follows(self) -> list[str]:
        with self.connect() as db:
            return [row[0] for row in db.execute("SELECT source_id FROM source_follows ORDER BY created_at")]

    def follow_source(self, source_id: str, enabled: bool = True):
        if not source_id or len(source_id) > 100 or not all(c.isalnum() or c in "-_" for c in source_id):
            raise ValueError("Invalid public source identifier")
        with self.connect() as db:
            if enabled:
                db.execute("INSERT OR IGNORE INTO source_follows VALUES (?, ?)", (source_id, utc_now()))
            else:
                db.execute("DELETE FROM source_follows WHERE source_id=?", (source_id,))

    def save_intelligence_event(self, item: dict) -> bool:
        with self.connect() as db:
            cursor = db.execute(
                "INSERT OR IGNORE INTO intelligence_events "
                "(id,event_type,entity_id,ticker,published_at,detected_at,payload) "
                "VALUES (?,?,?,?,?,?,?)",
                (item["id"], item["event_type"], item["entity_id"], item.get("ticker") or "",
                 item["published_at"], item["detected_at"], json.dumps(item)),
            )
            return cursor.rowcount == 1

    def intelligence_events(self, limit: int = 200) -> list[dict]:
        with self.connect() as db:
            rows = db.execute(
                "SELECT payload,read_at FROM intelligence_events "
                "ORDER BY published_at DESC,id LIMIT ?", (min(max(limit, 1), 5000),)
            ).fetchall()
        return [{**json.loads(payload), "read_at": read_at} for payload, read_at in rows]

    def mark_intelligence_read(self, event_id: str) -> bool:
        with self.connect() as db:
            cursor = db.execute("UPDATE intelligence_events SET read_at=COALESCE(read_at,?) WHERE id=?",
                                (utc_now(), event_id))
            db.execute("UPDATE notification_outbox SET read_at=COALESCE(read_at,?), status='read' WHERE event_id=?",
                       (utc_now(), event_id))
            return cursor.rowcount == 1

    def dismiss_notification(self, event_id: str) -> bool:
        with self.connect() as db:
            exists = db.execute("SELECT 1 FROM intelligence_events WHERE id=?", (event_id,)).fetchone()
            db.execute("UPDATE notification_outbox SET status='dismissed' WHERE event_id=? AND status IN ('pending','failed')",
                       (event_id,))
            return bool(exists)

    def enqueue_notification(self, event_id: str, channel: str, priority: str):
        with self.connect() as db:
            db.execute("INSERT OR IGNORE INTO notification_outbox "
                       "(event_id,channel,priority,status,created_at) VALUES (?,?,?,?,?)",
                       (event_id, channel, priority, "pending", utc_now()))

    def notifications(self, limit: int = 100) -> list[dict]:
        with self.connect() as db:
            rows = db.execute("SELECT event_id,channel,priority,status,created_at,attempted_at,delivered_at,read_at,error "
                              "FROM notification_outbox ORDER BY created_at DESC LIMIT ?", (min(max(limit, 1), 500),)).fetchall()
        return [dict(zip(("event_id", "channel", "priority", "status", "created_at", "attempted_at", "delivered_at", "read_at", "error"), row, strict=True)) for row in rows]

    def set_notification_status(self, event_id: str, channel: str, status: str, error: str | None = None):
        if status not in {"delivered", "failed", "dismissed", "read"}:
            raise ValueError("Unsupported notification status")
        now = utc_now()
        with self.connect() as db:
            db.execute("UPDATE notification_outbox SET status=?,error=?,attempted_at=?,"
                       "delivered_at=CASE WHEN ?='delivered' THEN ? ELSE delivered_at END,"
                       "read_at=CASE WHEN ?='read' THEN ? ELSE read_at END "
                       "WHERE event_id=? AND channel=?",
                       (status, error, now, status, now, status, now, event_id, channel))

    def save_thesis(
        self,
        ticker: str,
        text: str,
        rule: dict | None = None,
        thesis_id: str | None = None,
    ) -> dict:
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
            db.execute(
                "INSERT OR REPLACE INTO theses VALUES (?, ?, ?)",
                (item["id"], ticker, json.dumps(item)),
            )
        return item

    def theses(self, ticker: str) -> list[dict]:
        with self.connect() as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT payload FROM theses WHERE ticker=? ORDER BY rowid",
                    (ticker,),
                )
            ]

    def record_evaluation(self, thesis: dict, evaluation: dict):
        item = {**thesis, **evaluation, "last_evaluated_at": evaluation["evaluated_at"]}
        with self.connect() as db:
            db.execute(
                "INSERT INTO evaluations VALUES (?, ?, ?, ?)",
                (
                    uuid.uuid4().hex,
                    thesis["id"],
                    evaluation["evaluated_at"],
                    json.dumps(item),
                ),
            )
            db.execute(
                "UPDATE theses SET payload=? WHERE id=?",
                (json.dumps(item), thesis["id"]),
            )

    def history(self, thesis_id: str) -> list[dict]:
        with self.connect() as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT payload FROM evaluations WHERE thesis_id=? ORDER BY evaluated_at",
                    (thesis_id,),
                )
            ]

    def save_snapshot(self, kind: str, entity_id: str, snapshot_id: str, payload: dict):
        with self.connect() as db:
            db.execute(
                "INSERT OR REPLACE INTO snapshots VALUES (?, ?, ?, ?, ?)",
                (kind, entity_id, snapshot_id, utc_now(), json.dumps(payload)),
            )

    def snapshots(self, kind: str, entity_id: str) -> list[dict]:
        with self.connect() as db:
            return [
                json.loads(row[0])
                for row in db.execute(
                    "SELECT payload FROM snapshots WHERE kind=? AND entity_id=? ORDER BY snapshot_id DESC",
                    (kind, entity_id),
                )
            ]
