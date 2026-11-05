"""Recorded PQ1 scheduler evidence and shared reader failure boundaries."""

import asyncio
from dataclasses import replace
from itertools import chain
from typing import cast
from unittest.mock import AsyncMock
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant

from custom_components.foxess_modbus.common.entity_controller import EntityController
from custom_components.foxess_modbus.common.types import Inv
from custom_components.foxess_modbus.common.types import RegisterType
from custom_components.foxess_modbus.const import ENTITY_ID_PREFIX
from custom_components.foxess_modbus.const import FRIENDLY_NAME
from custom_components.foxess_modbus.entities.modbus_schedule_sensor import ModbusScheduleSensor
from custom_components.foxess_modbus.entities.schedule_descriptions import SCHEDULE_DESCRIPTION
from custom_components.foxess_modbus.entities.schedule_descriptions import ModbusScheduleFactory
from custom_components.foxess_modbus.entities.schedule_descriptions import ScheduleAddressSpec
from custom_components.foxess_modbus.inverter_profiles import INVERTER_PROFILES
from custom_components.foxess_modbus.schedule_reader_manager import ScheduleReaderManager

# App-generated capture: disabled 18:00 period precedes an enabled 23:30
# period; Remaining Time moved to record five after an 08:00 period was added.
RECORDS = [
    [1, 0, 1310, 6, 25610, 45, 8000, 0, 0, 1],
    [1, 2048, 2560, 2, 25610, 40, 12000, 0, 1, 1],
    [0, 4608, 4864, 7, 25610, 40, 12000, 0, 0, 1],
    [1, 5918, 5947, 6, 25610, 45, 8000, 0, 0, 1],
    [1, 0, 5947, 1, 25610, 10, 0, 0, 0, 1],
]


@pytest.fixture
def reader(hass: HomeAssistant) -> ScheduleReaderManager:
    controller = MagicMock(spec=EntityController)
    controller.hass = hass
    controller.is_connected = True
    controller.inverter_details = {ENTITY_ID_PREFIX: "pq1", FRIENDLY_NAME: "PQ1"}
    words = {48010 + index: word for index, word in enumerate(chain.from_iterable(RECORDS))}

    async def read(address: int, count: int, register_type: RegisterType) -> list[int]:
        assert register_type == RegisterType.HOLDING
        return [words[address + offset] for offset in range(count)]

    controller.read_registers = AsyncMock(side_effect=read)
    config = SCHEDULE_DESCRIPTION.create_if_supported(Inv.PQ1, RegisterType.HOLDING)
    assert config is not None
    manager = ScheduleReaderManager(controller, config, 8)
    controller.schedule_reader_manager = manager
    manager.add_listener(MagicMock())
    return manager


def controller_mock(reader: ScheduleReaderManager) -> MagicMock:
    return cast(MagicMock, reader._controller)  # noqa: SLF001


async def scan(reader: ScheduleReaderManager) -> None:
    await reader.poll_complete_callback()
    task = reader._task  # noqa: SLF001
    if task is not None:
        await task
        await asyncio.sleep(0)


async def test_recorded_scan_includes_disabled_and_stops_at_remaining_time(reader: ScheduleReaderManager) -> None:
    await scan(reader)
    snapshot = reader.snapshot
    assert snapshot is not None
    assert len(snapshot.entries) == 4
    assert snapshot.entries[0]["start"] == "00:00"
    assert snapshot.entries[0]["end"] == "05:30"
    assert snapshot.entries[0]["min_soc"] == 10
    assert snapshot.entries[0]["max_soc"] == 100
    assert snapshot.entries[0]["mode_soc"] == 45
    assert snapshot.entries[0]["power_w"] == 8000
    assert snapshot.entries[2]["enabled"] is False
    assert snapshot.entries[3]["start"] == "23:30"
    assert snapshot.remaining_time["register_address"] == 48050
    assert snapshot.remaining_time["work_mode"] == "Self Use"
    assert snapshot.remaining_time["raw_registers"] == RECORDS[4]
    calls = controller_mock(reader).read_registers.await_args_list
    assert len(calls) == 10
    assert all(call.args[1] <= 8 for call in calls)
    assert max(call.args[0] + call.args[1] - 1 for call in calls) == 48059
    controller_mock(reader).write_register.assert_not_called()
    controller_mock(reader).write_registers.assert_not_called()
    await scan(reader)
    assert len(controller_mock(reader).read_registers.await_args_list) == 10


async def test_remaining_time_can_be_first_record(reader: ScheduleReaderManager) -> None:
    controller_mock(reader).read_registers.side_effect = None
    controller_mock(reader).read_registers.side_effect = [RECORDS[-1][:8], RECORDS[-1][8:]]
    await scan(reader)
    assert reader.snapshot is not None
    assert reader.snapshot.entries == []
    assert reader.snapshot.remaining_time["register_address"] == 48010


