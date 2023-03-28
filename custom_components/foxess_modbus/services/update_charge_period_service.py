from typing import Any
import voluptuous as vol
import asyncio
import logging

from pymodbus.exceptions import ModbusIOException

from homeassistant.helpers import config_validation as cv
from homeassistant.core import HomeAssistant

from ..const import DOMAIN
from ..const import FRIENDLY_NAME
from ..modbus_controller import ModbusController

_LOGGER: logging.Logger = logging.getLogger(__package__)

_WRITE_SCHEMA = vol.Schema(
    {
        vol.Required("friendly_name", description="Friendly Name"): cv.string,
        vol.Required("start_address", description="Start Address"): int,
        vol.Required("values", description="Values"): cv.string,
    }
)


def register(
    hass: HomeAssistant, inverter_controllers: list[tuple[Any, ModbusController]]
) -> None:
    hass.services.async_register(
        DOMAIN,
        "update_charge_period",
        lambda data: None,
        _WRITE_SCHEMA,
    )
