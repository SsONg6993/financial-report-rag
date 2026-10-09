"""Optional, bounded free-channel delivery from the durable local outbox."""

import os
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit

import requests


class NotificationDispatcher:
    def __init__(self, store, session=None, clock=None):
        self.store = store
        self.session = session or requests
        self.clock = clock or (lambda: datetime.now(UTC))

    def _configuration(self):
        channel = os.getenv("THESISLENS_NOTIFICATION_CHANNEL", "local").lower()
        if channel == "local":
            return channel, None
        if channel == "telegram":
            token = os.getenv("THESISLENS_TELEGRAM_BOT_TOKEN", "")
            chat = os.getenv("THESISLENS_TELEGRAM_CHAT_ID", "")
            if not token or not chat or not all(c.isalnum() or c in ":_-" for c in token):
                raise ValueError("Telegram Bot token and chat ID are required for optional Telegram delivery")
            return channel, (token, chat)
        if channel == "ntfy":
            base = os.getenv("THESISLENS_NTFY_BASE_URL", "http://127.0.0.1:2586").rstrip("/")
            topic = os.getenv("THESISLENS_NTFY_TOPIC", "")
            parts = urlsplit(base)
            if parts.scheme not in {"http", "https"} or not parts.hostname or parts.username or parts.password:
                raise ValueError("Invalid self-hosted ntfy URL")
            if not topic or len(topic) > 100 or not all(c.isalnum() or c in "-_" for c in topic):
                raise ValueError("A simple ntfy topic is required")
            return channel, (base, topic)
        raise ValueError("Unsupported notification channel")

    @staticmethod
    def _message(event):
        return f"ThesisLens: {event['headline']}\n{event['source_url']}\nPublished/filed: {event['published_at'][:10]}"

    def _send(self, channel, config, event):
        message = self._message(event)
        if channel == "telegram":
            token, chat = config
            response = self.session.post(f"https://api.telegram.org/bot{token}/sendMessage",
                                         json={"chat_id": chat, "text": message,
                                               "disable_web_page_preview": True}, timeout=(3, 10))
        else:
            base, topic = config
            response = self.session.post(f"{base}/{topic}", data=message.encode(),
                                         headers={"Content-Type": "text/plain; charset=utf-8"}, timeout=(3, 10))
        response.raise_for_status()

    def _candidates(self, channel: str, max_items: int):
        now = self.clock()
        quiet_start = os.getenv("THESISLENS_QUIET_START_UTC", "22:00")
        quiet_end = os.getenv("THESISLENS_QUIET_END_UTC", "07:00")
        hour = now.strftime("%H:%M")
        quiet = (hour >= quiet_start or hour < quiet_end) if quiet_start > quiet_end else quiet_start <= hour < quiet_end
        if quiet:
            return [], "Quiet hours; outbox retained"
        rows = self.store.notifications(500)
        today = now.date().isoformat()
        delivered_today = sum(r["channel"] == channel and r["status"] == "delivered"
                              and (r["delivered_at"] or "").startswith(today) for r in rows)
        cap = min(max(int(os.getenv("THESISLENS_DAILY_NOTIFICATION_CAP", "20")), 0), 100)
        budget = min(max(max_items, 0), 5, max(0, cap - delivered_today))
        events = {e["id"]: e for e in self.store.intelligence_events(5000)}
        candidates = []
        for row in sorted(rows, key=lambda item: (item["priority"] != "critical", item["created_at"])):
            if len(candidates) >= budget:
                break
            if row["channel"] != "local" or row["status"] != "pending":
                continue
            event = events.get(row["event_id"])
            if not event:
                continue
            previous = next((r for r in rows if r["event_id"] == row["event_id"] and r["channel"] == channel), None)
            if previous and previous["status"] in {"delivered", "read", "dismissed"}:
                continue
            if previous and previous["attempted_at"]:
                attempted = datetime.fromisoformat(previous["attempted_at"])
                if now - attempted < timedelta(minutes=15):
                    continue
            candidates.append((row, event))
        return candidates, "Eligible pending alerts; digest-only events remain in the daily brief"

    def dry_run(self, channel: str, max_items: int = 1) -> dict:
        """Preview without credentials, network calls, or outbox mutations."""
        if channel not in {"telegram", "ntfy", "hermes"}:
            raise ValueError("Dry-run channel must be telegram, ntfy, or hermes")
        candidates, note = self._candidates(channel, max_items)
        return {"channel": channel, "dry_run": True, "note": note,
                "deliveries": [{"event_id": row["event_id"], "priority": row["priority"],
                                "message": self._message(event),
                                "source_url": event["source_url"],
                                "target": "Hermes REST consumer" if channel == "hermes" else channel}
                               for row, event in candidates]}

    def dispatch(self, max_items: int = 1) -> dict:
        """Explicit one-shot delivery. No paid broadcast, startup job, or infinite retries."""
        channel, config = self._configuration()
        if channel == "local":
            return {"channel": "local", "delivered": 0, "note": "Local outbox only; external delivery disabled"}
        candidates, note = self._candidates(channel, max_items)
        sent = 0
        for row, event in candidates:
            self.store.enqueue_notification(row["event_id"], channel, row["priority"])
            try:
                self._send(channel, config, event)
            except requests.RequestException as exc:
                self.store.set_notification_status(row["event_id"], channel, "failed", type(exc).__name__)
                continue
            self.store.set_notification_status(row["event_id"], channel, "delivered")
            sent += 1
        return {"channel": channel, "delivered": sent,
                "note": note + "; failures retry no sooner than 15 minutes"}
