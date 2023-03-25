"""Defines the different inverter models and connection types"""
import logging
from typing import Any
from typing import Iterable

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity import Entity

from .common.entity_controller import EntityController
from .const import INVERTER_BASE
from .const import INVERTER_CONN
from .entities import xx1_aux_charge_periods
from .entities import xx1_aux_entity_descriptions
from .entities import xx1_lan_entity_descriptions
from .entities.modbus_charge_period_config import ModbusChargePeriodConfig
from .entities.modbus_entity_description_base import ModbusEntityDescriptionBase
from .entities.modbus_sensor import ModbusSensor
from .inverter_connection_types import CONNECTION_TYPES
from .inverter_connection_types import InverterConnectionType

_LOGGER = logging.getLogger(__package__)


class InverterModelConnectionTypeProfile:
    """Describes the capabilities of an inverter when connected to over a particular interface"""

    def __init__(
        self,
        connection_type: InverterConnectionType,
        entity_descriptions: list[ModbusEntityDescriptionBase],
        charge_periods: list[ModbusChargePeriodConfig],
    ) -> None:
        self.connection_type = connection_type
        self.entity_descriptions = entity_descriptions
        self.charge_periods = charge_periods

        for charge_period in charge_periods:
            self.entity_descriptions.extend(charge_period.entity_descriptions)

        self.all_addresses = sorted(
            set(
                (
                    address
                    for entity in self.entity_descriptions
                    for address in entity.addresses
                ),
            )
        )

    def create_read_ranges(self, max_read: int) -> Iterable[tuple[int, int]]:
        """
        Generates a set of read ranges to cover the addresses of all registers on this inverter,
        respecting the maxumum number of registers to read at a time

        :returns: Sequence of tuples of (start_address, num_registers_to_read)
        """

        # The idea here is that read operations are expensive (there seems to be a large round-trip time at least
        # with the W610), but reading additional unneeded registers is relatively cheap (probably < 1ms).

        # To give some intuition, here are some examples of the groupings we want to achieve, assuming max_read = 5
        # 1,2 / 4,5 -> 1,2,3,4,5 (i.e. to read the registers 1, 2, 4 and 5, we'll do a single read spanning 1-5)
        # 1,2 / 5,6,7,8 -> 1,2 / 5,6,7,8
        # 1,2 / 5,6,7,8,9 -> 1,2 / 5,6,7,8,9
        # 1,2 / 5,6,7,8,9,10 -> 1,2,3,4,5 / 6,7,8,9,10
        # 1,2,3 / 5,6,7 / 9,10 -> 1,2,3,4,5 / 6,7,8,9,10

        # The problem as a whole looks like it's NP-hard (although I can't find a name for it).
        # We're therefore going to use a fairly simple algorithm which just makes each read as large as it can be.

        start_address: int | None = None
        read_size = 0
        for address in self.all_addresses:
            if start_address is None:
                start_address, read_size = address, 1
            elif address <= start_address + max_read - 1:
                read_size = address - start_address + 1
            else:
                # There's a previous read, and we can't extend it to cover this address
                yield (start_address, read_size)
                start_address, read_size = address, 1

            if read_size == max_read:
                yield (start_address, read_size)
                start_address, read_size = None, 0

        if start_address is not None:
            yield (start_address, read_size)

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
            model="H1",
            connection_types=[
                InverterModelConnectionTypeProfile(
                    connection_type=CONNECTION_TYPES["AUX"],
                    entity_descriptions=xx1_aux_entity_descriptions.H1
                    + xx1_aux_entity_descriptions.H1_AC1,
                    charge_periods=xx1_aux_charge_periods.H1_AC1,
                ),
                InverterModelConnectionTypeProfile(
                    connection_type=CONNECTION_TYPES["LAN"],
                    entity_descriptions=xx1_lan_entity_descriptions.H1
                    + xx1_lan_entity_descriptions.H1_AC1,
                    charge_periods=[],
                ),
            ],
        ),
        InverterModelProfile(
            model="AC1",
            connection_types=[
                InverterModelConnectionTypeProfile(
                    connection_type=CONNECTION_TYPES["AUX"],
                    entity_descriptions=xx1_aux_entity_descriptions.H1_AC1,
                    charge_periods=xx1_aux_charge_periods.H1_AC1,
                ),
                InverterModelConnectionTypeProfile(
                    connection_type=CONNECTION_TYPES["LAN"],
                    entity_descriptions=xx1_lan_entity_descriptions.H1_AC1,
                    charge_periods=[],
                ),
            ],
        ),
        InverterModelProfile(
            model="AIO-H1",
            connection_types=[
                InverterModelConnectionTypeProfile(
                    connection_type=CONNECTION_TYPES["AUX"],
                    entity_descriptions=xx1_aux_entity_descriptions.H1
                    + xx1_aux_entity_descriptions.H1_AC1,
                    charge_periods=xx1_aux_charge_periods.H1_AC1,
                ),
                InverterModelConnectionTypeProfile(
                    connection_type=CONNECTION_TYPES["LAN"],
                    entity_descriptions=xx1_lan_entity_descriptions.H1
                    + xx1_lan_entity_descriptions.H1_AC1,
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
