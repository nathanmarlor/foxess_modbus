"""Sensor"""

import logging
from collections import deque
from dataclasses import dataclass
from dataclasses import field
from datetime import date
from datetime import datetime
from decimal import Decimal
from typing import Any
from typing import Callable
from typing import cast

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import Platform
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import StateType

from ..common.entity_controller import EntityController
from ..common.types import Inv
from ..common.types import RegisterType
from ..const import ROUND_SENSOR_VALUES
from .base_validator import BaseValidator
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .inverter_model_spec import ModbusAddressesSpec
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusSensorDescription(SensorEntityDescription, EntityFactory):  # type: ignore[misc]
    """Custom sensor description"""

    addresses: list[ModbusAddressesSpec]
    scale: float | None = None
    round_to: float | None = None
    post_process: Callable[[float], float] | None = None
    validate: list[BaseValidator] = field(default_factory=list)
    signed: bool = True

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: Inv,
        register_type: RegisterType,
    ) -> Entity | None:
        addresses = self._addresses_for_inverter_model(self.addresses, inverter_model, register_type)
        round_to = self.round_to if controller.inverter_details.get(ROUND_SENSOR_VALUES, False) else None
        return ModbusSensor(controller, self, addresses, round_to) if addresses is not None else None

    def serialize(self, inverter_model: Inv, register_type: RegisterType) -> dict[str, Any] | None:
        addresses = self._addresses_for_inverter_model(self.addresses, inverter_model, register_type)
        if addresses is None:
            return None

        return {
            "type": "sensor",
            "key": self.key,
            "name": self.name,
            "addresses": addresses,
            "scale": self.scale,
            "signed": self.signed,
        }


class ModbusSensor(ModbusEntityMixin, SensorEntity):
    """Sensor class."""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusSensorDescription,
        # Array of registers which this value is split over, from lower-order bits to higher-order bits
        # (usually high address, low address)
        addresses: list[int],
        round_to: float | None,
    ) -> None:
        """Initialize the sensor."""

        self._controller = controller
        self.entity_description = entity_description
        self._addresses = addresses
        self._round_to = round_to
        self._moving_average_filter: deque[float] | None = deque(maxlen=6) if round_to is not None else None
        self.entity_id = self._get_entity_id(Platform.SENSOR)

    def _calculate_native_value(self) -> int | float | None:
        """Return the value reported by the sensor."""
        entity_description = cast(ModbusSensorDescription, self.entity_description)
        original = self._controller.read(self._addresses, signed=entity_description.signed)

        if original is None:
            return None

        value: float | int = original

        if entity_description.scale is not None:
            value = value * entity_description.scale
        if entity_description.post_process is not None:
            value = entity_description.post_process(float(value))
        if not self._validate(entity_description.validate, value, original):
            return None

        return value

    def _round_native_value(self, value: StateType | date | datetime | Decimal) -> Any:
        def nearest_multiple(value: float, round_to: float) -> float:
            return round_to * round(value / round_to)

        # The aim here is to reduce the amount of data send to HA's database:
        # - Filter out small amounts of noise
        # - Still respond quickly if the value changes by a large amount
        # - Avoid sitting close, but not quite on, the actual value for an extended period
        # - If the value ramps slowly from one point to another, break this into a series of larger steps
        #
        # To do this, we combine snapping rounding with a moving average filter.
        # With snapping rounding, we maintain a bit of hysteresis. If we round to the nearest 20, then we'll only
        # change value once we get more than 20 away from the previous value, whereupon we'll round to the nearest 20.
        # For example, if the previous value is 100, values from 80-120 will all round to 100. Once we get above 120,
        # we'll round to the nearest 20 (e.g. 120-129 will round to 120, 130-149 will round to 140).
        #
        # When we receive a new value, we add it to the moving average. If the output of the moving average is more than
        # round_to from the last value, we flush the filter and set the current value to the new value, rounded to
        # round_to. Flushing the filter means that we don't slowly ramp to a new value, which will create even more
        # data points: the opposite of what we're trying to achieve!

        if self._round_to is not None:
            assert self._moving_average_filter is not None
            assert self._moving_average_filter.maxlen is not None

            if value is None or not isinstance(value, float):
                self._moving_average_filter.clear()
            else:
                self._moving_average_filter.append(value)
                # If it's empty, fill it
                while len(self._moving_average_filter) < self._moving_average_filter.maxlen:
                    self._moving_average_filter.append(value)
                average_value = sum(self._moving_average_filter) / len(self._moving_average_filter)

                if self._attr_native_value is None or not isinstance(self._attr_native_value, float):
                    value = nearest_multiple(value, self._round_to)
                else:
                    if abs(self._attr_native_value - average_value) >= self._round_to:
                        value = nearest_multiple(value, self._round_to)
                        for _ in range(self._moving_average_filter.maxlen):
                            self._moving_average_filter.append(value)
                    else:
                        value = self._attr_native_value

        return value

    def update_callback(self, changed_addresses: set[int]) -> None:
        # If we're using rounding and a filter, we need to respond to every update, even if the register hasn't changed
        if self._round_to is None:
            super().update_callback(changed_addresses)
        else:
            self._address_updated()

    def _address_updated(self) -> None:
        new_value = self._round_native_value(self._calculate_native_value())
        if new_value != self._attr_native_value:
            self._attr_native_value = new_value
            super()._address_updated()

    @property
    def addresses(self) -> list[int]:
        return self._addresses
