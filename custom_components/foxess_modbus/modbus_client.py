import asyncio
import logging
import socket
from typing import Any

from pymodbus.client import ModbusSerialClient
from pymodbus.client import ModbusTcpClient
from pymodbus.client import ModbusUdpClient
from pymodbus.pdu import ModbusResponse
from pymodbus.register_read_message import ReadHoldingRegistersResponse
from pymodbus.register_read_message import ReadInputRegistersResponse
from pymodbus.register_write_message import WriteMultipleRegistersResponse
from pymodbus.register_write_message import WriteSingleRegisterResponse

from .common.register_type import RegisterType
from .const import MODBUS_TYPE
from .const import SERIAL
from .const import TCP
from .const import UDP


_LOGGER = logging.getLogger(__name__)


class CustomModbusTcpClient(ModbusTcpClient):
    def __init__(self, **kwargs: any) -> None:
        super().__init__(**kwargs)

    def connect(self) -> bool:
        was_connected = self.socket is not None
        if not was_connected:
            _LOGGER.debug("Connecting to %s", self.params)
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
            UDP: ModbusUdpClient,
        }
        self._poll_delay = 30 / 1000 if self._config_type == SERIAL else 0

        self._client = self._class[self._config_type](**config)

    async def close(self):
        """Close connection"""
        _LOGGER.debug("Closing connection to modbus on %s", self)
        await self._async_pymodbus_call(self._client.close)

    async def read_registers(
        self,
        start_address: int,
        num_registers: int,
        register_type: RegisterType,
        slave: int,
    ):
        """Read registers"""
        if register_type == RegisterType.HOLDING:
            response = await self._async_pymodbus_call(
                self._client.read_holding_registers,
                start_address,
                num_registers,
                slave,
            )
            expected_response_type = ReadHoldingRegistersResponse
        elif register_type == RegisterType.INPUT:
            response = await self._async_pymodbus_call(
                self._client.read_input_registers,
                start_address,
                num_registers,
                slave,
            )
            expected_response_type = ReadInputRegistersResponse
        else:
            assert False

        if response.isError():
            message = f"Error reading registers. Type: {register_type}; start: {start_address}; count: {num_registers}; slave: {slave}"
            if isinstance(response, BaseException):
                raise ModbusClientFailedException(message, self, response) from response
            raise ModbusClientFailedException(message, self, response)

        # We've seen cases where the remote device gets two requests at the same time and sends the wrong response to the wrong thing.
        # pymodbus doesn't check whether the response type matches the request type
        if not isinstance(response, expected_response_type):
            message = (
                f"Error reading registers. Type: {register_type}; start: {start_address}; count: {num_registers}; slave: {slave}. "
                + f"Received incorrect response type {response}. Please ensure that your adapter is correctly configured to "
                + "allow multiple connections, see the instructions at https://github.com/nathanmarlor/foxess_modbus/wiki"
            )
            # ModbusController only logs this as debug. Make this a bit clearer so people spot and fix this
            _LOGGER.warning(message)
            raise ModbusClientFailedException(
                message,
                self,
                response,
            )

        return response.registers

    async def write_registers(self, register_address, register_values, slave):
        """Write registers"""
        if len(register_values) > 1:
            register_values = [int(i) for i in register_values]
            response = await self._async_pymodbus_call(
                self._client.write_registers,
                register_address,
                register_values,
                slave,
            )
            expected_response_type = WriteMultipleRegistersResponse
        else:
            response = await self._async_pymodbus_call(
                self._client.write_register,
                register_address,
                int(register_values[0]),
                slave,
            )
            expected_response_type = WriteSingleRegisterResponse

        if response.isError():
            message = f"Error writing registers. Start: {register_address}; values: {register_values}; slave: {slave}"
            if isinstance(response, BaseException):
                raise ModbusClientFailedException(message, self, response) from response
            raise ModbusClientFailedException(message, self, response)

        # We've seen cases where the remote device gets two requests at the same time and sends the wrong response to the wrong thing.
        # pymodbus doesn't check whether the response type matches the request type
        if not isinstance(response, expected_response_type):
            message = (
                f"Error writing registers. Start: {register_address}; values: {register_values}; slave: {slave}. "
                + f"Received incorrect response type {response}. Please ensure that your adapter is correctly configured to "
                + "allow multiple connections, see the instructions at https://github.com/nathanmarlor/foxess_modbus/wiki"
            )
            raise ModbusClientFailedException(
                message,
                self,
                response,
            )

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

    def __str__(self) -> str:
        return (
            f"{self._config['port']}"
            if self._config_type == SERIAL
            else f"{self._config_type.lower()}://{self._config['host']}:{self._config['port']}"
        )


class ModbusClientFailedException(Exception):
    """Raised when the ModbusClient fails to read/write"""

    def __init__(
        self, message: str, client: ModbusClient, response: ModbusResponse | Exception
    ) -> None:
        super().__init__(f"{message} from {client}: {response}")
        self.message = message
        self.client = client
        self.response = response

    def __str__(self) -> str:
        return f"{self.message} from {self.client}: {self.response}"
