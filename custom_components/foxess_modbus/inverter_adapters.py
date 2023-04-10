"""Contains information on the various adapters to connect to an inverter"""
from dataclasses import dataclass

from .const import SERIAL
from .const import TCP
from .const import UDP
from .inverter_connection_types import CONNECTION_TYPES
from .inverter_connection_types import InverterConnectionType


@dataclass
class InverterAdapter:
    """Describes an adapter used to connect to an inverter"""

    id: str  # Internal ID, also used as the translation key
    connection_type: InverterConnectionType
    setup_link: str
    protocols: list[str]
    recommended_protocol: str | None = None


ADAPTERS = {
    x.id: x
    for x in [
        InverterAdapter(
            "direct",
            CONNECTION_TYPES["LAN"],
            setup_link="https://github.com/nathanmarlor/foxess_modbus/wiki",
            protocols=[TCP],
        ),
        InverterAdapter(
            "serial",
            CONNECTION_TYPES["AUX"],
            setup_link="https://github.com/nathanmarlor/foxess_modbus/wiki",
            protocols=[SERIAL],
        ),
        InverterAdapter(
            "usr-w610",
            CONNECTION_TYPES["AUX"],
            setup_link="https://github.com/nathanmarlor/foxess_modbus/wiki",
            protocols=[TCP, UDP],
            recommended_protocol=UDP,
        ),
        InverterAdapter(
            "waveshare",
            CONNECTION_TYPES["AUX"],
            setup_link="https://github.com/nathanmarlor/foxess_modbus/wiki/Waveshare-RS485-to-ETH-(B)-Setup-Guide",
            protocols=[TCP],
        ),
    ]
}
