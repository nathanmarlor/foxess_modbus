"""Select"""
import logging
from dataclasses import dataclass
from dataclasses import field
from typing import Callable
from typing import cast

from homeassistant.components.number import NumberEntity
from homeassistant.components.number import NumberEntityDescription
from homeassistant.components.number import NumberMode
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
class ModbusNumberDescription(NumberEntityDescription, EntityFactory):
    """Custom number entity description"""

    address: list[ModbusAddressSpec]
    mode: NumberMode = NumberMode.AUTO
    scale: float | None = None
    post_process: Callable[[int], int] | None = None
    validate: list[BaseValidator] = field(default_factory=list)

    @property
    def entity_type(self) -> type[Entity]:
        return NumberEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: str,
        register_type: RegisterType,
        entry: ConfigEntry,
        inv_details,
    ) -> Entity | None:
        address = self._address_for_inverter_model(
            self.address, inverter_model, register_type
        )
        return (
            ModbusNumber(controller, self, address, entry, inv_details)
            if address is not None
            else None
        )


class ModbusNumber(ModbusEntityMixin, NumberEntity):
    """Number class"""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusNumberDescription,
        address: int,
        entry: ConfigEntry,
        inv_details,
    ) -> None:
        """Initialize the sensor."""

        self._controller = controller
        self.entity_description = entity_description
        self._address = address
        self._entry = entry
        self._inv_details = inv_details
        self.entity_id = "number." + self._get_unique_id()

    @property
    def native_value(self):
        """Return the value reported by the sensor."""
        value = original = self._controller.read(self._address)
        if value is None:
            return None
        if self.entity_description.scale is not None:
            value = value * self.entity_description.scale
        if self.entity_description.post_process is not None:
            value = self.entity_description.post_process(value)
        if not self._validate(self.entity_description.validate, value, original):
            return None

        return value

    @property
    def mode(self) -> NumberMode:
        return cast(ModbusNumberDescription, self.entity_description).mode

    async def async_set_native_value(self, value: float) -> None:
        int_value = int(
            max(
                self.entity_description.native_min_value,
                min(self.entity_description.native_max_value, value),
            )
        )

        await self._controller.write_register(self._address, int_value)

    @property
    def addresses(self) -> list[int]:
        return [self._address]
