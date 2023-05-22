"""Sensor platform for foxess_modbus."""
import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .const import INVERTERS
from .inverter_profiles import create_entities

_LOGGER = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_devices: AddEntitiesCallback) -> None:
    """Setup numbers platform."""

    inverters = hass.data[DOMAIN][entry.entry_id][INVERTERS]

    for inverter, controller in inverters:
        async_add_devices(create_entities(NumberEntity, controller, entry, inverter))
