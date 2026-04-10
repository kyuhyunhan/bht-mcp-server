"""BHt MCP Server — MCP server with tool registration.

Entry point for `bht-mcp` CLI command and `python -m bht_mcp`.
Uses stdio transport for MCP client integration.

All 7 tools registered.
"""

from __future__ import annotations

import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import Context, FastMCP

from bht_mcp.cache import CacheManager
from bht_mcp.fetcher import Fetcher
from bht_mcp.tools.annotations import bht_text_annotations as _bht_text_annotations
from bht_mcp.tools.detail import bht_token_detail as _bht_token_detail
from bht_mcp.tools.search import (
    bht_field_info as _bht_field_info,
    bht_list_books as _bht_list_books,
    bht_search as _bht_search,
)
from bht_mcp.tools.syntax import (
    bht_sentence_analysis as _bht_sentence_analysis,
    bht_syntax_tree as _bht_syntax_tree,
)

# Default cache location
_DEFAULT_CACHE_DIR = Path.home() / ".bht"


# ---------------------------------------------------------------------------
# Shared state — initialized in lifespan, accessed by tools via Context
# ---------------------------------------------------------------------------


@dataclass
class AppState:
    cache: CacheManager
    fetcher: Fetcher


@asynccontextmanager
async def lifespan(server: FastMCP):
    """Initialize cache and HTTP client; clean up on shutdown."""
    cache = CacheManager(_DEFAULT_CACHE_DIR)
    await cache.initialize()
    fetcher = Fetcher(cache)
    await fetcher.initialize()
    try:
        yield AppState(cache=cache, fetcher=fetcher)
    finally:
        await fetcher.close()
        await cache.close()


def _get_state(ctx: Context) -> AppState:
    return ctx.request_context.lifespan_context


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "bht",
    instructions=(
        "BHt (Biblia Hebraica transcripta) MCP server. "
        "Access the Hebrew Bible linguistic database from LMU Munich. "
        "Start with bht_list_books to see available books, "
        "bht_field_info to discover search field values, "
        "then bht_search to find tokens."
    ),
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Tool 1: bht_list_books
# ---------------------------------------------------------------------------


