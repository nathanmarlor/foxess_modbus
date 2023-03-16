"""Inverter sensor"""
import logging

from .modbus_sensor import ModbusSensor
from .modbus_sensor import SensorDescription

_LOGGER: logging.Logger = logging.getLogger(__package__)

SENSORS: dict[str, SensorDescription] = {
    "time_period_1_enabled": SensorDescription(
        key="time_period_1_enabled",
        address=41001,
        name="Period 1 - Enabled",
        post_process=lambda v: "On" if v else "Off",
    ),
    "time_period_2_enabled": SensorDescription(
        key="time_period_2_enabled",
        address=41004,
        name="Period 2 - Enabled",
        post_process=lambda v: "On" if v else "Off",
    ),
}


def binary_sensors(controller, entry, inverter) -> list:
    """Setup sensor platform."""
    entities = []

    for sensor in SENSORS:
        sen = ModbusSensor(controller, SENSORS[sensor], entry, inverter)
        entities.append(sen)

    return entities
