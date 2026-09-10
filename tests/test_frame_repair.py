"""Tests for the missing-unit-id frame repair (FoxESS H3 fw 2.23 / Manager 1.95).

Frames are the ones captured on 2026-09-10 with tools/probe_frames.py, see
docs/ANALYSIS-2026-09-10-fw223.md.
"""

from custom_components.foxess_modbus.client.frame_repair import MissingUnitIdRepairer

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
