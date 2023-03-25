"""Entity Factory"""
from abc import ABC
from abc import abstractmethod

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController


class EntityFactory(ABC):
    """Factory which can create entities"""

    @property
    @abstractmethod
    def entity_type(self) -> type[Entity]:
        """Fetch the type of entity that this factory creates"""

    @property
    @abstractmethod
    def addresses(self) -> list[int]:
        """Fetch the set of modbus addresses on which the created entity will depend"""

    @abstractmethod
    def create_entity(
        self, controller: EntityController, entry: ConfigEntry, inv_details
    ) -> Entity:
        """Instantiate a new entity. The returned type must match self.entity_type"""
