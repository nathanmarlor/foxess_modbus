"""Holds information on the various sensors required to represent a time period"""
import logging
from dataclasses import dataclass

from .modbus_time_period_sensors import ModbusEnableForceChargeSensorDescription
from .modbus_time_period_sensors import ModbusTimePeriodStartEndSensorDescription

_LOGGER = logging.getLogger(__name__)


@dataclass
class ModbusTimePeriodConfig:
    """Holds information on the various sensors required to represent a time period"""

    period_start: ModbusTimePeriodStartEndSensorDescription
    period_end: ModbusTimePeriodStartEndSensorDescription
    enable_force_charge: ModbusEnableForceChargeSensorDescription
