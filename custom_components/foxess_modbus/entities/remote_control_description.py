from ..const import H1_SET
from ..const import H3_SET
from ..const import KH
from ..const import KUARA_H3
from .modbus_remote_control_config import ModbusRemoteControlAddressConfig
from .modbus_remote_control_config import ModbusRemoteControlFactory
from .modbus_remote_control_config import RemoteControlAddressSpec

REMOTE_CONTROL_DESCRIPTION = ModbusRemoteControlFactory(
    addresses=[
        RemoteControlAddressSpec(
            H1_SET,
            input=ModbusRemoteControlAddressConfig(
                remote_enable=44000,
                timeout_set=44001,
                active_power=[44002],
                ac_power_limit_down=44008,
                work_mode=41000,
                max_soc=41010,
                invbatpower=11008,
                battery_soc=11036,
                pwr_limit_bat_up=44012,
                pv_voltages=[11000, 11003],
            ),
            # H1 LAN doesn't support anything above 44003, or work mode / max soc
            holding=ModbusRemoteControlAddressConfig(
                remote_enable=44000,
                timeout_set=44001,
                active_power=[44002],
                ac_power_limit_down=None,
                work_mode=None,
                max_soc=None,
                invbatpower=31022,
                battery_soc=31024,
                pwr_limit_bat_up=None,
                pv_voltages=[31000, 31003],
            ),
        ),
        RemoteControlAddressSpec(
            # The KH doesn't support anything above 44003
            [KH],
            input=ModbusRemoteControlAddressConfig(
                remote_enable=44000,
                timeout_set=44001,
                active_power=[44002],
                ac_power_limit_down=None,
                work_mode=41000,
                max_soc=41010,
                invbatpower=11008,
                battery_soc=11036,
                pwr_limit_bat_up=None,
                pv_voltages=[11000, 11003, 11096, 11099],
            ),
            holding=ModbusRemoteControlAddressConfig(
                remote_enable=44000,
                timeout_set=44001,
                active_power=[44002],
                ac_power_limit_down=None,
                work_mode=41000,
                max_soc=41010,
                invbatpower=31022,
                battery_soc=31024,
                pwr_limit_bat_up=None,
                pv_voltages=[31000, 31003, 31039, 31042],
            ),
        ),
        RemoteControlAddressSpec(
            # The H3 doesn't support anything above 44005, and the active/reactive power regisers are 2 values
            # The Kuara H3 doesn't support this, see https://github.com/nathanmarlor/foxess_modbus/issues/532
            list(set(H3_SET) - {KUARA_H3}),
            holding=ModbusRemoteControlAddressConfig(
                remote_enable=44000,
                timeout_set=44001,
                active_power=[44003, 44002],
                ac_power_limit_down=None,
                work_mode=41000,
                max_soc=41010,
                invbatpower=31022,
                battery_soc=31036,
                pwr_limit_bat_up=None,
                pv_voltages=[31000, 31003],
            ),
        ),
    ]
)
