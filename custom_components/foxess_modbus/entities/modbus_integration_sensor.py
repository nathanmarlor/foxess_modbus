"""Sensor"""
import logging
from dataclasses import dataclass

from homeassistant.components.integration.sensor import IntegrationSensor
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.components.sensor import SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTime
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController
from ..common.register_type import RegisterType
from ..const import ENTITY_ID_PREFIX
from .entity_factory import EntityFactory
from .inverter_model_spec import EntitySpec
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class ModbusIntegrationSensorDescription(SensorEntityDescription, EntityFactory):
    """Custom sensor description"""

    models: list[EntitySpec]
    integration_method: str
    name: str
    round_digits: int
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
        inv_details,
    ) -> Entity | None:
        if (
            self._addresses_for_inverter_model(
                self.models, inverter_model, register_type
            )
            is None
        ):
            return None

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

        entity_id_prefix = self._inv_details[ENTITY_ID_PREFIX]
        if entity_id_prefix != "":
            source_entity = f"sensor.{entity_id_prefix}_{source_entity}"
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

    @property
    def addresses(self) -> list[int]:
        return []
