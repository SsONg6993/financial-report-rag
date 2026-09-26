# Financial Investment Intelligence Dashboard — Implementation Plan

1. Preserve and regression-test the existing SEC parser changes; improve practical table serialization and chunk metadata.
2. Add configuration, typed data models, SEC Company Facts normalization, resilient market-data access, and deterministic analytics/valuation functions.
3. Extend retrieval with BM25, rank-based RRF hybrid search, optional local reranking, source-aware hits, and an evaluation runner.
4. Add lightweight query routing, grounded Ollama prompts/fallbacks, risk comparison, bull/bear evidence, and Markdown report assembly.
5. Replace the single-purpose Streamlit screen with the ten-tab research dashboard while retaining retrieval-only operation.
6. Update dependencies, environment examples, third-party documentation, README, and bundled evaluation examples.
7. Rebuild the Python 3.12 virtual environment, run focused red/green tests and the complete suite, smoke-test Streamlit, and exercise an AAPL SEC workflow where network access permits.

Implementation remains local-first, calculation-first, modular without unnecessary abstraction, and preserves the user’s uncommitted `src/parser.py` work.
