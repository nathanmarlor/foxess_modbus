from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.entity_controller import RemoteControlMode
from ..common.register_type import RegisterType
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .modbus_select import ModbusSelect
from .modbus_select import ModbusSelectDescription

_FORCE_CHARGE = "Force Charge"
_FORCE_DISCHARGE = "Force Discharge"


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusWorkModeSelectDescription(ModbusSelectDescription):
    def create_entity_if_supported(
        self,
        _hass: HomeAssistant,
        controller: EntityController,
        inverter_model: str,
        register_type: RegisterType,
        entry: ConfigEntry,
        inv_details: dict[str, Any],
    ) -> Entity | None:
        address = self._address_for_inverter_model(self.address, inverter_model, register_type)
        return ModbusWorkModeSelect(controller, self, address, entry, inv_details) if address is not None else None


class ModbusWorkModeSelect(ModbusSelect):
    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusSelectDescription,
        address: int,
        entry: ConfigEntry,
        inv_details: dict[str, Any],
    ) -> None:
        super().__init__(controller, entity_description, address, entry, inv_details)

        if controller.remote_control_manager is not None:
            self._attr_options.extend([_FORCE_CHARGE, _FORCE_DISCHARGE])

    @property
    def current_option(self) -> str | None:
        if self._controller.remote_control_manager is not None:
            mode = self._controller.remote_control_manager.mode
            if mode == RemoteControlMode.FORCE_CHARGE:
                return _FORCE_CHARGE
            if mode == RemoteControlMode.FORCE_DISCHARGE:
                return _FORCE_DISCHARGE
        return super().current_option

    async def async_select_option(self, option: str) -> None:
        if option == _FORCE_CHARGE:
            assert self._controller.remote_control_manager is not None
            await self._controller.remote_control_manager.set_mode(RemoteControlMode.FORCE_CHARGE)
        if option == _FORCE_DISCHARGE:
            assert self._controller.remote_control_manager is not None
            await self._controller.remote_control_manager.set_mode(RemoteControlMode.FORCE_DISCHARGE)
        else:
            if self._controller.remote_control_manager is not None:
                await self._controller.remote_control_manager.set_mode(RemoteControlMode.DISABLE)
            await super().async_select_option(option)
