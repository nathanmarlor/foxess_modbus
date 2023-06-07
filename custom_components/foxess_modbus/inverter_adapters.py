"""Contains information on the various adapters to connect to an inverter"""
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .const import AUX
from .const import LAN
from .const import MAX_READ
from .const import POLL_RATE
from .const import RTU_OVER_TCP
from .const import TCP
from .const import UDP


class InverterAdapterType(str, Enum):
    """Describes the different means of connecting to an inverter"""

    # These values are used as translation keys in the config flow
    DIRECT = "direct"
    SERIAL = "serial"
    NETWORK = "network"


_DEFAULT_POLL_RATE = 10
_DEFAULT_MAX_READ = 20  # Be safe by default


@dataclass
class InverterAdapter:
    """Describes an adapter used to connect to an inverter"""

    adapter_id: str  # Internal ID, also used as the translation key in the config flow
    adapter_type: InverterAdapterType
    connection_type: str  # AUX / LAN
    setup_link: str
    poll_rate: int
    max_read: int
    network_protocols: list[str] | None = None  # If type is NETWORK/DIRECT, whether we support TCP and/or UDP
    recommended_protocol: str | None = None
    default_host: str | None = None

    @staticmethod
    def direct(
        adapter_id: str,
        setup_link: str,
        poll_rate: int = _DEFAULT_POLL_RATE,
        max_read: int = _DEFAULT_MAX_READ,
    ) -> "InverterAdapter":
        """Add a direct connection to the inverter"""

        return InverterAdapter(
            adapter_id=adapter_id,
            adapter_type=InverterAdapterType.DIRECT,
            connection_type=LAN,
            setup_link=setup_link,
            network_protocols=[TCP],
            poll_rate=poll_rate,
            max_read=max_read,
        )

    @staticmethod
    def serial(
        adapter_id: str,
        setup_link: str,
        default_host: str = "/dev/ttyUSB0",
        poll_rate: int = _DEFAULT_POLL_RATE,
        max_read: int = _DEFAULT_MAX_READ,
    ) -> "InverterAdapter":
        """Add a serial connection to the inverter"""

        return InverterAdapter(
            adapter_id=adapter_id,
            adapter_type=InverterAdapterType.SERIAL,
            connection_type=AUX,
            setup_link=setup_link,
            default_host=default_host,
            poll_rate=poll_rate,
            max_read=max_read,
        )

    @staticmethod
    def network(
        adapter_id: str,
        setup_link: str,
        network_protocols: list[str],
        recommended_protocol: str | None = None,
        poll_rate: int = _DEFAULT_POLL_RATE,
        max_read: int = _DEFAULT_MAX_READ,
    ) -> "InverterAdapter":
        """Add a network connection to the inverter"""

        return InverterAdapter(
            adapter_id=adapter_id,
            adapter_type=InverterAdapterType.NETWORK,
            connection_type=AUX,
            setup_link=setup_link,
            network_protocols=network_protocols,
            recommended_protocol=recommended_protocol,
            poll_rate=poll_rate,
            max_read=max_read,
        )

    def inverter_config(self) -> dict[str, Any]:
        """
        Generate a dict which is merged into the user's inverter config.
        User preferences are then merged in on top of this"""
        return {
            POLL_RATE: self.poll_rate,
            MAX_READ: self.max_read,
        }


# IMPORTANT!! READ!
# * These keys are stored in user config. Do not rename or remove any!
#   (If you do, you'll need to write a migration to handle your change).
# * These keys map to strings, see the selects in languages/en.json
# * The order of elements in this array controls the order they appear in the config flow UI.
ADAPTERS = {
    x.adapter_id: x
    for x in [
        # Direct LAN Connection
        InverterAdapter.direct(
            "direct",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/Direct-Ethernet-Connection-to-Inverter",
            max_read=100,
        ),
        # Serial Adapters
        InverterAdapter.serial(
            "dsd_tech_sh_u10",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/DSD-TECH-SH-U10",
            max_read=100,
        ),
        InverterAdapter.serial(
            "runcci_yun_usb_to_rs485_converter",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/RUNCCI-YUN-USB-to-RS485-Converter",
        ),
        InverterAdapter.serial(
            "waveshare_usb_to_rs485_b",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/Waveshare-USB-to-RS485-%28B%29",
            default_host="/dev/ttyACM0",
            max_read=100,
        ),
        InverterAdapter.serial(
            "serial_other",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/Other-Serial-Adapter",
        ),
        # Network adapters
        InverterAdapter.network(
            "elfin_ew11",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/Elfin-EW11",
            network_protocols=[TCP, UDP],
            max_read=100,
        ),
        InverterAdapter.network(
            "usr_tcp232_304",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/USR-TCP232-304",
            network_protocols=[RTU_OVER_TCP],
            max_read=100,
        ),
        InverterAdapter.network(
            "usr_tcp232_410s",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/USR-TCP232-410s",
            network_protocols=[TCP, UDP],
            max_read=100,
        ),
        InverterAdapter.network(
            "usr_w610",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/USR-W610",
            network_protocols=[TCP, UDP],
            recommended_protocol=UDP,
            max_read=8,
        ),
        InverterAdapter.network(
            "waveshare_rs485_to_eth_b",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/Waveshare-RS485-to-ETH-%28B%29",
            network_protocols=[TCP, UDP],
            max_read=100,
        ),
        InverterAdapter.network(
            "network_other",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/Other-Ethernet-Adapter",
            network_protocols=[TCP, UDP, RTU_OVER_TCP],
            # This might be a W610 and they've been migrated
            max_read=8,
        ),
    ]
}
