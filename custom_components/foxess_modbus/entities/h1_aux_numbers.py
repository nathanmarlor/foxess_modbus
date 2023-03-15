"""Inverter sensor"""
import logging

from homeassistant.components.number import NumberDeviceClass
from homeassistant.components.number import NumberMode

from .modbus_number import ModbusNumber
from .modbus_number import ModbusNumberDescription

_LOGGER: logging.Logger = logging.getLogger(__package__)

NUMBERS: dict[str, ModbusNumberDescription] = {
    "min_soc": ModbusNumberDescription(
        key="min_soc",
        address=41009,
        name="Min SoC",
        mode=NumberMode.BOX,
        native_min_value=10,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
        device_class=NumberDeviceClass.BATTERY,
    ),
    "min_soc_on_grid": ModbusNumberDescription(
        key="min_soc_on_grid",
        address=41011,
        name="Min SoC (On Grid)",
        mode=NumberMode.BOX,
        native_min_value=10,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
        device_class=NumberDeviceClass.BATTERY,
    ),
    "max_soc": ModbusNumberDescription(
        key="max_soc",
        address=41010,
        name="Max SoC",
        mode=NumberMode.BOX,
        native_min_value=10,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement="%",
        device_class=NumberDeviceClass.BATTERY,
    ),
}


def numbers(controller, entry, inverter) -> list:
    """Setup number platform."""

    return list(
        ModbusNumber(controller, number, entry, inverter) for number in NUMBERS.values()
    )
