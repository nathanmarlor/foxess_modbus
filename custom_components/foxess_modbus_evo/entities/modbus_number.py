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
class ModbusNumberDescription(NumberEntityDescription, EntityFactory):  # type: ignore[misc]
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
        inverter_model: Inv,
        register_type: RegisterType,
    ) -> Entity | None:
        address = self._address_for_inverter_model(self.address, inverter_model, register_type)
        return ModbusNumber(controller, self, address) if address is not None else None

    def serialize(self, inverter_model: Inv, register_type: RegisterType) -> dict[str, Any] | None:
        addresses = self._addresses_for_inverter_model(self.address, inverter_model, register_type)
        if addresses is None:
            return None

        return {
            "type": "number",
            "key": self.key,
            "name": self.name,
            "addresses": addresses,
            "scale": self.scale,
        }


class ModbusNumber(ModbusEntityMixin, NumberEntity):
    """Number class"""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusNumberDescription,
        address: int,
    ) -> None:
        """Initialize the sensor."""

        self._controller = controller
        self.entity_description = entity_description
        self._address = address
        self.entity_id = self._get_entity_id(Platform.NUMBER)

    @property
    def native_value(self) -> int | float | None:
        """Return the value reported by the sensor."""
        entity_description = cast(ModbusNumberDescription, self.entity_description)
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

    @property
    def mode(self) -> NumberMode:
        return cast(ModbusNumberDescription, self.entity_description).mode

    async def async_set_native_value(self, value: float) -> None:
        entity_description = cast(ModbusNumberDescription, self.entity_description)
        if (
            self.entity_description.native_min_value is not None
            and self.entity_description.native_max_value is not None
        ):
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
