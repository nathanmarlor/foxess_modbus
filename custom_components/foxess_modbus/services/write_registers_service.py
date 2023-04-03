import asyncio
import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.core import ServiceCall
from homeassistant.helpers import config_validation as cv
from pymodbus.exceptions import ModbusIOException

from ..const import DOMAIN
from ..const import FRIENDLY_NAME
from ..modbus_controller import ModbusController

_LOGGER: logging.Logger = logging.getLogger(__package__)

_WRITE_SCHEMA = vol.Schema(
    {
        vol.Optional("friendly_name", description="Friendly Name"): cv.string,
        vol.Required("start_address", description="Start Address"): int,
        vol.Required("values", description="Values"): cv.string,
    }
)


def register(
    hass: HomeAssistant, inverter_controllers: list[tuple[Any, ModbusController]]
) -> None:
    hass.services.async_register(
        DOMAIN,
        "write_registers",
        lambda data: asyncio.run_coroutine_threadsafe(
            _write_service(inverter_controllers, data), hass.loop
        ),
        _WRITE_SCHEMA,
    )


async def _write_service(
    mapping: list[tuple[Any, ModbusController]], service_data: ServiceCall
):
    """Write service"""
    try:
        friendly_name = service_data.data.get(FRIENDLY_NAME, "")
        for inverter, controller in mapping:
            if inverter[FRIENDLY_NAME] == friendly_name:
                if {"start_address", "values"} <= set(service_data.data):
                    start_address = service_data.data["start_address"]
                    values = service_data.data["values"].split(",")
                    await controller.write_registers(start_address, values)
                else:
                    _LOGGER.warning(
                        "Modbus write service called with incorrect data format"
                    )
    except ModbusIOException as ex:
        _LOGGER.warning(ex, exc_info=1)
