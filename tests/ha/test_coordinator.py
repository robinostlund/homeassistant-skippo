"""Tests for SkippoCoordinator — all API calls are mocked."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from tests.common import MockConfigEntry

# Capture the real _async_update_data at import time (before any test fixture
# patches the class attribute). This reference survives the autouse mock.
from homeassistant.components.skippo.coordinator import SkippoCoordinator as _Coord
_REAL_ASYNC_UPDATE_DATA = _Coord._async_update_data

FAKE_VESSEL_ID = "265023580"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


class TestCoordinatorData:
    async def test_data_is_dict(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ):
        await _setup(hass, config_entry)
        coordinator = config_entry.runtime_data
        assert isinstance(coordinator.data, dict)

    async def test_tracked_vessel_in_data(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ):
        await _setup(hass, config_entry)
        coordinator = config_entry.runtime_data
        assert FAKE_VESSEL_ID in coordinator.data, (
            f"Tracked vessel {FAKE_VESSEL_ID} missing from coordinator.data. "
            f"Keys present: {list(coordinator.data.keys())}"
        )

    async def test_vessel_has_online_flag(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ):
        await _setup(hass, config_entry)
        coordinator = config_entry.runtime_data
        vessel = coordinator.data[FAKE_VESSEL_ID]
        assert "online" in vessel, "Coordinator data missing 'online' flag"
        assert isinstance(vessel["online"], bool)

    async def test_vessel_has_coordinates(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ):
        await _setup(hass, config_entry)
        coordinator = config_entry.runtime_data
        vessel = coordinator.data[FAKE_VESSEL_ID]
        if vessel.get("online"):
            assert "lat" in vessel, f"Online vessel missing 'lat': {vessel}"
            assert "lon" in vessel, f"Online vessel missing 'lon': {vessel}"


class TestOfflineVessel:
    async def test_offline_vessel_preserves_last_known(
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
    ):
        """When a vessel disappears from mapAll, last known position is preserved.

        The autouse fixture replaces _async_update_data with a mock at the class
        level. We call _REAL_ASYNC_UPDATE_DATA (captured at import time, before
        any mock) directly on the coordinator instance, with HTTP-level helpers
        patched at instance level so no network calls escape.
        """
        await _setup(hass, config_entry)
        coordinator = config_entry.runtime_data

        initial = coordinator.data.get(FAKE_VESSEL_ID, {})
        assert initial, "No initial data — autouse mock should have set this up"
        assert initial.get("lat") is not None, "Expected lat in initial data"

        # Pre-seed _last_known as the real poll would have done
        coordinator._last_known[FAKE_VESSEL_ID] = dict(initial)

        # Call the REAL _async_update_data via the captured reference.
        # Patch HTTP-level helpers at instance level so they don't reach the network.
        with (
            patch.object(coordinator, "_build_headers", new_callable=AsyncMock, return_value={}),
            patch.object(coordinator, "_fetch_map_all", new_callable=AsyncMock, return_value=[]),
        ):
            result = await _REAL_ASYNC_UPDATE_DATA(coordinator)

        assert result, "No data returned — last known should be injected"
        assert result[FAKE_VESSEL_ID]["online"] is False, (
            "Expected online=False for vessel absent from mapAll"
        )
        assert result[FAKE_VESSEL_ID].get("lat") == initial["lat"], (
            "Last known lat should be preserved when vessel goes offline"
        )
