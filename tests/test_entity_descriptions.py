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

from custom_components.foxess_modbus.common.types import ConnectionType
from custom_components.foxess_modbus.common.types import InverterModel
from custom_components.foxess_modbus.const import ENTITY_ID_PREFIX
from custom_components.foxess_modbus.const import INVERTER_BASE
from custom_components.foxess_modbus.const import INVERTER_CONN
from custom_components.foxess_modbus.const import UNIQUE_ID_PREFIX
from custom_components.foxess_modbus.entities.entity_descriptions import ENTITIES
from custom_components.foxess_modbus.inverter_profiles import INVERTER_PROFILES
from custom_components.foxess_modbus.inverter_profiles import Version
from custom_components.foxess_modbus.inverter_profiles import create_entities


@pytest.fixture
def snapshot_json(snapshot: SnapshotAssertion) -> SnapshotAssertion:
    return snapshot.use_extension(extension_class=JSONSnapshotExtension)


async def test_creates_all_entities(hass: HomeAssistant) -> None:
    controller = MagicMock()
    controller.hass = hass

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


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "model" in metafunc.fixturenames:
        inputs = []
        for model, profile in INVERTER_PROFILES.items():
            for connection_type, connection_type_profile in profile.connection_types.items():
                for version in connection_type_profile.versions:
                    v = "latest" if version is None else f"v{version}"
                    inputs.append((model, connection_type, v))

        metafunc.parametrize(("model", "connection_type", "version"), inputs)


def test_entities(
    model: InverterModel, connection_type: ConnectionType, version: str, snapshot_json: SnapshotAssertion
) -> None:
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

    connection_type_profile = INVERTER_PROFILES[model].connection_types[connection_type]
    v = None if version == "latest" else Version.parse(version.lstrip("v"))
    inv = connection_type_profile.get_inv_for_version(v)

    entities = []
    for entity_factory in ENTITIES:
        serialized = entity_factory.serialize(inv, connection_type_profile.register_type)
        if serialized is not None:
            _process(serialized)
            entities.append(serialized)

    entities.sort(key=lambda x: x.get("key", ""))

    assert entities == snapshot_json
