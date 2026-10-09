"""Read-only register enums, independent of writable select entities."""

from dataclasses import dataclass
from typing import Any
from typing import cast

from homeassistant.components.sensor import SensorDeviceClass
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import Platform
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.types import Inv
from ..common.types import RegisterType
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .inverter_model_spec import ModbusAddressSpec
from .modbus_entity_mixin import ModbusEntityMixin


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusEnumSensorDescription(SensorEntityDescription, EntityFactory):  # type: ignore[misc]
    """An enum with only verified register values in its option map."""

    address: list[ModbusAddressSpec]
    options_map: dict[int, str]

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

    def create_entity_if_supported(
        self, controller: EntityController, inverter_model: Inv, register_type: RegisterType
    ) -> Entity | None:
        address = self._address_for_inverter_model(self.address, inverter_model, register_type)
        return ModbusEnumSensor(controller, self, address) if address is not None else None

    def serialize(self, inverter_model: Inv, register_type: RegisterType) -> dict[str, Any] | None:
        address = self._address_for_inverter_model(self.address, inverter_model, register_type)
        if address is None:
            return None
        return {
            "type": "enum-sensor",
            "key": self.key,
            "name": self.name,
            "addresses": [address],
            "options_map": dict(self.options_map),
        }


class ModbusEnumSensor(ModbusEntityMixin, SensorEntity):
    """Expose unknown codes as unknown state, retaining the raw value."""

    _attr_device_class = SensorDeviceClass.ENUM

    def __init__(self, controller: EntityController, description: ModbusEnumSensorDescription, address: int) -> None:
        self._controller = controller
        self.entity_description = description
        self._address = address
        self._attr_options = list(description.options_map.values())
        self.entity_id = self._get_entity_id(Platform.SENSOR)

    @property
    def native_value(self) -> str | None:
        value = self._controller.read(self._address, signed=False)
        if value is None:
            return None
        return cast(ModbusEnumSensorDescription, self.entity_description).options_map.get(value)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"raw_value": self._controller.read(self._address, signed=False)}

    @property
    def addresses(self) -> list[int]:
        return [self._address]
