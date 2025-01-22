"""Select"""

import logging
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import cast

from homeassistant.components.select import SelectEntity
from homeassistant.components.select import SelectEntityDescription
from homeassistant.const import Platform
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.types import Inv
from ..common.types import RegisterType
from .base_validator import BaseValidator
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .inverter_model_spec import ModbusAddressSpec
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER: logging.Logger = logging.getLogger(__package__)


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusSelectDescription(SelectEntityDescription, EntityFactory):  # type: ignore[misc]
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
        inverter_model: Inv,
        register_type: RegisterType,
    ) -> Entity | None:
        address = self._address_for_inverter_model(self.address, inverter_model, register_type)
        return ModbusSelect(controller, self, address) if address is not None else None

    def serialize(self, inverter_model: Inv) -> dict[str, Any] | None:
        address_map = self._addresses_for_serialization(self.address, inverter_model)
        if address_map is None:
            return None

        return {
            "type": "select",
            "key": self.key,
            "name": self.name,
            "addresses": address_map,
            "values": self.options_map,
        }


class ModbusSelect(ModbusEntityMixin, SelectEntity):
    """Select class"""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusSelectDescription,
        address: int,
    ) -> None:
        """Initialize the sensor."""

        self._controller = controller
        self.entity_description = entity_description
        self._address = address
        self.entity_id = self._get_entity_id(Platform.SELECT)
        self._attr_options = list(self.entity_description.options_map.values())

    @property
    def current_option(self) -> str | None:
        entity_description = cast(ModbusSelectDescription, self.entity_description)
        value = self._controller.read(self._address, signed=False)
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
                list(entity_description.options_map.values()),
            )
            return

        await self._controller.write_register(self._address, value)

    @property
    def addresses(self) -> list[int]:
        return [self._address]
