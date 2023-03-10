"""Sensor"""
import logging

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_IDENTIFIERS
from homeassistant.const import ATTR_MANUFACTURER
from homeassistant.const import ATTR_MODEL
from homeassistant.const import ATTR_NAME

from ..common.callback_controller import CallbackController
from ..const import DOMAIN
from .sensor_desc import SensorDescription

_LOGGER = logging.getLogger(__name__)


class ModbusSensor(SensorEntity):
    """Sensor class."""

    def __init__(
        self,
        controller: CallbackController,
        entity_description: SensorDescription,
        entry: ConfigEntry,
        inv_details,
    ) -> None:
        """Initialize the sensor."""

        self._controller = controller
        self._entity_description = entity_description
        self._entry = entry
        self._inv_details = inv_details
        self.entity_id = "sensor." + self._get_unique_id()

    @property
    def unique_id(self) -> str:
        return "foxess_modbus_" + self._get_unique_id()

    @property
    def device_info(self):
        friendly_name, inv_type, conn_type = self._inv_details
        if friendly_name != "":
            attr_name = f"FoxESS - Modbus ({friendly_name})"
        else:
            attr_name = "FoxESS - Modbus"

        return {
            ATTR_IDENTIFIERS: {(DOMAIN, self._entry.entry_id)},
            ATTR_NAME: attr_name,
            ATTR_MODEL: f"{inv_type} - {conn_type}",
            ATTR_MANUFACTURER: "FoxESS",
        }

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._entity_description.name

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        value = self._controller.read(self._entity_description.address)
        if value is not None:
            if self._entity_description.scale is not None:
                value = value * self._entity_description.scale
            if self._entity_description.post_process is not None:
                return self._entity_description.post_process(value)

        return value

    @property
    def native_unit_of_measurement(self) -> str:
        """Return native unit of measurement"""
        return self._entity_description.native_unit_of_measurement

    @property
    def icon(self) -> str:
        """Return the icon of the sensor."""
        return self._entity_description.icon

    @property
    def device_class(self) -> SensorDeviceClass:
        """Return the device class of the sensor."""
        return self._entity_description.device_class

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state.
        False if entity pushes its state to HA.
        """
        return self._entity_description.should_poll

    async def async_added_to_hass(self) -> None:
        """Add update callback after being added to hass."""
        await super().async_added_to_hass()
        self._controller.add_update_listener(self)

    def update_callback(self) -> None:
        """Schedule a state update."""
        self.schedule_update_ha_state(True)

    def _get_unique_id(self):
        """Get unique ID"""
        friendly_name, _, _ = self._inv_details
        if friendly_name != "":
            return f"{friendly_name}_{self._entity_description.key}"
        else:
            return f"{self._entity_description.key}"
