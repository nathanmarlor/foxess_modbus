"""Select"""
import logging
from dataclasses import dataclass
from dataclasses import field
from typing import Any
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
    post_process: Callable[[float], float] | None = None
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
        inv_details: dict[str, Any],
    ) -> Entity | None:
        address = self._address_for_inverter_model(self.address, inverter_model, register_type)
        return ModbusNumber(controller, self, address, entry, inv_details) if address is not None else None


class ModbusNumber(ModbusEntityMixin, NumberEntity):
    """Number class"""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusNumberDescription,
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
        self.entity_id = "number." + self._get_unique_id()

    @property
    def native_value(self) -> int | float | None:
        """Return the value reported by the sensor."""
        entity_description = cast(ModbusNumberDescription, self.entity_description)
        value: float | int | None = self._controller.read(self._address)
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

    @property
    def mode(self) -> NumberMode:
        return cast(ModbusNumberDescription, self.entity_description).mode

    async def async_set_native_value(self, value: float) -> None:
        entity_description = cast(ModbusNumberDescription, self.entity_description)
        value = max(
            self.entity_description.native_min_value,
            min(self.entity_description.native_max_value, value),
        )

        if entity_description.scale is not None:
            value = value / entity_description.scale

        int_value = int(value)

        await self._controller.write_register(self._address, int_value)

    @property
    def addresses(self) -> list[int]:
        return [self._address]
