"""Sensor"""

import logging
from dataclasses import dataclass
from datetime import timedelta
from typing import Any
from typing import cast

from homeassistant.components.integration.sensor import DEFAULT_ROUND
from homeassistant.components.integration.sensor import IntegrationSensor
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import Platform
from homeassistant.const import UnitOfTime
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.types import Inv
from ..common.types import RegisterType
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .inverter_model_spec import EntitySpec
from .modbus_entity_mixin import ModbusEntityMixin
from .modbus_entity_mixin import get_entity_id

_LOGGER = logging.getLogger(__name__)

MAX_SUB_INTERVAL = timedelta(minutes=1)  # Default used by integration sensor config


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusIntegrationSensorDescription(SensorEntityDescription, EntityFactory):
    """Custom sensor description"""

    models: list[EntitySpec]
    integration_method: str
    round_digits: int | None = None
    source_entity: str
    unit_time: UnitOfTime

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

    def create_entity_if_supported(
        self,
        controller: EntityController,
        inverter_model: Inv,
        register_type: RegisterType,
    ) -> Entity | None:
        if not self._supports_inverter_model(self.models, inverter_model, register_type):
            return None

        source_entity = get_entity_id(controller, Platform.SENSOR, self.source_entity)

        # this piggybacks on the existing factory to create IntegrationSensors
        return ModbusIntegrationSensor(
            controller=controller,
            entity_description=self,
            integration_method=self.integration_method,
            round_digits=self.round_digits,
            source_entity=source_entity,
            unit_time=self.unit_time,
        )

    def serialize(self, inverter_model: Inv) -> dict[str, Any] | None:
        address_map = self._addresses_for_serialization(self.models, inverter_model)
        if address_map is None:
            return None

        return {
            "type": "integration-sensor",
            "key": self.key,
            "name": self.name,
            "register_types": address_map.keys(),
            "method": self.integration_method,
            "source": self.source_entity,
            "unit_time": self.unit_time,
        }


class ModbusIntegrationSensor(ModbusEntityMixin, IntegrationSensor):
    """Sensor class."""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusIntegrationSensorDescription,
        integration_method: str,
        round_digits: int | None,
        source_entity: str,
        unit_time: UnitOfTime,
    ) -> None:
        """Initialize the sensor."""

        if round_digits is None:
            round_digits = DEFAULT_ROUND

        self._controller = controller
        self.entity_description = entity_description
        self.entity_id = self._get_entity_id(Platform.SENSOR)

        IntegrationSensor.__init__(
            self=self,
            integration_method=integration_method,
            name=cast(str, entity_description.name),
            round_digits=round_digits,
            source_entity=source_entity,
            unique_id=None,
            unit_prefix=None,
            unit_time=unit_time,
            max_sub_interval=MAX_SUB_INTERVAL,
        )

        # Use the icon from entity_description
        delattr(self, "_attr_icon")

    @property
    def addresses(self) -> list[int]:
        return []
