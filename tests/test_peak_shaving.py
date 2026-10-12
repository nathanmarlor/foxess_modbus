"""Peak shaving settings and export power limit on the H3 with Manager >= 1.93."""

from typing import Any

import pytest

from custom_components.foxess_modbus.common.types import Inv
from custom_components.foxess_modbus.common.types import RegisterType
from custom_components.foxess_modbus.entities.entity_descriptions import ENTITIES

_NEW_KEYS = {"peak_shaving_threshold_soc", "export_peak_limit", "charge_in_low_import"}


def _serialized(inv: Inv) -> dict[tuple[str, str], dict[str, Any]]:
    result = {}
    for factory in ENTITIES:
        serialized = factory.serialize(inv, RegisterType.HOLDING)
        if serialized is not None:
            result[(serialized["type"], serialized["key"])] = serialized
    return result


def test_h3_193() -> None:
    entities = _serialized(Inv.H3_193)
    assert entities[("number", "import_power_limit")]["addresses"] == [46502, 46501]
    assert entities[("number", "peak_shaving_threshold_soc")]["addresses"] == [46503]
    assert entities[("number", "export_peak_limit")]["addresses"] == [46505, 46504]
    assert entities[("select", "charge_in_low_import")]["addresses"] == [46506]
    assert entities[("number", "export_power_limit")]["addresses"] == [46617, 46616]
    windows = [
        f"charge_in_low_time_{window}_{edge}_{unit}"
        for window in (1, 2)
        for edge in ("start", "end")
        for unit in ("hour", "minute")
    ]
    assert [entities[("sensor", key)]["addresses"] for key in windows] == [[a] for a in range(46507, 46515)]
    assert not any(("number", key) in entities for key in windows)


@pytest.mark.parametrize("inv", [Inv.H3_180, Inv.H3_PRE180, Inv.AIO_H3_101, Inv.KUARA_H3])
def test_older_h3_unchanged(inv: Inv) -> None:
    keys = {key for _, key in _serialized(inv)}
    assert not keys & (_NEW_KEYS | {"import_power_limit", "export_power_limit"})


@pytest.mark.parametrize("inv", [Inv.KH_133, Inv.H3_SMART])
def test_kh_and_h3_smart_unchanged(inv: Inv) -> None:
    entities = _serialized(inv)
    assert entities[("number", "import_power_limit")]["addresses"] == [46502, 46501]
    assert entities[("number", "export_power_limit")]["addresses"] == [46617, 46616]
    assert not {key for _, key in entities} & _NEW_KEYS
