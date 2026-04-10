"""BHt MCP Tools — bht_token_detail.

Retrieves full morphological analysis by beleg_nr from bht_search results.
Always call bht_search first to discover tokens and their beleg_nr values.

Source: beleg_cache (Tier 2). Cache miss triggers 1 HTML fetch + parse.
"""

from __future__ import annotations

from typing import Any

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


async def bht_token_detail(
    cache: CacheManager,
    fetcher: Fetcher,
    buch: str,
    beleg_nr: int,
) -> ToolResponse:
    """Get full morphological analysis of a single Hebrew Bible token.

    beleg_nr comes from bht_search results. Always call bht_search first.
    """
    quota = await cache.get_quota()

    # Validate and normalize book code
    try:
        book_info = validate_book(buch)
        buch = book_info.code
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

    # Check beleg cache
    cached = await cache.get_beleg(buch, beleg_nr)
    if cached is not None:
        await cache.log_request(
            endpoint="beleg", params=f"book={buch},b_nr={beleg_nr}", cached=True
        )
        return ToolResponse(data=_format_detail(cached), quota=await cache.get_quota())

    # Cache miss — need kapitel for the beleg URL
    kapitel = await _resolve_kapitel(cache, fetcher, buch, beleg_nr)
    if kapitel is None:
        return ToolResponse(
            data=None,
            quota=await cache.get_quota(),
            error=ErrorInfo(
                code=ErrorCode.INVALID_FIELD,
                message=f"beleg_nr={beleg_nr} not found in {buch}.",
                suggestion="Use bht_search to get valid beleg_nr values.",
            ),
        )

    try:
        html = await fetcher.fetch_beleg_html(buch, kapitel, beleg_nr)
    except DailyLimitExceeded as e:
        return ToolResponse(data=None, quota=await cache.get_quota(), error=e.error_info)
    except BhtUnavailable as e:
        return ToolResponse(data=None, quota=await cache.get_quota(), error=e.error_info)

    # Parse HTML
    try:
        parsed = parse_beleg(html)
    except ValueError as e:
        return ToolResponse(
            data=None,
            quota=await cache.get_quota(),
            error=ErrorInfo(
                code=ErrorCode.PARSE_ERROR,
                message=str(e),
                suggestion="BHt website structure may have changed. Cached data is still available.",
            ),
        )

    # Store in cache
    await cache.set_beleg(parsed)

    return ToolResponse(data=_format_detail(parsed), quota=await cache.get_quota())


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _resolve_kapitel(
    cache: CacheManager,
    fetcher: Fetcher,
    buch: str,
    beleg_nr: int,
) -> int | None:
    """Look up kapitel for a beleg_nr from the tokens table."""
    try:
        await _ensure_book_tokens(cache, fetcher, buch)
    except BhtUnavailable:
        return None
    token = await cache.get_token_by_beleg_nr(buch, beleg_nr)
    return token.get("kapitel") if token else None


# ---------------------------------------------------------------------------
# Output formatting
# ---------------------------------------------------------------------------


def _format_detail(row: dict[str, Any]) -> dict[str, Any]:
    """Format a beleg_cache row into the Tool 4 nested response structure."""
    return {
        "location": {
            "buch": row.get("buch", ""),
            "kapitel": row.get("kapitel"),
            "vers": row.get("vers"),
            "satz": row.get("satz", ""),
            "pos": row.get("pos"),
            "beleg_nr": row.get("beleg_nr"),
        },
        "token": {
            "text": row.get("token", ""),
            "betacode": row.get("betacode", ""),
        },
        "morphology": {
            "person": row.get("person", ""),
            "genus": row.get("genus", ""),
            "numerus": row.get("numerus", ""),
            "stamm": row.get("stamm", ""),
        },
        "wortart": {
            "full": row.get("wortart_full", ""),
            "wa_code": row.get("wa_code", ""),
            "wa": row.get("wa", ""),
            "wa2": row.get("wa2", ""),
            "wa3": row.get("wa3", ""),
        },
        "kernseme": row.get("kernseme", ""),
        "funktionen": {
            "code": row.get("funktionen", ""),
            "wa_fun": row.get("wa_fun", ""),
            "ps_fun": row.get("ps_fun", ""),
            "gen_fun": row.get("gen_fun", ""),
            "num_fun": row.get("num_fun", ""),
            "sem_fun": row.get("sem_fun", ""),
        },
        "bautyp": {
            "type": row.get("bautyp", ""),
            "bau_fun": row.get("bau_fun", ""),
            "bau_el": row.get("bau_el", ""),
            "bau_el_fun": row.get("bau_el_fun", ""),
            "bau_opp": row.get("bau_opp", ""),
            "bau_var": row.get("bau_var", ""),
            "bau_ab": row.get("bau_ab", ""),
            "alt": row.get("alt", ""),
        },
        "endung": {
            "value": row.get("endung", ""),
            "erweiterung": row.get("erweiterung", ""),
            "funktion": row.get("endung_fun", ""),
        },
        "basis": {
            "text": row.get("basis", ""),
            "betacode": row.get("basis_beta", ""),
            "homonym": row.get("bas_hom", ""),
            "bas_el": row.get("bas_el", ""),
            "bas_var": row.get("bas_var", ""),
            "bas_ab": row.get("bas_ab", ""),
        },
        "wurzel": {
            "text": row.get("wurzel", ""),
            "betacode": row.get("wurzel_beta", ""),
        },
        "lexem": {
            "text": row.get("lexem", ""),
            "betacode": row.get("lexem_beta", ""),
            "homonym": row.get("lex_hom", ""),
        },
        "sprache": row.get("sprache", ""),
        "navigation": {
            "bm_nr": row.get("bm_nr"),
            "s_nr": row.get("s_nr"),
        },
    }
