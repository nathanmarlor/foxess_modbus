from typing import TYPE_CHECKING
from typing import Any
from typing import Awaitable
from typing import Callable

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlowResult

from ..const import ADAPTER_ID
from ..const import ENTITY_ID_PREFIX
from ..const import FRIENDLY_NAME
from ..const import HOST
from ..const import INVERTER_BASE
from ..const import INVERTER_CONN
from ..const import INVERTER_MODEL
from ..const import MODBUS_SLAVE
from ..const import MODBUS_TYPE
from ..const import UNIQUE_ID_PREFIX
from ..inverter_adapters import ADAPTERS
from .inverter_data import InverterData

if TYPE_CHECKING:
    _FlowHandlerMixinBase = config_entries.ConfigFlow
else:
    _FlowHandlerMixinBase = object


class FlowHandlerMixin(_FlowHandlerMixinBase):
    """Mixin for config flow / options flow classes, providing common functionality"""

    async def with_default_form(
        self,
        body: Callable[[dict[str, Any]], Awaitable[ConfigFlowResult | None]],
        user_input: dict[str, Any] | None,
        step_id: str,
        data_schema: vol.Schema,
        *,
        suggested_values: dict[str, Any] | None = None,
        description_placeholders: dict[str, str] | None = None,
    ) -> ConfigFlowResult:
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
        if suggested_values:
            schema_with_input = self.add_suggested_values_to_schema(schema_with_input, suggested_values)
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

    def _inverter_data_to_dict(self, inverter: InverterData) -> dict[str, Any]:
        assert inverter.adapter is not None
        inverter_config = {
            ADAPTER_ID: inverter.adapter.adapter_id,
            INVERTER_BASE: inverter.inverter_base_model,
            INVERTER_MODEL: inverter.inverter_model,
            INVERTER_CONN: inverter.adapter.connection_type,
            MODBUS_SLAVE: inverter.modbus_slave,
            MODBUS_TYPE: inverter.inverter_protocol,
            HOST: inverter.host,
            ENTITY_ID_PREFIX: inverter.entity_id_prefix if inverter.entity_id_prefix else "",
            UNIQUE_ID_PREFIX: inverter.unique_id_prefix if inverter.unique_id_prefix else "",
            FRIENDLY_NAME: inverter.friendly_name if inverter.friendly_name else "",
        }
        return inverter_config

    def _dict_to_inverter_data(self, config: dict[str, Any]) -> InverterData:
        adapter = ADAPTERS[config[ADAPTER_ID]]
        inverter_data = InverterData(
            adapter_type=adapter.adapter_type,
            adapter=adapter,
            inverter_base_model=config[INVERTER_BASE],
            inverter_model=config[INVERTER_MODEL],
            modbus_slave=config[MODBUS_SLAVE],
            inverter_protocol=config[MODBUS_TYPE],
            host=config[HOST],
            entity_id_prefix=config[ENTITY_ID_PREFIX] if config[ENTITY_ID_PREFIX] else None,
            unique_id_prefix=config[UNIQUE_ID_PREFIX] if config[UNIQUE_ID_PREFIX] else None,
            friendly_name=config[FRIENDLY_NAME] if config[ENTITY_ID_PREFIX] else None,
        )
        return inverter_data


class ValidationFailedError(Exception):
    """Throw to cause a validation error to be shown"""

    def __init__(
        self,
        errors: dict[str, str],
        error_placeholders: dict[str, str] | None = None,
    ) -> None:
        self.errors = errors
        self.error_placeholders = error_placeholders
