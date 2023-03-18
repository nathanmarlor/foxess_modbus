"""Sensor"""
import logging
from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.config_entries import ConfigEntry

from ..common.entity_controller import EntityController
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class ModbusEnableForceChargeSensorDescription(BinarySensorEntityDescription):
    """Custom sensor description"""

    period_start_address: int
    period_end_address: int


class ModbusEnableForceChargeSensor(ModbusEntityMixin, BinarySensorEntity):
    """Sensor class."""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusEnableForceChargeSensorDescription,
        entry: ConfigEntry,
        inv_details,
    ) -> None:
        self._controller = controller
        self.entity_description = entity_description
        self._entry = entry
        self._inv_details = inv_details
        self.entity_id = "binary_sensor." + self._get_unique_id()
        self._attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    @property
    def is_on(self) -> bool | None:
        start_time = self._controller.read(self.entity_description.period_start_address)
        end_time = self._controller.read(self.entity_description.period_end_address)
        return (start_time is not None and start_time > 0) and (
            end_time is not None and end_time > 0
        )

    @property
    def should_poll(self) -> bool:
        return False

    def update_callback(self, changed_addresses: set[int]) -> None:
        """Schedule a state update."""
        if (self.entity_description.period_start_address in changed_addresses) or (
            self.entity_description.period_end_address in changed_addresses
        ):
            self.schedule_update_ha_state(True)
