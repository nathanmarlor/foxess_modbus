"""Validate and execute the example with HA's actual template/script engines."""

from pathlib import Path
from typing import Any

import pytest
import yaml  # type: ignore[import-untyped]
from homeassistant.core import Context
from homeassistant.core import HomeAssistant
from homeassistant.core import ServiceCall
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import script
from homeassistant.helpers.template import Template

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = yaml.safe_load((ROOT / "examples/automations/PQ1_REMOTE_OVERRIDES.yaml").read_text())


def state(hass: HomeAssistant, key: str, value: Any, **attrs: Any) -> None:
    hass.states.async_set(key, value, attrs)


@pytest.fixture
async def example(hass: HomeAssistant) -> tuple[script.Script, list[tuple[str, dict[str, Any]]]]:
    calls: list[tuple[str, dict[str, Any]]] = []
    for domain in ("input_boolean", "input_text", "input_select", "input_datetime", "input_number"):
        for key, config in PACKAGE[domain].items():
            value = config.get(
                "initial", "off" if domain == "input_boolean" else "Idle" if domain == "input_select" else ""
            )
            state(hass, f"{domain}.{key}", value)
    for key, value in {
        "sensor.solar_inverter_battery_soc": "60",
        "sensor.solar_inverter_max_soc": "100",
        "sensor.solar_inverter_min_soc": "10",
        "sensor.solar_inverter_min_soc_on_grid": "10",
        "select.solar_inverter_force_charge_mode": "Disable",
        "select.solar_inverter_remote_control_target": "Battery",
        "number.solar_inverter_remote_control_watchdog_timeout": "0",
        "sensor.solar_inverter_current_work_mode": "Self Use",
        "binary_sensor.foxess_example_charge_opportunity": "off",
        "binary_sensor.foxess_example_discharge_opportunity": "off",
    }.items():
        state(hass, key, value)
    for direction in ("charge", "discharge"):
        state(hass, f"number.solar_inverter_force_{direction}_power", "1", max=8)

    async def service(call: ServiceCall) -> None:
        calls.append((f"{call.domain}.{call.service}", dict(call.data)))
        ids = call.data["entity_id"]
        if isinstance(ids, str):
            ids = [ids]
        value = call.data.get("option", call.data.get("value", "on" if call.service == "turn_on" else "off"))
        for entity_id in ids:
            old = hass.states.get(entity_id)
            state(hass, entity_id, value, **(dict(old.attributes) if old else {}))

    for domain, services in {
        "input_boolean": ["turn_on", "turn_off"],
        "input_select": ["select_option"],
        "input_text": ["set_value"],
        "select": ["select_option"],
        "number": ["set_value"],
    }.items():
        for name in services:
            hass.services.async_register(domain, name, service)
    actions = await script.async_validate_actions_config(
        hass, cv.SCRIPT_SCHEMA(PACKAGE["script"]["foxess_example_reconcile"]["sequence"])
    )
    executor = script.Script(hass, actions, "FoxESS example", "test")
    return executor, calls


async def run(executor: script.Script) -> None:
    await executor.async_run(context=Context())


async def test_charge_soc_cutoff_latches_and_releases(hass: HomeAssistant, example: Any) -> None:
    executor, calls = example
    state(hass, "binary_sensor.foxess_example_charge_opportunity", "on")
    await run(executor)
    assert hass.states.get("select.solar_inverter_force_charge_mode").state == "Force Charge"
    state(hass, "sensor.solar_inverter_battery_soc", "100")
    await run(executor)
    assert hass.states.get("select.solar_inverter_force_charge_mode").state == "Disable"
    state(hass, "sensor.solar_inverter_battery_soc", "99")
    calls.clear()
    await run(executor)
    assert not any(service == "select.select_option" for service, _ in calls)
    assert hass.states.get("input_boolean.foxess_example_charge_done").state == "on"
    state(hass, "binary_sensor.foxess_example_charge_opportunity", "off")
    await run(executor)
    assert hass.states.get("input_boolean.foxess_example_charge_done").state == "off"


async def test_charge_priority_and_end_of_opportunity(hass: HomeAssistant, example: Any) -> None:
    executor, _ = example
    state(hass, "binary_sensor.foxess_example_charge_opportunity", "on")
    state(hass, "binary_sensor.foxess_example_discharge_opportunity", "on")
    await run(executor)
    assert hass.states.get("select.solar_inverter_force_charge_mode").state == "Force Charge"
    state(hass, "binary_sensor.foxess_example_charge_opportunity", "off")
    await run(executor)
    assert hass.states.get("select.solar_inverter_force_charge_mode").state == "Force Discharge"
    state(hass, "binary_sensor.foxess_example_discharge_opportunity", "off")
    await run(executor)
    assert hass.states.get("select.solar_inverter_force_charge_mode").state == "Disable"