@pytest.mark.parametrize("index, value", [(0, 2), (1, 60), (2, 6144), (4, 256101), (4, 12900), (5, 101), (6, -1)])
async def test_invalid_records_are_not_published(reader: ScheduleReaderManager, index: int, value: int) -> None:
    words = RECORDS[0].copy()
    words[index] = value
    controller_mock(reader).read_registers.side_effect = [words[:8], words[8:]]
    await scan(reader)
    assert reader.snapshot is None
    assert reader.error is not None


async def test_unknown_mode_and_unresolved_fields_preserved(reader: ScheduleReaderManager) -> None:
    words = RECORDS[-1].copy()
    words[3] = 99
    words[7:] = [42, 32768, 65535]
    controller_mock(reader).read_registers.side_effect = [words[:8], words[8:]]
    await scan(reader)
    assert reader.snapshot is not None
    assert reader.snapshot.remaining_time["work_mode"] == "Unknown (99)"
    assert reader.snapshot.remaining_time["raw_registers"] == words


@pytest.mark.parametrize("response", [[], [1], RuntimeError("Modbus read failed")])
async def test_failed_reads_keep_last_snapshot_but_mark_unavailable(
    reader: ScheduleReaderManager, response: list[int] | Exception
) -> None:
    await scan(reader)
    original = reader.snapshot
    reader._next_scan_at = 0  # noqa: SLF001
    controller_mock(reader).read_registers.side_effect = [response]
    await scan(reader)
    assert reader.snapshot is original
    assert reader.error is not None
    reader._next_scan_at = 0  # noqa: SLF001
    controller_mock(reader).read_registers.side_effect = [RECORDS[-1][:8], RECORDS[-1][8:]]
    await scan(reader)
    assert reader.error is None
    assert reader.snapshot is not original


async def test_missing_remaining_time_stops_at_range_boundary(reader: ScheduleReaderManager) -> None:
    controller_mock(reader).read_registers.side_effect = [RECORDS[0][:8], RECORDS[0][8:]] * 96
    await scan(reader)
    assert reader.snapshot is None
    assert reader.error == "Remaining Time record not found within the configured schedule range"
    calls = controller_mock(reader).read_registers.await_args_list
    assert max(call.args[0] + call.args[1] - 1 for call in calls) == 48969


async def test_disabled_sensors_do_not_read(reader: ScheduleReaderManager) -> None:
    for listener in tuple(reader._listeners):  # noqa: SLF001
        reader.remove_listener(listener)
    await scan(reader)
    controller_mock(reader).read_registers.assert_not_called()


async def test_sensor_states_share_snapshot_and_lifecycle(reader: ScheduleReaderManager) -> None:
    descriptions = SCHEDULE_DESCRIPTION.entity_descriptions
    controller = controller_mock(reader)
    entries = descriptions[0].create_entity_if_supported(controller, Inv.PQ1, RegisterType.HOLDING)
    remaining = descriptions[1].create_entity_if_supported(controller, Inv.PQ1, RegisterType.HOLDING)
    assert isinstance(entries, ModbusScheduleSensor)
    assert isinstance(remaining, ModbusScheduleSensor)
    assert entries.native_value is None
    assert not entries.available
    assert entries.addresses == []
    assert entries.entity_id == "sensor.pq1_schedule_entries"
    await scan(reader)
    assert entries.native_value == 4
    assert remaining.native_value == "Self Use"
    assert entries.available
    assert entries.extra_state_attributes["last_updated"] == remaining.extra_state_attributes["last_updated"]
    assert len(entries.extra_state_attributes["entries"]) == 4
    assert remaining.extra_state_attributes["register_address"] == 48050
    with patch.object(entries, "schedule_update_ha_state") as update:
        await entries.async_added_to_hass()
        reader._notify()  # noqa: SLF001
        update.assert_called_once()
        await entries.async_will_remove_from_hass()
        reader._notify()  # noqa: SLF001
        update.assert_called_once()
    reader.error = "Invalid scan"
    assert not entries.available
    assert entries.native_value is None
    assert entries.extra_state_attributes["read_error"] == "Invalid scan"


