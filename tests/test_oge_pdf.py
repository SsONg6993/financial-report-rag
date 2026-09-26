from src.public_disclosures import parse_oge_pdf


class Page:
    def __init__(self, text, rows):
        self.text = text
        self.rows = rows

    def extract_text(self):
        return self.text

    def extract_tables(self):
        return [self.rows]


class Pdf:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def test_pdf_parser_preserves_verified_range_and_date(monkeypatch):
    page = Page("OGE Form 278-T\nFiler Name Donald Trump\nSubmitted 05/08/2026",
                [["1", "Example bond", "Purchase", "03/27/2026", "Yes", "$100,001 - $250,000"]])
    monkeypatch.setattr("pdfplumber.open", lambda stream: Pdf([page]))
    result = parse_oge_pdf(b"PDF test bytes", "https://www.oge.gov/trump-05.08.2026.pdf")
    assert result["filing_date"] == "2026-05-08"
    assert result["records"][0]["amount_range"] == "$100,001 - $250,000"
    assert result["records"][0]["transaction_date"] == "03/27/2026"


def test_noisy_pdf_rows_are_not_presented_as_verified_transactions(monkeypatch):
    page = Page("OGE Form 278-T\nDonald Trump", [
        ["1", "Broken text", "", "3/212028", "Yes", "$1 .000.001"],
        ["2", "Future date", "Purchase", "03/27/2028", "Yes", "$100,001 - $250,000"],
    ])
    monkeypatch.setattr("pdfplumber.open", lambda stream: Pdf([page]))
    result = parse_oge_pdf(b"PDF test bytes", "https://www.oge.gov/trump-05.08.2026.pdf")
    assert result["records"] == []
    assert result["rejected_rows"] == 2
    assert result["filing_date"] == ""
    assert result["excerpts"][0]["source_url"].endswith("#page=1")


def test_annual_oge_preserves_source_excerpts_without_inventing_weights(monkeypatch):
    page = Page("OGE Form 278e\nDonald Trump\nAssets and Income\nExample property $1,000,001 - $5,000,000", [])
    monkeypatch.setattr("pdfplumber.open", lambda stream: Pdf([page]))
    result = parse_oge_pdf(b"PDF test bytes", "https://www.oge.gov/annual.pdf")
    assert "Annual" in result["disclosure_type"]
    assert result["records"] == []
    assert "$1,000,001" in result["excerpts"][0]["text"]
