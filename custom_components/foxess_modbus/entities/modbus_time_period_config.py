"""Holds information on the various sensors required to represent a time period"""
import logging
from dataclasses import dataclass

from .modbus_enable_force_charge_sensor import ModbusEnableForceChargeSensorDescription

_LOGGER = logging.getLogger(__name__)


@dataclass
class ModbusTimePeriodConfig:
    """Holds information on the various sensors required to represent a time period"""

    enable_force_charge: ModbusEnableForceChargeSensorDescription
