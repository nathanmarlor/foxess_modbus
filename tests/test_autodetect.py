from typing import Any
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

from custom_components.foxess_modbus.common.types import InverterModel
from custom_components.foxess_modbus.const import MAX_READ
from custom_components.foxess_modbus.modbus_controller import ModbusController
from custom_components.foxess_modbus.modbus_controller import _decode_model


def _packed(text: str, length: int) -> list[int]:
    data = text.encode("ascii").ljust(length * 2, b"\0")
    return [(data[i] << 8) | data[i + 1] for i in range(0, length * 2, 2)]


def test_decode_model_packed() -> None:
    assert _decode_model(_packed("H1-5.0-E-G2", 15)) == "H1-5.0-E-G2"


def test_decode_model_one_char_per_register() -> None:
    assert _decode_model([ord(c) for c in " H3-10.0-E"] + [32] * 5) == "H3-10.0-E"


def test_decode_model_unpopulated() -> None:
    assert _decode_model([0xFFFF] * 15) == ""


async def test_autodetect_falls_back_to_sunspec() -> None:
    # Register contents taken from a WEG SIW200H S114 W20 (FoxESS H1-US): 30000 onwards is 0xFFFF, but the SunSpec
    # common block at 40000 has the model
    registers: dict[int, int] = dict.fromkeys(range(30000, 30020), 0xFFFF)
    registers.update({40000: 0x5375, 40001: 0x6E53})
    registers.update(dict(zip(range(40020, 40036), _packed("SIW200H S114 W20", 16), strict=True)))

    async def read_registers(start: int, count: int, *_args: Any) -> list[int]:
        return [registers.get(start + i, 0) for i in range(count)]

    client = MagicMock()
    client.read_registers = AsyncMock(side_effect=read_registers)
    client.close = AsyncMock()

    model, full_model = await ModbusController.autodetect(client, 1, {MAX_READ: 8})

    assert model == InverterModel.WEG_SIW200H_US
    assert full_model == "SIW200H S114 W20"
