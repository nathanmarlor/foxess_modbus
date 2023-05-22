"""Select"""
import logging
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import cast

from homeassistant.components.select import SelectEntity
from homeassistant.components.select import SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.register_type import RegisterType
from .base_validator import BaseValidator
from .entity_factory import EntityFactory
from .inverter_model_spec import ModbusAddressSpec
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER: logging.Logger = logging.getLogger(__package__)


@dataclass(kw_only=True)
class ModbusSelectDescription(SelectEntityDescription, EntityFactory):
    """Custom select entity description"""

    address: list[ModbusAddressSpec]
    options_map: dict[int, str]
    validate: list[BaseValidator] = field(default_factory=list)

    @property
    def entity_type(self) -> type[Entity]:
        return SelectEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: str,
        register_type: RegisterType,
        entry: ConfigEntry,
        inv_details: dict[str, Any],
    ) -> Entity | None:
        address = self._address_for_inverter_model(self.address, inverter_model, register_type)
        return ModbusSelect(controller, self, address, entry, inv_details) if address is not None else None


class ModbusSelect(ModbusEntityMixin, SelectEntity):
    """Select class"""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusSelectDescription,
        address: int,
        entry: ConfigEntry,
        inv_details: dict[str, Any],
    ) -> None:
        """Initialize the sensor."""

        self._controller = controller
        self.entity_description = entity_description
        self._address = address
        self._entry = entry
        self._inv_details = inv_details
        self.entity_id = "select." + self._get_unique_id()
        self._attr_options = list(self.entity_description.options_map.values())

    @property
    def current_option(self) -> str | None:
        entity_description = cast(ModbusSelectDescription, self.entity_description)
        value = self._controller.read(self._address)
        if value is None:
            return None
        if not self._validate(entity_description.validate, value):
            return None

        selected = entity_description.options_map.get(value)
        if selected is None:
            _LOGGER.warning(
                "Select option (%s) for address (%s) is not valid. Valid values: (%s)",
                value,
                self._address,
                entity_description.options_map,
            )
        return selected

    async def async_select_option(self, option: str) -> None:
        entity_description = cast(ModbusSelectDescription, self.entity_description)
        value = next(
            (k for k, v in entity_description.options_map.items() if v == option),
            None,
        )
        if value is None:
            _LOGGER.warning(
                "Failed to write unknown value '%s' to register '%s' with address %s. Valid values: %s",
                option,
                self.name,
                self._address,
                self.options,
            )
            return

        await self._controller.write_register(self._address, value)

    @property
    def addresses(self) -> list[int]:
        return [self._address]
