"""Read-only schedule entities backed by one shared schedule reader."""

from dataclasses import dataclass
from typing import Any
from typing import cast

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import Platform
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.types import Inv
from ..common.types import RegisterType
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .modbus_entity_mixin import ModbusEntityMixin
from .schedule_descriptions import ModbusScheduleFactory


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusScheduleSensorDescription(SensorEntityDescription, EntityFactory):  # type: ignore[misc]
    """Create schedule sensors using the same capability as the manager."""

    factory: ModbusScheduleFactory

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

    def create_entity_if_supported(
        self, controller: EntityController, inverter_model: Inv, register_type: RegisterType
    ) -> Entity | None:
        if self.factory.create_if_supported(inverter_model, register_type) is None:
            return None
        return ModbusScheduleSensor(controller, self)

    def serialize(self, inverter_model: Inv, register_type: RegisterType) -> dict[str, Any] | None:
        config = self.factory.create_if_supported(inverter_model, register_type)
        if config is None:
            return None
        return {
            "type": "schedule",
            "key": self.key,
            "name": self.name,
            "first_record_address": config.first_record_address,
            "record_size": config.record_size,
            "max_records": config.max_records,
        }


class ModbusScheduleSensor(ModbusEntityMixin, SensorEntity):
    """Publish a count/list or Remaining Time mode/parameters; never write."""

    def __init__(self, controller: EntityController, description: ModbusScheduleSensorDescription) -> None:
        self._controller = controller
        self.entity_description = description
        self.entity_id = self._get_entity_id(Platform.SENSOR)
        manager = controller.schedule_reader_manager
        assert manager is not None
        self._manager = manager

    @property
    def addresses(self) -> list[int]:
        # Dynamic schedule reads are deliberately excluded from normal telemetry
        # subscriptions. The manager scans only the configured range through Remaining Time.
        return []

    @property
    def available(self) -> bool:
        return super().available and self._manager.snapshot is not None and self._manager.error is None

    @property
    def native_value(self) -> int | str | None:
        snapshot = self._manager.snapshot
        if snapshot is None or self._manager.error is not None:
            return None
        if self.entity_description.key == "schedule_entries":
            return len(snapshot.entries)
        return cast(str, snapshot.remaining_time["work_mode"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        result: dict[str, Any] = {"read_error": self._manager.error}
        snapshot = self._manager.snapshot
        if snapshot is not None:
            result.update(
                scan_started_at=snapshot.started_at.isoformat(), last_updated=snapshot.finished_at.isoformat()
            )
            if self.entity_description.key == "schedule_entries":
                result["entries"] = snapshot.entries
            else:
                result.update(snapshot.remaining_time)
        return result

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._manager.add_listener(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        self._manager.remove_listener(self.schedule_update_ha_state)
        await super().async_will_remove_from_hass()
