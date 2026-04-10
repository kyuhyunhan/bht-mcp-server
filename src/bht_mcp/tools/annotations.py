"""BHt MCP Tools — bht_text_annotations.

Returns textual criticism annotations for a chapter.
Source: text_anm HTML → text_anm_cache.
BHt requests: 0 (cached) or 1 (cache miss).
"""

from __future__ import annotations

import json
from typing import Any

from bs4 import BeautifulSoup

from bht_mcp.cache import CacheManager
from bht_mcp.fetcher import BhtUnavailable, DailyLimitExceeded, Fetcher
from bht_mcp.models import (
    ErrorCode,
    ErrorInfo,
    ToolResponse,
    validate_book,
)


async def bht_text_annotations(
    cache: CacheManager,
    fetcher: Fetcher,
    buch: str,
    kapitel: int,
) -> ToolResponse:
    """Get textual criticism annotations for a chapter."""
    quota = await cache.get_quota()

    try:
        validate_book(buch)
    except ValueError as e:
        return ToolResponse(
            data=None, quota=quota,
            error=ErrorInfo(code=ErrorCode.INVALID_BOOK, message=str(e),
                            suggestion="Use bht_list_books to see all valid book codes."),
        )

    # Check cache
    cached_json = await cache.get_text_anm(buch, kapitel)
    if cached_json is not None:
        return ToolResponse(data=json.loads(cached_json), quota=quota)

    # Fetch HTML
    try:
        html = await fetcher.fetch_text_anm_html(buch, kapitel)
    except DailyLimitExceeded as e:
        return ToolResponse(data=None, quota=await cache.get_quota(), error=e.error_info)
    except BhtUnavailable as e:
        return ToolResponse(data=None, quota=await cache.get_quota(), error=e.error_info)

    # Parse annotations
    annotations = _parse_text_anm(html)

    # Cache and return (even if empty — avoids re-fetching chapters with no annotations)
    anm_json = json.dumps(annotations, ensure_ascii=False)
    await cache.set_text_anm(buch, kapitel, anm_json)
    return ToolResponse(data=annotations, quota=await cache.get_quota())


def _parse_text_anm(html: str) -> list[dict[str, str]]:
    """Parse text annotations table.

    Each row has 4 cells: [stellenangabe, token, type, annotation].
    Returns list of annotation dicts.
    """
    soup = BeautifulSoup(html, "html.parser")
    # The annotations table has no border attribute (unlike beleg's border="0")
    # Find the table with 4-column rows containing annotation data
    results: list[dict[str, str]] = []

    for table in soup.find_all("table"):
        for tr in table.find_all("tr"):
            cells = tr.find_all("td")
            if len(cells) != 4:
                continue
            texts = [c.get_text(strip=True) for c in cells]
            # Skip empty rows or header-like rows
            if not texts[0] or not any(texts):
                continue
            results.append({
                "stellenangabe": texts[0],
                "token": texts[1],
                "type": texts[2],
                "annotation": texts[3],
            })

    return results
