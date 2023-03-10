import logging

from custom_components.foxess_modbus.modbus_client import ModbusClient
from pymodbus.client import AsyncModbusSerialClient

_LOGGER = logging.getLogger(__name__)


class ModbusSerialClient(ModbusClient):
    """Modbus"""

    def __init__(self, device, slave):
        """Init"""
        client = AsyncModbusSerialClient(device)
        ModbusClient.__init__(self, client, slave)
