from .common.entity_controller import EntityController
from .common.entity_controller import EntityRemoteControlManager
from .common.entity_controller import ModbusControllerEntity
from .common.entity_controller import RemoteControlMode
from .entities.modbus_remote_control_config import ModbusRemoteControlAddressConfig


class RemoteControlManager(EntityRemoteControlManager, ModbusControllerEntity):
    def __init__(self, controller: EntityController, addresses: ModbusRemoteControlAddressConfig) -> None:
        self._controller = controller
        self._addresses = addresses

        self._controller.register_modbus_entity(self)
        self._mode = RemoteControlMode.DISABLE

    @property
    def mode(self) -> RemoteControlMode:
        return self._mode

    @mode.setter
    def mode(self, value: RemoteControlMode) -> None:
        self._mode = value

    @property
    def addresses(self) -> list[int]:
        return [self._addresses.battery_soc_address, self._addresses.pv_power_limit_address]

    def update_callback(self, changed_addresses: set[int]) -> None:
        pass

    def is_connected_changed_callback(self) -> None:
        pass
