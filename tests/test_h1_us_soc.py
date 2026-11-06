"""Battery SoC on the H1-US is in 0.1% steps, and must not leak float noise into the state."""

import pytest

from custom_components.foxess_modbus.common.types import Inv
from custom_components.foxess_modbus.common.types import RegisterType
from custom_components.foxess_modbus.entities.entity_descriptions import ENTITIES
from custom_components.foxess_modbus.entities.modbus_battery_sensor import ModbusBatterySensorDescription


def _h1_us_soc() -> ModbusBatterySensorDescription:
    for factory in ENTITIES:
        if (
            isinstance(factory, ModbusBatterySensorDescription)
            and factory.key == "battery_soc"
            and factory.serialize(Inv.H1_US, RegisterType.INPUT) is not None
        ):
            return factory
    raise AssertionError("H1-US battery_soc not found")


@pytest.mark.parametrize("raw", range(1001))
def test_soc_has_a_single_decimal(raw: int) -> None:
    description = _h1_us_soc()
    assert description.scale is not None
    assert description.post_process is not None

    value = description.post_process(raw * description.scale)

    # Exactly the nearest 0.1, with no float noise such as 87.30000000000001
    assert value == raw / 10
    assert str(value) == str(raw / 10)


def test_soc_suggests_one_decimal_for_display() -> None:
    assert _h1_us_soc().suggested_display_precision == 1
