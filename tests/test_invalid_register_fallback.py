"""Reads which hit an invalid register (#1217, #1218)."""

import logging
from collections.abc import AsyncIterator
from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import async_fire_time_changed  # type: ignore[import-untyped]

from custom_components.foxess_modbus.client.modbus_client import ModbusClientFailedError
from custom_components.foxess_modbus.common.entity_controller import ModbusControllerEntity
from custom_components.foxess_modbus.common.types import ConnectionType
from custom_components.foxess_modbus.common.types import InverterModel
from custom_components.foxess_modbus.const import ENTITY_ID_PREFIX
from custom_components.foxess_modbus.const import FRIENDLY_NAME
from custom_components.foxess_modbus.const import INVERTER_BASE
from custom_components.foxess_modbus.const import INVERTER_CONN
from custom_components.foxess_modbus.const import INVERTER_MODEL
from custom_components.foxess_modbus.const import UNIQUE_ID_PREFIX
from custom_components.foxess_modbus.inverter_profiles import inverter_connection_type_profile_from_config
from custom_components.foxess_modbus.modbus_controller import ModbusController
from custom_components.foxess_modbus.vendor.pymodbus import ExceptionResponse
from custom_components.foxess_modbus.vendor.pymodbus import ModbusExceptions

POLL_RATE = 10

# A 32-bit value, a gap the inverter refuses (no entity uses it), and a single register after it
VALUE_32 = [39249, 39248]
UNUSED_INVALID = 39251
SINGLE = 39253


class _Entity(ModbusControllerEntity):
    def __init__(self, addresses: list[int]) -> None:
        self._addresses = addresses

    @property
    def addresses(self) -> list[int]:
        return self._addresses

    def update_callback(self, changed_addresses: set[int]) -> None:
        pass

    def is_connected_changed_callback(self) -> None:
        pass


class _Inverter:
    """Answers reads from `registers`, and refuses any read which touches an `invalid` register"""

    def __init__(self, registers: dict[int, int], invalid: set[int]) -> None:
        self.registers = registers
        self.invalid = invalid
        self.reads: list[tuple[int, int]] = []

    async def read_registers(self, start: int, count: int, *_args: Any) -> list[int]:
        self.reads.append((start, count))
        if any(address in self.invalid for address in range(start, start + count)):
            raise ModbusClientFailedError(
                "Error reading registers", MagicMock(), ExceptionResponse(3, ModbusExceptions.IllegalAddress)
            )
        return [self.registers.get(address, 0) for address in range(start, start + count)]

    def reads_within(self, first: int, last: int) -> list[tuple[int, int]]:
        return [(start, count) for start, count in self.reads if first <= start <= last]


@pytest.fixture
def inverter() -> _Inverter:
    return _Inverter({39248: 0x0001, 39249: 0xFFFF, SINGLE: 7}, invalid={UNUSED_INVALID})


@pytest.fixture
async def controller(hass: HomeAssistant, inverter: _Inverter) -> AsyncIterator[ModbusController]:
    client = MagicMock()
    client.read_registers = AsyncMock(side_effect=inverter.read_registers)
    details = {
        INVERTER_BASE: InverterModel.H3,
        INVERTER_CONN: ConnectionType.AUX,
        INVERTER_MODEL: "H3-5.0-E",
        FRIENDLY_NAME: "",
        ENTITY_ID_PREFIX: "",
        UNIQUE_ID_PREFIX: "",
    }
    controller = ModbusController(
        hass, client, inverter_connection_type_profile_from_config(details), details, 247, POLL_RATE, 50
    )
    controller.register_modbus_entity(_Entity(VALUE_32))
    controller.register_modbus_entity(_Entity([SINGLE]))
    yield controller
    controller.unload()


async def _poll(hass: HomeAssistant, polls: int = 1) -> None:
    for i in range(1, polls + 1):
        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=POLL_RATE * i))
        await hass.async_block_till_done()


async def test_registers_of_a_value_come_from_one_read(
    hass: HomeAssistant, controller: ModbusController, inverter: _Inverter
) -> None:
    await _poll(hass)

    assert inverter.reads_within(39248, SINGLE) == [
        (39248, 6),  # refused because of 39251
        (39248, 2),  # the 32-bit value, in one read
        (39250, 1),
        (UNUSED_INVALID, 1),
        (39252, 1),
        (SINGLE, 1),
    ]
    assert controller.read(VALUE_32, signed=True) == 0x0001FFFF
    assert controller.read(SINGLE, signed=False) == 7


async def test_value_with_an_invalid_register_is_read_register_by_register(
    hass: HomeAssistant, controller: ModbusController, inverter: _Inverter
) -> None:
    inverter.invalid.add(39249)

    await _poll(hass)

    assert inverter.reads_within(39248, 39249) == [(39248, 6), (39248, 2), (39248, 1), (39249, 1)]
    assert controller.read(VALUE_32, signed=True) is None
    assert controller.read(SINGLE, signed=False) == 7


async def test_invalid_register_is_not_read_again(
    hass: HomeAssistant, controller: ModbusController, inverter: _Inverter
) -> None:
    await _poll(hass)
    inverter.reads.clear()

    await _poll(hass, polls=2)

    # Each poll reads around the invalid register, in reads which don't fail
    assert inverter.reads_within(39248, SINGLE) == [(39248, 2), (SINGLE, 1)] * 2
    assert controller.read(VALUE_32, signed=True) == 0x0001FFFF


@pytest.mark.usefixtures("controller")
async def test_invalid_register_is_logged_once(
    hass: HomeAssistant, inverter: _Inverter, caplog: pytest.LogCaptureFixture
) -> None:
    inverter.invalid.add(SINGLE)

    with caplog.at_level(logging.WARNING):
        await _poll(hass, polls=3)

    warnings = [r.getMessage() for r in caplog.records if r.levelno >= logging.WARNING]
    # SINGLE is used by an entity, which is now unavailable; UNUSED_INVALID only filled a gap in a larger read
    invalid = [w for w in warnings if "is invalid" in w]
    assert len(invalid) == 1
    assert invalid[0].endswith(f"register {SINGLE} is invalid")
