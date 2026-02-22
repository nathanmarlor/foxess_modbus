import re
from typing import Any
from typing import Awaitable
from typing import Callable

import voluptuous as vol
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.selector import selector

from ..client.modbus_client import ModbusClient
from ..client.modbus_client import ModbusClientFailedError
from ..common.exceptions import AutoconnectFailedError
from ..common.exceptions import UnsupportedInverterError
from ..common.types import ConnectionType
from ..const import RTU_OVER_TCP
from ..const import SERIAL
from ..const import TCP
from ..const import UDP
from ..inverter_adapters import ADAPTERS
from ..inverter_adapters import InverterAdapter
from ..inverter_adapters import InverterAdapterType
from ..modbus_controller import ModbusController
from ..vendor.pymodbus import ConnectionException
from ..vendor.pymodbus import ModbusIOException
from .flow_handler_mixin import FlowHandlerMixin
from .flow_handler_mixin import ValidationFailedError
from .inverter_data import InverterData

_DEFAULT_PORT = 502
_DEFAULT_SLAVE = 247


class AdapterFlowSegment:
    def __init__(
        self,
        flow: FlowHandlerMixin,
        inverter_data: InverterData,
        other_inverters: list[InverterData],
        on_complete: Callable[[], Awaitable[ConfigFlowResult]],
    ) -> None:
        self._flow = flow
        self._on_complete = on_complete

        self.inverter_data = inverter_data
        self._other_inverters = other_inverters

        self._adapter_type_to_step = {
            InverterAdapterType.DIRECT: self.async_step_tcp_adapter,
            InverterAdapterType.SERIAL: self.async_step_serial_adapter,
            InverterAdapterType.NETWORK: self.async_step_tcp_adapter,
        }

    async def async_step_select_adapter_type(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user select their adapter type"""

        async def body(user_input: dict[str, Any]) -> ConfigFlowResult:
            adapter_type = InverterAdapterType(user_input["adapter_type"])
            self.inverter_data.adapter_type = adapter_type

            adapters = [x for x in ADAPTERS.values() if x.adapter_type == adapter_type]

            assert len(adapters) > 0
            if len(adapters) == 1:
                self.inverter_data.adapter = adapters[0]
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

        suggested_values: dict[str, Any] = {}
        if self.inverter_data.adapter_type is not None:
            suggested_values["adapter_type"] = self.inverter_data.adapter_type.value
        return await self._flow.with_default_form(
            body, user_input, "select_adapter_type", schema, suggested_values=suggested_values
        )

    async def async_step_select_adapter_model(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user select their adapter model"""

        async def body(user_input: dict[str, Any]) -> ConfigFlowResult:
            self.inverter_data.adapter = ADAPTERS[user_input["adapter_model"]]
            assert self.inverter_data.adapter_type is not None
            return await self._adapter_type_to_step[self.inverter_data.adapter_type]()

        adapters = [x for x in ADAPTERS.values() if x.adapter_type == self.inverter_data.adapter_type]

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

        suggested_values: dict[str, Any] = {}
        if self.inverter_data.adapter is not None:
            suggested_values["adapter_model"] = self.inverter_data.adapter.adapter_id
        return await self._flow.with_default_form(
            body,
            user_input,
            "select_adapter_model",
            schema,
            suggested_values=suggested_values,
        )

    async def async_step_tcp_adapter(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user enter connection details for their TCP/UDP/RTU_OVER_TCP adapter"""

        adapter = self.inverter_data.adapter

        async def body(user_input: dict[str, Any]) -> ConfigFlowResult:
            assert adapter is not None
            assert adapter.network_protocols is not None
            protocol = user_input.get(
                "protocol",
                user_input.get("protocol_with_recommendation", adapter.network_protocols[0]),
            )
            host = user_input.get("adapter_host", user_input.get("lan_connection_host"))
            self._validate_hostname(host)
            assert host is not None
            port = user_input.get("adapter_port", _DEFAULT_PORT)
            host_and_port = f"{host}:{port}"
            slave = user_input.get("modbus_slave", _DEFAULT_SLAVE)
            await self._autodetect_modbus_and_save_to_inverter_data(protocol, host_and_port, slave, adapter)
            return await self._on_complete()

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

        if adapter.connection_type == ConnectionType.AUX:
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

        suggested_values: dict[str, Any] = {}
        if self.inverter_data.inverter_protocol is not None:
            suggested_values["protocol"] = self.inverter_data.inverter_protocol
            suggested_values["protocol_with_recommendation"] = self.inverter_data.inverter_protocol
        # If they've switched from network to serial or vice versa, don't recommend their previous host...
        if self.inverter_data.host is not None and self.inverter_data.inverter_protocol in [TCP, UDP, RTU_OVER_TCP]:
            host_parts = self.inverter_data.host.split(":")
            suggested_values["adapter_host"] = host_parts[0]
            suggested_values["adapter_port"] = int(host_parts[1])
            suggested_values["lan_connection_host"] = host_parts[0]
        if self.inverter_data.modbus_slave is not None:
            suggested_values["modbus_slave"] = self.inverter_data.modbus_slave

        return await self._flow.with_default_form(
            body,
            user_input,
            "tcp_adapter",
            schema,
            suggested_values=suggested_values,
            description_placeholders=description_placeholders,
        )

    async def async_step_serial_adapter(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        """Let the user enter connection details for their serial adapter"""

        adapter = self.inverter_data.adapter

        async def body(user_input: dict[str, Any]) -> ConfigFlowResult:
            assert adapter is not None
            device = user_input["serial_device"]
            slave = user_input.get("modbus_slave", _DEFAULT_SLAVE)
            await self._autodetect_modbus_and_save_to_inverter_data(SERIAL, device, slave, adapter)
            return await self._on_complete()

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

        suggested_values: dict[str, Any] = {}
        # If they've switched from network to serial or vice versa, don't recommend their previous host...
        if self.inverter_data.host is not None and self.inverter_data.inverter_protocol == SERIAL:
            suggested_values["serial_device"] = self.inverter_data.host
        if self.inverter_data.modbus_slave is not None:
            suggested_values["modbus_slave"] = self.inverter_data.modbus_slave
        return await self._flow.with_default_form(
            body,
            user_input,
            "serial_adapter",
            schema,
            suggested_values=suggested_values,
            description_placeholders=description_placeholders,
        )

    async def _autodetect_modbus_and_save_to_inverter_data(
        self,
        protocol: str,
        host: str,
        slave: int,
        adapter: InverterAdapter,
    ) -> None:
        """
        Check that connection details are unique, then connect to the inverter and add its details to
        self._inverter_data
        """

        if any(
            x
            for x in self._other_inverters
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
            client = ModbusClient(self._flow.hass, protocol, adapter, params)
            base_model, full_model = await ModbusController.autodetect(
                client, slave, adapter.config.inverter_config(protocol)
            )

            self.inverter_data.inverter_base_model = base_model
            self.inverter_data.inverter_model = full_model
            self.inverter_data.inverter_protocol = protocol
            self.inverter_data.modbus_slave = slave
            self.inverter_data.host = host
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
                    parts.extend({record.message for record in ex.log_records})
                    result = "; ".join(parts)
                else:
                    # Oh. Fall back
                    result = str(ex.__cause__)
                return result

            if isinstance(ex.__cause__, ConnectionException):
                # Mainly TCP timeouts. The actual exception message dosen't contain anything interesting here
                raise ValidationFailedError(
                    {
                        "base": (
                            "unable_to_connect_to_inverter"
                            if adapter.connection_type == ConnectionType.LAN
                            else "unable_to_connect_to_adapter"
                        )
                    },
                    error_placeholders={"error_details": get_details(ex, False)},
                ) from ex

            if isinstance(ex.__cause__, ModbusIOException):
                # This is for things like invalid frames. The exception message here can be useful
                raise ValidationFailedError(
                    {
                        "base": (
                            "unable_to_communicate_with_inverter"
                            if adapter.connection_type == ConnectionType.LAN
                            else "adapter_unable_to_communicate_with_inverter"
                        )
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
                    {
                        "base": (
                            "other_inverter_error"
                            if adapter.connection_type == ConnectionType.LAN
                            else "other_adapter_error"
                        )
                    },
                    error_placeholders={"error_details": details},
                ) from ex

            raise ValidationFailedError(
                {
                    "base": (
                        "other_inverter_error"
                        if adapter.connection_type == ConnectionType.LAN
                        else "other_adapter_error"
                    )
                },
                error_placeholders={"error_details": get_details(ex, True)},
            ) from ex

    def _validate_hostname(self, host: str) -> None:
        if not re.fullmatch(r"[a-zA-Z0-9\.\-]+", host):
            raise ValidationFailedError({"base": "invalid_hostname"}, error_placeholders={"hostname": host})
