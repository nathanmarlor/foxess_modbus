"""Inverter Select entities"""
import logging

from .modbus_select import ModbusSelectDescription

_LOGGER: logging.Logger = logging.getLogger(__package__)

SELECTS: list[ModbusSelectDescription] = [
    ModbusSelectDescription(
        key="work_mode",
        address=41000,
        name="Work Mode",
        options_map={0: "Self Use", 1: "Feed-in First", 2: "Back-up"},
    ),
]
