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
from .entities import xx1_aux_numbers

_LOGGER = logging.getLogger(__package__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_devices
) -> None:
    """Setup numbers platform."""

    inverters = hass.data[DOMAIN][entry.entry_id][INVERTERS]

    for inverter, controller in inverters:
        if inverter[INVERTER_MODEL] == H1:
            if inverter[INVERTER_CONN] == LAN:
                numbers = []
            else:
                numbers = xx1_aux_numbers.numbers(controller, entry, inverter)

        async_add_devices(numbers)