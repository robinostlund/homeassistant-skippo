import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import CONF_SCAN_INTERVAL, CONF_TARGET, CONF_VESSELS, DEFAULT_SCAN_INTERVAL, DEFAULT_TARGET, DOMAIN
from .coordinator import SkippoCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER, Platform.SENSOR]

type SkippoConfigEntry = ConfigEntry[SkippoCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SkippoConfigEntry) -> bool:
    vessels: dict[str, str] = entry.data.get(CONF_VESSELS, {})
    vessel_ids = set(vessels.keys())

    coordinator = SkippoCoordinator(
        hass,
        vessel_ids=vessel_ids,
        target=entry.data.get(CONF_TARGET, DEFAULT_TARGET),
        scan_interval=entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _remove_stale_devices(hass, entry, vessel_ids)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


def _remove_stale_devices(
    hass: HomeAssistant,
    entry: SkippoConfigEntry,
    current_vessel_ids: set[str],
) -> None:
    """Remove device registry entries for vessels no longer being tracked."""
    dev_reg = dr.async_get(hass)
    for device_entry in dr.async_entries_for_config_entry(dev_reg, entry.entry_id):
        vessel_id = next(
            (ident[1] for ident in device_entry.identifiers if ident[0] == DOMAIN),
            None,
        )
        if vessel_id is not None and vessel_id not in current_vessel_ids:
            _LOGGER.debug("Removing stale device for vessel %s", vessel_id)
            dev_reg.async_remove_device(device_entry.id)


async def _async_update_listener(hass: HomeAssistant, entry: SkippoConfigEntry) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: SkippoConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
