"""PQ1 monitoring and the boundaries of its provisional register map."""

import re
from collections.abc import Iterator
from collections.abc import Mapping
from dataclasses import replace
from datetime import datetime
from datetime import timezone
from typing import Any
from typing import cast
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.number import NumberEntity
from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory

from custom_components.foxess_modbus.client.modbus_client import ModbusClient
from custom_components.foxess_modbus.common.entity_controller import ModbusControllerEntity
from custom_components.foxess_modbus.common.entity_controller import RemoteControlMode
from custom_components.foxess_modbus.common.exceptions import AutoconnectFailedError
from custom_components.foxess_modbus.common.types import ConnectionType
from custom_components.foxess_modbus.common.types import Inv
from custom_components.foxess_modbus.common.types import InverterModel
from custom_components.foxess_modbus.common.types import RegisterType
from custom_components.foxess_modbus.const import ENTITY_ID_PREFIX
from custom_components.foxess_modbus.const import FRIENDLY_NAME
from custom_components.foxess_modbus.const import INVERTER_BASE
from custom_components.foxess_modbus.const import INVERTER_CONN
from custom_components.foxess_modbus.const import INVERTER_MODEL
from custom_components.foxess_modbus.const import MAX_READ
from custom_components.foxess_modbus.const import UNIQUE_ID_PREFIX
from custom_components.foxess_modbus.entities.entity_descriptions import ENTITIES
from custom_components.foxess_modbus.entities.inverter_model_spec import ModbusAddressSpec
from custom_components.foxess_modbus.entities.modbus_current_work_mode_sensor import ModbusCurrentWorkModeSensor
from custom_components.foxess_modbus.entities.modbus_enum_sensor import ModbusEnumSensorDescription
from custom_components.foxess_modbus.entities.modbus_lambda_sensor import ModbusLambdaSensor
from custom_components.foxess_modbus.entities.modbus_select import ModbusSelect
from custom_components.foxess_modbus.entities.modbus_select import ModbusSelectDescription
from custom_components.foxess_modbus.entities.modbus_sensor import ModbusSensor
from custom_components.foxess_modbus.entities.modbus_sensor import ModbusSensorDescription
from custom_components.foxess_modbus.inverter_profiles import INVERTER_PROFILES
from custom_components.foxess_modbus.inverter_profiles import inverter_connection_type_profile_from_config
from custom_components.foxess_modbus.modbus_controller import ModbusController


@pytest.fixture
def controller(hass: HomeAssistant) -> Iterator[ModbusController]:
    details = {
        INVERTER_BASE: InverterModel.PQ1,
        INVERTER_MODEL: "PQ1-8.0",
        INVERTER_CONN: ConnectionType.LAN,
        ENTITY_ID_PREFIX: "pq1",
        UNIQUE_ID_PREFIX: "pq1",
        FRIENDLY_NAME: "PQ1",
    }
    result = ModbusController(
        hass, AsyncMock(spec=ModbusClient), inverter_connection_type_profile_from_config(details), details, 247, 10, 20
    )
    yield result
    result.unload()


@pytest.fixture
def sensors(controller: ModbusController) -> dict[str, SensorEntity]:
    profile = inverter_connection_type_profile_from_config(controller.inverter_details)
    result = {}
    for entity in profile.create_entities(SensorEntity, controller, filter_depends_on_other_entites=False):
        sensor = cast(SensorEntity, entity)
        assert sensor.entity_description.key not in result
        result[sensor.entity_description.key] = sensor
        controller.register_modbus_entity(cast(ModbusControllerEntity, sensor))
    return result


def set_registers(controller: ModbusController, values: Mapping[int, int | None]) -> None:
    for address, value in values.items():
        controller._data[address].read_value = value  # noqa: SLF001


def numeric_value(sensor: SensorEntity) -> int | float | None:
    return cast(ModbusSensor, sensor)._calculate_native_value()  # noqa: SLF001


@pytest.fixture
def remote_target(controller: ModbusController) -> ModbusSelect:
    profile = inverter_connection_type_profile_from_config(controller.inverter_details)
    entity = next(
        entity
        for entity in profile.create_entities(SelectEntity, controller)
        if entity.entity_description.key == "remote_control_target"
    )
    controller.register_modbus_entity(cast(ModbusControllerEntity, entity))
    return cast(ModbusSelect, entity)


@pytest.mark.parametrize("other_bits", [0, 1, 2, 3, 0x8003])
@pytest.mark.parametrize("target, option", [(0, "AC"), (4, "Battery"), (8, "Grid CT-Meter"), (12, "AC (Grid First)")])
async def test_remote_target_preserves_fresh_non_target_bits(
    controller: ModbusController, remote_target: ModbusSelect, other_bits: int, target: int, option: str
) -> None:
    # Cached configuration is deliberately different from the fresh read.
    set_registers(controller, {46001: 12})
    with (
        patch.object(controller, "read_registers", AsyncMock(return_value=[other_bits | 12])) as read,
        patch.object(controller, "write_register", AsyncMock()) as write,
    ):
        await remote_target.async_select_option(option)
        read.assert_awaited_once_with(46001, 1, RegisterType.HOLDING)
        write.assert_awaited_once_with(46001, other_bits | target)


