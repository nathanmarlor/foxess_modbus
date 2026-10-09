"""Remote enable bit preservation and PQ1 control through the shared manager."""

from dataclasses import replace
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import call

import pytest

from custom_components.foxess_modbus.common.entity_controller import EntityController
from custom_components.foxess_modbus.common.entity_controller import RemoteControlMode
from custom_components.foxess_modbus.common.types import Inv
from custom_components.foxess_modbus.common.types import RegisterType
from custom_components.foxess_modbus.entities.modbus_remote_control_config import ModbusRemoteControlAddressConfig
from custom_components.foxess_modbus.entities.modbus_remote_control_config import WorkMode
from custom_components.foxess_modbus.entities.remote_control_description import REMOTE_CONTROL_DESCRIPTION
from custom_components.foxess_modbus.inverter_profiles import INVERTER_PROFILES
from custom_components.foxess_modbus.remote_control_manager import RemoteControlManager


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "legacy_config" not in metafunc.fixturenames:
        return
    inputs = []
    for model, profile in INVERTER_PROFILES.items():
        for connection, connection_profile in profile.connection_types.items():
            for version in connection_profile.versions:
                inv = connection_profile.get_inv_for_version(version)
                if inv == Inv.PQ1:
                    continue
                config = REMOTE_CONTROL_DESCRIPTION.create_if_supported(
                    MagicMock(spec=EntityController), inv, connection_profile.register_type
                )
                if config is not None:
                    inputs.append(pytest.param(config, id=f"{model}-{connection}-{version}"))
    metafunc.parametrize("legacy_config", inputs)


@pytest.fixture
def controller() -> MagicMock:
    result = MagicMock(spec=EntityController)
    result.is_connected = True
    result.inverter_capacity = 8000
    result.read.side_effect = lambda address, **_: {
        31024: 73,
        41010: 100,
        39070: 985,
        39072: 811,
        39074: 1499,
        39076: 340,
        (39238, 39237): 620,
    }.get(tuple(address) if isinstance(address, list) else address)
    result.read_registers = AsyncMock(return_value=[12])
    result.read_registers.side_effect = (
        lambda address, *_: [60] if address == 46002 else result.read_registers.return_value
    )
    return result


@pytest.fixture
def config(controller: MagicMock) -> ModbusRemoteControlAddressConfig:
    result = REMOTE_CONTROL_DESCRIPTION.create_if_supported(controller, Inv.PQ1, RegisterType.HOLDING)
    assert result is not None
    return result


@pytest.fixture
def manager(controller: MagicMock, config: ModbusRemoteControlAddressConfig) -> RemoteControlManager:
    return RemoteControlManager(controller, config, 10)


async def test_pq1_charge_and_disable_preserve_fresh_bits(controller: MagicMock, manager: RemoteControlManager) -> None:
    # A connected idle manager must not take ownership of app control.
    await manager.poll_complete_callback()
    controller.write_register.assert_not_awaited()
    controller.write_registers.assert_not_awaited()
    manager.charge_power = 600
    await manager.set_mode(RemoteControlMode.FORCE_CHARGE)
    assert controller.write_register.await_args_list == [call(46002, 20), call(46001, 13)]
    controller.write_registers.assert_awaited_once_with(46003, [65535, 64936])
    assert controller.read_registers.await_args_list == [
        call(46002, 1, RegisterType.HOLDING),
        call(46001, 1, RegisterType.HOLDING),
    ]

    # Preserve a different target, direction and upper bits changed since enabling.
    controller.read_registers.return_value = [0x800B]
    await manager.set_mode(RemoteControlMode.DISABLE)
    assert controller.write_register.await_args_list[-2:] == [call(46001, 0x800A), call(46002, 60)]
    assert controller.read_registers.await_count == 3
    assert all(c.args[0] not in {41000, 49203, 48000} for c in controller.write_register.await_args_list)


