"""Inverter sensor"""
import logging

from .modbus_time_period_config import ModbusTimePeriodConfig
from .modbus_time_period_sensors import ModbusEnableForceChargeSensorDescription
from .modbus_time_period_sensors import ModbusTimePeriodStartEndSensorDescription

_LOGGER: logging.Logger = logging.getLogger(__package__)

H1_AC1_PERIODS = [
    ModbusTimePeriodConfig(
        period_start=ModbusTimePeriodStartEndSensorDescription(
            key="time_period_1_start",
            address=41002,
            other_address=41003,
            name="Period 1 - Start",
        ),
        period_end=ModbusTimePeriodStartEndSensorDescription(
            key="time_period_1_end",
            address=41003,
            other_address=41002,
            name="Period 1 - End",
        ),
        enable_force_charge=ModbusEnableForceChargeSensorDescription(
            key="time_period_1_enable_force_charge",
            name="Period 1 - Enable force charge",
            period_start_address=41002,
            period_end_address=41003,
        ),
    ),
    ModbusTimePeriodConfig(
        period_start=ModbusTimePeriodStartEndSensorDescription(
            key="time_period_2_start",
            address=41005,
            other_address=41006,
            name="Period 2 - Start",
        ),
        period_end=ModbusTimePeriodStartEndSensorDescription(
            key="time_period_2_end",
            address=41006,
            other_address=41005,
            name="Period 2 - End",
        ),
        enable_force_charge=ModbusEnableForceChargeSensorDescription(
            key="time_period_2_enable_force_charge",
            name="Period 2 - Enable force charge",
            period_start_address=41005,
            period_end_address=41006,
        ),
    ),
]
