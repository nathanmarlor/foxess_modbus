from typing import Any

import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.core import HomeAssistant
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from ..const import DOMAIN
from ..const import FRIENDLY_NAME
from ..const import INVERTERS
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
def get_charge_periods(hass: HomeAssistant, connection: websocket_api.ActiveConnection, msg: dict[str, Any]) -> None:
    inverter_controllers = [x for entry in hass.data[DOMAIN].values() for x in entry[INVERTERS]]
    controller = get_controller_from_friendly_name_or_device_id(msg["inverter"], inverter_controllers, hass)
    charge_periods = []
    for charge_period in controller.charge_periods:
        charge_periods.append(
            {
                "period_start_entity_id": charge_period.period_start_entity_id,
                "period_end_entity_id": charge_period.period_end_entity_id,
                "enable_force_charge_entity_id": charge_period.enable_force_charge_entity_id,
                "enable_charge_from_grid_entity_id": charge_period.enable_charge_from_grid_entity_id,
            }
        )
    connection.send_result(
        msg["id"],
        {
            "friendly_name": controller.inverter_details[FRIENDLY_NAME],
            "charge_periods": charge_periods,
        },
    )
