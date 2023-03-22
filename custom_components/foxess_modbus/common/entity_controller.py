"""Callback controller"""
import logging
from abc import ABC
from abc import abstractmethod

_LOGGER = logging.getLogger(__name__)


class EntityController(ABC):
    """Callback controller base"""

    def __init__(self) -> None:
        self._update_listeners = []

    def add_update_listener(self, listener) -> None:
        """Add a listener for update notifications."""
        self._update_listeners.append(listener)

    def _notify_listeners(self, changed_addresses: set[int]) -> None:
        """Notify listeners"""
        for listener in self._update_listeners:
            listener.update_callback(changed_addresses)

    @abstractmethod
    async def write_register(self, address: int, value: int) -> None:
        """Write a single value to a register"""

    @abstractmethod
    async def read(self, address: int) -> int | None:
        """Fetch the last-read value for the given address, or None if none is avaiable"""
