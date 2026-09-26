from src.chunker import chunk_filing
from src.parser import parse_filing, table_to_text
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


def test_table_parser_collapses_spacer_cells_and_preserves_colspan():
    from bs4 import BeautifulSoup

    html = """<table>
      <tr><th colspan="2">Products and Services</th><th>2025</th><th>2024</th></tr>
      <tr><td>Total net sales</td><td></td><td><ix:nonfraction>416,161</ix:nonfraction></td><td>391,035</td></tr>
    </table>"""
    table = BeautifulSoup(html, "lxml").find("table")

    assert table_to_text(table).splitlines() == [
        "Products and Services | 2025 | 2024",
        "Total net sales | 416,161 | 391,035",
    ]


def test_chunking_has_overlap_and_metadata():
    text = "Item 7\n" + ("Revenue grew.\n" * 200)
    chunks = chunk_filing(text, "ABC", 2025, "10-K", chunk_size=200, overlap=30)
    assert len(chunks) > 1
    assert all(len(chunk["text"]) <= 200 for chunk in chunks)
    assert chunks[0]["ticker"] == "ABC" and chunks[1]["section"] == "Item 7"
    assert chunks[0]["start_char"] == 0
    assert chunks[0]["source_url"] == ""


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


def test_collection_name_is_versioned_for_chunk_schema():
    from src.retriever import collection_name

    filing = {"ticker": "AAPL", "accession_number": "0000320193-25-000079"}
    assert collection_name(filing, "model").startswith("filing_v2_")
