"""Binary Sensor"""

import logging
from dataclasses import dataclass
from dataclasses import field
from typing import Any
from typing import Callable
from typing import cast

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntityDescription
from homeassistant.const import Platform
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.types import Inv
from ..common.types import RegisterType
from .base_validator import BaseValidator
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .inverter_model_spec import InverterModelSpec
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusBinarySensorDescription(BinarySensorEntityDescription, EntityFactory):
    """Description for ModbusBinarySensor"""

    address: list[InverterModelSpec]
    validate: list[BaseValidator] = field(default_factory=list)
    icon_func: Callable[[bool | None], str | None] | None

    @property
    def entity_type(self) -> type[Entity]:
        return BinarySensorEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: Inv,
        register_type: RegisterType,
    ) -> Entity | None:
        address = self._address_for_inverter_model(self.address, inverter_model, register_type)
        return ModbusBinarySensor(controller, self, address) if address is not None else None

    def serialize(self, inverter_model: Inv) -> dict[str, Any]:
        return {}


class ModbusBinarySensor(ModbusEntityMixin, BinarySensorEntity):
    """Modbus binary sensor"""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusBinarySensorDescription,
        address: int,
    ) -> None:
        """Initialize the sensor."""

        self._controller = controller
        self.entity_description = entity_description
        self._address = address
        self.entity_id = self._get_entity_id(Platform.BINARY_SENSOR)

    @property
    def is_on(self) -> bool | None:
        """Return the value reported by the sensor."""
        value = self._controller.read(self._address, signed=False)
        if value is None:
            return value
        rules = cast(ModbusBinarySensorDescription, self.entity_description).validate
        if not self._validate(rules, value):
            return None
        return value > 0

    @property
    def icon(self) -> str | None:
        entity_description = cast(ModbusBinarySensorDescription, self.entity_description)
        if entity_description.icon_func is not None:
            return entity_description.icon_func(self.is_on)
        return super().icon

    @property
    def addresses(self) -> list[int]:
        return [self._address]
