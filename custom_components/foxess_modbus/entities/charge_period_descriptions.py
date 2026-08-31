"""Inverter time period configs"""

import logging

from ..common.types import Inv
from .modbus_charge_period_config import ChargePeriodAddressSpec
from .modbus_charge_period_config import ModbusChargePeriodAddressConfig
from .modbus_charge_period_config import ModbusChargePeriodFactory

_LOGGER: logging.Logger = logging.getLogger(__package__)


# The H3 Smart (and H3 Pro, which shares the same register map) defines its charge periods via the
# time-group system (Table 3-11). Each group is a contiguous block of 10 registers, starting at
# 48010 + 10*(N-1). We use groups 1 and 2, which are the same groups the FoxESS app uses for its charge
# periods, so that the card and the app stay in sync. Unlike the H1, force charge is controlled by a
# dedicated enable register (the group's enable), rather than being inferred from the start/end times, so
# these factories use enable_force_charge_from_enable_address=True.
def _h3_group_base(group: int) -> int:
    """Returns the base address of the given time group (1-based)."""
    return 48010 + 10 * (group - 1)


def _h3_charge_period_factory(
    group: int,
    period_start_key: str,
    period_start_name: str,
    period_end_key: str,
    period_end_name: str,
    enable_force_charge_key: str,
    enable_force_charge_name: str,
    enable_charge_from_grid_key: str,
    enable_charge_from_grid_name: str,
) -> ModbusChargePeriodFactory:
    base = _h3_group_base(group)
    return ModbusChargePeriodFactory(
        addresses=[
            ChargePeriodAddressSpec(
                holding=ModbusChargePeriodAddressConfig(
                    period_start_address=base + 1,
                    period_end_address=base + 2,
                    # 'Enable charge from grid' is determined by whether the force-charge power (FDPWR,
                    # offset +6) is non-zero. We point this at the FDPWR register so that the resulting
                    # binary sensor (device class power) also serves as the marker entity that the
                    # charge-period card uses to discover supported inverters.
                    enable_charge_from_grid_address=base + 6,
                    enable_address=base,
                    work_mode_address=base + 3,
                    soc_address=base + 4,
                    fdsoc_address=base + 5,
                    fdpwr_address=base + 6,
                    enable_flag_address=base + 9,
                    # The global Max SoC / Min SoC OnGrid registers are mirrored into the group's SoC
                    # bounds (offset +4), matching how the FoxESS app configures a charge period.
                    max_soc_global_address=46610,
                    min_soc_global_address=46611,
                ),
                models=Inv.H3_PRO_SET | Inv.H3_SMART,
            ),
        ],
        period_start_key=period_start_key,
        period_start_name=period_start_name,
        period_end_key=period_end_key,
        period_end_name=period_end_name,
        enable_force_charge_key=enable_force_charge_key,
        enable_force_charge_name=enable_force_charge_name,
        enable_charge_from_grid_key=enable_charge_from_grid_key,
        enable_charge_from_grid_name=enable_charge_from_grid_name,
        enable_force_charge_from_enable_address=True,
    )


CHARGE_PERIODS = [
    ModbusChargePeriodFactory(
        addresses=[
            ChargePeriodAddressSpec(
                input=ModbusChargePeriodAddressConfig(
                    period_start_address=41002,
                    period_end_address=41003,
                    enable_charge_from_grid_address=41001,
                ),
                models=Inv.H1_G1 | Inv.KH_PRE119,
            ),
            ChargePeriodAddressSpec(
                holding=ModbusChargePeriodAddressConfig(
                    period_start_address=41002,
                    period_end_address=41003,
                    enable_charge_from_grid_address=41001,
                ),
                models=Inv.H1_G2_SET | Inv.EVO,
            ),
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
                input=ModbusChargePeriodAddressConfig(
                    period_start_address=41005,
                    period_end_address=41006,
                    enable_charge_from_grid_address=41004,
                ),
                models=Inv.H1_G1 | Inv.KH_PRE119,
            ),
            ChargePeriodAddressSpec(
                holding=ModbusChargePeriodAddressConfig(
                    period_start_address=41005,
                    period_end_address=41006,
                    enable_charge_from_grid_address=41004,
                ),
                models=Inv.H1_G2_SET | Inv.EVO,
            ),
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
    _h3_charge_period_factory(
        1,
        "time_period_1_start",
        "Period 1 - Start",
        "time_period_1_end",
        "Period 1 - End",
        "time_period_1_enable_force_charge",
        "Period 1 - Enable Force Charge",
        "time_period_1_enable_charge_from_grid",
        "Period 1 - Enable Charge from Grid",
    ),
    _h3_charge_period_factory(
        2,
        "time_period_2_start",
        "Period 2 - Start",
        "time_period_2_end",
        "Period 2 - End",
        "time_period_2_enable_force_charge",
        "Period 2 - Enable Force Charge",
        "time_period_2_enable_charge_from_grid",
        "Period 2 - Enable Charge from Grid",
    ),
]