async def test_discharge_margin_forecast_and_invalid_data(hass: HomeAssistant, example: Any) -> None:
    executor, _ = example
    state(hass, "binary_sensor.foxess_example_discharge_opportunity", "on")
    state(hass, "sensor.solar_inverter_battery_soc", "54")
    await run(executor)
    assert hass.states.get("select.solar_inverter_force_charge_mode").state == "Disable"
    state(hass, "sensor.solar_inverter_battery_soc", "56")
    await run(executor)
    state(hass, "sensor.solar_inverter_battery_soc", "52")
    await run(executor)
    assert hass.states.get("select.solar_inverter_force_charge_mode").state == "Force Discharge"
    state(hass, "input_text.foxess_example_reserve_entity", "sensor.forecast_soc")
    state(hass, "sensor.forecast_soc", "unavailable")
    await run(executor)
    assert hass.states.get("select.solar_inverter_force_charge_mode").state == "Disable"


async def test_external_control_not_taken_over(hass: HomeAssistant, example: Any) -> None:
    executor, calls = example
    state(hass, "binary_sensor.foxess_example_charge_opportunity", "on")
    state(hass, "select.solar_inverter_force_charge_mode", "Force Discharge")
    await run(executor)
    assert not any(service in {"select.select_option", "number.set_value"} for service, _ in calls)


async def test_manual_cancel_and_missing_soc(hass: HomeAssistant, example: Any) -> None:
    executor, _ = example
    state(hass, "binary_sensor.foxess_example_charge_opportunity", "on")
    await run(executor)
    state(hass, "sensor.solar_inverter_battery_soc", "unavailable")
    await run(executor)
    assert hass.states.get("select.solar_inverter_force_charge_mode").state == "Disable"
    state(hass, "sensor.solar_inverter_battery_soc", "60")
    await run(executor)
    state(hass, "select.solar_inverter_force_charge_mode", "Disable")
    await run(executor)
    await run(executor)
    assert hass.states.get("select.solar_inverter_force_charge_mode").state == "Disable"


@pytest.mark.usefixtures("example")
async def test_opportunity_signals_and_overnight_window(hass: HomeAssistant) -> None:
    state(hass, "input_boolean.foxess_example_charge_enabled", "on")
    state(hass, "input_boolean.foxess_example_cheap_enabled", "on")
    # The distributed package contains an account placeholder, not a valid HA
    # entity ID. Simulate the user supplying their own tariff signal.
    octopus = "binary_sensor.example_octopus_off_peak"
    state(hass, "input_text.foxess_example_off_peak_entity", octopus)
    state(hass, octopus, "on")
    charge = Template(PACKAGE["template"][0]["binary_sensor"][0]["state"], hass)
    assert charge.async_render() is True
    state(hass, octopus, "unavailable")
    assert charge.async_render() is False
    state(hass, "input_boolean.foxess_example_charge_window_enabled", "on")
    state(hass, "input_datetime.foxess_example_charge_start", "23:00:00")
    state(hass, "input_datetime.foxess_example_charge_end", "22:59:59")
    # A near-full-day overnight interval covers the fixture clock.
    from homeassistant.util import dt as dt_util

    now = dt_util.now().strftime("%H:%M:%S")
    expected = now >= "23:00:00" or now < "22:59:59"
    assert charge.async_render() == expected


@pytest.mark.usefixtures("example")
async def test_card_templates_render(hass: HomeAssistant) -> None:
    card = yaml.safe_load((ROOT / "examples/lovelace/PQ1_REMOTE_OVERRIDES_CARD.yaml").read_text())
    for item in card["cards"]:
        if "content" in item:
            rendered = Template(item["content"], hass).async_render()
            assert isinstance(rendered, str)


@pytest.mark.usefixtures("example")
async def test_package_automation_and_helper_schemas(hass: HomeAssistant) -> None:
    from importlib import import_module

    from homeassistant.components.automation.config import PLATFORM_SCHEMA
    from homeassistant.helpers.trigger import async_validate_trigger_config

    for domain in ("input_boolean", "input_text", "input_select", "input_datetime", "input_number"):
        component = import_module(f"homeassistant.components.{domain}")
        component.CONFIG_SCHEMA({domain: PACKAGE[domain]})
    for automation in PACKAGE["automation"]:
        config = PLATFORM_SCHEMA(automation)
        await async_validate_trigger_config(hass, config["triggers"])
    # Validate the separate stop button's script too.
    await script.async_validate_actions_config(
        hass, cv.SCRIPT_SCHEMA(PACKAGE["script"]["foxess_example_stop"]["sequence"])
    )


