"""Contains knowledge of the various ways to connect to inverters"""
import logging

from .const import AUX
from .const import LAN

_LOGGER = logging.getLogger(__package__)


class InverterConnectionType:
    """Describes a means of connecting to an inverter"""

    def __init__(self, key: str, serial_start_address: int) -> None:
        self.key = key
        self.serial_start_address = serial_start_address


CONNECTION_TYPES = {
    x.key: x
    for x in [
        InverterConnectionType(key=AUX, serial_start_address=10000),
        InverterConnectionType(key=LAN, serial_start_address=30000),
    ]
}
