"""Decodes the fault registers"""
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.register_type import RegisterType
from .entity_factory import EntityFactory
from .inverter_model_spec import ModbusAddressesSpec
from .modbus_entity_mixin import ModbusEntityMixin

_FAULTS: list[list[str | None]] = [
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
    # Fault Code 3 is empty, so we don't bother reading it
    # [None] * 16,
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
        "Slave SPI Fault",
        "Slave Sample Fault",
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
        "Battery Over-voltage",
        "Battery under-voltage",
        "BMS Charge Over-current",
        "BMS Discharge Over-current",
        "BMS Over-temperature",
        "BMS Under-temperature",
        "BMS Cell Imbalance",
        "BMS Hardware Protection Fault",
        "BMS Circuit Fault",
        "BMS Insulation Fault",
        "BMS Voltage Sensor Fault",
        "BMS Temperature Sensor Fault",
        "BMS Current Sensor Fault",
        "BMS Relay Fault",
    ],
    [
        "BMS Type Mismatch",
        "BMS Version Mismatch",
        "BMS Manufacturer Mismatch",
        "BMS Software/Hardware Mismatch",
        "BMS Master/Slave Mismatch",
        "BMS Charge Request Not Acknowledged",
        "BMS Supply Fault",
        None,
        "BMS Self Check Fault",
        "BMS Cell Temperature Difference Fault",
        "BMS Cell Voltage Break Line Fault",
        "BMS Self Check Voltage Mismatch Fault",
        "BMS Precharge Fault",
        "BMS Self Check HVB Fault",
        "BMS Self Check Pack Current Fault",
        "BMS Self Check Sys Mismatch Fault",
    ],
]

# Processed in order. If key is active, any faults in value will be removed
_MASKS = {"Grid Lost Fault": ["Grid Voltage Fault", "Grid Frequency Fault"]}

for assert_fault, assert_masks in _MASKS.items():
    assert any(fault for fault_list in _FAULTS for fault in fault_list if fault == assert_fault)
    for assert_mask in assert_masks:
        assert any(fault for fault_list in _FAULTS for fault in fault_list if fault == assert_mask)


@dataclass(kw_only=True)
class ModbusFaultSensorDescription(SensorEntityDescription, EntityFactory):
    """Description for ModbusFaultSensor"""

    addresses: list[ModbusAddressesSpec]

    # We can't quite be SensorDeviceClass.ENUM, as we can return multiple faults

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
        addresses = self._addresses_for_inverter_model(self.addresses, inverter_model, register_type)
        return ModbusFaultSensor(controller, self, addresses, inv_details) if addresses is not None else None


class ModbusFaultSensor(ModbusEntityMixin, SensorEntity):
    """Sensor class."""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusFaultSensorDescription,
        addresses: list[int],
        inv_details: dict[str, Any],
    ) -> None:
        assert len(addresses) == len(_FAULTS)

        self._controller = controller
        self.entity_description = entity_description
        self._addresses = addresses
        self._inv_details = inv_details
        self.entity_id = "sensor." + self._get_unique_id()

    @property
    def native_value(self) -> str | None:
        faults = []
        for i, address in enumerate(self._addresses):
            value = self._controller.read(address)
            if value is None:
                return None
            if value != 0:
                for index, fault_code in enumerate(_FAULTS[i]):
                    if fault_code is not None and (value & (1 << index)) > 0:
                        faults.append(fault_code)

        if len(faults) == 0:
            return "None"

        to_remove: set[str] = set()
        for fault in faults:
            masks = _MASKS.get(fault, [])
            for mask in masks:
                if mask in faults:
                    to_remove.add(mask)
        for fault_to_remove in to_remove:
            faults.remove(fault_to_remove)

        return "; ".join(faults)

    @property
    def addresses(self) -> list[int]:
        return self._addresses
