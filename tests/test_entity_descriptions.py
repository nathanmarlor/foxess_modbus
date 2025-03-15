from typing import Any
from typing import Iterable
from unittest.mock import MagicMock

import pytest
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.components.number import NumberEntity
from homeassistant.components.select import SelectEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant
from syrupy.assertion import SnapshotAssertion
from syrupy.extensions.json import JSONSnapshotExtension

from custom_components.foxess_modbus.common.types import Inv
from custom_components.foxess_modbus.const import ENTITY_ID_PREFIX
from custom_components.foxess_modbus.const import INVERTER_BASE
from custom_components.foxess_modbus.const import INVERTER_CONN
from custom_components.foxess_modbus.const import UNIQUE_ID_PREFIX
from custom_components.foxess_modbus.entities.entity_descriptions import ENTITIES
from custom_components.foxess_modbus.inverter_profiles import INVERTER_PROFILES
from custom_components.foxess_modbus.inverter_profiles import create_entities


@pytest.fixture
def snapshot_json(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    return snapshot.use_extension(extension_class=JSONSnapshotExtension)


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


def pytest_generate_tests(metafunc: Any) -> None:
    if "model" in metafunc.fixturenames:
        metafunc.parametrize("model", Inv)


def test_entity_descriptions_for_model(model: Inv, snapshot_json: SnapshotAssertion) -> None:
    # syrupy doesn't like keys which aren't strings
    def _process(d: Any) -> None:
        if isinstance(d, dict):
            for k, v in d.copy().items():
                if not isinstance(k, str):
                    del d[k]
                    d[str(k)] = v
                _process(v)
        elif isinstance(d, str):
            pass
        elif isinstance(d, Iterable):
            for v in d:
                _process(v)

    entities = []
    for entity_factory in ENTITIES:
        serialized = entity_factory.serialize(model)
        if serialized is not None:
            _process(serialized)
            entities.append(serialized)

    entities.sort(key=lambda x: x.get("key", ""))

    assert entities == snapshot_json