@pytest.mark.parametrize(
    "raw, option",
    [
        (12, "AC (Grid First)"),
        (13, "AC (Grid First)"),
        (7, "Battery"),
        (0x800B, "Grid CT-Meter"),
        (1, "AC"),
        (None, None),
    ],
)
def test_remote_target_decodes_only_target_bits(
    controller: ModbusController, remote_target: ModbusSelect, raw: int | None, option: str | None
) -> None:
    set_registers(controller, {46001: raw})
    assert remote_target.current_option == option


@pytest.mark.parametrize("words", [[], [12, 12], [-1], [65536]])
async def test_remote_target_invalid_read_does_not_write(
    controller: ModbusController, remote_target: ModbusSelect, words: list[int]
) -> None:
    with (
        patch.object(controller, "read_registers", AsyncMock(return_value=words)),
        patch.object(controller, "write_register", AsyncMock()) as write,
    ):
        with pytest.raises(ValueError, match="unavailable or invalid"):
            await remote_target.async_select_option("Battery")
        write.assert_not_awaited()


async def test_remote_target_read_error_does_not_write(
    controller: ModbusController, remote_target: ModbusSelect
) -> None:
    with (
        patch.object(controller, "read_registers", AsyncMock(side_effect=RuntimeError("read failed"))),
        patch.object(controller, "write_register", AsyncMock()) as write,
    ):
        with pytest.raises(RuntimeError, match="read failed"):
            await remote_target.async_select_option("Battery")
        write.assert_not_awaited()


async def test_remote_target_unknown_option_does_not_write(
    controller: ModbusController, remote_target: ModbusSelect
) -> None:
    with (
        patch.object(controller, "read_registers", AsyncMock()) as read,
        patch.object(controller, "write_register", AsyncMock()) as write,
    ):
        await remote_target.async_select_option("Invalid")
        read.assert_not_awaited()
        write.assert_not_awaited()


async def test_existing_select_still_writes_whole_register(controller: ModbusController) -> None:
    # The optional mask must not change existing select behaviour.
    description = ModbusSelectDescription(
        key="unmasked_test",
        name="Unmasked",
        address=[ModbusAddressSpec(holding=49203, models=Inv.PQ1)],
        options_map={1: "Self Use", 2: "Feed-in Priority"},
    )
    entity = cast(ModbusSelect, description.create_entity_if_supported(controller, Inv.PQ1, RegisterType.HOLDING))
    with (
        patch.object(controller, "read_registers", AsyncMock()) as read,
        patch.object(controller, "write_register", AsyncMock()) as write,
    ):
        await entity.async_select_option("Feed-in Priority")
        read.assert_not_awaited()
        write.assert_awaited_once_with(49203, 2)


def test_remote_target_serialization_does_not_mutate_options(remote_target: ModbusSelect) -> None:
    description = cast(ModbusSelectDescription, remote_target.entity_description)
    serialized = description.serialize(Inv.PQ1, RegisterType.HOLDING)
    assert serialized is not None
    serialized["values"]["0"] = serialized["values"].pop(0)
    assert description.options_map[0] == "AC"


@pytest.mark.parametrize("packed", [False, True])
async def test_detect_pq1(packed: bool) -> None:
    client = AsyncMock(spec=ModbusClient)
    chars = list(b"PQ1-8.0 ")
    words = [(chars[i] << 8) | chars[i + 1] for i in range(0, len(chars), 2)] if packed else chars
    words += [0] * (15 - len(words))
    client.read_registers.side_effect = lambda start, count, *_: words[start - 30000 : start - 30000 + count]
    assert await ModbusController.autodetect(client, 247, {MAX_READ: 4}) == (InverterModel.PQ1, "PQ1-8.0")
    assert all(call.args[2:] == (RegisterType.HOLDING, 247) for call in client.read_registers.call_args_list)
    client.close.assert_awaited_once()
    client.write_registers.assert_not_awaited()


async def test_reject_unrecognised_pq1_suffix() -> None:
    client = AsyncMock(spec=ModbusClient)
    client.read_registers.return_value = list(b"PQ1-8.0-OTHER") + [0] * 3
    with pytest.raises(AutoconnectFailedError):
        await ModbusController.autodetect(client, 247, {MAX_READ: 20})
    client.close.assert_awaited_once()


