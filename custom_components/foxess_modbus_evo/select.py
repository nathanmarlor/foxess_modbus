"""Sensor platform for foxess_modbus."""  # noqa: A005

import logging

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common.types import HassData
from .const import DOMAIN
from .inverter_profiles import create_entities

_LOGGER = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_devices: AddEntitiesCallback) -> None:
    """Setup select platform."""

    hass_data: HassData = hass.data[DOMAIN]
    controllers = hass_data[entry.entry_id]["controllers"]

    for controller in controllers:
        async_add_devices(create_entities(SelectEntity, controller))
