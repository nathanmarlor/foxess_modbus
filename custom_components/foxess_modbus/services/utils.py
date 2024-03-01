"""Utilities used by services"""

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry

from ..const import DOMAIN
from ..const import FRIENDLY_NAME
from ..modbus_controller import ModbusController


def get_controller_from_friendly_name_or_device_id(
    device_id: str | None,
    controllers: list[ModbusController],
    hass: HomeAssistant,
) -> ModbusController:
    # HomeAssisantErrors here are shown to the user when they call a service or use the charge period card

    if len(controllers) == 0:
        raise HomeAssistantError("No inverters configured in FoxESS - Modbus")

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
        (controller for controller in controllers if controller.inverter_details[FRIENDLY_NAME] == friendly_name),
        None,
    )

    if modbus_controller is None:
        friendly_names = ", ".join(f"'{controller.inverter_details[FRIENDLY_NAME]}'" for controller in controllers)

        raise HomeAssistantError(
            f"Unable to find an inverter with the device ID or friendly name '{friendly_name}'. Valid friendly names: "
            f"{friendly_names}"
        )

    return modbus_controller