def test_profile_and_entities(controller: ModbusController, sensors: dict[str, SensorEntity]) -> None:
    profile = inverter_connection_type_profile_from_config(controller.inverter_details)
    assert profile is INVERTER_PROFILES[InverterModel.PQ1].connection_types[ConnectionType.AUX]
    assert profile.register_type == RegisterType.HOLDING
    assert profile.get_inv_for_version(None) == Inv.PQ1
    assert controller.inverter_capacity == 8000
    assert re.match(profile.inverter_model_profile.model_pattern, "P1-8.0-E") is None
    assert controller.remote_control_manager is not None
    assert controller.charge_periods == []
    numbers = profile.create_entities(NumberEntity, controller)
    selects = profile.create_entities(SelectEntity, controller)
    assert {entity.entity_description.key for entity in numbers} == {"force_charge_power", "force_discharge_power"}
    assert {entity.entity_description.key for entity in selects} == {"force_charge_mode", "remote_control_target"}
    target = next(entity for entity in selects if entity.entity_description.key == "remote_control_target")
    assert target.entity_description.name == "Target Power Measure"
    assert target.entity_description.entity_category is None
    assert cast(ModbusControllerEntity, target).addresses == [46001]
    assert not any(
        factory.depends_on_other_entities for factory in ENTITIES if factory.serialize(Inv.PQ1, RegisterType.HOLDING)
    )
    addresses = {a for entity in sensors.values() for a in cast(ModbusControllerEntity, entity).addresses}
    assert {31020, 31021, 31024, 39237, 39238} <= addresses
    assert not addresses.intersection({31022, 31023, 31025, 31026, 31027, 31028, 32018, 32019, 32020})
    assert set(range(39601, 39605)) <= addresses
    assert {31049, 31050} <= addresses
    assert not addresses.intersection(range(41001, 41007))
    assert not addresses.intersection({39118, 44003, 37700, 38307, 38914, 39605})
    assert not addresses.intersection(range(48010, 48970))
    assert isinstance(sensors["pv_power_now"], ModbusLambdaSensor)
    assert cast(ModbusControllerEntity, sensors["load_power"]).addresses == [39226, 39225]
    assert cast(ModbusControllerEntity, sensors["solar_energy_total"]).addresses == [39602, 39601]
    assert cast(ModbusControllerEntity, sensors["solar_energy_today"]).addresses == [39604, 39603]
    for key in ("grid_ct", "feed_in", "grid_consumption"):
        assert cast(ModbusControllerEntity, sensors[key]).addresses == [31050, 31049]
    assert "bms_kwh_remaining" not in sensors
    assert "invbatpower_39248" not in sensors
    assert cast(ModbusControllerEntity, sensors["rpower"]).addresses == [39249, 39248]
    assert sensors["rpower"].entity_description.name == "Inverter Rpower"
    assert "inv_power_39248" not in sensors
    assert 31008 not in addresses
    assert cast(ModbusControllerEntity, sensors["inv_power"]).addresses == [39135, 39134]
    assert "load_power_39134" not in sensors
    assert "pv1_energy_total" not in sensors
    assert "pv5_power" not in sensors
    assert "work_mode" not in sensors
    for pv in range(1, 5):
        assert f"pv{pv}_voltage" in sensors
        assert f"pv{pv}_current" in sensors
        assert f"pv{pv}_power" in sensors


@pytest.mark.parametrize("max_read", [1, 8, 20, 125])
async def test_poll_ranges_avoid_invalid_block(
    controller: ModbusController, sensors: dict[str, SensorEntity], max_read: int
) -> None:
    assert sensors
    controller._max_read = max_read  # noqa: SLF001
    ranges = list(controller._create_read_ranges(max_read, is_initial_connection=True))  # noqa: SLF001
    polled = {a for start, count in ranges for a in range(start, start + count)}
    assert {41000, 49203, 41007, 41008, 41009, 41010, 41011} <= polled
    assert not polled.intersection(range(41001, 41007))
    assert all(1 <= count <= max_read for _, count in ranges)
    client = cast(AsyncMock, controller._client)  # noqa: SLF001
    client.read_registers.side_effect = lambda _start, count, *_: [0] * count
    await controller._read_all_registers()  # noqa: SLF001
    client.write_registers.assert_not_awaited()
    assert all(call.args[2:] == (RegisterType.HOLDING, 247) for call in client.read_registers.call_args_list)


