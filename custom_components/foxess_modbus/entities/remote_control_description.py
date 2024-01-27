from ..const import H1_SET
from ..const import H3_SET
from ..const import KH
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
                active_power=44002,
                ac_power_limit_down=44008,
                pv_power_limit=44013,
                work_mode=41000,
                max_soc=41010,
                battery_soc=11036,
                inverter_power=[11011],
                pv_voltages=[11000, 11003],
                pv_powers=[11002, 11005],
            ),
            holding=ModbusRemoteControlAddressConfig(
                remote_enable=44000,
                timeout_set=44001,
                active_power=44002,
                ac_power_limit_down=44008,
                pv_power_limit=44013,
                work_mode=None,
                max_soc=None,
                battery_soc=31024,
                inverter_power=[31008],
                pv_voltages=[31000, 31003],
                pv_powers=[31002, 31005],
            ),
        ),
        RemoteControlAddressSpec(
            [KH],
            input=ModbusRemoteControlAddressConfig(
                remote_enable=44000,
                timeout_set=44001,
                active_power=44002,
                ac_power_limit_down=44008,
                pv_power_limit=44013,
                work_mode=41000,
                max_soc=41010,
                battery_soc=11036,
                inverter_power=[11011],
                pv_voltages=[11000, 11003, 11096, 11099],
                pv_powers=[11002, 11005, 11098, 11101],
            ),
            holding=ModbusRemoteControlAddressConfig(
                remote_enable=44000,
                timeout_set=44001,
                active_power=44002,
                ac_power_limit_down=44008,
                pv_power_limit=44013,
                work_mode=41000,
                max_soc=41010,
                battery_soc=31024,
                inverter_power=[31008],
                pv_voltages=[31000, 31003, 31039, 31042],
                pv_powers=[31002, 31005, 31041, 31044],
            ),
        ),
        RemoteControlAddressSpec(
            H3_SET,
            holding=ModbusRemoteControlAddressConfig(
                remote_enable=44000,
                timeout_set=44001,
                active_power=44002,
                ac_power_limit_down=44008,
                pv_power_limit=44013,
                work_mode=41000,
                max_soc=41010,
                battery_soc=31038,
                inverter_power=[31012, 31013, 31014],
                pv_voltages=[31000, 31003],
                pv_powers=[31002, 31005],
            ),
        ),
    ]
)
