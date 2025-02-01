import sys
from pathlib import Path

# Update python.analysis.extraPaths in .vscode/settings.json if you change this.
# If changed, make sure subclasses in modbus_client are still valid!
sys.path.insert(0, str((Path(__file__).parent / "pymodbus-3.6.9").absolute()))

from pymodbus.client import ModbusSerialClient
from pymodbus.client import ModbusTcpClient
from pymodbus.client import ModbusUdpClient
from pymodbus.exceptions import ConnectionException
from pymodbus.exceptions import ModbusIOException
from pymodbus.register_read_message import ReadHoldingRegistersResponse
from pymodbus.register_read_message import ReadInputRegistersResponse
from pymodbus.register_write_message import WriteMultipleRegistersResponse
from pymodbus.register_write_message import WriteSingleRegisterResponse
from pymodbus.pdu import ModbusResponse
from pymodbus.transaction import ModbusRtuFramer
from pymodbus.transaction import ModbusSocketFramer

sys.path.pop(0)

__all__ = [
    "ModbusSerialClient",
    "ModbusTcpClient",
    "ModbusUdpClient",
    "ConnectionException",
    "ModbusIOException",
    "ModbusPDU",
    "ReadHoldingRegistersResponse",
    "ReadInputRegistersResponse",
    "WriteMultipleRegistersResponse",
    "WriteSingleRegisterResponse",
    "ModbusResponse",
    "ModbusRtuFramer",
    "ModbusSocketFramer",
]
