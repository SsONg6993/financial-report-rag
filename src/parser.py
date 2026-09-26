"""Turn visible SEC filing HTML into readable text and approximate item labels."""

import re
import warnings

from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning


def clean_text(text: str) -> str:
    """Normalize whitespace inside extracted text."""
    return re.sub(r"\s+", " ", text).strip()


def table_to_text(table: Tag) -> str:
    """
    Convert one HTML table into row-based plain text.

    Example:
    <tr>
        <td>Total net sales</td>
        <td>416,161</td>
        <td>391,035</td>
    </tr>

    becomes:

    Total net sales | 416,161 | 391,035
    """
    rows = []

    for row in table.find_all("tr"):
        cells = []

        for cell in row.find_all(["td", "th"], recursive=False):
            cell_text = clean_text(cell.get_text(" ", strip=True))

            if cell_text:
                cells.append(cell_text)

        if cells:
            rows.append(" | ".join(cells))

    return "\n".join(rows)


def parse_filing(html: str) -> str:
    """
    Convert SEC filing HTML into cleaner plain text while preserving
    basic table row/column structure.
    """

    # SEC Inline XBRL may look like XML, but we want the visible HTML.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(html, "lxml")

    # ---------------------------------------------------------
    # 1. Remove hidden / irrelevant content
    # ---------------------------------------------------------
    for tag in list(soup.find_all(True)):
        if tag.name in {
            "script",
            "style",
            "noscript",
            "ix:header",
            "ix:hidden",
        }:
            tag.decompose()
            continue

        if not isinstance(tag, Tag) or tag.parent is None:
            continue

        style = tag.get("style", "").lower().replace(" ", "")

        if (
            tag.has_attr("hidden")
            or tag.get("aria-hidden") == "true"
            or "display:none" in style
            or "visibility:hidden" in style
        ):
            tag.decompose()

    # ---------------------------------------------------------
    # 2. Extract tables separately
    # ---------------------------------------------------------
    #
    # Instead of flattening all <td>/<th> tags directly into the
    # full document, we convert each table into structured text.
    #
    # After converting a table, we replace the original table
    # with its cleaned text representation.
    # ---------------------------------------------------------
    for table in soup.find_all("table"):
        table_text = table_to_text(table)

        if table_text:
            table.replace_with(f"\n{table_text}\n")
        else:
            table.decompose()

    # ---------------------------------------------------------
    # 3. Preserve paragraph / heading boundaries
    # ---------------------------------------------------------
    for tag in soup.find_all(
        ["br", "p", "div", "h1", "h2", "h3", "h4", "li"]
    ):
        tag.insert_before("\n")

    # ---------------------------------------------------------
    # 4. Convert remaining HTML into plain text
    # ---------------------------------------------------------
    raw_text = soup.get_text(" ")

    lines = []

    for line in raw_text.splitlines():
        cleaned = clean_text(line)

        if cleaned:
            lines.append(cleaned)

    return "\n".join(lines)


def section_at(text: str, form: str, position: int) -> str:
    """
    Return the most recent SEC Item heading appearing before
    a given character position.
    """

    items = "1|1A|7|7A|8" if form == "10-K" else "3|4|5|8|11|17|18"

    pattern = re.compile(
        rf"\bitem\s+({items})\s*[.:-]?\b",
        re.IGNORECASE,
    )

    matches = list(pattern.finditer(text, 0, position + 1))

    if matches:
        return f"Item {matches[-1].group(1).upper()}"

    return "Filing overview"