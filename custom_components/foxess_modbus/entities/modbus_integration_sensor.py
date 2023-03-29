"""Sensor"""
import logging
from dataclasses import dataclass

from custom_components.foxess_modbus.const import FRIENDLY_NAME
from custom_components.foxess_modbus.entities.modbus_entity_mixin import (
    ModbusEntityMixin,
)
from homeassistant.components.integration.sensor import IntegrationSensor
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.sensor import SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from .entity_factory import EntityFactory

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class ModbusIntegrationSensorDescription(SensorEntityDescription, EntityFactory):
    """Custom sensor description"""

    # Unused for this sensor type
    address = 0
    integration_method: str
    name: str
    round_digits: int
    source_entity: str
    unit_time: UnitOfTime

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

    @property
    def addresses(self) -> list[int]:
        # Unused for this sensor type
        return []

    def create_entity(
        self, controller: EntityController, entry: ConfigEntry, inv_details
    ) -> Entity:
        # this piggybacks on the existing factory to create IntegrationSensors
        return ModbusIntegrationSensor(
            controller=controller,
            entity_description=self,
            entry=entry,
            inv_details=inv_details,
            integration_method=self.integration_method,
            name=self.name,
            round_digits=self.round_digits,
            source_entity=self.source_entity,
            unit_time=self.unit_time,
        )


class ModbusIntegrationSensor(ModbusEntityMixin, IntegrationSensor):
    """Sensor class."""

    def __init__(
        self,
        controller,
        entity_description,
        entry,
        inv_details,
        integration_method: str,
        name: str,
        round_digits: int,
        source_entity: str,
        unit_time: UnitOfTime,
    ) -> None:
        """Initialize the sensor."""

        self._controller = controller
        self._entry = entry
        self._inv_details = inv_details
        self.entity_description = entity_description
        self.entity_id = "sensor." + self._get_unique_id()

        friendly_name = self._inv_details[FRIENDLY_NAME]
        if friendly_name != "":
            source_entity = f"sensor.{friendly_name}_{source_entity}"
        else:
            source_entity = f"sensor.{source_entity}"

        IntegrationSensor.__init__(
            self=self,
            integration_method=integration_method,
            name=name,
            round_digits=round_digits,
            source_entity=source_entity,
            unique_id=None,
            unit_prefix=None,
            unit_time=unit_time,
        )

    @property
    def native_unit_of_measurement(self) -> str:
        """Return native unit of measurement"""
        return self.entity_description.native_unit_of_measurement

    @property
    def state_class(self) -> SensorStateClass:
        """Return the device class of the sensor."""
        return self.entity_description.state_class

    @property
    def should_poll(self) -> bool:
        return False
