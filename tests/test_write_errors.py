"""A failed write reaches the user as a HomeAssistantError, not as an unknown error."""

from collections.abc import AsyncIterator
from unittest.mock import AsyncMock
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from custom_components.foxess_modbus.client.modbus_client import ModbusClientFailedError
from custom_components.foxess_modbus.common.types import ConnectionType
from custom_components.foxess_modbus.common.types import InverterModel
from custom_components.foxess_modbus.const import ENTITY_ID_PREFIX
from custom_components.foxess_modbus.const import FRIENDLY_NAME
from custom_components.foxess_modbus.const import INVERTER_BASE
from custom_components.foxess_modbus.const import INVERTER_CONN
from custom_components.foxess_modbus.const import INVERTER_MODEL
from custom_components.foxess_modbus.const import UNIQUE_ID_PREFIX
from custom_components.foxess_modbus.inverter_profiles import inverter_connection_type_profile_from_config
from custom_components.foxess_modbus.modbus_controller import ModbusController
from custom_components.foxess_modbus.vendor.pymodbus import ModbusIOException


@pytest.fixture
def client() -> MagicMock:
    client = MagicMock()
    client.write_registers = AsyncMock()
    return client


@pytest.fixture
async def controller(hass: HomeAssistant, client: MagicMock) -> AsyncIterator[ModbusController]:
    inverter = {
        INVERTER_BASE: InverterModel.H3,
        INVERTER_CONN: ConnectionType.AUX,
        INVERTER_MODEL: "H3-5.0-E",
        FRIENDLY_NAME: "",
        ENTITY_ID_PREFIX: "",
        UNIQUE_ID_PREFIX: "",
    }
    controller = ModbusController(
        hass, client, inverter_connection_type_profile_from_config(inverter), inverter, 247, 10, 50
    )
    yield controller
    controller.unload()


async def test_failed_write_raises_home_assistant_error(controller: ModbusController, client: MagicMock) -> None:
    error = ModbusClientFailedError("Error writing registers", MagicMock(), ModbusIOException("timeout"))
    client.write_registers.side_effect = error
    with pytest.raises(HomeAssistantError, match="Error writing registers") as raised:
        await controller.write_registers(41009, [20])
    assert raised.value.__cause__ is error


async def test_out_of_range_value_raises_home_assistant_error(controller: ModbusController, client: MagicMock) -> None:
    with pytest.raises(HomeAssistantError, match="must be between"):
        await controller.write_registers(41009, [70000])
    client.write_registers.assert_not_called()
