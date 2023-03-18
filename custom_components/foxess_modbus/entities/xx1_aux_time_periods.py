"""Inverter sensor"""
import logging

from .modbus_time_period_config import ModbusTimePeriodConfig

_LOGGER: logging.Logger = logging.getLogger(__package__)

H1_AC1_PERIODS = [
    ModbusTimePeriodConfig(
        period_start_key="time_period_1_start",
        period_start_name="Period 1 - Start",
        period_start_address=41002,
        period_end_key="time_period_1_end",
        period_end_name="Period 1 - End",
        period_end_address=41003,
        enable_force_charge_key="time_period_1_enable_force_charge",
        enable_force_charge_name="Period 1 - Enable force charge",
        enable_charge_from_grid_key="time_period_1_enabled",
        enable_charge_from_grid_name="Period 1 - Enable charge from grid",
        enable_charge_from_grid_address=41001,
    ),
    ModbusTimePeriodConfig(
        period_start_key="time_period_2_start",
        period_start_name="Period 2 - Start",
        period_start_address=41005,
        period_end_key="time_period_2_end",
        period_end_name="Period 2 - End",
        period_end_address=41006,
        enable_force_charge_key="time_period_2_enable_force_charge",
        enable_force_charge_name="Period 2 - Enable force charge",
        enable_charge_from_grid_key="time_period_2_enabled",
        enable_charge_from_grid_name="Period 2 - Enable charge from grid",
        enable_charge_from_grid_address=41004,
    ),
]
