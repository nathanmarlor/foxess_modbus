"""Sensor"""
import logging
from dataclasses import dataclass
from dataclasses import field
from typing import Callable

from custom_components.foxess_modbus.entities.validation import BaseValidator
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.sensor import SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from .entity_factory import EntityFactory
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class ModbusSensorDescription(SensorEntityDescription, EntityFactory):
    """Custom sensor description"""

    address: int
    scale: float | None = None
    post_process: Callable[[int], int] | None = None
    validate: list[BaseValidator] = field(default_factory=list)

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

    @property
    def addresses(self) -> list[int]:
        return [self.address]

    def create_entity(
        self, controller: EntityController, entry: ConfigEntry, inv_details
    ) -> Entity:
        return ModbusSensor(controller, self, entry, inv_details)


class ModbusSensor(ModbusEntityMixin, SensorEntity):
    """Sensor class."""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusSensorDescription,
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
        value = original = self._controller.read(self.entity_description.address)

        if value is None:
            return value

        if self.entity_description.scale is not None:
            value = value * self.entity_description.scale
        if self.entity_description.post_process is not None:
            value = self.entity_description.post_process(value)
        rules = self.entity_description.validate
        if not self._validate(rules, value, original):
            return None

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
        return False