@pytest.mark.parametrize(
    ("key", "values", "expected"),
    [
        ("pv3_voltage", {39074: 2561}, 256.1),
        ("pv3_current", {39075: 150}, 1.5),
        ("pv3_power", {39284: 395}, 0.395),
        ("pv1_power", {39280: 40000}, 40),
        ("invbatvolt", {31020: 4000}, 400),
        ("batvolt", {37609: 2629}, 262.9),
        ("invbatcurrent", {31021: 65521}, -1.5),
        ("invbatpower", {39237: 65535, 39238: 64492}, -1.044),
        ("battery_charge", {39237: 65535, 39238: 64492}, 1.044),
        ("battery_discharge", {39237: 65535, 39238: 64492}, 0),
        ("battery_charge", {39237: 0, 39238: 1044}, 0),
        ("battery_discharge", {39237: 0, 39238: 1044}, 1.044),
        ("battery_soc", {31024: 97}, 97),
        ("battery_nominal_capacity", {37635: 1971}, 19.71),
        ("rfreq", {39139: 4991}, 49.91),
        ("max_charge_current", {41007: 500}, 50),
        ("min_soc", {41009: 10}, 10),
        ("max_soc", {41010: 100}, 100),
        ("grid_ct", {31049: 65535, 31050: 65339}, 0.197),
        ("grid_ct", {31049: 65535, 31050: 65333}, 0.203),
        ("grid_ct", {31049: 0, 31050: 284}, -0.284),
        ("feed_in", {31049: 65535, 31050: 65333}, 0.203),
        ("grid_consumption", {31049: 65535, 31050: 65333}, 0),
        ("feed_in", {31049: 0, 31050: 284}, 0),
        ("grid_consumption", {31049: 0, 31050: 284}, 0.284),
        ("grid_ct", {31049: 0, 31050: 0}, 0),
        ("feed_in", {31049: 0, 31050: 0}, 0),
        ("grid_consumption", {31049: 0, 31050: 0}, 0),
        ("grid_ct", {31049: 0, 31050: 40000}, -40),
        ("grid_ct", {31049: 65535, 31050: 25536}, 40),
        ("load_power", {39225: 0, 39226: 203}, 0.203),
        ("load_power", {39225: 0, 39226: 271}, 0.271),
        ("inv_power", {39134: 0, 39135: 3422}, 3.422),
        ("inv_power", {39134: 0, 39135: 1010}, 1.010),
        ("inv_power", {39134: 0, 39135: 4920}, 4.920),
        ("inv_power", {39134: 0, 39135: 1288}, 1.288),
        # Import direction uses the existing shared S32 decoder; hardware test pending.
        ("inv_power", {39134: 65535, 39135: 65036}, -0.500),
        ("invbatpower", {39237: 65535, 39238: 65333}, -0.203),
        ("invbatpower", {39237: 0, 39238: 570}, 0.570),
        ("invbatpower", {39237: 0, 39238: 465}, 0.465),
        ("invbatpower", {39237: 0, 39238: 30}, 0.030),
        ("invbatpower", {39237: 65535, 39238: 64474}, -1.062),
        ("invbatpower", {39237: 0, 39238: 0}, 0.0),
        ("invbatpower", {39237: 0, 39238: 40000}, 40.0),
        ("invbatpower", {39237: 65535, 39238: 25536}, -40.0),
        ("battery_charge", {39237: 65535, 39238: 25536}, 40.0),
        ("battery_discharge", {39237: 0, 39238: 40000}, 40.0),
        ("total_yield_today", {32017: 71}, 7.1),
        ("total_yield_total", {32015: 1, 32016: 2}, 6553.8),
        ("rpower", {39248: 0, 39249: 412}, 0.412),
        ("rpower", {39248: 65535, 39249: 65522}, -0.014),
        ("rpower", {39248: 65535, 39249: 65455}, -0.081),
        ("rpower", {39248: 0, 39249: 548}, 0.548),
        ("rpower", {39248: 0, 39249: 708}, 0.708),
        ("rpower", {39248: 65535, 39249: 65036}, -0.500),
        ("battery_charge_total", {32003: 0, 32004: 464}, 46.4),
        ("battery_charge_today", {32005: 62}, 6.2),
        ("battery_discharge_total", {32006: 0, 32007: 371}, 37.1),
        ("battery_discharge_today", {32008: 31}, 3.1),
        ("load_energy_today", {32023: 36}, 3.6),
        ("feed_in_energy_total", {32009: 0, 32010: 363}, 36.3),
        ("feed_in_energy_today", {32011: 9}, 0.9),
        ("grid_consumption_energy_total", {32012: 0, 32013: 199}, 19.9),
        ("grid_consumption_energy_today", {32014: 4}, 0.4),
        ("load_power_total", {32021: 0, 32022: 309}, 30.9),
        ("feed_in_energy_total", {32009: 1, 32010: 2}, 6553.8),
        ("export_power_limit", {46616: 0, 46617: 15000}, 15000),
        ("export_power_limit", {46616: 1, 46617: 4464}, 70000),
        ("solar_energy_total", {39601: 0, 39602: 9220}, 92.2),
        ("solar_energy_today", {39603: 0, 39604: 2830}, 28.3),
        ("solar_energy_total", {39601: 1, 39602: 2}, 655.38),
        ("solar_energy_today", {39603: 1, 39604: 2}, 655.38),
        ("solar_energy_today", {39603: 0, 39604: 32768}, 327.68),
    ],
)
def test_decoding(
    controller: ModbusController, sensors: dict[str, SensorEntity], key: str, values: dict[int, int], expected: float
) -> None:
    set_registers(controller, values)
    assert numeric_value(sensors[key]) == pytest.approx(expected)


