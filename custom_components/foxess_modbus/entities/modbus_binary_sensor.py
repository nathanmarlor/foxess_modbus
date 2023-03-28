"""Binary Sensor"""
import logging
from dataclasses import dataclass
from dataclasses import field

from custom_components.foxess_modbus.entities.validation import BaseValidator
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.sensor import SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from .entity_factory import EntityFactory
from .modbus_entity_mixin import ModbusEntityMixin


_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class ModbusBinarySensorDescription(BinarySensorEntityDescription, EntityFactory):
    """Description for ModbusBinarySensor"""

    address: int
    validate: list[BaseValidator] = field(default_factory=list)

    @property
    def entity_type(self) -> type[Entity]:
        return BinarySensorEntity

    @property
    def addresses(self) -> list[int]:
        return [self.address]

    def create_entity(
        self, controller: EntityController, entry: ConfigEntry, inv_details
    ) -> Entity:
        return ModbusBinarySensor(controller, self, entry, inv_details)


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
        if value is None:
            return value
        rules = self.entity_description.validate
        if not self._validate(rules, value):
            return None
        return value

    @property
    def state_class(self) -> SensorStateClass:
        """Return the device class of the sensor."""
        return self.entity_description.state_class

    @property
    def should_poll(self) -> bool:
        return False
