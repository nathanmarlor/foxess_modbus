"""Time period sensors"""
import logging
from dataclasses import dataclass
from dataclasses import field
from datetime import time
from typing import Any
from typing import cast

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
from ..common.register_type import RegisterType
from .base_validator import BaseValidator
from .entity_factory import EntityFactory
from .inverter_model_spec import InverterModelSpec
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER = logging.getLogger(__name__)


def is_time_value_valid(value: int) -> bool:
    """Determines whether the given time period start/end register holds a valid value"""
    hours, minutes = ((value & 0xFF00) >> 8, value & 0xFF)
    return 0 <= hours <= 23 and 0 <= minutes <= 59


def parse_time_value(value: int) -> time:
    """Parses a time period start/end register to a time"""
    hours, minutes = ((value & 0xFF00) >> 8, value & 0xFF)
    return time(hour=hours, minute=minutes)


def serialize_time_to_value(time_value: time) -> int:
    """Serializez a time to a time period start/end register"""
    return (time_value.hour << 8) | time_value.minute


def _is_force_charge_enabled(
    start_or_end_1: int,
    start_or_end_2: int,
) -> bool:
    return start_or_end_1 > 0 or start_or_end_2 > 0


@dataclass(kw_only=True)
class ModbusChargePeriodStartEndSensorDescription(SensorEntityDescription, EntityFactory):
    """Entity description for ModbusChargePeriodStartEndSensor"""

    address: list[InverterModelSpec]
    # Address of period end if this is the start, and vice versa
    other_address: list[InverterModelSpec]
    validate: list[BaseValidator] = field(default_factory=list)

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: str,
        register_type: RegisterType,
        entry: ConfigEntry,
        inv_details: dict[str, Any],
    ) -> Entity | None:
        address = self._address_for_inverter_model(self.address, inverter_model, register_type)
        other_address = self._address_for_inverter_model(self.other_address, inverter_model, register_type)

        if address is None:
            assert (
                other_address is None
            ), f"{self}: address is None but other_address is {other_address} for ({inverter_model}, {register_type})"
            return None

        assert (
            other_address is not None
        ), f"{self}: address is {address} but other_address is None for ({inverter_model}, {register_type})"
        return ModbusChargePeriodStartEndSensor(controller, self, address, other_address, entry, inv_details)


class ModbusChargePeriodStartEndSensor(ModbusEntityMixin, RestoreEntity, SensorEntity):
    """Sensor used for the start/end of a charge time period"""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusChargePeriodStartEndSensorDescription,
        address: int,
        other_address: int,
        entry: ConfigEntry,
        inv_details: dict[str, Any],
    ) -> None:
        self._controller = controller
        self.entity_description = entity_description
        self._address = address
        self._other_address = other_address
        self._entry = entry
        self._inv_details = inv_details
        self.entity_id = "sensor." + self._get_unique_id()
        # The last value this sensor had when force-charge was enabled
        self._last_enabled_value: int | None = None

    @property
    def native_value(self) -> time | None:
        """Return the value reported by the sensor."""
        value = self._controller.read(self._address)

        if value is None:
            return None

        rules = cast(ModbusChargePeriodStartEndSensorDescription, self.entity_description).validate
        if not self._validate(rules, value):
            return None

        other_value = self._controller.read(self._other_address)
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

        parsed_value = parse_time_value(value)

        return parsed_value

    async def async_added_to_hass(self) -> None:
        """Add update callback after being added to hass."""
        await super().async_added_to_hass()
        extra_data = await self.async_get_last_extra_data()
        if extra_data:
            self._last_enabled_value = extra_data.json_dict.get("last_enabled_value")

    @property
    def extra_restore_state_data(self) -> ExtraStoredData:
        """Return specific state data to be restored."""
        return RestoredExtraData(json_dict={"last_enabled_value": self._last_enabled_value})

    def _address_updated(self) -> None:
        # If we've got a value of 0, and the other end of the period changes from
        # 0 to a non-zero value, that means that someone has enabled a force-charge window
        # with a start time of midnight, so we need to update ourselves.
        # Therefore, we need to be sensitive to other_address
        value = self._controller.read(self._address)
        if value is not None:
            other_value = self._controller.read(self._other_address)
            rules = cast(ModbusChargePeriodStartEndSensorDescription, self.entity_description).validate
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
    def addresses(self) -> list[int]:
        return [self._address, self._other_address]


@dataclass(kw_only=True)
class ModbusEnableForceChargeSensorDescription(BinarySensorEntityDescription, EntityFactory):
    """Entity description for ModbusEnableForceChargeSensor"""

    period_start_address: list[InverterModelSpec]
    period_end_address: list[InverterModelSpec]
    validate: list[BaseValidator] = field(default_factory=list)

    @property
    def entity_type(self) -> type[Entity]:
        return BinarySensorEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: str,
        register_type: RegisterType,
        entry: ConfigEntry,
        inv_details: dict[str, Any],
    ) -> Entity | None:
        period_start_address = self._address_for_inverter_model(
            self.period_start_address, inverter_model, register_type
        )
        period_end_address = self._address_for_inverter_model(self.period_end_address, inverter_model, register_type)
        if period_start_address is None:
            assert period_end_address is None, (
                f"{self}: period_start_address is None but period_end_address is {period_end_address} for "
                f"({inverter_model}, {register_type})"
            )
            return None

        assert period_end_address is not None, (
            f"{self}: period_start_address is {period_start_address} but period_end_address is None for "
            f"({inverter_model}, {register_type})"
        )
        return ModbusEnableForceChargeSensor(
            controller,
            self,
            period_start_address,
            period_end_address,
            entry,
            inv_details,
        )


class ModbusEnableForceChargeSensor(ModbusEntityMixin, BinarySensorEntity):
    """Sensor which synthesises an "enable force charge" state, based on the start/end time registers"""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusEnableForceChargeSensorDescription,
        period_start_address: int,
        period_end_address: int,
        entry: ConfigEntry,
        inv_details: dict[str, Any],
    ) -> None:
        self._controller = controller
        self.entity_description = entity_description
        self._period_start_address = period_start_address
        self._period_end_address = period_end_address
        self._entry = entry
        self._inv_details = inv_details
        self.entity_id = "binary_sensor." + self._get_unique_id()
        self._attr_device_class = BinarySensorDeviceClass.POWER

    @property
    def is_on(self) -> bool | None:
        start_time = self._controller.read(self._period_start_address)
        end_time = self._controller.read(self._period_end_address)
        rules = cast(ModbusEnableForceChargeSensorDescription, self.entity_description).validate

        if (
            start_time is None
            or not self._validate(
                rules,
                start_time,
                address_override=self._period_start_address,
            )
            or end_time is None
            or not self._validate(
                rules,
                end_time,
                address_override=self._period_end_address,
            )
        ):
            return None

        return _is_force_charge_enabled(start_time, end_time)

    @property
    def icon(self) -> str | None:
        return "mdi:battery-lock" if self.is_on else "mdi:battery-lock-open"

    @property
    def addresses(self) -> list[int]:
        return [self._period_start_address, self._period_end_address]
