"""Contains information on the various adapters to connect to an inverter"""
from dataclasses import dataclass
from enum import Enum

from .const import TCP
from .const import UDP
from .inverter_connection_types import CONNECTION_TYPES
from .inverter_connection_types import InverterConnectionType


class InverterAdapterType(str, Enum):
    """Describes the different means of connecting to an inverter"""

    # These values are used as translation keys in the config flow
    DIRECT = "direct"
    SERIAL = "serial"
    NETWORK = "network"


@dataclass
class InverterAdapter:
    """Describes an adapter used to connect to an inverter"""

    id: str  # Internal ID, also used as the translation key in the config flow
    type: InverterAdapterType
    connection_type: InverterConnectionType
    setup_link: str
    network_protocols: list[
        str
    ] | None = None  # If type is NETWORK/DIRECT, whether we support TCP and/or UDP
    recommended_protocol: str | None = None


# The order of elements in this array controls the order they appear in the config flow UI
ADAPTERS = {
    x.id: x
    for x in [
        InverterAdapter(
            "direct",
            InverterAdapterType.DIRECT,
            CONNECTION_TYPES["LAN"],
            setup_link="https://github.com/nathanmarlor/foxess_modbus/wiki",
            network_protocols=[TCP],
        ),
        InverterAdapter(
            "serial",
            InverterAdapterType.SERIAL,
            CONNECTION_TYPES["AUX"],
            setup_link="https://github.com/nathanmarlor/foxess_modbus/wiki",
        ),
        InverterAdapter(
            "usr-w610",
            InverterAdapterType.NETWORK,
            CONNECTION_TYPES["AUX"],
            setup_link="https://github.com/nathanmarlor/foxess_modbus/wiki",
            network_protocols=[TCP, UDP],
            recommended_protocol=UDP,
        ),
        InverterAdapter(
            "waveshare",
            InverterAdapterType.NETWORK,
            CONNECTION_TYPES["AUX"],
            setup_link="https://github.com/nathanmarlor/foxess_modbus/wiki/Waveshare-RS485-to-ETH-(B)-Setup-Guide",
            network_protocols=[TCP],
        ),
        InverterAdapter(
            "other_network",
            InverterAdapterType.NETWORK,
            CONNECTION_TYPES["AUX"],
            setup_link="https://github.com/nathanmarlor/foxess_modbus/wiki",
            network_protocols=[TCP, UDP],
        ),
    ]
}
