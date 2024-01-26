"""Inverter time period configs"""
import logging

from ..const import H1_SET
from ..const import KH
from .modbus_charge_period_config import ChargePeriodAddressSpec
from .modbus_charge_period_config import ModbusChargePeriodAddressConfig
from .modbus_charge_period_config import ModbusChargePeriodFactory

_LOGGER: logging.Logger = logging.getLogger(__package__)

CHARGE_PERIODS = [
    ModbusChargePeriodFactory(
        addresses=[
            ChargePeriodAddressSpec(
                models=[*H1_SET, KH],
                input=ModbusChargePeriodAddressConfig(
                    period_start_address=41002,
                    period_end_address=41003,
                    enable_charge_from_grid_address=41001,
                ),
            )
        ],
        period_start_key="time_period_1_start",
        period_start_name="Period 1 - Start",
        period_end_key="time_period_1_end",
        period_end_name="Period 1 - End",
        enable_force_charge_key="time_period_1_enable_force_charge",
        enable_force_charge_name="Period 1 - Enable Force Charge",
        enable_charge_from_grid_key="time_period_1_enable_charge_from_grid",
        enable_charge_from_grid_name="Period 1 - Enable Charge from Grid",
    ),
    ModbusChargePeriodFactory(
        addresses=[
            ChargePeriodAddressSpec(
                models=[*H1_SET, KH],
                input=ModbusChargePeriodAddressConfig(
                    period_start_address=41005,
                    period_end_address=41006,
                    enable_charge_from_grid_address=41004,
                ),
            )
        ],
        period_start_key="time_period_2_start",
        period_start_name="Period 2 - Start",
        period_end_key="time_period_2_end",
        period_end_name="Period 2 - End",
        enable_force_charge_key="time_period_2_enable_force_charge",
        enable_force_charge_name="Period 2 - Enable Force Charge",
        enable_charge_from_grid_key="time_period_2_enable_charge_from_grid",
        enable_charge_from_grid_name="Period 2 - Enable Charge from Grid",
    ),
]
