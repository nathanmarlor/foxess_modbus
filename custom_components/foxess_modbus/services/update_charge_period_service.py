import logging
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
            raise vol.Invalid(
                "'end' must be specified if 'enable_force_charge' is True", path=["end"]
            )
    return data


def _end_must_be_after_start(data: dict[str, Any]) -> dict[str, Any]:
    if "start" in data and "end" in data:
        start = data["start"]
        end = data["end"]
        if end.hour < start.hour or (
            end.hour == start.hour and end.minute <= start.minute
        ):
            raise vol.Invalid(
                "'end' must be at least 1 minute after 'start'", path=["end"]
            )
    return data


_SCHEMA = vol.Schema(
    vol.All(
        {
            # Let the value to this be omitted, instead of forcing them to specify ''
            vol.Required("inverter", description="Inverter"): vol.Any(cv.string, None),
            vol.Required("charge_period", description="Charge Period"): vol.All(
                _integer, vol.Range(min=1, max=2)
            ),
            vol.Required(
                "enable_force_charge", description="Enable force charge"
            ): cv.boolean,
            vol.Required(
                "enable_charge_from_grid", description="Enable charge from grid"
            ): cv.boolean,
            vol.Optional("start", description="Period Start"): vol.All(
                cv.time, _seconds_must_be_zero
            ),
            vol.Optional("end", description="Period End"): vol.All(
                cv.time, vol.Range(min=time(hour=0, minute=1)), _seconds_must_be_zero
            ),
        },
        _start_end_must_be_present_if_enabled,
        _end_must_be_after_start,
    )
)


def register(
    hass: HomeAssistant, inverter_controllers: list[tuple[Any, ModbusController]]
) -> None:
    """Register the service with HA"""

    async def _callback(service_data: ServiceCall):
        await hass.loop.create_task(_handler(inverter_controllers, service_data, hass))

    hass.services.async_register(
        DOMAIN,
        "update_charge_period",
        _callback,
        _SCHEMA,
    )


# pylint: disable-next=too-many-locals
async def _handler(
    mapping: list[tuple[Any, ModbusController]],
    service_data: ServiceCall,
    hass: HomeAssistant,
) -> None:
    controller = get_controller_from_friendly_name_or_device_id(
        service_data.data["inverter"], mapping, hass
    )
    charge_period_index = service_data.data["charge_period"] - 1
    enable_force_charge = service_data.data["enable_force_charge"]
    enable_charge_from_grid = service_data.data["enable_charge_from_grid"]
    start_time = service_data.data["start"]
    end_time = service_data.data["end"]

    type_profile = controller.connection_type_profile

    if len(type_profile.charge_periods) == 0:
        raise HomeAssistantError("Inverter does not support setting charge periods")
    if charge_period_index >= len(type_profile.charge_periods):
        raise HomeAssistantError(
            f"Inverter does not support setting charge period {charge_period_index + 1}"
        )

    assert 0 <= charge_period_index < len(type_profile.charge_periods)

    # List of (address, value)
    writes: list[tuple[int, int]] = []

    for i, charge_period in enumerate(type_profile.charge_periods):
        if i != charge_period_index:
            period_start_time_value = controller.read(
                charge_period.period_start_address
            )
            period_end_time_value = controller.read(charge_period.period_end_address)
            period_enable_charge_from_grid_value = controller.read(
                charge_period.enable_charge_from_grid_address
            )

            if (
                period_start_time_value is None
                or period_end_time_value is None
                or period_enable_charge_from_grid_value is None
            ):
                raise HomeAssistantError(
                    f"Data for charge period {i + 1} is not available. Please try again in a few seconds"
                )
            if not is_time_value_valid(
                period_start_time_value
            ) or not is_time_value_valid(period_end_time_value):
                raise HomeAssistantError(
                    f"Start time '{period_start_time_value}' or end time '{period_end_time_value}' for charge period {i + 1} is not valid"
                )

            writes.append((charge_period.period_start_address, period_start_time_value))
            writes.append((charge_period.period_end_address, period_end_time_value))
            writes.append(
                (
                    charge_period.enable_charge_from_grid_address,
                    period_enable_charge_from_grid_value,
                )
            )

            # Make sure that this charge period does not overlap the one being set
            if enable_force_charge:
                period_start_time = parse_time_value(period_start_time_value)
                period_end_time = parse_time_value(period_end_time_value)

                # It's permissible to have two periods which have the same start/end time (at least the foxcloud app allows it)
                if period_start_time < end_time and start_time < period_end_time:
                    raise HomeAssistantError(
                        f"Specified period {start_time}-{end_time} overlaps existing charge period {i + 1} {period_start_time}-{period_end_time}"
                    )

    # We expect enable_charge_from_grid, start, end to be next to each other, in that order
    charge_period = type_profile.charge_periods[charge_period_index]

    writes.append(
        (
            charge_period.period_start_address,
            serialize_time_to_value(start_time) if enable_force_charge else 0,
        )
    )
    writes.append(
        (
            charge_period.period_end_address,
            serialize_time_to_value(end_time) if enable_force_charge else 0,
        )
    )
    writes.append(
        (
            charge_period.enable_charge_from_grid_address,
            1 if enable_charge_from_grid else 0,
        )
    )

    # We expect all of the writes to have a contiguous set of addresses
    write_values = [None] * len(writes)
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
        _LOGGER.warning(ex, exc_info=1)
        raise HomeAssistantError() from ex
