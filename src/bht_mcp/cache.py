"""BHt MCP Server — SQLite cache layer.

Manages all 11 cache tables across 4 tiers:
- Tier 0: Reference data (books, wortarten, field_values_cache)
- Tier 1: Token text (tokens, search_cache)
- Tier 2: Beleg morphology (beleg_cache)
- Tier 3: Syntax/sentence/annotations (tree_cache, sentence_cache, text_anm_cache)
- Operations: request_log, request_history

All methods are async (aiosqlite). Cache is stored at ~/.bht/cache.db by default.
"""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import aiosqlite

logger = logging.getLogger("bht-mcp.cache")

from bht_mcp.models import DAILY_HTML_LIMIT, Quota

# ---------------------------------------------------------------------------
# Schema — CREATE TABLE statements (idempotent via IF NOT EXISTS)
# ---------------------------------------------------------------------------

_SCHEMA = """\
-- Tier 0: Reference data

CREATE TABLE IF NOT EXISTS books (
    code        TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    chapters    INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS wortarten (
    code        TEXT PRIMARY KEY,
    name        TEXT,
    abbrev      TEXT,
    parent_code TEXT,
    klasse      INTEGER
);

CREATE TABLE IF NOT EXISTS field_values_cache (
    field       TEXT NOT NULL,
    value       TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (field, value)
);

-- Tier 1: Token text (flex_search results)

CREATE TABLE IF NOT EXISTS tokens (
    buch        TEXT NOT NULL,
    beleg_nr    INTEGER NOT NULL,
    token       TEXT,
    kapitel     INTEGER,
    text        TEXT,
    vers        INTEGER,
    satz        TEXT,
    bezug       TEXT,
    frag        INTEGER,
    pos         INTEGER,
    PRIMARY KEY (buch, beleg_nr)
);

CREATE INDEX IF NOT EXISTS idx_tokens_location
    ON tokens(buch, kapitel, vers);
CREATE INDEX IF NOT EXISTS idx_tokens_pos
    ON tokens(buch, kapitel, vers, pos);

CREATE TABLE IF NOT EXISTS search_cache (
    query_hash  TEXT PRIMARY KEY,
    query_desc  TEXT,
    result_json TEXT NOT NULL,
    result_count INTEGER,
    fetched_at  TEXT NOT NULL
);

-- Tier 2: Beleg morphology (on-demand HTML parsing)

CREATE TABLE IF NOT EXISTS beleg_cache (
    buch        TEXT NOT NULL,
    beleg_nr    INTEGER NOT NULL,

    kapitel     INTEGER,
    vers        INTEGER,
    satz        TEXT,
    frag        INTEGER,
    pos         INTEGER,

    token       TEXT,
    betacode    TEXT,

    person      TEXT,
    genus       TEXT,
    numerus     TEXT,
    stamm       TEXT,

    wortart_full TEXT,
    wa_code     TEXT,
    wa          TEXT,
    wa2         TEXT,
    wa3         TEXT,

    kernseme    TEXT,

    funktionen  TEXT,
    wa_fun      TEXT,
    ps_fun      TEXT,
    gen_fun     TEXT,
    num_fun     TEXT,
    sem_fun     TEXT,

    bautyp      TEXT,
    bau_fun     TEXT,
    bau_el      TEXT,
    bau_el_fun  TEXT,
    bau_opp     TEXT,
    bau_var     TEXT,
    bau_ab      TEXT,
    alt         TEXT,

    endung      TEXT,
    erweiterung TEXT,
    endung_fun  TEXT,

    basis       TEXT,
    basis_beta  TEXT,
    bas_hom     TEXT,
    bas_el      TEXT,
    bas_var     TEXT,
    bas_ab      TEXT,
    wurzel      TEXT,
    wurzel_beta TEXT,
    lexem       TEXT,
    lexem_beta  TEXT,
    lex_hom     TEXT,

    sprache     TEXT,

    bm_nr       INTEGER,
    s_nr        INTEGER,

    fetched_at  TEXT NOT NULL,

    PRIMARY KEY (buch, beleg_nr)
);

CREATE INDEX IF NOT EXISTS idx_beleg_location
    ON beleg_cache(buch, kapitel, vers);
CREATE INDEX IF NOT EXISTS idx_beleg_wa
    ON beleg_cache(wa_code);
CREATE INDEX IF NOT EXISTS idx_beleg_wurzel
    ON beleg_cache(wurzel);
CREATE INDEX IF NOT EXISTS idx_beleg_lexem
    ON beleg_cache(lexem);

-- Tier 3: Syntax / Sentence / Annotations

CREATE TABLE IF NOT EXISTS tree_cache (
    buch        TEXT NOT NULL,
    kapitel     INTEGER NOT NULL,
    vers        INTEGER NOT NULL,
    satz        TEXT NOT NULL,
    s_nr        INTEGER NOT NULL,
    bm_nr       INTEGER NOT NULL,
    b_nr        INTEGER NOT NULL,
    tree_json   TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (buch, kapitel, vers, satz, s_nr)
);

CREATE TABLE IF NOT EXISTS sentence_cache (
    buch        TEXT NOT NULL,
    kapitel     INTEGER NOT NULL,
    vers        INTEGER NOT NULL,
    satz        TEXT NOT NULL,
    s_nr        INTEGER NOT NULL,
    bm_nr       INTEGER NOT NULL,
    analysis_json TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (buch, kapitel, vers, satz, s_nr)
);

CREATE TABLE IF NOT EXISTS text_anm_cache (
    buch        TEXT NOT NULL,
    kapitel     INTEGER NOT NULL,
    annotations_json TEXT NOT NULL,
    fetched_at  TEXT NOT NULL,
    PRIMARY KEY (buch, kapitel)
);

-- Operations: Rate limiting and request tracking

CREATE TABLE IF NOT EXISTS request_log (
    date        TEXT NOT NULL,
    endpoint    TEXT NOT NULL,
    count       INTEGER DEFAULT 0,
    PRIMARY KEY (date, endpoint)
);

CREATE TABLE IF NOT EXISTS request_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    endpoint    TEXT NOT NULL,
    url         TEXT,
    params      TEXT,
    status      INTEGER,
    response_ms INTEGER,
    cached      INTEGER DEFAULT 0,
    error       TEXT
);

CREATE INDEX IF NOT EXISTS idx_history_date
    ON request_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_history_endpoint
    ON request_history(endpoint);
"""

