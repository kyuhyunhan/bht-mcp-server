"""BHt MCP Tools — bht_token_detail.

Two access patterns:
  Option A: by beleg_nr (direct, from bht_search results)
  Option B: by location (buch, kapitel, vers, pos) → resolve via tokens table

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
    beleg_nr: int | None = None,
    kapitel: int | None = None,
    vers: int | None = None,
    pos: int | None = None,
) -> ToolResponse:
    """Get full morphological analysis of a single Hebrew Bible token.

    Option A: buch + beleg_nr
    Option B: buch + kapitel + vers + pos (resolved via tokens table)
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

    # Resolve beleg_nr
    if beleg_nr is not None:
        # Option A: direct
        resolved_nr = beleg_nr
        resolved_kapitel = kapitel  # may be None, that's ok
    elif kapitel is not None and vers is not None and pos is not None:
        # Option B: resolve via tokens table
        resolved_nr = await _resolve_beleg_nr(
            cache, fetcher, buch, kapitel, vers, pos
        )
        if resolved_nr is None:
            return ToolResponse(
                data=None,
                quota=await cache.get_quota(),
                error=ErrorInfo(
                    code=ErrorCode.INVALID_BOOK,
                    message=(
                        f"No token found at {buch} {kapitel}:{vers} pos={pos}."
                    ),
                    suggestion=(
                        "Use bht_search to find valid positions. "
                        "The 'pos' value comes from search results."
                    ),
                ),
            )
        resolved_kapitel = kapitel
    else:
        return ToolResponse(
            data=None,
            quota=quota,
            error=ErrorInfo(
                code=ErrorCode.INVALID_FIELD,
                message="Provide either beleg_nr or (kapitel + vers + pos).",
                suggestion=(
                    "Option A: bht_token_detail(buch='Gen', beleg_nr=3)\n"
                    "Option B: bht_token_detail(buch='Gen', kapitel=1, vers=1, pos=1)"
                ),
            ),
        )

    # Check beleg cache
    cached = await cache.get_beleg(buch, resolved_nr)
    if cached is not None:
        await cache.log_request(
            endpoint="beleg", params=f"book={buch},b_nr={resolved_nr}", cached=True
        )
        return ToolResponse(data=_format_detail(cached), quota=await cache.get_quota())

    # Cache miss — fetch beleg HTML
    # Need kapitel for the URL; try to get it from tokens table if not provided
    if resolved_kapitel is None:
        resolved_kapitel = await _resolve_kapitel(cache, fetcher, buch, resolved_nr)

    if resolved_kapitel is None:
        return ToolResponse(
            data=None,
            quota=await cache.get_quota(),
            error=ErrorInfo(
                code=ErrorCode.INVALID_FIELD,
                message=f"Cannot determine chapter for beleg_nr={resolved_nr}.",
                suggestion="Provide kapitel parameter or use bht_search first.",
            ),
        )

    try:
        html = await fetcher.fetch_beleg_html(buch, resolved_kapitel, resolved_nr)
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
# Resolution helpers
# ---------------------------------------------------------------------------


async def _resolve_beleg_nr(
    cache: CacheManager,
    fetcher: Fetcher,
    buch: str,
    kapitel: int,
    vers: int,
    pos: int,
) -> int | None:
    """Resolve (buch, kapitel, vers, pos) → beleg_nr via tokens table.

    Ensures book tokens are cached first (may trigger 1 flex_search API call).
    """
    try:
        await _ensure_book_tokens(cache, fetcher, buch)
    except BhtUnavailable:
        return None

    # Query tokens table
    tokens = await cache.get_tokens(buch, kapitel=kapitel, vers=vers)
    for t in tokens:
        if t.get("pos") == pos:
            return t["beleg_nr"]
    return None


async def _resolve_kapitel(
    cache: CacheManager,
    fetcher: Fetcher,
    buch: str,
    beleg_nr: int,
) -> int | None:
    """Look up kapitel for a beleg_nr from the tokens table."""
    await _ensure_book_tokens(cache, fetcher, buch)
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
