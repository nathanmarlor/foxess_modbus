import logging
import select
import socket
import time
from typing import Any
from typing import cast

from pymodbus.client import ModbusTcpClient
from pymodbus.exceptions import ConnectionException

_LOGGER = logging.getLogger(__name__)


class CustomModbusTcpClient(ModbusTcpClient):
    """Custom ModbusTcpClient subclass with some hacks"""

    def __init__(self, delay_on_connect: int | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._delay_on_connect = delay_on_connect

    def connect(self) -> bool:
        was_connected = self.socket is not None
        if not was_connected:
            _LOGGER.debug("Connecting to %s", self.comm_params)
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
    def recv(self, size: int | None) -> bytes:
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
        self.socket.setblocking(False)

        timeout = self.comm_params.timeout_connect or 0

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

        self.last_frame_end = round(time.time(), 6)
        return b"".join(data)
