from typing import Any
import voluptuous as vol
import asyncio
import logging
from datetime import time

from pymodbus.exceptions import ModbusIOException

from homeassistant.helpers import config_validation as cv
from homeassistant.core import HomeAssistant
from homeassistant.core import ServiceCall

from ..const import DOMAIN
from ..const import FRIENDLY_NAME
from ..modbus_controller import ModbusController

_LOGGER: logging.Logger = logging.getLogger(__package__)


def _seconds_must_be_zero(value: time) -> time:
    if value.second != 0:
        raise vol.Invalid("Seconds component must be 0 if specified")
    return value


def _start_end_must_be_present_if_enabled(data: dict[str, Any]) -> dict[str, Any]:
    if data["enable_force_charge"]:
        if not "start" in data:
            raise vol.Invalid(
                "'start' must be specified if 'enable_force_charge' is True",
                path=["start"],
            )
        if not "end" in data:
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
            vol.Required("device", description="Inverter"): cv.string,
            vol.Required("charge_period", description="Charge Period"): vol.All(
                int, vol.Range(min=0, max=1)
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
    hass.services.async_register(
        DOMAIN,
        "update_charge_period",
        lambda data: asyncio.run_coroutine_threadsafe(
            _handler(inverter_controllers, data), hass.loop
        ),
        _SCHEMA,
    )


async def _handler(
    mapping: list[tuple[Any, ModbusController]], service_data: ServiceCall
) -> None:
    raise Exception("NOOOOO")
