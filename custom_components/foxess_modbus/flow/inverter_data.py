from dataclasses import dataclass

from ..inverter_adapters import InverterAdapter
from ..inverter_adapters import InverterAdapterType


@dataclass
class InverterData:
    """Holds data gathered on an inverter as the user went through the flow"""

    adapter_type: InverterAdapterType | None = None
    adapter: InverterAdapter | None = None
    inverter_base_model: str | None = None
    inverter_model: str | None = None
    modbus_slave: int | None = None
    inverter_protocol: str | None = None  # TCP, UDP, SERIAL, RTU_OVER_TCP
    host: str | None = None  # host:port or /dev/serial
    entity_id_prefix: str | None = None
    friendly_name: str | None = None
