"""Free official-source providers. Source text is data, never instructions."""

import re
from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from backend.market_pulse.providers import canonical_url
from src.local_store import utc_now


@dataclass(frozen=True)
class PublicUpdate:
    provider_id: str
    source_id: str
    entity_id: str
    publisher: str
    headline: str
    original_url: str
    published_at: str | None
    event_at: str | None
    checked_at: str
    source_type: str
    cursor: str | None = None


class PublicUpdateProvider(Protocol):
    id: str

    def fetch_updates(self, source: str, cursor: str | None = None, limit: int = 40) -> list[PublicUpdate]: ...
    def resolve_source(self, identifier: str) -> str | None: ...
    def health_check(self) -> dict: ...


class RSSPublicUpdateProvider:
    """Read the last-good cache from Market Pulse's official RSS/Atom adapters."""

    id = "rss"

    def __init__(self, pulse):
        self.pulse = pulse

    def resolve_source(self, identifier: str) -> str | None:
        return next((p.id for p in self.pulse.providers if p.id == identifier), None)

    def fetch_updates(self, source: str, cursor: str | None = None, limit: int = 40) -> list[PublicUpdate]:
        provider = next((p for p in self.pulse.providers if p.id == source), None)
        if provider is None:
            raise ValueError("Unknown official RSS source")
        rows = self.pulse.state(provider).get("events", [])
        updates = []
        for row in rows[:max(1, min(limit, 40))]:
            url, published = row.get("source_url", ""), row.get("published_at")
            if not published or urlsplit(url).scheme != "https":
                continue
            if cursor and published <= cursor:
                continue
            updates.append(PublicUpdate(
                provider_id=self.id, source_id=provider.id, entity_id=provider.id,
                publisher=provider.name, headline=row.get("headline", "")[:220],
                original_url=canonical_url(url), published_at=published,
                event_at=row.get("event_time"), checked_at=utc_now(),
                source_type="Official RSS/Atom", cursor=published,
            ))
        return updates

    def health_check(self) -> dict:
        return {p.id: {k: self.pulse.state(p).get(k) for k in ("checked_at", "successful_at", "error")}
                for p in self.pulse.providers}


class OfficialDisclosureProvider:
    """Read existing dated SEC/ARK caches; SEC adapters remain the only fetchers."""

    id = "official_disclosure"

    def __init__(self, research):
        self.research = research

    def resolve_source(self, identifier: str) -> str | None:
        return identifier if self.research.registry.get(identifier) else None

    def fetch_updates(self, source: str, cursor: str | None = None, limit: int = 40) -> list[PublicUpdate]:
        manager = self.research.registry.get(source)
        if not manager:
            raise ValueError("Unknown tracked manager")
        updates = []
        for filing in self.research.portfolios(source)[:max(1, min(limit, 40))]:
            if cursor and filing.filing_date <= cursor:
                continue
            updates.append(PublicUpdate(
                provider_id=self.id, source_id=source, entity_id=source,
                publisher=manager.name, headline=f"{manager.name} reported holdings for {filing.reporting_period}",
                original_url=filing.source_url, published_at=filing.filing_date,
                event_at=None, checked_at=utc_now(), source_type=filing.source_type,
                cursor=filing.filing_date,
            ))
        return updates

    def health_check(self) -> dict:
        return {"available": True, "mode": "cached official filings; no independent network fetch"}


class WebsiteFeedProvider:
    """Curated official Berkshire letter index; year-only links are not dated feed events."""

    id = "website"
    SOURCE = "berkshire-letters"
    URL = "https://www.berkshirehathaway.com/letters/letters.html"

    def resolve_source(self, identifier: str) -> str | None:
        return self.SOURCE if identifier == self.SOURCE else None

    def fetch_updates(self, source: str, cursor: str | None = None, limit: int = 40) -> list[PublicUpdate]:
        if source != self.SOURCE:
            raise ValueError("Unsupported official website source")
        response = requests.get(self.URL, timeout=(3, 12), stream=True,
                                headers={"User-Agent": "ThesisLens/0.1 public letter index"})
        response.raise_for_status()
        content = bytearray()
        for chunk in response.iter_content(65536):
            content.extend(chunk)
            if len(content) > 1_000_000:
                raise ValueError("Official index exceeded safe size limit")
        soup = BeautifulSoup(bytes(content), "html.parser")
        updates = []
        for anchor in soup.find_all("a", href=True):
            year = anchor.get_text(" ", strip=True)
            if not re.fullmatch(r"(?:19|20)\d{2}", year):
                continue
            url = canonical_url(urljoin(self.URL, anchor["href"]))
            if urlsplit(url).hostname != "www.berkshirehathaway.com":
                continue
            # An index year is not a publication day. Never fabricate a date.
            updates.append(PublicUpdate(
                provider_id=self.id, source_id=self.SOURCE, entity_id="berkshire",
                publisher="Berkshire Hathaway", headline=f"Berkshire Hathaway {year} shareholder letter",
                original_url=url, published_at=None, event_at=None, checked_at=utc_now(),
                source_type="Official investor letter index", cursor=year,
            ))
        return sorted(updates, key=lambda item: item.cursor or "", reverse=True)[:max(1, min(limit, 40))]

    def health_check(self) -> dict:
        return {"available": True, "source_url": self.URL, "publication_dates": "year only; excluded from dated feed"}
