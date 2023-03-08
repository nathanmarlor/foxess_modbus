"""Sensor platform for foxess_modbus."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONFIG
from .const import CONNECTION
from .const import CONTROLLER
from .const import DOMAIN
from .const import H1
from .const import INVERTER
from .const import LAN
from .sensors import h1_aux_sensors
from .sensors import h1_lan_sensors

_LOGGER = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_devices
) -> None:
    """Setup sensor platform."""

    controllers = hass.data[DOMAIN][entry.entry_id][CONTROLLER]
    config = hass.data[DOMAIN][entry.entry_id][CONFIG]

    inverter_type = config[INVERTER]
    connection_type = config[CONNECTION]

    if inverter_type == H1:
        if connection_type == LAN:
            sensors = h1_lan_sensors.sensors(controllers, entry)
        else:
            sensors = h1_aux_sensors.sensors(controllers, entry)

    async_add_devices(sensors)
