"""Sensor platform for foxess_modbus."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .const import INVERTERS
from .inverter_profiles import inverter_connection_type_profile_from_config

_LOGGER = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_devices
) -> None:
    """Setup sensor platform."""

    inverters = hass.data[DOMAIN][entry.entry_id][INVERTERS]

    for inverter, controller in inverters:
        async_add_devices(
            inverter_connection_type_profile_from_config(inverter).create_sensors(
                controller, entry, inverter
            )
        )
