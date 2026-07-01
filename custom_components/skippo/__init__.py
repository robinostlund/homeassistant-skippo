from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry

from .const import CONF_SCAN_INTERVAL, CONF_TARGET, CONF_VESSELS, DEFAULT_SCAN_INTERVAL, DEFAULT_TARGET, DOMAIN
from .coordinator import SkippoCoordinator

PLATFORMS = [Platform.BINARY_SENSOR, Platform.DEVICE_TRACKER, Platform.SENSOR]

type SkippoConfigEntry = ConfigEntry[SkippoCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: SkippoConfigEntry) -> bool:
    vessels: dict[str, str] = entry.data.get(CONF_VESSELS, {})
    vessel_ids = set(vessels.keys())

    coordinator = SkippoCoordinator(
        hass,
        vessel_ids=vessel_ids,
        target=entry.data.get(CONF_TARGET, DEFAULT_TARGET),
        entry_id=entry.entry_id,
        scan_interval=entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
    )
    await coordinator.async_load_last_known()
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def _async_update_listener(hass: HomeAssistant, entry: SkippoConfigEntry) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: SkippoConfigEntry,
    device_entry: DeviceEntry,
) -> bool:
    """Allow deleting a vessel device directly from the HA device UI."""
    vessel_id = next(
        (ident[1] for ident in device_entry.identifiers if ident[0] == DOMAIN),
        None,
    )
    if vessel_id is None:
        return False
    vessels = dict(entry.data.get(CONF_VESSELS, {}))
    vessels.pop(vessel_id, None)
    hass.config_entries.async_update_entry(
        entry, data={**entry.data, CONF_VESSELS: vessels}
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: SkippoConfigEntry) -> bool:
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
