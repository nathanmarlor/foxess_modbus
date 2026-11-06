"""EPS power per phase on the H3-Pro / H3-Smart map (see #669)."""

import pytest

from custom_components.foxess_modbus.common.types import Inv
from custom_components.foxess_modbus.common.types import RegisterType
from custom_components.foxess_modbus.entities.entity_descriptions import ENTITIES


@pytest.mark.parametrize("inv", [Inv.H3_PRO_PRE122, Inv.H3_PRO_122, Inv.H3_SMART])
def test_eps_power_phases_follow_the_modbus_definition(inv: Inv) -> None:
    addresses = {}
    for factory in ENTITIES:
        serialized = factory.serialize(inv, RegisterType.HOLDING)
        if serialized is not None and serialized["key"] in ("eps_power_R", "eps_power_S", "eps_power_T"):
            addresses[serialized["key"]] = serialized["addresses"]
    # Lower-order word first: R is 39210-39211, S 39212-39213, T 39214-39215
    assert addresses == {
        "eps_power_R": [39211, 39210],
        "eps_power_S": [39213, 39212],
        "eps_power_T": [39215, 39214],
    }