async def test_pq1_discharge_packing_and_refresh(controller: MagicMock, manager: RemoteControlManager) -> None:
    manager.discharge_power = 700
    await manager.set_mode(RemoteControlMode.FORCE_DISCHARGE)
    await manager.poll_complete_callback()
    assert controller.write_registers.await_args_list == [call(46003, [0, 700]), call(46003, [0, 700])]
    # Timeout/enable are established once; the power command refreshes the watchdog.
    assert controller.write_register.await_args_list == [call(46002, 20), call(46001, 13)]


async def test_pq1_soc_cutoff(controller: MagicMock, manager: RemoteControlManager) -> None:
    await manager.set_mode(RemoteControlMode.FORCE_CHARGE)
    controller.read.side_effect = lambda address, **_: 100 if address in (31024, 41010) else None
    await manager.poll_complete_callback()
    assert controller.write_register.await_args_list[-2:] == [call(46001, 12), call(46002, 60)]
    assert controller.write_registers.await_count == 1


@pytest.mark.parametrize("words", [[], [12, 0], [-1], [65536]])
async def test_invalid_enable_read_does_not_write_power(
    controller: MagicMock, manager: RemoteControlManager, words: list[int]
) -> None:
    controller.read_registers.return_value = words
    with pytest.raises(ValueError, match="Remote enable register"):
        await manager.set_mode(RemoteControlMode.FORCE_CHARGE)
    controller.write_register.assert_awaited_once_with(46002, 20)
    controller.write_registers.assert_not_awaited()
    # Failed enable does not mark the manager as owning control; the next poll retries.
    controller.read_registers.return_value = [12]
    await manager.poll_complete_callback()
    assert controller.write_register.await_args_list[-1] == call(46001, 13)


async def test_failed_disable_retries(controller: MagicMock, manager: RemoteControlManager) -> None:
    await manager.set_mode(RemoteControlMode.FORCE_DISCHARGE)
    controller.write_register.side_effect = OSError("write failed")
    with pytest.raises(OSError, match="write failed"):
        await manager.set_mode(RemoteControlMode.DISABLE)
    # Never extend the watchdog while control may still be enabled.
    assert call(46002, 60) not in controller.write_register.await_args_list
    controller.write_register.side_effect = None
    await manager.poll_complete_callback()
    assert controller.write_register.await_args_list[-2:] == [call(46001, 12), call(46002, 60)]


@pytest.mark.parametrize("original_timeout", [0, 90, 65535])
async def test_restore_actual_timeout_across_mode_change_and_reconnect(
    controller: MagicMock, manager: RemoteControlManager, original_timeout: int
) -> None:
    controller.read_registers.side_effect = lambda address, *_: [original_timeout] if address == 46002 else [12]
    await manager.set_mode(RemoteControlMode.FORCE_CHARGE)
    await manager.set_mode(RemoteControlMode.FORCE_DISCHARGE)
    controller.is_connected = False
    await manager.poll_complete_callback()
    controller.is_connected = True
    await manager.became_connected_callback()
    await manager.set_mode(RemoteControlMode.DISABLE)
    assert controller.write_register.await_args_list[-2:] == [call(46001, 12), call(46002, original_timeout)]
    assert controller.read_registers.await_args_list.count(call(46002, 1, RegisterType.HOLDING)) == 1

    # A new session takes a new snapshot rather than reusing the old saved value.
    controller.read_registers.side_effect = lambda address, *_: [45] if address == 46002 else [12]
    await manager.set_mode(RemoteControlMode.FORCE_DISCHARGE)
    await manager.set_mode(RemoteControlMode.DISABLE)
    assert controller.write_register.await_args_list[-1] == call(46002, 45)


