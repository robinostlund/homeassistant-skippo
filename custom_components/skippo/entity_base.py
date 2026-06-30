from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER, MODEL_AIS, MODEL_USER
from .coordinator import SkippoCoordinator


class SkippoVesselEntity(CoordinatorEntity[SkippoCoordinator]):
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: SkippoCoordinator,
        vessel_id: str,
        vessel_name: str,
        unique_id_suffix: str,
    ) -> None:
        super().__init__(coordinator)
        self._vessel_id = vessel_id
        self._attr_unique_id = f"{vessel_id}_{unique_id_suffix}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, vessel_id)},
            name=vessel_name,
            manufacturer=MANUFACTURER,
            model=MODEL_AIS if vessel_id.isdigit() else MODEL_USER,
            serial_number=vessel_id,
        )

    @property
    def _data(self) -> dict:
        return self.coordinator.data.get(self._vessel_id, {})

    @property
    def available(self) -> bool:
        return super().available and bool(self._data)
