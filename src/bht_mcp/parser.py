"""BHt MCP Server — HTML parsers for beleg and other BHt pages.

Parsing strategy (from PLAN.md §5.5):
- Label-text based, NOT row-index based (resilient to row reordering).
- Each beleg page has a single <table border="0"> with 23 rows.
- Complex rows contain <b>SubField:</b> value patterns extracted generically.
- Navigation links (tree, satzfugungsebene) provide bm_nr and s_nr.

HIGH RISK module: if BHt changes its HTML structure, this will break.
All parse functions return dicts matching beleg_cache column names.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import parse_qs, urlparse

from bs4 import BeautifulSoup, NavigableString, Tag


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def parse_beleg(html: str) -> dict[str, Any]:
    """Parse a beleg HTML page into a flat dict matching beleg_cache columns.

    Raises ValueError if the expected table structure is not found.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", attrs={"border": "0"})
    if table is None:
        raise ValueError("No beleg data table found (expected <table border='0'>)")

    # Build label → value-cell mapping (label-based, not index-based)
    label_cells: dict[str, Tag] = {}
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        label = cells[0].get_text(strip=True).rstrip(":")
        if label and label != "\xa0":
            label_cells[label] = cells[1]

    result: dict[str, Any] = {}

    _parse_buch(label_cells, result)
    _parse_stellenangabe(label_cells, result)
    _parse_token(label_cells, result)
    _parse_simple(label_cells, "Person/Status", "person", result)
    _parse_simple(label_cells, "Genus", "genus", result)
    _parse_simple(label_cells, "Numerus", "numerus", result)
    _parse_simple(label_cells, "Stamm", "stamm", result)
    _parse_wortart(label_cells, result)
    _parse_simple(label_cells, "Kernseme", "kernseme", result)
    _parse_funktionen(label_cells, result)
    _parse_bautyp(label_cells, result)
    _parse_endung(label_cells, result)
    _parse_basis(label_cells, result)
    _parse_wurzel(label_cells, result)
    _parse_lexem(label_cells, result)
    _parse_simple(label_cells, "Sprache", "sprache", result)
    _parse_navigation(soup, result)

    return result


# ---------------------------------------------------------------------------
# Row parsers
# ---------------------------------------------------------------------------

# Stellenangabe pattern: "Gen 1,1PR.0 (1)"
# Groups: buch, kapitel, vers, satz, frag, pos
_STELLEN_RE = re.compile(
    r"^(\S+)\s+(\d+),(\d+)([^.]*?)\.(\d+)\s+\((\d+)\)$"
)


def _parse_buch(cells: dict[str, Tag], out: dict[str, Any]) -> None:
    cell = cells.get("Buch")
    if cell is None:
        return
    subfields = _extract_subfields(cell)
    b_nr_str = subfields.get("b_nr", "")
    out["beleg_nr"] = int(b_nr_str) if b_nr_str.isdigit() else 0
    # buch is extracted from Stellenangabe (more reliable), but set fallback
    text = cell.get_text(strip=True)
    buch_match = re.match(r"^(\S+)", text)
    if buch_match:
        out.setdefault("buch", buch_match.group(1))


def _parse_stellenangabe(cells: dict[str, Tag], out: dict[str, Any]) -> None:
    cell = cells.get("Stellenangabe")
    if cell is None:
        return
    text = cell.get_text(strip=True)
    m = _STELLEN_RE.match(text)
    if m:
        out["buch"] = m.group(1)
        out["kapitel"] = int(m.group(2))
        out["vers"] = int(m.group(3))
        out["satz"] = m.group(4) or ""
        out["frag"] = int(m.group(5))
        out["pos"] = int(m.group(6))
    else:
        raise ValueError(f"Cannot parse Stellenangabe: {text!r}")


def _parse_token(cells: dict[str, Tag], out: dict[str, Any]) -> None:
    cell = cells.get("Token")
    if cell is None:
        return
    # Token text is in the first <i> tag
    italic = cell.find("i")
    out["token"] = italic.get_text(strip=True) if italic else ""
    # Betacode is after <b>Betacode:</b>
    subfields = _extract_subfields(cell)
    out["betacode"] = subfields.get("Betacode", "")


