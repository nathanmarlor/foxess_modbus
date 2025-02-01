"""This is only used for H1 on LAN, as it doesn't have a work mode"""

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.components.select import SelectEntityDescription
from homeassistant.const import Platform
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.entity_controller import RemoteControlMode
from ..common.types import Inv
from ..common.types import RegisterType
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .inverter_model_spec import EntitySpec
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER: logging.Logger = logging.getLogger(__package__)


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusRemoteControlSelectDescription(SelectEntityDescription, EntityFactory):  # type: ignore[misc]
    models: list[EntitySpec]

    @property
    def entity_type(self) -> type[Entity]:
        return SelectEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: Inv,
        register_type: RegisterType,
    ) -> Entity | None:
        if not self._supports_inverter_model(self.models, inverter_model, register_type):
            return None
        return ModbusRemoteControlSelect(controller, self)

    def serialize(self, _inverter_model: Inv) -> dict[str, Any] | None:
        return None


class ModbusRemoteControlSelect(ModbusEntityMixin, SelectEntity):
    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusRemoteControlSelectDescription,
    ) -> None:
        """Initialize the sensor."""

        self._controller = controller
        self.entity_description = entity_description
        self.entity_id = self._get_entity_id(Platform.SELECT)
        self._options_map = {
            RemoteControlMode.DISABLE: "Disable",
            RemoteControlMode.FORCE_CHARGE: "Force Charge",
            RemoteControlMode.FORCE_DISCHARGE: "Force Discharge",
        }
        self._attr_options = list(self._options_map.values())
        self._prev_option: RemoteControlMode | None = None

        assert self._controller.remote_control_manager is not None
        self._manager = self._controller.remote_control_manager

    @property
    def current_option(self) -> str | None:
        value = self._manager.mode

        selected = self._options_map.get(value)
        if selected is None:
            _LOGGER.warning(
                "Select option (%s) is not valid. Valid values: (%s)",
                value,
                self._options_map,
            )

        self._prev_option = value
        return selected

    async def async_select_option(self, option: str) -> None:
        value = next(
            (k for k, v in self._options_map.items() if v == option),
            None,
        )
        if value is None:
            _LOGGER.warning(
                "Failed to set unknown value '%s' Valid values: %s",
                option,
                list(self._options_map.values()),
            )
            return

        await self._manager.set_mode(value)
        self.schedule_update_ha_state()

    def update_callback(self, _changed_addresses: set[int]) -> None:
        if self._manager.mode != self._prev_option:
            self.schedule_update_ha_state()

    @property
    def addresses(self) -> list[int]:
        return []
