"""Entity which gets its value by applying a lambda to a set of other entities"""

import logging
from dataclasses import dataclass
from typing import Any
from typing import Callable

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import Platform
from homeassistant.core import Event
from homeassistant.core import EventStateChangedData
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change_event

from ..common.entity_controller import EntityController
from ..common.types import Inv
from ..common.types import RegisterType
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .inverter_model_spec import EntitySpec
from .modbus_entity_mixin import ModbusEntityMixin
from .modbus_entity_mixin import get_entity_id

_LOGGER = logging.getLogger(__name__)


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusLambdaSensorDescription(SensorEntityDescription, EntityFactory):  # type: ignore[misc, override]
    """Entity description for ModbusLambdaSensors"""

    models: list[EntitySpec]
    sources: list[str]
    # This might have fewer inputs than there are elements in sources, if some inputs are disabled
    method: Callable[[list[float]], Any]

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

        source_entity_ids = [get_entity_id(controller, Platform.SENSOR, x) for x in self.sources]

        return ModbusLambdaSensor(
            controller=controller,
            entity_description=self,
            source_entity_ids=source_entity_ids,
            method=self.method,
        )

    def serialize(self, inverter_model: Inv) -> dict[str, Any] | None:
        address_map = self._addresses_for_serialization(self.models, inverter_model)
        if address_map is None:
            return None

        return {
            "type": "lambda",
            "key": self.key,
            "name": self.name,
            "register_types": address_map.keys(),
            "sources": self.sources,
        }


class ModbusLambdaSensor(ModbusEntityMixin, SensorEntity):
    """Generates a value by applying a lambda to the values of a number of other sensors"""

    def __init__(
        self,
        controller: EntityController,
        entity_description: ModbusLambdaSensorDescription,
        source_entity_ids: list[str],
        method: Callable[[list[float]], Any],
    ) -> None:
        self._controller = controller
        self.entity_description = entity_description
        self._source_entity_ids = source_entity_ids
        self._method = method

    async def async_added_to_hass(self) -> None:
        """Add update callback after being added to hass."""
        await super().async_added_to_hass()

        self.async_on_remove(async_track_state_change_event(self.hass, self._source_entity_ids, self._handle_event))

        self._update_value()

    def _handle_event(self, _event: Event[EventStateChangedData]) -> None:
        self._update_value()

    def _update_value(self) -> None:
        inputs = []
        new_value = None
        success = True
        # If all source sensors are unknown/unavailable, return unknown.
        # However we might be operating on a number of inputs and the user might have disabled some
        # (e.g. we sum PV1-PV4 and the user disabled PV4), so if any input is disabled (provided we have
        # at least one enabled input), we'll keep going.
        # However, if any input isn't a float, or is unknown/unavailable, we'll abort.
        for source in self._source_entity_ids:
            state = self.hass.states.get(source)
            if state is None:
                # Disabled
                continue
            str_value = state.state
            if str_value is None or str_value == "unknown" or str_value == "unavailable":
                success = False
                break
            try:
                float_value = float(str_value)
                inputs.append(float_value)
            except ValueError:
                success = False
                break

        if success and len(inputs) > 0:
            new_value = self._method(inputs)

        if new_value != self._attr_native_value:
            self._attr_native_value = new_value
            self.schedule_update_ha_state()

    @property
    def addresses(self) -> list[int]:
        return []
