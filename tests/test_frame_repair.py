"""Tests for the missing-unit-id frame repair (FoxESS H3 Manager >= 1.93 / Master 2.23).

Frames were captured on 2026-09-10 on an H3-10.0-E (Manager 1.95) behind a
Modbus-TCP<->RTU gateway, by sending raw requests on a socket and logging the answers.
"""

from typing import Any

import pytest

from custom_components.foxess_modbus.client.custom_modbus_tcp_client import CustomModbusTcpClient
from custom_components.foxess_modbus.client.frame_repair import MissingUnitIdRepairer
from custom_components.foxess_modbus.vendor.pymodbus import ModbusRtuFramer
from custom_components.foxess_modbus.vendor.pymodbus import ModbusSocketFramer

UNIT = 247

# FC 03, 30016 x 3 -> 223 / 103 / 405
SHORT_READ = bytes.fromhex("0064 0000 0008 03 06 00df 0067 0195")
GOOD_READ = bytes.fromhex("0064 0000 0009 f7 03 06 00df 0067 0195")

# FC 03 exception 02 (illegal address) for 41001..41006
SHORT_EXC = bytes.fromhex("0009 0000 0002 83 02")
GOOD_EXC = bytes.fromhex("0009 0000 0003 f7 83 02")

# FC 06 write echo, 41011 <- 10
SHORT_WRITE = bytes.fromhex("0011 0000 0005 06 a033 000a")
GOOD_WRITE = bytes.fromhex("0011 0000 0006 f7 06 a033 000a")


def _repairer(fc: int) -> MissingUnitIdRepairer:
    r = MissingUnitIdRepairer()
    r.expect(UNIT, fc)
    return r


def test_short_read_gets_unit_id() -> None:
    r = _repairer(3)
    assert r.repair(SHORT_READ) == GOOD_READ
    assert r.repaired == 1 and r.passed == 0


def test_good_read_untouched() -> None:
    r = _repairer(3)
    assert r.repair(GOOD_READ) == GOOD_READ
    assert r.repaired == 0 and r.passed == 1


def test_short_exception_gets_unit_id() -> None:
    r = _repairer(3)
    assert r.repair(SHORT_EXC) == GOOD_EXC


def test_short_write_echo_gets_unit_id() -> None:
    r = _repairer(6)
    assert r.repair(SHORT_WRITE) == GOOD_WRITE


def test_pymodbus_reads_header_first_then_rest() -> None:
    """pymodbus asks for 8 bytes, then the remainder: repair must happen on the first piece
    and must not be applied twice when the buffer grows."""
    r = _repairer(3)
    first = r.repair(SHORT_READ[:8])
    assert first == GOOD_READ[:9]
    assert r.repair(first + SHORT_READ[8:]) == GOOD_READ


def test_frame_shorter_than_header_waits() -> None:
    r = _repairer(3)
    assert r.repair(SHORT_READ[:6]) == SHORT_READ[:6]
    assert r.repaired == 0 and r.passed == 0
    assert r.repair(SHORT_READ) == GOOD_READ


def test_foreign_frame_left_alone() -> None:
    """Another client's answer (unit ok, other fc) or garbage is not touched."""
    r = _repairer(4)
    foreign = bytes.fromhex("0064 0000 0008 03 06 00df 0067 0195")
    assert r.repair(foreign) == foreign
    assert r.repaired == 0 and r.passed == 0


def test_unit_id_equal_to_function_code_is_not_repaired() -> None:
    """A healthy slave 3 answering FC 03 has byte 6 == 3 == unit: must pass through."""
    r = MissingUnitIdRepairer()
    r.expect(3, 3)
    frame = bytes.fromhex("0001 0000 0009 03 03 06 0001 0002 0003")
    assert r.repair(frame) == frame
    assert r.passed == 1


def test_rearm_inspects_next_frame_again() -> None:
    r = _repairer(3)
    assert r.repair(SHORT_READ) == GOOD_READ
    assert r.repair(SHORT_READ) == SHORT_READ  # already done for this request
    r.rearm()
    assert r.repair(SHORT_READ) == GOOD_READ
    assert r.repaired == 2


def test_no_expectation_no_repair() -> None:
    r = MissingUnitIdRepairer()
    assert r.repair(SHORT_READ) == SHORT_READ


def test_wrong_transaction_id_not_repaired() -> None:
    r = MissingUnitIdRepairer()
    r.expect(UNIT, 3, transaction_id=0x0065, register_count=3)
    assert r.repair(SHORT_READ) == SHORT_READ
    assert r.repaired == 0


