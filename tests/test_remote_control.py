from typing import Any
from typing import cast

from custom_components.foxess_modbus.common.entity_controller import RemoteControlMode
from custom_components.foxess_modbus.entities.modbus_remote_control_config import ModbusRemoteControlAddressConfig
from custom_components.foxess_modbus.entities.modbus_remote_control_config import WorkMode
from custom_components.foxess_modbus.remote_control_manager import RemoteControlManager


class _FakeController:
    """Minimal stand-in for ModbusController, exposing only what the remote control manager needs."""

    def __init__(self, registers: dict[int, int], *, capacity: int = 12_000) -> None:
        self._registers = registers
        self.inverter_capacity = capacity
        self.is_connected = True
        self.writes: list[tuple[int, Any]] = []

    def read(self, address: int | list[int], *, signed: bool) -> int | None:
        addresses = [address] if isinstance(address, int) else address
        value = 0
        for i, a in enumerate(addresses):
            register = self._registers.get(a)
            if register is None:
                return None
            value |= (register & 0xFFFF) << (i * 16)
        if signed:
            sign_bit = 1 << (len(addresses) * 16 - 1)
            value = (value & (sign_bit - 1)) - (value & sign_bit)
        return value

    async def write_register(self, address: int, value: int) -> None:
        self.writes.append((address, value))

    async def write_registers(self, start_address: int, values: list[int]) -> None:
        self.writes.append((start_address, list(values)))

    def register_modbus_entity(self, _entity: Any) -> None:
        pass


def _addresses() -> ModbusRemoteControlAddressConfig:
    return ModbusRemoteControlAddressConfig(
        remote_enable=46001,
        timeout_set=46002,
        active_power=[46004, 46003],
        work_mode=49203,
        work_mode_map={WorkMode.SELF_USE: 1, WorkMode.FEED_IN_FIRST: 2, WorkMode.BACK_UP: 3},
        max_soc=46610,
        invbatpower=[39238, 39237],
        battery_soc=[37612],
        pwr_limit_bat_up=[46019, 46018],
        pv_voltages=[39070],
    )


def _registers(*, work_mode: int) -> dict[int, int]:
    return {
        37612: 10,  # battery SoC
        46610: 100,  # max SoC
        39070: 800,  # PV1 voltage = 80.0 V -> daylight
        46018: 0,  # pwr_limit_bat_up, low word
        46019: 0,  # pwr_limit_bat_up, high word
        39237: 0xFE0C,  # invbatpower, low word: -500 W
        39238: 0xFFFF,  # invbatpower, high word
        49203: work_mode,
    }


def _manager(controller: _FakeController) -> RemoteControlManager:
    return RemoteControlManager(controller=cast(Any, controller), addresses=_addresses(), poll_rate=15)


async def test_force_charge_keeps_remote_control_enabled_in_back_up() -> None:
    controller = _FakeController(_registers(work_mode=3))  # Back-up
    manager = _manager(controller)

    await manager.set_mode(RemoteControlMode.FORCE_CHARGE)

    # Remote control is enabled and a full-power charge is commanded, instead of disabling force charge
    assert (46002, 30) in controller.writes
    assert (46001, 1) in controller.writes
    assert (46001, 0) not in controller.writes
    assert any(address == 46003 for address, _ in controller.writes)


async def test_force_charge_still_disables_remote_control_when_zero_in_self_use() -> None:
    controller = _FakeController(_registers(work_mode=1))  # Self Use
    manager = _manager(controller)

    await manager.set_mode(RemoteControlMode.FORCE_CHARGE)

    # The reading is trusted in other work modes, so remote control is not enabled (unchanged behaviour)
    assert (46001, 1) not in controller.writes
    assert (49203, 3) in controller.writes
