"""The client used to talk Modbus"""
import asyncio
import logging
import select
import socket
import time
from typing import Any
from typing import Callable
from typing import Type
from typing import TypeVar
from typing import cast

from homeassistant.core import HomeAssistant
from pymodbus.client import ModbusSerialClient
from pymodbus.client import ModbusTcpClient
from pymodbus.client import ModbusUdpClient
from pymodbus.exceptions import ConnectionException
from pymodbus.pdu import ModbusResponse
from pymodbus.register_read_message import ReadHoldingRegistersResponse
from pymodbus.register_read_message import ReadInputRegistersResponse
from pymodbus.register_write_message import WriteMultipleRegistersResponse
from pymodbus.register_write_message import WriteSingleRegisterResponse
from pymodbus.transaction import ModbusRtuFramer
from pymodbus.transaction import ModbusSocketFramer

from .common.register_type import RegisterType
from .const import LAN
from .const import RTU_OVER_TCP
from .const import SERIAL
from .const import TCP
from .const import UDP
from .inverter_adapters import InverterAdapter

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class CustomModbusTcpClient(ModbusTcpClient):
    """Custom ModbusTcpClient subclass with some hacks"""

    def __init__(self, delay_on_connect: int | None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._delay_on_connect = delay_on_connect

    def connect(self) -> bool:
        was_connected = self.socket is not None
        if not was_connected:
            _LOGGER.debug("Connecting to %s", self.params)
        is_connected = cast(bool, super().connect())
        # pymodbus doesn't disable Nagle's algorithm. This slows down reads quite substantially as the
        # TCP stack waits to see if we're going to send anything else. Disable it ourselves.
        if not was_connected and is_connected:
            assert self.socket is not None
            self.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, True)
            if self._delay_on_connect is not None:
                time.sleep(self._delay_on_connect)
        return is_connected

    # Replacement of ModbusTcpClient to use poll rather than select, see
    # https://github.com/nathanmarlor/foxess_modbus/issues/275
    def recv(self, size: int) -> bytes:
        """Read data from the underlying descriptor."""
        super(ModbusTcpClient, self).recv(size)
        if not self.socket:
            raise ConnectionException(str(self))

        # socket.recv(size) waits until it gets some data from the host but
        # not necessarily the entire response that can be fragmented in
        # many packets.
        # To avoid split responses to be recognized as invalid
        # messages and to be discarded, loops socket.recv until full data
        # is received or timeout is expired.
        # If timeout expires returns the read data, also if its length is
        # less than the expected size.
        self.socket.setblocking(0)

        timeout = self.params.timeout

        # If size isn't specified read up to 4096 bytes at a time.
        if size is None:
            recv_size = 4096
        else:
            recv_size = size

        data: list[bytes] = []
        data_length = 0
        time_ = time.time()
        end = time_ + timeout
        poll = select.poll()
        # We don't need to call poll.unregister, since we're deallocing the poll. register just adds the socket to a
        # dict owned by the poll object (the underlying syscall has no concept of register/unregister, and just takes an
        # array of fds to poll). If we hit a disconnection the socket.fileno() becomes -1 anyway, so unregistering will
        # fail
        poll.register(self.socket, select.POLLIN)
        while recv_size > 0:
            poll_res = poll.poll(end - time_)
            # We expect a single-element list if this succeeds, or an empty list if it timed out
            if len(poll_res) > 0:
                if (recv_data := self.socket.recv(recv_size)) == b"":
                    return self._handle_abrupt_socket_close(  # type: ignore[no-any-return]
                        size, data, time.time() - time_
                    )
                data.append(recv_data)
                data_length += len(recv_data)
            time_ = time.time()

            # If size isn't specified continue to read until timeout expires.
            if size:
                recv_size = size - data_length

            # Timeout is reduced also if some data has been received in order
            # to avoid infinite loops when there isn't an expected response
            # size and the slave sends noisy data continuously.
            if time_ > end:
                break

        return b"".join(data)

    # Replacement of ModbusTcpClient to use poll rather than select, see
    # https://github.com/nathanmarlor/foxess_modbus/issues/275
    def _check_read_buffer(self) -> bytes | None:
        """Check read buffer."""
        time_ = time.time()
        end = time_ + self.params.timeout
        data = None

        assert self.socket is not None
        poll = select.poll()
        poll.register(self.socket, select.POLLIN)
        poll_res = poll.poll(end - time_)
        if len(poll_res) > 0:
            data = self.socket.recv(1024)
        return data


