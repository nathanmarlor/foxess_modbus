from .common.entity_controller import EntityController
from .common.entity_controller import EntityRemoteControlManager
from .common.entity_controller import ModbusControllerEntity
from .common.entity_controller import RemoteControlMode
from .entities.modbus_remote_control_config import ModbusRemoteControlAddressConfig


class RemoteControlManager(EntityRemoteControlManager, ModbusControllerEntity):
    def __init__(
        self, controller: EntityController, addresses: ModbusRemoteControlAddressConfig, poll_rate: int
    ) -> None:
        self._controller = controller
        self._addresses = addresses
        self._poll_rate = poll_rate

        self._controller.register_modbus_entity(self)
        self._mode = RemoteControlMode.DISABLE

    @property
    def mode(self) -> RemoteControlMode:
        return self._mode

    async def set_mode(self, mode: RemoteControlMode) -> None:
        if self._mode != mode:
            self._mode = mode
            await self._update(initialise=True)

    async def _update(self, initialise: bool = False) -> None:
        if self._mode == RemoteControlMode.DISABLE:
            await self._update_disable(initialise)
        elif self._mode == RemoteControlMode.FORCE_DISCHARGE:
            await self._update_discharge(initialise)

    async def _update_disable(self, initialise: bool) -> None:
        if initialise:
            await self._controller.write_register(self._addresses.remote_enable_address, 0)
            await self._controller.write_register(self._addresses.active_power_address, 0)

    async def _update_discharge(self, initialise: bool) -> None:
        if initialise:
            await self._controller.write_register(self._addresses.timeout_set_address, self._poll_rate * 2)
            await self._controller.write_register(self._addresses.remote_enable_address, 1)

        await self._controller.write_register(self._addresses.active_power_address, 1000)

    @property
    def addresses(self) -> list[int]:
        return [self._addresses.battery_soc_address, self._addresses.pv_power_limit_address]

    async def poll_complete_callback(self) -> None:
        await self._update()

    async def became_connected_callback(self) -> None:
        await self._update(initialise=True)

    def update_callback(self, changed_addresses: set[int]) -> None:
        pass

    def is_connected_changed_callback(self) -> None:
        pass
