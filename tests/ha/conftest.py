"""Shared fixtures for Skippo HA integration tests.

These tests run inside the HA core tree (pytest root = ha-core/).
The fixtures here supplement HA's own tests/conftest.py.
"""

from __future__ import annotations

import asyncio
import base64
import re

import aiohttp
import pytest


@pytest.fixture(scope="session")
def real_vessel_id() -> str:
    """Return a vessel ID that currently exists in the live Skippo SE mapAll."""

    async def _fetch() -> str:
        timeout = aiohttp.ClientTimeout(total=20)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get("https://www.skippo.se/plan") as resp:
                html = await resp.text()

            paths = list(set(re.findall(r'/(?:plan/)?_next/static/chunks/[^\s"\']+\.js', html)))
            _pat1 = re.compile(r'concat\("webClient",":"\)\.concat\("([^"]+)"\)')
            _pat2 = re.compile(r'btoa\("webClient:([^"]+)"\)')

            async def _check(p: str) -> str | None:
                try:
                    async with session.get(f"https://www.skippo.se{p}") as r:
                        if r.status != 200:
                            return None
                        t = await r.text()
                        for pat in [_pat1, _pat2]:
                            m = pat.search(t)
                            if m:
                                return m.group(1)
                except aiohttp.ClientError:
                    pass
                return None

            results = await asyncio.gather(*[_check(p) for p in paths])
            secret = next((r for r in results if r), None)
            assert secret, "Could not scrape Basic auth from Skippo JS bundle"

            basic = base64.b64encode(f"webClient:{secret}".encode()).decode()
            headers = {
                "content-type": "application/json",
                "origin": "https://www.skippo.se",
                "referer": "https://www.skippo.se/",
                "authorization": f"Basic {basic}",
                "target": "SE",
            }

            async with session.get(
                "https://boat-data-service.skippo.io/data/mapAll", headers=headers
            ) as resp:
                assert resp.status == 200, f"mapAll failed: HTTP {resp.status}"
                vessels = await resp.json(content_type=None)

        assert vessels, "mapAll returned an empty vessel list"
        return vessels[0]["id"]

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_fetch())
    finally:
        loop.close()


@pytest.fixture
def skippo_config_entry_data(real_vessel_id: str) -> dict:
    """Minimal valid config entry data for the Skippo integration."""
    return {
        "target": "SE",
        "vessels": {real_vessel_id: "Test Vessel"},
    }


@pytest.fixture
def config_entry(skippo_config_entry_data: dict):
    """MockConfigEntry for the Skippo integration."""
    from tests.common import MockConfigEntry
    return MockConfigEntry(domain="skippo", data=skippo_config_entry_data)


@pytest.fixture
async def loaded_entry(hass, skippo_config_entry_data: dict):
    """Set up a Skippo config entry and return it."""
    from tests.common import MockConfigEntry
    from homeassistant.core import HomeAssistant
    entry = MockConfigEntry(domain="skippo", data=skippo_config_entry_data)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
