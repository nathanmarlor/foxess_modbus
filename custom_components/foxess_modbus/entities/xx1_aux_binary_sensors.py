"""Inverter sensor"""
import logging

from .modbus_binary_sensor import ModbusBinarySensorDescription

_LOGGER: logging.Logger = logging.getLogger(__package__)

SENSORS: list[ModbusBinarySensorDescription] = [
    ModbusBinarySensorDescription(
        key="time_period_1_enabled",
        address=41001,
        name="Period 1 - Enabled",
    ),
    ModbusBinarySensorDescription(
        key="time_period_2_enabled",
        address=41004,
        name="Period 2 - Enabled",
    ),
]
