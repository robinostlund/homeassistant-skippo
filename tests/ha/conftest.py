"""Shared fixtures for Skippo HA integration tests.

These tests run inside the HA core tree (pytest root = ha-core/).
All fixtures use canned data — no real network calls are made.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

FAKE_VESSEL_ID = "265023580"
FAKE_VESSEL_NAME = "Test Vessel"

FAKE_COORDINATOR_DATA = {
    FAKE_VESSEL_ID: {
        "online": True,
        "lat": 57.7089,
        "lon": 11.9746,
        "course": 270.0,
        "speed_knots": 5.2,
        "s": 1,
        "anchored": False,
        "a": False,
        "timestamp": 1720000000000,
        "name": FAKE_VESSEL_NAME,
    }
}

_PATCH_UPDATE = (
    "homeassistant.components.skippo.coordinator"
    ".SkippoCoordinator._async_update_data"
)


@pytest.fixture(autouse=True)
def mock_coordinator_update():
    """Prevent real API calls in every test by mocking the coordinator update."""
    with patch(_PATCH_UPDATE, new_callable=AsyncMock, return_value=FAKE_COORDINATOR_DATA):
        yield


@pytest.fixture
def vessel_id() -> str:
    """The fake vessel ID used in all canned fixtures."""
    return FAKE_VESSEL_ID


@pytest.fixture
def skippo_config_entry_data() -> dict:
    return {
        "target": "SE",
        "vessels": {FAKE_VESSEL_ID: FAKE_VESSEL_NAME},
    }


@pytest.fixture
def config_entry(skippo_config_entry_data: dict):
    from tests.common import MockConfigEntry
    return MockConfigEntry(domain="skippo", data=skippo_config_entry_data)


@pytest.fixture
async def loaded_entry(hass, skippo_config_entry_data: dict):
    """Set up a Skippo config entry with mocked coordinator data."""
    from tests.common import MockConfigEntry

    entry = MockConfigEntry(domain="skippo", data=skippo_config_entry_data)
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry
