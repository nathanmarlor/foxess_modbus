"""Defines RegisterType"""

from enum import Enum
from enum import IntEnum
from enum import StrEnum


class RegisterType(Enum):
    """The different register types exposed by inverters"""

    INPUT = 1
    HOLDING = 2


class ConnectionType(StrEnum):
    # NOTE: Values match those stored in config
    AUX = "AUX"
    LAN = "LAN"


class RegisterPollType(IntEnum):
    """Describs when a register should be polled"""

    # These must be ordered from least frequent to most frequent
    ON_CONNECTION = 0
    PERIODICALLY = 1
