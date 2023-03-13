"""Adds config flow for foxess_modbus."""
import logging
from collections import defaultdict
from datetime import datetime
from typing import Any

import voluptuous as vol
from custom_components.foxess_modbus.modbus_serial_client import ModbusSerialClient
from custom_components.foxess_modbus.modbus_tcp_client import ModbusTCPClient
from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import selector

from .const import ADD_ANOTHER
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
                vol.Optional(FRIENDLY_NAME, default=""): cv.string,
                vol.Required(MODBUS_HOST): cv.string,
                vol.Required(
                    MODBUS_PORT,
                    default=502,
                ): int,
                vol.Required(
                    MODBUS_SLAVE,
                    default=247,
                ): int,
                vol.Required(ADD_ANOTHER): bool,
            }
        )

        self._modbus_serial_schema = vol.Schema(
            {
                vol.Optional(FRIENDLY_NAME, default=""): cv.string,
                vol.Required(
                    MODBUS_SERIAL_HOST,
                    default=self._data.get(MODBUS_SERIAL_HOST, "/dev/ttyUSB0"),
                ): cv.string,
                vol.Required(
                    MODBUS_SLAVE,
                    default=self._data.get(MODBUS_SLAVE, 247),
                ): int,
                vol.Required(ADD_ANOTHER): cv.boolean,
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
            inverter = self._parse_inverter(user_input)
            host = f"{user_input[MODBUS_HOST]}:{user_input[MODBUS_PORT]}"
            return await self.add_or_rerun(TCP, host, inverter, user_input)

        return self.async_show_form(
            step_id="tcp", data_schema=self._modbus_tcp_schema, errors=self._errors
        )

    async def async_step_serial(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""
        if MODBUS_SERIAL_HOST in user_input:
            inverter = self._parse_inverter(user_input)
            return await self.add_or_rerun(
                SERIAL, user_input[MODBUS_SERIAL_HOST], inverter, user_input
            )

        return self.async_show_form(
            step_id="serial",
            data_schema=self._modbus_serial_schema,
            errors=self._errors,
        )

    async def add_or_rerun(self, inv_type, host, inverter, user_input):
        """Add or rerun the config flow"""
        if not self.detect_duplicate(TCP, host, user_input[FRIENDLY_NAME]):
            result = await self.async_add_inverter(inv_type, host, inverter)
            if user_input[ADD_ANOTHER]:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._modbus_type_schema,
                    errors=self._errors,
                )
            else:
                return result

    def detect_duplicate(self, inv_type, host, friendly_name):
        """Detect duplicates"""
        if host in self._data[inv_type]:
            if friendly_name in self._data[inv_type][host]:
                self._errors["base"] = "modbus_duplicate"
                return True
            else:
                return False

    async def async_add_inverter(self, inv_type, host, inverter):
        """Handle a flow initialized by the user."""
        result, inv_model, inv_conn = await self._autodetect_modbus(
            inv_type, host, inverter[MODBUS_SLAVE]
        )
        if result:
            inverter[INVERTER_MODEL] = inv_model
            inverter[INVERTER_CONN] = inv_conn
            self._errors["base"] = None
            # create dictionary entry
            base_data = self._data.setdefault(inv_type, {})
            host_data = base_data.setdefault(host, {})
            host_data[inverter[FRIENDLY_NAME]] = inverter
            self._data[_SAVE_TIME] = datetime.now()
            return self.async_create_entry(title=_TITLE, data=self._data)
        else:
            self._errors["base"] = "modbus_error"

    def _parse_inverter(self, user_input):
        """Parser inverter details"""
        return {
            MODBUS_SLAVE: user_input[MODBUS_SLAVE],
            FRIENDLY_NAME: user_input[FRIENDLY_NAME],
        }

    async def _autodetect_modbus(self, inv_type, host, slave):
        """Return true if modbus connection can be established"""
        try:
            if inv_type == TCP:
                host_ip, port = host.split(":")
                client = ModbusTCPClient(host_ip, port)
            else:
                client = ModbusSerialClient(host)
            controller = ModbusController(None, client, None, slave)
            return await controller.autodetect()
        except Exception as ex:  # pylint: disable=broad-except
            _LOGGER.warn(ex)
            pass
        return False, None, None

    # @staticmethod
    # @callback
    # def async_get_options_flow(config_entry: ConfigEntry):
    #    """Get the options flow for this handler."""
    #    return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    """Handles options flow for the component."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self.config_entry = config_entry
        self._errors = {}

    async def async_step_init(self, user_input):
        """Manage the options for the custom component."""
        if user_input is not None:
            inv_type, host, name = user_input["select"].split("-")

        inverters = self.dict_to_string(self.config_entry.data)
        options_schema = vol.Schema(
            {
                vol.Required("select"): selector(
                    {
                        "select": {
                            "options": inverters,
                            "mode": "dropdown",
                        }
                    }
                )
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=options_schema, errors=self._errors
        )

    def dict_to_string(self, dct):
        """Convert to flattened strings"""
        values = []
        if TCP in dct:
            for host, name_dict in dct[TCP].items():
                for name, _ in name_dict.items():
                    values.append(f"TCP-{host}-{name}")

        if SERIAL in dct:
            for host, name_dict in dct[SERIAL].items():
                for name, _ in name_dict.items():
                    values.append(f"SERIAL-{host}-{name}")

        return values
