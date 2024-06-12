import logging

from .common.entity_controller import EntityController
from .common.entity_controller import EntityRemoteControlManager
from .common.entity_controller import ModbusControllerEntity
from .common.entity_controller import RemoteControlMode
from .entities.modbus_remote_control_config import ModbusRemoteControlAddressConfig
from .entities.modbus_remote_control_config import WorkMode

_LOGGER = logging.getLogger(__package__)

# If the PV voltage is below this value, count it as no sun
_PV_VOLTAGE_THRESHOLD = 70


class RemoteControlManager(EntityRemoteControlManager, ModbusControllerEntity):
    def __init__(
        self, controller: EntityController, addresses: ModbusRemoteControlAddressConfig, poll_rate: int
    ) -> None:
        self._controller = controller
        self._addresses = addresses
        self._poll_rate = poll_rate

        self._mode = RemoteControlMode.DISABLE
        self._prev_mode = RemoteControlMode.DISABLE
        self._remote_control_enabled = False
        self._current_import_power = 0  # Set the first time that we enable force charge
        self._discharge_power: int | None = None
        self._charge_power: int | None = None
        self._max_soc_override: int | None = None

        modbus_addresses = [
            *self._addresses.battery_soc,
            self._addresses.work_mode,
            self._addresses.max_soc,
            *self._addresses.invbatpower,
            *(self._addresses.pwr_limit_bat_up if self._addresses.pwr_limit_bat_up is not None else []),
            *self._addresses.pv_voltages,
        ]
        self._modbus_addresses = [x for x in modbus_addresses if x is not None]

        self._controller.register_modbus_entity(self)

    @property
    def mode(self) -> RemoteControlMode:
        return self._mode

    async def set_mode(self, mode: RemoteControlMode) -> None:
        if self._mode != mode:
            self._mode = mode
            await self._update()

    @property
    def charge_power(self) -> int | None:
        return self._charge_power

    @charge_power.setter
    def charge_power(self, value: int | None) -> None:
        self._charge_power = value

    @property
    def discharge_power(self) -> int | None:
        return self._discharge_power

    @discharge_power.setter
    def discharge_power(self, value: int | None) -> None:
        self._discharge_power = value

    @property
    def max_soc(self) -> int | None:
        return self._max_soc_override

    @max_soc.setter
    def max_soc(self, value: int | None) -> None:
        self._max_soc_override = value

    async def _update(self) -> None:
        if not self._controller.is_connected:
            self._prev_mode = RemoteControlMode.DISABLE
            return

        if self._mode == RemoteControlMode.DISABLE:
            await self._update_disable()
        elif self._mode == RemoteControlMode.FORCE_CHARGE:
            await self._update_charge()
        elif self._mode == RemoteControlMode.FORCE_DISCHARGE:
            await self._update_discharge()

        self._prev_mode = self._mode

    async def _update_disable(self) -> None:
        await self._disable_remote_control()

    def _sum(self, addresses: list[int]) -> int | None:
        total = 0
        for address in addresses:
            value = self._read(address, signed=True)
            if value is None:
                return None
            total += value
        return total

    def _has_any_pv_voltage(self) -> int | None:
        for address in self._addresses.pv_voltages:
            value = self._read(address, signed=True)
            # Units are 0.1V
            if value is not None and value > _PV_VOLTAGE_THRESHOLD * 10:
                return True
        return False

    async def _write_active_power(self, export_power: int) -> None:
        values = []
        for i in range(len(self._addresses.active_power)):
            # If there are multiple registers, they must be contiguous and descending
            # (Low-order bits are in the higher register)
            if i > 0:
                assert self._addresses.active_power[i] == self._addresses.active_power[i - 1] - 1
            values.append((export_power >> (i * 16)) & 0xFFFF)
        # Last register is the lowest address
        values.reverse()
        await self._controller.write_registers(self._addresses.active_power[-1], values)

    async def _update_charge(self) -> None:
        # The inverter doesn't respect Max Soc. Therefore if the SoC >= Max SoC, turn off remote control.
        # We don't let the user configure charge power: they can't figure it with normal charge periods, so why bother?
        # They can set the max charge current if they want, which has the same effect.
        # If there are multiple batteries, then we'll take the max. That doesn't stop the inverter charging the other
        # of course, but it's probably the best we can do.

        soc: int | None = None
        for address in self._addresses.battery_soc:
            value = self._read(address, signed=False)
            if value is not None and (soc is None or value > soc):
                soc = value

        # max_soc might not be available, e.g. on H1 LAN. In this case, we use an override, controlled from a sensor
        if self._max_soc_override is not None:
            max_soc: int | None = self._max_soc_override
        else:
            max_soc = self._read(self._addresses.max_soc, signed=False)

        if soc is not None and max_soc is not None and soc >= max_soc:
            _LOGGER.debug("Force charge: soc %s%% >= max soc %s%%, using Back-up", soc, max_soc)
            # Avoid discharging the battery with Back-Up
            await self._disable_remote_control(WorkMode.BACK_UP)
            return

        # If it's daylight, both PV and the input power are bringing power into the inverter. The input power will
        # first displace PV (so PV generation falls to 0), then the inverter will start limiting the input power.
        # Therefore, we need to keep an eye on the PV generation, and decrease the input power so as not to displace
        # it.
        #
        # Actually monitoring whether we're clipping PV is hard. The best way I've found is to monitor the sum of PV
        # powers, and the PV Power Limit register, and we're clipping when PV Power Limit falls below the PV Power.
        # We can also be clipping if they're close (within 50W of each other). This works well enough if the inverter is
        # importing, but gets quite bad when we need to tell the inverter to start exporting: we can quite easily end up
        # not charging the battery, or actually discharging it.
        #
        # (We can't use Back-up for this, as Back-up prefers to cover the house load rather than PV. This means that if
        # we have enough PV to cover charge and part of house load, it'll cover the load in full then part of the
        # charge).
        #
        # A better way seems to be to use the Pwr_limit_Bat_up register. This seems to hold the maximum input power
        # that the battery can take, including things like BMS limits (which might not be exposed by the inverter,
        # depending on model). Therefore we can control the actual battery charge power so it's slightly below the
        # limit: this means that PV isn't being clipped (as it would fill the gap if it was).
        # We do seem to need to leave a bit of a gap: the inverter will happily provide the battery with ~50W less than
        # it can take and still clip PV: I suspect this is to do with losses somewhere, but I'm not quite sure where.

        max_import_power = self._charge_power
        inverter_capacity = self._controller.inverter_capacity

        if max_import_power is None or max_import_power > inverter_capacity:
            max_import_power = inverter_capacity

        # If there's no sun, don't try and do any control.
        # (If we do, we can end up limiting the power to the max PV power, rather than the max inverter input power).
        if not self._has_any_pv_voltage():
            _LOGGER.debug("Remote control: no sun (or PV unavailable), defaulting to %sW", max_import_power)
            # If remote control stops, we want to be in Back-up
            await self._enable_remote_control(WorkMode.BACK_UP)
            await self._write_active_power(-max_import_power)
            return

        # These are both negative
        # max_battery_charge_power_negative isn't available on the H1 over LAN
        max_battery_charge_power_negative = self._read(self._addresses.pwr_limit_bat_up, signed=True)
        current_battery_charge_power_negative = self._read(self._addresses.invbatpower, signed=True)
        if max_battery_charge_power_negative is None or current_battery_charge_power_negative is None:
            _LOGGER.debug(
                "Remote control: max or current battery charge power unavailable, defaulting to %sW",
                max_import_power,
            )
            await self._enable_remote_control(WorkMode.BACK_UP)
            await self._write_active_power(-max_import_power)
            return

        max_battery_charge_power = -max_battery_charge_power_negative
        current_battery_charge_power = -current_battery_charge_power_negative

        # If the BMS has decided not to charge the battery (which it might do if it's almost full), then don't try and
        # be clever.
        # Similarly, if the max battery power is very small, we won't be able to set the setpoint such that there's a
        # margin for PV, which means we run the risk of completely clipping PV.
        if max_battery_charge_power < 50:
            _LOGGER.debug("Remote control: max battery charge power is %sW, using Back-up", max_battery_charge_power)
            await self._disable_remote_control(WorkMode.BACK_UP)
            return

        # If we're just switching to export, do a cycle with 0 import. This tells us how much PV is providing
        # (as bat charge power = pv power), which lets us set the import/export power pretty accurately.
        if self._prev_mode != RemoteControlMode.FORCE_CHARGE:
            self._current_import_power = 0
        else:
            # We'll try and set the setpoint 200W below the desired charge current, then scale back to 50 if this is
            # too much. We checked above that it's > 50
            setpoint = max(max_battery_charge_power - 200, 50)

            previous_import_power = self._current_import_power

            # We should never be importing more than the battery can take
            error = setpoint - current_battery_charge_power
            if previous_import_power > setpoint:
                new_import_power = setpoint
            else:
                # When we're dialling back import power in order to let PV recover, we'll often find that PV takes up
                # some of the slack as it recovers, which means we need to keep stepping. Use a slightly larger P to
                # compensate for this.
                p = 1.5 if error < 0 else 1.0
                new_import_power = previous_import_power + int(p * error)

            # Force a pause on 0W if we're switching between importing and exporting. This stops us from crashing
            # between the two if it somehow end up unstable.
            if (previous_import_power > 0 and new_import_power < 0) or (
                previous_import_power < 0 and new_import_power > 0
            ):
                new_import_power = 0
            else:
                new_import_power = max(min(new_import_power, max_import_power), -max_import_power)

            self._current_import_power = new_import_power

            # Right, let's set that
            _LOGGER.debug(
                "Remote control: Bat: %sW, limit: %sW, error: %sW, import %sW -> %sW",
                current_battery_charge_power,
                max_battery_charge_power,
                error,
                previous_import_power,
                self._current_import_power,
            )

        # If remote control stops, we want to be in Back-up, charging as much as we can
        await self._enable_remote_control(WorkMode.BACK_UP)
        await self._write_active_power(-self._current_import_power)

    async def _update_discharge(self) -> None:
        # For force discharge, normally we can just leave it, and it will do the right thing: respect Min SoC and the
        # Max Discharge Current.

        export_power = self._discharge_power
        inverter_capacity = self._controller.inverter_capacity

        if export_power is None or export_power > inverter_capacity:
            export_power = inverter_capacity

        # If remote control stops, we still want to feed in as much as possible
        await self._enable_remote_control(WorkMode.FEED_IN_FIRST)
        # Positive values = discharge
        await self._write_active_power(export_power)

    async def _enable_remote_control(self, fallback_work_mode: WorkMode) -> None:
        # We set a fallback work mode so that the inverter still does "roughly" the right thing if we disconnect
        # (This might not be available, e.g. on H1 LAN)
        assert self._addresses.work_mode_map is not None
        fallback_work_mode_value = self._addresses.work_mode_map[fallback_work_mode]

        current_work_mode = self._read(self._addresses.work_mode, signed=False)
        if current_work_mode != fallback_work_mode_value and self._addresses.work_mode is not None:
            await self._controller.write_register(self._addresses.work_mode, fallback_work_mode_value)

        if not self._remote_control_enabled:
            self._remote_control_enabled = True
            timeout = self._poll_rate * 2

            # We can't do multi-register writes to these registers
            await self._controller.write_register(self._addresses.timeout_set, timeout)
            await self._controller.write_register(self._addresses.remote_enable, 1)

    async def _disable_remote_control(self, work_mode: WorkMode | None = None) -> None:
        # The strategy periods feature of the foxess app use the remote control register internally. If we disable
        # remote control when a strategy period is active, we'll end up disabling it.
        # We therefore need to be a bit careful, and only disable remote control if we previously enabled it.
        # If we did have it enabled, but then restarted, then we just need to let the watchdog catch it.

        if self._remote_control_enabled:
            self._remote_control_enabled = False
            await self._controller.write_register(self._addresses.remote_enable, 0)

        # This might not be available, e.g. on H1 LAN
        if (
            work_mode is not None
            and self._addresses.work_mode is not None
            and self._addresses.work_mode_map is not None
        ):
            current_work_mode = self._read(self._addresses.work_mode, signed=False)
            work_mode_value = self._addresses.work_mode_map[work_mode]
            if current_work_mode != work_mode_value:
                await self._controller.write_register(self._addresses.work_mode, work_mode_value)

    def _read(self, address: list[int] | int | None, signed: bool) -> int | None:
        if address is None:
            return None
        return self._controller.read(address, signed=signed)

    @property
    def addresses(self) -> list[int]:
        return self._modbus_addresses

    async def poll_complete_callback(self) -> None:
        await self._update()

    async def became_connected_callback(self) -> None:
        self._remote_control_enabled = False
        await self._update()

    def update_callback(self, changed_addresses: set[int]) -> None:
        pass

    def is_connected_changed_callback(self) -> None:
        pass
