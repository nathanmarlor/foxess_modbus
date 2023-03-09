"""Adds config flow for foxess_modbus."""
import logging
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback

from .const import DOMAIN
from .const import FRIENDLY_NAME
from .const import INVERTER_CONN
from .const import INVERTER_TYPE
from .const import MODBUS_HOST
from .const import MODBUS_PORT
from .const import MODBUS_SLAVE
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
        self._user_input = {}
        if config is None:
            self._data = dict()
            self._options = dict()
        else:
            self._data = dict(self._config.data)
            self._options = dict(self._config.options)

        self._modbus_schema = vol.Schema(
            {
                vol.Optional(
                    FRIENDLY_NAME,
                    default=self._data.get(FRIENDLY_NAME, ""),
                ): str,
                vol.Required(
                    MODBUS_HOST,
                    default=self._data.get(MODBUS_HOST, ""),
                ): str,
                vol.Required(
                    MODBUS_PORT,
                    default=self._data.get(MODBUS_PORT, 502),
                ): int,
                vol.Required(
                    MODBUS_SLAVE,
                    default=self._data.get(MODBUS_SLAVE, 247),
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

        return await self.async_step_modbus(user_input)

    async def async_step_modbus(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""
        if user_input is not None:
            result, inv_type, conn_type = await self._autodetect_modbus(
                user_input[MODBUS_HOST],
                user_input[MODBUS_PORT],
                user_input[MODBUS_SLAVE],
            )
            if result:
                user_input[INVERTER_TYPE] = inv_type
                user_input[INVERTER_CONN] = conn_type
                self._errors["base"] = None
                self._user_input.update(user_input)
                title = self._get_friendly_name(user_input)
                return self.async_create_entry(title=title, data=self._user_input)
            else:
                self._errors["base"] = "modbus_error"

        return self.async_show_form(
            step_id="user", data_schema=self._modbus_schema, errors=self._errors
        )

    def _get_friendly_name(self, user_input):
        """Friendly name"""
        friendly_name = user_input[FRIENDLY_NAME]
        if friendly_name == "":
            return _TITLE
        else:
            return _TITLE + f" ({friendly_name})"

    async def _autodetect_modbus(self, host: str, port: int, slave: int):
        """Return true if modbus connection can be established"""
        try:
            modbus = ModbusClient(host, port, slave)
            controller = ModbusController(None, modbus, None)
            return await controller.autodetect()
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warn(ex)
            pass
        return False

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry):
        """Get the options flow for this handler."""
        return ModbusFlowHandler(config=config_entry)
