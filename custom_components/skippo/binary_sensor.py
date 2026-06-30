from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_VESSELS, DOMAIN
from .coordinator import SkippoCoordinator
from .entity_base import SkippoVesselEntity

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SkippoCoordinator = hass.data[DOMAIN][entry.entry_id]
    vessels: dict[str, str] = entry.data.get(CONF_VESSELS, {})
    entities = []
    for vessel_id, name in vessels.items():
        entities.append(SkippoConnectivitySensor(coordinator, vessel_id, name))
        entities.append(SkippoMovingSensor(coordinator, vessel_id, name))
    async_add_entities(entities)


class SkippoConnectivitySensor(SkippoVesselEntity, BinarySensorEntity):
    _attr_translation_key = "online"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator: SkippoCoordinator, vessel_id: str, vessel_name: str) -> None:
        super().__init__(coordinator, vessel_id, vessel_name, "online")

    @property
    def is_on(self) -> bool | None:
        return self._data.get("online", False)


class SkippoMovingSensor(SkippoVesselEntity, BinarySensorEntity):
    _attr_translation_key = "moving"
    _attr_device_class = BinarySensorDeviceClass.MOVING

    def __init__(self, coordinator: SkippoCoordinator, vessel_id: str, vessel_name: str) -> None:
        super().__init__(coordinator, vessel_id, vessel_name, "moving")

    @property
    def is_on(self) -> bool | None:
        data = self._data
        if not data:
            return None
        speed = data.get("speed_knots")
        if speed is not None:
            return speed > 0
        s = data.get("s")
        if s is not None:
            return s == 1
        return None
