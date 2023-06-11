from typing import Any
from ..modbus_controller import ModbusController
from homeassistant.components import websocket_api
from homeassistant.helpers import config_validation as cv
import voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.core import callback

def register(hass: HomeAssistant, inverter_controllers: list[tuple[Any, ModbusController]]) -> None:
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
    connection.send_result(msg["id"], {"test": "foo"})