def test_experimental_tag_remains_available_for_community_testing(
    controller: ModbusController, sensors: dict[str, SensorEntity]
) -> None:
    description = cast(ModbusSensorDescription, sensors["invbatpower"].entity_description)
    experimental = replace(description, experimental_models=Inv.PQ1)
    sensor = experimental.create_entity_if_supported(controller, Inv.PQ1, RegisterType.HOLDING)
    assert isinstance(sensor, ModbusSensor)
    set_registers(controller, {39237: None, 39238: 10})
    assert numeric_value(sensor) is None
    assert sensor.entity_description.name == "Inverter Battery Power (Experimental)"
    assert sensor.entity_description.entity_category == EntityCategory.DIAGNOSTIC
    assert sensor.entity_description.entity_registry_enabled_default is False
    assert sensor.entity_description.state_class is None
    assert sensor.extra_state_attributes == {
        "mapping_status": "provisional",
        "raw_registers": {"39238": 10, "39237": None},
    }
    serialized = experimental.serialize(Inv.PQ1, RegisterType.HOLDING)
    assert serialized is not None
    assert serialized["experimental"] is True
    assert not str(description.name).endswith("(Experimental)")


def test_battery_state_does_not_use_unverified_connection_flags(
    controller: ModbusController, sensors: dict[str, SensorEntity]
) -> None:
    set_registers(controller, {31024: 97})
    sensor = sensors["battery_soc"]
    with patch.object(sensor, "schedule_update_ha_state"):
        cast(ModbusControllerEntity, sensor).update_callback({31024})
    assert sensor.native_value == 97


def test_production_cleanup_does_not_remove_p1_readings(controller: ModbusController) -> None:
    profile = INVERTER_PROFILES[InverterModel.P1].connection_types[ConnectionType.AUX]
    p1_sensors = {
        entity.entity_description.key: cast(SensorEntity, entity)
        for entity in profile.create_entities(SensorEntity, controller, filter_depends_on_other_entites=False)
    }
    for key in ("input_energy_total", "battery_temp", "feed_in", "bms_charge_rate", "total_yield_total"):
        assert not str(p1_sensors[key].entity_description.name).endswith("(Experimental)")
        assert p1_sensors[key].entity_description.entity_registry_enabled_default == (key != "bms_charge_rate")
        assert p1_sensors[key].entity_description.state_class is not None
    assert p1_sensors["total_yield_total"].entity_description.name == "Yield Total"


@pytest.mark.parametrize(
    "key",
    [
        "invbatvolt",
        "batvolt",
        "invbatcurrent",
        "pv1_power",
        "pv2_power",
        "pv3_power",
        "pv4_power",
        "load_power",
        "invbatpower",
        "rpower",
        "inv_power",
        "grid_ct",
        "grid_consumption",
        "feed_in",
        "total_yield_today",
        "total_yield_total",
        "battery_charge_total",
        "battery_charge_today",
        "battery_discharge_total",
        "battery_discharge_today",
        "load_energy_today",
        "solar_energy_total",
        "solar_energy_today",
        "feed_in_energy_total",
        "feed_in_energy_today",
        "grid_consumption_energy_total",
        "grid_consumption_energy_today",
        "load_power_total",
    ],
)
def test_confirmed_sensors_are_enabled_with_statistics(sensors: dict[str, SensorEntity], key: str) -> None:
    description = sensors[key].entity_description
    assert not str(description.name).endswith("(Experimental)")
    assert description.entity_registry_enabled_default
    assert description.entity_category is None
    assert description.state_class is not None


def test_production_entities_have_no_experimental_or_raw_readings(sensors: dict[str, SensorEntity]) -> None:
    for sensor in sensors.values():
        assert not str(sensor.entity_description.name).endswith("(Experimental)")
        assert not sensor.entity_description.key.startswith("pq1_register_")
    removed = {
        "invbatpower_39237",
        "load_power_31016",
        "input_energy_today",
        "input_energy_total",
        "battery_temp",
        "bat_current",
        "bms_charge_rate",
        "bms_discharge_rate",
        "inv_power_Q_R",
        "manual_work_mode_49203",
    }
    assert removed.isdisjoint(sensors)
    for key in ("export_power_limit", "manual_work_mode_41000"):
        assert sensors[key].entity_description.entity_category == EntityCategory.DIAGNOSTIC
        assert not sensors[key].entity_description.entity_registry_enabled_default
    assert sensors["manual_work_mode"].entity_description.name == "Basic Work Mode"
    assert sensors["total_yield_today"].entity_description.name == "Inverter AC Output Energy Today"
    assert sensors["total_yield_total"].entity_description.name == "Inverter AC Output Energy Total"


@pytest.mark.parametrize(
    ("key", "values"),
    [
        ("load_power", {39225: None, 39226: 203}),
        ("inv_power", {39134: 0, 39135: None}),
        ("inv_power", {39134: None, 39135: 1288}),
        ("invbatpower", {39237: None, 39238: 570}),
        ("rpower", {39248: 65535, 39249: None}),
        ("solar_energy_total", {39601: None, 39602: 9220}),
        ("solar_energy_total", {39601: 0, 39602: None}),
        ("solar_energy_today", {39603: None, 39604: 2830}),
        ("solar_energy_today", {39603: 0, 39604: None}),
        ("grid_ct", {31049: None, 31050: 284}),
        ("grid_ct", {31049: 0, 31050: None}),
        ("feed_in", {31049: None, 31050: 65333}),
        ("grid_consumption", {31049: 0, 31050: None}),
    ],
)
def test_duplicate_pairs_require_both_words(
    controller: ModbusController, sensors: dict[str, SensorEntity], key: str, values: dict[int, int | None]
) -> None:
    set_registers(controller, values)
    assert numeric_value(sensors[key]) is None


