from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SkippoConfigEntry
from .const import CONF_VESSELS, MOVING_SPEED_THRESHOLD
from .coordinator import SkippoCoordinator
from .entity_base import SkippoVesselEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SkippoBinarySensorEntityDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict], bool | None] = lambda data: None


def _moving_value(data: dict) -> bool | None:
    speed = data.get("speed_knots")
    if speed is not None:
        return speed >= MOVING_SPEED_THRESHOLD
    s = data.get("s")
    if s is not None:
        return s == 1
    return None


BINARY_SENSOR_DESCRIPTIONS: tuple[SkippoBinarySensorEntityDescription, ...] = (
    SkippoBinarySensorEntityDescription(
        key="online",
        translation_key="online",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda data: data.get("online", False),
    ),
    SkippoBinarySensorEntityDescription(
        key="moving",
        translation_key="moving",
        device_class=BinarySensorDeviceClass.MOVING,
        value_fn=_moving_value,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: SkippoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator: SkippoCoordinator = entry.runtime_data
    vessels: dict[str, str] = entry.data.get(CONF_VESSELS, {})
    async_add_entities(
        SkippoBinarySensor(coordinator, vessel_id, name, description)
        for vessel_id, name in vessels.items()
        for description in BINARY_SENSOR_DESCRIPTIONS
    )


class SkippoBinarySensor(SkippoVesselEntity, BinarySensorEntity):
    entity_description: SkippoBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: SkippoCoordinator,
        vessel_id: str,
        vessel_name: str,
        description: SkippoBinarySensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, vessel_id, vessel_name, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool | None:
        if not self._data:
            return None
        return self.entity_description.value_fn(self._data)
