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

## Reference projects

FinRobot, ai-hedge-fund, agentii-investment-intelligence, and agentic-financial-rag were treated as conceptual references only. No source code was copied or adapted from those repositories in this milestone.
