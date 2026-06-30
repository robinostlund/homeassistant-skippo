"""Tests for SkippoCoordinator — all API calls are mocked."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from tests.common import MockConfigEntry

DOMAIN = "skippo"
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
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        assert isinstance(coordinator.data, dict)

    async def test_tracked_vessel_in_data(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ):
        await _setup(hass, config_entry)
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        assert FAKE_VESSEL_ID in coordinator.data, (
            f"Tracked vessel {FAKE_VESSEL_ID} missing from coordinator.data. "
            f"Keys present: {list(coordinator.data.keys())}"
        )

    async def test_vessel_has_online_flag(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ):
        await _setup(hass, config_entry)
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        vessel = coordinator.data[FAKE_VESSEL_ID]
        assert "online" in vessel, "Coordinator data missing 'online' flag"
        assert isinstance(vessel["online"], bool)

    async def test_vessel_has_coordinates(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ):
        await _setup(hass, config_entry)
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
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
        """When a vessel disappears from mapAll, last known position is preserved."""
        await _setup(hass, config_entry)
        coordinator = hass.data[DOMAIN][config_entry.entry_id]

        initial = coordinator.data.get(FAKE_VESSEL_ID, {})
        assert initial, "No initial data — autouse mock should have set this up"

        # Pre-seed _last_known as a real poll would
        coordinator._last_known[FAKE_VESSEL_ID] = dict(initial)

        # Run the real _async_update_data (bypass autouse class-level mock by
        # calling the method directly via the unbound class reference) with
        # HTTP-level methods mocked to simulate vessel absent from mapAll.
        from homeassistant.components.skippo.coordinator import SkippoCoordinator

        with (
            patch.object(
                coordinator, "_build_headers", new_callable=AsyncMock, return_value={}
            ),
            patch.object(
                coordinator, "_fetch_map_all", new_callable=AsyncMock, return_value=[]
            ),
        ):
            result = await SkippoCoordinator._async_update_data(coordinator)

        assert result, "No data returned for offline vessel"
        assert result[FAKE_VESSEL_ID]["online"] is False, (
            "Expected online=False for vessel absent from mapAll"
        )
        if initial.get("lat") is not None:
            assert result[FAKE_VESSEL_ID].get("lat") == initial["lat"], (
                "Last known lat should be preserved when vessel goes offline"
            )
