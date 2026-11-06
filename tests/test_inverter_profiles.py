import re

import pytest

from custom_components.foxess_modbus.common.types import InverterModel
from custom_components.foxess_modbus.inverter_profiles import INVERTER_PROFILES


def _detect(model: str) -> InverterModel:
    """Mirror the autodetect logic in modbus_controller (first matching profile wins)."""
    for profile in INVERTER_PROFILES.values():
        if re.match(profile.model_pattern, model):
            # The controller also requires the capacity to be parseable
            profile.inverter_capacity(model)
            return profile.model
    raise AssertionError(f"no profile matched '{model}'")


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        # H3-Smart, as reported by most firmwares
        ("H3-12.0-Smart", InverterModel.H3_SMART),
        ("H3-15.0-Smart", InverterModel.H3_SMART),
        # Uppercase variant, seen with Manager 1.28+ (issues #1201, #1225)
        ("H3-12.0-SMART", InverterModel.H3_SMART),
        ("H3-15.0-SMART", InverterModel.H3_SMART),
        # OEM/installer variant of the H3-Smart (issue #1023)
        ("H3-10.0-M", InverterModel.H3_SMART),
        ("H3-12.0-M", InverterModel.H3_SMART),
        # Plain H3 must still fall through to the legacy profile
        ("H3-12.0", InverterModel.H3),
        ("H3-5.0-E", InverterModel.H3),
    ],
)
def test_h3_model_detection(model: str, expected: InverterModel) -> None:
    assert _detect(model) == expected