def test_pv_total_uses_all_four_confirmed_strings(hass: HomeAssistant, sensors: dict[str, SensorEntity]) -> None:
    sensor = cast(ModbusLambdaSensor, sensors["pv_power_now"])
    sensor.hass = hass
    for pv, power in enumerate((0.430, 0.411, 0.448, 0.050), start=1):
        hass.states.async_set(sensors[f"pv{pv}_power"].entity_id, str(power))
    with patch.object(sensor, "schedule_update_ha_state"):
        sensor._update_value()  # noqa: SLF001
        assert sensor.native_value == pytest.approx(1.339)
        hass.states.async_set(sensors["pv3_power"].entity_id, "unavailable")
        sensor._update_value()  # noqa: SLF001
        assert sensor.native_value is None


@pytest.mark.parametrize(
    ("capacity", "soh", "soc", "expected"),
    [
        ("19.71", "100", "83", 16.3593),
        ("19.71", "90", "50", 8.8695),
        ("19.71", "100", "0", 0),
        ("19.71", "100", "100", 19.71),
        ("19.71", None, "50", None),
        ("19.71", "unavailable", "50", None),
        ("19.71", "100", "unknown", None),
        ("19.71", "101", "50", None),
        ("19.71", "100", "-1", None),
        ("nan", "100", "50", None),
        ("0", "100", "50", None),
    ],
)
def test_estimated_battery_energy_requires_valid_sources(
    hass: HomeAssistant,
    sensors: dict[str, SensorEntity],
    capacity: str,
    soh: str | None,
    soc: str,
    expected: float | None,
) -> None:
    sensor = cast(ModbusLambdaSensor, sensors["battery_energy_remaining"])
    sensor.hass = hass
    for key, value in zip(("battery_nominal_capacity", "battery_soh", "battery_soc"), (capacity, soh, soc)):
        if value is not None:
            hass.states.async_set(sensors[key].entity_id, value)
    with patch.object(sensor, "schedule_update_ha_state"):
        sensor._update_value()  # noqa: SLF001
    if expected is None:
        assert sensor.native_value is None
    else:
        assert sensor.native_value == pytest.approx(expected)


def test_enum_serialization_does_not_mutate_mode_map(
    controller: ModbusController, sensors: dict[str, SensorEntity]
) -> None:
    description = sensors["manual_work_mode"].entity_description
    assert isinstance(description, ModbusEnumSensorDescription)
    serialized = description.serialize(Inv.PQ1, RegisterType.HOLDING)
    assert serialized is not None
    serialized["options_map"]["1"] = serialized["options_map"].pop(1)
    set_registers(controller, {49203: 1})
    assert sensors["manual_work_mode"].native_value == "Self Use"


@pytest.mark.parametrize(
    ("value", "label"),
    [
        (1, "Self Use"),
        (2, "Feed-in Priority"),
        (3, "Backup"),
        (4, "Peak Shaving"),
        (0, None),
        (6, None),
        (12, None),
        (None, None),
    ],
)
def test_manual_mode_preserves_unknown_codes(
    controller: ModbusController, sensors: dict[str, SensorEntity], value: int | None, label: str | None
) -> None:
    set_registers(controller, {49203: value})
    assert sensors["manual_work_mode"].native_value == label
    assert sensors["manual_work_mode"].extra_state_attributes == {"raw_value": value}


@pytest.mark.parametrize(
    ("legacy", "newer", "label"),
    [(0, 1, "Self Use"), (1, 2, "Feed-in Priority"), (2, 3, "Backup"), (3, 4, "Peak Shaving")],
)
def test_manual_mode_encodings_remain_independent(
    controller: ModbusController, sensors: dict[str, SensorEntity], legacy: int, newer: int, label: str
) -> None:
    set_registers(controller, {41000: legacy, 49203: newer})
    assert sensors["manual_work_mode"].native_value == label
    assert sensors["manual_work_mode_41000"].native_value == label
    set_registers(controller, {49203: 0})
    assert sensors["manual_work_mode"].native_value is None
    assert sensors["manual_work_mode"].extra_state_attributes == {"raw_value": 0}


@pytest.mark.parametrize(("value", "expected"), [(0, False), (1, True), (2, None), (12, None), (None, None)])
def test_scheduler_is_strict_boolean(controller: ModbusController, value: int | None, expected: bool | None) -> None:
    profile = inverter_connection_type_profile_from_config(controller.inverter_details)
    entities = profile.create_entities(BinarySensorEntity, controller)
    assert len(entities) == 1
    sensor = cast(BinarySensorEntity, entities[0])
    controller.register_modbus_entity(cast(ModbusControllerEntity, sensor))
    set_registers(controller, {48000: value})
    assert sensor.is_on is expected


