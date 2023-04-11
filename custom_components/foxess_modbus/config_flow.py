"""Adds config flow for foxess_modbus."""
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from typing import Awaitable
from typing import Callable
from typing import Mapping

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
from .const import CONFIG_SAVE_TIME
from .const import DOMAIN
from .const import ENERGY_DASHBOARD
from .const import FRIENDLY_NAME
from .const import INVERTER_BASE
from .const import INVERTER_CONN
from .const import INVERTER_MODEL
from .const import MAX_READ
from .const import MODBUS_SLAVE
from .const import MODBUS_TYPE
from .const import POLL_RATE
from .const import SERIAL
from .const import TCP
from .const import UDP
from .inverter_adapters import ADAPTERS
from .inverter_adapters import InverterAdapter
from .inverter_connection_types import InverterConnectionType
from .modbus_controller import ModbusController

_TITLE = "FoxESS - Modbus"

_DEFAULT_PORT = 502
_DEFAULT_SLAVE = 247

_LOGGER = logging.getLogger(__name__)


@dataclass
class InverterData:
    """Holds data gathered on an inverter as the user went through the flow"""

    adapter: InverterAdapter | None = None
    inverter_base_model: str | None = None
    inverter_model: str | None = None
    modbus_slave: int | None = None
    inverter_protocol: str | None = None  # TCP, UDP, SERIAL
    host: str | None = None  # host:port or /dev/serial
    friendly_name: str | None = None


class ModbusFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for foxess_modbus."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize."""
        self._inverter_data = InverterData()
        self._all_inverters: list[InverterData] = []

    async def async_step_user(self, user_input: dict[str, Any] = None):
        """Handle a flow initialized by the user."""

        return await self.async_step_select_adapter()

    async def async_step_select_adapter(
        self, user_input: dict[str, str] = None
    ) -> FlowResult:
        """Let the user select their adapter type / model"""

        async def body(user_input):
            adapter = ADAPTERS[user_input["adapter"]]
            self._inverter_data.adapter = adapter
            if SERIAL in adapter.protocols:
                assert len(adapter.protocols) == 1
                return await self.async_step_serial_adapter()
            return await self.async_step_tcp_adapter()

        schema = vol.Schema(
            {
                vol.Required("adapter"): selector(
                    {
                        "select": {
                            "options": list(ADAPTERS.keys()),
                            "translation_key": "inverter_adapters",
                        }
                    }
                )
            }
        )
        return await self._with_default_form(body, user_input, "select_adapter", schema)

    async def async_step_tcp_adapter(
        self, user_input: dict[str, str] = None
    ) -> FlowResult:
        """Let the user enter connection details for their TCP/UDP adapter"""

        adapter = self._inverter_data.adapter
        assert adapter is not None

        async def body(user_input):
            protocol = user_input.get(
                "protocol",
                user_input.get("protocol_with_recommendation", adapter.protocols[0]),
            )
            host = user_input.get(
                "adapter_host", user_input.get("direct_connection_host")
            )
            assert host is not None
            port = user_input.get("adapter_port", _DEFAULT_PORT)
            host_and_port = f"{host}:{port}"
            slave = user_input.get("modbus_slave", _DEFAULT_SLAVE)
            await self._autodetect_modbus_and_save_to_inverter_data(
                protocol, adapter.connection_type, host_and_port, slave
            )
            return await self.async_step_friendly_name()

        schema_parts = {}
        description_placeholders = {"setup_link": adapter.setup_link}

        if len(adapter.protocols) > 1:
            # Prompt for TCP vs UDP if that's relevant
            # If we provide a recommendation, show that
            key = (
                "protocol_with_recommendation"
                if adapter.recommended_protocol is not None
                else "protocol"
            )
            schema_parts[vol.Required(key)] = selector(
                {"select": {"options": adapter.protocols}}
            )
            description_placeholders[
                "recommended_protocol"
            ] = adapter.recommended_protocol

        if adapter.connection_type.key == "AUX":
            schema_parts[vol.Required("adapter_host")] = cv.string
            schema_parts[
                vol.Required(
                    "adapter_port",
                    default=_DEFAULT_PORT,
                )
            ] = int
        else:
            # If it's a direct connection we know what the port is
            schema_parts[vol.Required("direct_connection_host")] = cv.string

        schema_parts[
            vol.Required(
                "modbus_slave",
                default=_DEFAULT_SLAVE,
            )
        ] = int

        schema = vol.Schema(schema_parts)

        return await self._with_default_form(
            body, user_input, "tcp_adapter", schema, description_placeholders
        )

    async def async_step_serial_adapter(
        self, user_input: dict[str, str] = None
    ) -> FlowResult:
        """Let the user enter connection details for their serial adapter"""

        adapter = self._inverter_data.adapter
        assert adapter is not None

        async def body(user_input):
            device = user_input["serial_device"]
            slave = user_input.get("modbus_slave", _DEFAULT_SLAVE)
            # TODO: Check for duplicate host/port/slave/protocol combinations
            await self._autodetect_modbus_and_save_to_inverter_data(
                SERIAL, adapter.connection_type, device, slave
            )
            return await self.async_step_friendly_name()

        # TODO: Look at self._data.get(MODBUS_SERIAL_HOST etc)
        schema = vol.Schema(
            {
                vol.Required(
                    "serial_device",
                    default="/dev/ttyUSB0",
                ): cv.string,
                vol.Required("modbus_slave", default=_DEFAULT_SLAVE): int,
            }
        )
        description_placeholders = {"setup_link": adapter.setup_link}

        return await self._with_default_form(
            body, user_input, "serial_adapter", schema, description_placeholders
        )

    async def async_step_friendly_name(
        self, user_input: dict[str, str] = None
    ) -> FlowResult:
        """Let the user enter a friendly name for their inverter"""

        async def body(user_input):
            friendly_name = user_input.get("friendly_name", "")
            if friendly_name and not re.fullmatch(r"\w+", friendly_name):
                raise ValidationFailedException(
                    {"friendly_name": "invalid_friendly_name"}
                )
            if any(x for x in self._all_inverters if x.friendly_name == friendly_name):
                raise ValidationFailedException(
                    {"friendly_name": "duplicate_friendly_name"}
                )

            self._inverter_data.friendly_name = friendly_name
            self._all_inverters.append(self._inverter_data)
            self._inverter_data = InverterData()
            return await self.async_step_add_another_inverter()

        schema = vol.Schema({vol.Optional("friendly_name"): cv.string})

        return await self._with_default_form(body, user_input, "friendly_name", schema)

    async def async_step_add_another_inverter(
        self, _user_input: dict[str, str] = None
    ) -> FlowResult:
        """Let the user choose whether to add another inverter"""

        options = ["select_adapter", "energy"]
        return self.async_show_menu(
            step_id="add_another_inverter", menu_options=options
        )

    async def async_step_energy(self, user_input: dict[str, Any] = None):
        """Let the user choose whether to set up the energy dashboard"""

        async def body(user_input):
            if user_input[ENERGY_DASHBOARD]:
                await self._setup_energy_dashboard()
            return self.async_create_entry(title=_TITLE, data=self._create_entry_data())

        schema = vol.Schema(
            {
                vol.Required(ENERGY_DASHBOARD, default=False): bool,
            }
        )

        return await self._with_default_form(body, user_input, "energy", schema)

    def _create_entry_data(self) -> dict[str, Any]:
        """Create the config entry for all inverters in self._all_inverters"""

        entry = {}
        for inverter in self._all_inverters:
            protocol_data = entry.setdefault(inverter.inverter_protocol, {})
            host_data = protocol_data.setdefault(inverter.host, {})
            host_data[inverter.friendly_name] = {
                INVERTER_BASE: inverter.inverter_base_model,
                INVERTER_MODEL: inverter.inverter_model,
                INVERTER_CONN: inverter.adapter.connection_type.key,
                MODBUS_SLAVE: inverter.modbus_slave,
                FRIENDLY_NAME: inverter.friendly_name,
            }
        entry[CONFIG_SAVE_TIME] = datetime.now()
        return entry

    async def _autodetect_modbus_and_save_to_inverter_data(
        self, protocol: str, conn_type: InverterConnectionType, host: str, slave: int
    ) -> tuple[str, str]:
        """Check that connection details are unique, then connect to the inverter and add its details to self._inverter_data"""
        if any(
            x
            for x in self._all_inverters
            if x.inverter_protocol == protocol
            and x.host == host
            and x.modbus_slave == slave
        ):
            raise ValidationFailedException({"base": "duplicate_connection_details"})

        try:
            params = {MODBUS_TYPE: protocol}
            if protocol in [TCP, UDP]:
                params.update(
                    {"host": host.split(":")[0], "port": int(host.split(":")[1])}
                )
            else:
                params.update({"port": host, "baudrate": 9600})
            client = ModbusClient(self.hass, params)
            base_model, full_model = await ModbusController.autodetect(
                client, conn_type, slave
            )

            self._inverter_data.inverter_base_model = base_model
            self._inverter_data.inverter_model = full_model
            self._inverter_data.inverter_protocol = protocol
            self._inverter_data.modbus_slave = slave
            self._inverter_data.host = host
        except UnsupportedInverterException as ex:
            _LOGGER.warning(f"{ex}")
            raise ValidationFailedException({"base": "modbus_model_not_supported"})
        except ConnectionException as ex:
            _LOGGER.warning(f"{ex}")
            raise ValidationFailedException({"base": "modbus_error"})

    async def _setup_energy_dashboard(self):
        """Setup Energy Dashboard"""

        manager = await data.async_get_manager(self.hass)

        friendly_names = [x.friendly_name for x in self._all_inverters]

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

    async def _with_default_form(
        self,
        body: Callable[[dict[str, str]], Awaitable[FlowResult | None]],
        user_input: dict[str, str] | None,
        step_id: str,
        data_schema: vol.Schema,
        description_placeholders: Mapping[str, str | None] | None = None,
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
            except ValidationFailedException as ex:
                errors = ex.errors

        schema_with_input = self.add_suggested_values_to_schema(data_schema, user_input)
        return self.async_show_form(
            step_id=step_id,
            data_schema=schema_with_input,
            errors=errors,
            description_placeholders=description_placeholders,
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


class ValidationFailedException(Exception):
    def __init__(self, errors: dict[str, str]):
        self.errors = errors
