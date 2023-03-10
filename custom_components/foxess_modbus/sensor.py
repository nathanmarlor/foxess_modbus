"""Sensor platform for foxess_modbus."""
import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .const import H1
from .const import INVERTER_CONN
from .const import INVERTER_MODEL
from .const import INVERTERS
from .const import LAN
from .sensors import h1_aux_sensors
from .sensors import h1_lan_sensors

_LOGGER = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_devices
) -> None:
    """Setup sensor platform."""

    inverters = hass.data[DOMAIN][entry.entry_id][INVERTERS]

    for inverter, controller in inverters:
        if inverter[INVERTER_MODEL] == H1:
            if inverter[INVERTER_CONN] == LAN:
                sensors = h1_lan_sensors.sensors(controller, entry, inverter)
            else:
                sensors = h1_aux_sensors.sensors(controller, entry, inverter)

        async_add_devices(sensors)
