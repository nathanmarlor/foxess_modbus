import logging
from typing import Any

import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.core import ServiceCall
from homeassistant.core import ServiceResponse
from homeassistant.core import SupportsResponse
from homeassistant.helpers import config_validation as cv

from ..common.types import RegisterType
from ..const import DOMAIN
from ..modbus_controller import ModbusController
from .utils import get_controller_from_friendly_name_or_device_id

_LOGGER: logging.Logger = logging.getLogger(__package__)

_READ_SCHEMA = vol.Schema(
    vol.All(
        {
            # Let the value to this be omitted, instead of forcing them to specify ''
            vol.Required("inverter", description="Inverter"): vol.Any(cv.string, None),
            vol.Required("start_address", description="Start Address"): cv.positive_int,
            vol.Required("count", description="Values"): cv.positive_int,
            vol.Required("type", description="Type of register to read"): vol.In(["input", "holding"]),
        },
    )
)


def register(hass: HomeAssistant, controllers: list[ModbusController]) -> None:
    """Register the service with hass"""

    async def _callback(service_data: ServiceCall) -> ServiceResponse:
        return await hass.async_create_task(_read_service(controllers, service_data, hass))

    hass.services.async_register(
        DOMAIN,
        "read_registers",
        _callback,
        _READ_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


async def _read_service(
    controllers: list[ModbusController],
    service_data: ServiceCall,
    hass: HomeAssistant,
) -> ServiceResponse:
    """Write service"""
    # Support both for backwards compatibility
    inverter_id = service_data.data.get("inverter")
    friendly_name = service_data.data.get("friendly_name")
    controller = get_controller_from_friendly_name_or_device_id(
        inverter_id if inverter_id is not None else friendly_name, controllers, hass
    )

    response: dict[str, Any] = {}

    try:
        start_address = service_data.data["start_address"]
        num_registers = service_data.data["count"]
        types = {"input": RegisterType.INPUT, "holding": RegisterType.HOLDING}
        register_type = types[service_data.data["type"]]
        values = await controller.read_registers(start_address, num_registers, register_type)
        response_values = {}
        for i in range(num_registers):
            response_values[start_address + i] = values[i]
        response["values"] = response_values
    except Exception as ex:
        _LOGGER.warning(ex, exc_info=True)
        response["error"] = str(ex)

    if service_data.return_response:
        return response

    return None
