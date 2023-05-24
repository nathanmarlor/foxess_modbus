"""Defines the service to write registers"""
import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.core import ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from pymodbus.exceptions import ModbusIOException

from ..const import DOMAIN
from ..modbus_controller import ModbusController
from .utils import get_controller_from_friendly_name_or_device_id

_LOGGER: logging.Logger = logging.getLogger(__package__)


def _must_specify_either_interver_or_friendly_name(data: dict[str, Any]) -> dict[str, Any]:
    if "inverter" not in data and "friendly_name" not in data:
        raise vol.Invalid("required key not provided", path=["inverter"])
    return data


_WRITE_SCHEMA = vol.Schema(
    vol.All(
        {
            # We require either inverter or friendly_name (legacy)
            # Let the value to this be omitted, instead of forcing them to specify ''
            vol.Optional("inverter", description="Inverter"): vol.Any(cv.string, None),
            vol.Optional("friendly_name", description="Friendly Name"): cv.string,
            vol.Required("start_address", description="Start Address"): int,
            vol.Required("values", description="Values"): cv.string,
        },
        _must_specify_either_interver_or_friendly_name,
    )
)


def register(hass: HomeAssistant, inverter_controllers: list[tuple[Any, ModbusController]]) -> None:
    """Register the service with hass"""

    async def _callback(service_data: ServiceCall) -> None:
        await hass.loop.create_task(_write_service(inverter_controllers, service_data, hass))

    hass.services.async_register(
        DOMAIN,
        "write_registers",
        _callback,
        _WRITE_SCHEMA,
    )


async def _write_service(
    mapping: list[tuple[Any, ModbusController]],
    service_data: ServiceCall,
    hass: HomeAssistant,
) -> None:
    """Write service"""
    # Support both for backwards compatibility
    inverter_id = service_data.data.get("inverter")
    friendly_name = service_data.data.get("friendly_name")
    controller = get_controller_from_friendly_name_or_device_id(
        inverter_id if inverter_id is not None else friendly_name, mapping, hass
    )

    try:
        start_address = service_data.data["start_address"]
        values = service_data.data["values"].split(",")
        await controller.write_registers(start_address, values)
    except ModbusIOException as ex:
        _LOGGER.warning(ex, exc_info=True)
        raise HomeAssistantError() from ex