@pytest.mark.parametrize("words", [[], [60, 0], [-1], [65536]])
async def test_invalid_timeout_read_does_not_enable(
    controller: MagicMock, manager: RemoteControlManager, words: list[int]
) -> None:
    controller.read_registers.side_effect = None
    controller.read_registers.return_value = words
    with pytest.raises(ValueError, match="Remote timeout register"):
        await manager.set_mode(RemoteControlMode.FORCE_DISCHARGE)
    controller.write_register.assert_not_awaited()
    controller.write_registers.assert_not_awaited()


async def test_timeout_read_error_does_not_enable(controller: MagicMock, manager: RemoteControlManager) -> None:
    controller.read_registers.side_effect = OSError("read failed")
    with pytest.raises(OSError, match="read failed"):
        await manager.set_mode(RemoteControlMode.FORCE_DISCHARGE)
    controller.write_register.assert_not_awaited()
    controller.write_registers.assert_not_awaited()


async def test_failed_timeout_restore_retries_without_reenabling(
    controller: MagicMock, manager: RemoteControlManager
) -> None:
    await manager.set_mode(RemoteControlMode.FORCE_DISCHARGE)

    def fail_restore(address: int, value: int) -> None:
        if (address, value) == (46002, 60):
            raise OSError("restore failed")

    controller.write_register.side_effect = fail_restore
    with pytest.raises(OSError, match="restore failed"):
        await manager.set_mode(RemoteControlMode.DISABLE)
    assert manager.active_mode == RemoteControlMode.DISABLE
    controller.write_register.side_effect = None
    await manager.poll_complete_callback()
    assert controller.write_register.await_args_list[-1] == call(46002, 60)
    assert controller.write_register.await_args_list.count(call(46001, 12)) == 1
    writes = controller.write_register.await_count
    await manager.poll_complete_callback()
    assert controller.write_register.await_count == writes


async def test_failed_enable_retains_original_timeout_for_disable(
    controller: MagicMock, manager: RemoteControlManager
) -> None:
    controller.read_registers.return_value = []
    with pytest.raises(ValueError, match="Remote enable register"):
        await manager.set_mode(RemoteControlMode.FORCE_DISCHARGE)
    await manager.set_mode(RemoteControlMode.DISABLE)
    assert controller.write_register.await_args_list == [call(46002, 20), call(46002, 60)]


async def test_legacy_enable_values_unchanged(controller: MagicMock, config: ModbusRemoteControlAddressConfig) -> None:
    manager = RemoteControlManager(
        controller, replace(config, remote_enable_mask=None, remote_enable=44000, restore_timeout=False), 10
    )
    await manager.set_mode(RemoteControlMode.FORCE_DISCHARGE)
    await manager.set_mode(RemoteControlMode.DISABLE)
    assert controller.write_register.await_args_list == [call(46002, 20), call(44000, 1), call(44000, 0)]
    controller.read_registers.assert_not_awaited()


def test_pq1_config_uses_only_supported_monitoring(config: ModbusRemoteControlAddressConfig) -> None:
    assert config.active_power == [46004, 46003]
    assert config.remote_enable_mask == 1
    assert config.restore_timeout
    assert config.work_mode is None
    assert config.max_soc == 41010
    assert config.battery_soc == [31024]
    assert config.invbatpower == [39238, 39237]
    assert config.pwr_limit_bat_up is None
    assert config.pv_voltages == [39070, 39072, 39074, 39076]


