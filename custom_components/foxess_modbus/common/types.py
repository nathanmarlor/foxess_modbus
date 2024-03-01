"""Defines RegisterType"""

from enum import Enum
from enum import Flag
from enum import IntEnum
from enum import StrEnum
from enum import auto


class RegisterType(Enum):
    """The different register types exposed by inverters"""

    INPUT = 1
    HOLDING = 2


class ConnectionType(StrEnum):
    # NOTE: Values match those stored in config
    AUX = "AUX"
    LAN = "LAN"


class InverterModel(StrEnum):
    """
    Inverter models are detected during auto-connection (during the config flow) and stored in config
    as config[INVERTER_BASE].
    """

    H1 = "H1"
    AC1 = "AC1"
    AIO_H1 = "AIO-H1"

    KH = "KH"

    H3 = "H3"
    AC3 = "AC3"
    AIO_H3 = "AIO-H3"
    KUARA_H3 = "KUARA-H3"
    SK_HWR = "SK-HWR"
    STAR_H3 = "STAR-H3"
    SOLAVITA_SP = "SOLAVITA-SP"


class Inv(Flag):
    """
    An InverterModel and connection type (and, maybe in the future, things like manager version) are together mapped to
    an Inv, in inverter_profiles. This Inv is then used as a key in entity_descriptions to identify the register
    address(es) and register type (Input, Holding) to use
    """

    H1_LAN = auto()
    H1_G1 = auto()

    H3 = auto()
    KUARA_H3 = auto()
    H3_SET = H3 | KUARA_H3

    KH_PRE119 = auto()
    KH_119 = auto()
    KH_SET = KH_PRE119 | KH_119

    ALL = H1_LAN | H1_G1 | H3_SET | KH_SET


class RegisterPollType(IntEnum):
    """Describes when a register should be polled"""

    # These must be ordered from least frequent to most frequent
    ON_CONNECTION = 0
    PERIODICALLY = 1
