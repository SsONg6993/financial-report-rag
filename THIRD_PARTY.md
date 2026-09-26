# Third-party components

This project integrates mature libraries through small internal adapters. No third-party algorithm implementation has been copied into the repository.

| Component | Project / license | Use and rationale | Local modifications |
|---|---|---|---|
| Streamlit | `streamlit/streamlit`, Apache-2.0 | Local interactive dashboard with native metrics, tabs, caching, and downloads. | Application-specific dashboard composition only. |
| Sentence Transformers | `UKPLab/sentence-transformers`, Apache-2.0 | Local `BAAI/bge-small-en-v1.5` embeddings and optional CrossEncoder reranking. | Wrapped by `Embeddings` and `CrossEncoderReranker`. |
| Qdrant client | `qdrant/qdrant-client`, Apache-2.0 | Embedded local vector persistence and cosine retrieval without a server. | Wrapped by `Retriever`; filing/model-specific collection names. |
| BM25S | `xhluca/bm25s`, MIT | Fast, maintained sparse retrieval implementation. | Wrapped by `BM25Retriever` with Lucene-style BM25 parameters. |
| Plotly | `plotly/plotly.py`, MIT | Interactive financial and peer-comparison charts. | No library modifications. |
| pandas / NumPy | BSD-3-Clause | Tabular transformations and numerical data handling. | No library modifications. |
| Beautiful Soup | `wention/BeautifulSoup4`, MIT | Practical SEC HTML parsing. | Filing-specific cleanup and table serialization in `src/parser.py`. |
| lxml | BSD-3-Clause | Robust HTML parser backend. | No library modifications. |
| Requests | Apache-2.0 | SEC, Ollama, and TypeSafe HTTP calls. | Timeouts, SEC identification, caching, and graceful fallbacks. |
| yfinance | `ranaroussi/yfinance`, Apache-2.0 | Optional no-key market snapshot provider. Yahoo data can be delayed or unavailable. | Isolated behind `MarketDataProvider`; failures return a partial snapshot. |
| TypeSafe Jev | External TypeSafe AI service; API terms apply | Optional typed Choice, Score, and Noul judgments for routing, evidence, risk, and bounded workflow decisions. | Direct adapter to the documented System One HTTP API. No TypeSafe source code copied. |
| Ollama | `ollama/ollama`, MIT | Optional local natural-language synthesis and local-LLM routing. | HTTP adapter with retrieval-only fallback. |
| SQLite / Python sqlite3 | SQLite public domain; Python PSF license | Simple local transactions for personal thesis history and dated disclosure snapshots. | Small parameterized SQL repository; no cloud dependency. |
| pdfplumber | `jsvine/pdfplumber`, MIT | OGE PDF text and table extraction. | Range-preserving validation, source-page provenance, rejection of unreliable text layers; no library modifications. |

## ThesisLens source adapters

SEC 13F XML is read using the existing lxml dependency. Official reporting semantics are preserved: dollars for filings from January 3, 2023 and thousands before then, shares/principal and put/call kept distinct. Original filings are normalized; amendments are not merged. Share-change classification is application business logic, not a copied algorithm.

Official ARKK CSV holdings are a separate daily fund adapter. OGE PDF disclosures use a separate range-preserving model and never produce inferred exact portfolio weights. Exact issuer-name ticker matches use the official SEC directory; optional sector metadata comes from Yahoo Finance and displays coverage.

## Consumer app dependencies

| Component / source | License | Why chosen | Modifications |
| --- | --- | --- | --- |
| Next.js (`vercel/next.js`) 16.3.6 / React (`facebook/react`) 19.3.0 | MIT | Maintained App Router, server-rendered shell and interactive UI | App-specific routes and same-origin FastAPI proxy; no framework changes |
| TypeScript (`microsoft/TypeScript`) | Apache-2.0 | Strict frontend compilation | Project configuration only |
| Tailwind CSS (`tailwindlabs/tailwindcss`) v4 | MIT | CSS-first tokens and responsive layout | ThesisLens theme and small semantic CSS; no library changes |
| shadcn/ui (`shadcn-ui/ui`), Radix UI (`radix-ui/primitives`) | MIT | Established accessible primitives | Installed Button/Badge/Skeleton/Tooltip via official CLI; generated `cn` imports corrected to local utility, Button transition narrowed to colors |
| TanStack Query (`TanStack/query`) | MIT | Cache, retries, invalidation and background queries | Provider defaults and feature-specific query keys |
| Zod (`colinhacks/zod`) v4 | MIT | Runtime API response validation | Product schemas only |
| Lucide (`lucide-icons/lucide`) | ISC | Small consistent interface icons | No icon changes |
| clsx / tailwind-merge / class-variance-authority | MIT / MIT / Apache-2.0 | Maintained class composition used by shadcn | Local `cn` wrapper; no library changes |
| FastAPI (`fastapi/fastapi`) / Pydantic (`pydantic/pydantic`) | MIT | Python HTTP boundary and validated contracts | Thin adapters to existing services |
| Uvicorn (`encode/uvicorn`) / HTTPX (`encode/httpx`) | BSD-3-Clause | Local ASGI server and API testing | No library changes |
| Playwright (`microsoft/playwright`) | Apache-2.0 | Production desktop/mobile browser verification | Product journeys and screenshots; no library changes |
| Vitest (`vitest-dev/vitest`) / Prettier (`prettier/prettier`) | MIT | Boundary unit tests and consistent formatting | Tests/config only |

SEC Form 4 and Schedule 13D/G use lxml and official EDGAR documents, not an LLM parser. Form 4 preserves nested values, transaction codes, roles, dates and footnotes. Modern Schedule XML fields were checked against an actual SEC filing; legacy HTML retains source links and unknown fields. No investment motives are inferred. Existing financial calculations and mature retrieval implementations remain unchanged.

## Reference projects

FinRobot, ai-hedge-fund, agentii-investment-intelligence, and agentic-financial-rag were treated as conceptual references only. No source code was copied or adapted from those repositories in this milestone.
