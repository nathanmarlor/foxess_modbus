import logging

from pymodbus.client import AsyncModbusTcpClient
from pymodbus.exceptions import ConnectionException
from pymodbus.exceptions import ModbusIOException

_LOGGER = logging.getLogger(__name__)


class ModbusClient:
    """Modbus"""

    def __init__(self, host, port, slave):
        """Init"""
        self._host = host
        self._port = port
        self._slave = slave
        self._client = AsyncModbusTcpClient(self._host, self._port)

    async def _connect(self):
        """Connect to device"""
        if not await self._client.connect():
            raise ConnectionException(
                f"Error connecting to device: ({self._host}:{self._port})"
            )

    async def read_registers(self, start_address, num_registers, holding):
        """Read registers"""
        if not self._client.connected:
            _LOGGER.info(f"Connecting to modbus: ({self._host}:{self._port})")
            await self._connect()

        _LOGGER.debug(f"Reading register: ({start_address}, {num_registers})")
        if holding:
            response = await self._client.read_holding_registers(
                start_address, num_registers, self._slave
            )
        else:
            response = await self._client.read_input_registers(
                start_address, num_registers, self._slave
            )
        if response.isError():
            raise ModbusIOException(f"Error reading registers: {response}")

        # convert to signed integers
        regs = [
            reading if reading < 32768 else reading - 65536
            for reading in response.registers
        ]
        return regs

    async def write_registers(self, register_address, register_values):
        """Write registers"""
        if not self._client.connected:
            _LOGGER.info(f"Connecting to modbus: ({self._host}:{self._port})")
            await self._connect()

        _LOGGER.debug(f"Writing register: ({register_address}, {register_values})")

        if len(register_values) > 1:
            response = await self._client.write_registers(
                register_address, register_values, self._slave
            )
        else:
            response = await self._client.write_register(
                register_address, int(register_values[0]), self._slave
            )
        if response.isError():
            raise ModbusIOException(f"Error writing holding register: {response}")
        return True
