"""Infer the current mode without pretending a configuration is firmware status."""

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity
from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import Platform
from homeassistant.helpers.entity import Entity
from homeassistant.util import dt as dt_util

from ..common.entity_controller import EntityController
from ..common.entity_controller import RemoteControlMode
from ..common.types import Inv
from ..common.types import RegisterType
from .entity_factory import ENTITY_DESCRIPTION_KWARGS
from .entity_factory import EntityFactory
from .modbus_entity_mixin import ModbusEntityMixin
from .modbus_schedule_config import ModbusCurrentWorkModeAddressConfig
from .schedule_descriptions import ModbusScheduleFactory


@dataclass(kw_only=True, **ENTITY_DESCRIPTION_KWARGS)
class ModbusCurrentWorkModeSensorDescription(SensorEntityDescription, EntityFactory):  # type: ignore[misc]
    """Only profiles with explicit mode-inference inputs receive this sensor."""

    factory: ModbusScheduleFactory

    @property
    def entity_type(self) -> type[Entity]:
        return SensorEntity

    def create_entity_if_supported(
        self, controller: EntityController, inverter_model: Inv, register_type: RegisterType
    ) -> Entity | None:
        config = self.factory.create_if_supported(inverter_model, register_type)
        if config is None or config.current_work_mode is None:
            return None
        return ModbusCurrentWorkModeSensor(controller, self, config.current_work_mode)

    def serialize(self, inverter_model: Inv, register_type: RegisterType) -> dict[str, Any] | None:
        config = self.factory.create_if_supported(inverter_model, register_type)
        if config is None or config.current_work_mode is None:
            return None
        mode = config.current_work_mode
        return {
            "type": "current-work-mode",
            "key": self.key,
            "name": self.name,
            "addresses": [mode.manual_work_mode, mode.scheduler_enabled, mode.battery_soc, mode.remote_enable],
        }


