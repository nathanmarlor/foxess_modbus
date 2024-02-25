from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.types import RegisterPollType
from ..common.types import RegisterType
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .inverter_model_spec import ModbusAddressSpec
from .modbus_entity_mixin import ModbusEntityMixin


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusVersionSensorDescription(SensorEntityDescription, EntityFactory):
    """Description for ModbusVersionSensor"""

    address: list[ModbusAddressSpec]

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

    def create_entity_if_supported(
        self,
        _hass: HomeAssistant,
        controller: EntityController,
        inverter_model: str,
        register_type: RegisterType,
        _entry: ConfigEntry,
        inv_details: dict[str, Any],
    ) -> Entity | None:
        address = self._address_for_inverter_model(self.address, inverter_model, register_type)
        return ModbusVersionSensor(controller, self, address, inv_details) if address is not None else None


class ModbusVersionSensor(ModbusEntityMixin, SensorEntity):
    """Sensor class."""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusVersionSensorDescription,
        address: int,
        inv_details: dict[str, Any],
    ) -> None:
        self._controller = controller
        self.entity_description = entity_description
        self._address = address
        self._inv_details = inv_details
        self.entity_id = self._get_entity_id(Platform.SENSOR)

    @property
    def native_value(self) -> str | None:
        value = self._controller.read(self._address, signed=False)
        if value is None:
            return None

        # These have the format x.yy
        major = value // 100
        minor = value % 100
        return f"{major}.{minor:02}"

    @property
    def addresses(self) -> list[int]:
        return [self._address]

    @property
    def register_poll_type(self) -> RegisterPollType:
        return RegisterPollType.ON_CONNECTION
