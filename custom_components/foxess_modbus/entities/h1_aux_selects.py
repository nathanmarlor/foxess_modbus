"""Inverter Select entities"""
import logging

from .modbus_select import ModbusSelectDescription
from .modbus_select import ModbusSelect

_LOGGER: logging.Logger = logging.getLogger(__package__)


SELECTS: dict[str, ModbusSelectDescription] = {
    "work_mode": ModbusSelectDescription(
        key="work_mode",
        address=41000,
        name="Work Mode",
        options_map={0: "Self Use", 1: "Feed-in First", 2: "Back-up"},
    ),
}


def selects(controller, entry, inverter) -> list:
    """Setup select platform."""

    return list(
        ModbusSelect(controller, select, entry, inverter) for select in SELECTS.values()
    )
