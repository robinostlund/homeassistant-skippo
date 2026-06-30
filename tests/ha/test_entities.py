"""Tests for entity creation — device tracker, speed sensor, and binary sensors."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_registry import async_get as er_get
from homeassistant.helpers.device_registry import async_get as dr_get
from tests.common import MockConfigEntry

DOMAIN = "skippo"


class TestEntityCreation:
    async def test_device_tracker_registered(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry, real_vessel_id: str
    ):
        er = er_get(hass)
        tracker = next(
            (e for e in er.entities.values() if e.unique_id == f"{real_vessel_id}_tracker"),
            None,
        )
        assert tracker is not None, (
            f"No device_tracker entity found with unique_id '{real_vessel_id}_tracker'"
        )
        assert tracker.domain == "device_tracker"

    async def test_speed_sensor_registered(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry, real_vessel_id: str
    ):
        er = er_get(hass)
        sensor = next(
            (e for e in er.entities.values() if e.unique_id == f"{real_vessel_id}_speed"),
            None,
        )
        assert sensor is not None, (
            f"No sensor entity found with unique_id '{real_vessel_id}_speed'"
        )
        assert sensor.domain == "sensor"

    @pytest.mark.parametrize("suffix", ["online", "moving", "anchored"])
    async def test_binary_sensor_registered(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry, real_vessel_id: str, suffix: str
    ):
        er = er_get(hass)
        entity = next(
            (e for e in er.entities.values() if e.unique_id == f"{real_vessel_id}_{suffix}"),
            None,
        )
        assert entity is not None, (
            f"No binary_sensor entity found with unique_id '{real_vessel_id}_{suffix}'"
        )
        assert entity.domain == "binary_sensor"

    async def test_all_entities_share_one_device(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry, real_vessel_id: str
    ):
        er = er_get(hass)
        device_ids = set()
        for suffix in ("_tracker", "_speed", "_online", "_moving", "_anchored"):
            uid = f"{real_vessel_id}{suffix}"
            entry = next((e for e in er.entities.values() if e.unique_id == uid), None)
            assert entry is not None, f"Entity '{uid}' not found in entity registry"
            device_ids.add(entry.device_id)

        assert len(device_ids) == 1, (
            f"All 5 entities should share 1 device, found {len(device_ids)} devices"
        )

    async def test_device_has_skippo_manufacturer(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry, real_vessel_id: str
    ):
        er = er_get(hass)
        dr = dr_get(hass)

        entity = next(
            (e for e in er.entities.values() if e.unique_id == f"{real_vessel_id}_tracker"),
            None,
        )
        assert entity is not None
        device = dr.async_get(entity.device_id)
        assert device is not None
        assert device.manufacturer == "Skippo"


class TestEntityStates:
    async def test_device_tracker_state_is_set(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry, real_vessel_id: str
    ):
        er = er_get(hass)
        entity = next(
            (e for e in er.entities.values() if e.unique_id == f"{real_vessel_id}_tracker"),
            None,
        )
        assert entity is not None
        state = hass.states.get(entity.entity_id)
        assert state is not None, f"State is None for {entity.entity_id}"

    @pytest.mark.parametrize("suffix", ["online", "moving", "anchored"])
    async def test_binary_sensor_state_is_valid(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry, real_vessel_id: str, suffix: str
    ):
        er = er_get(hass)
        entity = next(
            (e for e in er.entities.values() if e.unique_id == f"{real_vessel_id}_{suffix}"),
            None,
        )
        assert entity is not None
        state = hass.states.get(entity.entity_id)
        assert state is not None
        assert state.state in ("on", "off", "unavailable"), (
            f"Unexpected state for {suffix} sensor: {state.state!r}"
        )
