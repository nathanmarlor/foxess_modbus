"""Defines the services to update charge periods"""

import logging
from dataclasses import dataclass
from datetime import time
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv

from ..const import DOMAIN
from ..entities.modbus_charge_period_config import ModbusChargePeriodAddressConfig
from ..entities.modbus_charge_period_sensors import is_time_value_valid
from ..entities.modbus_charge_period_sensors import parse_time_value
from ..entities.modbus_charge_period_sensors import serialize_time_to_value
from ..modbus_controller import ModbusController
from ..vendor.pymodbus import ModbusIOException
from .utils import get_controller_from_friendly_name_or_device_id

_LOGGER: logging.Logger = logging.getLogger(__package__)


def _integer(value: Any) -> int:
    """Validate and coerce a boolean value."""
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            pass
    raise vol.Invalid(f"invalid int value {value}")


def _seconds_must_be_zero(value: time) -> time:
    if value.second != 0:
        raise vol.Invalid("Seconds component must be 0 if specified")
    return value


def _start_end_must_be_present_if_enabled(data: dict[str, Any]) -> dict[str, Any]:
    if data["enable_force_charge"]:
        if "start" not in data:
            raise vol.Invalid(
                "'start' must be specified if 'enable_force_charge' is True",
                path=["start"],
            )
        if "end" not in data:
            raise vol.Invalid("'end' must be specified if 'enable_force_charge' is True", path=["end"])
    return data


def _end_must_not_be_start_if_enabled(data: dict[str, Any]) -> dict[str, Any]:
    if data["enable_force_charge"] and "start" in data and "end" in data:
        start = data["start"]
        end = data["end"]
        if start.hour == end.hour and start.minute == end.minute:
            raise vol.Invalid("'end' must not be the same as 'start'", path=["end"])
    return data


_UPDATE_CHARGE_PERIOD_SCHEMA = vol.Schema(
    vol.All(
        {
            # Let the value to this be omitted, instead of forcing them to specify ''
            vol.Required("inverter", description="Inverter"): vol.Any(cv.string, None),
            vol.Required("charge_period", description="Charge Period"): vol.All(_integer, vol.Range(min=1, max=2)),
            vol.Required("enable_force_charge", description="Enable force charge"): cv.boolean,
            vol.Required("enable_charge_from_grid", description="Enable charge from grid"): cv.boolean,
            vol.Optional("start", description="Period Start"): vol.All(cv.time, _seconds_must_be_zero),
            vol.Optional("end", description="Period End"): vol.All(cv.time, _seconds_must_be_zero),
        },
        _start_end_must_be_present_if_enabled,
        _end_must_not_be_start_if_enabled,
    )
)

_UPDATE_ALL_CHARGE_PERIODS_SCHEMA = vol.Schema(
    {
        # Let the value to this be omitted, instead of forcing them to specify ''
        vol.Required("inverter", description="Inverter"): vol.Any(cv.string, None),
        vol.Required("charge_periods", description="Charge Periods"): vol.All(
            [
                vol.All(
                    {
                        vol.Required("enable_force_charge", description="Enable force charge"): cv.boolean,
                        vol.Required(
                            "enable_charge_from_grid",
                            description="Enable charge from grid",
                        ): cv.boolean,
                        vol.Optional("start", description="Period Start"): vol.All(cv.time, _seconds_must_be_zero),
                        vol.Optional("end", description="Period End"): vol.All(
                            cv.time,
                            _seconds_must_be_zero,
                        ),
                    },
                    _start_end_must_be_present_if_enabled,
                    _end_must_not_be_start_if_enabled,
                )
            ],
            vol.Length(min=2, max=2),
        ),
    }
)


def register(hass: HomeAssistant, controllers: list[ModbusController]) -> None:
    """Register the services with HA"""

    async def _update_charge_period_callback(service_data: ServiceCall) -> None:
        await hass.loop.create_task(_update_charge_period(controllers, service_data, hass))

    hass.services.async_register(
        DOMAIN,
        "update_charge_period",
        _update_charge_period_callback,
        _UPDATE_CHARGE_PERIOD_SCHEMA,
    )

    async def _update_all_charge_periods_callback(service_data: ServiceCall) -> None:
        await hass.loop.create_task(_update_all_charge_periods(controllers, service_data, hass))

    hass.services.async_register(
        DOMAIN,
        "update_all_charge_periods",
        _update_all_charge_periods_callback,
        _UPDATE_ALL_CHARGE_PERIODS_SCHEMA,
    )


