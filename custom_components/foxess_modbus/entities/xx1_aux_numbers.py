"""Inverter sensor"""
import logging

from custom_components.foxess_modbus.const import AC1
from custom_components.foxess_modbus.const import H1
from homeassistant.components.number import NumberDeviceClass
from homeassistant.components.number import NumberMode

from .modbus_number import ModbusNumber
from .modbus_number import ModbusNumberDescription

_LOGGER: logging.Logger = logging.getLogger(__package__)

NUMBERS: list[ModbusNumberDescription] = [
    ModbusNumberDescription(
        key="min_soc",
        address=41009,
        name="Min SoC",
        mode=NumberMode.BOX,
        native_min_value=10,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
        device_class=NumberDeviceClass.BATTERY,
        icon="mdi:battery-arrow-down",
    ),
    ModbusNumberDescription(
        key="min_soc_on_grid",
        address=41011,
        name="Min SoC (On Grid)",
        mode=NumberMode.BOX,
        native_min_value=10,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
        device_class=NumberDeviceClass.BATTERY,
        icon="mdi:battery-arrow-down",
    ),
    ModbusNumberDescription(
        key="max_soc",
        address=41010,
        name="Max SoC",
        mode=NumberMode.BOX,
        native_min_value=10,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
        device_class=NumberDeviceClass.BATTERY,
        icon="mdi:battery-arrow-up",
    ),
]

COMPAT: dict[str, list] = {H1: NUMBERS, AC1: NUMBERS}


def numbers(base_model, controller, entry, inverter) -> list:
    """Setup number platform."""

    return list(
        ModbusNumber(controller, number, entry, inverter)
        for number in COMPAT[base_model]
    )
