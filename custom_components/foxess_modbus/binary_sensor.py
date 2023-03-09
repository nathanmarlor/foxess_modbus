"""Sensor platform for foxess_modbus."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import CONFIG
from .const import CONNECTION
from .const import CONTROLLER
from .const import DOMAIN
from .const import FRIENDLY_NAME
from .const import H1
from .const import INVERTER
from .const import LAN
from .sensors import h1_aux_binary_sensors

_LOGGER = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_devices
) -> None:
    """Setup sensor platform."""

    controllers = hass.data[DOMAIN][entry.entry_id][CONTROLLER]
    config = hass.data[DOMAIN][entry.entry_id][CONFIG]

    friendly_name = config[FRIENDLY_NAME]
    inverter_type = config[INVERTER]
    connection_type = config[CONNECTION]
    inv_details = (friendly_name, inverter_type, connection_type)

    if inverter_type == H1:
        if connection_type == LAN:
            sensors = []
        else:
            sensors = h1_aux_binary_sensors.binary_sensors(
                controllers, entry, inv_details
            )

    async_add_devices(sensors)
