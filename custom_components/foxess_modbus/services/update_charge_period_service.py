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
from pymodbus.exceptions import ModbusIOException

from ..const import DOMAIN
from ..entities.modbus_charge_period_sensors import is_time_value_valid
from ..entities.modbus_charge_period_sensors import parse_time_value
from ..entities.modbus_charge_period_sensors import serialize_time_to_value
from ..modbus_controller import ModbusController
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


def _end_must_be_after_start(data: dict[str, Any]) -> dict[str, Any]:
    if "start" in data and "end" in data:
        start = data["start"]
        end = data["end"]
        if end.hour < start.hour or (end.hour == start.hour and end.minute <= start.minute):
            raise vol.Invalid("'end' must be at least 1 minute after 'start'", path=["end"])
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
            vol.Optional("end", description="Period End"): vol.All(
                cv.time, vol.Range(min=time(hour=0, minute=1)), _seconds_must_be_zero
            ),
        },
        _start_end_must_be_present_if_enabled,
        _end_must_be_after_start,
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
                            vol.Range(min=time(hour=0, minute=1)),
                            _seconds_must_be_zero,
                        ),
                    },
                    _start_end_must_be_present_if_enabled,
                    _end_must_be_after_start,
                )
            ],
            vol.Length(min=2, max=2),
        ),
    }
)


def register(hass: HomeAssistant, inverter_controllers: list[tuple[Any, ModbusController]]) -> None:
    """Register the services with HA"""

    async def _update_charge_period_callback(service_data: ServiceCall) -> None:
        await hass.loop.create_task(_update_charge_period(inverter_controllers, service_data, hass))

    hass.services.async_register(
        DOMAIN,
        "update_charge_period",
        _update_charge_period_callback,
        _UPDATE_CHARGE_PERIOD_SCHEMA,
    )

    async def _update_all_charge_periods_callback(service_data: ServiceCall) -> None:
        await hass.loop.create_task(_update_all_charge_periods(inverter_controllers, service_data, hass))

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
    mapping: list[tuple[Any, ModbusController]],
    service_data: ServiceCall,
    hass: HomeAssistant,
) -> None:
    controller = get_controller_from_friendly_name_or_device_id(service_data.data["inverter"], mapping, hass)

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
    mapping: list[tuple[Any, ModbusController]],
    service_data: ServiceCall,
    hass: HomeAssistant,
) -> None:
    controller = get_controller_from_friendly_name_or_device_id(service_data.data["inverter"], mapping, hass)
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

        period_start_time_value = controller.read(charge_period.period_start_address)
        period_end_time_value = controller.read(charge_period.period_end_address)
        period_enable_charge_from_grid_value = controller.read(charge_period.enable_charge_from_grid_address)

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

        charge_periods[i] = ChargePeriod(
            enable_force_charge=period_start_time_value > 0 or period_end_time_value > 0,
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

    # Make sure that none of the charge periods overlap. Sort by start time, then ensure each doesn't overlap the next
    sorted_enabled_periods = sorted((x for x in charge_periods if x.enable_force_charge), key=lambda x: x.start)
    for i, charge_period in enumerate(sorted_enabled_periods):
        if i == 0:
            continue
        previous = sorted_enabled_periods[i - 1]
        # It's permissible to have two periods which have the same start/end time (at least the foxcloud app allows it)
        if charge_period.start < previous.end and previous.start < charge_period.end:
            raise HomeAssistantError(
                f"Charge period {i} {previous.start}-{previous.end} overlaps charge period {i + 1} "
                f"{charge_period.start}-{charge_period.end}"
            )

    # List of (address, value)
    writes: list[tuple[int, int]] = []
    for charge_period, config in zip(charge_periods, controller.charge_periods, strict=True):
        writes.append(
            (
                config.period_start_address,
                serialize_time_to_value(charge_period.start) if charge_period.enable_force_charge else 0,
            )
        )
        writes.append(
            (
                config.period_end_address,
                serialize_time_to_value(charge_period.end) if charge_period.enable_force_charge else 0,
            )
        )
        writes.append(
            (
                config.enable_charge_from_grid_address,
                1 if charge_period.enable_charge_from_grid else 0,
            )
        )

    # We expect all of the writes to have a contiguous set of addresses
    write_values: list[int] = [None] * len(writes)  # type: ignore
    write_start_address = min(write[0] for write in writes)

    for address, value in writes:
        i = address - write_start_address
        assert i < len(write_values)
        assert write_values[i] is None
        write_values[i] = value

    assert not any(x for x in write_values if x is None)

    try:
        await controller.write_registers(write_start_address, write_values)
    except ModbusIOException as ex:
        _LOGGER.warning(ex, exc_info=True)
        raise HomeAssistantError() from ex
