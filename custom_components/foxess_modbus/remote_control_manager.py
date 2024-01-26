import logging
from enum import IntEnum

from .common.entity_controller import EntityController
from .common.entity_controller import EntityRemoteControlManager
from .common.entity_controller import ModbusControllerEntity
from .common.entity_controller import RemoteControlMode
from .entities.modbus_remote_control_config import ModbusRemoteControlAddressConfig

_LOGGER = logging.getLogger(__package__)


# Currently these are the same across all models
class WorkMode(IntEnum):
    SELF_USE = 0
    FEED_IN_FIRST = 1
    BACK_UP = 2


# If the PV voltage is below this value, count it as no sun
_PV_VOLTAGE_THRESHOLD = 20


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
        self._current_import_power = 0  # Set the first time that we enable force charge
        self._discharge_power: int | None = None

    @property
    def mode(self) -> RemoteControlMode:
        return self._mode

    async def set_mode(self, mode: RemoteControlMode) -> None:
        if self._mode != mode:
            self._mode = mode
            await self._update()

    @property
    def discharge_power(self) -> int | None:
        return self._discharge_power

    @discharge_power.setter
    def discharge_power(self, value: int | None) -> None:
        self._discharge_power = value

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

    def _pv_power_sum(self) -> int | None:
        pv_sum = 0
        for address in self._addresses.pv_powers:
            value = self._controller.read(address, signed=True)
            if value is None:
                return None
            pv_sum += value
        return pv_sum

    def _has_any_pv_voltage(self) -> int | None:
        for address in self._addresses.pv_voltages:
            value = self._controller.read(address, signed=True)
            # Units are 0.1V
            if value is not None and value > _PV_VOLTAGE_THRESHOLD * 10:
                return True
        return False

    async def _update_charge(self) -> None:
        # The inverter doesn't respect Max Soc. Therefore if the SoC >= Max SoC, turn off remote control.
        # We don't let the user configure charge power: they can't figure it with normal charge periods, so why bother?
        # They can set the max charge current if they want, which has the same effect.

        soc = self._controller.read(self._addresses.battery_soc, signed=False)
        max_soc = self._controller.read(self._addresses.max_soc, signed=False)

        if soc is not None and max_soc is not None and soc >= max_soc:
            _LOGGER.debug("Force charge: soc %s%% >= max soc %s%%, using Back-up", soc, max_soc)
            # Avoid discharging the battery with Back-Up
            await self._disable_remote_control(WorkMode.BACK_UP)
            return

        # If it's daylight, both PV and the input power are bringing power into the inverter. The input power will
        # first displace PV (so PV generation falls to 0), then the inverter will start limiting the input power.
        # Therefore, we need to keep an eye on the PV generation, and decrease the input power so as not to displace
        # it. Once we get to the point of exporting (so PV is providing all the power that the battery can take), we
        # might as well just switch to Back-Up.
        # Actually monitoring whether we're clipping PV is hard. The best way I've found is to monitor the sum of PV
        # powers, and the PV Power Limit register, and we're clipping when PV Power Limit falls below the PV Power.
        # We can also be clipping if they're close (within 50W of each other).
        #
        # So, we start off with a starting power (TBD, might make sense to read register 44008, but only when we
        # have the ability to read registers once on start-up), and then we implement a little P controller, which
        # steps up the power so long as PV isn't being saturated, and steps it down if it is.

        # If the work mode is Back-up, and the inverter is currently exporting, then PV is able to handle all of the
        # battery charging. In this case, leave it alone.
        current_work_mode = self._controller.read(self._addresses.work_mode, signed=False)
        if current_work_mode == WorkMode.BACK_UP:
            inverter_power = self._controller.read(self._addresses.inverter_power, signed=True)
            if inverter_power is not None and inverter_power > 0:
                _LOGGER.debug("Force charge: inverter exporting and work mode Back-up, leaving as-is")
                return

        # This is -ve
        max_import_power = self._controller.read(self._addresses.ac_power_limit_down, signed=True)
        if max_import_power is None or max_import_power >= 0:
            _LOGGER.warn("Max import power not available. Not enabling remote control")
            await self._disable_remote_control()
            return

        max_import_power = -max_import_power

        # If there's no sun, don't try and do any control.
        # (If we do, we can end up limiting the power to the max PV power, rather than the max inverter input power).
        pv_power_sum = self._pv_power_sum()
        pv_power_limit = self._controller.read(self._addresses.pv_power_limit, signed=True)
        if not self._has_any_pv_voltage() or pv_power_sum is None or pv_power_limit is None:
            _LOGGER.debug("Remote control: no sun (or PV unavailable), defaulting to %sW", max_import_power)
            # If remote control stops, we want to be in Back-up
            await self._enable_remote_control(WorkMode.BACK_UP)
            await self._controller.write_register(self._addresses.active_power, -max_import_power)
            return

        # If we're currently disabled, do a period to get data before we start doing active control.
        # Do this after the 'None' check above to avoid flip-flopping if the registers aren't available for some
        # reason
        if self._remote_control_enabled is not True:
            self._current_import_power = max_import_power

        # We aim to have the PV Power Limit 50W above PV Sum.
        # (It seems PV can still be clipped if PV is small, and the PV limit is just slightly larger)
        # Having this also means that PV can increase between polls, and we won't lose all of it
        setpoint = 50
        # Positive values = not clipping (which means we can raise the import power)
        actual = pv_power_limit - pv_power_sum
        error = setpoint - actual

        # Never step by more than 1kW
        max_step = 1000

        # When we're trying to stop clipping PV, we'll use a slightly higher P. This means that we're quicker to stop
        # clipping, but not quite as unstable going the other way
        p = 1.5 if error > 0 else 1.0
        delta = -int(error * p)
        delta = min(max_step, delta) if delta > 0 else max(-max_step, delta)

        previous_import_power = self._current_import_power
        self._current_import_power = min(self._current_import_power + delta, max_import_power)

        # It's valid for this to go negative, if PV is supplying all the charging the battery can handle. In this
        # case, switch to Back-up
        # (It seems we start clipping solar, and the PV limit doesn't tell us this, below around 80W)
        if self._current_import_power < 80 - setpoint:
            # Avoid this going too negative, for when we start importing again
            self._current_import_power = 0
            _LOGGER.debug("Remote control: PV %sW clipping at 0W import, changing to Back-up", pv_power_sum)
            await self._disable_remote_control(WorkMode.BACK_UP)
            return

        # Right, let's set that
        _LOGGER.debug(
            "Remote control: PV: %sW, limit: %sW, error: %sW, import %sW -> %sW",
            pv_power_sum,
            pv_power_limit,
            error,
            previous_import_power,
            self._current_import_power,
        )

        # If remote control stops, we want to be in Back-up, charging as much as we can
        await self._enable_remote_control(WorkMode.BACK_UP)
        await self._controller.write_register(self._addresses.active_power, -self._current_import_power)

    async def _update_discharge(self) -> None:
        # For force discharge, normally we can just leave it, and it will do the right thing: respect Min SoC and the
        # Max Discharge Current.
        # Discharge Power should be the feed-in power, so we need to add on the house load. The house load can be
        # negative, in which case we'll treat it as zero: starting to import power during a force *dis*charge period
        # would just be confusing.

        if self._discharge_power is None:
            _LOGGER.warn("Remote control: discharge power has not been set, so not discharging")
            await self._disable_remote_control()
            return

        load_power = self._controller.read(self._addresses.load_power, signed=True)
        max_discharge_power = self._controller.read(self._addresses.ac_power_limit_up, signed=False)
        inverter_discharge_power = (
            self._discharge_power + load_power if load_power is not None and load_power > 0 else self._discharge_power
        )
        if max_discharge_power is not None and inverter_discharge_power > max_discharge_power:
            inverter_discharge_power = max_discharge_power

        # If remote control stops, we still want to feed in as much as possible
        await self._enable_remote_control(WorkMode.FEED_IN_FIRST)
        # Positive values = discharge
        await self._controller.write_register(self._addresses.active_power, inverter_discharge_power)

    async def _enable_remote_control(self, fallback_work_mode: WorkMode) -> None:
        if self._remote_control_enabled in (None, False):
            self._remote_control_enabled = True
            timeout = self._poll_rate * 2

            # We set a fallback work mode so that the inverter still does "roughly" the right thing if we disconnect
            current_work_mode = self._controller.read(self._addresses.work_mode, signed=False)
            if current_work_mode != fallback_work_mode:
                await self._controller.write_register(self._addresses.work_mode, int(fallback_work_mode))

            # We can't do multi-register writes to these registers
            await self._controller.write_register(self._addresses.timeout_set, timeout)
            await self._controller.write_register(self._addresses.remote_enable, 1)

    async def _disable_remote_control(self, work_mode: WorkMode | None = None) -> None:
        if self._remote_control_enabled in (None, True):
            self._remote_control_enabled = False
            await self._controller.write_register(self._addresses.remote_enable, 0)

        if work_mode is not None:
            current_work_mode = self._controller.read(self._addresses.work_mode, signed=False)
            if current_work_mode != work_mode:
                await self._controller.write_register(self._addresses.work_mode, int(work_mode))

    @property
    def addresses(self) -> list[int]:
        return [
            self._addresses.battery_soc,
            self._addresses.max_soc,
            self._addresses.load_power,
            self._addresses.inverter_power,
            self._addresses.pv_power_limit,
            self._addresses.ac_power_limit_down,
            *self._addresses.pv_voltages,
            *self._addresses.pv_powers,
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
