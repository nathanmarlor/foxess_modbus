"""Callback controller"""
import logging
from abc import ABC
from abc import abstractmethod

_LOGGER = logging.getLogger(__name__)


class EntityUpdateListener(ABC):
    """Interface implemented by subscribers to EntityController"""

    @abstractmethod
    def update_callback(self, changed_addresses: set[int]) -> None:
        """Notify listeners that the given addresses have changed"""

    @abstractmethod
    def is_connected_changed_callback(self) -> None:
        """Notify listeners that availability state of the inverter has changed"""


class EntityController(ABC):
    """Callback controller base"""

    def __init__(self) -> None:
        self._update_listeners: set[EntityUpdateListener] = set()

    @property
    @abstractmethod
    def is_connected(self) -> bool:
        """Returns whether the inverter is currently connected"""

    def add_update_listener(self, listener: EntityUpdateListener) -> None:
        """Add a listener for update notifications."""
        self._update_listeners.add(listener)

    def remove_update_listener(self, listener: EntityUpdateListener) -> None:
        """Removes a listener from update notifications"""
        self._update_listeners.discard(listener)

    def _notify_update(self, changed_addresses: set[int]) -> None:
        """Notify listeners"""
        for listener in self._update_listeners:
            listener.update_callback(changed_addresses)

    def _notify_is_connected_changed(self) -> None:
        """Notify listeners that the availability states of the inverter changed"""
        for listener in self._update_listeners:
            listener.is_connected_changed_callback()

    @abstractmethod
    async def write_register(self, address: int, value: int) -> None:
        """Write a single value to a register"""

    @abstractmethod
    def read(self, address: int) -> int | None:
        """Fetch the last-read value for the given address, or None if none is avaiable"""
