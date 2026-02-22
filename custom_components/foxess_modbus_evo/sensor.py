"""Sensor platform for foxess_modbus."""

import logging

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common.types import HassData
from .const import DOMAIN
from .entities.connection_status_sensor import ConnectionStatusSensor
from .inverter_profiles import create_entities

_LOGGER = logging.getLogger(__package__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_devices: AddEntitiesCallback) -> None:
    """Setup sensor platform."""

    hass_data: HassData = hass.data[DOMAIN]
    controllers = hass_data[entry.entry_id]["controllers"]

    for controller in controllers:
        async_add_devices([ConnectionStatusSensor(controller)])
        # We have to add sensors which don't depend on other sensors, before we add the sensors which *do* depend on
        # other sensors (like the integration sensors), otherwise HA crashes when trying to create the IntegrationSensor
        # because it can't find the sensor it depends on. See https://github.com/nathanmarlor/foxess_modbus/issues/886
        async_add_devices(create_entities(SensorEntity, controller, filter_depends_on_other_entites=False))
        async_add_devices(create_entities(SensorEntity, controller, filter_depends_on_other_entites=True))
