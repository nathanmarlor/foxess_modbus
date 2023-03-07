"""Callback controller"""
import logging

_LOGGER = logging.getLogger(__name__)


class CallbackController:
    """Callback controller base"""

    def __init__(self) -> None:
        self._update_listeners = []

    def add_update_listener(self, listener) -> None:
        """Add a listener for update notifications."""
        self._update_listeners.append(listener)

    def _notify_listeners(self) -> None:
        """Notify listeners"""
        for listener in self._update_listeners:
            listener.update_callback()