def _parse_simple(
    cells: dict[str, Tag], label: str, column: str, out: dict[str, Any]
) -> None:
    """Parse a row with a single text value."""
    cell = cells.get(label)
    if cell is None:
        out[column] = ""
        return
    out[column] = cell.get_text(strip=True)


def _parse_wortart(cells: dict[str, Tag], out: dict[str, Any]) -> None:
    cell = cells.get("Wortart")
    if cell is None:
        return
    subfields = _extract_subfields(cell)
    out["wa_code"] = subfields.get("wa_code", "")
    out["wa"] = subfields.get("wa", "")
    out["wa2"] = subfields.get("wa2", "")
    out["wa3"] = subfields.get("wa3", "")
    # Full description = text before the first <b> sub-field tag
    out["wortart_full"] = _extract_preamble(cell)


def _parse_funktionen(cells: dict[str, Tag], out: dict[str, Any]) -> None:
    cell = cells.get("Funktionen")
    if cell is None:
        return
    subfields = _extract_subfields(cell)
    out["funktionen"] = _extract_preamble(cell)
    out["wa_fun"] = subfields.get("waFun", "")
    out["ps_fun"] = subfields.get("psFun", "")
    out["gen_fun"] = subfields.get("genFun", "")
    out["num_fun"] = subfields.get("numFun", "")
    out["sem_fun"] = subfields.get("semFun", "")


def _parse_bautyp(cells: dict[str, Tag], out: dict[str, Any]) -> None:
    cell = cells.get("Bautyp")
    if cell is None:
        return
    subfields = _extract_subfields(cell)
    out["bautyp"] = _extract_preamble(cell)
    out["bau_fun"] = subfields.get("BauFun", "")
    out["bau_el"] = subfields.get("BauEl", "")
    out["bau_el_fun"] = subfields.get("BauElFun", "")
    out["bau_opp"] = subfields.get("BauOpp", "")
    out["bau_var"] = subfields.get("BauVar", "")
    out["bau_ab"] = subfields.get("BauAb", "")
    out["alt"] = subfields.get("Alt", "")


def _parse_endung(cells: dict[str, Tag], out: dict[str, Any]) -> None:
    cell = cells.get("Endung")
    if cell is None:
        return
    subfields = _extract_subfields(cell)
    out["endung"] = _extract_preamble(cell)
    out["erweiterung"] = subfields.get("Erweiterung", "")
    out["endung_fun"] = subfields.get("Funktion", "")


def _parse_basis(cells: dict[str, Tag], out: dict[str, Any]) -> None:
    cell = cells.get("Basis")
    if cell is None:
        return
    subfields = _extract_subfields(cell)
    out["bas_el"] = subfields.get("BasEl", "")
    out["bas_var"] = subfields.get("BasVar", "")
    out["bas_ab"] = subfields.get("BasAb", "")

    # Basis text: first <i> tag content + any text before bracket
    # Basis betacode: content inside [ ... ]
    # Basis homonym: number between first <i> and bracket (if present)
    text_parts, betacode = _extract_italic_and_bracket(cell)
    out["basis"] = text_parts
    out["basis_beta"] = betacode
    out["bas_hom"] = _extract_homonym(cell)


def _parse_wurzel(cells: dict[str, Tag], out: dict[str, Any]) -> None:
    cell = cells.get("Wurzel")
    if cell is None:
        return
    italic = cell.find("i")
    if italic:
        out["wurzel"] = italic.get_text(strip=True)
    else:
        out["wurzel"] = ""
    # Betacode from [ ... ]
    bracket = _extract_bracket_content(cell)
    out["wurzel_beta"] = bracket


def _parse_lexem(cells: dict[str, Tag], out: dict[str, Any]) -> None:
    cell = cells.get("Lexem")
    if cell is None:
        return
    text_parts, betacode = _extract_italic_and_bracket(cell)
    out["lexem"] = text_parts
    out["lexem_beta"] = betacode
    out["lex_hom"] = _extract_homonym(cell)


