"""The client used to talk Modbus"""

import asyncio
import logging
import os
from typing import Any
from typing import Callable
from typing import Type
from typing import TypeVar
from typing import cast

import serial
from homeassistant.core import HomeAssistant

from .. import client
from ..common.types import ConnectionType
from ..common.types import RegisterType
from ..const import RTU_OVER_TCP
from ..const import SERIAL
from ..const import TCP
from ..const import UDP
from ..inverter_adapters import InverterAdapter
from ..vendor.pymodbus import ModbusResponse
from ..vendor.pymodbus import ModbusRtuFramer
from ..vendor.pymodbus import ModbusSerialClient
from ..vendor.pymodbus import ModbusSocketFramer
from ..vendor.pymodbus import ModbusUdpClient
from ..vendor.pymodbus import ReadHoldingRegistersResponse
from ..vendor.pymodbus import ReadInputRegistersResponse
from ..vendor.pymodbus import WriteMultipleRegistersResponse
from ..vendor.pymodbus import WriteSingleRegisterResponse
from .custom_modbus_tcp_client import CustomModbusTcpClient

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


_CLIENTS: dict[str, dict[str, Any]] = {
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

serial.protocol_handler_packages.append(client.__name__)


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
            "delay_on_connect": 1 if adapter.connection_type == ConnectionType.LAN else None,
        }

        # If our custom PosixPollSerial hack is supported, use that. This uses poll rather than select, which means we
        # don't break when there are more than 1024 fds. See #457.
        # Only supported on posix, see https://github.com/pyserial/pyserial/blob/7aeea35429d15f3eefed10bbb659674638903e3a/serial/__init__.py#L31
        # This ties into the call to serial.protocol_handler_packages.append above, and means that pyserial will find
        # our protocol_pollserial module, and the Serial class inside, when we use the prefix pollserial://
        if protocol == SERIAL and os.name == "posix":
            config["port"] = f"pollserial://{config['port']}"

        # Some serial devices need a short delay after polling. Also do this for the inverter, just
        # in case it helps.
        self._poll_delay = 30 / 1000 if protocol == SERIAL or adapter.connection_type == ConnectionType.LAN else 0

        self._client = client["client"](**config)

    async def close(self) -> None:
        """Close connection"""
        _LOGGER.debug("Closing connection to modbus on %s", self)
        await self._async_pymodbus_call(self._client.close, auto_connect=False)

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
            for i in range(10):
                _LOGGER.info(f"Some error ({response}), now try {i+1} / 10.. ")
                response = await self._async_pymodbus_call(
                    self._client.read_holding_registers,
                    start_address,
                    num_registers,
                    slave,
                )
                if not response.isError():
                    _LOGGER.info(f"... puh, got it. :-) ")
                    return cast(list[int], response.registers)
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

    async def _async_pymodbus_call(self, call: Callable[..., T], *args: Any, auto_connect: bool = True) -> T:
        """Convert async to sync pymodbus call."""

        def _call() -> T:
            # When using pollserial://, connected calls into serial.serial_for_url, which calls importlib.import_module,
            # which HA doesn't like (see https://github.com/nathanmarlor/foxess_modbus/issues/618).
            # Therefore we need to do this check inside the executor job
            if auto_connect and not self._client.connected:
                self._client.connect()
            # If the connection failed, this call will throw an appropriate error
            return call(*args)

        async with self._lock:
            result = await self._hass.async_add_executor_job(_call)
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
