"""Turn visible SEC filing HTML into readable text and approximate item labels."""

import re
import warnings

from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning


def parse_filing(html: str) -> str:
    # SEC Inline XBRL can look like XML to BeautifulSoup, but its visible markup is HTML.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", XMLParsedAsHTMLWarning)
        soup = BeautifulSoup(html, "lxml")
    for tag in list(soup.find_all(True)):
        if tag.name in {"script", "style", "noscript", "ix:header", "ix:hidden"}:
            tag.decompose()
            continue
        if not isinstance(tag, Tag) or tag.parent is None:
            continue
        style = tag.get("style", "").lower().replace(" ", "")
        if (tag.has_attr("hidden") or tag.get("aria-hidden") == "true"
                or "display:none" in style or "visibility:hidden" in style):
            tag.decompose()

    # Newlines preserve table rows and headings; visible iXBRL fact tags retain their text.
    for tag in soup.find_all(["br", "tr", "p", "div", "h1", "h2", "h3", "h4", "li"]):
        tag.insert_before("\n")
    for tag in soup.find_all(["td", "th"]):
        tag.insert_after(" | ")
    lines = [re.sub(r"\s+", " ", line).strip(" |") for line in soup.get_text(" ").splitlines()]
    return "\n".join(line for line in lines if line)


def section_at(text: str, form: str, position: int) -> str:
    items = "1|1A|7|7A|8" if form == "10-K" else "3|4|5|8|11|17|18"
    pattern = re.compile(rf"\bitem\s+({items})\s*[.:-]?\b", re.IGNORECASE)
    matches = list(pattern.finditer(text, 0, position + 1))
    return f"Item {matches[-1].group(1).upper()}" if matches else "Filing overview"
