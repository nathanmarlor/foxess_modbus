import re
import uuid
from datetime import datetime
from datetime import timezone
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
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import selector
from slugify import slugify

from ..const import CONFIG_ENTRY_TITLE
from ..const import CONFIG_SAVE_TIME
from ..const import DOMAIN
from ..const import INVERTERS
from ..inverter_adapters import ADAPTERS
from ..inverter_adapters import InverterAdapter
from ..inverter_adapters import InverterAdapterType
from .adapter_flow_segment import AdapterFlowSegment
from .flow_handler_mixin import FlowHandlerMixin
from .inverter_data import InverterData
from .options_handler import OptionsHandler


class FlowHandler(FlowHandlerMixin, config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for foxess_modbus."""

    VERSION = 7
    CONNECTION_CLASS = config_entries.CONN_CLASS_LOCAL_POLL

    def __init__(self) -> None:
        """Initialize."""
        self._inverter_data = InverterData()
        self._all_inverters: list[InverterData] = []

        self._adapter_segment: AdapterFlowSegment | None = None

    async def async_step_user(self, _user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Handle a flow initialized by the user."""

        await self.async_set_unique_id(DOMAIN)
        self._abort_if_unique_id_configured()

        return await self.async_step_select_adapter_type()

    async def async_step_select_adapter_type(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        async def adapter_segment_complete() -> ConfigFlowResult:
            self._adapter_segment = None
            return await self.async_step_friendly_name()

        if self._adapter_segment is None:
            self._adapter_segment = AdapterFlowSegment(
                self, self._inverter_data, self._all_inverters, adapter_segment_complete
            )
        return await self._adapter_segment.async_step_select_adapter_type(user_input)

    async def async_step_select_adapter_model(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        assert self._adapter_segment is not None
        return await self._adapter_segment.async_step_select_adapter_model(user_input)

    async def async_step_tcp_adapter(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        assert self._adapter_segment is not None
        return await self._adapter_segment.async_step_tcp_adapter(user_input)

    async def async_step_serial_adapter(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        assert self._adapter_segment is not None
        return await self._adapter_segment.async_step_serial_adapter(user_input)

    async def async_step_friendly_name(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user enter a friendly name for their inverter"""

        # This is a bit involved, so we'll avoid _with_default_form

        def generate_entity_id_prefix(friendly_name: str | None) -> str:
            return slugify(friendly_name, separator="_").strip("_") if friendly_name else ""

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
                # It would probably make more sense to use the entity_id_prefix here, but for a long time the
                # friendly_name and entity_id_prefix were the same (i.e. not slugified). We keep this behaviour
                # (allowing spaces, special chars, etc in the friendly name) so that if someone removes and
                # re-adds the integration using the same friendly_name, their unique IDs stay the same.
                self._inverter_data.unique_id_prefix = friendly_name
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

    async def async_step_add_another_inverter(self, _user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user choose whether to add another inverter"""

        options = ["select_adapter_type", "energy"]
        return self.async_show_menu(step_id="add_another_inverter", menu_options=options)

    async def async_step_energy(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user choose whether to set up the energy dashboard"""

        async def body(user_input: dict[str, Any]) -> ConfigFlowResult:
            if user_input["energy_dashboard"]:
                await self._setup_energy_dashboard()
            return self.async_create_entry(title=CONFIG_ENTRY_TITLE, data=self._create_entry_data())

        schema = vol.Schema(
            {
                vol.Required("energy_dashboard", default=False): bool,
            }
        )

        return await self.with_default_form(body, user_input, "energy", schema)

    def _create_entry_data(self) -> dict[str, Any]:
        """Create the config entry for all inverters in self._all_inverters"""

        entry: dict[str, Any] = {INVERTERS: {}}
        for inverter in self._all_inverters:
            inverter_config = self._inverter_data_to_dict(inverter)
            entry[INVERTERS][str(uuid.uuid4())] = inverter_config
        entry[CONFIG_SAVE_TIME] = datetime.now(timezone.utc)
        return entry

    async def _select_adapter_model_helper(
        self,
        step_id: str,
        user_input: dict[str, Any] | None,
        adapter_type: InverterAdapterType,
        complete_callback: Callable[[InverterAdapter], Awaitable[ConfigFlowResult]],
        description_placeholders: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
        """Helper used in the steps which let the user select their adapter model"""

        async def body(user_input: dict[str, Any]) -> ConfigFlowResult:
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

        return await self.with_default_form(
            body,
            user_input,
            step_id,
            schema,
            description_placeholders=description_placeholders,
        )

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
        return OptionsHandler(config_entry)
