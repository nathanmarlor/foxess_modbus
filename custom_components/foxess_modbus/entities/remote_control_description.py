from ..const import H1_SET
from .modbus_remote_control_config import ModbusRemoteControlAddressConfig
from .modbus_remote_control_config import ModbusRemoteControlFactory
from .modbus_remote_control_config import RemoteControlAddressSpec

REMOTE_CONTROL_DESCRIPTION = ModbusRemoteControlFactory(
    addresses=[
        RemoteControlAddressSpec(
            H1_SET,
            input=ModbusRemoteControlAddressConfig(
                remote_enable_address=44000,
                timeout_set_address=44001,
                active_power_address=44002,
                battery_soc_address=11036,
            ),
        )
    ]
)
