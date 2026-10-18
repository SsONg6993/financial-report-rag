from src.public_disclosures import parse_oge_pdf


class Page:
    def __init__(self, text, rows):
        self.text = text
        self.rows = rows

    def extract_text(self):
        return self.text

    def extract_tables(self, **_kwargs):
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
    assert result["records"][0]["transaction_date"] == "2026-03-27"
    assert result["extraction"]["status"] == "verified"
    assert result["extraction"]["candidate_count"] == 1


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
    assert result["extraction"]["rejection_reasons"] == {
        "future_transaction_date": 1,
        "unrecognized_transaction_type": 1,
    }


def test_annual_oge_preserves_source_excerpts_without_inventing_weights(monkeypatch):
    page = Page("OGE Form 278e\nDonald Trump\nAssets and Income\nExample property $1,000,001 - $5,000,000", [])
    monkeypatch.setattr("pdfplumber.open", lambda stream: Pdf([page]))
    result = parse_oge_pdf(b"PDF test bytes", "https://www.oge.gov/annual.pdf")
    assert "Annual" in result["disclosure_type"]
    assert result["records"] == []
    assert "$1,000,001" in result["excerpts"][0]["text"]
    assert result["extraction"]["status"] == "source_only"


def test_ptr_reconstructs_multiline_and_cross_page_rows(monkeypatch):
    first = Page(
        "OGE Form 278-T\nFiler Name\nExample Official",
        [["1", "Example", "Pur-", "03/27/2026", "Yes", "$15,001 -"]],
    )
    second = Page(
        "OGE Form 278-T continued",
        [
            ["", "Bond", "chase", "", "", "$50,000"],
            ["No.", "Description", "Type", "Date", "Notification", "Amount"],
            ["2", "Second asset", "Sale", "03/28/2026", "No", "$1,001 - $15,000"],
        ],
    )
    monkeypatch.setattr("pdfplumber.open", lambda stream: Pdf([first, second]))

    result = parse_oge_pdf(
        b"PDF test bytes", "https://www.oge.gov/example-05.08.2026-278t.pdf"
    )

    assert len(result["records"]) == 2
    assert result["records"][0]["asset_name"] == "Example Bond"
    assert result["records"][0]["transaction_type"] == "Purchase"
    assert result["records"][0]["amount_range"] == "$15,001 - $50,000"
    assert result["records"][0]["page"] == 1
    assert result["extraction"]["raw_fragment_count"] == 4


def test_ptr_tracks_missing_dates_and_repeated_headers_without_false_rows(monkeypatch):
    page = Page(
        "OGE Form 278-T\nDonald J Trump",
        [
            ["No.", "Description", "Type", "Date", "Notification", "Amount"],
            ["1", "Missing date asset", "Purchase", "", "Yes", "$1,001 - $15,000"],
            ["No.", "Description", "Type", "Date", "Notification", "Amount"],
            ["2", "Range asset", "Sale", "03/28/2026", "Yes", "$15,001 - $50,000"],
        ],
    )
    monkeypatch.setattr("pdfplumber.open", lambda stream: Pdf([page]))

    result = parse_oge_pdf(
        b"PDF test bytes", "https://www.oge.gov/trump-05.08.2026-278t.pdf"
    )

    assert [record["row_number"] for record in result["records"]] == ["2"]
    assert result["extraction"]["candidate_count"] == 2
    assert result["extraction"]["rejection_reasons"] == {
        "invalid_transaction_date": 1
    }


def test_ptr_normalizes_only_known_oge_amount_bands(monkeypatch):
    page = Page(
        "OGE Form 278-T\nDonald J Trump",
        [
            ["1", "OCR asset l", "ourchaso", "3/27/2026", "Yoa", "S1 001 • S15 000"],
            ["2", "Unknown range", "Sale", "3/27/2026", "Yes", "$2,000 - $9,000"],
        ],
    )
    monkeypatch.setattr("pdfplumber.open", lambda stream: Pdf([page]))

    result = parse_oge_pdf(
        b"PDF test bytes", "https://www.oge.gov/trump-05.08.2026-278t.pdf"
    )

    assert result["records"][0]["amount_range"] == "$1,001 - $15,000"
    assert result["records"][0]["transaction_type"] == "Purchase"
    assert result["extraction"]["rejection_reasons"] == {
        "invalid_amount_range": 1
    }


def test_ptr_deduplicates_repeated_table_extraction(monkeypatch):
    row = [
        "1",
        "Example security",
        "Purchase",
        "03/27/2026",
        "Yes",
        "$1,001 - $15,000",
    ]
    page = Page("OGE Form 278-T\nDonald J Trump", [row])
    page.extract_tables = lambda **_kwargs: [[row], [row]]
    monkeypatch.setattr("pdfplumber.open", lambda stream: Pdf([page]))

    result = parse_oge_pdf(
        b"PDF test bytes", "https://www.oge.gov/trump-05.08.2026-278t.pdf"
    )

    assert len(result["records"]) == 1
    assert result["extraction"]["candidate_count"] == 2
    assert result["extraction"]["deduplicated_count"] == 1


def test_malformed_text_layer_is_review_required_not_a_false_empty_report(monkeypatch):
    page = Page("", [])
    page.extract_text = lambda: (_ for _ in ()).throw(ValueError("broken text map"))
    monkeypatch.setattr("pdfplumber.open", lambda stream: Pdf([page]))

    result = parse_oge_pdf(
        b"PDF test bytes", "https://www.oge.gov/example-05.08.2026-278t.pdf"
    )

    assert result["records"] == []
    assert result["extraction"]["status"] == "review_required"
    assert result["extraction"]["text_layer_status"] == "unusable"
    assert result["extraction"]["ocr_used"] is False
    assert result["extraction"]["ocr_reason"] == "local_ocr_unavailable"
