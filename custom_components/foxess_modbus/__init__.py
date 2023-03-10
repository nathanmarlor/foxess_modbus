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

from .const import DOMAIN
from .const import FRIENDLY_NAME
from .const import INVERTER_CONN
from .const import INVERTERS
from .const import MODBUS_HOST
from .const import MODBUS_PORT
from .const import MODBUS_SLAVE
from .const import PLATFORMS
from .const import STARTUP_MESSAGE
from .modbus_client import ModbusClient
from .modbus_controller import ModbusController

_LOGGER: logging.Logger = logging.getLogger(__package__)

_WRITE_SCHEMA = vol.Schema(
    {
        vol.Required("start_address", description="Start Address"): int,
        vol.Required("values", description="Values"): str,
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

    inverter_controller = []
    for inverter in entry.data.values():
        _LOGGER.debug(
            f"Setting up inverter - ({inverter[MODBUS_HOST]}, {inverter[MODBUS_PORT]}, {inverter[MODBUS_SLAVE]}, {inverter[FRIENDLY_NAME]})"
        )
        modbus_client = ModbusClient(
            inverter[MODBUS_HOST], inverter[MODBUS_PORT], inverter[MODBUS_SLAVE]
        )
        modbus_controller = ModbusController(
            hass, modbus_client, inverter[INVERTER_CONN]
        )

        inverter_controller.append((inverter, modbus_controller))

    hass.data[DOMAIN][entry.entry_id] = {
        INVERTERS: inverter_controller,
    }

    hass.services.async_register(
        DOMAIN, "write_registers", modbus_controller.write, _WRITE_SCHEMA
    )

    hass.data[DOMAIN][entry.entry_id]["unload"] = entry.add_update_listener(
        async_reload_entry
    )

    return True


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
