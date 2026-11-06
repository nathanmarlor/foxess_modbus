from datetime import time
from typing import Any
from typing import cast

from custom_components.foxess_modbus.entities.modbus_charge_period_config import ModbusChargePeriodAddressConfig
from custom_components.foxess_modbus.entities.modbus_charge_period_config import ModbusChargePeriodInfo
from custom_components.foxess_modbus.services.update_charge_period_service import ChargePeriod
from custom_components.foxess_modbus.services.update_charge_period_service import _build_write_blocks


class _FakeController:
    """Minimal stand-in for ModbusController, exposing only what the charge-period writer needs."""

    def __init__(
        self,
        charge_periods: list[ModbusChargePeriodInfo],
        *,
        capacity: int = 10_000,
        registers: dict[int, int] | None = None,
    ) -> None:
        self.charge_periods = charge_periods
        self.inverter_capacity = capacity
        self._registers = registers or {}

    def read(self, address: int | list[int], *, signed: bool) -> int | None:  # noqa: ARG002
        if not isinstance(address, int):
            raise AssertionError("The charge-period writer must only read single registers")
        return self._registers.get(address)


def _info(**addresses: int) -> ModbusChargePeriodInfo:
    return ModbusChargePeriodInfo(
        addresses=ModbusChargePeriodAddressConfig(**addresses),
        period_start_entity_id="start",
        period_end_entity_id="end",
        enable_force_charge_entity_id="force_charge",
        enable_charge_from_grid_entity_id="charge_from_grid",
    )


def _time_group_info(base: int) -> ModbusChargePeriodInfo:
    return _info(
        period_start_address=base + 1,
        period_end_address=base + 2,
        enable_charge_from_grid_address=base + 6,
        enable_address=base,
        work_mode_address=base + 3,
        soc_address=base + 4,
        fdsoc_address=base + 5,
        fdpwr_address=base + 6,
        enable_flag_address=base + 9,
        max_soc_global_address=46620,
        min_soc_global_address=46611,
    )


def _controller(
    charge_periods: list[ModbusChargePeriodInfo],
    *,
    capacity: int = 10_000,
    registers: dict[int, int] | None = None,
) -> Any:
    return cast(Any, _FakeController(charge_periods, capacity=capacity, registers=registers))


def test_enabled_time_group_is_written_as_a_complete_block() -> None:
    controller = _controller(
        [_time_group_info(48010), _time_group_info(48020)],
        capacity=12_000,
        registers={46620: 90, 46611: 20},
    )
    periods = [
        ChargePeriod(enable_force_charge=True, enable_charge_from_grid=True, start=time(2, 0), end=time(5, 30)),
        ChargePeriod(enable_force_charge=True, enable_charge_from_grid=False, start=time(18, 0), end=time(20, 0)),
    ]

    blocks = _build_write_blocks(controller, periods)

    assert blocks[0] == (48010, [1, 2 << 8, 5 << 8 | 30, 6, 90 << 8 | 20, 90, 12_000, 0, 0, 1])
    assert blocks[1] == (48020, [1, 18 << 8, 20 << 8, 6, 90 << 8 | 20, 90, 0, 0, 0, 2])
    # The global Time Mode Flag is written last, as a full block
    assert blocks[2] == (48000, [1, 0, 0, 0, 0, 0, 0, 0, 0, 0])


def test_disabled_time_group_is_written_as_a_complete_block_and_preserves_configuration() -> None:
    controller = _controller(
        [_time_group_info(48010), _time_group_info(48020)],
        registers={48011: 6 << 8, 48012: 8 << 8, 48013: 2, 46620: 100, 46611: 10},
    )
    periods = [
        ChargePeriod(enable_force_charge=False, enable_charge_from_grid=False, start=time(0, 0), end=time(0, 0)),
        ChargePeriod(enable_force_charge=False, enable_charge_from_grid=False, start=time(0, 0), end=time(0, 0)),
    ]

    blocks = _build_write_blocks(controller, periods)

    # Times and work mode are preserved, but the group is switched off and its force-charge power cleared
    assert blocks[0] == (48010, [0, 6 << 8, 8 << 8, 2, 100 << 8 | 10, 100, 0, 0, 0, 1])
    assert blocks[1] == (48020, [0, 0, 0, 6, 100 << 8 | 10, 100, 0, 0, 0, 2])
    assert blocks[2] == (48000, [0, 0, 0, 0, 0, 0, 0, 0, 0, 0])


def test_time_mode_flag_is_enabled_if_any_period_is_enabled() -> None:
    controller = _controller([_time_group_info(48010), _time_group_info(48020)])
    periods = [
        ChargePeriod(enable_force_charge=False, enable_charge_from_grid=False, start=time(0, 0), end=time(0, 0)),
        ChargePeriod(enable_force_charge=True, enable_charge_from_grid=False, start=time(7, 0), end=time(9, 0)),
    ]

    blocks = _build_write_blocks(controller, periods)

    assert blocks[-1] == (48000, [1, 0, 0, 0, 0, 0, 0, 0, 0, 0])


def test_non_time_group_periods_are_unchanged() -> None:
    controller = _controller(
        [
            _info(period_start_address=41002, period_end_address=41003, enable_charge_from_grid_address=41001),
            _info(period_start_address=41005, period_end_address=41006, enable_charge_from_grid_address=41004),
        ]
    )
    periods = [
        ChargePeriod(enable_force_charge=True, enable_charge_from_grid=True, start=time(1, 0), end=time(2, 0)),
        ChargePeriod(enable_force_charge=False, enable_charge_from_grid=False, start=time(0, 0), end=time(0, 0)),
    ]

    blocks = _build_write_blocks(controller, periods)

    # The H1-style path keeps writing only the three registers it needs, as contiguous runs
    assert blocks == [
        (41001, [1, 1 << 8, 2 << 8]),
        (41004, [0, 0, 0]),
    ]
