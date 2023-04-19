"""Binary Sensor"""
import logging
from dataclasses import dataclass
from dataclasses import field

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.sensor import SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from .base_validator import BaseValidator
from .entity_factory import EntityFactory
from .inverter_model_spec import ModbusAddressSpec
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class ModbusBinarySensorDescription(BinarySensorEntityDescription, EntityFactory):
    """Description for ModbusBinarySensor"""

    address: list[ModbusAddressSpec]
    validate: list[BaseValidator] = field(default_factory=list)

    @property
    def entity_type(self) -> type[Entity]:
        return BinarySensorEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: str,
        connection_type: str,
        entry: ConfigEntry,
        inv_details,
    ) -> Entity | None:
        address = self._address_for_inverter_model(
            self.address, inverter_model, connection_type
        )
        return (
            ModbusBinarySensor(controller, self, address, entry, inv_details)
            if address is not None
            else None
        )


class ModbusBinarySensor(ModbusEntityMixin, BinarySensorEntity):
    """Modbus binary sensor"""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusBinarySensorDescription,
        address: int,
        entry: ConfigEntry,
        inv_details,
    ) -> None:
        """Initialize the sensor."""

        self._controller = controller
        self.entity_description = entity_description
        self._address = address
        self._entry = entry
        self._inv_details = inv_details
        self.entity_id = "binary_sensor." + self._get_unique_id()

    @property
    def is_on(self) -> bool | None:
        """Return the value reported by the sensor."""
        value = self._controller.read(self._address)
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

    @property
    def addresses(self) -> list[int]:
        return [self._address]
