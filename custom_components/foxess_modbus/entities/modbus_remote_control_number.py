"""Select"""
import logging
from dataclasses import dataclass
from typing import Any
from typing import Callable
from typing import cast

from homeassistant.components.number import NumberEntity
from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.number import NumberMode
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.restore_state import ExtraStoredData
from homeassistant.helpers.restore_state import RestoredExtraData
from homeassistant.helpers.restore_state import RestoreEntity

from ..common.entity_controller import EntityController
from ..common.entity_controller import EntityRemoteControlManager
from ..common.register_type import RegisterType
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .inverter_model_spec import EntitySpec
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER: logging.Logger = logging.getLogger(__package__)


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusRemoteControlNumberDescription(NumberEntityDescription, EntityFactory):
    """Custom number entity description"""

    models: list[EntitySpec]
    mode: NumberMode = NumberMode.AUTO
    setter: Callable[[EntityRemoteControlManager, int], None]

    @property
    def entity_type(self) -> type[Entity]:
        return NumberEntity

    def create_entity_if_supported(
        self,
        _hass: HomeAssistant,
        controller: EntityController,
        inverter_model: str,
        register_type: RegisterType,
        entry: ConfigEntry,
        inv_details: dict[str, Any],
    ) -> Entity | None:
        if not self._supports_inverter_model(self.models, inverter_model, register_type):
            return None
        return ModbusRemoteControlNumber(controller, self, entry, inv_details)


class ModbusRemoteControlNumber(ModbusEntityMixin, RestoreEntity, NumberEntity):
    """Number class"""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusRemoteControlNumberDescription,
        entry: ConfigEntry,
        inv_details: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""

        self._controller = controller
        self.entity_description = entity_description
        self._entry = entry
        self._inv_details = inv_details
        self.entity_id = self._get_entity_id(Platform.NUMBER)

    @property
    def native_value(self) -> int | float | None:
        """Return the value reported by the sensor."""
        entity_description = cast(ModbusRemoteControlNumberDescription, self.entity_description)
        value: float | int | None = self._controller.read(self._address, signed=False)
        original = value
        if value is None:
            return None
        if entity_description.scale is not None:
            value = value * entity_description.scale
        if entity_description.post_process is not None:
            value = entity_description.post_process(float(value))
        if not self._validate(entity_description.validate, value, original):
            return None

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
        return RestoredExtraData(json_dict={"last_enabled_value": self._last_enabled_value})

    @property
    def mode(self) -> NumberMode:
        return cast(ModbusRemoteControlNumberDescription, self.entity_description).mode

    async def async_set_native_value(self, value: float) -> None:
        entity_description = cast(ModbusRemoteControlNumberDescription, self.entity_description)
        value = max(
            self.entity_description.native_min_value,
            min(self.entity_description.native_max_value, value),
        )

        if entity_description.scale is not None:
            value = value / entity_description.scale

        int_value = int(round(value))

        await self._controller.write_register(self._address, int_value)

    @property
    def addresses(self) -> list[int]:
        return [self._address]
