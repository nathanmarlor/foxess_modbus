"""Decodes the fault registers"""
from dataclasses import dataclass
from typing import Any
from typing import cast

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.register_type import RegisterType
from .entity_factory import EntityFactory
from .inverter_model_spec import ModbusAddressSpec
from .modbus_entity_mixin import ModbusEntityMixin

H1_INVERTER_STATES = [
    "Waiting",
    "Checking",
    "On Grid",
    "Off Grid / EPS",
    "Recoverable Fault",
    "Unrecoverable Fault",
]

KH_INVERTER_STATES = [
    "Self Test",
    "Waiting",
    "Checking",
    "On Grid",
    "Off Grid / EPS",
    "Recoverable Fault",
    "Unrecoverable Fault",
]


@dataclass(kw_only=True)
class ModbusInverterStateSensorDescription(SensorEntityDescription, EntityFactory):
    """Description for ModbusInverterStateSensor"""

    address: list[ModbusAddressSpec]
    states: list[str]

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: str,
        register_type: RegisterType,
        _entry: ConfigEntry,
        inv_details: dict[str, Any],
    ) -> Entity | None:
        address = self._address_for_inverter_model(self.address, inverter_model, register_type)
        return ModbusInverterStateSensor(controller, self, address, inv_details) if address is not None else None


class ModbusInverterStateSensor(ModbusEntityMixin, SensorEntity):
    """Sensor class."""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusInverterStateSensorDescription,
        address: int,
        inv_details: dict[str, Any],
    ) -> None:
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = entity_description.states

        self._controller = controller
        self.entity_description = entity_description
        self._address = address
        self._inv_details = inv_details
        self.entity_id = "sensor." + self._get_unique_id()

    @property
    def native_value(self) -> str | None:
        entity_description = cast(ModbusInverterStateSensorDescription, self.entity_description)
        value = self._controller.read(self._address)
        if value is None or value >= len(entity_description.states):
            return None
        return entity_description.states[value]

    @property
    def addresses(self) -> list[int]:
        return [self._address]
