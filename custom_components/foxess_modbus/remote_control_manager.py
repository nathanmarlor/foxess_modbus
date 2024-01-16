from .common.entity_controller import EntityController
from .common.entity_controller import ModbusControllerEntity
from .entities.modbus_remote_control_config import ModbusRemoteControlAddressConfig


class RemoteControlManager(ModbusControllerEntity):
    def __init__(self, controller: EntityController, addresses: ModbusRemoteControlAddressConfig) -> None:
        self._controller = controller
        self._addresses = addresses

        self._controller.register_modbus_entity(self)

    @property
    def addresses(self) -> list[int]:
        return self._addresses.addresses

    def update_callback(self, changed_addresses: set[int]) -> None:
        pass

    def is_connected_changed_callback(self) -> None:
        pass
