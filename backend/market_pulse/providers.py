"""Bounded public RSS/Atom adapters; no full article scraping or paid feeds."""

import hashlib
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Protocol
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from backend.market_pulse.models import MarketEvent


def clean(text: str, limit=450) -> str:
    return re.sub(
        r"\s+", " ", BeautifulSoup(text or "", "html.parser").get_text(" ", strip=True)
    ).strip()[:limit]


def timestamp(value: str | None) -> str | None:
    if not value:
        return None
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        try:
            moment = parsedate_to_datetime(value)
        except (ValueError, TypeError, OverflowError):
            return None
    return moment.astimezone(UTC).isoformat() if moment.tzinfo else None


def canonical_url(url: str) -> str:
    parts = urlsplit(url)
    query = [
        (k, v)
        for k, v in parse_qsl(parts.query)
        if not k.startswith("utm_") and k not in {"fbclid", "gclid"}
    ]
    return urlunsplit(
        (parts.scheme.lower(), parts.netloc.lower(), parts.path, urlencode(query), "")
    )


def categorize(text: str, default: str):
    rules = [
        (r"\bsanctions?\b", "Sanctions", ["Cross-border business"]),
        (
            r"\btariffs?|trade restrictions?\b",
            "Trade / Tariffs",
            ["Cross-border business"],
        ),
        (r"\bwar|armed conflict|military strikes?\b", "War / Conflict", []),
        (r"\binflation|consumer price|\bcpi\b", "Inflation", []),
        (
            r"\bfomc|interest rates?|monetary policy|central bank\b",
            "Interest Rates / Central Banks",
            [],
        ),
        (r"\bemployment|payroll|unemployment\b", "Employment", []),
        (r"\bgdp|gross domestic product\b", "GDP / Growth", []),
        (r"\boil|natural gas|petroleum|diesel|energy supply\b", "Energy", ["Energy"]),
        (r"\bsemiconductors?|chips?\b", "Semiconductors", ["Semiconductors"]),
        (
            r"\bai\b|artificial intelligence",
            "Artificial Intelligence",
            ["AI infrastructure"],
        ),
        (r"\bsupply chain|shipping routes?\b", "Supply Chain", ["Supply chain"]),
        (r"\bregulation|regulator|antitrust\b", "Regulation", []),
        (r"\bacquisition|merger\b", "M&A", []),
        (r"\bgeopolitical|diplomatic\b", "Geopolitics", []),
        (
            r"\bearnings|dividend|financial results|appoints?\b",
            "Corporate / Industry Events",
            [],
        ),
    ]
    return next(
        (
            (category, sectors)
            for pattern, category, sectors in rules
            if re.search(pattern, text, re.IGNORECASE)
        ),
        (default, []),
    )


@dataclass
class FetchResult:
    events: list[MarketEvent] | None
    etag: str | None = None
    last_modified: str | None = None


class EventProvider(Protocol):
    id: str
    name: str
    ttl_seconds: int

    def fetch(self, state: dict) -> FetchResult: ...


@dataclass
class RSSProvider:
    id: str
    name: str
    url: str
    category: str
    ttl_seconds: int = 1800
    issuer: str | None = None

    def fetch(self, state: dict) -> FetchResult:
        headers = {
            "User-Agent": "ThesisLens/0.1 public RSS research",
            "Accept": "application/rss+xml, application/atom+xml, text/xml",
        }
        if state.get("etag"):
            headers["If-None-Match"] = state["etag"]
        if state.get("last_modified"):
            headers["If-Modified-Since"] = state["last_modified"]
        with requests.get(
            self.url, headers=headers, timeout=(3, 12), stream=True
        ) as response:
            if response.status_code == 304:
                return FetchResult(None, state.get("etag"), state.get("last_modified"))
            response.raise_for_status()
            content = bytearray()
            for chunk in response.iter_content(65536):
                content.extend(chunk)
                if len(content) > 2_000_000:
                    raise ValueError("Feed exceeded safe size limit")
            events = self.parse(bytes(content), datetime.now(UTC))
            if not events:
                raise ValueError("Feed supplied no valid dated events; retaining cache")
            return FetchResult(
                events,
                response.headers.get("ETag"),
                response.headers.get("Last-Modified"),
            )

    def parse(self, content: bytes, now: datetime) -> list[MarketEvent]:
        if b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
            raise ValueError("Unsupported feed entities")
        root = ET.fromstring(content)
        items = root.findall(".//item") or root.findall(
            ".//{http://www.w3.org/2005/Atom}entry"
        )
        events = []
        for item in items[:40]:
            fields = {child.tag.rsplit("}", 1)[-1]: child for child in item}

            def text(key, fields=fields):
                child = fields.get(key)
                return (child.text or "") if child is not None else ""

            headline = clean(text("title"), 220)
            link = fields.get("link")
            url = (
                canonical_url(
                    urljoin(self.url, link.get("href", "") or link.text or "")
                )
                if link is not None
                else ""
            )
            published = timestamp(
                text("pubDate") or text("published") or text("updated")
            )
            if (
                not headline
                or not published
                or urlsplit(url).scheme not in {"http", "https"}
            ):
                continue
            if (datetime.fromisoformat(published) - now).total_seconds() > 600:
                continue
            summary = clean(text("description") or text("summary")) or headline
            # The headline defines the release, not an incidental statistic in
            # its description (e.g. current-account balance as a percent of GDP).
            category, sectors = categorize(headline, self.category)
            events.append(
                MarketEvent(
                    id=hashlib.sha256(url.encode()).hexdigest()[:20],
                    headline=headline,
                    summary=summary,
                    category=category,
                    source=self.name,
                    source_url=url,
                    published_at=published,
                    event_time=None,
                    regions=[
                        r
                        for r in [
                            "China",
                            "Europe",
                            "United States",
                            "Middle East",
                            "Ukraine",
                            "Russia",
                        ]
                        if r.lower() in (headline + " " + summary).lower()
                    ],
                    sectors=sectors,
                    importance="HIGH"
                    if self.id == "fed" and "fomc" in headline.lower()
                    else "NORMAL",
                    cached_at=now.isoformat(),
                    provider_id=self.id,
                )
            )
        return events


def default_providers():
    return [
        RSSProvider(
            "bea",
            "Bureau of Economic Analysis",
            "https://apps.bea.gov/rss/rss.xml",
            "Macroeconomics",
            3600,
        ),
        RSSProvider(
            "fed",
            "Federal Reserve",
            "https://www.federalreserve.gov/feeds/press_monetary.xml",
            "Interest Rates / Central Banks",
            3600,
        ),
        RSSProvider(
            "bls",
            "Bureau of Labor Statistics",
            "https://www.bls.gov/feed/cpi.rss",
            "Inflation",
            3600,
        ),
        RSSProvider(
            "eia",
            "U.S. Energy Information Administration",
            "https://www.eia.gov/rss/todayinenergy.xml",
            "Energy",
            1800,
        ),
        RSSProvider(
            "nvidia",
            "NVIDIA Newsroom",
            "https://nvidianews.nvidia.com/cats/press_release.xml",
            "Technology",
            1800,
            "NVDA",
        ),
    ]
