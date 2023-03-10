"""Adds config flow for foxess_modbus."""
import logging
import uuid
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback

from .const import DOMAIN
from .const import FRIENDLY_NAME
from .const import INVERTER_CONN
from .const import INVERTER_MODEL
from .const import INVERTER_TYPE
from .const import MODBUS_HOST
from .const import MODBUS_PORT
from .const import MODBUS_SLAVE
from .const import TCP
from .modbus_client import ModbusClient
from .modbus_controller import ModbusController

_TITLE = "FoxESS - Modbus"

_LOGGER = logging.getLogger(__name__)


class ModbusFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for foxess_modbus."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self, config=None) -> None:
        """Initialize."""
        self._errors = {}
        self._config = config
        if config is None:
            self._data = dict()
        else:
            self._data = dict(self._config.data)

        self._modbus_schema = vol.Schema(
            {
                vol.Optional(FRIENDLY_NAME, default=""): str,
                vol.Required(MODBUS_HOST): str,
                vol.Required(
                    MODBUS_PORT,
                    default=502,
                ): int,
                vol.Required(
                    MODBUS_SLAVE,
                    default=247,
                ): int,
            }
        )

    async def async_step_init(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        return await self.async_step_modbus(user_input)

    async def async_step_user(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return await self.async_step_modbus(user_input)

    async def async_step_modbus(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            inverter = self._parse_inverter(user_input)
            result, inv_model, inv_conn = await self._autodetect_modbus(inverter)
            if result:
                inverter[INVERTER_TYPE] = TCP
                inverter[INVERTER_MODEL] = inv_model
                inverter[INVERTER_CONN] = inv_conn
                self._errors["base"] = None
                self._data[uuid.uuid4()] = inverter
                return self.async_create_entry(title=_TITLE, data=self._data)
            else:
                self._errors["base"] = "modbus_error"

        return self.async_show_form(
            step_id="user", data_schema=self._modbus_schema, errors=self._errors
        )

    def _parse_inverter(self, user_input):
        """Parser inverter details"""
        return {
            MODBUS_HOST: user_input[MODBUS_HOST],
            MODBUS_PORT: user_input[MODBUS_PORT],
            MODBUS_SLAVE: user_input[MODBUS_SLAVE],
            FRIENDLY_NAME: user_input[FRIENDLY_NAME],
        }

    async def _autodetect_modbus(self, inverter):
        """Return true if modbus connection can be established"""
        try:
            modbus = ModbusClient(
                inverter[MODBUS_HOST], inverter[MODBUS_PORT], inverter[MODBUS_SLAVE]
            )
            controller = ModbusController(None, modbus, None)
            return await controller.autodetect()
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warn(ex)
            pass
        return False, None, None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Get the options flow for this handler."""
        return ModbusFlowHandler(config=config_entry)
