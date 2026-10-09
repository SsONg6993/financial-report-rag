"""Deterministic Ask intent routing before any company or model work occurs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class AskMode(StrEnum):
    AUTO = "auto"
    GENERAL = "general"
    RESEARCH = "research"


class AskIntent(StrEnum):
    GENERAL = "general"
    FINANCIAL_RESEARCH = "financial_research"
    PORTFOLIO_ANALYSIS = "portfolio_analysis"
    CURRENT_PUBLIC_INFORMATION = "current_public_information"
    UNSUPPORTED = "unsupported"


@dataclass(frozen=True, slots=True)
class AskRoute:
    intent: AskIntent
    ticker: str | None
    reason: str


_EXCLUDED_SYMBOLS = {
    "AI",
    "API",
    "EPS",
    "ETF",
    "FCF",
    "GDP",
    "LLM",
    "PE",
    "RAG",
    "SEC",
    "USD",
    "YTD",
}
_COMPANY_ALIASES = {
    "apple": "AAPL",
    "alphabet": "GOOGL",
    "google": "GOOGL",
    "meta": "META",
    "microsoft": "MSFT",
    "nvidia": "NVDA",
    "rocket lab": "RKLB",
    "tesla": "TSLA",
}


def extract_ticker(question: str, context: str | None = None) -> str | None:
    symbols = re.findall(r"\b[A-Z][A-Z0-9.-]{0,9}\b", question)
    explicit = [symbol for symbol in symbols if symbol not in _EXCLUDED_SYMBOLS]
    if explicit:
        return explicit[-1]
    lowered = question.lower()
    alias = next(
        (ticker for name, ticker in _COMPANY_ALIASES.items() if name in lowered), None
    )
    return alias or (context.upper() if context else None)


def route_ask(
    question: str,
    mode: AskMode | str = AskMode.AUTO,
    ticker_context: str | None = None,
) -> AskRoute:
    selected_mode = AskMode(mode)
    query = question.strip().lower()
    ticker = extract_ticker(question, ticker_context)

    if selected_mode is AskMode.GENERAL:
        return AskRoute(AskIntent.GENERAL, None, "General mode selected by user.")

    if re.search(
        r"\b(execute|place|submit)\b.{0,24}\b(trade|order)\b|"
        r"\b(access|read|connect)\b.{0,24}\b(private account|brokerage|email)\b",
        query,
    ):
        return AskRoute(
            AskIntent.UNSUPPORTED,
            ticker,
            "The request requires account access or transaction execution.",
        )

    portfolio = bool(
        re.search(
            r"\b(13f|institutional|portfolio|holding|holdings|disclos|"
            r"berkshire|buffett|pershing|ackman|arkk?|cathie wood|"
            r"scion|burry|appaloosa|tepper|duquesne|druckenmiller)\b",
            query,
        )
    )
    current = bool(
        re.search(
            r"\b(news|headline|public update|press release|market pulse|macro|"
            r"oil price|today's news|current news|recent news|latest news)\b",
            query,
        )
    )
    financial = bool(
        ticker
        or re.search(
            r"\b(revenue|earnings|cash flow|free cash flow|margin|valuation|"
            r"filing|10-[qk]|balance sheet|income statement|financial|"
            r"quarter|annual|thesis|risk factor|eps)\b",
            query,
        )
    )

    if portfolio:
        return AskRoute(
            AskIntent.PORTFOLIO_ANALYSIS,
            ticker,
            "Institutional disclosure language detected.",
        )
    if current:
        return AskRoute(
            AskIntent.CURRENT_PUBLIC_INFORMATION,
            ticker,
            "Current or public-information language detected.",
        )
    if financial:
        return AskRoute(
            AskIntent.FINANCIAL_RESEARCH,
            ticker,
            "Company or financial-research language detected.",
        )
    if selected_mode is AskMode.RESEARCH:
        return AskRoute(
            AskIntent.UNSUPPORTED,
            None,
            "Research mode requires a company, filing, investor, or public-data question.",
        )
    return AskRoute(AskIntent.GENERAL, None, "No financial-data intent detected.")