# HTML endpoints that count toward the daily limit
_HTML_ENDPOINTS = frozenset({"beleg", "tree", "satz", "text_anm"})


# ---------------------------------------------------------------------------
# CacheManager
# ---------------------------------------------------------------------------


class CacheManager:
    """Async SQLite cache for all BHt data tiers.

    Usage::

        async with CacheManager(Path("~/.bht")) as cache:
            values = await cache.get_field_values("wa")
    """

    def __init__(self, cache_dir: Path) -> None:
        self._cache_dir = cache_dir
        self._db_path = cache_dir / "cache.db"
        self._db: aiosqlite.Connection | None = None

    # -- Lifecycle -----------------------------------------------------------

    async def initialize(self) -> None:
        """Create cache directory, open DB, ensure schema exists."""
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._db = await aiosqlite.connect(self._db_path)
        self._db.row_factory = aiosqlite.Row
        await self._db.executescript(_SCHEMA)
        await self._db.commit()
        # Clean up old request history (>30 days)
        await self._cleanup_history()
        logger.info("Cache initialized at %s", self._db_path)

    async def close(self) -> None:
        if self._db:
            await self._db.close()
            self._db = None

    async def __aenter__(self) -> CacheManager:
        await self.initialize()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    @property
    def db(self) -> aiosqlite.Connection:
        assert self._db is not None, "CacheManager not initialized"
        return self._db

    # -----------------------------------------------------------------------
    # Tier 0: field_values_cache
    # -----------------------------------------------------------------------

    async def get_field_values(self, field: str) -> list[str] | None:
        """Return cached autocomplete values for a field, or None if not cached."""
        cursor = await self.db.execute(
            "SELECT value FROM field_values_cache WHERE field = ? ORDER BY value",
            (field,),
        )
        rows = await cursor.fetchall()
        if not rows:
            return None
        return [row["value"] for row in rows]

    async def set_field_values(self, field: str, values: list[str]) -> None:
        """Store autocomplete values for a field (replaces existing)."""
        now = _now_iso()
        await self.db.execute(
            "DELETE FROM field_values_cache WHERE field = ?", (field,)
        )
        await self.db.executemany(
            "INSERT INTO field_values_cache (field, value, fetched_at) VALUES (?, ?, ?)",
            [(field, v, now) for v in values],
        )
        await self.db.commit()

    # -----------------------------------------------------------------------
    # Tier 1: tokens
    # -----------------------------------------------------------------------

    async def has_book_tokens(self, buch: str) -> bool:
        """Check if any tokens are cached for a book."""
        cursor = await self.db.execute(
            "SELECT 1 FROM tokens WHERE buch = ? LIMIT 1", (buch,)
        )
        return await cursor.fetchone() is not None

    async def get_tokens(
        self,
        buch: str,
        kapitel: int | None = None,
        vers: int | None = None,
    ) -> list[dict[str, Any]]:
        """Query cached tokens with optional location filters.

        Returns empty list if book is not cached.
        """
        conditions = ["buch = ?"]
        params: list[Any] = [buch]
        if kapitel is not None:
            conditions.append("kapitel = ?")
            params.append(kapitel)
        if vers is not None:
            conditions.append("vers = ?")
            params.append(vers)

        sql = f"SELECT * FROM tokens WHERE {' AND '.join(conditions)} ORDER BY beleg_nr"
        cursor = await self.db.execute(sql, params)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]

    async def set_book_tokens(self, buch: str, rows: list[dict[str, Any]]) -> None:
        """Bulk insert tokens for a book (replaces existing)."""
        await self.db.execute("DELETE FROM tokens WHERE buch = ?", (buch,))
        await self.db.executemany(
            """INSERT INTO tokens
               (buch, beleg_nr, token, kapitel, text, vers, satz, bezug, frag, pos)
               VALUES (:buch, :beleg_nr, :token, :kapitel, :text, :vers, :satz, :bezug, :frag, :pos)""",
            rows,
        )
        await self.db.commit()

    # -----------------------------------------------------------------------
    # Tier 1: search_cache
    # -----------------------------------------------------------------------

    async def get_search_cache(self, query_hash: str) -> tuple[str, int] | None:
        """Return (result_json, result_count) or None."""
        cursor = await self.db.execute(
            "SELECT result_json, result_count FROM search_cache WHERE query_hash = ?",
            (query_hash,),
        )
        row = await cursor.fetchone()
        if row is None:
            return None
        return row["result_json"], row["result_count"]

    async def set_search_cache(
        self,
        query_hash: str,
        query_desc: str,
        result_json: str,
        result_count: int,
    ) -> None:
        await self.db.execute(
            """INSERT OR REPLACE INTO search_cache
               (query_hash, query_desc, result_json, result_count, fetched_at)
               VALUES (?, ?, ?, ?, ?)""",
            (query_hash, query_desc, result_json, result_count, _now_iso()),
        )
        await self.db.commit()

    @staticmethod
    def compute_query_hash(filters: list[dict[str, str]]) -> tuple[str, str]:
        """Compute deterministic hash and description for a filter set.

        Returns (hash, description) tuple.
        Filters are sorted by field name to ensure determinism.
        """
        sorted_filters = sorted(filters, key=lambda f: f["field"])
        desc = ", ".join(f'{f["field"]}={f["value"]}' for f in sorted_filters)
        h = hashlib.sha256(desc.encode()).hexdigest()
        return h, desc

    # -----------------------------------------------------------------------
    # Tier 2: beleg_cache
    # -----------------------------------------------------------------------

    async def get_beleg(self, buch: str, beleg_nr: int) -> dict[str, Any] | None:
        """Return full beleg row as dict, or None."""
        cursor = await self.db.execute(
            "SELECT * FROM beleg_cache WHERE buch = ? AND beleg_nr = ?",
            (buch, beleg_nr),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def is_beleg_cached(self, buch: str, beleg_nr: int) -> bool:
        cursor = await self.db.execute(
            "SELECT 1 FROM beleg_cache WHERE buch = ? AND beleg_nr = ?",
            (buch, beleg_nr),
        )
        return await cursor.fetchone() is not None

    async def is_beleg_cached_bulk(
        self, buch: str, beleg_nrs: list[int]
    ) -> set[int]:
        """Return the subset of beleg_nrs that are cached."""
        if not beleg_nrs:
            return set()
        placeholders = ",".join("?" * len(beleg_nrs))
        cursor = await self.db.execute(
            f"SELECT beleg_nr FROM beleg_cache WHERE buch = ? AND beleg_nr IN ({placeholders})",
            [buch, *beleg_nrs],
        )
        rows = await cursor.fetchall()
        return {row["beleg_nr"] for row in rows}

    async def set_beleg(self, data: dict[str, Any]) -> None:
        """Insert or replace a single beleg row."""
        cols = [
            "buch", "beleg_nr",
            "kapitel", "vers", "satz", "frag", "pos",
            "token", "betacode",
            "person", "genus", "numerus", "stamm",
            "wortart_full", "wa_code", "wa", "wa2", "wa3",
            "kernseme",
            "funktionen", "wa_fun", "ps_fun", "gen_fun", "num_fun", "sem_fun",
            "bautyp", "bau_fun", "bau_el", "bau_el_fun", "bau_opp", "bau_var", "bau_ab", "alt",
            "endung", "erweiterung", "endung_fun",
            "basis", "basis_beta", "bas_hom", "bas_el", "bas_var", "bas_ab",
            "wurzel", "wurzel_beta",
            "lexem", "lexem_beta", "lex_hom",
            "sprache",
            "bm_nr", "s_nr",
            "fetched_at",
        ]
        placeholders = ", ".join(f":{c}" for c in cols)
        col_names = ", ".join(cols)

        # Ensure fetched_at is present
        if "fetched_at" not in data:
            data["fetched_at"] = _now_iso()

        await self.db.execute(
            f"INSERT OR REPLACE INTO beleg_cache ({col_names}) VALUES ({placeholders})",
            data,
        )
        await self.db.commit()

    # -----------------------------------------------------------------------
    # Tier 3: tree_cache
    # -----------------------------------------------------------------------

    async def get_tree(
        self, buch: str, kapitel: int, vers: int, satz: str, s_nr: int
    ) -> str | None:
        """Return tree JSON string or None."""
        cursor = await self.db.execute(
            """SELECT tree_json FROM tree_cache
               WHERE buch = ? AND kapitel = ? AND vers = ? AND satz = ? AND s_nr = ?""",
            (buch, kapitel, vers, satz, s_nr),
        )
        row = await cursor.fetchone()
        return row["tree_json"] if row else None

    async def set_tree(
        self,
        buch: str,
        kapitel: int,
        vers: int,
        satz: str,
        s_nr: int,
        bm_nr: int,
        b_nr: int,
        tree_json: str,
    ) -> None:
        await self.db.execute(
            """INSERT OR REPLACE INTO tree_cache
               (buch, kapitel, vers, satz, s_nr, bm_nr, b_nr, tree_json, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (buch, kapitel, vers, satz, s_nr, bm_nr, b_nr, tree_json, _now_iso()),
        )
        await self.db.commit()

    # -----------------------------------------------------------------------
    # Tier 3: sentence_cache
    # -----------------------------------------------------------------------

    async def get_sentence(
        self, buch: str, kapitel: int, vers: int, satz: str, s_nr: int
    ) -> str | None:
        """Return sentence analysis JSON string or None."""
        cursor = await self.db.execute(
            """SELECT analysis_json FROM sentence_cache
               WHERE buch = ? AND kapitel = ? AND vers = ? AND satz = ? AND s_nr = ?""",
            (buch, kapitel, vers, satz, s_nr),
        )
        row = await cursor.fetchone()
        return row["analysis_json"] if row else None

    async def set_sentence(
        self,
        buch: str,
        kapitel: int,
        vers: int,
        satz: str,
        s_nr: int,
        bm_nr: int,
        analysis_json: str,
    ) -> None:
        await self.db.execute(
            """INSERT OR REPLACE INTO sentence_cache
               (buch, kapitel, vers, satz, s_nr, bm_nr, analysis_json, fetched_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (buch, kapitel, vers, satz, s_nr, bm_nr, analysis_json, _now_iso()),
        )
        await self.db.commit()

    # -----------------------------------------------------------------------
    # Tier 3: text_anm_cache
    # -----------------------------------------------------------------------

    async def get_text_anm(self, buch: str, kapitel: int) -> str | None:
        """Return text annotations JSON string or None."""
        cursor = await self.db.execute(
            "SELECT annotations_json FROM text_anm_cache WHERE buch = ? AND kapitel = ?",
            (buch, kapitel),
        )
        row = await cursor.fetchone()
        return row["annotations_json"] if row else None

    async def set_text_anm(
        self, buch: str, kapitel: int, annotations_json: str
    ) -> None:
        await self.db.execute(
            """INSERT OR REPLACE INTO text_anm_cache
               (buch, kapitel, annotations_json, fetched_at)
               VALUES (?, ?, ?, ?)""",
            (buch, kapitel, annotations_json, _now_iso()),
        )
        await self.db.commit()

    # -----------------------------------------------------------------------
    # Operations: request_log (daily counters)
    # -----------------------------------------------------------------------

    async def get_daily_html_count(self, for_date: date | None = None) -> int:
        """Sum of today's HTML endpoint request counts."""
        d = (for_date or date.today()).isoformat()
        placeholders = ",".join("?" * len(_HTML_ENDPOINTS))
        cursor = await self.db.execute(
            f"""SELECT COALESCE(SUM(count), 0) AS total
                FROM request_log
                WHERE date = ? AND endpoint IN ({placeholders})""",
            [d, *_HTML_ENDPOINTS],
        )
        row = await cursor.fetchone()
        return row["total"]

    async def increment_request_count(self, endpoint: str) -> None:
        """Increment today's count for an endpoint."""
        d = date.today().isoformat()
        await self.db.execute(
            """INSERT INTO request_log (date, endpoint, count) VALUES (?, ?, 1)
               ON CONFLICT (date, endpoint) DO UPDATE SET count = count + 1""",
            (d, endpoint),
        )
        await self.db.commit()

    async def get_quota(self) -> Quota:
        """Build current Quota object."""
        used = await self.get_daily_html_count()
        return Quota(
            daily_html_used=used,
            daily_html_limit=DAILY_HTML_LIMIT,
            daily_html_remaining=max(0, DAILY_HTML_LIMIT - used),
        )

    async def can_make_html_request(self) -> bool:
        """Check if daily HTML limit allows another request."""
        used = await self.get_daily_html_count()
        return used < DAILY_HTML_LIMIT

    # -----------------------------------------------------------------------
    # Operations: request_history (detailed log)
    # -----------------------------------------------------------------------

    async def log_request(
        self,
        endpoint: str,
        url: str | None = None,
        params: str | None = None,
        status: int | None = None,
        response_ms: int | None = None,
        cached: bool = False,
        error: str | None = None,
    ) -> None:
        """Record a request in the history log."""
        await self.db.execute(
            """INSERT INTO request_history
               (timestamp, endpoint, url, params, status, response_ms, cached, error)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                _now_iso(),
                endpoint,
                url,
                params,
                status,
                response_ms,
                1 if cached else 0,
                error,
            ),
        )
        await self.db.commit()

    async def _cleanup_history(self, days: int = 30) -> None:
        """Delete request history older than N days."""
        await self.db.execute(
            "DELETE FROM request_history WHERE timestamp < date('now', ?)",
            (f"-{days} days",),
        )
        await self.db.commit()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now_iso() -> str:
    """Current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()
