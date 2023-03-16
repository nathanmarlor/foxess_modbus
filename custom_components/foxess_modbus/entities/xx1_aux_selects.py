"""Inverter Select entities"""
import logging

from custom_components.foxess_modbus.const import AC1
from custom_components.foxess_modbus.const import H1

from .modbus_select import ModbusSelect
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

COMPAT: dict[str, list] = {H1: SELECTS, AC1: SELECTS}


def selects(base_model, controller, entry, inverter) -> list:
    """Setup select platform."""

    return list(
        ModbusSelect(controller, select, entry, inverter)
        for select in COMPAT[base_model]
    )
