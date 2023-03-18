"""Binary Sensor"""
import logging
from dataclasses import dataclass

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.sensor import SensorStateClass
from homeassistant.config_entries import ConfigEntry

from ..common.entity_controller import EntityController
from .modbus_entity_mixin import ModbusEntityMixin


_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class ModbusBinarySensorDescription(BinarySensorEntityDescription):
    """Description for ModbusBinarySensor"""

    address: int


class ModbusBinarySensor(ModbusEntityMixin, BinarySensorEntity):
    """Modbus binary sensor"""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusBinarySensorDescription,
        entry: ConfigEntry,
        inv_details,
    ) -> None:
        """Initialize the sensor."""

        self._controller = controller
        self.entity_description = entity_description
        self._entry = entry
        self._inv_details = inv_details
        self.entity_id = "binary_sensor." + self._get_unique_id()

    @property
    def is_on(self) -> bool | None:
        """Return the value reported by the sensor."""
        value = self._controller.read(self.entity_description.address)
        return value

    @property
    def state_class(self) -> SensorStateClass:
        """Return the device class of the sensor."""
        return self.entity_description.state_class

    @property
    def should_poll(self) -> bool:
        return False
