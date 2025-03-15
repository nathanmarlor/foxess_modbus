import copy
from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers.selector import selector

from ..const import ADAPTER_ID
from ..const import CONFIG_ENTRY_TITLE
from ..const import INVERTER_VERSION
from ..const import INVERTERS
from ..const import MAX_READ
from ..const import MODBUS_TYPE
from ..const import POLL_RATE
from ..const import ROUND_SENSOR_VALUES
from ..inverter_adapters import ADAPTERS
from ..inverter_profiles import Version
from ..inverter_profiles import inverter_connection_type_profile_from_config
from .adapter_flow_segment import AdapterFlowSegment
from .flow_handler_mixin import FlowHandlerMixin


class OptionsHandler(FlowHandlerMixin, config_entries.OptionsFlow):
    """Options flow handler"""

    def __init__(self, config: config_entries.ConfigEntry) -> None:
        self._config = config
        self._selected_inverter_id: str | None = None

        self._adapter_segment: AdapterFlowSegment | None = None

    async def async_step_init(self, _user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Start the config flow"""

        if len(self._config.data[INVERTERS]) == 1:
            self._selected_inverter_id = next(iter(self._config.data[INVERTERS]))
            return await self.async_step_inverter_options_category()

        return await self.async_step_select_inverter()

    async def async_step_select_inverter(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user select their inverter, if they have multiple inverters"""

        async def body(user_input: dict[str, Any]) -> ConfigFlowResult:
            self._selected_inverter_id = user_input["inverter"]
            return await self.async_step_inverter_options_category()

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
                                for inverter_id, inverter in self._combined_config_for_all_inverters().items()
                            ]
                        }
                    }
                )
            }
        )

        return await self.with_default_form(body, user_input, "select_inverter", schema)

    async def async_step_inverter_options_category(self, _user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user choose what sort of inverter options to configure"""

        assert self._selected_inverter_id is not None

        _, _, combined_config_options = self._config_for_inverter(self._selected_inverter_id)
        versions = inverter_connection_type_profile_from_config(combined_config_options).versions

        options = ["select_adapter_type"]
        if len(versions) > 1:
            options.append("version_settings")
        options.append("inverter_advanced_options")

        return self.async_show_menu(step_id="inverter_options_category", menu_options=options)

    async def async_step_select_adapter_type(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        async def adapter_segment_complete() -> ConfigFlowResult:
            assert self._adapter_segment is not None
            assert self._selected_inverter_id is not None

            _, options, _ = self._config_for_inverter(self._selected_inverter_id)
            options.update(self._inverter_data_to_dict(self._adapter_segment.inverter_data))
            self._adapter_segment = None

            return self._save_selected_inverter_options(options)

        if self._adapter_segment is None:
            inverter_configs = self._combined_config_for_all_inverters()
            other_inverters = []
            for inverter_id, _combined_config in inverter_configs.items():
                inverter_data = self._dict_to_inverter_data(_combined_config)
                if inverter_id == self._selected_inverter_id:
                    selected_inverter_data = inverter_data
                else:
                    other_inverters.append(inverter_data)
            self._adapter_segment = AdapterFlowSegment(
                self, selected_inverter_data, other_inverters, adapter_segment_complete
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

    async def async_step_version_settings(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user configure their inverter version"""
        assert self._selected_inverter_id is not None

        _, options, combined_config_options = self._config_for_inverter(self._selected_inverter_id)

        async def body(user_input: dict[str, Any]) -> ConfigFlowResult:
            version = user_input.get("version")
            if version is None or version == "latest":
                options.pop(INVERTER_VERSION, None)
            else:
                options[INVERTER_VERSION] = version

            return self._save_selected_inverter_options(options)

        schema_parts: dict[Any, Any] = {}

        versions: list[Version | None] = sorted(  # type: ignore[type-var]
            inverter_connection_type_profile_from_config(combined_config_options).versions.keys()
        )
        assert len(versions) > 1

        version_options = []
        prev_version = None
        # The last element will be None, which means "latest"
        for version in versions[:-1]:
            assert version is not None
            # For the sake of clarity, we'll shown an exclusive range as the version one minor version below
            # (We don't know whether that version ever actually existed, but that doesn't matter here)
            if prev_version is None:
                label = f"Earlier than {version}"
            else:
                inclusive_end = Version(version.major, version.minor - 1)
                label = f"{inclusive_end}" if inclusive_end == prev_version else f"{prev_version} - {inclusive_end}"

            version_options.append({"label": label, "value": str(version)})
            prev_version = version
        version_options.append({"label": f"{versions[-2]} and higher", "value": "latest"})  # hass can't cope with None

        schema_parts[vol.Required("version", default=options.get(INVERTER_VERSION, "latest"))] = selector(
            {
                "select": {
                    "options": list(reversed(version_options)),
                    "mode": "dropdown",
                }
            }
        )

        schema = vol.Schema(schema_parts)

        description_placeholders = {
            # TODO: Will need changing if we let them set the friendly name / host / port
            "inverter": self._create_label_for_inverter(combined_config_options),
        }
        return await self.with_default_form(
            body,
            user_input,
            "version_settings",
            schema,
            description_placeholders=description_placeholders,
        )

    async def async_step_inverter_advanced_options(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user set the selected inverter's advanced settings"""

        assert self._selected_inverter_id is not None

        _, options, combined_config_options = self._config_for_inverter(self._selected_inverter_id)

        current_adapter = ADAPTERS[combined_config_options[ADAPTER_ID]]

        async def body(user_input: dict[str, Any]) -> ConfigFlowResult:
            poll_rate = user_input.get("poll_rate")
            if poll_rate is not None:
                options[POLL_RATE] = poll_rate
            else:
                options.pop(POLL_RATE, None)

            if user_input.get("round_sensor_values", False):
                options[ROUND_SENSOR_VALUES] = True
            else:
                options.pop(ROUND_SENSOR_VALUES, None)

            max_read = user_input.get("max_read")
            if max_read is not None:
                options[MAX_READ] = max_read
            else:
                options.pop(MAX_READ, None)

            return self._save_selected_inverter_options(options)

        schema_parts: dict[Any, Any] = {}

        schema_parts[vol.Required("round_sensor_values", default=options.get(ROUND_SENSOR_VALUES, False))] = selector(
            {"boolean": {}}
        )
        schema_parts[
            vol.Optional(
                "poll_rate",
                description={"suggested_value": options.get(POLL_RATE)},
            )
        ] = vol.Any(None, vol.All(int, vol.Range(min=1)))
        schema_parts[vol.Optional("max_read", description={"suggested_value": options.get(MAX_READ)})] = vol.Any(
            None, vol.All(int, vol.Range(min=1))
        )

        schema = vol.Schema(schema_parts)

        inverter_config = current_adapter.config.inverter_config(combined_config_options[MODBUS_TYPE])
        description_placeholders = {
            # TODO: Will need changing if we let them set the friendly name / host / port
            "inverter": self._create_label_for_inverter(combined_config_options),
            "default_poll_rate": f"{inverter_config[POLL_RATE]}",
            "default_max_read": f"{inverter_config[MAX_READ]}",
        }

        return await self.with_default_form(
            body,
            user_input,
            "inverter_advanced_options",
            schema,
            description_placeholders=description_placeholders,
        )

    def _save_selected_inverter_options(self, inverter_options: dict[str, Any]) -> ConfigFlowResult:
        # We must not mutate any part of self._config.options, otherwise HA thinks we haven't changed the options
        options = copy.deepcopy(dict(self._config.options))
        options.setdefault(INVERTERS, {})[self._selected_inverter_id] = inverter_options

        return self.async_create_entry(title=CONFIG_ENTRY_TITLE, data=options)

    # Returns config, options, combined
    def _config_for_inverter(self, inverter_id: str) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
        config = copy.deepcopy(dict(self._config.data[INVERTERS].get(inverter_id, {})))
        options = copy.deepcopy(dict(self._config.options.get(INVERTERS, {}).get(inverter_id, {})))
        combined = copy.deepcopy(config)
        combined.update(options)
        return config, options, combined

    def _combined_config_for_all_inverters(self) -> dict[str, Any]:
        inverter_ids: set[str] = {
            *self._config.data[INVERTERS].keys(),
            *self._config.options.get(INVERTERS, {}).keys(),
        }
        result = {}
        for inverter_id in inverter_ids:
            _, _, combined = self._config_for_inverter(inverter_id)
            result[inverter_id] = combined

        return result
