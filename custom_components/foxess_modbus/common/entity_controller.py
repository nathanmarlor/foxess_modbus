"""Callback controller"""

import logging
from abc import ABC
from abc import abstractmethod
from enum import Enum

from .register_poll_type import RegisterPollType

_LOGGER = logging.getLogger(__name__)


class ModbusControllerEntity(ABC):
    """Interface implemented by entities controlled by the ModbusController"""

    @property
    @abstractmethod
    def addresses(self) -> list[int]:
        """The addresses that this entity depends on (if any)"""

    @property
    def register_poll_type(self) -> RegisterPollType:
        return RegisterPollType.PERIODICALLY

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

    @property
    @abstractmethod
    def charge_power(self) -> int | None:
        """Get the current charge power"""

    @charge_power.setter
    @abstractmethod
    def charge_power(self, value: int | None) -> None:
        """Set the charge power"""

    @property
    @abstractmethod
    def discharge_power(self) -> int | None:
        """Get the current discharge power"""

    @discharge_power.setter
    @abstractmethod
    def discharge_power(self, value: int | None) -> None:
        """Set the discharge power"""

    @property
    @abstractmethod
    def max_soc(self) -> int | None:
        """Gets a value to override the max_soc register, if any"""

    @max_soc.setter
    @abstractmethod
    def max_soc(self, value: int | None) -> None:
        """Set a value to override the max_soc register, if any"""


class EntityController(ABC):
    """Interface given to entities to access the ModbusController"""

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Returns whether the inverter is currently connected"""

    @property
    @abstractmethod
    def current_connection_error(self) -> str | None:
        """Returns the current connection error, or None if there is no connection error"""

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
    async def write_registers(self, start_address: int, values: list[int]) -> None:
        """Write multiple registers"""

    @abstractmethod
    def read(self, address: int, *, signed: bool) -> int | None:
        """Fetch the last-read value for the given address, or None if none is avaiable"""
