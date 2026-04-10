"""BHt MCP Tools — Search tools (bht_list_books, bht_field_info, bht_search).

Routing logic for bht_search:
- Location-only filters (buch, kapitel, vers) → tokens table, 0 BHt requests
- Morphological filters (wa, stamm, Wurzel, ...) → flex_search API → search_cache
- kapitel and vers are NEVER sent to flex_search (not valid search fields);
  they are always applied as local post-filters.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any

from bht_mcp.cache import CacheManager
from bht_mcp.fetcher import BhtUnavailable, DailyLimitExceeded, Fetcher
from bht_mcp.models import (
    BOOKS_DATA,
    DEFAULT_SEARCH_LIMIT,
    MAX_SEARCH_LIMIT,
    VALID_FIELDS,
    BookInfo,
    ErrorCode,
    ErrorInfo,
    ToolResponse,
    validate_book,
    validate_field,
)

# kapitel and vers appear in flex_search responses but are NOT valid search fields.
# They are applied as local post-filters on results.
_POST_FILTER_FIELDS = frozenset({"kapitel", "vers"})

# buch is a search field but also triggers the tokens-table path
# when it's the ONLY search field present.
_LOCATION_FIELDS = frozenset({"buch", "kapitel", "vers"})


# ---------------------------------------------------------------------------
# Tool 1: bht_list_books
# ---------------------------------------------------------------------------


async def bht_list_books(cache: CacheManager) -> ToolResponse:
    """List all 47 books with abbreviation codes and chapter counts.

    Source: Tier 0 (static constants). BHt requests: 0.
    """
    books = [
        _book_to_dict(b) for b in BOOKS_DATA.values()
    ]
    quota = await cache.get_quota()
    return ToolResponse(data=books, quota=quota)


def _book_to_dict(b: BookInfo) -> dict[str, Any]:
    d: dict[str, Any] = {"code": b.code, "name": b.name, "chapters": b.chapters}
    if b.chapter_list is not None:
        d["chapter_list"] = list(b.chapter_list)
    return d


# ---------------------------------------------------------------------------
# Tool 2: bht_field_info
# ---------------------------------------------------------------------------


async def bht_field_info(
    cache: CacheManager, fetcher: Fetcher, field: str
) -> ToolResponse:
    """Get valid values for a BHt search field.

    Source: field_values_cache → autocomplete API on cache miss.
    BHt requests: 0 (cached) or 1 (cache miss).
    """
    quota = await cache.get_quota()

    # Validate field name
    try:
        info = validate_field(field)
    except ValueError as e:
        return ToolResponse(
            data=None,
            quota=quota,
            error=ErrorInfo(
                code=ErrorCode.INVALID_FIELD,
                message=str(e),
                suggestion="Valid fields: " + ", ".join(sorted(VALID_FIELDS.keys())),
            ),
        )

    # Check cache
    values = await cache.get_field_values(field)
    if values is not None:
        return ToolResponse(
            data={"field": field, "description": info.description, "values": values},
            quota=quota,
        )

    # Cache miss — fetch from autocomplete API
    try:
        values = await fetcher.autocomplete(field)
    except BhtUnavailable as e:
        return ToolResponse(data=None, quota=await cache.get_quota(), error=e.error_info)

    # Cache and return
    if values:
        await cache.set_field_values(field, values)

    quota = await cache.get_quota()
    return ToolResponse(
        data={"field": field, "description": info.description, "values": values},
        quota=quota,
    )


# ---------------------------------------------------------------------------
# Tool 3: bht_search
# ---------------------------------------------------------------------------


async def bht_search(
    cache: CacheManager,
    fetcher: Fetcher,
    filters: list[dict[str, str]],
    limit: int = DEFAULT_SEARCH_LIMIT,
) -> ToolResponse:
    """Search BHt database for Hebrew Bible tokens matching filters.

    Routing:
    - Location-only (buch [+kapitel] [+vers]) → tokens table (0 BHt requests)
    - Morphological filters → flex_search API → search_cache (0-1 BHt requests)

    BHt requests: 0 (cached) or 1 (cache miss).
    """
    limit = max(1, min(limit, MAX_SEARCH_LIMIT))
    quota = await cache.get_quota()

    # Validate filters
    if not filters:
        return ToolResponse(
            data=None,
            quota=quota,
            error=ErrorInfo(
                code=ErrorCode.INVALID_FIELD,
                message="At least one filter is required.",
                suggestion="Example: [{field: 'buch', value: 'Gen'}]",
            ),
        )

    # Validate field names and book codes
    for f in filters:
        field_name = f.get("field", "")
        if field_name not in VALID_FIELDS and field_name not in _POST_FILTER_FIELDS:
            return ToolResponse(
                data=None,
                quota=quota,
                error=ErrorInfo(
                    code=ErrorCode.INVALID_FIELD,
                    message=f"Unknown field: '{field_name}'",
                    suggestion="Valid fields: " + ", ".join(sorted(VALID_FIELDS.keys())),
                ),
            )
        if field_name == "buch":
            try:
                validate_book(f["value"])
            except ValueError as e:
                return ToolResponse(
                    data=None,
                    quota=quota,
                    error=ErrorInfo(
                        code=ErrorCode.INVALID_BOOK,
                        message=str(e),
                        suggestion="Use bht_list_books to see all valid book codes.",
                    ),
                )

    # Classify filters
    search_fields = {f["field"]: f["value"] for f in filters if f["field"] not in _POST_FILTER_FIELDS}
    post_filters = {f["field"]: f["value"] for f in filters if f["field"] in _POST_FILTER_FIELDS}
    is_location_only = all(f in _LOCATION_FIELDS for f in search_fields)

    # Route
    try:
        if is_location_only and "buch" in search_fields:
            rows = await _search_via_tokens_table(
                cache, fetcher, search_fields, post_filters
            )
        else:
            rows = await _search_via_flex_search(
                cache, fetcher, filters, post_filters
            )
    except BhtUnavailable as e:
        return ToolResponse(data=None, quota=await cache.get_quota(), error=e.error_info)

    # Apply limit and truncation before cached flag check —
    # no need to query beleg_cache for rows that will be discarded.
    total = len(rows)
    truncated = total > limit
    rows = rows[:limit]

    # Add cached flag (only on the returned rows)
    if rows:
        buch_groups: dict[str, list[dict]] = {}
        for row in rows:
            buch_groups.setdefault(row["buch"], []).append(row)
        for buch, group in buch_groups.items():
            beleg_nrs = [r["beleg_nr"] for r in group]
            cached_set = await cache.is_beleg_cached_bulk(buch, beleg_nrs)
            for r in group:
                r["cached"] = r["beleg_nr"] in cached_set

    quota = await cache.get_quota()
    resp = ToolResponse(data=rows, quota=quota, truncated=truncated)
    if truncated:
        resp.total_available = total
    return resp


# ---------------------------------------------------------------------------
# Search paths
# ---------------------------------------------------------------------------


async def ensure_book_tokens(cache: CacheManager, fetcher: Fetcher, buch: str) -> None:
    """Ensure all tokens for a book are in the tokens table.

    If not cached, fetches via flex_search API (1 JSON request, no daily limit).
    Called from search, detail, and syntax modules.
    """
    if await cache.has_book_tokens(buch):
        return
    raw = await fetcher.flex_search([{"field": "buch", "value": buch}])
    rows = [_normalize_api_row(r) for r in raw]
    await cache.set_book_tokens(buch, rows)


async def _search_via_tokens_table(
    cache: CacheManager,
    fetcher: Fetcher,
    search_fields: dict[str, str],
    post_filters: dict[str, str],
) -> list[dict[str, Any]]:
    """Location-only search: tokens table with local filtering."""
    buch = search_fields["buch"]
    await ensure_book_tokens(cache, fetcher, buch)

    # Query tokens table with location filters
    kapitel = _int_or_none(post_filters.get("kapitel"))
    vers = _int_or_none(post_filters.get("vers"))
    return await cache.get_tokens(buch, kapitel=kapitel, vers=vers)


async def _search_via_flex_search(
    cache: CacheManager,
    fetcher: Fetcher,
    filters: list[dict[str, str]],
    post_filters: dict[str, str],
) -> list[dict[str, Any]]:
    """Morphological search: flex_search API with query cache."""
    # Only send valid search fields to the API (exclude kapitel, vers)
    api_filters = [f for f in filters if f["field"] not in _POST_FILTER_FIELDS]

    query_hash, query_desc = CacheManager.compute_query_hash(api_filters)

    # Check search cache
    cached = await cache.get_search_cache(query_hash)
    if cached is not None:
        result_json, _ = cached
        rows = json.loads(result_json)
    else:
        # Cache miss — call flex_search API
        raw = await fetcher.flex_search(api_filters)
        rows = [_normalize_api_row(r) for r in raw]
        # Cache the result
        await cache.set_search_cache(
            query_hash, query_desc, json.dumps(rows), len(rows)
        )

    # Apply post-filters (kapitel, vers)
    if post_filters:
        rows = _apply_post_filters(rows, post_filters)

    return rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _normalize_api_row(raw: dict[str, Any]) -> dict[str, Any]:
    """Convert flex_search API response row to our internal schema.

    API uses camelCase (belegNr), we use snake_case (beleg_nr).
    API returns strings for numeric fields; we convert to int.
    """
    return {
        "buch": raw.get("buch", ""),
        "beleg_nr": int(raw.get("belegNr", 0)),
        "token": raw.get("token", "").strip(),
        "kapitel": int(raw.get("kapitel", 0)),
        "text": raw.get("text", "").strip(),
        "vers": int(raw.get("vers", 0)),
        "satz": raw.get("satz", ""),
        "bezug": raw.get("bezug", ""),
        "frag": int(raw.get("frag", 0)),
        "pos": int(raw.get("pos", 0)),
    }


def _apply_post_filters(
    rows: list[dict[str, Any]], post_filters: dict[str, str]
) -> list[dict[str, Any]]:
    """Filter rows by kapitel/vers (local post-filter)."""
    result = rows
    if "kapitel" in post_filters:
        kap = int(post_filters["kapitel"])
        result = [r for r in result if r.get("kapitel") == kap]
    if "vers" in post_filters:
        v = int(post_filters["vers"])
        result = [r for r in result if r.get("vers") == v]
    return result


def _int_or_none(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None
