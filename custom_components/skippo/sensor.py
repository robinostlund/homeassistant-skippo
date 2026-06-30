from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import UnitOfSpeed
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SkippoConfigEntry
from .const import CONF_VESSELS
from .coordinator import SkippoCoordinator
from .entity_base import SkippoVesselEntity

PARALLEL_UPDATES = 0


@dataclass(frozen=True, kw_only=True)
class SkippoSensorEntityDescription(SensorEntityDescription):
    value_fn: Callable[[dict], float | None] = lambda data: None


def _speed_value(data: dict) -> float | None:
    if "speed_knots" in data:
        return data["speed_knots"]
    if data.get("s") == 0:
        return 0.0
    return None


SENSOR_DESCRIPTIONS: tuple[SkippoSensorEntityDescription, ...] = (
    SkippoSensorEntityDescription(
        key="speed",
        translation_key="speed",
        device_class=SensorDeviceClass.SPEED,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=UnitOfSpeed.KNOTS,
        suggested_display_precision=1,
        value_fn=_speed_value,
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
        SkippoSensor(coordinator, vessel_id, name, description)
        for vessel_id, name in vessels.items()
        for description in SENSOR_DESCRIPTIONS
    )


class SkippoSensor(SkippoVesselEntity, SensorEntity):
    entity_description: SkippoSensorEntityDescription

    def __init__(
        self,
        coordinator: SkippoCoordinator,
        vessel_id: str,
        vessel_name: str,
        description: SkippoSensorEntityDescription,
    ) -> None:
        super().__init__(coordinator, vessel_id, vessel_name, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> float | None:
        if not self._data:
            return None
        return self.entity_description.value_fn(self._data)
