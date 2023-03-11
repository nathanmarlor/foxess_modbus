import logging

from custom_components.foxess_modbus.modbus_client import ModbusClient
from pymodbus.client import AsyncModbusTcpClient

_LOGGER = logging.getLogger(__name__)


class ModbusTCPClient(ModbusClient):
    """Modbus"""

    def __init__(self, host, port):
        """Init"""
        client = AsyncModbusTcpClient(host, port)
        ModbusClient.__init__(self, client)
