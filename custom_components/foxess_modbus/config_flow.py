"""Adds config flow for foxess_modbus."""
import logging
import re
from collections import defaultdict
from datetime import datetime
from typing import Any
from typing import Awaitable
from typing import Callable

import voluptuous as vol
from custom_components.foxess_modbus import ModbusClient
from homeassistant import config_entries
from homeassistant.components.energy import data
from homeassistant.components.energy.data import BatterySourceType
from homeassistant.components.energy.data import EnergyPreferencesUpdate
from homeassistant.components.energy.data import FlowFromGridSourceType
from homeassistant.components.energy.data import FlowToGridSourceType
from homeassistant.components.energy.data import GridSourceType
from homeassistant.components.energy.data import SolarSourceType
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import selector
from pymodbus.exceptions import ConnectionException

from .common.exceptions import UnsupportedInverterException
from .const import ADD_ANOTHER
from .const import CONFIG_SAVE_TIME
from .const import DOMAIN
from .const import ENERGY_DASHBOARD
from .const import FRIENDLY_NAME
from .const import INVERTER_BASE
from .const import INVERTER_CONN
from .const import INVERTER_MODEL
from .const import INVERTER_TYPE
from .const import MAX_READ
from .const import MODBUS_HOST
from .const import MODBUS_PORT
from .const import MODBUS_SERIAL_HOST
from .const import MODBUS_SLAVE
from .const import MODBUS_TYPE
from .const import POLL_RATE
from .const import SERIAL
from .const import TCP
from .modbus_controller import ModbusController

_TITLE = "FoxESS - Modbus"

_LOGGER = logging.getLogger(__name__)


class ModbusFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for foxess_modbus."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self, config=None) -> None:
        """Initialize."""
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
                ),
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

        self._energy_dash = vol.Schema(
            {
                vol.Required(ENERGY_DASHBOARD, default=False): bool,
            }
        )

    async def async_step_init(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""
        return await self.async_step_user(user_input)

    async def async_step_user(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""

        async def body(user_input):
            if user_input[INVERTER_TYPE] == TCP:
                return await self.async_step_tcp(user_input)
            else:
                return await self.async_step_serial(user_input)

        return await self._with_default_form(
            user_input, "user", self._modbus_type_schema, body
        )

    async def async_step_tcp(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""

        async def body(user_input):
            if MODBUS_HOST in user_input:
                inverter = self._parse_inverter(user_input)
                host = f"{user_input[MODBUS_HOST]}:{user_input[MODBUS_PORT]}"
                await self.async_add_inverter(TCP, host, inverter)
                if user_input[ADD_ANOTHER]:
                    return self.async_show_form(
                        step_id="user",
                        data_schema=self._modbus_type_schema,
                    )
                else:
                    return await self.async_step_energy()
            return None

        return await self._with_default_form(
            user_input, "tcp", self._modbus_tcp_schema, body
        )

    async def async_step_serial(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""

        async def body(user_input):
            if MODBUS_SERIAL_HOST in user_input:
                inverter = self._parse_inverter(user_input)
                await self.async_add_inverter(
                    SERIAL, user_input[MODBUS_SERIAL_HOST], inverter
                )
                if user_input[ADD_ANOTHER]:
                    return self.async_show_form(
                        step_id="user",
                        data_schema=self._modbus_type_schema,
                    )
                else:
                    return await self.async_step_energy()
            return None

        return await self._with_default_form(
            user_input, "serial", self._modbus_serial_schema, body
        )

    async def async_step_energy(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""

        async def body(user_input):
            if user_input[ENERGY_DASHBOARD]:
                await self._setup_energy_dashboard()
            return self.async_create_entry(title=_TITLE, data=self._data)

        return await self._with_default_form(
            user_input, "energy", self._energy_dash, body
        )

    def ensure_not_duplicate(self, inv_type, host, friendly_name):
        """Detect duplicates"""
        if host in self._data[inv_type]:
            # TODO: Shouldn't we be checking for duplicate friendly names across all hosts?
            if friendly_name in self._data[inv_type][host]:
                raise ValidationFailedExeption({"base": "modbus_duplicate"})

    async def async_add_inverter(self, inv_type, host, inverter):
        """Handle a flow initialized by the user."""
        self.ensure_not_duplicate(inv_type, host, inverter[FRIENDLY_NAME])
        details = await self._autodetect_modbus(inv_type, host, inverter[MODBUS_SLAVE])
        base_model, full_model, inv_conn = details
        inverter[INVERTER_BASE] = base_model
        inverter[INVERTER_MODEL] = full_model
        inverter[INVERTER_CONN] = inv_conn
        # create dictionary entry
        base_data = self._data.setdefault(inv_type, {})
        host_data = base_data.setdefault(host, {})
        host_data[inverter[FRIENDLY_NAME]] = inverter
        self._data[CONFIG_SAVE_TIME] = datetime.now()

    def _parse_inverter(self, user_input):
        """Parser inverter details"""
        return {
            MODBUS_SLAVE: user_input[MODBUS_SLAVE],
            FRIENDLY_NAME: user_input[FRIENDLY_NAME],
        }

    async def _autodetect_modbus(self, inv_type, host, slave):
        """Return true if modbus connection can be established"""
        try:
            params = {MODBUS_TYPE: inv_type}
            if inv_type == TCP:
                params.update({"host": host.split(":")[0], "port": host.split(":")[1]})
            else:
                params.update({"port": host, "baudrate": 9600})
            client = ModbusClient(self.hass, params)
            return await ModbusController.autodetect(client, slave)
        except UnsupportedInverterException as ex:
            _LOGGER.warning(f"{ex}")
            raise ValidationFailedExeption({"base": "modbus_model_not_supported"})
        except ConnectionException as ex:
            _LOGGER.warning(f"{ex}")
            raise ValidationFailedExeption({"base": "modbus_error"})

    async def _setup_energy_dashboard(self):
        """Setup Energy Dashboard"""
        manager = await data.async_get_manager(self.hass)

        friendly_names = self._get_friendly_names(self._data)

        def _prefix_name(name):
            if name != "":
                return f"sensor.{name}_"
            else:
                return "sensor."

        energy_prefs = EnergyPreferencesUpdate(energy_sources=[])
        for name in friendly_names:
            name_prefix = _prefix_name(name)
            energy_prefs["energy_sources"].extend(
                [
                    SolarSourceType(
                        type="solar", stat_energy_from=f"{name_prefix}pv1_energy_total"
                    ),
                    SolarSourceType(
                        type="solar", stat_energy_from=f"{name_prefix}pv2_energy_total"
                    ),
                    BatterySourceType(
                        type="battery",
                        stat_energy_to=f"{name_prefix}battery_charge_total",
                        stat_energy_from=f"{name_prefix}battery_discharge_total",
                    ),
                ]
            )

        grid_source = GridSourceType(
            type="grid", flow_from=[], flow_to=[], cost_adjustment_day=0
        )
        for name in friendly_names:
            name_prefix = _prefix_name(name)
            grid_source["flow_from"].append(
                FlowFromGridSourceType(
                    stat_energy_from=f"{name_prefix}grid_consumption_energy_total"
                )
            )
            grid_source["flow_to"].append(
                FlowToGridSourceType(
                    stat_energy_to=f"{name_prefix}feed_in_energy_total"
                )
            )
        energy_prefs["energy_sources"].append(grid_source)

        await manager.async_update(energy_prefs)

    def _get_friendly_names(self, data_dict):
        """Return all friendly names"""
        names = []
        inverters = {k: v for k, v in data_dict.items() if k in (TCP, SERIAL)}
        for _, host_dict in inverters.items():
            for _, name_dict in host_dict.items():
                names.extend(list(name_dict.keys()))

        return names

    async def _with_default_form(
        self,
        user_input: dict[str, str] | None,
        step_id: str,
        data_schema: vol.Schema,
        body: Callable[[dict[str, str]], Awaitable[FlowResult | None]],
    ):
        """
        If user_input is not None, call body() and return the result.
        If body throws a ValidationFailedException, or returns None, or user_input is None,
        show the default form specified by step_id and data_schema
        """

        errors: dict[str, str] | None = None
        if user_input is not None:
            try:
                result = await body(user_input)
                if result is not None:
                    return result
            except ValidationFailedExeption as ex:
                errors = ex.errors

        schema_with_input = self.add_suggested_values_to_schema(data_schema, user_input)
        return self.async_show_form(
            step_id=step_id, data_schema=schema_with_input, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return ModbusOptionsHandler(config_entry)


class ModbusOptionsHandler(config_entries.OptionsFlow):
    """Options flow handler"""

    def __init__(self, config: config_entries.ConfigEntry) -> None:
        self._config = config
        self._data = dict(self._config.data)

    async def async_step_init(self, user_input=None):
        """Init options"""
        if user_input is not None:
            self._data[POLL_RATE] = user_input[POLL_RATE]
            self._data[MAX_READ] = user_input[MAX_READ]
            return self.async_create_entry(title=_TITLE, data=self._data)

        options_schema = vol.Schema(
            {
                vol.Required(POLL_RATE, default=self._data.get(POLL_RATE, 10)): int,
                vol.Required(MAX_READ, default=self._data.get(MAX_READ, 8)): int,
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema)


class ValidationFailedExeption(Exception):
    def __init__(self, errors: dict[str, str]):
        self.errors = errors
