"""Contains information on the various adapters to connect to an inverter"""

from abc import ABC
from abc import abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Any

from .common.types import ConnectionType
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


class InverterAdapterConfigProvider(ABC):
    @abstractmethod
    def inverter_config(self, network_protocol: str) -> dict[str, Any]:
        """
        Generate a dict which is merged into the user's inverter config.
        User preferences are then merged in on top of this"""


class _DefaultConfig(InverterAdapterConfigProvider):
    def __init__(self, max_read: int = _DEFAULT_MAX_READ, poll_rate: int = _DEFAULT_POLL_RATE) -> None:
        self._config = {POLL_RATE: poll_rate, MAX_READ: max_read}

    def inverter_config(self, _network_protocol: str) -> dict[str, Any]:
        return self._config


class _W610Config(InverterAdapterConfigProvider):
    def inverter_config(self, network_protocol: str) -> dict[str, Any]:
        return {
            POLL_RATE: 15 if network_protocol == TCP else 10,
            MAX_READ: 8,
        }


@dataclass
class InverterAdapter:
    """Describes an adapter used to connect to an inverter"""

    adapter_id: str  # Internal ID, also used as the translation key in the config flow
    adapter_type: InverterAdapterType
    connection_type: ConnectionType
    setup_link: str
    config: InverterAdapterConfigProvider
    network_protocols: list[str] | None = None  # If type is NETWORK/DIRECT, whether we support TCP and/or UDP
    recommended_protocol: str | None = None
    default_host: str | None = None

    @staticmethod
    def direct(
        adapter_id: str,
        setup_link: str,
        config: InverterAdapterConfigProvider,
    ) -> "InverterAdapter":
        """Add a direct connection to the inverter"""

        return InverterAdapter(
            adapter_id=adapter_id,
            adapter_type=InverterAdapterType.DIRECT,
            connection_type=ConnectionType.LAN,
            setup_link=setup_link,
            network_protocols=[TCP],
            config=config,
        )

    @staticmethod
    def serial(
        adapter_id: str,
        setup_link: str,
        config: InverterAdapterConfigProvider,
        default_host: str = "/dev/ttyUSB0",
    ) -> "InverterAdapter":
        """Add a serial connection to the inverter"""

        return InverterAdapter(
            adapter_id=adapter_id,
            adapter_type=InverterAdapterType.SERIAL,
            connection_type=ConnectionType.AUX,
            setup_link=setup_link,
            default_host=default_host,
            config=config,
        )

    @staticmethod
    def network(
        adapter_id: str,
        setup_link: str,
        network_protocols: list[str],
        config: InverterAdapterConfigProvider,
        recommended_protocol: str | None = None,
    ) -> "InverterAdapter":
        """Add a network connection to the inverter"""

        return InverterAdapter(
            adapter_id=adapter_id,
            adapter_type=InverterAdapterType.NETWORK,
            connection_type=ConnectionType.AUX,
            setup_link=setup_link,
            network_protocols=network_protocols,
            recommended_protocol=recommended_protocol,
            config=config,
        )


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
            config=_DefaultConfig(max_read=100),
        ),
        # Serial Adapters
        InverterAdapter.serial(
            "dsd_tech_sh_u10",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/DSD-TECH-SH-U10",
            config=_DefaultConfig(max_read=100),
        ),
        InverterAdapter.serial(
            "runcci_yun_usb_to_rs485_converter",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/RUNCCI-YUN-USB-to-RS485-Converter",
            config=_DefaultConfig(),
        ),
        InverterAdapter.serial(
            "waveshare_usb_to_rs485_b",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/Waveshare-USB-to-RS485-%28B%29",
            default_host="/dev/ttyACM0",
            config=_DefaultConfig(max_read=100),
        ),
        InverterAdapter.serial(
            "serial_other",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/Other-Serial-Adapter",
            config=_DefaultConfig(),
        ),
        # Network adapters
        InverterAdapter.network(
            "elfin_ew11",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/Elfin-EW11",
            network_protocols=[TCP, UDP],
            config=_DefaultConfig(max_read=100),
        ),
        InverterAdapter.network(
            "usr_tcp232_304",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/USR-TCP232-304",
            network_protocols=[RTU_OVER_TCP],
            config=_DefaultConfig(max_read=100),
        ),
        InverterAdapter.network(
            "usr_tcp232_410s",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/USR-TCP232-410s",
            network_protocols=[TCP, UDP],
            config=_DefaultConfig(max_read=100),
        ),
        InverterAdapter.network(
            "usr_w610",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/USR-W610",
            network_protocols=[TCP, UDP],
            recommended_protocol=UDP,
            config=_W610Config(),
        ),
        InverterAdapter.network(
            "waveshare_rs485_to_eth_b",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/Waveshare-RS485-to-ETH-%28B%29",
            network_protocols=[TCP, UDP],
            config=_DefaultConfig(max_read=100),
        ),
        InverterAdapter.network(
            "network_other",
            "https://github.com/nathanmarlor/foxess_modbus/wiki/Other-Ethernet-Adapter",
            network_protocols=[TCP, UDP, RTU_OVER_TCP],
            # This might be a W610 and they've been migrated
            config=_W610Config(),
        ),
    ]
}
