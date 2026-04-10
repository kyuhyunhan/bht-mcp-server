"""BHt MCP Server — HTTP client with rate limiting and request tracking.

Responsibilities:
- Rate limiting: 1 req/s fixed interval (MIN_REQUEST_INTERVAL)
- Daily HTML limit enforcement (DAILY_HTML_LIMIT via CacheManager)
- Cookie session management (httpx AsyncClient)
- Request logging (via CacheManager)
- Timeout handling with single retry for timeouts

This module is a thin HTTP layer. Cache orchestration and HTML parsing
are handled by the tool layer.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx

from bht_mcp.cache import CacheManager
from bht_mcp.models import (
    BHT_AJAX_URL,
    BHT_VIEWS_URL,
    MIN_REQUEST_INTERVAL,
    SEARCH_POST_ID,
    ErrorCode,
    ErrorInfo,
)

_TIMEOUT = 10.0  # seconds
_RETRY_DELAY = 5.0  # seconds before retry on timeout


class DailyLimitExceeded(Exception):
    """Raised when the daily HTML request limit is reached."""

    def __init__(self) -> None:
        super().__init__("Daily HTML request limit reached")
        self.error_info = ErrorInfo(
            code=ErrorCode.DAILY_LIMIT_REACHED,
            message="Daily HTML request limit (150) reached. Resets at midnight.",
            suggestion=(
                "Cached data is still available. Use bht_search to explore, "
                "or request tokens that have cached:true."
            ),
        )


class BhtUnavailable(Exception):
    """Raised when BHt server is unreachable or returns a server error."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.error_info = ErrorInfo(
            code=ErrorCode.BHT_UNAVAILABLE,
            message=message,
            suggestion=(
                "The BHt server at LMU Munich may be temporarily down. "
                "Try again later. Cached data is still available."
            ),
        )