@pytest.mark.parametrize(
    ("register", "raw", "decoded"), [(36001, 289, "1.21"), (36002, 257, "1.01"), (36003, 288, "1.20")]
)
def test_firmware(
    controller: ModbusController, sensors: dict[str, SensorEntity], register: int, raw: int, decoded: str
) -> None:
    key = {36001: "master_version", 36002: "slave_version", 36003: "manager_version"}[register]
    set_registers(controller, {register: raw})
    assert sensors[key].native_value == decoded


async def test_schedule_reader_runs_after_remote_control(controller: ModbusController) -> None:
    """Schedule requests share the poll lifecycle and cannot precede watchdog maintenance."""
    manager = controller.schedule_reader_manager
    remote = controller.remote_control_manager
    assert manager is not None
    assert remote is not None
    order = []

    async def remote_callback() -> None:
        assert not manager._ready.is_set()  # noqa: SLF001
        order.append("remote")

    async def schedule_callback() -> None:
        assert manager._ready.is_set()  # noqa: SLF001
        order.append("schedule")

    with (
        patch.object(controller, "_read_all_registers", AsyncMock(return_value=[])),
        patch.object(remote, "poll_complete_callback", remote_callback),
        patch.object(manager, "poll_complete_callback", schedule_callback),
    ):
        await controller._refresh(None)  # type: ignore[arg-type] # noqa: SLF001
    assert order == ["remote", "schedule"]


@pytest.fixture
def current_mode(sensors: dict[str, SensorEntity]) -> ModbusCurrentWorkModeSensor:
    return cast(ModbusCurrentWorkModeSensor, sensors["current_work_mode"])


def mode_snapshot(controller: ModbusController, code: int = 6, after_soc: int = 1, enabled: int = 1) -> None:
    """A saved 08:00-09:00 forced period followed by Remaining Time."""
    from custom_components.foxess_modbus.schedule_reader_manager import ScheduleSnapshot

    manager = controller.schedule_reader_manager
    assert manager is not None
    record = manager._decode_record(48010, [enabled, 2048, 2304, code, 25610, 45, 8000, 0, after_soc, 1])  # noqa: SLF001
    fallback = manager._decode_record(48020, [1, 0, 5947, 1, 25610, 10, 0, 0, 0, 1])  # noqa: SLF001
    stamp = datetime(2026, 10, 8, 8, 0, tzinfo=timezone.utc)
    manager.snapshot = ScheduleSnapshot([record], fallback, stamp, stamp)
    set_registers(controller, {46001: 12, 48000: 1, 41000: 0, 49203: 1, 31024: 30})


def mode_clock(hour: int = 8, minute: int = 30) -> Any:
    return patch(
        "custom_components.foxess_modbus.entities.modbus_current_work_mode_sensor.dt_util.now",
        return_value=datetime(2026, 10, 8, hour, minute, tzinfo=timezone.utc),
    )


@pytest.mark.parametrize(
    "raw, expected", [(1, "Self Use"), (2, "Feed-in Priority"), (3, "Back-up"), (4, "Peak Shaving")]
)
def test_current_manual_mode_without_schedule_snapshot(
    controller: ModbusController, current_mode: ModbusCurrentWorkModeSensor, raw: int, expected: str
) -> None:
    set_registers(controller, {46001: 12, 48000: 0, 49203: raw})
    assert current_mode.native_value == expected
    assert current_mode.extra_state_attributes["source"] == "manual"
    assert current_mode.extra_state_attributes["inferred"] is True


@pytest.mark.parametrize(
    "code, soc, met, after_soc, behavior",
    [
        (6, 44, False, 1, None),
        (6, 45, True, 1, "Standby"),
        (6, 80, True, 3, "Resume Work Mode"),
        (7, 46, False, 1, None),
        (7, 45, True, 1, "Standby"),
        (7, 10, True, 3, "Resume Work Mode"),
    ],
)
def test_current_scheduled_mode_keeps_label_and_reports_soc_fallback(
    controller: ModbusController,
    current_mode: ModbusCurrentWorkModeSensor,
    code: int,
    soc: int,
    met: bool,
    after_soc: int,
    behavior: str | None,
) -> None:
    mode_snapshot(controller, code, after_soc)
    set_registers(controller, {31024: soc})
    with mode_clock():
        assert current_mode.native_value == ("Force Charge" if code == 6 else "Force Discharge")
        attrs = current_mode.extra_state_attributes
    assert attrs["soc_cutoff_met"] is met
    assert attrs["fallback_in_operation"] is met
    assert attrs.get("after_soc_behavior") == behavior
    if met:
        assert attrs["fallback_work_mode"] == ("Standby" if after_soc == 1 else None)


