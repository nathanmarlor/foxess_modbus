import sys
from pathlib import Path
from contextlib import contextmanager
from typing import Iterator


@contextmanager
def _load(path: Path, name: str) -> Iterator[None]:
    def _remove_modules(name: str) -> None:
        old_modules = {n: m for n, m in sys.modules.items(
        ) if n == name or n.startswith(name + ".")}
        for n in old_modules:
            del sys.modules[n]
        return old_modules

    # Save and remove any existing loaded modules
    old_modules = _remove_modules(name)

    # Load the vendored module
    sys.path.insert(0, str(path.absolute()))
    yield ()
    sys.path.pop(0)

    # Remove anything we've added to the global modules
    _remove_modules(name)
    # Re-add any existing loaded modules
    sys.modules.update(old_modules)


with _load(Path(__file__).parent / "pymodbus-3.6.9", "pymodbus"):
    from pymodbus.client import ModbusSerialClient
    from pymodbus.client import ModbusTcpClient
    from pymodbus.client import ModbusUdpClient
    from pymodbus.exceptions import ConnectionException
    from pymodbus.exceptions import ModbusIOException
    from pymodbus.register_read_message import ReadHoldingRegistersResponse
    from pymodbus.register_read_message import ReadInputRegistersResponse
    from pymodbus.register_write_message import WriteMultipleRegistersResponse
    from pymodbus.register_write_message import WriteSingleRegisterResponse
    from pymodbus.pdu import ModbusExceptions
    from pymodbus.pdu import ModbusResponse
    from pymodbus.pdu import ExceptionResponse
    from pymodbus.transaction import ModbusRtuFramer
    from pymodbus.transaction import ModbusSocketFramer


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
    "ModbusExceptions",
    "ModbusResponse",
    "ExceptionResponse",
    "ModbusRtuFramer",
    "ModbusSocketFramer",
]
