"""Select"""

import logging
from dataclasses import dataclass
from typing import Callable
from typing import cast

from homeassistant.components.number import NumberEntity
from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.number import NumberMode
from homeassistant.components.number import RestoreNumber
from homeassistant.const import Platform
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.entity_controller import EntityRemoteControlManager
from ..common.types import Inv
from ..common.types import RegisterType
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .inverter_model_spec import EntitySpec
from .inverter_model_spec import InverterModelSpec
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER: logging.Logger = logging.getLogger(__package__)


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusRemoteControlNumberDescription(NumberEntityDescription, EntityFactory):
    """Custom number entity description"""

    models: list[EntitySpec]
    max_value_address: list[InverterModelSpec] | None
    fallback_native_max_value: Callable[[EntityController], int]
    """Used if the max_value_address isn't available for an inverter"""
    mode: NumberMode = NumberMode.AUTO
    scale: float = 1.0
    signed: bool = False
    value_setter: Callable[[EntityRemoteControlManager, int], None]

    @property
    def entity_type(self) -> type[Entity]:
        return NumberEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: Inv,
        register_type: RegisterType,
    ) -> Entity | None:
        if not self._supports_inverter_model(self.models, inverter_model, register_type):
            return None
        max_value_address = (
            self._address_for_inverter_model(self.max_value_address, inverter_model, register_type)
            if self.max_value_address is not None
            else None
        )
        return ModbusRemoteControlNumber(controller, self, max_value_address)


class ModbusRemoteControlNumber(ModbusEntityMixin, RestoreNumber, NumberEntity):
    """Number class"""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusRemoteControlNumberDescription,
        max_value_address: int | None,
    ) -> None:
        """Initialize the sensor."""

        # This defaults to 100 before we manage to read from the inverter, which isn't particularly helpful
        self._attr_native_max_value = float("inf")
        self._controller = controller
        self.entity_description = entity_description
        self._max_value_address = max_value_address
        self.entity_id = self._get_entity_id(Platform.NUMBER)

        assert controller.remote_control_manager is not None
        self._manager = controller.remote_control_manager

    async def async_added_to_hass(self) -> None:
        """Add update callback after being added to hass."""
        await super().async_added_to_hass()

        extra_data = await self.async_get_last_number_data()
        # Sometimes we can have extra_data set, but incomplete
        if extra_data and extra_data.native_value is not None:
            if extra_data.native_max_value is not None:
                self._attr_native_max_value = extra_data.native_max_value
            self._update_native_value(extra_data.native_value)
        else:
            self._attr_native_value = None

        # This might overwrite the max value we set above
        self._address_updated()
        self.schedule_update_ha_state()

    @property
    def mode(self) -> NumberMode:
        return cast(ModbusRemoteControlNumberDescription, self.entity_description).mode

    async def async_set_native_value(self, value: float) -> None:
        self._update_native_value(value)

    def _address_updated(self) -> None:
        entity_description = cast(ModbusRemoteControlNumberDescription, self.entity_description)
        max_value = (
            self._controller.read(self._max_value_address, signed=entity_description.signed)
            if self._max_value_address is not None
            else entity_description.fallback_native_max_value(self._controller)
        )
        if max_value is not None:
            native_max_value = max_value * entity_description.scale
            self._attr_native_max_value = native_max_value
            if self._attr_native_value is None or self._attr_native_value > native_max_value:
                self._update_native_value(native_max_value)

    def _update_native_value(self, native_value: float) -> None:
        entity_description = cast(ModbusRemoteControlNumberDescription, self.entity_description)

        native_value = max(
            self.native_min_value,
            min(self.native_max_value, native_value),
        )

        self._attr_native_value = native_value

        scaled = int(native_value / entity_description.scale)
        entity_description.value_setter(self._manager, scaled)

        self.schedule_update_ha_state()

    @property
    def addresses(self) -> list[int]:
        return [self._max_value_address] if self._max_value_address is not None else []
