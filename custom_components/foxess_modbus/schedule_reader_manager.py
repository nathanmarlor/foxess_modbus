"""Read complete scheduler records without changing inverter configuration."""

import asyncio
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.util import dt as dt_util

from .common.entity_controller import EntityController
from .entities.modbus_charge_period_sensors import is_time_value_valid
from .entities.modbus_charge_period_sensors import parse_time_value
from .entities.modbus_schedule_config import ModbusScheduleAddressConfig

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScheduleSnapshot:
    """Both sensors consume the same completed scan, never a partial list."""

    entries: list[dict[str, Any]]
    remaining_time: dict[str, Any]
    started_at: datetime
    finished_at: datetime


class ScheduleReaderManager:
    """Scan in the background, yielding between bounded Modbus requests.

    The controller pauses the scan during telemetry and watchdog maintenance;
    one in-flight request can finish, but no new request starts while paused.
    A scan is not an atomic firmware snapshot: the app may edit/reorder records
    while it is being read. Timestamps expose this observation interval; register
    contents do not prove the inverter has applied them to its operation.
    """

    def __init__(self, controller: EntityController, config: ModbusScheduleAddressConfig, max_read: int) -> None:
        if (
            config.record_size != 10
            or config.max_records < 1
            or max_read < 1
            or config.first_record_address < 0
            or config.last_address > 0xFFFF
            or config.refresh_interval < 0
        ):
            raise ValueError("Invalid schedule layout or adapter read limit")
        self._controller = controller
        self._config = config
        self._max_read = max_read
        self._listeners: set[Callable[[], None]] = set()
        self._task: asyncio.Task[None] | None = None
        self._ready = asyncio.Event()
        self._ready.set()
        self._pause_count = 0
        self._next_scan_at = 0.0
        self.snapshot: ScheduleSnapshot | None = None
        self.error: str | None = None

    def add_listener(self, listener: Callable[[], None]) -> None:
        self._listeners.add(listener)

    def remove_listener(self, listener: Callable[[], None]) -> None:
        self._listeners.discard(listener)
        if not self._listeners:
            self.unload()
            self._next_scan_at = 0.0

    def _notify(self) -> None:
        for listener in tuple(self._listeners):
            listener()

    def _decode_record(self, address: int, words: list[int]) -> dict[str, Any]:
        if len(words) != 10 or any(not isinstance(word, int) or not 0 <= word <= 0xFFFF for word in words):
            raise ValueError(f"Invalid or incomplete schedule record at {address}")
        if words[0] not in (0, 1):
            raise ValueError(f"Invalid schedule enabled flag at {address}")
        if not is_time_value_valid(words[1]) or not is_time_value_valid(words[2]):
            raise ValueError(f"Invalid schedule time at {address}")
        max_soc, min_soc = words[4] >> 8, words[4] & 0xFF
        if not 0 <= min_soc <= max_soc <= 100 or words[5] > 100:
            raise ValueError(f"Invalid schedule SOC at {address}")
        mode_config = self._config.current_work_mode
        is_remaining = words[1] == 0 and words[2] == (23 << 8 | 59)
        after_soc_applicable = None
        after_soc_behavior = "Unknown"
        if mode_config is not None:
            if is_remaining or words[3] in mode_config.after_soc_not_applicable_modes:
                after_soc_applicable = False
                after_soc_behavior = "Not Applicable"
            elif words[3] in (mode_config.force_charge_mode, mode_config.force_discharge_mode):
                after_soc_applicable = True
                after_soc_behavior = mode_config.after_soc_map.get(words[8], f"Unknown ({words[8]})")
            # App availability has not been checked for every other main mode.
        return {
            "register_address": address,
            "enabled": bool(words[0]),
            "start": parse_time_value(words[1]).strftime("%H:%M"),
            "end": parse_time_value(words[2]).strftime("%H:%M"),
            "work_mode": self._config.work_mode_map.get(words[3], f"Unknown ({words[3]})"),
            "work_mode_raw": words[3],
            "min_soc": min_soc,
            "max_soc": max_soc,
            "mode_soc": words[5],
            "power_w": words[6],
            # +8 is mode-dependent: Feed-in Priority can store 1 without an
            # app option, and Remaining Time stores 0. Value 3 does not identify
            # which of Self Use, Feed-in Priority or Back-up resumes.
            "after_soc_applicable": after_soc_applicable,
            "after_soc_behavior": after_soc_behavior,
            "after_soc_raw": words[8],
            # +7/+9 remain unresolved; always retain all original words.
            "raw_registers": list(words),
        }

    def pause(self) -> None:
        """Prevent new schedule requests until all active controller polls finish."""
        self._pause_count += 1
        self._ready.clear()

    def resume(self) -> None:
        self._pause_count -= 1
        if self._pause_count == 0:
            self._ready.set()

    def unload(self) -> None:
        """Cancel outstanding work on integration unload or last sensor removal."""
        if self._task is not None:
            self._task.cancel()

    async def poll_complete_callback(self) -> None:
        """Start a due scan without holding up the next telemetry/watchdog poll."""
        if not self._listeners or self._task is not None or time.monotonic() < self._next_scan_at:
            return
        self._task = self._controller.hass.async_create_background_task(
            self._scan(), "foxess_modbus schedule scan", eager_start=False
        )
        self._task.add_done_callback(self._scan_done)

    def _scan_done(self, task: asyncio.Task[None]) -> None:
        # Also runs when a task is cancelled before its coroutine starts.
        if self._task is task:
            self._task = None

    async def _scan(self) -> None:
        entries: list[dict[str, Any]] = []
        started_at = dt_util.utcnow()
        try:
            for index in range(self._config.max_records):
                address = self._config.first_record_address + index * self._config.record_size
                words = []
                for offset in range(0, self._config.record_size, self._max_read):
                    await self._ready.wait()
                    if not self._controller.is_connected:
                        raise ValueError("Inverter is disconnected")
                    count = min(self._max_read, self._config.record_size - offset)
                    chunk = await self._controller.read_registers(address + offset, count, self._config.register_type)
                    if len(chunk) != count:
                        raise ValueError(f"Incomplete schedule read at {address + offset}")
                    words.extend(chunk)
                    # Give a newly due telemetry poll the opportunity to pause us.
                    # The client also serializes individual Modbus requests.
                    await asyncio.sleep(0)
                record = self._decode_record(address, words)
                # Disabled entries before this marker are genuine saved schedules.
                # Neither enabled=0 nor apparent repetition terminates the scan.
                if record["start"] == "00:00" and record["end"] == "23:59":
                    self.snapshot = ScheduleSnapshot(entries, record, started_at, dt_util.utcnow())
                    self.error = None
                    self._notify()
                    return
                entries.append(record)
            raise ValueError("Remaining Time record not found within the configured schedule range")
        except Exception as ex:
            # A bad scheduler read must not disrupt telemetry or remote control.
            # Keep the last snapshot for diagnostics, but mark sensors unavailable.
            self.error = str(ex)
            _LOGGER.warning("Unable to read inverter schedules: %s", ex)
            self._notify()
        finally:
            self._next_scan_at = time.monotonic() + self._config.refresh_interval
