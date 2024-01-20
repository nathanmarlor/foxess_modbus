from enum import IntEnum

from .common.entity_controller import EntityController
from .common.entity_controller import EntityRemoteControlManager
from .common.entity_controller import ModbusControllerEntity
from .common.entity_controller import RemoteControlMode
from .entities.modbus_remote_control_config import ModbusRemoteControlAddressConfig


# Currently these are the same across all models
class WorkMode(IntEnum):
    SELF_USE = 0
    FEED_IN_FIRST = 1
    BACK_UP = 2


class RemoteControlManager(EntityRemoteControlManager, ModbusControllerEntity):
    def __init__(
        self, controller: EntityController, addresses: ModbusRemoteControlAddressConfig, poll_rate: int
    ) -> None:
        self._controller = controller
        self._addresses = addresses
        self._poll_rate = poll_rate

        self._controller.register_modbus_entity(self)
        self._mode = RemoteControlMode.DISABLE
        self._remote_control_enabled: bool | None = None  # None = we don't know

        self.charge_power = 4000
        self.discharge_power = 4000

    @property
    def mode(self) -> RemoteControlMode:
        return self._mode

    async def set_mode(self, mode: RemoteControlMode) -> None:
        if self._mode != mode:
            self._mode = mode
            await self._update()

    async def _update(self) -> None:
        if not self._controller.is_connected:
            return

        if self._mode == RemoteControlMode.DISABLE:
            await self._update_disable()
        elif self._mode == RemoteControlMode.FORCE_CHARGE:
            await self._update_charge()
        elif self._mode == RemoteControlMode.FORCE_DISCHARGE:
            await self._update_discharge()

    async def _update_disable(self) -> None:
        await self._disable_remote_control()

    async def _update_charge(self) -> None:
        # The inverter doesn't respect Max Soc. Therefore if the SoC >= Max SoC, turn off remote control.

        soc = self._controller.read(self._addresses.battery_soc)
        max_soc = self._controller.read(self._addresses.max_soc)
        if soc is not None and max_soc is not None and soc >= max_soc:
            # Avoid discharging the battery with Back-Up
            await self._disable_remote_control(WorkMode.BACK_UP)
        else:
            await self._enable_remote_control()
            # Negative values = charge
            await self._controller.write_register(self._addresses.active_power, -self.charge_power)

    async def _update_discharge(self) -> None:
        # For force discharge, normally we can just leave it, and it will do the right thing: respect Min SoC and the
        # Max Discharge Current.
        # However, if the house load is more than the power we set, then the inverter won't increase its power output
        # to compensate. Therefore, if the house load exceeds the export power, disable remote control.

        load_power = self._controller.read(self._addresses.load_power)
        if load_power is not None and load_power > self.discharge_power:
            # If we're discharging, we need to use Feed-in First to avoid charging the battery
            await self._disable_remote_control(WorkMode.FEED_IN_FIRST)
        else:
            await self._enable_remote_control()
            # Positive values = discharge
            await self._controller.write_register(self._addresses.active_power, self.discharge_power)

    async def _enable_remote_control(self) -> None:
        if self._remote_control_enabled in (None, False):
            self._remote_control_enabled = True
            timeout = self._poll_rate * 2
            # We can't do multi-register writes to these registers
            await self._controller.write_register(self._addresses.timeout_set, timeout)
            await self._controller.write_register(self._addresses.remote_enable, 1)

    async def _disable_remote_control(self, work_mode: WorkMode | None = None) -> None:
        if self._remote_control_enabled in (None, True):
            self._remote_control_enabled = False
            await self._controller.write_register(self._addresses.remote_enable, 0)

            if work_mode is not None:
                await self._controller.write_register(self._addresses.work_mode, int(work_mode))

    @property
    def addresses(self) -> list[int]:
        return [
            self._addresses.battery_soc,
            self._addresses.max_soc,
            self._addresses.load_power,
            self._addresses.pv_power_limit,
        ]

    async def poll_complete_callback(self) -> None:
        await self._update()

    async def became_connected_callback(self) -> None:
        self._remote_control_enabled = None  # Don't know whether it's enabled or not
        await self._update()

    def update_callback(self, changed_addresses: set[int]) -> None:
        pass

    def is_connected_changed_callback(self) -> None:
        pass
