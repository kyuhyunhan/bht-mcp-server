"""BHt MCP Server — MCP server with tool registration.

Entry point for `bht-mcp` CLI command and `python -m bht_mcp`.
Uses stdio transport for MCP client integration.

All 7 tools registered.
"""

from __future__ import annotations

import json
import logging
import sys
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# MCP stdio servers must never write to stdout. Configure logging to stderr.
logging.basicConfig(
    level=logging.INFO,
    stream=sys.stderr,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("bht-mcp")

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
    logger.info("Starting bht-mcp server (cache: %s)", _DEFAULT_CACHE_DIR)
    cache = CacheManager(_DEFAULT_CACHE_DIR)
    await cache.initialize()
    fetcher = Fetcher(cache)
    await fetcher.initialize()
    logger.info("Server ready — 7 tools available")
    try:
        yield AppState(cache=cache, fetcher=fetcher)
    finally:
        await fetcher.close()
        await cache.close()
        logger.info("Server shut down")


def _get_state(ctx: Context) -> AppState:
    return ctx.request_context.lifespan_context


# ---------------------------------------------------------------------------
# MCP Server
# ---------------------------------------------------------------------------

mcp = FastMCP(
    "bht",
    instructions=(
        "BHt (Biblia Hebraica transcripta) MCP server. "
        "Access the Hebrew Bible linguistic database from LMU Munich.\n\n"
        "Book codes: Gen=Genesis, Ex=Exodus, Lev=Leviticus, Num=Numeri, "
        "Dt=Deuteronomium, Jos=Josua, Ri=Richter, 1Sam, 2Sam, "
        "1Koen=1 Kings, 2Koen=2 Kings, Jes=Isaiah, Jer=Jeremiah, "
        "Ez=Ezekiel, Hos, Joel, Am=Amos, Ob=Obadiah, Jon=Jonah, "
        "Mich=Micah, Nah, Hab=Habakkuk, Zef=Zephaniah, Hag=Haggai, "
        "Sach=Zechariah, Mal=Malachi, Ps=Psalms, Ij=Job, Spr=Proverbs, "
        "Rut=Ruth, Hl=Song of Songs, Koh=Ecclesiastes, Klgl=Lamentations, "
        "Est=Esther, Dan=Daniel, Esr=Ezra, Neh=Nehemiah, 1Chr, 2Chr, "
        "ASir-TSir=Sirach fragments.\n\n"
        "You can use either codes (Gen) or full names (Genesis) in all tools.\n\n"
        "Recommended workflow:\n"
        "1. bht_search to find tokens (returns beleg_nr for each)\n"
        "2. bht_token_detail with beleg_nr from search results\n"
        "3. bht_syntax_tree / bht_sentence_analysis for syntax\n\n"
        "IMPORTANT: Always call bht_search first before bht_token_detail. "
        "Use beleg_nr (not pos) to identify tokens — pos resets per sentence "
        "and can be ambiguous."
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
        "Call this FIRST before bht_token_detail — it returns beleg_nr "
        "values needed to identify each token for detailed analysis.\n\n"
        "Returns text-level results (token text, location, sentence context) "
        "with a 'cached' flag and beleg_nr for each token.\n\n"
        "Multiple filters are combined with AND.\n\n"
        "Pass filters as a dict: {buch: 'Gen', kapitel: '1', vers: '1'}\n\n"
        "Common filter combinations:\n"
        "- {buch: 'Gen', kapitel: '1', vers: '1'} → Genesis 1:1\n"
        "- {buch: 'Gen', wa: '11 VERB', stamm: 'G'} → all Qal verbs in Genesis\n"
        "- {Wurzel: 'BRʾ'} → all tokens with root BRʾ (create)\n"
        "- {buch: 'Ps', wa: '12 SUBSTANTIV'} → all nouns in Psalms\n\n"
        "Book names (Genesis, Exodus, ...) are accepted as well as codes (Gen, Ex, ...)."
    ),
)
async def search(
    filters: dict[str, str],
    ctx: Context,
    limit: int = 100,
) -> str:
    """Search for Hebrew Bible tokens matching filters.

    Args:
        filters: Filter dict. Keys are field names, values are filter values. Combined with AND.
        limit: Maximum results to return (default 100, max 1000).
    """
    state = _get_state(ctx)
    filter_list = [{"field": k, "value": str(v)} for k, v in filters.items()]
    resp = await _bht_search(state.cache, state.fetcher, filter_list, limit)
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
        "Always call bht_search first to get the token list, then use "
        "beleg_nr from search results to identify the token.\n\n"
        "Example: bht_search({buch:'Gen',kapitel:'1',vers:'1'}) returns "
        "tokens with beleg_nr=1..11, then call bht_token_detail(buch='Gen', "
        "beleg_nr=3) for detailed morphology."
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
        "Only requires book, chapter, and verse. If satz is omitted, returns "
        "trees for ALL sentences in the verse. Internal parameters (bm_nr, "
        "s_nr) are resolved automatically."
    ),
)
async def syntax_tree(
    buch: str,
    kapitel: int,
    vers: int,
    ctx: Context,
    satz: str | None = None,
) -> str:
    """Get the syntactic tree for a verse or sentence.

    Args:
        buch: Book code or name (e.g. 'Gen' or 'Genesis').
        kapitel: Chapter number.
        vers: Verse number.
        satz: Sentence label ('P', 'PR', 'a', 'b'). Optional — omit to get all sentences.
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
        "word-level syntax tree.\n\n"
        "If satz is omitted, returns analysis for ALL sentences in the verse."
    ),
)
async def sentence_analysis(
    buch: str,
    kapitel: int,
    vers: int,
    ctx: Context,
    satz: str | None = None,
) -> str:
    """Get sentence-level syntactic analysis for a verse or sentence.

    Args:
        buch: Book code or name (e.g. 'Gen' or 'Genesis').
        kapitel: Chapter number.
        vers: Verse number.
        satz: Sentence label ('P', 'PR', 'a', 'b'). Optional — omit to get all sentences.
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
