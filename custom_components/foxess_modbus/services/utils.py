"""Utilities used by services"""
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry

from ..const import DOMAIN
from ..const import FRIENDLY_NAME
from ..modbus_controller import ModbusController


def get_controller_from_friendly_name_or_device_id(
    device_id: str | None,
    inverter_controllers: list[tuple[Any, ModbusController]],
    hass: HomeAssistant,
) -> ModbusController:
    """Fetch a ModbusController from a string containing either its device ID or friendly name"""
    if device_id is None:
        device_id = ""

    # See if there's a device with this ID first
    registry = device_registry.async_get(hass)
    device = registry.devices.get(device_id)
    if device is not None:
        identifiers = device.identifiers
        assert len(identifiers) > 0
        (parts,) = identifiers
        # We rely on the format set by ModbusEntityMixin.device_info
        if len(parts) < 4 or parts[0] != DOMAIN:
            raise HomeAssistantError(
                f"Device with ID '{device_id}' is not an inverter from the foxess_modbus integration"
            )
        friendly_name = parts[3]  # type: ignore
    else:
        # No? OK, they probably specified a friendly name
        friendly_name = device_id

    modbus_controller = next(
        (controller for (inverter, controller) in inverter_controllers if inverter[FRIENDLY_NAME] == friendly_name),
        None,
    )

    if modbus_controller is None:
        friendly_names = ", ".join(f"'{inverter[FRIENDLY_NAME]}'" for (inverter, _) in inverter_controllers)
        raise HomeAssistantError(
            f"Unable to find an inverter with the device ID or friendly name '{friendly_name}'. Valid friendly names: "
            f"{friendly_names}"
        )

    return modbus_controller
