"""
Custom integration to integrate FoxESS Modbus with Home Assistant.

For more details about this integration, please refer to
https://github.com/nathanmarlor/foxess_modbus
"""
import asyncio
import logging

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
from pymodbus.exceptions import ModbusIOException

from .const import DOMAIN
from .const import FRIENDLY_NAME
from .const import INVERTERS
from .const import MAX_READ
from .const import MODBUS_SLAVE
from .const import MODBUS_TYPE
from .const import PLATFORMS
from .const import POLL_RATE
from .const import SERIAL
from .const import STARTUP_MESSAGE
from .const import TCP
from .inverter_profiles import inverter_connection_type_profile_from_config
from .modbus_client import ModbusClient
from .modbus_controller import ModbusController

_LOGGER: logging.Logger = logging.getLogger(__package__)

_WRITE_SCHEMA = vol.Schema(
    {
        vol.Required("friendly_name", description="Friendly Name"): cv.string,
        vol.Required("start_address", description="Start Address"): int,
        vol.Required("values", description="Values"): cv.string,
    }
)


async def async_setup(hass: HomeAssistant, config: Config):
    """Set up this integration using YAML is not supported."""
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up this integration using UI."""
    if hass.data.get(DOMAIN) is None:
        hass.data.setdefault(DOMAIN, {})
        _LOGGER.info(STARTUP_MESSAGE)

    for platform in PLATFORMS:
        if entry.options.get(platform, True):
            hass.async_add_job(
                hass.config_entries.async_forward_entry_setup(entry, platform)
            )

    if len(entry.options) > 0:
        # overwrite data with options
        entry.data = entry.options

    poll_rate = entry.data.get(POLL_RATE, 10)
    max_read = entry.data.get(MAX_READ, 8)

    def create_controller(hass, client, inverter):
        controller = ModbusController(
            hass,
            client,
            inverter_connection_type_profile_from_config(inverter),
            inverter[MODBUS_SLAVE],
            poll_rate,
            max_read,
        )
        inverter_controller.append((inverter, controller))

    inverter_controller = []
    inverters = {k: v for k, v in entry.data.items() if k in (TCP, SERIAL)}
    # create controllers for inverters
    for modbus_type, host_dict in inverters.items():
        for host, name_dict in host_dict.items():
            params = {MODBUS_TYPE: modbus_type}
            if modbus_type == TCP:
                params.update({"host": host.split(":")[0], "port": host.split(":")[1]})
            else:
                params.update({"port": host, "baudrate": 9600})
            client = ModbusClient(hass, params)
            for _, inverter in name_dict.items():
                create_controller(hass, client, inverter)

    hass.services.async_register(
        DOMAIN,
        "write_registers",
        lambda data: asyncio.run_coroutine_threadsafe(
            write_service(inverter_controller, data), hass.loop
        ),
        _WRITE_SCHEMA,
    )

    hass.data[DOMAIN][entry.entry_id] = {
        INVERTERS: inverter_controller,
    }

    hass.data[DOMAIN][entry.entry_id]["unload"] = entry.add_update_listener(
        async_reload_entry
    )

    return True


async def write_service(*args):
    """Write service"""
    try:
        mapping, service_data = args[0], args[1]
        for inverter, controller in mapping:
            if inverter[FRIENDLY_NAME] == service_data.data[FRIENDLY_NAME]:
                await controller.write(service_data)
    except ModbusIOException as ex:
        _LOGGER.warning(ex, exc_info=1)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Handle removal of an entry."""
    unloaded = all(
        await asyncio.gather(
            *[
                hass.config_entries.async_forward_entry_unload(entry, platform)
                for platform in PLATFORMS
            ]
        )
    )

    if unloaded:
        controllers = hass.data[DOMAIN][entry.entry_id][INVERTERS]
        for _, controller in controllers:
            controller.unload()

        hass.data[DOMAIN][entry.entry_id]["unload"]()
        hass.data[DOMAIN].pop(entry.entry_id)

    return unloaded


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await async_unload_entry(hass, entry)
    await async_setup_entry(hass, entry)


async def options_update_listener(hass: HomeAssistant, config_entry: ConfigEntry):
    """Handle options update."""
    await hass.config_entries.async_reload(config_entry.entry_id)
