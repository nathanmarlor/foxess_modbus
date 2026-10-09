"""Shared address configuration for the record-based mode scheduler.

This is separate from the legacy two charge periods: scheduler modes, enabled
flags and Remaining Time have different meanings from the legacy registers.
"""

from dataclasses import dataclass

from ..common.types import RegisterType


@dataclass(frozen=True)
class ModbusCurrentWorkModeAddressConfig:
    """Inputs for inferred mode precedence; scheduler enums stay independent."""

    manual_work_mode: int
    manual_work_mode_map: dict[int, str]
    scheduler_enabled: int
    battery_soc: int
    remote_enable: int
    remote_enable_mask: int
    force_charge_mode: int
    force_discharge_mode: int
    after_soc_map: dict[int, str]
    after_soc_not_applicable_modes: frozenset[int]


@dataclass(frozen=True)
class ModbusScheduleAddressConfig:
    """Describe a tested scheduler layout, independently of inverter model."""

    register_type: RegisterType
    first_record_address: int
    record_size: int
    max_records: int
    work_mode_map: dict[int, str]
    current_work_mode: ModbusCurrentWorkModeAddressConfig | None = None
    refresh_interval: float = 60
    """Wait between completed background scans, started after normal polls."""

    @property
    def last_address(self) -> int:
        """Inclusive scan boundary; max_records includes Remaining Time."""
        return self.first_record_address + self.record_size * self.max_records - 1
