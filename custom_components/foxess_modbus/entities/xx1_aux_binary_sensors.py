"""Inverter sensor"""
import logging

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
