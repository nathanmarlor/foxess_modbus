"""H3 with Manager >= 1.93: charge periods on time groups 1 and 2, like the H3 Smart / Pro."""

from typing import Any

import pytest

from custom_components.foxess_modbus.common.types import Inv
from custom_components.foxess_modbus.common.types import RegisterType
from custom_components.foxess_modbus.entities.entity_descriptions import ENTITIES


def _serialized(inv: Inv) -> dict[str, dict[str, Any]]:
    result = {}
    for factory in ENTITIES:
        serialized = factory.serialize(inv, RegisterType.HOLDING)
        if serialized is not None:
            result[serialized["key"]] = serialized
    return result


def test_same_charge_periods_as_h3_smart() -> None:
    h3 = _serialized(Inv.H3_193)
    smart = _serialized(Inv.H3_SMART)
    for period in (1, 2):
        for suffix in ("start", "end", "enable_force_charge", "enable_charge_from_grid"):
            key = f"time_period_{period}_{suffix}"
            assert h3[key] == smart[key], key
    assert h3["time_period_1_start"]["addresses"] == [48011]
    assert h3["time_period_2_end"]["addresses"] == [48022]


@pytest.mark.parametrize("inv", [Inv.H3_180, Inv.H3_PRE180, Inv.AIO_H3_101, Inv.KUARA_H3])
def test_older_h3_has_no_charge_periods(inv: Inv) -> None:
    assert not any(key.startswith("time_period_") for key in _serialized(inv))
