"""Service helpers find the inverter through Home Assistant's device registry (see #1262)."""

import logging
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry
from pytest_homeassistant_custom_component.common import MockConfigEntry  # type: ignore[import-untyped]

from custom_components.foxess_modbus.const import DOMAIN
from custom_components.foxess_modbus.const import FRIENDLY_NAME
from custom_components.foxess_modbus.services import utils


def _controller(friendly_name: str) -> MagicMock:
    controller = MagicMock()
    controller.inverter_details = {FRIENDLY_NAME: friendly_name}
    return controller


def _device(hass: HomeAssistant, domain: str, identifier: tuple[str, ...]) -> str:
    entry = MockConfigEntry(domain=domain)
    entry.add_to_hass(hass)
    registry = device_registry.async_get(hass)
    # The integration's device identifiers have 4 parts (see ModbusEntityMixin.device_info)
    return registry.async_get_or_create(config_entry_id=entry.entry_id, identifiers={identifier}).id  # type: ignore[arg-type]


async def test_lookup_by_device_id(hass: HomeAssistant, caplog: pytest.LogCaptureFixture) -> None:
    caplog.set_level(logging.WARNING)
    controller = _controller("inverter")
    device_id = _device(hass, DOMAIN, (DOMAIN, "H3", "AUX", "inverter"))
    assert utils.get_controller_from_friendly_name_or_device_id(device_id, [controller], hass) is controller
    # #1262: HA warns when device_registry.devices is used as a mapping
    assert "device_registry.devices" not in caplog.text


async def test_lookup_by_friendly_name(hass: HomeAssistant) -> None:
    controller = _controller("inverter")
    assert utils.get_controller_from_friendly_name_or_device_id("inverter", [controller], hass) is controller


async def test_device_of_another_integration(hass: HomeAssistant) -> None:
    device_id = _device(hass, "other_integration", ("other_integration", "H3", "AUX", "inverter"))
    with pytest.raises(HomeAssistantError, match="not an inverter"):
        utils.get_controller_from_friendly_name_or_device_id(device_id, [_controller("inverter")], hass)


@pytest.mark.parametrize("device_id", ["missing", None])
async def test_unknown_device_or_name(hass: HomeAssistant, device_id: str | None) -> None:
    with pytest.raises(HomeAssistantError, match="Unable to find an inverter"):
        utils.get_controller_from_friendly_name_or_device_id(device_id, [_controller("inverter")], hass)


async def test_no_inverters(hass: HomeAssistant) -> None:
    with pytest.raises(HomeAssistantError, match="No inverters configured"):
        utils.get_controller_from_friendly_name_or_device_id("inverter", [], hass)
