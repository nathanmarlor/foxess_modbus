from ..common.types import Inv
from .modbus_remote_control_config import ModbusRemoteControlAddressConfig
from .modbus_remote_control_config import ModbusRemoteControlFactory
from .modbus_remote_control_config import RemoteControlAddressSpec
from .modbus_remote_control_config import WorkMode

_NORMAL_WORK_MODE_MAP = {
    WorkMode.SELF_USE: 0,
    WorkMode.FEED_IN_FIRST: 1,
    WorkMode.BACK_UP: 2,
}

REMOTE_CONTROL_DESCRIPTION = ModbusRemoteControlFactory(
    addresses=[
        RemoteControlAddressSpec(
            input=ModbusRemoteControlAddressConfig(
                remote_enable=44000,
                timeout_set=44001,
                active_power=[44002],
                work_mode=41000,
                work_mode_map=_NORMAL_WORK_MODE_MAP,
                max_soc=41010,
                invbatpower=[11008],
                battery_soc=[11036],
                pwr_limit_bat_down=[44012],
                pv_voltages=[11000, 11003],
            ),
            models=Inv.H1_G1,
        ),
        RemoteControlAddressSpec(
            # H1 LAN doesn't support anything above 44003, or work mode / max soc
            holding=ModbusRemoteControlAddressConfig(
                remote_enable=44000,
                timeout_set=44001,
                active_power=[44002],
                work_mode=None,
                work_mode_map=None,
                max_soc=None,
                invbatpower=[31022],
                battery_soc=[31024],
                pwr_limit_bat_down=None,
                pv_voltages=[31000, 31003],
            ),
            models=Inv.H1_LAN,
        ),
        RemoteControlAddressSpec(
            holding=ModbusRemoteControlAddressConfig(
                remote_enable=44000,
                timeout_set=44001,
                active_power=[44002],
                work_mode=41000,
                work_mode_map=_NORMAL_WORK_MODE_MAP,
                max_soc=41010,
                invbatpower=[31022],
                battery_soc=[31024],
                pwr_limit_bat_down=None,
                pv_voltages=[39070, 39072],
            ),
            models=Inv.H1_G2_SET,
        ),
        # The KH doesn't support anything above 44003
        RemoteControlAddressSpec(
            input=ModbusRemoteControlAddressConfig(
                remote_enable=44000,
                timeout_set=44001,
                active_power=[44002],
                work_mode=41000,
                work_mode_map=_NORMAL_WORK_MODE_MAP,
                max_soc=41010,
                invbatpower=[11008],
                battery_soc=[11036],
                pwr_limit_bat_down=None,
                # Exists, but see https://github.com/nathanmarlor/foxess_modbus/discussions/666
                pv_voltages=[11000, 11003, 11096, 11099],
            ),
            models=Inv.KH_PRE119,
        ),
        RemoteControlAddressSpec(
            holding=ModbusRemoteControlAddressConfig(
                remote_enable=44000,
                timeout_set=44001,
                active_power=[44002],
                work_mode=41000,
                work_mode_map=_NORMAL_WORK_MODE_MAP,
                max_soc=41010,
                invbatpower=[31022],
                battery_soc=[31024],
                pwr_limit_bat_down=None,
                pv_voltages=[31000, 31003, 31039, 31042],
            ),
            models=Inv.KH_PRE133 | Inv.KH_133,
        ),
        RemoteControlAddressSpec(
            # The H3 before 1.80 doesn't support anything above 44005, and the active/reactive power regisers are 2 values
            # The Kuara H3 doesn't support this, see https://github.com/nathanmarlor/foxess_modbus/issues/532
            holding=ModbusRemoteControlAddressConfig(
                remote_enable=44000,
                timeout_set=44001,
                active_power=[44003, 44002],
                work_mode=41000,
                work_mode_map=_NORMAL_WORK_MODE_MAP,
                max_soc=41010,
                invbatpower=[31036],
                battery_soc=[31038],
                pwr_limit_bat_down=None,
                pv_voltages=[31000, 31003],
            ),
            models=Inv.H3_PRE180 & ~Inv.KUARA_H3 & ~Inv.AIO_H3_101 & ~Inv.AIO_H3_PRE101,
        ),
        RemoteControlAddressSpec(
            # H3 after 180 supports pwr_limit_bat_down
            holding=ModbusRemoteControlAddressConfig(
                remote_enable=44000,
                timeout_set=44001,
                active_power=[44003, 44002],
                work_mode=41000,
                work_mode_map=_NORMAL_WORK_MODE_MAP,
                max_soc=41010,
                invbatpower=[31036],
                battery_soc=[31038],
                pwr_limit_bat_down=[44012],
                pv_voltages=[31000, 31003],
            ),
            models=Inv.H3_180,
        ),
        RemoteControlAddressSpec(
            holding=ModbusRemoteControlAddressConfig(
                remote_enable=46001,
                timeout_set=46002,
                active_power=[46004, 46003],
                work_mode=49203,
                work_mode_map={
                    WorkMode.SELF_USE: 1,
                    WorkMode.FEED_IN_FIRST: 2,
                    WorkMode.BACK_UP: 3,
                },
                max_soc=46610,
                invbatpower=[39238, 39237],
                battery_soc=[37612, 38310],
                pwr_limit_bat_down=[46021, 46020],
                pv_voltages=[39070, 39072, 39074, 39076, 39078, 39080],
            ),
            models=Inv.H3_PRO_SET | Inv.H3_SMART,
        ),
    ]
)
