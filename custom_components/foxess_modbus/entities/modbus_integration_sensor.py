"""Sensor"""
import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.integration.sensor import DEFAULT_ROUND
from homeassistant.components.integration.sensor import IntegrationSensor
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.register_type import RegisterType
from .entity_factory import EntityFactory
from .inverter_model_spec import EntitySpec
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
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
        inverter_model: str,
        register_type: RegisterType,
        entry: ConfigEntry,
        inv_details: dict[str, Any],
    ) -> Entity | None:
        if not self._supports_inverter_model(self.models, inverter_model, register_type):
            return None

        # this piggybacks on the existing factory to create IntegrationSensors
        return ModbusIntegrationSensor(
            controller=controller,
            entity_description=self,
            entry=entry,
            inv_details=inv_details,
            integration_method=self.integration_method,
            round_digits=self.round_digits,
            source_entity=self.source_entity,
            unit_time=self.unit_time,
        )


class ModbusIntegrationSensor(ModbusEntityMixin, IntegrationSensor):
    """Sensor class."""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusIntegrationSensorDescription,
        entry: ConfigEntry,
        inv_details: dict[str, Any],
        integration_method: str,
        round_digits: int | None,
        source_entity: str,
        unit_time: UnitOfTime,
    ) -> None:
        """Initialize the sensor."""

        if round_digits is None:
            round_digits = DEFAULT_ROUND

        self._controller = controller
        self._entry = entry
        self._inv_details = inv_details
        self.entity_description = entity_description
        self.entity_id = "sensor." + self._get_unique_id()

        source_entity = f"sensor.{self._add_entity_id_prefix(source_entity)}"

        IntegrationSensor.__init__(
            self=self,
            integration_method=integration_method,
            name=entity_description.name,
            round_digits=round_digits,
            source_entity=source_entity,
            unique_id=None,
            unit_prefix=None,
            unit_time=unit_time,
        )

        # Use the icon from entity_description
        delattr(self, "_attr_icon")

    @property
    def addresses(self) -> list[int]:
        return []
