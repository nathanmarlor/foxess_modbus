"""Sensor"""
import logging
from dataclasses import dataclass
from datetime import time

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.restore_state import ExtraStoredData
from homeassistant.helpers.restore_state import RestoredExtraData
from homeassistant.helpers.restore_state import RestoreEntity

from ..common.entity_controller import EntityController
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class ModbusTimePeriodStartEndSensorDescription(SensorEntityDescription):
    """Entity description for ModbusTimePeriodStartEndSensor"""

    address: int
    other_address: int  # Address of period end if this is the start, and vice versa


class ModbusTimePeriodStartEndSensor(ModbusEntityMixin, RestoreEntity, SensorEntity):
    """Sensor used for the start/end of a charge time period"""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusTimePeriodStartEndSensorDescription,
        entry: ConfigEntry,
        inv_details,
    ) -> None:
        self._controller = controller
        self.entity_description = entity_description
        self._entry = entry
        self._inv_details = inv_details
        self.entity_id = "sensor." + self._get_unique_id()
        self._last_non_zero_value: int | None = None

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        value = self._controller.read(self.entity_description.address)
        if value is not None:
            # If the charge window is disabled (i.e. both start and end are 0),
            # return the last-stored value rather than midnight
            if value == 0 and self._last_non_zero_value is not None:
                other_value = self._controller.read(
                    self.entity_description.other_address
                )
                if other_value == 0:
                    value = self._last_non_zero_value

            value = time(hour=(value & 0xFF00) >> 8, minute=value & 0xFF)

        return value

    async def async_added_to_hass(self) -> None:
        """Add update callback after being added to hass."""
        await super().async_added_to_hass()
        extra_data = await self.async_get_last_extra_data()
        if extra_data:
            self._last_non_zero_value = extra_data.json_dict.get("last_non_zero_value")

    @property
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Return specific state data to be restored."""
        return RestoredExtraData(
            json_dict={"last_non_zero_value": self._last_non_zero_value}
        )

    def update_callback(self, changed_addresses: set[int]) -> None:
        """Schedule a state update."""
        if self.entity_description.address in changed_addresses:
            value = self._controller.read(self.entity_description.address)
            if value is not None and value > 0:
                self._last_non_zero_value = value

            self.schedule_update_ha_state(True)

    @property
    def should_poll(self) -> bool:
        return False


@dataclass(kw_only=True)
class ModbusEnableForceChargeSensorDescription(BinarySensorEntityDescription):
    """Entity description for ModbusEnableForceChargeSensor"""

    period_start_address: int
    period_end_address: int


class ModbusEnableForceChargeSensor(ModbusEntityMixin, BinarySensorEntity):
    """Sensor which synthesises an "enable force charge" state, based on the start/end time registers"""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusEnableForceChargeSensorDescription,
        entry: ConfigEntry,
        inv_details,
    ) -> None:
        self._controller = controller
        self.entity_description = entity_description
        self._entry = entry
        self._inv_details = inv_details
        self.entity_id = "binary_sensor." + self._get_unique_id()
        self._attr_device_class = BinarySensorDeviceClass.BATTERY_CHARGING

    @property
    def is_on(self) -> bool | None:
        start_time = self._controller.read(self.entity_description.period_start_address)
        end_time = self._controller.read(self.entity_description.period_end_address)

        if start_time is None or end_time is None:
            return None

        # It's valid to have a window which starts at midnight
        return start_time > 0 or end_time > 0

    @property
    def should_poll(self) -> bool:
        return False

    def update_callback(self, changed_addresses: set[int]) -> None:
        """Schedule a state update."""
        if (self.entity_description.period_start_address in changed_addresses) or (
            self.entity_description.period_end_address in changed_addresses
        ):
            self.schedule_update_ha_state(True)
