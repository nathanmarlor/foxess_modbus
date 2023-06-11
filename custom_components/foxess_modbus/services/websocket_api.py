from typing import Any

from ..const import DOMAIN
from ..modbus_controller import ModbusController
from homeassistant.components import websocket_api
from homeassistant.helpers import config_validation as cv
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from .utils import get_controller_from_friendly_name_or_device_id

def register(hass: HomeAssistant) -> None:
    hass.components.websocket_api.async_register_command(get_charge_periods)

@websocket_api.websocket_command(
    {
        vol.Required("type"): "foxess_modbus/get_charge_periods",
        vol.Required("inverter"): vol.Any(cv.string, None),
    }
)
@callback
def get_charge_periods(
    hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]
) -> None:
    inverter_controllers = [x for inverter_controllers in hass.data[DOMAIN].values() for x in inverter_controllers]
    controller = get_controller_from_friendly_name_or_device_id(msg["inverter"], inverter_controllers, hass)
    charge_periods = []
    controller.charge_periods
    connection.send_result(msg["id"], {"test": "foo"})
