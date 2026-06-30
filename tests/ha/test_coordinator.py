"""Tests for SkippoCoordinator — uses the live Skippo API (no credentials needed)."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from tests.common import MockConfigEntry

DOMAIN = "skippo"


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
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
        real_vessel_id: str,
    ):
        await _setup(hass, config_entry)
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        assert real_vessel_id in coordinator.data, (
            f"Tracked vessel {real_vessel_id} missing from coordinator.data. "
            f"Keys present: {list(coordinator.data.keys())}"
        )

    async def test_vessel_has_online_flag(
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
        real_vessel_id: str,
    ):
        await _setup(hass, config_entry)
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        vessel = coordinator.data[real_vessel_id]
        assert "online" in vessel, "Coordinator data missing 'online' flag"
        assert isinstance(vessel["online"], bool)

    async def test_vessel_has_coordinates(
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
        real_vessel_id: str,
    ):
        await _setup(hass, config_entry)
        coordinator = hass.data[DOMAIN][config_entry.entry_id]
        vessel = coordinator.data[real_vessel_id]
        if vessel.get("online"):
            assert "lat" in vessel, f"Online vessel missing 'lat': {vessel}"
            assert "lon" in vessel, f"Online vessel missing 'lon': {vessel}"


class TestOfflineVessel:
    async def test_offline_vessel_preserves_last_known(
        self,
        hass: HomeAssistant,
        config_entry: MockConfigEntry,
        real_vessel_id: str,
    ):
        """When a vessel disappears from mapAll, last known position is kept."""
        await _setup(hass, config_entry)
        coordinator = hass.data[DOMAIN][config_entry.entry_id]

        initial = dict(coordinator.data.get(real_vessel_id, {}))
        if not initial:
            pytest.skip("No initial data available — cannot test offline persistence")

        with patch(
            "homeassistant.components.skippo.coordinator.SkippoCoordinator._fetch_map_all",
            new_callable=AsyncMock,
            return_value=[],
        ):
            await coordinator.async_refresh()
            await hass.async_block_till_done()

        offline = coordinator.data.get(real_vessel_id, {})
        assert offline, "No data after vessel went offline — last known should be preserved"
        assert offline.get("online") is False
        if initial.get("lat") is not None:
            assert offline.get("lat") == initial["lat"], (
                "Last known lat should be preserved when vessel goes offline"
            )
