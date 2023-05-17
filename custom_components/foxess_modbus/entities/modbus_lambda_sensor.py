import logging
from dataclasses import dataclass
from typing import Any
from typing import Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change_event

from ..common.entity_controller import EntityController
from ..common.register_type import RegisterType
from .entity_factory import EntityFactory
from .inverter_model_spec import EntitySpec
from .modbus_entity_mixin import ModbusEntityMixin

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True)
class ModbusLambdaSensorDescription(SensorEntityDescription, EntityFactory):
    """Entity description for ModbusLambdaSensors"""

    models: list[EntitySpec]
    sources: list[str]
    method: Callable[[list[float]], Any]

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
        if not self._supports_inverter_model(
            self.models, inverter_model, register_type
        ):
            return None

        return ModbusLambdaSensor(
            controller=controller,
            entity_description=self,
            inv_details=inv_details,
            sources=self.sources,
            method=self.method,
        )


class ModbusLambdaSensor(ModbusEntityMixin, SensorEntity):
    """Generates a value by applying a lambda to the values of a number of other sensors"""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusLambdaSensorDescription,
        inv_details: dict[str, Any],
        sources: list[str],
        method: Callable[[list[float]], Any],
    ) -> None:
        self._controller = controller
        self.entity_description = entity_description
        self._inv_details = inv_details
        self._source_entity_ids = [
            f"sensor.{self._add_entity_id_prefix(x)}" for x in sources
        ]
        self._method = method

    async def async_added_to_hass(self) -> None:
        """Add update callback after being added to hass."""
        await super().async_added_to_hass()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass, self._source_entity_ids, self._handle_event
            )
        )

        self._update_value()

    def _handle_event(self, _event: Event):
        self._update_value()

    def _update_value(self):
        inputs = []
        new_value = None
        for source in self._source_entity_ids:
            state = self.hass.states.get(source)
            if state is None:
                break
            str_value = state.state
            if (
                str_value is None
                or str_value == "unknown"
                or str_value == "unavailable"
            ):
                break
            try:
                float_value = float(str_value)
                inputs.append(float_value)
            except ValueError:
                break
        else:
            new_value = self._method(inputs)

        if new_value != self._attr_native_value:
            self._attr_native_value = new_value
            self.async_schedule_update_ha_state()

    @property
    def addresses(self) -> list[int]:
        return []
