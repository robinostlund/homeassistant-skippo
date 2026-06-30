"""Basic auth helper for the Skippo integration.

The Skippo boat-data API uses a static Basic auth credential embedded in the
Skippo web app JS bundle:
  btoa("".concat("webClient",":").concat("<password>"))

This credential is scraped dynamically at startup so the integration continues
working if Skippo deploys a new web app version. A hardcoded fallback is used
only when scraping fails (e.g. no network at startup).
"""

import asyncio
import base64
import logging
import re

import aiohttp

from .const import BASIC_AUTH_FALLBACK, SKIPPO_WEB_PLAN_URL

_LOGGER = logging.getLogger(__name__)

# Module-level cache: scraped once per HA session
_cached_basic_auth: str | None = None


async def async_fetch_basic_auth(session: aiohttp.ClientSession) -> str:
    """Return the Base64-encoded Basic auth credential for the Skippo API.

    Scrapes the Skippo web app JS bundle on first call; subsequent calls return
    the cached result instantly. Falls back to the hardcoded value if scraping
    fails.
    """
    global _cached_basic_auth  # noqa: PLW0603
    if _cached_basic_auth is not None:
        return _cached_basic_auth

    try:
        _cached_basic_auth = await _scrape_basic_auth(session)
    except Exception:  # noqa: BLE001
        _cached_basic_auth = None

    if _cached_basic_auth is None:
        _LOGGER.warning(
            "Could not scrape Skippo Basic auth from JS bundle; using fallback"
        )
        _cached_basic_auth = BASIC_AUTH_FALLBACK

    return _cached_basic_auth


def invalidate_basic_auth_cache() -> None:
    """Clear the cached Basic auth credential so it is re-scraped on next call."""
    global _cached_basic_auth  # noqa: PLW0603
    _cached_basic_auth = None


async def _scrape_basic_auth(session: aiohttp.ClientSession) -> str | None:
    """Scrape the Skippo Next.js bundle for the webClient Basic auth credential."""
    async with session.get(
        SKIPPO_WEB_PLAN_URL,
        timeout=aiohttp.ClientTimeout(total=15),
    ) as resp:
        if resp.status != 200:
            return None
        html = await resp.text()

    chunk_paths = list(set(re.findall(r'/(?:plan/)?_next/static/chunks/[^\s"\']+\.js', html)))
    _LOGGER.debug("Skippo: found %d JS chunks to search for Basic auth", len(chunk_paths))

    _pat1 = re.compile(r'concat\("webClient",":"\)\.concat\("([^"]+)"\)')
    _pat2 = re.compile(r'btoa\("webClient:([^"]+)"\)')

    async def _check(path: str) -> str | None:
        url = f"https://www.skippo.se{path}"
        try:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status != 200:
                    return None
                text = await resp.text()
        except aiohttp.ClientError:
            return None
        for pat in [_pat1, _pat2]:
            m = pat.search(text)
            if m:
                return m.group(1)
        return None

    results = await asyncio.gather(*[_check(p) for p in chunk_paths])
    for path, secret in zip(chunk_paths, results):
        if secret:
            b64 = base64.b64encode(f"webClient:{secret}".encode()).decode()
            _LOGGER.debug("Skippo: scraped Basic auth credential from %s", path)
            return b64

    return None
