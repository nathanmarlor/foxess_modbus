"""Sensor"""
import logging
from dataclasses import dataclass
from dataclasses import field
from typing import Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.sensor import SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from .base_validator import BaseValidator
from .entity_factory import EntityFactory
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class ModbusSensorDescription(SensorEntityDescription, EntityFactory):
    """Custom sensor description"""

    # Array of registers which this value is split over, from lower-order bits to higher-order bits
    addresses: list[int]
    _addresses: list[int] = field(init=False, repr=False)
    scale: float | None = None
    post_process: Callable[[int], int] | None = None
    validate: list[BaseValidator] = field(default_factory=list)
    signed: bool = True

    @property
    def addresses(self) -> list[int]:
        return self._addresses

    @addresses.setter
    def addresses(self, value: list[int]) -> None:
        self._addresses = value

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

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
        self._attr_unique_id = "sensor." + self._get_unique_id()

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        original = 0
        for i, address in enumerate(self.entity_description.addresses):
            register_value = self._controller.read(address)
            if register_value is None:
                return None
            original |= (register_value & 0xFFFF) << (i * 16)

        if self.entity_description.signed:
            sign_bit = 1 << (len(self.entity_description.addresses) * 16 - 1)
            original = (original & (sign_bit - 1)) - (original & sign_bit)

        value = original

        if self.entity_description.scale is not None:
            value = value * self.entity_description.scale
        if self.entity_description.post_process is not None:
            value = self.entity_description.post_process(value)
        if not self._validate(self.entity_description.validate, value, original):
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
