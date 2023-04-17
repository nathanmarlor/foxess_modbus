import asyncio
import logging
import socket
from typing import Any

from pymodbus.client import ModbusSerialClient
from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ModbusIOException

from .const import MODBUS_TYPE
from .const import SERIAL
from .const import TCP

_LOGGER = logging.getLogger(__name__)


class CustomModbusTcpClient(ModbusTcpClient):
    def __init__(self, **kwargs: any) -> None:
        super().__init__(**kwargs)

    def connect(self) -> bool:
        was_connected = self.socket is not None
        is_connected = super().connect()
        # pymodbus doesn't disable Nagle's algorithm. This slows down reads quite substantially as the
        # TCP stack waits to see if we're going to send anything else. Disable it ourselves.
        if not was_connected and is_connected:
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, True)
        return is_connected


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
            TCP: CustomModbusTcpClient,
        }
        self._poll_delay = 30 / 1000 if self._config_type == SERIAL else 0

        self._client = self._class[self._config_type](**config)

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

        return response.registers

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
            result = await self._hass.async_add_executor_job(call, *args)
            # This seems to be required for serial devices, otherwise subsequent reads fail
            # The HA modbus integration does the same
            if self._poll_delay > 0:
                await asyncio.sleep(self._poll_delay)
            return result