@dataclass
class ChargePeriod:
    """Holds the data for a single charge period"""

    enable_force_charge: bool
    enable_charge_from_grid: bool
    start: time
    end: time


async def _update_all_charge_periods(
    controllers: list[ModbusController],
    service_data: ServiceCall,
    hass: HomeAssistant,
) -> None:
    controller = get_controller_from_friendly_name_or_device_id(service_data.data["inverter"], controllers, hass)

    charge_periods: list[ChargePeriod] = []
    for charge_period in service_data.data["charge_periods"]:
        charge_periods.append(
            ChargePeriod(
                enable_force_charge=charge_period["enable_force_charge"],
                enable_charge_from_grid=charge_period["enable_charge_from_grid"],
                start=charge_period.get("start", time(hour=0, minute=0)),
                end=charge_period.get("end", time(hour=0, minute=0)),
            )
        )

    await _set_charge_periods(controller, charge_periods)


async def _update_charge_period(
    controllers: list[ModbusController],
    service_data: ServiceCall,
    hass: HomeAssistant,
) -> None:
    controller = get_controller_from_friendly_name_or_device_id(service_data.data["inverter"], controllers, hass)
    charge_period_index = service_data.data["charge_period"] - 1

    if charge_period_index >= len(controller.charge_periods):
        raise HomeAssistantError(f"Inverter does not support setting charge period {charge_period_index + 1}")

    charge_periods: list[ChargePeriod] = [None] * len(controller.charge_periods)  # type: ignore

    charge_periods[charge_period_index] = ChargePeriod(
        enable_force_charge=service_data.data["enable_force_charge"],
        enable_charge_from_grid=service_data.data["enable_charge_from_grid"],
        start=service_data.data.get("start", time(hour=0, minute=0)),
        end=service_data.data.get("end", time(hour=0, minute=0)),
    )

    # Add the other charge periods, which aren't being set right now, to charge_periods
    for i, charge_period in enumerate(controller.charge_periods):
        if i == charge_period_index:
            continue

        period_start_time_value = controller.read(charge_period.addresses.period_start_address, signed=False)
        period_end_time_value = controller.read(charge_period.addresses.period_end_address, signed=False)
        period_enable_charge_from_grid_value = controller.read(
            charge_period.addresses.enable_charge_from_grid_address, signed=False
        )

        if (
            period_start_time_value is None
            or period_end_time_value is None
            or period_enable_charge_from_grid_value is None
        ):
            raise HomeAssistantError(
                f"Data for charge period {i + 1} is not available. Please try again in a few seconds"
            )
        if not is_time_value_valid(period_start_time_value) or not is_time_value_valid(period_end_time_value):
            raise HomeAssistantError(
                f"Start time '{period_start_time_value}' or end time '{period_end_time_value}' for charge period "
                f"{i + 1} is not valid"
            )

        # Inverters which use the time-group charge period system (e.g. the H3 Smart) control force charge
        # via a dedicated group-enable register, rather than inferring it from the start/end times.
        if charge_period.addresses.enable_address is not None:
            enable_value = controller.read(charge_period.addresses.enable_address, signed=False)
            if enable_value is None:
                raise HomeAssistantError(
                    f"Data for charge period {i + 1} is not available. Please try again in a few seconds"
                )
            enable_force_charge = enable_value > 0
        else:
            enable_force_charge = period_start_time_value > 0 or period_end_time_value > 0

        charge_periods[i] = ChargePeriod(
            enable_force_charge=enable_force_charge,
            enable_charge_from_grid=period_enable_charge_from_grid_value > 0,
            start=parse_time_value(period_start_time_value),
            end=parse_time_value(period_end_time_value),
        )

    await _set_charge_periods(controller, charge_periods)


