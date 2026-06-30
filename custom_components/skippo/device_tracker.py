from datetime import datetime, timezone

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CONF_VESSELS, DOMAIN
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
        SkippoDeviceTracker(coordinator, vessel_id, name)
        for vessel_id, name in vessels.items()
    )


class SkippoDeviceTracker(SkippoVesselEntity, TrackerEntity):
    _attr_name = None  # Entity name = device name
    _attr_translation_key = "vessel"

    def __init__(
        self,
        coordinator: SkippoCoordinator,
        vessel_id: str,
        vessel_name: str,
    ) -> None:
        super().__init__(coordinator, vessel_id, vessel_name, "tracker")

    @property
    def latitude(self) -> float | None:
        return self._data.get("lat")

    @property
    def longitude(self) -> float | None:
        return self._data.get("lon")

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def extra_state_attributes(self) -> dict:
        data = self._data
        attrs: dict = {}

        course = data.get("course") or data.get("c")
        if course is not None and course != -1.0:
            attrs["course"] = round(course, 1)

        for field in ("vessel_name", "call_sign", "country_code", "length", "width", "draught"):
            if data.get(field) is not None:
                attrs[field] = data[field]

        ts = data.get("ts")
        if ts:
            attrs["last_seen"] = datetime.fromtimestamp(
                ts / 1000, tz=timezone.utc
            ).isoformat()
        return attrs
