from dataclasses import dataclass
from typing import Any
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription

from ..common.register_type import RegisterType
from .entity_factory import EntityFactory
from .inverter_model_spec import ModbusAddressesSpec
from .modbus_entity_mixin import ModbusEntityMixin
from ..common.entity_controller import EntityController
from homeassistant.helpers.entity import Entity
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorStateClass

_FAULTS = [
    [
        "Grid Lost Fault",
        "Grid Voltage Fault",
        "Grid Frequency Fault",
        "Grid 10min Voltage Fault",
        "EPS Voltage Fault",
        "Software Inverter Over-current Fault",
        "DCI Fault",
        None,
        "Hardware Inverter Over-current Fault",
        "Software Bus Voltage Fault",
        "Battery Voltage Fault",
        "Software Battery Over-current Fault",
        "Isolation Fault",
        "Residual Over-current Fault",
        "PV Voltage Fault",
        "Software PV Over-current Fault",
    ],
    [
        "Inverter Temperature Fault",
        "Ground Connection Fault",
        "Inverter Overload Fault",
        "EPS Overload Fault",
        "Battery Power Low Fault",
        "Hardware Bus Voltage Fault",
        "Hardware PV Over-current Fault",
        "Hardware Battery Over-current Fault",
        "SCI Fault",
        "Master SPI Fault",
        "BMS Lost Fault",
        None,
        None,
        None,
        None,
        None,
    ],
    [None] * 16,
    [
        "Master Sample Detection Fault",
        "Residual Current Detection Fault",
        "Inverter EEPROM Fault",
        "PV Connection Direction Fault",
        "Battery Relay Open",
        "Battery Relay Short Circuit",
        "Battery Buck Fault",
        "Battery Boost Fault",
        "EPS Relay Fault",
        "Short EPS Load Fault",
        "Battery Connection Direction Fault",
        "Main Relay Open",
        "S1 Close Fault",
        "S2 Close Fault",
        "M1 Close Fault",
        "M2 Close Fault",
    ],
    [
        "Grid Voltage Consistency Fault",
        "Grid Frequency Consistency Fault",
        "DCI Consistency Fault",
        "Residual Current Consistency Fault",
        None,
        None,
        None,
        None,
        "RDSP SPI Fault",
        "RDSP Sample Fault",
        None,
        None,
        None,
        None,
        None,
        None,
    ],
    [
        "ARM EEPROM Fault",
        "Meter Lost Fault",
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
        None,
    ],
    [
        "BMS External Fault",
        "BMS Internal Fault",
        "BMS Voltage High",
        "BMS Voltage Low",
        "BMS Charge Current High",
        "BMS Charge Current Low",
    ],
]


@dataclass(kw_only=True)
class ModbusFaultSensorDescription(SensorEntityDescription, EntityFactory):
    addresses: list[ModbusAddressesSpec]

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: str,
        register_type: RegisterType,
        entry: ConfigEntry,
        inv_details,
    ) -> Entity | None:
        addresses = self._addresses_for_inverter_model(self.addresses, inverter_model, register_type)
        return ModbusFaultSensor(controller, self, addresses, inv_details) if addresses is not None else None


class ModbusFaultSensor(ModbusEntityMixin, SensorEntity):
    """Sensor class."""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusFaultSensorDescription,
        addresses: list[int],
        inv_details,
    ) -> None:
        assert len(addresses) == 8

        self._controller = controller
        self.entity_description = entity_description
        self._addresses = addresses
        self._inv_details = inv_details
        self.entity_id = "sensor." + self._get_unique_id()

    @property
    def native_value(self) -> Any:
        return None

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def addresses(self) -> list[int]:
        return self._addresses
