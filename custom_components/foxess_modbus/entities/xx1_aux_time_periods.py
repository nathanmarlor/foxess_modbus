"""Inverter sensor"""
import logging

from .modbus_enable_force_charge_sensor import ModbusEnableForceChargeSensorDescription
from .modbus_time_period_config import ModbusTimePeriodConfig

_LOGGER: logging.Logger = logging.getLogger(__package__)

H1_PERIODS = [
    ModbusTimePeriodConfig(
        enable_force_charge=ModbusEnableForceChargeSensorDescription(
            key="time_period_1_enable_force_charge",
            name="Period 1 - Enable force charge",
            period_start_address=41002,
            period_end_address=41003,
        )
    ),
    ModbusTimePeriodConfig(
        enable_force_charge=ModbusEnableForceChargeSensorDescription(
            key="time_period_2_enable_force_charge",
            name="Period 2 - Enable force charge",
            period_start_address=41005,
            period_end_address=41006,
        )
    ),
]
