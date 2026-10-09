"""Model/firmware specifications for read-only schedule support."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..common.types import Inv
from ..common.types import RegisterType
from .modbus_schedule_config import ModbusCurrentWorkModeAddressConfig
from .modbus_schedule_config import ModbusScheduleAddressConfig

if TYPE_CHECKING:
    from .entity_factory import EntityFactory


@dataclass(frozen=True)
class ScheduleAddressSpec:
    """Match a scheduler layout to the profile's firmware-specific Inv flag."""

    models: Inv
    config: ModbusScheduleAddressConfig


class ModbusScheduleFactory:
    """Use one capability specification for both the manager and its sensors."""

    def __init__(self, addresses: list[ScheduleAddressSpec]) -> None:
        self.address_specs = addresses

    def create_if_supported(
        self, inverter_model: Inv, register_type: RegisterType
    ) -> ModbusScheduleAddressConfig | None:
        matches = [
            spec.config
            for spec in self.address_specs
            if inverter_model in spec.models and register_type == spec.config.register_type
        ]
        assert len(matches) <= 1, "Multiple schedule configurations match this profile"
        return matches[0] if matches else None

    @property
    def entity_descriptions(self) -> list["EntityFactory"]:
        # Import here to keep the capability configuration independent of sensors.
        from .modbus_current_work_mode_sensor import ModbusCurrentWorkModeSensorDescription
        from .modbus_schedule_sensor import ModbusScheduleSensorDescription

        return [
            ModbusScheduleSensorDescription(
                key="schedule_entries", name="Schedule Entries", factory=self, icon="mdi:calendar-clock"
            ),
            ModbusScheduleSensorDescription(
                key="remaining_time", name="Remaining Time", factory=self, icon="mdi:calendar-clock"
            ),
            ModbusCurrentWorkModeSensorDescription(
                key="current_work_mode", name="Current Work Mode", factory=self, icon="mdi:state-machine"
            ),
        ]


SCHEDULE_DESCRIPTION = ModbusScheduleFactory(
    addresses=[
        ScheduleAddressSpec(
            models=Inv.PQ1,
            config=ModbusScheduleAddressConfig(
                register_type=RegisterType.HOLDING,
                first_record_address=48010,
                record_size=10,
                # PQ1 supports 95 explicit schedules plus Remaining Time, covering
                # 48010-48969. Other model/firmware specs can select another range.
                max_records=96,
                current_work_mode=ModbusCurrentWorkModeAddressConfig(
                    manual_work_mode=49203,
                    manual_work_mode_map={1: "Self Use", 2: "Feed-in Priority", 3: "Back-up", 4: "Peak Shaving"},
                    scheduler_enabled=48000,
                    battery_soc=31024,
                    remote_enable=46001,
                    remote_enable_mask=1,
                    force_charge_mode=6,
                    force_discharge_mode=7,
                    after_soc_map={1: "Standby", 3: "Resume Work Mode"},
                    after_soc_not_applicable_modes=frozenset({2}),
                ),
                work_mode_map={
                    1: "Self Use",
                    2: "Feed-in Priority",
                    3: "Back-up",
                    6: "Force Charge",
                    7: "Force Discharge",
                },
            ),
        )
    ]
)
