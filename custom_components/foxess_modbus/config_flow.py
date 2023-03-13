"""Adds config flow for foxess_modbus."""
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

import voluptuous as vol
from custom_components.foxess_modbus.modbus_serial_client import ModbusSerialClient
from custom_components.foxess_modbus.modbus_tcp_client import ModbusTCPClient
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import callback
from homeassistant.helpers.selector import selector

from .const import DOMAIN
from .const import FRIENDLY_NAME
from .const import INVERTER_CONN
from .const import INVERTER_MODEL
from .const import INVERTER_TYPE
from .const import MODBUS_HOST
from .const import MODBUS_PORT
from .const import MODBUS_SERIAL_HOST
from .const import MODBUS_SLAVE
from .const import SERIAL
from .const import TCP
from .modbus_controller import ModbusController

_TITLE = "FoxESS - Modbus"
_SAVE_TIME = "save_time"

_LOGGER = logging.getLogger(__name__)


class ModbusFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for foxess_modbus."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self, config=None) -> None:
        """Initialize."""
        self._errors = {}
        self._user_input = {}
        self._config = config
        if config is None:
            self._data = defaultdict(dict)
        else:
            self._data = dict(self._config.data)

        self._modbus_type_schema = vol.Schema(
            {
                vol.Required(INVERTER_TYPE, default="TCP"): selector(
                    {"select": {"options": ["TCP", "SERIAL"]}}
                )
            }
        )

        self._modbus_tcp_schema = vol.Schema(
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

        self._modbus_serial_schema = vol.Schema(
            {
                vol.Optional(FRIENDLY_NAME, default=""): str,
                vol.Required(
                    MODBUS_SERIAL_HOST,
                    default=self._data.get(MODBUS_SERIAL_HOST, "/dev/ttyUSB0"),
                ): str,
                vol.Required(
                    MODBUS_SLAVE,
                    default=self._data.get(MODBUS_SLAVE, 247),
                ): int,
            }
        )

    async def async_step_init(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""
        self._errors = {}

        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""
        self._errors = {}
        if user_input is not None:
            if user_input[INVERTER_TYPE] == TCP:
                return await self.async_step_tcp(user_input)
            else:
                return await self.async_step_serial(user_input)

        return self.async_show_form(
            step_id="user", data_schema=self._modbus_type_schema, errors=self._errors
        )

    async def async_step_tcp(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""
        if MODBUS_HOST in user_input:
            inverter = self._parse_tcp_inverter(user_input)
            result, inv_model, inv_conn = await self._autodetect_tcp_modbus(inverter)
            if result:
                inverter[INVERTER_MODEL] = inv_model
                inverter[INVERTER_CONN] = inv_conn
                self._errors["base"] = None
                # create dictionary entry
                tcp_data = self._data.setdefault(TCP, {})
                host_data = tcp_data.setdefault(
                    f"{inverter[MODBUS_HOST]}:{inverter[MODBUS_PORT]}", {}
                )
                host_data[inverter[FRIENDLY_NAME]] = inverter
                self._data[_SAVE_TIME] = datetime.now()

                return self.async_create_entry(title=_TITLE, data=self._data)
            else:
                self._errors["base"] = "modbus_error"

        return self.async_show_form(
            step_id="tcp", data_schema=self._modbus_tcp_schema, errors=self._errors
        )

    async def async_step_serial(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""
        if MODBUS_SERIAL_HOST in user_input:
            inverter = self._parse_serial_inverter(user_input)
            result, inv_model, inv_conn = await self._autodetect_serial_modbus(inverter)
            if result:
                inverter[INVERTER_MODEL] = inv_model
                inverter[INVERTER_CONN] = inv_conn
                self._errors["base"] = None
                # create dictionary entry
                serial_data = self._data.setdefault(SERIAL, {})
                device_data = serial_data.setdefault(inverter[MODBUS_SERIAL_HOST], {})
                device_data[inverter[FRIENDLY_NAME]] = inverter
                self._data[_SAVE_TIME] = datetime.now()

                return self.async_create_entry(title=_TITLE, data=self._data)
            else:
                self._errors["base"] = "modbus_error"

        return self.async_show_form(
            step_id="serial",
            data_schema=self._modbus_serial_schema,
            errors=self._errors,
        )

    def _parse_tcp_inverter(self, user_input):
        """Parser inverter details"""
        return {
            MODBUS_HOST: user_input[MODBUS_HOST],
            MODBUS_PORT: user_input[MODBUS_PORT],
            MODBUS_SLAVE: user_input[MODBUS_SLAVE],
            FRIENDLY_NAME: user_input[FRIENDLY_NAME],
        }

    def _parse_serial_inverter(self, user_input):
        """Parser inverter details"""
        return {
            MODBUS_SERIAL_HOST: user_input[MODBUS_SERIAL_HOST],
            MODBUS_SLAVE: user_input[MODBUS_SLAVE],
            FRIENDLY_NAME: user_input[FRIENDLY_NAME],
        }

    async def _autodetect_tcp_modbus(self, inverter):
        """Return true if modbus connection can be established"""
        try:
            client = ModbusTCPClient(inverter[MODBUS_HOST], inverter[MODBUS_PORT])
            controller = ModbusController(None, client, None, inverter[MODBUS_SLAVE])
            return await controller.autodetect()
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warn(ex)
            pass
        return False, None, None

    async def _autodetect_serial_modbus(self, inverter):
        """Return true if modbus connection can be established"""
        try:
            client = ModbusSerialClient(inverter[MODBUS_SERIAL_HOST])
            controller = ModbusController(None, client, None, inverter[MODBUS_SLAVE])
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
