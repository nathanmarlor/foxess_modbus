"""Sensor platform for foxess_modbus."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .sensors import inverter_sensors

_LOGGER = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_devices
) -> None:
    """Setup sensor platform."""

    controllers = hass.data[DOMAIN][entry.entry_id]["controllers"]

    async_add_devices(inverter_sensors.sensors(controllers, entry))
