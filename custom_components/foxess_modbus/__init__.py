"""
Custom integration to integrate FoxESS Modbus with Home Assistant.

For more details about this integration, please refer to
https://github.com/nathanmarlor/foxess_modbus
"""
import asyncio
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Config
from homeassistant.core import HomeAssistant

from .modbus_client import ModbusClient
from .modbus_controller import ModbusController
from .const import DOMAIN
from .const import MODBUS_HOST
from .const import MODBUS_PORT
from .const import PLATFORMS
from .const import STARTUP_MESSAGE

_LOGGER: logging.Logger = logging.getLogger(__package__)


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

    modbus_host = entry.data.get(MODBUS_HOST, "")
    modbus_port = entry.data.get(MODBUS_PORT, 502)

    modbus_client = ModbusClient(modbus_host, modbus_port)
    modbus_controller = ModbusController(hass, modbus_client)

    hass.data[DOMAIN][entry.entry_id] = {"controllers": {"modbus": modbus_controller}}

    # hass.services.async_register(
    #    DOMAIN, "read_register", modbus_controller.read_register
    # )
    # hass.services.async_register(
    #    DOMAIN, "write_register", modbus_controller.write_register
    # )
    #
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
        controllers = hass.data[DOMAIN][entry.entry_id]["controllers"]
        for controller in controllers.values():
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
