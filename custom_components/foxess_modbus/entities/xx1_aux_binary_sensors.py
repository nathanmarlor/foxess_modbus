"""Inverter sensor"""
import logging

from custom_components.foxess_modbus.const import AC1
from custom_components.foxess_modbus.const import H1

from .modbus_sensor import ModbusSensor
from .modbus_sensor import SensorDescription

_LOGGER: logging.Logger = logging.getLogger(__package__)

SENSORS: list[SensorDescription] = [
    SensorDescription(
        key="time_period_1_enabled",
        address=41001,
        name="Period 1 - Enabled",
        post_process=lambda v: "On" if v else "Off",
    ),
    SensorDescription(
        key="time_period_2_enabled",
        address=41004,
        name="Period 2 - Enabled",
        post_process=lambda v: "On" if v else "Off",
    ),
]


COMPAT: dict[str, list] = {H1: SENSORS, AC1: SENSORS}


def binary_sensors(base_model, controller, entry, inverter) -> list:
    """Setup binary sensor platform."""

    return list(
        ModbusSensor(controller, number, entry, inverter)
        for number in COMPAT[base_model]
    )
