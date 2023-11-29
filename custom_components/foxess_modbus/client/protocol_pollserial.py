"""
Custom protocol handler for pyserial, which uses poll but doesn't have
https://github.com/pyserial/pyserial/issues/617
"""

import os
import select
from enum import Enum

import serial
from serial import serialposix
from serial.serialutil import PortNotOpenError
from serial.serialutil import SerialException
from serial.serialutil import Timeout


class _PollResult(Enum):
    TIMEOUT = 0
    ABORT = 1
    DATA = 2


class Serial(serialposix.Serial):
    """
    From https://github.com/pyserial/pyserial/blob/7aeea35429d15f3eefed10bbb659674638903e3a/serial/serialposix.py,
    but with https://github.com/pyserial/pyserial/pull/618 applied
    """

    @serial.Serial.port.setter  # type: ignore
    def port(self, value: str) -> None:
        if value is not None:
            serial.Serial.port.__set__(self, value.removeprefix("pollserial://"))

    def read(self, size: int = 1) -> bytes:
        """\
        Read size bytes from the serial port. If a timeout is set it may
        return less characters as requested. With no timeout it will block
        until the requested number of bytes is read.
        """
        if not self.is_open:
            raise PortNotOpenError()
        read = bytearray()
        timeout = Timeout(self._timeout)
        poll = select.poll()
        poll.register(self.fd, select.POLLIN | select.POLLERR | select.POLLHUP | select.POLLNVAL)
        poll.register(self.pipe_abort_read_r, select.POLLIN | select.POLLERR | select.POLLHUP | select.POLLNVAL)
        if size > 0:
            while len(read) < size:
                # wait until device becomes ready to read (or something fails)
                result = _PollResult.TIMEOUT  # In case poll returns an empty list
                for fd, event in poll.poll(None if timeout.is_infinite else (timeout.time_left() * 1000)):
                    if fd == self.pipe_abort_read_r:
                        os.read(self.pipe_abort_read_r, 1000)
                        result = _PollResult.ABORT
                        break
                    if event & (select.POLLERR | select.POLLHUP | select.POLLNVAL):
                        raise SerialException("device reports error (poll)")
                    result = _PollResult.DATA

                if result == _PollResult.DATA:
                    buf = os.read(self.fd, size - len(read))
                    read.extend(buf)
                if (
                    result == _PollResult.TIMEOUT
                    or result == _PollResult.ABORT
                    or timeout.expired()
                    or (self._inter_byte_timeout is not None and self._inter_byte_timeout > 0)
                    and not buf
                ):
                    break  # early abort on timeout
        return bytes(read)


# This needs to have a very particular name, as it's registered by string in modbus_client
assert Serial.__module__ == "custom_components.foxess_modbus.client.protocol_pollserial"
assert Serial.__name__ == "Serial"
