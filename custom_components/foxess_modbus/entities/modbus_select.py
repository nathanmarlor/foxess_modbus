"""Select"""
import logging
from dataclasses import dataclass
from dataclasses import field

from custom_components.foxess_modbus.entities.validation import BaseValidator
from homeassistant.components.select import SelectEntity
from homeassistant.components.select import SelectEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from .entity_factory import EntityFactory
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER: logging.Logger = logging.getLogger(__package__)


@dataclass(kw_only=True)
class ModbusSelectDescription(SelectEntityDescription, EntityFactory):
    """Custom select entity description"""

    address: int
    options_map: dict[int, str]
    validate: list[BaseValidator] = field(default_factory=list)

    @property
    def entity_type(self) -> type[Entity]:
        return SelectEntity

    @property
    def addresses(self) -> list[int]:
        return [self.address]

    def create_entity(
        self, controller: EntityController, entry: ConfigEntry, inv_details
    ) -> Entity:
        return ModbusSelect(controller, self, entry, inv_details)


class ModbusSelect(ModbusEntityMixin, SelectEntity):
    """Select class"""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusSelectDescription,
        entry: ConfigEntry,
        inv_details,
    ) -> None:
        """Initialize the sensor."""

        self._controller = controller
        self.entity_description = entity_description
        self._entry = entry
        self._inv_details = inv_details
        self.entity_id = "select." + self._get_unique_id()
        self._attr_options = list(self.entity_description.options_map.values())

    @property
    def current_option(self) -> str | None:
        value = self._controller.read(self.entity_description.address)
        if value is None:
            return None
        if not self._validate(self.entity_description.validate, value):
            return None

        selected = self.entity_description.options_map.get(value)
        if selected is None:
            _LOGGER.warning(
                "Select option (%s) for address (%s) is not valid. Valid values: (%s)",
                value,
                self.entity_description.address,
                self.entity_description.options_map,
            )
        return selected

    async def async_select_option(self, option: str) -> None:
        value = next(
            (k for k, v in self.entity_description.options_map.items() if v == option),
            None,
        )
        if value is None:
            _LOGGER.warning(
                "Failed to write unknown value '%s' to register '%s' with address %s. Valid values: %s",
                option,
                self.name,
                self.entity_description.address,
                self.options,
            )
            return

        await self._controller.write_register(self.entity_description.address, value)

    @property
    def should_poll(self) -> bool:
        return False
