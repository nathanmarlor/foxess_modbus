import asyncio
import logging

from pymodbus.client import ModbusBaseClient
from pymodbus.exceptions import ConnectionException
from pymodbus.exceptions import ModbusIOException

_LOGGER = logging.getLogger(__name__)


class ModbusClient:
    """Modbus"""

    def __init__(self, client: ModbusBaseClient):
        """Init"""
        self._client = client
        self._lock = asyncio.Lock()

    async def _connect(self):
        """Connect to device"""
        if not self._client.connected:
            if not await self._client.connect():
                raise ConnectionException("Error connecting to device)")

    async def close(self):
        """Close connection"""
        async with self._lock:
            if self._client.connected:
                await self._client.close()

    async def read_registers(self, start_address, num_registers, holding, slave):
        """Read registers"""
        async with self._lock:
            if not self._client.connected:
                _LOGGER.info("Connecting to modbus")
                await self._connect()

            _LOGGER.debug(f"Reading register: ({start_address}, {num_registers})")
            if holding:
                response = await self._client.read_holding_registers(
                    start_address, num_registers, slave
                )
            else:
                response = await self._client.read_input_registers(
                    start_address, num_registers, slave
                )
            if response.isError():
                raise ModbusIOException(f"Error reading registers: {response}")

            # convert to signed integers
            regs = [
                reading if reading < 32768 else reading - 65536
                for reading in response.registers
            ]
            return regs

    async def write_registers(self, register_address, register_values, slave):
        """Write registers"""
        async with self._lock:
            if not self._client.connected:
                _LOGGER.info("Connecting to modbus")
                await self._connect()

            _LOGGER.debug(f"Writing register: ({register_address}, {register_values})")

            if len(register_values) > 1:
                register_values = [int(i) for i in register_values]
                response = await self._client.write_registers(
                    register_address, register_values, slave
                )
            else:
                response = await self._client.write_register(
                    register_address, int(register_values[0]), slave
                )
            if response.isError():
                raise ModbusIOException(f"Error writing holding register: {response}")
            return True
