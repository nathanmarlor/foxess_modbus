import asyncio
import logging
from typing import Any

from pymodbus.client import ModbusSerialClient
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusIOException

from .const import MODBUS_TYPE
from .const import SERIAL
from .const import TCP

_LOGGER = logging.getLogger(__name__)


class ModbusClient:
    """Modbus"""

    def __init__(self, hass, config: dict[str, Any]):
        """Init"""
        self._hass = hass
        self._config = config
        self._lock = asyncio.Lock()
        self._config_type = config[MODBUS_TYPE]
        self._class = {
            SERIAL: ModbusSerialClient,
            TCP: ModbusTcpClient,
        }

        self._client = self._class[self._config_type](**config)
        self._hass.async_create_task(self.connect())

    async def connect(self):
        """Connect to device"""
        _LOGGER.debug(f"Connecting to modbus - ({self._config})")
        if not await self._async_pymodbus_call(self._client.connect):
            _LOGGER.debug("Connect failed, pymodbus will retry")

    async def close(self):
        """Close connection"""
        _LOGGER.debug("Closing connection to modbus")
        await self._async_pymodbus_call(self._client.close)

    async def read_registers(self, start_address, num_registers, holding, slave):
        """Read registers"""
        _LOGGER.debug(
            f"Reading register: ({start_address}, {num_registers}, ({slave}))"
        )
        if holding:
            response = await self._async_pymodbus_call(
                self._client.read_holding_registers,
                start_address,
                num_registers,
                slave,
            )
        else:
            response = await self._async_pymodbus_call(
                self._client.read_input_registers,
                start_address,
                num_registers,
                slave,
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
        _LOGGER.debug(
            f"Writing register: ({register_address}, {register_values}, {slave})"
        )
        if len(register_values) > 1:
            register_values = [int(i) for i in register_values]
            response = await self._async_pymodbus_call(
                self._client.write_registers,
                register_address,
                register_values,
                slave,
            )
        else:
            response = await self._async_pymodbus_call(
                self._client.write_register,
                register_address,
                int(register_values[0]),
                slave,
            )
        if response.isError():
            raise ModbusIOException(f"Error writing holding register: {response}")
        return True

    async def _async_pymodbus_call(self, call, *args):
        """Convert async to sync pymodbus call."""
        async with self._lock:
            return await self._hass.async_add_executor_job(call, *args)