def test_capability_is_shared_and_other_profiles_remain_unsupported() -> None:
    for profile in INVERTER_PROFILES.values():
        for connection in profile.connection_types.values():
            for inv in connection.versions.values():
                config = SCHEDULE_DESCRIPTION.create_if_supported(inv, connection.register_type)
                assert (config is not None) == (inv == Inv.PQ1 and connection.register_type == RegisterType.HOLDING)
    assert SCHEDULE_DESCRIPTION.create_if_supported(Inv.PQ1, RegisterType.INPUT) is None
    config = SCHEDULE_DESCRIPTION.create_if_supported(Inv.PQ1, RegisterType.HOLDING)
    assert config is not None
    # A second firmware-specific model can reuse the manager with another layout.
    factory = ModbusScheduleFactory(
        [ScheduleAddressSpec(Inv.H3_SMART, replace(config, first_record_address=50000, max_records=3))]
    )
    other = factory.create_if_supported(Inv.H3_SMART, RegisterType.HOLDING)
    assert other is not None
    assert other.first_record_address == 50000
    assert factory.create_if_supported(Inv.PQ1, RegisterType.HOLDING) is None


async def test_full_95_entries_then_remaining_time(reader: ScheduleReaderManager) -> None:
    records = [RECORDS[0].copy() for _ in range(95)] + [RECORDS[-1]]
    # Repeated-looking records and disabled slots cannot terminate the scan.
    records[30][0] = 0
    words = dict(enumerate(chain.from_iterable(records), 48010))

    async def read(address: int, count: int, register_type: RegisterType) -> list[int]:
        assert register_type == RegisterType.HOLDING
        return [words[address + offset] for offset in range(count)]

    controller_mock(reader).read_registers.side_effect = read
    await scan(reader)
    assert reader.snapshot is not None
    assert len(reader.snapshot.entries) == 95
    assert reader.snapshot.entries[30]["enabled"] is False
    assert reader.snapshot.remaining_time["register_address"] == 48960
    calls = controller_mock(reader).read_registers.await_args_list
    assert len(calls) == 192
    assert max(call.args[0] + call.args[1] - 1 for call in calls) == 48969


async def test_alternative_range_boundary(reader: ScheduleReaderManager) -> None:
    config = SCHEDULE_DESCRIPTION.create_if_supported(Inv.PQ1, RegisterType.HOLDING)
    assert config is not None
    config = replace(config, first_record_address=50000, max_records=3)
    assert config.last_address == 50029
    other = ScheduleReaderManager(controller_mock(reader), config, 4)
    other.add_listener(MagicMock())

    async def read(address: int, count: int, register_type: RegisterType) -> list[int]:
        assert register_type == RegisterType.HOLDING
        assert 50000 <= address <= address + count - 1 <= 50029
        return [RECORDS[0][(address - 50000 + offset) % 10] for offset in range(count)]

    controller_mock(reader).read_registers.side_effect = read
    await scan(other)
    assert other.snapshot is None
    assert other.error is not None
    assert controller_mock(reader).read_registers.await_args_list[-1].args[:2] == (50028, 2)


async def test_scan_pauses_between_requests_without_publishing_partial_state(reader: ScheduleReaderManager) -> None:
    mock = controller_mock(reader)
    read = mock.read_registers.side_effect
    first_read = asyncio.Event()

    async def pause_after_read(address: int, count: int, register_type: RegisterType) -> list[int]:
        result = await read(address, count, register_type)
        if not first_read.is_set():
            reader.pause()
            first_read.set()
        return cast(list[int], result)

    mock.read_registers.side_effect = pause_after_read
    await reader.poll_complete_callback()
    task = reader._task  # noqa: SLF001
    assert task is not None
    await first_read.wait()
    await asyncio.sleep(0)
    assert mock.read_registers.await_count == 1
    assert reader.snapshot is None
    # A second poll cannot start an overlapping scan.
    await reader.poll_complete_callback()
    assert reader._task is task  # noqa: SLF001
    reader.resume()
    await task
    assert reader.snapshot is not None


async def test_last_sensor_removal_cancels_a_paused_scan(reader: ScheduleReaderManager) -> None:
    reader.pause()
    await reader.poll_complete_callback()
    task = reader._task  # noqa: SLF001
    assert task is not None
    await asyncio.sleep(0)
    for listener in tuple(reader._listeners):  # noqa: SLF001
        reader.remove_listener(listener)
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0)
    assert reader._task is None  # noqa: SLF001
    controller_mock(reader).read_registers.assert_not_called()
    reader.resume()
    reader.add_listener(MagicMock())
    reader._next_scan_at = 0  # noqa: SLF001
    await scan(reader)
    assert reader.snapshot is not None


async def test_unload_before_scan_starts_clears_task(reader: ScheduleReaderManager) -> None:
    await reader.poll_complete_callback()
    task = reader._task  # noqa: SLF001
    assert task is not None
    reader.unload()
    with pytest.raises(asyncio.CancelledError):
        await task
    await asyncio.sleep(0)
    assert reader._task is None  # noqa: SLF001
    controller_mock(reader).read_registers.assert_not_called()
