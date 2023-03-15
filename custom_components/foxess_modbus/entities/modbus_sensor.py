"""Sensor"""
import logging

from dataclasses import dataclass
from typing import Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorStateClass
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.config_entries import ConfigEntry

from .modbus_entity_mixin import ModbusEntityMixin
from ..common.callback_controller import CallbackController

_LOGGER = logging.getLogger(__name__)


@dataclass
class SensorDescription(SensorEntityDescription):
    """Custom sensor description"""

    address: int | None = 0
    should_poll: bool | None = False
    scale: float | None = None
    post_process: Callable[[int], int] | None = None


class ModbusSensor(ModbusEntityMixin, SensorEntity):
    """Sensor class."""

    def __init__(
        self,
        controller: CallbackController,
        entity_description: SensorDescription,
        entry: ConfigEntry,
        inv_details,
    ) -> None:
        """Initialize the sensor."""

        self._controller = controller
        self.entity_description = entity_description
        self._entry = entry
        self._inv_details = inv_details
        self.entity_id = "sensor." + self._get_unique_id()

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        value = self._controller.read(self.entity_description.address)
        if value is not None:
            if self.entity_description.scale is not None:
                value = value * self.entity_description.scale
            if self.entity_description.post_process is not None:
                return self.entity_description.post_process(value)

        return value

    @property
    def native_unit_of_measurement(self) -> str:
        """Return native unit of measurement"""
        return self.entity_description.native_unit_of_measurement

    @property
    def state_class(self) -> SensorStateClass:
        """Return the device class of the sensor."""
        return self.entity_description.state_class

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.
        False if entity pushes its state to HA.
        """
        return self.entity_description.should_poll
