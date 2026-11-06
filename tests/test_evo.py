from custom_components.foxess_modbus.common.types import Inv
from custom_components.foxess_modbus.common.types import ConnectionType
from custom_components.foxess_modbus.common.types import RegisterType
from custom_components.foxess_modbus.const import INVERTER_BASE
from custom_components.foxess_modbus.const import INVERTER_CONN
from custom_components.foxess_modbus.entities.entity_descriptions import ENTITIES
from custom_components.foxess_modbus.entities.modbus_remote_control_config import WorkMode
from custom_components.foxess_modbus.entities.remote_control_description import REMOTE_CONTROL_DESCRIPTION
from custom_components.foxess_modbus.inverter_profiles import inverter_connection_type_profile_from_config


def _evo_entities() -> dict[str, dict[str, object]]:
    result = {}
    for entity in ENTITIES:
        serialized = entity.serialize(Inv.EVO, RegisterType.HOLDING)
        if serialized is not None:
            result[str(serialized["key"])] = serialized
    return result


def test_evo_remote_control_addresses() -> None:
    config = REMOTE_CONTROL_DESCRIPTION.create_if_supported(
        None, Inv.EVO, RegisterType.HOLDING  # type: ignore[arg-type]
    )

    assert config is not None
    assert config.remote_enable == 46001
    assert config.timeout_set == 46002
    assert config.active_power == [46004, 46003]
    assert config.work_mode == 49203
    assert config.work_mode_map == {
        WorkMode.SELF_USE: 1,
        WorkMode.FEED_IN_FIRST: 2,
        WorkMode.BACK_UP: 3,
    }
    assert config.max_soc == 46610
    assert config.invbatpower == [39238, 39237]
    assert config.battery_soc == [39423]
    assert config.pwr_limit_bat_up == [46019, 46018]
    assert config.pv_voltages == [39070, 39072, 39074]


def test_legacy_adam_evo_config_identifier_is_migrated() -> None:
    profile = inverter_connection_type_profile_from_config(
        {INVERTER_BASE: "EVO_10_H", INVERTER_CONN: ConnectionType.AUX}
    )

    assert profile.get_inv_for_version(None) == Inv.EVO
    assert profile.overlaps_invalid_range(37637, 37699)
    assert not profile.overlaps_invalid_range(37636, 37636)
    assert not profile.overlaps_invalid_range(37700, 37700)


def test_evo_system_soc_and_bms_entities() -> None:
    entities = _evo_entities()

    assert entities["battery_soc"]["addresses"] == [39423]
    assert entities["battery_soc"]["name"] == "System SoC"
    assert entities["battery_soc"]["signed"] is False
    assert entities["battery_soh_1"]["addresses"] == [37624]
    assert entities["battery_soh_2"]["addresses"] == [38322]
    assert entities["battery_temp_1"]["addresses"] == [37611]
    assert entities["battery_temp_2"]["addresses"] == [38309]


def test_evo_reserved_ambient_temperature_is_not_exposed() -> None:
    assert "ambtemp" not in _evo_entities()


def test_evo_protocol_scaling_and_signedness() -> None:
    serialized = [
        value
        for entity in ENTITIES
        if (value := entity.serialize(Inv.EVO, RegisterType.HOLDING)) is not None
    ]

    def sensor(key: str) -> dict[str, object]:
        return next(value for value in serialized if value["type"] == "sensor" and value["key"] == key)

    assert sensor("inv_power")["scale"] == 0.001
    assert sensor("grid_voltage_R")["signed"] is True
    assert sensor("rfreq")["signed"] is True
    assert sensor("eps_frequency")["signed"] is True

    for key in (
        "battery_charge_today",
        "battery_discharge_today",
        "feed_in_energy_today",
        "grid_consumption_energy_today",
        "total_yield_today",
        "input_energy_today",
        "load_energy_today",
        "min_soc",
        "max_soc",
        "min_soc_on_grid",
    ):
        assert sensor(key)["signed"] is False
