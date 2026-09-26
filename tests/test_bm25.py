from src.bm25 import BM25Retriever


def test_bm25_returns_lexical_matches_with_raw_score_and_rank():
    chunks = [
        {"chunk_id": "a", "text": "deferred revenue increased", "section": "Item 8"},
        {"chunk_id": "b", "text": "cybersecurity risk oversight", "section": "Item 1A"},
    ]
    retriever = BM25Retriever(chunks)

    results = retriever.search("deferred revenue", top_k=1)

    assert results[0]["chunk_id"] == "a"
    assert results[0]["backend"] == "bm25"
    assert results[0]["backend_rank"] == 1
    assert results[0]["score"] > 0
