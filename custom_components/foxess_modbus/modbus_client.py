import logging

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ConnectionException
from pymodbus.exceptions import ModbusIOException

_LOGGER = logging.getLogger(__name__)
_SLAVE = 247


class ModbusClient:
    """Modbus"""

    def __init__(self, host, port=502):
        """Init"""
        self._host = host
        self._port = port
        self._client = ModbusTcpClient(self._host, self._port)

    def _connect(self):
        """Connect to device"""
        if not self._client.connect():
            raise ConnectionException(
                f"Error connecting to device: ({self._host}:{self._port})"
            )

    def read_registers(self, start_address, num_registers, holding):
        """Read registers"""
        if not self._client.is_socket_open():
            _LOGGER.info(f"Connecting to modbus: ({self._host}:{self._port})")
            self._connect()

        _LOGGER.debug(f"Reading register: ({start_address}, {num_registers})")
        if holding:
            response = self._client.read_holding_registers(
                start_address, num_registers, _SLAVE
            )
        else:
            response = self._client.read_input_registers(
                start_address, num_registers, _SLAVE
            )
        if response.isError():
            raise ModbusIOException(f"Error reading registers: {response}")

        # convert to signed integers
        regs = [
            reading if reading < 32768 else reading - 65536
            for reading in response.registers
        ]
        return regs

    def write_registers(self, register_address, register_values):
        """Write registers"""
        if not self._client.is_socket_open():
            _LOGGER.info(f"Connecting to modbus: ({self._host}:{self._port})")
            self._connect()

        _LOGGER.debug(f"Writing register: ({register_address}, {register_values})")

        if len(register_values) > 1:
            response = self._client.write_registers(
                register_address, register_values, _SLAVE
            )
        else:
            response = self._client.write_register(
                register_address, int(register_values[0]), _SLAVE
            )
        if response.isError():
            raise ModbusIOException(f"Error writing holding register: {response}")
        return True
