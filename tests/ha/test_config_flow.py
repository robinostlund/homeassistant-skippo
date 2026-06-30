"""Tests for the Skippo config flow and options flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from tests.common import MockConfigEntry

DOMAIN = "skippo"

_PATCH_VESSEL_EXISTS = "homeassistant.components.skippo.config_flow._vessel_exists"


class TestConfigFlowUserStep:
    async def test_shows_form_initially(self, hass: HomeAssistant):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == "form"
        assert result["step_id"] == "user"

    async def test_user_step_advances_to_vessel(self, hass: HomeAssistant):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={"target": "SE"},
        )
        assert result["type"] == "form"
        assert result["step_id"] == "vessel"

    async def test_already_configured_aborts(self, hass: HomeAssistant):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={"target": "SE", "vessels": {"123": "My Boat"}},
        )
        entry.add_to_hass(hass)

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}
        )
        assert result["type"] == "abort"
        assert result["reason"] == "already_configured"


class TestConfigFlowVesselStep:
    async def _start_flow(self, hass: HomeAssistant) -> str:
        """Advance past user step and return flow_id."""
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "user"},
            data={"target": "SE"},
        )
        assert result["step_id"] == "vessel"
        return next(iter(hass.config_entries.flow._progress))

    async def test_nonexistent_vessel_shows_error(self, hass: HomeAssistant):
        flow_id = await self._start_flow(hass)
        with patch(_PATCH_VESSEL_EXISTS, return_value=(False, None)):
            result = await hass.config_entries.flow.async_configure(
                flow_id,
                user_input={"vessel_id": "0000000000", "vessel_name": "", "add_another": False},
            )
        assert result["type"] == "form"
        assert result["errors"].get("vessel_id") == "vessel_not_found"

    async def test_network_error_shows_cannot_connect(self, hass: HomeAssistant):
        flow_id = await self._start_flow(hass)
        with patch(_PATCH_VESSEL_EXISTS, return_value=(False, "cannot_connect")):
            result = await hass.config_entries.flow.async_configure(
                flow_id,
                user_input={"vessel_id": "123", "vessel_name": "", "add_another": False},
            )
        assert result["type"] == "form"
        assert result["errors"].get("base") == "cannot_connect"

    async def test_valid_vessel_creates_entry(
        self, hass: HomeAssistant, real_vessel_id: str
    ):
        flow_id = await self._start_flow(hass)
        with patch(_PATCH_VESSEL_EXISTS, return_value=(True, None)):
            result = await hass.config_entries.flow.async_configure(
                flow_id,
                user_input={
                    "vessel_id": real_vessel_id,
                    "vessel_name": "My Boat",
                    "add_another": False,
                },
            )
        assert result["type"] == "create_entry", (
            f"Expected create_entry but got {result['type']}. "
            f"Errors: {result.get('errors')}"
        )
        assert result["data"]["vessels"] == {real_vessel_id: "My Boat"}
        assert result["data"]["target"] == "SE"
        assert "refresh_token" not in result["data"]
        assert "email" not in result["data"]

    async def test_add_another_loops_back(
        self, hass: HomeAssistant, real_vessel_id: str
    ):
        flow_id = await self._start_flow(hass)
        with patch(_PATCH_VESSEL_EXISTS, return_value=(True, None)):
            result = await hass.config_entries.flow.async_configure(
                flow_id,
                user_input={
                    "vessel_id": real_vessel_id,
                    "vessel_name": "First Boat",
                    "add_another": True,
                },
            )
        assert result["type"] == "form"
        assert result["step_id"] == "vessel"


class TestOptionsFlow:
    async def test_options_shows_menu(
        self, hass: HomeAssistant, loaded_entry: MockConfigEntry
    ):
        result = await hass.config_entries.options.async_init(loaded_entry.entry_id)
        assert result["type"] == "menu"
        assert "add_vessel" in result["menu_options"]
        assert "remove_vessel" in result["menu_options"]

    async def test_remove_vessel_removes_from_entry_data(
        self,
        hass: HomeAssistant,
        loaded_entry: MockConfigEntry,
        real_vessel_id: str,
    ):
        result = await hass.config_entries.options.async_init(loaded_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={"next_step_id": "remove_vessel"}
        )
        assert result["step_id"] == "remove_vessel"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={"vessel_ids": [real_vessel_id]},
        )
        assert result["type"] == "create_entry"
        assert real_vessel_id not in loaded_entry.data.get("vessels", {})