class Fetcher:
    """Async HTTP client for BHt with rate limiting and request tracking.

    Usage::

        fetcher = Fetcher(cache)
        await fetcher.initialize()
        try:
            results = await fetcher.flex_search(filters)
        finally:
            await fetcher.close()
    """

    def __init__(self, cache: CacheManager) -> None:
        self._cache = cache
        self._client: httpx.AsyncClient | None = None
        self._last_request: float = 0.0

    # -- Lifecycle -----------------------------------------------------------

    async def initialize(self) -> None:
        self._client = httpx.AsyncClient(
            follow_redirects=True,
            timeout=httpx.Timeout(_TIMEOUT),
            headers={
                "User-Agent": "bht-mcp/0.1 (research tool; https://github.com/)",
                "X-Requested-With": "XMLHttpRequest",
            },
        )

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> Fetcher:
        await self.initialize()
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    @property
    def client(self) -> httpx.AsyncClient:
        assert self._client is not None, "Fetcher not initialized"
        return self._client

    # -- JSON API endpoints (no daily limit) ---------------------------------

    async def flex_search(
        self, filters: list[dict[str, str]], post_id: int = SEARCH_POST_ID
    ) -> list[dict[str, Any]]:
        """Execute a flex_search query. Returns list of result dicts.

        Filters: [{"field": "buch", "value": "Gen"}, ...]
        """
        payload: dict[str, str] = {
            "action": "flexsearch_search_action",
            "id": str(post_id),
        }
        for i, f in enumerate(filters):
            payload[f"field{i}"] = f["field"]
            payload[f"value{i}"] = f["value"]
        payload["paramCount"] = str(len(filters))

        response = await self._post(
            BHT_AJAX_URL, data=payload, endpoint="search"
        )
        return response.json()

    async def autocomplete(
        self, field: str, value: str = "", post_id: int = SEARCH_POST_ID
    ) -> list[str]:
        """Fetch autocomplete values for a search field.

        Returns list of value strings.
        Response format: [{"auto": "G", "custom": "G"}, ...]
        """
        payload = {
            "action": "flexsearch_autocomplete_action",
            "id": str(post_id),
            "autoField": field,
            "autoValue": value,
        }
        response = await self._post(
            BHT_AJAX_URL, data=payload, endpoint="autocomplete"
        )
        data = response.json()
        if isinstance(data, list):
            if data and isinstance(data[0], dict):
                return [item.get("auto", str(item)) for item in data]
            return [str(item) for item in data]
        return []

    # -- HTML endpoints (daily limit applies) --------------------------------

    async def fetch_beleg_html(
        self, buch: str, chapter: int, b_nr: int
    ) -> str:
        """Fetch a beleg page. Returns raw HTML string.

        Raises DailyLimitExceeded if daily HTML limit is reached.
        """
        await self._check_daily_limit()
        url = f"{BHT_VIEWS_URL}/beleg/?book={buch}&chapter={chapter}&b_nr={b_nr}"
        response = await self._get(
            url, endpoint="beleg", params=f"book={buch},chapter={chapter},b_nr={b_nr}"
        )
        return response.text

    async def fetch_tree_html(
        self,
        buch: str,
        chapter: int,
        b_nr: int,
        bm_nr: int,
        vers: int,
        satz: str,
        s_nr: int,
    ) -> str:
        """Fetch a syntax tree page. Returns raw HTML string."""
        await self._check_daily_limit()
        url = (
            f"{BHT_VIEWS_URL}/tree/?book={buch}&chapter={chapter}"
            f"&b_nr={b_nr}&bm_nr={bm_nr}&vers={vers}&satz={satz}&s_nr={s_nr}"
        )
        response = await self._get(
            url, endpoint="tree", params=f"book={buch},chapter={chapter},satz={satz}"
        )
        return response.text

    async def fetch_sentence_html(
        self,
        buch: str,
        chapter: int,
        b_nr: int,
        bm_nr: int,
        vers: int,
        satz: str,
        s_nr: int,
    ) -> str:
        """Fetch a sentence analysis page. Returns raw HTML string."""
        await self._check_daily_limit()
        url = (
            f"{BHT_VIEWS_URL}/satzfugungsebene/?book={buch}&chapter={chapter}"
            f"&b_nr={b_nr}&bm_nr={bm_nr}&vers={vers}&satz={satz}&s_nr={s_nr}"
        )
        response = await self._get(
            url, endpoint="satz", params=f"book={buch},chapter={chapter},satz={satz}"
        )
        return response.text

    async def fetch_text_anm_html(self, buch: str, chapter: int) -> str:
        """Fetch text annotations page. Returns raw HTML string."""
        await self._check_daily_limit()
        url = f"{BHT_VIEWS_URL}/text_anm/?book={buch}&chapter={chapter}"
        response = await self._get(
            url, endpoint="text_anm", params=f"book={buch},chapter={chapter}"
        )
        return response.text

    # -- Internal: rate limiting, request execution, logging -----------------

    async def _rate_limit_wait(self) -> None:
        """Wait until MIN_REQUEST_INTERVAL has elapsed since last request."""
        elapsed = time.monotonic() - self._last_request
        if elapsed < MIN_REQUEST_INTERVAL:
            await asyncio.sleep(MIN_REQUEST_INTERVAL - elapsed)
        self._last_request = time.monotonic()

    async def _check_daily_limit(self) -> None:
        """Raise DailyLimitExceeded if daily HTML quota is exhausted."""
        if not await self._cache.can_make_html_request():
            raise DailyLimitExceeded()

    async def _post(
        self,
        url: str,
        data: dict[str, str],
        endpoint: str,
    ) -> httpx.Response:
        """POST request with rate limiting, logging, and retry."""
        return await self._request("POST", url, endpoint=endpoint, data=data)

    async def _get(
        self,
        url: str,
        endpoint: str,
        params: str = "",
    ) -> httpx.Response:
        """GET request with rate limiting, logging, and retry."""
        return await self._request(
            "GET", url, endpoint=endpoint, log_params=params
        )

    async def _request(
        self,
        method: str,
        url: str,
        endpoint: str,
        data: dict[str, str] | None = None,
        log_params: str = "",
    ) -> httpx.Response:
        """Core request method with rate limiting, single retry, and logging."""
        await self._rate_limit_wait()

        start_ms = _now_ms()
        try:
            response = await self._do_request(method, url, data)
        except httpx.TimeoutException:
            # Single retry after delay for timeouts only
            await self._cache.log_request(
                endpoint=endpoint, url=url, params=log_params,
                status=None, response_ms=_now_ms() - start_ms,
                error="timeout",
            )
            await asyncio.sleep(_RETRY_DELAY)
            await self._rate_limit_wait()
            start_ms = _now_ms()
            try:
                response = await self._do_request(method, url, data)
            except httpx.TimeoutException:
                await self._cache.log_request(
                    endpoint=endpoint, url=url, params=log_params,
                    status=None, response_ms=_now_ms() - start_ms,
                    error="timeout_retry_failed",
                )
                raise BhtUnavailable(
                    f"BHt server did not respond (timeout after {_TIMEOUT}s, "
                    f"retried once after {_RETRY_DELAY}s)."
                )

        elapsed_ms = _now_ms() - start_ms

        # Check for server errors
        if response.status_code >= 500:
            await self._cache.log_request(
                endpoint=endpoint, url=url, params=log_params,
                status=response.status_code, response_ms=elapsed_ms,
                error=f"server_error_{response.status_code}",
            )
            raise BhtUnavailable(
                f"BHt server returned {response.status_code}."
            )

        if response.status_code == 404:
            await self._cache.log_request(
                endpoint=endpoint, url=url, params=log_params,
                status=404, response_ms=elapsed_ms,
                error="not_found",
            )
            raise BhtUnavailable(
                f"BHt returned 404 for {url}. The resource may not exist."
            )

        # Success — log and increment counter for HTML endpoints
        await self._cache.log_request(
            endpoint=endpoint, url=url, params=log_params,
            status=response.status_code, response_ms=elapsed_ms,
        )
        await self._cache.increment_request_count(endpoint)

        return response

    async def _do_request(
        self, method: str, url: str, data: dict[str, str] | None
    ) -> httpx.Response:
        if method == "POST":
            return await self.client.post(url, data=data)
        return await self.client.get(url)


def _now_ms() -> int:
    return int(time.monotonic() * 1000)