def _parse_navigation(soup: BeautifulSoup, out: dict[str, Any]) -> None:
    """Extract bm_nr and s_nr from tree or satzfugungsebene links."""
    out["bm_nr"] = None
    out["s_nr"] = None

    for a_tag in soup.find_all("a", href=True):
        href = a_tag["href"]
        if "tree" in href or "satzfugungsebene" in href:
            params = parse_qs(urlparse(href).query)
            if "bm_nr" in params:
                out["bm_nr"] = int(params["bm_nr"][0])
            if "s_nr" in params:
                out["s_nr"] = int(params["s_nr"][0])
            break  # first matching link is sufficient


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def _extract_subfields(cell: Tag) -> dict[str, str]:
    """Extract <b>Key:</b> value pairs from a cell.

    Walks siblings after each <b> tag to collect the value text until
    the next <b> tag or structural boundary.
    """
    result: dict[str, str] = {}
    for b_tag in cell.find_all("b"):
        key_text = b_tag.get_text(strip=True)
        if not key_text.endswith(":"):
            continue
        key = key_text[:-1].strip()
        # Collect text nodes after this <b> until next <b> or end
        value_parts: list[str] = []
        for sibling in b_tag.next_siblings:
            if isinstance(sibling, Tag) and sibling.name == "b":
                break
            if isinstance(sibling, NavigableString):
                value_parts.append(str(sibling))
            elif isinstance(sibling, Tag):
                # Stop at structural tags like <b>, but include <i> text
                if sibling.name == "i":
                    value_parts.append(sibling.get_text())
                else:
                    break
        value = "".join(value_parts).strip().strip("\xa0")
        result[key] = value
    return result


def _extract_preamble(cell: Tag) -> str:
    """Extract text content before the first <b> sub-field tag.

    For rows like Wortart, Funktionen, Bautyp, Endung — the main value
    appears before the labeled sub-fields.
    """
    parts: list[str] = []
    for child in cell.children:
        if isinstance(child, Tag) and child.name == "b":
            # Stop at first <b> — that's where sub-fields begin
            break
        if isinstance(child, NavigableString):
            parts.append(str(child))
        elif isinstance(child, Tag):
            parts.append(child.get_text())
    return " ".join("".join(parts).split()).strip()


def _extract_bracket_content(cell: Tag) -> str:
    """Extract content inside the first [ ... ] in a cell's text."""
    text = cell.get_text()
    m = re.search(r"\[\s*(.*?)\s*\]", text)
    if m:
        return " ".join(m.group(1).split())  # normalize whitespace
    return ""


def _extract_italic_and_bracket(cell: Tag) -> tuple[str, str]:
    """Extract combined italic text + trailing content, and bracket betacode.

    Used for Basis and Lexem rows where the pattern is:
      <i>text</i> suffix [ betacode suffix ]
      <i>text</i> hom [ betacode hom ]

    Returns (full_text, betacode) where full_text combines italic + suffix.
    """
    # Get all text before the first <b> sub-field and before [ ... ]
    text_parts: list[str] = []
    hit_bracket = False
    for child in cell.children:
        if isinstance(child, Tag):
            if child.name == "b":
                break  # sub-fields start
            child_text = child.get_text()
            if "[" in child_text:
                # Only take text before [
                before = child_text.split("[")[0]
                text_parts.append(before)
                hit_bracket = True
                break
            text_parts.append(child_text)
        elif isinstance(child, NavigableString):
            s = str(child)
            if "[" in s:
                text_parts.append(s.split("[")[0])
                hit_bracket = True
                break
            text_parts.append(s)

    full_text = " ".join("".join(text_parts).split()).strip()
    betacode = _extract_bracket_content(cell)
    return full_text, betacode


def _extract_homonym(cell: Tag) -> str:
    """Extract homonym number from Basis/Lexem rows.

    Homonym is a standalone integer appearing after the first <i> tag
    and before the bracket content. e.g. '<i>brʾ</i> 1 [ ... ]'
    Returns the number string, or empty string if not found.
    """
    italic = cell.find("i")
    if italic is None:
        return ""

    # Walk siblings after first <i> looking for a standalone integer
    for sibling in italic.next_siblings:
        if isinstance(sibling, Tag):
            if sibling.name == "i":
                continue  # skip empty second <i>
            break  # hit <b> or other tag
        if isinstance(sibling, NavigableString):
            text = str(sibling).strip().strip("\xa0")
            if not text:
                continue
            # Check if it starts with an integer (homonym)
            m = re.match(r"^(\d+)", text)
            if m:
                return m.group(1)
            # If text starts with non-digit (like "l+"), no homonym
            if text and not text[0].isdigit():
                return ""
    return ""
