"""Unload controller"""
import logging

_LOGGER = logging.getLogger(__name__)


class UnloadController:
    """Unload controller base"""

    def __init__(self) -> None:
        self._unload_listeners = []

    def unload(self) -> None:
        """Unload all listeners"""
        for listener in self._unload_listeners:
            listener()

        self._unload_listeners.clear()
