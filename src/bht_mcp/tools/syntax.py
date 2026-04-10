"""BHt MCP Tools — bht_syntax_tree and bht_sentence_analysis.

Both tools require resolving internal parameters (bm_nr, s_nr) from
a token in the target sentence. Resolution path:
  1. Find a token matching (buch, kapitel, vers, satz) in tokens table
  2. Check beleg_cache for that token → get bm_nr, s_nr
  3. If not cached, fetch beleg HTML → parse → cache → get bm_nr, s_nr
  4. Use bm_nr, s_nr to fetch tree/sentence page
"""

from __future__ import annotations

import json
import re
from typing import Any

from bs4 import BeautifulSoup

from bht_mcp.cache import CacheManager
from bht_mcp.fetcher import BhtUnavailable, DailyLimitExceeded, Fetcher
from bht_mcp.tools.search import ensure_book_tokens as _ensure_book_tokens
from bht_mcp.models import (
    ErrorCode,
    ErrorInfo,
    ToolResponse,
    validate_book,
)
from bht_mcp.parser import parse_beleg


# ---------------------------------------------------------------------------
# Tool 5: bht_syntax_tree
# ---------------------------------------------------------------------------


async def bht_syntax_tree(
    cache: CacheManager,
    fetcher: Fetcher,
    buch: str,
    kapitel: int,
    vers: int,
    satz: str,
) -> ToolResponse:
    """Get the syntactic tree (Wortfügungsebene) for a sentence."""
    quota = await cache.get_quota()

    try:
        validate_book(buch)
    except ValueError as e:
        return ToolResponse(
            data=None, quota=quota,
            error=ErrorInfo(code=ErrorCode.INVALID_BOOK, message=str(e),
                            suggestion="Use bht_list_books to see all valid book codes."),
        )

    # Resolve bm_nr, s_nr, b_nr — tree requires bm_nr > 0
    try:
        nav = await _resolve_navigation(
            cache, fetcher, buch, kapitel, vers, satz, require_tree=True
        )
    except _ResolutionError as e:
        return ToolResponse(data=None, quota=await cache.get_quota(), error=e.error_info)
    except (DailyLimitExceeded, BhtUnavailable) as e:
        return ToolResponse(data=None, quota=await cache.get_quota(), error=e.error_info)

    bm_nr, s_nr, b_nr = nav["bm_nr"], nav["s_nr"], nav["b_nr"]

    # Check tree cache
    cached_json = await cache.get_tree(buch, kapitel, vers, satz, s_nr)
    if cached_json is not None:
        return ToolResponse(data=json.loads(cached_json), quota=await cache.get_quota())

    # Fetch tree HTML
    try:
        html = await fetcher.fetch_tree_html(
            buch, kapitel, b_nr, bm_nr, vers, satz, s_nr
        )
    except DailyLimitExceeded as e:
        return ToolResponse(data=None, quota=await cache.get_quota(), error=e.error_info)
    except BhtUnavailable as e:
        return ToolResponse(data=None, quota=await cache.get_quota(), error=e.error_info)

    # Parse inline JSON from tree page
    tree_data = _parse_tree_json(html)
    if tree_data is None:
        return ToolResponse(
            data=None, quota=await cache.get_quota(),
            error=ErrorInfo(
                code=ErrorCode.PARSE_ERROR,
                message="Could not extract syntax tree from page.",
                suggestion="BHt website structure may have changed.",
            ),
        )

    # Cache and return
    tree_json = json.dumps(tree_data, ensure_ascii=False)
    await cache.set_tree(buch, kapitel, vers, satz, s_nr, bm_nr, b_nr, tree_json)
    return ToolResponse(data=tree_data, quota=await cache.get_quota())


# ---------------------------------------------------------------------------
# Tool 6: bht_sentence_analysis
# ---------------------------------------------------------------------------


async def bht_sentence_analysis(
    cache: CacheManager,
    fetcher: Fetcher,
    buch: str,
    kapitel: int,
    vers: int,
    satz: str,
) -> ToolResponse:
    """Get sentence-level syntactic analysis (Satzfügungsebene)."""
    quota = await cache.get_quota()

    try:
        validate_book(buch)
    except ValueError as e:
        return ToolResponse(
            data=None, quota=quota,
            error=ErrorInfo(code=ErrorCode.INVALID_BOOK, message=str(e),
                            suggestion="Use bht_list_books to see all valid book codes."),
        )

    # Resolve navigation params
    try:
        nav = await _resolve_navigation(cache, fetcher, buch, kapitel, vers, satz)
    except _ResolutionError as e:
        return ToolResponse(data=None, quota=await cache.get_quota(), error=e.error_info)
    except (DailyLimitExceeded, BhtUnavailable) as e:
        return ToolResponse(data=None, quota=await cache.get_quota(), error=e.error_info)

    bm_nr, s_nr, b_nr = nav["bm_nr"], nav["s_nr"], nav["b_nr"]

    # Check sentence cache
    cached_json = await cache.get_sentence(buch, kapitel, vers, satz, s_nr)
    if cached_json is not None:
        return ToolResponse(data=json.loads(cached_json), quota=await cache.get_quota())

    # Fetch sentence HTML
    try:
        html = await fetcher.fetch_sentence_html(
            buch, kapitel, b_nr, bm_nr, vers, satz, s_nr
        )
    except DailyLimitExceeded as e:
        return ToolResponse(data=None, quota=await cache.get_quota(), error=e.error_info)
    except BhtUnavailable as e:
        return ToolResponse(data=None, quota=await cache.get_quota(), error=e.error_info)

    # Parse sentence analysis from HTML table
    analysis = _parse_sentence_html(html)
    if analysis is None:
        return ToolResponse(
            data=None, quota=await cache.get_quota(),
            error=ErrorInfo(
                code=ErrorCode.PARSE_ERROR,
                message="Could not parse sentence analysis page.",
                suggestion="BHt website structure may have changed.",
            ),
        )

    # Cache and return
    analysis_json = json.dumps(analysis, ensure_ascii=False)
    await cache.set_sentence(buch, kapitel, vers, satz, s_nr, bm_nr, analysis_json)
    return ToolResponse(data=analysis, quota=await cache.get_quota())


