"""Simple overlapping character chunks, cutting at paragraph boundaries when possible."""

from src.parser import section_at


def chunk_filing(text: str, ticker: str, year: int, form: str,
                 chunk_size: int = 1200, overlap: int = 180,
                 company: str = "", filing_date: str = "",
                 source_url: str = "") -> list[dict]:
    if chunk_size <= overlap or overlap < 0:
        raise ValueError("chunk_size must be greater than nonnegative overlap")
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        if end < len(text):
            boundary = text.rfind("\n", start + chunk_size // 2, end)
            if boundary > start:
                end = boundary
        excerpt = text[start:end].strip()
        if excerpt:
            chunks.append({
                "chunk_id": f"{ticker}-{year}-{form}-{len(chunks):05d}",
                "ticker": ticker,
                "year": year,
                "form": form,
                "section": section_at(text, form, start),
                "text": excerpt,
                "company": company,
                "filing_date": filing_date,
                "source_url": source_url,
                "chunk_ordinal": len(chunks),
                "start_char": start,
                "end_char": end,
            })
        if end == len(text):
            break
        start = max(start + 1, end - overlap)
    return chunks
