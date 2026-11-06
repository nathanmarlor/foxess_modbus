"""
Fallback model detection, for inverters which don't expose a model string at holding register 30000.

Each detector is attached to its profile in inverter_profiles.py (InverterModelProfile.model_detector). Autodetect
calls them in turn if 30000 can't be read or decodes to an empty string. A detector returns a model string to match
against the profiles, or None if the inverter doesn't look like one of its models.
"""

import logging
from typing import TYPE_CHECKING
from typing import Awaitable
from typing import Callable

from .common.types import RegisterType

if TYPE_CHECKING:
    from .client.modbus_client import ModbusClient

_LOGGER = logging.getLogger(__name__)

# (client, slave, max_read) -> model string, or None
ModelDetector = Callable[["ModbusClient", int, int], Awaitable[str | None]]

# F G3 "Basic information" block: protocol version (39000) to rated power Pn (39053-39054)
_F_G3_INFO_START_ADDRESS = 39000
_F_G3_INFO_LENGTH = 55


async def _read_holding_block(
    client: "ModbusClient", slave: int, max_read: int, start_address: int, count: int
) -> list[int]:
    values: list[int] = []
    while len(values) < count:
        values.extend(
            await client.read_registers(
                start_address + len(values),
                min(max_read, count - len(values)),
                RegisterType.HOLDING,
                slave,
            )
        )
    return values


def _decode_packed_string(registers: list[int]) -> str:
    chars = [b for reg in registers for b in ((reg >> 8) & 0xFF, reg & 0xFF)]
    return "".join(chr(c) for c in chars if 0x20 <= c < 0x7F).strip()


async def detect_f_g3(client: "ModbusClient", slave: int, max_read: int) -> str | None:
    """
    Identify an F G3 over its built-in WiFi interface, which only answers in 39000+ (no model string at 30000).

    Uses the "Basic information" table (FoxESS Modbus definition V1.05.04.00, table 3-5). On the firmware tested,
    the model name (39002) and model ID (39050) are blank, so there's no field which names the model. Instead we
    require all of the documented identity fields to look like an F G3. If the model name is populated, that is
    returned as-is and matched against the profiles like any other model string.
    """
    # From the F G3 datasheet: all models are dual MPPT, F3000 to F6000
    num_mppts_expected = 2
    min_rated_power_w = 3000
    max_rated_power_w = 6000

    try:
        regs = await _read_holding_block(client, slave, max_read, _F_G3_INFO_START_ADDRESS, _F_G3_INFO_LENGTH)
    except Exception as ex:
        _LOGGER.debug("Autodetect: F G3 probe failed for %s: %s", client, ex)
        return None

    def reg(address: int) -> int:
        return regs[address - _F_G3_INFO_START_ADDRESS]

    def u32(address: int) -> int:
        return (reg(address) << 16) | reg(address + 1)

    def string(address: int) -> str:
        offset = address - _F_G3_INFO_START_ADDRESS
        return _decode_packed_string(regs[offset : offset + 16])

    protocol_version = u32(39000)
    model_name = string(39002)
    serial = string(39018)
    num_mppts = reg(39052)
    rated_power_w = u32(39053)  # kW with gain 1000, i.e. W

    if model_name:
        _LOGGER.info("Autodetect: model name at 39002 is '%s'", model_name)
        return model_name

    looks_like_f_g3 = (
        (protocol_version >> 24) == 0x01
        and len(serial) >= 6
        and num_mppts == num_mppts_expected
        and min_rated_power_w <= rated_power_w <= max_rated_power_w
    )
    if not looks_like_f_g3:
        _LOGGER.debug(
            "Autodetect: not an F G3 (protocol 0x%08X, serial '%s', MPPTs %s, rated power %sW)",
            protocol_version,
            serial,
            num_mppts,
            rated_power_w,
        )
        return None

    full_model = f"F-G3-{rated_power_w / 1000:g}"
    _LOGGER.info(
        "Autodetect: identified F G3 via its WiFi interface (serial %s, protocol 0x%08X, rated power %sW); using '%s'",
        serial,
        protocol_version,
        rated_power_w,
        full_model,
    )
    return full_model
