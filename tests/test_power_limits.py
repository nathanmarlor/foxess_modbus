"""Import / export power limit bounds (see #1322)."""

import pytest

from custom_components.foxess_modbus.common.types import Inv
from custom_components.foxess_modbus.common.types import RegisterType
from custom_components.foxess_modbus.entities.entity_descriptions import ENTITIES
from custom_components.foxess_modbus.entities.modbus_number import ModbusNumberDescription
from custom_components.foxess_modbus.entities.modbus_sensor import ModbusSensorDescription

# What an H3 Smart reports in 46501-46502 when no import limit has been set
NO_LIMIT_W = 100000


@pytest.mark.parametrize("key", ["import_power_limit", "export_power_limit"])
@pytest.mark.parametrize("inv", [Inv.KH_133, Inv.H3_SMART])
def test_power_limit_accepts_the_no_limit_value(key: str, inv: Inv) -> None:
    descriptions = [
        factory
        for factory in ENTITIES
        if isinstance(factory, ModbusSensorDescription | ModbusNumberDescription)
        and factory.key == key
        and factory.serialize(inv, RegisterType.HOLDING) is not None
    ]
    assert len(descriptions) == 2

    for description in descriptions:
        assert all(validator.validate(NO_LIMIT_W) for validator in description.validate)
        if isinstance(description, ModbusNumberDescription):
            assert description.native_max_value is not None
            assert description.native_max_value >= NO_LIMIT_W