# ---------------------------------------------------------------------------
# Navigation resolution (shared by both tools)
# ---------------------------------------------------------------------------


class _ResolutionError(Exception):
    def __init__(self, error_info: ErrorInfo) -> None:
        self.error_info = error_info


async def _resolve_navigation(
    cache: CacheManager,
    fetcher: Fetcher,
    buch: str,
    kapitel: int,
    vers: int,
    satz: str,
    require_tree: bool = False,
) -> dict[str, int]:
    """Resolve bm_nr, s_nr, b_nr for a sentence.

    Path: tokens table → find token in sentence → beleg_cache → get navigation.
    May trigger 1-2 BHt requests (book tokens + beleg fetch).

    If require_tree=True, seeks a token with bm_nr > 0 (tree link exists).
    Some tokens (e.g. verbs) have bm_nr=0 and no tree data.
    """
    # Ensure book tokens are cached
    await _ensure_book_tokens(cache, fetcher, buch)

    # Find tokens in this sentence
    tokens = await cache.get_tokens(buch, kapitel=kapitel, vers=vers)
    matching = [t for t in tokens if t.get("satz") == satz]
    if not matching:
        raise _ResolutionError(ErrorInfo(
            code=ErrorCode.INVALID_FIELD,
            message=f"No tokens found for {buch} {kapitel}:{vers} satz='{satz}'.",
            suggestion="Use bht_search to find valid satz labels for this verse.",
        ))

    # Phase 1: Check already-cached belegs first (0 HTTP requests).
    # This avoids fetching belegs just to discover bm_nr=0 when a
    # cached beleg with bm_nr>0 already exists further in the list.
    uncached_targets: list[dict] = []
    for target in matching:
        b_nr = target["beleg_nr"]
        beleg = await cache.get_beleg(buch, b_nr)
        if beleg is not None and beleg.get("bm_nr") is not None:
            if require_tree and beleg["bm_nr"] == 0:
                continue
            return {"bm_nr": beleg["bm_nr"], "s_nr": beleg["s_nr"], "b_nr": b_nr}
        else:
            uncached_targets.append(target)

    # Phase 2: No cached beleg had valid nav params. Fetch uncached ones.
    for target in uncached_targets:
        b_nr = target["beleg_nr"]
        html = await fetcher.fetch_beleg_html(buch, kapitel, b_nr)
        parsed = parse_beleg(html)
        await cache.set_beleg(parsed)

        if parsed.get("bm_nr") is None:
            continue

        if require_tree and parsed["bm_nr"] == 0:
            continue

        return {"bm_nr": parsed["bm_nr"], "s_nr": parsed["s_nr"], "b_nr": b_nr}

    # No suitable token found
    if require_tree:
        raise _ResolutionError(ErrorInfo(
            code=ErrorCode.PARSE_ERROR,
            message=f"No syntax tree available for {buch} {kapitel}:{vers} satz='{satz}'.",
            suggestion="Not all sentences have word-level syntax trees. Use bht_sentence_analysis instead.",
        ))
    raise _ResolutionError(ErrorInfo(
        code=ErrorCode.PARSE_ERROR,
        message=f"Could not extract navigation params for {buch} {kapitel}:{vers} satz='{satz}'.",
        suggestion="This sentence may not have analysis data available.",
    ))


# ---------------------------------------------------------------------------
# HTML parsers
# ---------------------------------------------------------------------------


def _parse_tree_json(html: str) -> dict[str, Any] | None:
    """Extract the inline JSON tree from a tree (Wortfügungsebene) page.

    The tree data is embedded as: var json = {value:"...", children:[...]};
    Keys are unquoted (JS object notation), values are quoted strings.
    """
    m = re.search(r"var json = ({.*?});", html)
    if not m:
        return None
    js_obj = m.group(1)
    # Convert JS object notation to valid JSON (quote keys)
    json_str = re.sub(r"(\w+):", r'"\1":', js_obj)
    try:
        return json.loads(json_str)
    except json.JSONDecodeError:
        return None


def _parse_sentence_html(html: str) -> dict[str, Any] | None:
    """Parse the sentence analysis (Satzfügungsebene) table.

    Returns a flat dict of labeled fields from the table.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", attrs={"border": "0"})
    if table is None:
        return None

    result: dict[str, str] = {}
    for tr in table.find_all("tr"):
        cells = tr.find_all("td")
        if len(cells) < 2:
            continue
        raw_label = cells[0].get_text(strip=True).rstrip(":")
        if not raw_label or raw_label == "\xa0":
            continue
        value = cells[1].get_text(strip=True)
        # Preserve "- " prefix for sub-fields to avoid key collisions
        # e.g. "Syntagmen" (top-level) vs "- Syntagmen" (under Tiefenstruktur)
        label = raw_label.strip()
        if label.startswith("- "):
            label = "tiefen_" + label[2:].strip()
        if label:
            result[label] = value

    return result if result else None
