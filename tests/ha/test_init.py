"""Tests for integration setup and teardown."""

from __future__ import annotations

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from tests.common import MockConfigEntry

DOMAIN = "skippo"


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> bool:
    entry.add_to_hass(hass)
    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return result


class TestSetup:
    async def test_setup_entry_succeeds(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ):
        assert await _setup(hass, config_entry)
        assert config_entry.state is ConfigEntryState.LOADED

    async def test_setup_registers_coordinator(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ):
        await _setup(hass, config_entry)
        assert DOMAIN in hass.data
        assert config_entry.entry_id in hass.data[DOMAIN]

    async def test_unload_entry_succeeds(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ):
        await _setup(hass, config_entry)
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        assert config_entry.state is ConfigEntryState.NOT_LOADED

    async def test_unload_removes_coordinator(
        self, hass: HomeAssistant, config_entry: MockConfigEntry
    ):
        await _setup(hass, config_entry)
        await hass.config_entries.async_unload(config_entry.entry_id)
        assert config_entry.entry_id not in hass.data.get(DOMAIN, {})
