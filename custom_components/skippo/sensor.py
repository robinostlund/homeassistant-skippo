from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_VESSELS, DOMAIN

PARALLEL_UPDATES = 0
from .coordinator import SkippoCoordinator
from .entity_base import SkippoVesselEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SkippoCoordinator = hass.data[DOMAIN][entry.entry_id]
    vessels: dict[str, str] = entry.data.get(CONF_VESSELS, {})
    async_add_entities(
        SkippoSpeedSensor(coordinator, vessel_id, name)
        for vessel_id, name in vessels.items()
    )


class SkippoSpeedSensor(SkippoVesselEntity, SensorEntity):
    _attr_translation_key = "speed"
    _attr_device_class = SensorDeviceClass.SPEED
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = UnitOfSpeed.KNOTS
    _attr_suggested_display_precision = 1

    def __init__(
        self,
        coordinator: SkippoCoordinator,
        vessel_id: str,
        vessel_name: str,
    ) -> None:
        super().__init__(coordinator, vessel_id, vessel_name, "speed")

    @property
    def native_value(self) -> float | None:
        data = self._data
        if not data:
            return None
        if "speed_knots" in data:
            return data["speed_knots"]
        if data.get("s") == 0:
            return 0.0
        return None
