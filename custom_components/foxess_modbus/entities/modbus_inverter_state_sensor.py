"""Decodes the fault registers"""

from dataclasses import dataclass
from typing import Any
from typing import cast

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import Platform
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.types import Inv
from ..common.types import RegisterType
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .inverter_model_spec import ModbusAddressesSpec
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


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
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
        inverter_model: Inv,
        register_type: RegisterType,
    ) -> Entity | None:
        address = self._address_for_inverter_model(self.address, inverter_model, register_type)
        return ModbusInverterStateSensor(controller, self, address) if address is not None else None

    def serialize(self, inverter_model: Inv) -> dict[str, Any] | None:
        address_map = self._addresses_for_serialization(self.address, inverter_model)
        if address_map is None:
            return None

        return {
            "type": "inverter-state-sensor",
            "key": self.key,
            "name": self.name,
            "addresses": address_map,
            "states": self.states,
        }


class ModbusInverterStateSensor(ModbusEntityMixin, SensorEntity):
    """Sensor class."""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusInverterStateSensorDescription,
        address: int,
    ) -> None:
        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = entity_description.states

        self._controller = controller
        self.entity_description = entity_description
        self._address = address
        self.entity_id = self._get_entity_id(Platform.SENSOR)

    @property
    def native_value(self) -> str | None:
        entity_description = cast(ModbusInverterStateSensorDescription, self.entity_description)
        value = self._controller.read(self._address, signed=False)
        if value is None or value >= len(entity_description.states):
            return None
        return entity_description.states[value]

    @property
    def addresses(self) -> list[int]:
        return [self._address]


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusG2InverterStateSensorDescription(SensorEntityDescription, EntityFactory):
    """Description for ModbusInverterStateSensor"""

    # Fault 1 code, fault 3 code
    addresses: list[ModbusAddressesSpec]

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: Inv,
        register_type: RegisterType,
    ) -> Entity | None:
        addresses = self._addresses_for_inverter_model(self.addresses, inverter_model, register_type)
        return ModbusG2InverterStateSensor(controller, self, addresses) if addresses is not None else None

    def serialize(self, inverter_model: Inv) -> dict[str, Any] | None:
        address_map = self._addresses_for_serialization(self.addresses, inverter_model)
        if address_map is None:
            return None

        return {
            "type": "inverter-state-sensor",
            "key": self.key,
            "name": self.name,
            "addresses": address_map,
        }


class ModbusG2InverterStateSensor(ModbusEntityMixin, SensorEntity):
    """Sensor class."""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusG2InverterStateSensorDescription,
        addresses: list[int],
    ) -> None:
        assert len(addresses) == 2

        self._attr_device_class = SensorDeviceClass.ENUM
        self._attr_options = ["Fault", "Off Grid", "On Grid", "Standby"]

        self._controller = controller
        self.entity_description = entity_description
        self._addresses = addresses
        self.entity_id = self._get_entity_id(Platform.SENSOR)

    @property
    def native_value(self) -> str | None:
        # Bit 0: Standby, 2: Operation, 6: Fault
        status1 = self._controller.read(self._addresses[0], signed=False)
        # Bit 0: On-Grid/Off-grid (0/1)
        status3 = self._controller.read(self._addresses[1], signed=False)
        if status1 is None or status3 is None:
            return None

        if (status1 & 0x40) > 0:
            return "Fault"
        if (status3 & 0x01) > 0:
            return "Off Grid"
        if (status1 & 0x04) > 0:
            return "On Grid"
        if (status1 & 0x01) > 0:
            return "Standby"
        return None

    @property
    def addresses(self) -> list[int]:
        return self._addresses
