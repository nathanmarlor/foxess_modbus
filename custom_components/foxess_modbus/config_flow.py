"""Adds config flow for foxess_modbus."""
import copy
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime
from datetime import timezone
from typing import TYPE_CHECKING
from typing import Any
from typing import Awaitable
from typing import Callable

import voluptuous as vol
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
from pymodbus.exceptions import ModbusIOException
from slugify import slugify

from .common.exceptions import AutoconnectFailedError
from .common.exceptions import UnsupportedInverterError
from .const import ADAPTER_ID
from .const import AUX
from .const import CONFIG_SAVE_TIME
from .const import DOMAIN
from .const import ENTITY_ID_PREFIX
from .const import FRIENDLY_NAME
from .const import HOST
from .const import INVERTER_BASE
from .const import INVERTER_CONN
from .const import INVERTER_MODEL
from .const import INVERTERS
from .const import LAN
from .const import MAX_READ
from .const import MODBUS_SLAVE
from .const import MODBUS_TYPE
from .const import POLL_RATE
from .const import ROUND_SENSOR_VALUES
from .const import RTU_OVER_TCP
from .const import SERIAL
from .const import TCP
from .const import UDP
from .inverter_adapters import ADAPTERS
from .inverter_adapters import InverterAdapter
from .inverter_adapters import InverterAdapterType
from .modbus_client import ModbusClient
from .modbus_client import ModbusClientFailedError
from .modbus_controller import ModbusController

_TITLE = "FoxESS - Modbus"

_DEFAULT_PORT = 502
_DEFAULT_SLAVE = 247

_LOGGER = logging.getLogger(__name__)


@dataclass
class InverterData:
    """Holds data gathered on an inverter as the user went through the flow"""

    adapter_type: InverterAdapterType | None = None
    adapter: InverterAdapter | None = None
    inverter_base_model: str | None = None
    inverter_model: str | None = None
    modbus_slave: int | None = None
    inverter_protocol: str | None = None  # TCP, UDP, SERIAL, RTU_OVER_TCP
    host: str | None = None  # host:port or /dev/serial
    entity_id_prefix: str | None = None
    friendly_name: str | None = None


if TYPE_CHECKING:
    _FlowHandlerMixinBase = config_entries.ConfigFlow
else:
    _FlowHandlerMixinBase = object


