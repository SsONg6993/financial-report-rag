from src.chunker import chunk_filing
from src.parser import parse_filing
from src.sec import normalize_ticker


def test_ticker_normalization():
    assert normalize_ticker(" brk.b ") == "BRK.B"


def test_parser_keeps_visible_financial_values():
    html = """<html><body><ix:header><ix:hidden>SECRET</ix:hidden></ix:header>
    <script>BAD</script><div style="display:none">HIDDEN</div>
    <h2>Item 7</h2><p>Revenue <ix:nonfraction>$1,234</ix:nonfraction> (12%).</p>
    <table><tr><td>2025</td><td>$1,234</td></tr></table></body></html>"""
    text = parse_filing(html)
    assert "SECRET" not in text and "BAD" not in text and "HIDDEN" not in text
    assert "Revenue" in text and "$1,234" in text and "12%" in text


def test_chunking_has_overlap_and_metadata():
    text = "Item 7\n" + ("Revenue grew.\n" * 200)
    chunks = chunk_filing(text, "ABC", 2025, "10-K", chunk_size=200, overlap=30)
    assert len(chunks) > 1
    assert all(len(chunk["text"]) <= 200 for chunk in chunks)
    assert chunks[0]["ticker"] == "ABC" and chunks[1]["section"] == "Item 7"


def test_retrieval_returns_top_k(tmp_path):
    from src.retriever import Retriever

    class TinyEmbeddings:
        def embed_documents(self, texts):
            return [[1.0, 0.0] if "revenue" in text else [0.0, 1.0] for text in texts]

        def embed_query(self, query):
            return [1.0, 0.0]

    chunks = [
        {"chunk_id": "1", "ticker": "ABC", "year": 2025, "form": "10-K", "section": "Item 7", "text": "revenue grew"},
        {"chunk_id": "2", "ticker": "ABC", "year": 2025, "form": "10-K", "section": "Item 1", "text": "business overview"},
    ]
    retriever = Retriever(TinyEmbeddings(), tmp_path / "vectors")
    retriever.build_index("test", chunks)
    results = retriever.search("test", "revenue?", top_k=1)
    assert len(results) == 1 and results[0]["chunk_id"] == "1"
