"""Base type for entity descriptions"""
from abc import ABC
from abc import abstractmethod

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity

from ..common.entity_controller import EntityController


class ModbusEntityDescriptionBase(ABC):
    @property
    @abstractmethod
    def entity_type(self) -> type[Entity]:
        """Fetch the type of entity that this description is for"""

    @property
    @abstractmethod
    def addresses(self) -> list[int]:
        """Fetch the set of modbus addresses on which this entity depends"""

    @abstractmethod
    def create_entity(
        self, controller: EntityController, entry: ConfigEntry, inv_details
    ) -> Entity:
        """Instantiate a new entity based on this description"""
