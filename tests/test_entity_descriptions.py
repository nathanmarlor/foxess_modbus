from unittest.mock import MagicMock

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.number import NumberEntity
from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant

from custom_components.foxess_modbus.const import ENTITY_ID_PREFIX
from custom_components.foxess_modbus.const import INVERTER_BASE
from custom_components.foxess_modbus.const import INVERTER_CONN
from custom_components.foxess_modbus.const import UNIQUE_ID_PREFIX
from custom_components.foxess_modbus.inverter_profiles import INVERTER_PROFILES
from custom_components.foxess_modbus.inverter_profiles import create_entities


async def test_creates_all_entities(hass: HomeAssistant) -> None:
    controller = MagicMock()
    controller.hass = hass

    # config_entry = MockConfigEntry()

    for profile in INVERTER_PROFILES.values():
        for connection_type in profile.connection_types:
            for entity_type in [SensorEntity, BinarySensorEntity, SelectEntity, NumberEntity]:
                controller.inverter_details = {
                    INVERTER_BASE: profile.model,
                    INVERTER_CONN: connection_type,
                    ENTITY_ID_PREFIX: "",
                    UNIQUE_ID_PREFIX: "",
                }
                # Asserts if e.g. the ModbusAddressSpecs match
                create_entities(entity_type, controller)
