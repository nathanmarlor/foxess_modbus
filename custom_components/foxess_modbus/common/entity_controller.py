"""Callback controller"""
import logging
from abc import ABC
from abc import abstractmethod
from enum import Enum

_LOGGER = logging.getLogger(__name__)


class ModbusControllerEntity(ABC):
    """Interface implemented by entities controlled by the ModbusController"""

    @property
    @abstractmethod
    def addresses(self) -> list[int]:
        """The addresses that this entity depends on (if any)"""

    @abstractmethod
    def update_callback(self, changed_addresses: set[int]) -> None:
        """Notify listeners that the given addresses have changed"""

    @abstractmethod
    def is_connected_changed_callback(self) -> None:
        """Notify listeners that availability state of the inverter has changed"""


class RemoteControlMode(Enum):
    DISABLE = 0
    FORCE_CHARGE = 1
    FORCE_DISCHARGE = 2


class EntityRemoteControlManager(ABC):
    @property
    @abstractmethod
    def mode(self) -> RemoteControlMode:
        """Get the current mode"""

    @abstractmethod
    async def set_mode(self, value: RemoteControlMode) -> None:
        """Set the current mode"""


class EntityController(ABC):
    """Interface given to entities to access the ModbusController"""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Returns whether the inverter is currently connected"""

    @property
    @abstractmethod
    def remote_control_manager(self) -> EntityRemoteControlManager | None:
        """Fetch the remote control manager, if any"""

    @abstractmethod
    def register_modbus_entity(self, listener: ModbusControllerEntity) -> None:
        """Register a modbus entity with the ModbusController"""

    @abstractmethod
    def remove_modbus_entity(self, listener: ModbusControllerEntity) -> None:
        """Removes a modbus entity from the ModbusController"""

    @abstractmethod
    async def write_register(self, address: int, value: int) -> None:
        """Write a single value to a register"""

    @abstractmethod
    def read(self, address: int) -> int | None:
        """Fetch the last-read value for the given address, or None if none is avaiable"""