_CLIENTS = {
    SERIAL: {
        "client": ModbusSerialClient,
        "framer": ModbusRtuFramer,
    },
    TCP: {
        "client": CustomModbusTcpClient,
        "framer": ModbusSocketFramer,
    },
    UDP: {
        "client": ModbusUdpClient,
        "framer": ModbusSocketFramer,
    },
    RTU_OVER_TCP: {
        "client": CustomModbusTcpClient,
        "framer": ModbusRtuFramer,
    },
}


class ModbusClient:
    """Modbus"""

    def __init__(self, hass: HomeAssistant, protocol: str, adapter: InverterAdapter, config: dict[str, Any]) -> None:
        """Init"""
        self._hass = hass
        self._config = config
        self._lock = asyncio.Lock()
        self._protocol = protocol

        client = _CLIENTS[protocol]

        # Delaying for a second after establishing a connection seems to help the inverter stability,
        # see https://github.com/nathanmarlor/foxess_modbus/discussions/132
        config = {
            **config,
            "framer": client["framer"],
            "delay_on_connect": 1 if adapter.connection_type == LAN else None,
        }

        # Some serial devices need a short delay after polling. Also do this for the inverter, just
        # in case it helps.
        self._poll_delay = 30 / 1000 if protocol == SERIAL or adapter.connection_type == LAN else 0

        self._client = client["client"](**config)

    async def close(self) -> None:
        """Close connection"""
        _LOGGER.debug("Closing connection to modbus on %s", self)
        await self._async_pymodbus_call(self._client.close)

    async def read_registers(
        self,
        start_address: int,
        num_registers: int,
        register_type: RegisterType,
        slave: int,
    ) -> list[int]:
        """Read registers"""
        expected_response_type: Type[Any]
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
            raise AssertionError()

        if response.isError():
            message = (
                f"Error reading registers. Type: {register_type}; start: {start_address}; count: {num_registers}; "
                f"slave: {slave}"
            )
            if isinstance(response, Exception):
                raise ModbusClientFailedError(message, self, response) from response
            raise ModbusClientFailedError(message, self, response)

        # We've seen cases where the remote device gets two requests at the same time and sends the wrong response to
        # the wrong thing. pymodbus doesn't check whether the response type matches the request type
        if not isinstance(response, expected_response_type):
            message = (
                f"Error reading registers. Type: {register_type}; start: {start_address}; count: {num_registers}; "
                f"slave: {slave}. Received incorrect response type {response}. Please ensure that your adapter is "
                "correctly configured to allow multiple connections, see the instructions at "
                "https://github.com/nathanmarlor/foxess_modbus/wiki"
            )
            # ModbusController only logs this as debug. Make this a bit clearer so people spot and fix this
            _LOGGER.warning(message)
            raise ModbusClientFailedError(
                message,
                self,
                response,
            )

        return cast(list[int], response.registers)

    async def write_registers(self, register_address: int, register_values: list[int], slave: int) -> None:
        """Write registers"""
        expected_response_type: Type[Any]
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
            if isinstance(response, Exception):
                raise ModbusClientFailedError(message, self, response) from response
            raise ModbusClientFailedError(message, self, response)

        # We've seen cases where the remote device gets two requests at the same time and sends the wrong response to
        # the wrong thing. pymodbus doesn't check whether the response type matches the request type
        if not isinstance(response, expected_response_type):
            message = (
                f"Error writing registers. Start: {register_address}; values: {register_values}; slave: {slave}. "
                f"Received incorrect response type {response}. Please ensure that your adapter is correctly "
                "configured to allow multiple connections, see the instructions at "
                "https://github.com/nathanmarlor/foxess_modbus/wiki"
            )
            raise ModbusClientFailedError(
                message,
                self,
                response,
            )

    async def _async_pymodbus_call(self, call: Callable[..., T], *args: Any) -> T:
        """Convert async to sync pymodbus call."""
        async with self._lock:
            result = await self._hass.async_add_executor_job(call, *args)
            # This seems to be required for serial devices, otherwise subsequent reads fail
            # The HA modbus integration does the same
            if self._poll_delay > 0:
                await asyncio.sleep(self._poll_delay)
            return result

    def __str__(self) -> str:
        if self._protocol == SERIAL:
            return f"{self._config['port']}"
        return f"{self._protocol}://{self._config['host']}:{self._config['port']}"


class ModbusClientFailedError(Exception):
    """Raised when the ModbusClient fails to read/write"""

    def __init__(self, message: str, client: ModbusClient, response: ModbusResponse | Exception) -> None:
        super().__init__(f"{message} from {client}: {response}")
        self.message = message
        self.client = client
        self.response = response

    def __str__(self) -> str:
        return f"{self.message} from {self.client}: {self.response}"
