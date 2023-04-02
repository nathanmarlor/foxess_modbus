"""Time period sensors"""
import logging
from dataclasses import dataclass
from dataclasses import field
from datetime import time

from custom_components.foxess_modbus.entities.validation import BaseValidator
from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import ExtraStoredData
from homeassistant.helpers.restore_state import RestoredExtraData
from homeassistant.helpers.restore_state import RestoreEntity

from ..common.entity_controller import EntityController
from .entity_factory import EntityFactory
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER = logging.getLogger(__name__)


def _parse_time(value: int) -> tuple[int, int]:
    return ((value & 0xFF00) >> 8, value & 0xFF)


def _is_force_charge_enabled(
    start_or_end_1: int,
    start_or_end_2: int,
) -> bool:
    return start_or_end_1 > 0 or start_or_end_2 > 0


@dataclass(kw_only=True)
class ModbusChargePeriodStartEndSensorDescription(
    SensorEntityDescription, EntityFactory
):
    """Entity description for ModbusChargePeriodStartEndSensor"""

    address: int
    other_address: int  # Address of period end if this is the start, and vice versa
    validate: list[BaseValidator] = field(default_factory=list)

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

    @property
    def addresses(self) -> list[int]:
        return [self.address, self.other_address]

    def create_entity(
        self, controller: EntityController, entry: ConfigEntry, inv_details
    ) -> Entity:
        return ModbusChargePeriodStartEndSensor(controller, self, entry, inv_details)


class ModbusChargePeriodStartEndSensor(ModbusEntityMixin, RestoreEntity, SensorEntity):
    """Sensor used for the start/end of a charge time period"""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusChargePeriodStartEndSensorDescription,
        entry: ConfigEntry,
        inv_details,
    ) -> None:
        self._controller = controller
        self.entity_description = entity_description
        self._entry = entry
        self._inv_details = inv_details
        self.entity_id = "sensor." + self._get_unique_id()
        # The last value this sensor had when force-charge was enabled
        self._last_enabled_value: int | None = None

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        value = self._controller.read(self.entity_description.address)

        if value is None:
            return None

        rules = self.entity_description.validate
        if not self._validate(rules, value):
            return None

        other_value = self._controller.read(self.entity_description.other_address)
        # If the charge window is disabled (i.e. both start and end are 0),
        # return the last-stored value rather than midnight. If other_value is unavailable,
        # assume the charge window is enabled, so we'll only fall back to _last_enabled_value
        # if we're certain that force-charging is disabled
        if (
            self._last_enabled_value is not None
            and other_value is not None
            and self._validate(rules, other_value)
            and not _is_force_charge_enabled(value, other_value)
        ):
            value = self._last_enabled_value
        hours, minutes = _parse_time(value)
        value = time(hour=hours, minute=minutes)

        return value

    async def async_added_to_hass(self) -> None:
        """Add update callback after being added to hass."""
        await super().async_added_to_hass()
        extra_data = await self.async_get_last_extra_data()
        if extra_data:
            self._last_enabled_value = extra_data.json_dict.get("last_enabled_value")

    @property
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Return specific state data to be restored."""
        return RestoredExtraData(
            json_dict={"last_enabled_value": self._last_enabled_value}
        )

    def _address_updated(self) -> None:
        # If we've got a value of 0, and the other end of the period changes from
        # 0 to a non-zero value, that means that someone has enabled a force-charge window
        # with a start time of midnight, so we need to update ourselves.
        # Therefore, we need to be sensitive to other_address
        value = self._controller.read(self.entity_description.address)
        if value is not None:
            other_value = self._controller.read(self.entity_description.other_address)
            rules = self.entity_description.validate
            if (
                self._validate(rules, value)
                and other_value is not None
                and self._validate(rules, other_value)
                and _is_force_charge_enabled(value, other_value)
            ):
                self._last_enabled_value = value

        # I'm not sure whether there are any cases where our exposed state will changed
        # if other_address changes, but this won't change often, so be safe.
        super()._address_updated()

    @property
    def should_poll(self) -> bool:
        return False


@dataclass(kw_only=True)
class ModbusEnableForceChargeSensorDescription(
    BinarySensorEntityDescription, EntityFactory
):
    """Entity description for ModbusEnableForceChargeSensor"""

    period_start_address: int
    period_end_address: int
    validate: list[BaseValidator] = field(default_factory=list)

    @property
    def entity_type(self) -> type[Entity]:
        return BinarySensorEntity

    @property
    def addresses(self) -> list[int]:
        return [self.period_start_address, self.period_end_address]

    def create_entity(
        self, controller: EntityController, entry: ConfigEntry, inv_details
    ) -> Entity:
        return ModbusEnableForceChargeSensor(controller, self, entry, inv_details)


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
        rules = self.entity_description.validate

        if (
            start_time is None
            or not self._validate(rules, start_time)
            or end_time is None
            or not self._validate(rules, end_time)
        ):
            return None

        return _is_force_charge_enabled(start_time, end_time)

    @property
    def should_poll(self) -> bool:
        return False
