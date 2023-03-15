"""Select"""
import logging
from dataclasses import dataclass
from typing import Callable

from homeassistant.components.number import NumberEntity
from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.number import NumberMode
from homeassistant.config_entries import ConfigEntry

from ..modbus_controller import ModbusController
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER: logging.Logger = logging.getLogger(__package__)


@dataclass(kw_only=True)
class ModbusNumberDescription(NumberEntityDescription):
    """Custom number entity description"""

    address: int | None = 0
    mode: NumberMode = NumberMode.AUTO
    scale: float | None = None
    post_process: Callable[[int], int] | None = None


class ModbusNumber(ModbusEntityMixin, NumberEntity):
    """Number class"""

    def __init__(
        self,
        controller: ModbusController,
        entity_description: ModbusNumberDescription,
        entry: ConfigEntry,
        inv_details,
    ) -> None:
        """Initialize the sensor."""

        self._controller = controller
        self.entity_description = entity_description
        self._entry = entry
        self._inv_details = inv_details
        self.entity_id = "number." + self._get_unique_id()

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        value = self._controller.read(self.entity_description.address)
        if value is not None:
            if self.entity_description.scale is not None:
                value = value * self.entity_description.scale
            if self.entity_description.post_process is not None:
                return self.entity_description.post_process(value)

        return value

    @property
    def mode(self) -> NumberMode:
        return self.entity_description.mode

    async def async_set_native_value(self, value: float) -> None:
        int_value = int(
            max(
                self.entity_description.native_min_value,
                min(self.entity_description.native_max_value, value),
            )
        )

        await self._controller.write_register(
            self.entity_description.address, int_value
        )
        self.update_callback()

    @property
    def should_poll(self) -> bool:
        return False
