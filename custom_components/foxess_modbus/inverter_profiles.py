"""Defines the different inverter models and connection types"""
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity

from .common.entity_controller import EntityController
from .const import AC1
from .const import AIO_H1
from .const import AUX
from .const import H1
from .const import INVERTER_BASE
from .const import INVERTER_CONN
from .const import LAN
from .entities import xx1_aux_charge_periods
from .entities import xx1_aux_entity_descriptions
from .entities import xx1_lan_entity_descriptions
from .entities.entity_factory import EntityFactory
from .entities.modbus_charge_period_config import ModbusChargePeriodConfig
from .entities.modbus_sensor import ModbusSensor
from .inverter_connection_types import CONNECTION_TYPES
from .inverter_connection_types import InverterConnectionType

_LOGGER = logging.getLogger(__package__)


class InverterModelConnectionTypeProfile:
    """Describes the capabilities of an inverter when connected to over a particular interface"""

    def __init__(
        self,
        connection_type: InverterConnectionType,
        entity_descriptions: list[EntityFactory],
        invalid_register_ranges: list[tuple[int, int]],
        charge_periods: list[ModbusChargePeriodConfig],
    ) -> None:
        self.connection_type = connection_type
        self.entity_descriptions = entity_descriptions
        self.invalid_register_ranges = invalid_register_ranges
        self.charge_periods = charge_periods

        for charge_period in charge_periods:
            self.entity_descriptions.extend(charge_period.entity_descriptions)

    def overlaps_invalid_range(self, start_address, end_address):
        return any(
            r[0] <= end_address and start_address <= r[1]
            for r in self.invalid_register_ranges
        )

    def create_entities(
        self,
        entity_type: type[Entity],
        controller: EntityController,
        entry: ConfigEntry,
        inverter_details: dict[str, Any],
    ) -> list[ModbusSensor]:
        """Create and return all entities of the given type"""
        return list(
            entity.create_entity(controller, entry, inverter_details)
            for entity in self.entity_descriptions
            if entity.entity_type == entity_type
        )


class InverterModelProfile:
    """Describes the capabilities of an inverter model"""

    def __init__(
        self, model: str, connection_types: list[InverterModelConnectionTypeProfile]
    ) -> None:
        self.model = model
        self.connection_types = {x.connection_type.key: x for x in connection_types}


INVERTER_PROFILES = {
    x.model: x
    for x in [
        InverterModelProfile(
            model=H1,
            connection_types=[
                InverterModelConnectionTypeProfile(
                    connection_type=CONNECTION_TYPES[AUX],
                    entity_descriptions=xx1_aux_entity_descriptions.H1
                    + xx1_aux_entity_descriptions.H1_AC1,
                    invalid_register_ranges=xx1_aux_entity_descriptions.INVALID_RANGES,
                    charge_periods=xx1_aux_charge_periods.H1_AC1,
                ),
                InverterModelConnectionTypeProfile(
                    connection_type=CONNECTION_TYPES[LAN],
                    entity_descriptions=xx1_lan_entity_descriptions.H1
                    + xx1_lan_entity_descriptions.H1_AC1,
                    invalid_register_ranges=[],
                    charge_periods=[],
                ),
            ],
        ),
        InverterModelProfile(
            model=AC1,
            connection_types=[
                InverterModelConnectionTypeProfile(
                    connection_type=CONNECTION_TYPES[AUX],
                    entity_descriptions=xx1_aux_entity_descriptions.AC1
                    + xx1_aux_entity_descriptions.H1_AC1,
                    invalid_register_ranges=xx1_aux_entity_descriptions.INVALID_RANGES,
                    charge_periods=xx1_aux_charge_periods.H1_AC1,
                ),
                InverterModelConnectionTypeProfile(
                    connection_type=CONNECTION_TYPES[LAN],
                    entity_descriptions=xx1_lan_entity_descriptions.H1_AC1,
                    invalid_register_ranges=[],
                    charge_periods=[],
                ),
            ],
        ),
        InverterModelProfile(
            model=AIO_H1,
            connection_types=[
                InverterModelConnectionTypeProfile(
                    connection_type=CONNECTION_TYPES[AUX],
                    entity_descriptions=xx1_aux_entity_descriptions.H1
                    + xx1_aux_entity_descriptions.H1_AC1,
                    invalid_register_ranges=xx1_aux_entity_descriptions.INVALID_RANGES,
                    charge_periods=xx1_aux_charge_periods.H1_AC1,
                ),
                InverterModelConnectionTypeProfile(
                    connection_type=CONNECTION_TYPES[LAN],
                    entity_descriptions=xx1_lan_entity_descriptions.H1
                    + xx1_lan_entity_descriptions.H1_AC1,
                    invalid_register_ranges=[],
                    charge_periods=[],
                ),
            ],
        ),
    ]
}


def inverter_connection_type_profile_from_config(
    inverter_config: dict[str, Any]
) -> InverterModelConnectionTypeProfile:
    """Fetches a InverterConnectionTypeProfile for a given configuration object"""

    return INVERTER_PROFILES[inverter_config[INVERTER_BASE]].connection_types[
        inverter_config[INVERTER_CONN]
    ]