class FlowHandlerMixin(_FlowHandlerMixinBase):
    """Mixin for config flow / options flow classes, providing common functionality"""

    async def _with_default_form(
        self,
        body: Callable[[dict[str, Any]], Awaitable[FlowResult | None]],
        user_input: dict[str, Any] | None,
        step_id: str,
        data_schema: vol.Schema,
        description_placeholders: dict[str, str] | None = None,
    ) -> FlowResult:
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
            except ValidationFailedError as ex:
                errors = ex.errors
                if ex.errors:
                    if description_placeholders is None:
                        description_placeholders = ex.error_placeholders
                    elif ex.error_placeholders is not None:
                        description_placeholders.update(ex.error_placeholders)

        schema_with_input = self.add_suggested_values_to_schema(data_schema, user_input)
        return self.async_show_form(
            step_id=step_id,
            data_schema=schema_with_input,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    def _create_label_for_inverter(self, inverter: dict[str, Any]) -> str:
        result = ""
        if inverter[FRIENDLY_NAME]:
            result = f"{inverter[FRIENDLY_NAME]} - "
        result += f"{inverter[HOST]} ({inverter[MODBUS_SLAVE]})"
        return result


class ModbusFlowHandler(FlowHandlerMixin, config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for foxess_modbus."""

    VERSION = 6
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize."""
        self._inverter_data = InverterData()
        self._all_inverters: list[InverterData] = []

        self._adapter_type_to_step = {
            InverterAdapterType.DIRECT: self.async_step_tcp_adapter,
            InverterAdapterType.SERIAL: self.async_step_serial_adapter,
            InverterAdapterType.NETWORK: self.async_step_tcp_adapter,
        }

    async def async_step_user(self, _user_input: dict[str, Any] | None = None) -> FlowResult:
        """Handle a flow initialized by the user."""

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        return await self.async_step_select_adapter_type()

    async def async_step_select_adapter_type(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Let the user select their adapter type"""

        async def body(user_input: dict[str, Any]) -> FlowResult:
            adapter_type = InverterAdapterType(user_input["adapter_type"])
            self._inverter_data.adapter_type = adapter_type

            adapters = [x for x in ADAPTERS.values() if x.adapter_type == adapter_type]

            assert len(adapters) > 0
            if len(adapters) == 1:
                self._inverter_data.adapter = adapters[0]
                return await self._adapter_type_to_step[adapter_type]()

            return await self.async_step_select_adapter_model()

        schema = vol.Schema(
            {
                vol.Required("adapter_type"): selector(
                    {
                        "select": {
                            "options": [x.value for x in InverterAdapterType],
                            "translation_key": "inverter_adapter_types",
                        }
                    }
                )
            }
        )

        return await self._with_default_form(body, user_input, "select_adapter_type", schema)

    async def async_step_select_adapter_model(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Let the user select their adapter model"""

        async def body(user_input: dict[str, Any]) -> FlowResult:
            self._inverter_data.adapter = ADAPTERS[user_input["adapter_model"]]
            assert self._inverter_data.adapter_type is not None
            return await self._adapter_type_to_step[self._inverter_data.adapter_type]()

        adapters = [x for x in ADAPTERS.values() if x.adapter_type == self._inverter_data.adapter_type]

        schema = vol.Schema(
            {
                vol.Required("adapter_model"): selector(
                    {
                        "select": {
                            "options": [x.adapter_id for x in adapters],
                            "mode": "list",
                            "translation_key": "inverter_adapter_models",
                        }
                    }
                )
            }
        )

        return await self._with_default_form(
            body,
            user_input,
            "select_adapter_model",
            schema,
        )

    async def async_step_tcp_adapter(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Let the user enter connection details for their TCP/UDP/RTU_OVER_TCP adapter"""

        adapter = self._inverter_data.adapter

        async def body(user_input: dict[str, Any]) -> FlowResult:
            assert adapter is not None
            assert adapter.network_protocols is not None
            protocol = user_input.get(
                "protocol",
                user_input.get("protocol_with_recommendation", adapter.network_protocols[0]),
            )
            host = user_input.get("adapter_host", user_input.get("lan_connection_host"))
            assert host is not None
            port = user_input.get("adapter_port", _DEFAULT_PORT)
            host_and_port = f"{host}:{port}"
            slave = user_input.get("modbus_slave", _DEFAULT_SLAVE)
            await self._autodetect_modbus_and_save_to_inverter_data(protocol, host_and_port, slave, adapter)
            return await self.async_step_friendly_name()

        assert adapter is not None
        assert adapter.network_protocols is not None

        schema_parts: dict[Any, Any] = {}
        description_placeholders = {"setup_link": adapter.setup_link}

        if len(adapter.network_protocols) > 1:
            # Prompt for TCP vs UDP if that's relevant
            # If we provide a recommendation, show that
            if adapter.recommended_protocol is not None:
                key = "protocol_with_recommendation"
                description_placeholders["recommended_protocol"] = adapter.recommended_protocol
            else:
                key = "protocol"
            schema_parts[vol.Required(key)] = selector(
                {
                    "select": {
                        "options": adapter.network_protocols,
                        "translation_key": "network_protocols",
                    }
                }
            )

        if adapter.connection_type == AUX:
            schema_parts[vol.Required("adapter_host")] = cv.string
            schema_parts[
                vol.Required(
                    "adapter_port",
                    default=_DEFAULT_PORT,
                )
            ] = int
        else:
            # If it's a direct connection we know what the port is
            schema_parts[vol.Required("lan_connection_host")] = cv.string

        schema_parts[
            vol.Required(
                "modbus_slave",
                default=_DEFAULT_SLAVE,
            )
        ] = int

        schema = vol.Schema(schema_parts)

        return await self._with_default_form(body, user_input, "tcp_adapter", schema, description_placeholders)

    async def async_step_serial_adapter(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Let the user enter connection details for their serial adapter"""

        adapter = self._inverter_data.adapter

        async def body(user_input: dict[str, Any]) -> FlowResult:
            assert adapter is not None
            device = user_input["serial_device"]
            slave = user_input.get("modbus_slave", _DEFAULT_SLAVE)
            await self._autodetect_modbus_and_save_to_inverter_data(SERIAL, device, slave, adapter)
            return await self.async_step_friendly_name()

        assert adapter is not None

        schema = vol.Schema(
            {
                vol.Required(
                    "serial_device",
                    default=adapter.default_host,
                ): cv.string,
                vol.Required("modbus_slave", default=_DEFAULT_SLAVE): int,
            }
        )
        description_placeholders = {"setup_link": adapter.setup_link}

        return await self._with_default_form(body, user_input, "serial_adapter", schema, description_placeholders)

    async def async_step_friendly_name(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Let the user enter a friendly name for their inverter"""

        # This is a bit involved, so we'll avoid _with_default_form

        def generate_entity_id_prefix(friendly_name: str | None) -> str:
            return slugify(friendly_name, separator="_", regex_pattern=r"\W").strip("_") if friendly_name else ""

        def is_unique_entity_id_prefix(entity_id_prefix: str) -> bool:
            return not any(x for x in self._all_inverters if x.entity_id_prefix == entity_id_prefix)

        show_entity_id_prefix_input = False
        errors = {}
        if user_input:
            ready_to_submit = True
            entity_id_prefix = None

            friendly_name = user_input.get("friendly_name", "")
            autogenerate_entity_id_prefix = user_input.get("autogenerate_entity_id_prefix", True)

            if any(x for x in self._all_inverters if x.friendly_name == friendly_name):
                errors["friendly_name"] = "duplicate_friendly_name"
            else:
                # 1. If they unchecked "auto-generate entity ID prefix"...
                if not autogenerate_entity_id_prefix:
                    # a. If we haven't yet shown the input box, then show this and pre-populate with our guess. Don't
                    #    check whether our value is valid at this point
                    if "entity_id_prefix" not in user_input:
                        show_entity_id_prefix_input = True
                        ready_to_submit = False
                        user_input["entity_id_prefix"] = generate_entity_id_prefix(friendly_name)
                    # b. If they input a value (or submitted our auto-generated value), validate it
                    else:
                        entity_id_prefix = user_input["entity_id_prefix"]
                        show_entity_id_prefix_input = True
                        if entity_id_prefix and (
                            not re.fullmatch(r"[a-z0-9_]+", entity_id_prefix)
                            or entity_id_prefix.startswith("_")
                            or entity_id_prefix.endswith("_")
                        ):
                            errors["entity_id_prefix"] = "invalid_entity_id_prefix"
                        elif not is_unique_entity_id_prefix(entity_id_prefix):
                            errors["entity_id_prefix"] = "duplicate_entity_id_prefix"

                # 2. If checked "auto-generate entity ID prefix"...
                else:
                    # Try and generate one ourselves
                    entity_id_prefix = generate_entity_id_prefix(friendly_name)
                    # a. If it's not unique, then show an error, show an input box, and check the "specify an entity
                    #    ID" checkbox
                    if not is_unique_entity_id_prefix(entity_id_prefix):
                        show_entity_id_prefix_input = True
                        user_input["autogenerate_entity_id_prefix"] = False
                        user_input["entity_id_prefix"] = entity_id_prefix
                        errors["entity_id_prefix"] = "unable_to_generate_entity_id_prefix"

            # If we got to here, then we're all good. Don't move on if they checked the "specify entity ID prefix"
            # checkbox
            if ready_to_submit and not errors:
                assert entity_id_prefix is not None
                self._inverter_data.entity_id_prefix = entity_id_prefix
                self._inverter_data.friendly_name = friendly_name
                self._all_inverters.append(self._inverter_data)
                self._inverter_data = InverterData()
                return await self.async_step_add_another_inverter()

        schema_parts: dict[Any, Any] = {}
        schema_parts[vol.Optional("friendly_name")] = cv.string
        schema_parts[vol.Required("autogenerate_entity_id_prefix", default=True)] = cv.boolean
        if show_entity_id_prefix_input:
            schema_parts[vol.Optional("entity_id_prefix", default="")] = vol.Any(None, str)
        schema = vol.Schema(schema_parts)

        schema_with_input = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(
            step_id="friendly_name",
            data_schema=schema_with_input,
            errors=errors,
        )

    async def async_step_add_another_inverter(self, _user_input: dict[str, Any] | None = None) -> FlowResult:
        """Let the user choose whether to add another inverter"""

        options = ["select_adapter_type", "energy"]
        return self.async_show_menu(step_id="add_another_inverter", menu_options=options)

    async def async_step_energy(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Let the user choose whether to set up the energy dashboard"""

        async def body(user_input: dict[str, Any]) -> FlowResult:
            if user_input["energy_dashboard"]:
                await self._setup_energy_dashboard()
            return self.async_create_entry(title=_TITLE, data=self._create_entry_data())

        schema = vol.Schema(
            {
                vol.Required("energy_dashboard", default=False): bool,
            }
        )

        return await self._with_default_form(body, user_input, "energy", schema)

    def _create_entry_data(self) -> dict[str, Any]:
        """Create the config entry for all inverters in self._all_inverters"""

        entry: dict[str, Any] = {INVERTERS: {}}
        for inverter in self._all_inverters:
            assert inverter.adapter is not None
            inverter_config = {
                INVERTER_BASE: inverter.inverter_base_model,
                INVERTER_MODEL: inverter.inverter_model,
                INVERTER_CONN: inverter.adapter.connection_type,
                MODBUS_SLAVE: inverter.modbus_slave,
                ENTITY_ID_PREFIX: inverter.entity_id_prefix if inverter.entity_id_prefix else "",
                FRIENDLY_NAME: inverter.friendly_name if inverter.friendly_name else "",
                MODBUS_TYPE: inverter.inverter_protocol,
                HOST: inverter.host,
                ADAPTER_ID: inverter.adapter.adapter_id,
            }
            entry[INVERTERS][str(uuid.uuid4())] = inverter_config
        entry[CONFIG_SAVE_TIME] = datetime.now(timezone.utc)
        return entry

    async def _select_adapter_model_helper(
        self,
        step_id: str,
        user_input: dict[str, Any] | None,
        adapter_type: InverterAdapterType,
        complete_callback: Callable[[InverterAdapter], Awaitable[FlowResult]],
        description_placeholders: dict[str, str] | None = None,
    ) -> FlowResult:
        """Helper used in the steps which let the user select their adapter model"""

        async def body(user_input: dict[str, Any]) -> FlowResult:
            return await complete_callback(ADAPTERS[user_input["adapter_id"]])

        adapters = [x for x in ADAPTERS.values() if x.adapter_type == adapter_type]

        schema = vol.Schema(
            {
                vol.Required("adapter_id"): selector(
                    {
                        "select": {
                            "options": [x.adapter_id for x in adapters],
                            "translation_key": "inverter_adapter_models",
                        }
                    }
                )
            }
        )

        return await self._with_default_form(
            body,
            user_input,
            step_id,
            schema,
            description_placeholders=description_placeholders,
        )

    async def _autodetect_modbus_and_save_to_inverter_data(
        self, protocol: str, host: str, slave: int, adapter: InverterAdapter
    ) -> None:
        """
        Check that connection details are unique, then connect to the inverter and add its details to
        self._inverter_data
        """

        if any(
            x
            for x in self._all_inverters
            if x.inverter_protocol == protocol and x.host == host and x.modbus_slave == slave
        ):
            raise ValidationFailedError({"base": "duplicate_connection_details"})

        try:
            if protocol in [TCP, UDP, RTU_OVER_TCP]:
                params = {"host": host.split(":")[0], "port": int(host.split(":")[1])}
            elif protocol == SERIAL:
                params = {"port": host, "baudrate": 9600}
            else:
                raise AssertionError()
            client = ModbusClient(self.hass, protocol, adapter, params)
            base_model, full_model = await ModbusController.autodetect(client, slave, adapter)

            self._inverter_data.inverter_base_model = base_model
            self._inverter_data.inverter_model = full_model
            self._inverter_data.inverter_protocol = protocol
            self._inverter_data.modbus_slave = slave
            self._inverter_data.host = host
        except UnsupportedInverterError as ex:
            raise ValidationFailedError(
                {"base": "inverter_model_not_supported"},
                error_placeholders={"not_supported_model": ex.full_model},
            ) from ex
        except AutoconnectFailedError as ex:

            def get_details(ex: AutoconnectFailedError, use_exception: bool) -> str:
                if ex.log_records:
                    parts = []
                    if use_exception:
                        parts.append(str(ex.__cause__))
                    parts.extend(record.message for record in ex.log_records)
                    result = "; ".join(parts)
                else:
                    # Oh. Fall back
                    result = str(ex.__cause__)
                return result

            if isinstance(ex.__cause__, ConnectionException):
                # Mainly TCP timeouts. The actual exception message dosen't contain anything interesting here
                raise ValidationFailedError(
                    {
                        "base": "unable_to_connect_to_inverter"
                        if adapter.connection_type == LAN
                        else "unable_to_connect_to_adapter"
                    },
                    error_placeholders={"error_details": get_details(ex, False)},
                ) from ex

            if isinstance(ex.__cause__, ModbusIOException):
                # This is for things like invalid frames. The exception message here can be useful
                raise ValidationFailedError(
                    {
                        "base": "unable_to_communicate_with_inverter"
                        if adapter.connection_type == LAN
                        else "adapter_unable_to_communicate_with_inverter"
                    },
                    error_placeholders={"error_details": get_details(ex, True)},
                ) from ex

            if isinstance(ex.__cause__, ModbusClientFailedError):
                # This happens for things like UDP timeouts, inverter not connected to adapter, etc.
                # Annoyingly everything *seems* to come through as a ModbusIOException, so we can't tell exactly
                # what's going on. The error message here isn't useful to us. However, if it's got a __cause__ that can
                # be interesting, and if it doesn't the .response is useful
                client_failed_ex = ex.__cause__
                detail_parts = [str(client_failed_ex.response)]
                detail_parts.extend(record.message for record in ex.log_records)
                details = "; ".join(detail_parts)

                raise ValidationFailedError(
                    {"base": "other_inverter_error" if adapter.connection_type == LAN else "other_adapter_error"},
                    error_placeholders={"error_details": details},
                ) from ex

            raise ValidationFailedError(
                {"base": "other_inverter_error" if adapter.connection_type == LAN else "other_adapter_error"},
                error_placeholders={"error_details": get_details(ex, True)},
            ) from ex

    async def _setup_energy_dashboard(self) -> None:
        """Setup Energy Dashboard"""

        manager = await data.async_get_manager(self.hass)

        entity_id_prefixes = [x.entity_id_prefix for x in self._all_inverters]

        def _prefix_name(name: str | None) -> str:
            return f"sensor.{name}_" if name else "sensor."

        energy_prefs = EnergyPreferencesUpdate(energy_sources=[])  # type: ignore
        for entity_id_prefix in entity_id_prefixes:
            name_prefix = _prefix_name(entity_id_prefix)
            energy_prefs["energy_sources"].extend(
                [
                    SolarSourceType(
                        type="solar",
                        stat_energy_from=f"{name_prefix}pv1_energy_total",
                        config_entry_solar_forecast=None,
                    ),
                    SolarSourceType(
                        type="solar",
                        stat_energy_from=f"{name_prefix}pv2_energy_total",
                        config_entry_solar_forecast=None,
                    ),
                    BatterySourceType(
                        type="battery",
                        stat_energy_to=f"{name_prefix}battery_charge_total",
                        stat_energy_from=f"{name_prefix}battery_discharge_total",
                    ),
                ]
            )

        grid_source = GridSourceType(type="grid", flow_from=[], flow_to=[], cost_adjustment_day=0.0)
        for entity_id_prefix in entity_id_prefixes:
            name_prefix = _prefix_name(entity_id_prefix)
            grid_source["flow_from"].append(
                FlowFromGridSourceType(
                    stat_energy_from=f"{name_prefix}grid_consumption_energy_total",
                    stat_cost=None,
                    entity_energy_price=None,
                    number_energy_price=None,
                )
            )
            grid_source["flow_to"].append(
                FlowToGridSourceType(
                    stat_energy_to=f"{name_prefix}feed_in_energy_total",
                    stat_compensation=None,
                    entity_energy_price=None,
                    number_energy_price=None,
                )
            )
        energy_prefs["energy_sources"].append(grid_source)

        await manager.async_update(energy_prefs)

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        return ModbusOptionsHandler(config_entry)


class ModbusOptionsHandler(FlowHandlerMixin, config_entries.OptionsFlow):
    """Options flow handler"""

    def __init__(self, config: config_entries.ConfigEntry) -> None:
        self._config = config
        self._selected_inverter_id: str | None = None

    async def async_step_init(self, _user_input: dict[str, Any] | None = None) -> FlowResult:
        """Start the config flow"""

        if len(self._config.data[INVERTERS]) == 1:
            self._selected_inverter_id = next(iter(self._config.data[INVERTERS]))
            return await self.async_step_inverter_options()

        return await self.async_step_select_inverter()

    async def async_step_select_inverter(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Let the user select their inverter, if they have multiple inverters"""

        async def body(user_input: dict[str, Any]) -> FlowResult:
            self._selected_inverter_id = user_input["inverter"]
            return await self.async_step_inverter_options()

        schema = vol.Schema(
            {
                vol.Required("inverter"): selector(
                    {
                        "select": {
                            "options": [
                                {
                                    "label": self._create_label_for_inverter(inverter),
                                    "value": inverter_id,
                                }
                                for inverter_id, inverter in self._config.data[INVERTERS].items()
                            ]
                        }
                    }
                )
            }
        )

        return await self._with_default_form(body, user_input, "select_inverter", schema)

    async def async_step_inverter_options(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        """Let the user set the selected inverter's settings"""

        config = self._config.data[INVERTERS][self._selected_inverter_id]
        options = self._config.options.get(INVERTERS, {}).get(self._selected_inverter_id, {})

        current_adapter = ADAPTERS[options.get(ADAPTER_ID, config[ADAPTER_ID])]

        async def body(user_input: dict[str, Any]) -> FlowResult:
            inverter_options = {}

            # This won't be set if there's only a single adapter of that type, e.g. direct LAN conniction
            adapter_id = user_input.get("adapter_id", None)
            if adapter_id is not None and adapter_id != current_adapter.adapter_id:
                inverter_options[ADAPTER_ID] = adapter_id
            poll_rate = user_input.get("poll_rate")
            if poll_rate is not None:
                inverter_options[POLL_RATE] = poll_rate
            if user_input.get("round_sensor_values", False):
                inverter_options[ROUND_SENSOR_VALUES] = True
            max_read = user_input.get("max_read")
            if max_read is not None:
                inverter_options[MAX_READ] = max_read

            # We must not mutate any part of self._config.options, otherwise HA thinks we haven't changed the options
            options = copy.deepcopy(dict(self._config.options))
            options.setdefault(INVERTERS, {})[self._selected_inverter_id] = inverter_options

            return self.async_create_entry(title=_TITLE, data=options)

        adapters = [x for x in ADAPTERS.values() if x.adapter_type == current_adapter.adapter_type]

        schema_parts: dict[Any, Any] = {}
        if len(adapters) > 1:
            schema_parts[vol.Required("adapter_id", default=current_adapter.adapter_id)] = selector(
                {
                    "select": {
                        "options": [x.adapter_id for x in adapters],
                        "mode": "dropdown",
                        "translation_key": "inverter_adapter_models",
                    }
                }
            )

        schema_parts[vol.Required("round_sensor_values", default=options.get(ROUND_SENSOR_VALUES, False))] = selector(
            {"boolean": {}}
        )
        schema_parts[
            vol.Optional(
                "poll_rate",
                description={"suggested_value": options.get(POLL_RATE)},
            )
        ] = vol.Any(None, int)
        schema_parts[vol.Optional("max_read", description={"suggested_value": options.get(MAX_READ)})] = vol.Any(
            None, int
        )

        schema = vol.Schema(schema_parts)

        description_placeholders = {
            # TODO: Will need changing if we let them set the friendly name / host / port
            "inverter": self._create_label_for_inverter(config),
            "default_poll_rate": f"{current_adapter.poll_rate}",
            "default_max_read": f"{current_adapter.max_read}",
        }

        return await self._with_default_form(
            body,
            user_input,
            "inverter_options",
            schema,
            description_placeholders=description_placeholders,
        )


class ValidationFailedError(Exception):
    """Throw to cause a validation error to be shown"""

    def __init__(
        self,
        errors: dict[str, str],
        error_placeholders: dict[str, str] | None = None,
    ) -> None:
        self.errors = errors
        self.error_placeholders = error_placeholders
