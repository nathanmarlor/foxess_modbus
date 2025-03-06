"""Defines RegisterType"""  # noqa: A005

from enum import Enum
from enum import Flag
from enum import IntEnum
from enum import StrEnum
from enum import auto
from typing import TYPE_CHECKING
from typing import Callable
from typing import NotRequired
from typing import TypeAlias
from typing import TypedDict

if TYPE_CHECKING:
    from ..client.modbus_client import ModbusClient
    from ..modbus_controller import ModbusController


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

    H1_G1 = "H1"  # Can't change the value, as it's set in people's configs
    H1_G2 = "H1_G2"

    AC1 = "AC1"
    AC1_G2 = "AC1_G2"
    AIO_H1 = "AIO-H1"
    AIO_AC1 = "AIO-AC1"

    KH = "KH"

    H3 = "H3"
    AC3 = "AC3"
    AIO_H3 = "AIO-H3"
    KUARA_H3 = "KUARA-H3"
    SK_HWR = "SK-HWR"
    STAR_H3 = "STAR-H3"
    SOLAVITA_SP = "SOLAVITA-SP"
    ATRONIX_AX = "ATRONIX_AX"
    ENPAL_IX = "ENPAL_IX"

    H3_PRO = "H3_PRO"


class Inv(Flag):
    """
    An InverterModel and connection type (and, maybe in the future, things like manager version) are together mapped to
    an Inv, in inverter_profiles. This Inv is then used as a key in entity_descriptions to identify the register
    address(es) and register type (Input, Holding) to use
    """

    H1_LAN = auto()
    H1_G1 = auto()
    H1_G2_PRE144 = auto()
    H1_G2_144 = auto()
    H1_G2_SET = H1_G2_PRE144 | H1_G2_144

    KH_PRE119 = auto()
    KH_PRE133 = auto()
    KH_133 = auto()
    KH_SET = KH_PRE119 | KH_PRE133 | KH_133

    H3_PRE180 = auto()
    H3_180 = auto()
    AIO_H3_PRE101 = auto()
    AIO_H3_101 = auto()
    KUARA_H3 = auto()
    H3_SET = H3_180 | H3_PRE180 | AIO_H3_101 | AIO_H3_PRE101 | KUARA_H3

    H3_SMART = auto()

    H3_PRO_PRE122 = auto()
    H3_PRO_122 = auto()
    H3_PRO_SET = H3_PRO_PRE122 | H3_PRO_122 | H3_SMART

    ALL = H1_LAN | H1_G1 | H1_G2_SET | KH_SET | H3_SET | H3_PRO_SET


class RegisterPollType(IntEnum):
    """Describes when a register should be polled"""

    # These must be ordered from least frequent to most frequent
    ON_CONNECTION = 0
    PERIODICALLY = 1


class HassDataEntry(TypedDict):
    controllers: list["ModbusController"]
    modbus_clients: list["ModbusClient"]
    unload: NotRequired[Callable[[], None]]


HassData: TypeAlias = dict[str, HassDataEntry]