@pytest.mark.parametrize("enabled, hour", [(0, 8), (1, 10)])
def test_current_remaining_time_ignores_inactive_or_outside_period(
    controller: ModbusController, current_mode: ModbusCurrentWorkModeSensor, enabled: int, hour: int
) -> None:
    mode_snapshot(controller, enabled=enabled)
    with mode_clock(hour):
        assert current_mode.native_value == "Self Use"
        assert current_mode.extra_state_attributes["source"] == "remaining_time"
        assert current_mode.extra_state_attributes["fallback_in_operation"] is None


def test_feed_in_priority_does_not_infer_standby_from_plus8(
    controller: ModbusController, current_mode: ModbusCurrentWorkModeSensor
) -> None:
    mode_snapshot(controller, code=2, after_soc=1)
    set_registers(controller, {31024: 100})
    with mode_clock():
        assert current_mode.native_value == "Feed-in Priority"
        assert current_mode.extra_state_attributes["soc_cutoff_met"] is None
    manager = controller.schedule_reader_manager
    assert manager is not None and manager.snapshot is not None
    assert manager.snapshot.entries[0]["after_soc_applicable"] is False
    assert manager.snapshot.entries[0]["after_soc_behavior"] == "Not Applicable"
    assert manager.snapshot.remaining_time["after_soc_raw"] == 0
    assert manager.snapshot.remaining_time["after_soc_applicable"] is False


def test_current_mode_unknown_inputs_and_failed_scan(
    controller: ModbusController, current_mode: ModbusCurrentWorkModeSensor
) -> None:
    assert current_mode.native_value is None
    mode_snapshot(controller)
    set_registers(controller, {31024: None})
    with mode_clock():
        assert current_mode.native_value == "Force Charge"
        assert "Battery SOC unavailable" in current_mode.extra_state_attributes["reason"]
        assert current_mode.extra_state_attributes["fallback_in_operation"] is None
    manager = controller.schedule_reader_manager
    assert manager is not None
    manager.error = "Failed scan"
    assert current_mode.native_value is None
    assert current_mode.extra_state_attributes["reason"] == "Failed scan"
    set_registers(controller, {48000: 2})
    assert current_mode.native_value is None


@pytest.mark.parametrize("requested", [RemoteControlMode.FORCE_CHARGE, RemoteControlMode.FORCE_DISCHARGE])
def test_current_remote_mode_requires_enable_and_takes_priority(
    controller: ModbusController, current_mode: ModbusCurrentWorkModeSensor, requested: RemoteControlMode
) -> None:
    mode_snapshot(controller)
    remote = controller.remote_control_manager
    assert remote is not None
    with patch.object(remote, "_mode", requested):
        assert remote.active_mode == RemoteControlMode.DISABLE
        with (
            patch.object(remote, "_remote_control_enabled", True),
            patch.object(remote, "_prev_mode", requested),
        ):
            set_registers(controller, {46001: 13})
            assert current_mode.native_value == (
                "Force Charge" if requested == RemoteControlMode.FORCE_CHARGE else "Force Discharge"
            )
            assert current_mode.extra_state_attributes["source"] == "remote_control"
        # An external enable cannot be assigned the integration's requested mode.
        assert current_mode.native_value == "Remote Control"
        assert "not known" in current_mode.extra_state_attributes["reason"]
    set_registers(controller, {46001: 12, 48000: 0})
    assert current_mode.native_value == "Self Use"


def test_overlapping_periods_are_ambiguous(
    controller: ModbusController, current_mode: ModbusCurrentWorkModeSensor
) -> None:
    mode_snapshot(controller)
    manager = controller.schedule_reader_manager
    assert manager is not None and manager.snapshot is not None
    manager.snapshot.entries.append(dict(manager.snapshot.entries[0], register_address=48020))
    with mode_clock():
        assert current_mode.native_value is None
        assert current_mode.extra_state_attributes["matching_record_addresses"] == [48010, 48020]


async def test_current_mode_updates_on_poll_and_schedule_refresh(
    controller: ModbusController, current_mode: ModbusCurrentWorkModeSensor
) -> None:
    manager = controller.schedule_reader_manager
    assert manager is not None
    with patch.object(current_mode, "schedule_update_ha_state") as update:
        await current_mode.async_added_to_hass()
        cast(ModbusControllerEntity, current_mode).update_callback(set())
        manager._notify()  # noqa: SLF001
        assert update.call_count == 2
        await current_mode.async_will_remove_from_hass()
        manager._notify()  # noqa: SLF001
        assert update.call_count == 2


def test_remote_active_mode_retains_last_completed_direction_on_failed_change(controller: ModbusController) -> None:
    remote = controller.remote_control_manager
    assert remote is not None
    with (
        patch.object(remote, "_remote_control_enabled", True),
        patch.object(remote, "_prev_mode", RemoteControlMode.FORCE_CHARGE),
        patch.object(remote, "_mode", RemoteControlMode.FORCE_DISCHARGE),
    ):
        assert remote.active_mode == RemoteControlMode.FORCE_CHARGE
