"""API integration tests for the Skippo integration.

Run standalone (no Home Assistant needed):
    pip install aiohttp pytest pytest-asyncio
    pytest tests/test_api.py -v

All tests run without credentials — the Skippo API is accessible with just
the Basic auth credential scraped from the JS bundle.
"""

import asyncio
import base64
import importlib.util
import re
from pathlib import Path

import aiohttp
import pytest
import pytest_asyncio

# Load const.py directly — avoids importing the HA-dependent __init__.py
_ROOT = Path(__file__).parent.parent
_spec = importlib.util.spec_from_file_location(
    "skippo_const", _ROOT / "custom_components" / "skippo" / "const.py"
)
_const = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_const)

API_BASE_URL = _const.API_BASE_URL
BASIC_AUTH_FALLBACK = _const.BASIC_AUTH_FALLBACK
SKIPPO_WEB_PLAN_URL = _const.SKIPPO_WEB_PLAN_URL

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_CHUNK_RE = re.compile(r'/(?:plan/)?_next/static/chunks/[^\s"\']+\.js')
_PAT1 = re.compile(r'concat\("webClient",":"\)\.concat\("([^"]+)"\)')
_PAT2 = re.compile(r'btoa\("webClient:([^"]+)"\)')


async def _scrape_basic_auth(session: aiohttp.ClientSession) -> str | None:
    async with session.get(SKIPPO_WEB_PLAN_URL, timeout=aiohttp.ClientTimeout(total=20)) as resp:
        if resp.status != 200:
            return None
        html = await resp.text()

    chunk_paths = list(set(_CHUNK_RE.findall(html)))

    async def _check(path: str) -> str | None:
        url = f"https://www.skippo.se{path}"
        try:
            async with session.get(url) as r:
                if r.status != 200:
                    return None
                text = await r.text()
        except aiohttp.ClientError:
            return None
        for pat in [_PAT1, _PAT2]:
            m = pat.search(text)
            if m:
                return m.group(1)
        return None

    results = await asyncio.gather(*[_check(p) for p in chunk_paths])
    for secret in results:
        if secret:
            return base64.b64encode(f"webClient:{secret}".encode()).decode()
    return None


def _base_headers(basic: str, target: str = "SE") -> dict:
    return {
        "content-type": "application/json",
        "origin": "https://www.skippo.se",
        "referer": "https://www.skippo.se/",
        "authorization": f"Basic {basic}",
        "target": target,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def http_session():
    timeout = aiohttp.ClientTimeout(total=20)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        yield session


@pytest_asyncio.fixture
async def basic_auth(http_session):
    b64 = await _scrape_basic_auth(http_session)
    assert b64 is not None, (
        "Could not scrape Basic auth from Skippo JS bundle. "
        "Check that https://www.skippo.se/plan is reachable."
    )
    return b64


@pytest_asyncio.fixture
async def map_all_vessels(http_session, basic_auth):
    headers = _base_headers(basic_auth)
    async with http_session.get(f"{API_BASE_URL}/data/mapAll", headers=headers) as resp:
        assert resp.status == 200, f"mapAll returned HTTP {resp.status}"
        return await resp.json(content_type=None)


# ---------------------------------------------------------------------------
# Tests — Basic auth scraping
# ---------------------------------------------------------------------------

class TestBasicAuthScraping:
    async def test_scrape_returns_base64_string(self, basic_auth):
        decoded = base64.b64decode(basic_auth).decode()
        assert decoded.startswith("webClient:"), (
            f"Scraped credential does not start with 'webClient:': {decoded!r}"
        )

    async def test_scraped_credential_format(self, basic_auth):
        decoded = base64.b64decode(basic_auth).decode()
        parts = decoded.split(":", 1)
        assert len(parts) == 2 and parts[0] == "webClient" and len(parts[1]) > 0, (
            f"Unexpected credential format: {decoded!r}"
        )


# ---------------------------------------------------------------------------
# Tests — mapAll endpoint
# ---------------------------------------------------------------------------

class TestMapAll:
    async def test_returns_non_empty_list(self, map_all_vessels):
        assert isinstance(map_all_vessels, list)
        assert len(map_all_vessels) > 0, "mapAll returned an empty vessel list"

    async def test_vessel_schema(self, map_all_vessels):
        required_fields = {"id", "lat", "lon"}
        for vessel in map_all_vessels[:50]:
            missing = required_fields - vessel.keys()
            assert not missing, f"Vessel missing fields {missing}: {vessel}"
            assert isinstance(vessel["lat"], (int, float))
            assert isinstance(vessel["lon"], (int, float))

    async def test_coordinate_ranges(self, map_all_vessels):
        for vessel in map_all_vessels[:200]:
            assert -90 <= vessel["lat"] <= 90, f"Invalid lat: {vessel['lat']}"
            assert -180 <= vessel["lon"] <= 180, f"Invalid lon: {vessel['lon']}"

    async def test_status_field_is_binary(self, map_all_vessels):
        for vessel in map_all_vessels[:200]:
            if "s" in vessel:
                assert vessel["s"] in (0, 1), (
                    f"Field 's' should be 0 or 1, got {vessel['s']}"
                )


# ---------------------------------------------------------------------------
# Tests — Detail endpoint
# ---------------------------------------------------------------------------

class TestDetailEndpoint:
    async def test_detail_returns_location(self, http_session, basic_auth, map_all_vessels):
        vessel_id = map_all_vessels[0]["id"]
        headers = {k: v for k, v in _base_headers(basic_auth).items() if k != "target"}
        async with http_session.get(
            f"{API_BASE_URL}/data/2412/{vessel_id}", headers=headers
        ) as resp:
            assert resp.status == 200, f"Detail returned HTTP {resp.status} for {vessel_id}"
            data = await resp.json(content_type=None)

        assert "location" in data or "name" in data, (
            f"Detail response missing 'location' and 'name': {list(data.keys())}"
        )

    async def test_detail_speed_is_float_when_present(self, http_session, basic_auth, map_all_vessels):
        moving = [v for v in map_all_vessels if v.get("s") == 1]
        if not moving:
            pytest.skip("No moving vessels in mapAll response — cannot test speed field")

        vessel_id = moving[0]["id"]
        headers = {k: v for k, v in _base_headers(basic_auth).items() if k != "target"}
        async with http_session.get(
            f"{API_BASE_URL}/data/2412/{vessel_id}", headers=headers
        ) as resp:
            assert resp.status == 200
            data = await resp.json(content_type=None)

        loc = data.get("location", {})
        speed = loc.get("speed")
        if speed is not None:
            assert isinstance(speed, (int, float)), f"speed should be numeric, got {type(speed)}: {speed}"
            assert speed >= 0, f"speed should be non-negative, got {speed}"