def test_nonzero_protocol_id_not_repaired() -> None:
    r = _repairer(3)
    frame = bytes.fromhex("0064 0001 0008 03 06 00df 0067 0195")
    assert r.repair(frame) == frame
    assert r.repaired == 0


def test_byte_count_must_match_register_count() -> None:
    r = MissingUnitIdRepairer()
    r.expect(UNIT, 3, transaction_id=0x0064, register_count=4)
    assert r.repair(SHORT_READ) == SHORT_READ
    r = MissingUnitIdRepairer()
    r.expect(UNIT, 3, transaction_id=0x0064, register_count=3)
    assert r.repair(SHORT_READ) == GOOD_READ


def test_byte_count_must_match_length_field() -> None:
    r = _repairer(3)
    frame = bytes.fromhex("0064 0000 0009 03 06 00df 0067 0195 00")
    assert r.repair(frame) == frame
    assert r.repaired == 0


def test_max_length_field_does_not_overflow() -> None:
    r = _repairer(6)
    frame = bytes.fromhex("0064 0000 ffff 06 a033 000a")
    assert r.repair(frame) == frame


def test_expectation_from_request_packet() -> None:
    """send() hands over the framed MBAP request: unit, fc, tid and count come from it."""
    r = MissingUnitIdRepairer()
    r.expect_packet(bytes.fromhex("0064 0000 0006 f7 03 7540 0003"))  # 30016 x 3
    assert r.repair(SHORT_READ) == GOOD_READ
    r.expect_packet(bytes.fromhex("0065 0000 0006 f7 03 7540 0003"))  # other tid
    assert r.repair(SHORT_READ) == SHORT_READ


# Client level: the repair must only run for Modbus TCP (socket framer)


class _FakeSocket:
    def __init__(self) -> None:
        self.sent: list[bytes] = []

    def send(self, data: bytes) -> int:
        self.sent.append(data)
        return len(data)


class _Wire:
    """Stands in for CustomModbusTcpClient._recv_raw: serves the captured answer."""

    def __init__(self, answer: bytes) -> None:
        self.pending = answer
        self.sizes: list[int | None] = []

    def __call__(self, size: int | None) -> bytes:
        self.sizes.append(size)
        n = len(self.pending) if size is None else size
        data, self.pending = self.pending[:n], self.pending[n:]
        return data


def _client(framer: Any, answer: bytes, request: bytes, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, _Wire]:
    client = CustomModbusTcpClient(delay_on_connect=None, host="127.0.0.1", port=502, framer=framer)
    wire = _Wire(answer)
    monkeypatch.setattr(client, "_recv_raw", wire)
    monkeypatch.setattr(client, "socket", _FakeSocket())
    client.send(request)
    return client, wire


def test_client_socket_framer_repairs_in_two_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    request = bytes.fromhex("0064 0000 0006 f7 03 7540 0003")  # 30016 x 3
    client, _ = _client(ModbusSocketFramer, SHORT_READ, request, monkeypatch)
    assert client.repair_enabled
    header = client.recv(8)
    assert header == GOOD_READ[:8]
    assert header + client.recv(len(GOOD_READ) - 8) == GOOD_READ


@pytest.mark.parametrize(
    "frame",
    [
        # RTU answer to "unit 0xf7, FC03, 4 registers" whose 7th byte (a data byte) is 0x03
        bytes.fromhex("f7 03 08 0000 0000 0300 0000 aaaa"),
        # ... and with 0xff 0xff before it, which overflowed the length field
        bytes.fromhex("f7 03 08 0000 ffff 0300 0000 aaaa"),
        # 7th byte equals the exception form 0x83
        bytes.fromhex("f7 03 08 0000 0000 8300 0000 aaaa"),
    ],
)
def test_client_rtu_over_tcp_is_never_touched(frame: bytes, monkeypatch: pytest.MonkeyPatch) -> None:
    request = bytes.fromhex("f7 03 7540 0004 aaaa")
    client, _ = _client(ModbusRtuFramer, frame, request, monkeypatch)
    assert not client.repair_enabled
    data = client.recv(3)
    data += client.recv(len(frame) - 3)
    assert data == frame


def test_client_recv_zero_is_not_unbounded(monkeypatch: pytest.MonkeyPatch) -> None:
    request = bytes.fromhex("0064 0000 0006 f7 03 7540 0003")
    client, wire = _client(ModbusSocketFramer, GOOD_READ, request, monkeypatch)
    assert client.recv(0) == b""
    assert None not in wire.sizes