class ModbusCurrentWorkModeSensor(ModbusEntityMixin, SensorEntity):
    """Remote override > active schedule/fallback > manual mode.

    PQ1 has no verified effective-mode register. Time/SOC infer the intended
    mode from the last complete schedule scan. After SOC cut-off, retain the
    scheduled mode (as the Fox app does) and expose fallback as attributes.
    Application delay, inverter clock differences and cut-off hysteresis are
    not measurable here; never guess the exact resumed mode from manual mode.
    """

    def __init__(
        self,
        controller: EntityController,
        description: ModbusCurrentWorkModeSensorDescription,
        config: ModbusCurrentWorkModeAddressConfig,
    ) -> None:
        self._controller = controller
        self.entity_description = description
        self._config = config
        self.entity_id = self._get_entity_id(Platform.SENSOR)
        manager = controller.schedule_reader_manager
        assert manager is not None
        self._manager = manager

    @property
    def addresses(self) -> list[int]:
        cfg = self._config
        return [cfg.manual_work_mode, cfg.scheduler_enabled, cfg.battery_soc, cfg.remote_enable]

    def _resolve(self) -> tuple[str | None, dict[str, Any]]:
        cfg = self._config
        attrs: dict[str, Any] = {
            "inferred": True,
            "source": "unknown",
            "soc_cutoff_met": None,
            "fallback_in_operation": None,
        }
        remote_word = self._controller.read(cfg.remote_enable, signed=False)
        attrs["remote_enable_raw"] = remote_word
        if remote_word is None or not 0 <= remote_word <= 0xFFFF:
            attrs["reason"] = "Remote enable state is unavailable"
            return None, attrs
        if remote_word & cfg.remote_enable_mask:
            attrs["source"] = "remote_control"
            remote = self._controller.remote_control_manager
            active = remote.active_mode if remote is not None else RemoteControlMode.DISABLE
            modes = {
                RemoteControlMode.FORCE_CHARGE: "Force Charge",
                RemoteControlMode.FORCE_DISCHARGE: "Force Discharge",
            }
            if active in modes:
                return modes[active], attrs
            # External writers can enable remote control without this manager
            # knowing their target. PQ1 command-readback width is unresolved.
            attrs["reason"] = "Remote control enabled; applied direction is not known to this integration"
            return "Remote Control", attrs

        scheduler = self._controller.read(cfg.scheduler_enabled, signed=False)
        attrs["scheduler_enabled_raw"] = scheduler
        if scheduler == 0:
            attrs["source"] = "manual"
            manual = self._controller.read(cfg.manual_work_mode, signed=False)
            attrs["manual_work_mode_raw"] = manual
            mode = cfg.manual_work_mode_map.get(manual) if manual is not None else None
            if mode is None:
                attrs["reason"] = "Manual work mode is unavailable or unknown"
            return mode, attrs
        if scheduler != 1:
            attrs["reason"] = "Scheduler enable state is unavailable or invalid"
            return None, attrs
        snapshot = self._manager.snapshot
        if snapshot is None or self._manager.error is not None:
            attrs["reason"] = self._manager.error or "Waiting for a complete schedule scan"
            return None, attrs

        now = dt_util.now()
        minute = now.hour * 60 + now.minute
        attrs.update(schedule_last_updated=snapshot.finished_at.isoformat(), local_time=now.isoformat())

        def active_at(record: dict[str, Any]) -> bool:
            start = record["start"].split(":")
            end = record["end"].split(":")
            start_minute, end_minute = int(start[0]) * 60 + int(start[1]), int(end[0]) * 60 + int(end[1])
            # Minutes include both endpoints, matching the 23:59 day endpoint.
            # Overlapping inclusive endpoints remain ambiguous, not arbitrarily
            # resolved by record ordering. Overnight periods wrap at midnight.
            return (
                (start_minute <= minute <= end_minute)
                if start_minute <= end_minute
                else (minute >= start_minute or minute <= end_minute)
            )

        matches = [record for record in snapshot.entries if record["enabled"] and active_at(record)]
        if len(matches) > 1:
            attrs.update(
                reason="Multiple enabled schedules cover the current minute",
                matching_record_addresses=[record["register_address"] for record in matches],
            )
            return None, attrs
        record = matches[0] if matches else snapshot.remaining_time
        attrs.update(
            source="schedule" if matches else "remaining_time",
            schedule_record_address=record["register_address"],
            scheduled_work_mode=record["work_mode"],
        )
        code = record["work_mode_raw"]
        if record["work_mode"].startswith("Unknown"):
            attrs["reason"] = "Unknown scheduled work-mode enum"
            return None, attrs
        if matches and code in (cfg.force_charge_mode, cfg.force_discharge_mode):
            soc = self._controller.read(cfg.battery_soc, signed=False)
            attrs.update(battery_soc=soc, soc_cutoff=record["mode_soc"], after_soc_raw=record["after_soc_raw"])
            if soc is None or not 0 <= soc <= 100:
                attrs["reason"] = "Battery SOC unavailable; cannot determine after-cut-off behaviour"
                return str(record["work_mode"]), attrs
            met = soc >= record["mode_soc"] if code == cfg.force_charge_mode else soc <= record["mode_soc"]
            attrs["soc_cutoff_met"] = met
            attrs["fallback_in_operation"] = met
            if met:
                attrs["after_soc_behavior"] = record["after_soc_behavior"]
                # The requested mode remains the displayed state, like Fox Cloud.
                # +8=3 cannot identify the particular work mode resumed; +8=1
                # identifies Standby only for these forced schedule modes.
                if record["after_soc_behavior"] == "Standby":
                    attrs["fallback_work_mode"] = "Standby"
                else:
                    attrs["fallback_work_mode"] = None
                    attrs["reason"] = (
                        "Resume Work Mode does not identify Self Use, Feed-in Priority or Back-up"
                        if record["after_soc_behavior"] == "Resume Work Mode"
                        else "Unknown after-SOC behaviour"
                    )
        return str(record["work_mode"]), attrs

    @property
    def native_value(self) -> str | None:
        return self._resolve()[0]

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return self._resolve()[1]

    def update_callback(self, _changed_addresses: set[int]) -> None:
        # Re-evaluate on every telemetry poll, even when register values do not
        # change: crossing a time boundary changes which schedule is selected.
        self.schedule_update_ha_state()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self._manager.add_listener(self.schedule_update_ha_state)

    async def async_will_remove_from_hass(self) -> None:
        self._manager.remove_listener(self.schedule_update_ha_state)
        await super().async_will_remove_from_hass()