@mcp.tool(
    name="bht_list_books",
    description=(
        "List all books in the BHt Hebrew Bible database with their "
        "abbreviation codes and chapter counts. Use this to discover valid book "
        "codes before searching. Examples: Gen=Genesis(50ch), Ex=Exodus(40ch), "
        "Ps=Psalmen(150ch), Jes=Jesaja(66ch). Also includes Sirach fragments "
        "(ASir, BSir, etc.)."
    ),
)
async def list_books(ctx: Context) -> str:
    state = _get_state(ctx)
    resp = await _bht_list_books(state.cache)
    return json.dumps(resp.to_dict(), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tool 2: bht_field_info
# ---------------------------------------------------------------------------


@mcp.tool(
    name="bht_field_info",
    description=(
        "Get valid values for a BHt search field. Use this to discover "
        "what filter values are available before searching. Common fields:\n"
        "- wa: part of speech (e.g. '11 VERB', '12 SUBSTANTIV', '31 PRAEPOSITION')\n"
        "- stamm: verbal stem ('G'=Qal, 'D'=Piel, 'H'=Hiphil, 'N'=Niphal)\n"
        "- ps: person ('1','2','3','0'=n/a)\n"
        "- gen: gender ('M','F','0'=n/a)\n"
        "- num: number ('S'=singular,'P'=plural,'D'=dual,'0'=n/a)\n"
        "- Wurzel: root (e.g. 'BRʾ', 'ʾMR', 'HLK')\n"
        "- lexem: lexeme"
    ),
)
async def field_info(field: str, ctx: Context) -> str:
    """Get valid values for a search field.

    Args:
        field: One of the 42 search field names (e.g. 'wa', 'stamm', 'Wurzel').
    """
    state = _get_state(ctx)
    resp = await _bht_field_info(state.cache, state.fetcher, field)
    return json.dumps(resp.to_dict(), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tool 3: bht_search
# ---------------------------------------------------------------------------


@mcp.tool(
    name="bht_search",
    description=(
        "Search the BHt database for Hebrew Bible tokens matching filters. "
        "Returns text-level results (token text, location, sentence context) "
        "with a 'cached' flag indicating whether morphological detail is "
        "already available locally. Use bht_token_detail for morphological "
        "analysis of specific tokens.\n\n"
        "Multiple filters are combined with AND.\n\n"
        "Common filter combinations:\n"
        "- {buch: 'Gen', kapitel: '1', vers: '1'} → Genesis 1:1\n"
        "- {wa: '11 VERB', stamm: 'G'} → all Qal verbs in entire Bible\n"
        "- {Wurzel: 'BRʾ'} → all tokens with root BRʾ (create)\n"
        "- {buch: 'Ps', wa: '12 SUBSTANTIV'} → all nouns in Psalms\n\n"
        "Book codes: Gen,Ex,Lev,Num,Dt,Jos,Ri,1Sam,2Sam,1Koen,2Koen,"
        "Jes,Jer,Ez,Hos,Joel,Am,Ob,Jon,Mich,Nah,Hab,Zef,Hag,Sach,Mal,"
        "Ps,Ij,Spr,Rut,Hl,Koh,Klgl,Est,Dan,Esr,Neh,1Chr,2Chr"
    ),
)
async def search(
    filters: list[dict[str, str]],
    ctx: Context,
    limit: int = 100,
) -> str:
    """Search for Hebrew Bible tokens matching filters.

    Args:
        filters: List of {field, value} filter objects. Combined with AND.
        limit: Maximum results to return (default 100, max 1000).
    """
    state = _get_state(ctx)
    resp = await _bht_search(state.cache, state.fetcher, filters, limit)
    return json.dumps(resp.to_dict(), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tool 4: bht_token_detail
# ---------------------------------------------------------------------------


@mcp.tool(
    name="bht_token_detail",
    description=(
        "Get full morphological analysis of a single Hebrew Bible token "
        "from BHt. Returns person, gender, number, verbal stem, part of "
        "speech, root, lexeme, construction type, and more.\n\n"
        "Two ways to identify a token:\n"
        "  Option A: by beleg_nr (from bht_search results)\n"
        "  Option B: by location (buch, kapitel, vers, pos)\n\n"
        "Use bht_search to explore, then this tool for detailed analysis."
    ),
)
async def token_detail(
    buch: str,
    ctx: Context,
    beleg_nr: int | None = None,
    kapitel: int | None = None,
    vers: int | None = None,
    pos: int | None = None,
) -> str:
    """Get full morphological analysis of a single token.

    Args:
        buch: Book code (e.g. 'Gen'). Required.
        beleg_nr: Token ID from bht_search results (Option A).
        kapitel: Chapter number (Option B).
        vers: Verse number (Option B).
        pos: Position within verse, 1-based (Option B).
    """
    state = _get_state(ctx)
    resp = await _bht_token_detail(
        state.cache, state.fetcher, buch,
        beleg_nr=beleg_nr, kapitel=kapitel, vers=vers, pos=pos,
    )
    return json.dumps(resp.to_dict(), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tool 5: bht_syntax_tree
# ---------------------------------------------------------------------------


@mcp.tool(
    name="bht_syntax_tree",
    description=(
        "Get the syntactic tree (Wortfügungsebene) for a sentence in the "
        "Hebrew Bible. Returns a JSON tree with nodes like PV (predicate "
        "phrase), NV (nominal phrase), SUB (substantive), etc.\n\n"
        "Only requires book, chapter, verse, and sentence label. Internal "
        "parameters (bm_nr, s_nr) are resolved automatically."
    ),
)
async def syntax_tree(
    buch: str,
    kapitel: int,
    vers: int,
    satz: str,
    ctx: Context,
) -> str:
    """Get the syntactic tree for a sentence.

    Args:
        buch: Book code (e.g. 'Gen').
        kapitel: Chapter number.
        vers: Verse number.
        satz: Sentence label ('P', 'PR', 'a', 'b', etc.).
    """
    state = _get_state(ctx)
    resp = await _bht_syntax_tree(
        state.cache, state.fetcher, buch, kapitel, vers, satz
    )
    return json.dumps(resp.to_dict(), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tool 6: bht_sentence_analysis
# ---------------------------------------------------------------------------


@mcp.tool(
    name="bht_sentence_analysis",
    description=(
        "Get sentence-level syntactic analysis (Satzfügungsebene) for a "
        "sentence in the Hebrew Bible. Returns sentence type, deep structure, "
        "syntagms, relations, and clause elements. Higher-level than the "
        "word-level syntax tree."
    ),
)
async def sentence_analysis(
    buch: str,
    kapitel: int,
    vers: int,
    satz: str,
    ctx: Context,
) -> str:
    """Get sentence-level syntactic analysis.

    Args:
        buch: Book code (e.g. 'Gen').
        kapitel: Chapter number.
        vers: Verse number.
        satz: Sentence label ('P', 'PR', 'a', 'b', etc.).
    """
    state = _get_state(ctx)
    resp = await _bht_sentence_analysis(
        state.cache, state.fetcher, buch, kapitel, vers, satz
    )
    return json.dumps(resp.to_dict(), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Tool 7: bht_text_annotations
# ---------------------------------------------------------------------------


@mcp.tool(
    name="bht_text_annotations",
    description=(
        "Get textual criticism annotations for a chapter. Returns manuscript "
        "variants, text security notes (TS), and critical apparatus. Data "
        "includes references to manuscripts (G=Greek, MT=Masoretic Text).\n\n"
        "Efficient: retrieves all annotations for a chapter in one request."
    ),
)
async def text_annotations(
    buch: str,
    kapitel: int,
    ctx: Context,
) -> str:
    """Get textual criticism annotations for a chapter.

    Args:
        buch: Book code (e.g. 'Gen').
        kapitel: Chapter number.
    """
    state = _get_state(ctx)
    resp = await _bht_text_annotations(
        state.cache, state.fetcher, buch, kapitel
    )
    return json.dumps(resp.to_dict(), ensure_ascii=False)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the BHt MCP server on stdio transport."""
    mcp.run(transport="stdio")