async def test_failed_release_keeps_ownership_for_retry(hass: HomeAssistant, example: Any) -> None:
    from homeassistant.exceptions import HomeAssistantError

    executor, _ = example
    state(hass, "binary_sensor.foxess_example_charge_opportunity", "on")
    await run(executor)
    state(hass, "binary_sensor.foxess_example_charge_opportunity", "off")

    async def fail(_call: ServiceCall) -> None:
        raise HomeAssistantError("Connection lost")

    hass.services.async_register("select", "select_option", fail)
    with pytest.raises(HomeAssistantError, match="Connection lost"):
        await run(executor)
    assert hass.states.get("input_select.foxess_example_owner").state == "Charge"

    async def recover(call: ServiceCall) -> None:
        for entity_id in call.data["entity_id"]:
            state(hass, entity_id, call.data["option"])

    hass.services.async_register("select", "select_option", recover)
    await run(executor)
    assert hass.states.get("input_select.foxess_example_owner").state == "Idle"
    assert hass.states.get("select.solar_inverter_force_charge_mode").state == "Disable"


async def test_out_of_range_power_stops_owned_control(hass: HomeAssistant, example: Any) -> None:
    executor, _ = example
    state(hass, "binary_sensor.foxess_example_charge_opportunity", "on")
    await run(executor)
    state(hass, "input_number.foxess_example_charge_power", "9")
    await run(executor)
    assert hass.states.get("select.solar_inverter_force_charge_mode").state == "Disable"
    assert "Blocked" in hass.states.get("input_text.foxess_example_status").state


@pytest.mark.usefixtures("example")
async def test_card_highlights_current_schedule_and_basic_mode(hass: HomeAssistant) -> None:
    card = yaml.safe_load((ROOT / "examples/lovelace/PQ1_REMOTE_OVERRIDES_CARD.yaml").read_text())
    template = Template(card["cards"][-1]["content"], hass)
    state(hass, "binary_sensor.solar_inverter_scheduler_enabled", "on")
    state(hass, "sensor.solar_inverter_current_work_mode", "Force Charge", source="remote_control")
    state(hass, "sensor.solar_inverter_remaining_time", "Self Use", work_mode="Self Use")
    state(
        hass,
        "sensor.solar_inverter_schedule_entries",
        "1",
        entries=[
            {
                "start": "00:00",
                "end": "23:59",
                "enabled": True,
                "register_address": 48010,
                "work_mode": "Force Discharge",
            }
        ],
        last_updated="2026-10-22T12:00:00+01:00",
    )
    rendered = template.async_render()
    assert "Overridden now" in rendered
    assert "Force Discharge" in rendered
    state(hass, "binary_sensor.solar_inverter_scheduler_enabled", "off")
    state(hass, "sensor.solar_inverter_manual_work_mode", "Back-up")
    rendered = template.async_render()
    assert "Overriding Basic mode" in rendered
    assert "Back-up" in rendered


@pytest.mark.usefixtures("example")
async def test_opportunity_entities_are_created_by_ha(hass: HomeAssistant) -> None:
    from copy import deepcopy

    from homeassistant.setup import async_setup_component

    for direction in ("charge", "discharge"):
        hass.states.async_remove(f"binary_sensor.foxess_example_{direction}_opportunity")
    assert await async_setup_component(hass, "template", {"template": deepcopy(PACKAGE["template"])})
    await hass.async_block_till_done()
    entities = [s.entity_id for s in hass.states.async_all("binary_sensor") if "opportunity" in s.entity_id]
    assert "binary_sensor.foxess_example_discharge_opportunity" in entities
    assert "binary_sensor.foxess_example_charge_opportunity" in entities
    # Check a real entity update, not only rendering the state template in isolation.
    state(hass, "input_boolean.foxess_example_discharge_enabled", "on")
    state(hass, "input_boolean.foxess_example_discharge_window_enabled", "on")
    state(hass, "input_datetime.foxess_example_discharge_start", "00:00:00")
    state(hass, "input_datetime.foxess_example_discharge_end", "23:59:59")
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.foxess_example_discharge_opportunity").state == "on"
