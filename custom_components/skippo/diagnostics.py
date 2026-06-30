"""Diagnostics for the Skippo integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONF_TARGET, CONF_VESSELS, DOMAIN


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict:
    """Return diagnostics for a Skippo config entry.

    Vessel IDs (MMSIs) are public AIS identifiers — no redaction needed.
    """
    coordinator = hass.data[DOMAIN][entry.entry_id]
    return {
        "region": entry.data.get(CONF_TARGET),
        "tracked_vessel_count": len(entry.data.get(CONF_VESSELS, {})),
        "coordinator_data": coordinator.data,
    }