async def _set_charge_periods(controller: ModbusController, charge_periods: list[ChargePeriod]) -> None:
    if len(controller.charge_periods) == 0:
        raise HomeAssistantError("Inverter does not support setting charge periods")
    if len(charge_periods) > len(controller.charge_periods):
        raise HomeAssistantError(f"Inverter does not support setting charge period {len(controller.charge_periods)}")
    if len(charge_periods) < len(controller.charge_periods):
        raise HomeAssistantError(
            f"Entries must be provided for all charge periods. Expected {len(controller.charge_periods)} "
            f"charge periods, got {len(charge_periods)}"
        )

    # The current foxcloud version doesn't seem to impose any restrictions on charge periods overlapping.
    # (One charge period can contain another, or starts/ends can overlap).
    # Mirror this for consistancy, even though it is a little odd.

    # Inverters which use the time-group charge period system (e.g. the H3 Smart) only run their time
    # periods when the Time Period System is enabled (register 48000 = 1, the inverter's "Timer"/"Modus
    # Terminierer" mode). Following the H1 semantics of an additive charge-period window, we tie this to
    # whether any charge period is enabled: if any is enabled the time period system is switched on, and
    # when all of them are disabled it is switched off again, so that the inverter returns to its normal
    # (e.g. "Self Use") mode, just like the H1 does.
    writes = []
    is_time_group = False
    for charge_period, config in zip(charge_periods, controller.charge_periods, strict=True):
        if config.addresses.enable_address is not None:
            is_time_group = True
        writes.extend(_make_charge_period_writes(config.addresses, controller, charge_period))

    # Don't write the Time Period Mode flag (48000) from every enabled period: it's a single global register.
    if is_time_group:
        any_enabled = any(cp.enable_force_charge for cp in charge_periods)
        writes.append((48000, 1 if any_enabled else 0))

    write_blocks = _split_into_contiguous_runs(writes)

    for write_start_address, write_values in write_blocks:
        try:
            await controller.write_registers(write_start_address, write_values)
        except ModbusIOException as ex:
            _LOGGER.warning(ex, exc_info=True)
            raise HomeAssistantError() from ex


def _make_charge_period_writes(
    config: ModbusChargePeriodAddressConfig,
    controller: ModbusController,
    charge_period: ChargePeriod,
) -> list[tuple[int, int]]:
    """Builds the (address, value) register writes for a single charge period."""

    if config.enable_address is not None:
        return _make_time_group_writes(config, controller, charge_period)

    return [
        (
            config.period_start_address,
            serialize_time_to_value(charge_period.start) if charge_period.enable_force_charge else 0,
        ),
        (
            config.period_end_address,
            serialize_time_to_value(charge_period.end) if charge_period.enable_force_charge else 0,
        ),
        (
            config.enable_charge_from_grid_address,
            1 if charge_period.enable_charge_from_grid else 0,
        ),
    ]


def _make_time_group_writes(
    config: ModbusChargePeriodAddressConfig,
    controller: ModbusController,
    charge_period: ChargePeriod,
) -> list[tuple[int, int]]:
    """Builds the register writes for an inverter which uses the time-group charge period system (e.g. H3 Smart).

    A time group is a contiguous block of 10 registers (see FoxESS Modbus protocol, Table 3-11). When a
    charge period is enabled, the group is activated in Force Charge mode (Work Mode 6). "Charge from grid"
    simply controls the force-charge power (FDPWR): enabled charges from the grid at the inverter's full
    capacity, disabled charges from PV only (FDPWR = 0).

    When a charge period is disabled, the group is turned off and the force-charge power is cleared, so that
    the "charge from grid" state doesn't linger as on. The previously configured times are left intact.
    """

    base = config.enable_address
    assert base is not None

    if not charge_period.enable_force_charge:
        return [(base, 0), (base + 6, 0)]

    # The charge-period card doesn't expose a charge power or SoC target, so we use sensible defaults:
    # charge up to 100% (from the grid if 'charge from grid' is enabled, otherwise PV only) at the inverter's
    # full capacity.
    max_soc = 100
    min_soc = 10
    fdpwr = controller.inverter_capacity if charge_period.enable_charge_from_grid else 0

    return [
        (base, 1),  # +0: Time group enable
        (base + 1, serialize_time_to_value(charge_period.start)),  # +1: Start time (high byte=hour, low=min)
        (base + 2, serialize_time_to_value(charge_period.end)),  # +2: End time (high byte=hour, low=min)
        (base + 3, 6),  # +3: Work mode = Force Charge
        (base + 4, (max_soc << 8) | min_soc),  # +4: MaxSoC (high byte) | MinSoC (low byte)
        (base + 5, min_soc),  # +5: FDSOC
        (base + 6, fdpwr),  # +6: FDPWR (force charge power, W)
        (base + 7, 0),  # +7: reserve
        (base + 8, 0),  # +8: reserve
        (base + 9, 1),  # +9: enable flag (undocumented, but required for force charge)
    ]


def _split_into_contiguous_runs(writes: list[tuple[int, int]]) -> list[tuple[int, list[int]]]:
    """Groups a list of (address, value) writes into contiguous register runs, each returned as (start, values)."""

    runs: list[tuple[int, list[int]]] = []
    for address, value in sorted(writes, key=lambda x: x[0]):
        if runs and address == runs[-1][0] + len(runs[-1][1]):
            start, values = runs[-1]
            runs[-1] = (start, [*values, value])
        else:
            runs.append((address, [value]))

    return runs
