import logging

from custom_components.foxess_modbus.modbus_client import ModbusClient
from pymodbus.client import AsyncModbusSerialClient

_LOGGER = logging.getLogger(__name__)


class ModbusSerialClient(ModbusClient):
    """Modbus"""

    def __init__(self, device):
        """Init"""
        client = AsyncModbusSerialClient(device, baudrate=9600)
        ModbusClient.__init__(self, client)
