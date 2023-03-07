"""Sensor"""
import logging
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_IDENTIFIERS
from homeassistant.const import ATTR_NAME
from homeassistant.helpers.device_registry import DeviceEntryType

from ..common.callback_controller import CallbackController

from ..const import ATTR_ENTRY_TYPE
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
    ) -> None:
        """Initialize the sensor."""

        self._controller = controller
        self._entity_description = entity_description

        self._attributes = {}
        self._attr_extra_state_attributes = {}

        self._attr_device_info = {
            ATTR_IDENTIFIERS: {(DOMAIN, entry.entry_id)},
            ATTR_NAME: "FoxESS - Modbus",
            ATTR_ENTRY_TYPE: DeviceEntryType.SERVICE,
        }

        self._unique_id = f"foxess_modbus_{entity_description.name}"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._entity_description.name

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        value = self._controller.get_raw_value(self._entity_description.address)
        if value is not None and self._entity_description.post_process is not None:
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
    def unique_id(self) -> str:
        """Return the unique ID of the binary sensor."""
        return self._unique_id

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