@pytest.mark.parametrize("operation", ["night_charge", "day_charge", "discharge", "soc_cutoff"])
async def test_existing_profiles_control_sequence(
    controller: MagicMock, legacy_config: ModbusRemoteControlAddressConfig, operation: str
) -> None:
    """Exercise every existing model/connection/firmware profile with its actual map."""
    config = legacy_config
    assert config.remote_enable_mask is None
    assert not config.restore_timeout
    values: dict[int | tuple[int, ...], int] = dict.fromkeys(
        config.pv_voltages, 800 if operation == "day_charge" else 0
    )
    values.update(dict.fromkeys(config.battery_soc, 100 if operation == "soc_cutoff" else 50))
    if config.max_soc is not None:
        values[config.max_soc] = 100
    if config.work_mode is not None:
        assert config.work_mode_map is not None
        values[config.work_mode] = config.work_mode_map[WorkMode.SELF_USE]
    values[tuple(config.invbatpower)] = -500
    if config.pwr_limit_bat_up is not None:
        values[tuple(config.pwr_limit_bat_up)] = -1000
    controller.read.side_effect = lambda address, **_: values.get(
        tuple(address) if isinstance(address, list) else address
    )
    controller.write_register.side_effect = lambda address, value: values.update({address: value})
    manager = RemoteControlManager(controller, config, 10)
    manager.max_soc = 100
    manager.charge_power = 600
    manager.discharge_power = 700

    await manager.poll_complete_callback()
    controller.write_register.assert_not_awaited()
    controller.write_registers.assert_not_awaited()

    mode = RemoteControlMode.FORCE_DISCHARGE if operation == "discharge" else RemoteControlMode.FORCE_CHARGE
    await manager.set_mode(mode)
    await manager.poll_complete_callback()

    fallback = WorkMode.FEED_IN_FIRST if operation == "discharge" else WorkMode.BACK_UP
    expected_single_writes = []
    if config.work_mode is not None:
        assert config.work_mode_map is not None
        expected_single_writes.append(call(config.work_mode, config.work_mode_map[fallback]))

    if operation == "soc_cutoff":
        # No enable/command at maximum SOC; preserve the existing Backup fallback.
        assert controller.write_register.await_args_list == expected_single_writes
        controller.write_registers.assert_not_awaited()
    else:
        expected_single_writes.extend([call(config.timeout_set, 20), call(config.remote_enable, 1)])
        assert controller.write_register.await_args_list == expected_single_writes
        if operation == "discharge":
            powers = [700, 700]
        elif operation == "day_charge" and config.pwr_limit_bat_up is not None:
            # First observe PV at zero import, then target (1000 - 200) W with 500 W already charging.
            powers = [0, -300]
        else:
            powers = [-600, -600]
        packed = [[(power >> (16 * i)) & 0xFFFF for i in reversed(range(len(config.active_power)))] for power in powers]
        assert controller.write_registers.await_args_list == [call(config.active_power[-1], words) for words in packed]

        await manager.set_mode(RemoteControlMode.DISABLE)
        assert controller.write_register.await_args_list == [*expected_single_writes, call(config.remote_enable, 0)]

    # Existing models retain whole-register 1/0 writes and require no new device reads.
    controller.read_registers.assert_not_awaited()


async def test_existing_profiles_reconnect_and_failed_enable(
    controller: MagicMock, legacy_config: ModbusRemoteControlAddressConfig
) -> None:
    config = legacy_config
    controller.read.return_value = None
    controller.read.side_effect = None
    manager = RemoteControlManager(controller, config, 10)
    manager.discharge_power = 700

    def fail_enable(address: int, _value: int) -> None:
        if address == config.remote_enable:
            raise OSError("enable failed")

    controller.write_register.side_effect = fail_enable
    with pytest.raises(OSError, match="enable failed"):
        await manager.set_mode(RemoteControlMode.FORCE_DISCHARGE)
    controller.write_registers.assert_not_awaited()

    controller.write_register.side_effect = None
    await manager.poll_complete_callback()
    assert controller.write_register.await_args_list[-1] == call(config.remote_enable, 1)
    assert controller.write_registers.await_count == 1

    controller.is_connected = False
    await manager.poll_complete_callback()
    assert controller.write_registers.await_count == 1
    controller.is_connected = True
    await manager.became_connected_callback()
    assert controller.write_register.await_args_list[-2:] == [
        call(config.timeout_set, 20),
        call(config.remote_enable, 1),
    ]
    assert controller.write_registers.await_count == 2
    controller.read_registers.assert_not_awaited()
