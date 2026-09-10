"""Repair Modbus-TCP frames whose RTU unit-id byte is missing.

FoxESS H3 firmware Master 2.23 / Manager 1.95 (2026-09) drops the first byte (slave
address) of most RTU responses. A Modbus-TCP<->RTU gateway forwards what it got, so
the MBAP frame reaching us is one byte short:

    good:  tid pid 0009 f7 03 06 <6 data bytes>
    short: tid pid 0008    03 06 <6 data bytes>

pymodbus reads byte 6 as the unit id and byte 7 as the function code, so the short
frame decodes as unit 3 / function 6 and is rejected. This module re-inserts the
unit id when the frame is provably the answer to the request we just sent.

Stdlib only, no Home Assistant imports, so it is unit-testable on its own.
"""

import logging

_LOGGER = logging.getLogger(__name__)

_MBAP_LEN = 6  # tid(2) pid(2) length(2); byte 6 is the unit id


class MissingUnitIdRepairer:
    """Stateful repairer: knows which (unit, function code) answer is pending."""

    def __init__(self) -> None:
        self._unit: int | None = None
        self._function_code: int | None = None
        self._done = False
        self.repaired = 0
        self.passed = 0

    def expect(self, unit: int, function_code: int) -> None:
        """Called when a request is sent: the next frame should answer it."""
        self._unit = unit
        self._function_code = function_code & 0x7F
        self._done = False

    def rearm(self) -> None:
        """Called when the pending request is (re)sent: inspect the next frame again."""
        self._done = False

    def repair(self, buffer: bytes) -> bytes:
        """Inspect a buffer that starts at an MBAP frame boundary and fix it if needed.

        Idempotent per request: once a frame was inspected (repaired or accepted) the
        buffer is returned unchanged until :meth:`expect` is called again.
        """
        if self._done or self._unit is None or self._function_code is None:
            return buffer
        if len(buffer) <= _MBAP_LEN:
            return buffer  # nothing to decide yet
        byte6 = buffer[_MBAP_LEN]
        if byte6 == self._unit:
            self._done = True
            self.passed += 1
            return buffer
        if byte6 in (self._function_code, self._function_code | 0x80):
            length = int.from_bytes(buffer[4:6], "big") + 1
            repaired = buffer[:4] + length.to_bytes(2, "big") + bytes([self._unit]) + buffer[_MBAP_LEN:]
            self._done = True
            self.repaired += 1
            _LOGGER.debug(
                "Re-inserted missing unit id %d (fc 0x%02x); repaired=%d passed=%d",
                self._unit,
                self._function_code,
                self.repaired,
                self.passed,
            )
            return repaired
        # Neither ours nor a recognisable short frame (e.g. another client's answer):
        # leave it to pymodbus, which will reject it as before.
        self._done = True
        return buffer
