"""Select"""
import logging
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity
from homeassistant.components.select import SelectEntityDescription
from homeassistant.config_entries import ConfigEntry

from ..modbus_controller import ModbusController
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER: logging.Logger = logging.getLogger(__package__)


@dataclass(kw_only=True)
class ModbusSelectDescription(SelectEntityDescription):
    """Custom select entity description"""

    address: int | None = 0
    options_map: dict[int, str]


class ModbusSelect(ModbusEntityMixin, SelectEntity):
    """Select class"""

    def __init__(
        self,
        controller: ModbusController,
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
        return self.entity_description.options_map.get(value)

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
